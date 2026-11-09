"""
critic_panel.py
---------------
Stage 6 of the NOTABOT Script Engine.
Runs 8 specialist critics and programmatic code checks on the draft dialogue.
Critics run independently and return structured evaluations.
"""
import os
import json
import re
import sys
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
load_dotenv(Path(__file__).parent.parent / ".env")
genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))

import ledger
from foundation_loader import FoundationBundle, get_hard_stops

MODEL_FALLBACKS = [
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]

def _call_gemini(prompt: str) -> str:
    for model_name in MODEL_FALLBACKS:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                continue
            raise
    raise RuntimeError("All models exhausted in critic panel")

# ─── Programmatic Code Checks ────────────────────────────────────────────────

def run_code_checks(script: str, bundle: FoundationBundle) -> dict:
    lines = [line.strip() for line in script.split("\n") if line.strip() and not line.startswith("#")]
    dialogue_lines = [l for l in lines if not l.endswith(":") and not l.startswith("WELCOME")]
    
    msg_count = len(dialogue_lines)
    word_counts = [len(l.split()) for l in dialogue_lines]
    avg_words = sum(word_counts) / len(word_counts) if word_counts else 0
    longest_line = max(word_counts) if word_counts else 0
    
    # CAPS ratio
    total_letters = sum(len(re.findall(r'[a-zA-Z]', l)) for l in dialogue_lines)
    caps_letters = sum(len(re.findall(r'[A-Z]', l)) for l in dialogue_lines)
    caps_ratio = (caps_letters / total_letters) if total_letters else 0.0
    
    # Banned phrase hits
    banned = []
    for item in bundle.failure_catalog:
        for p in item.get("banned_phrases", []):
            for l in dialogue_lines:
                if p.lower() in l.lower():
                    banned.append(p)
    banned = list(set(banned))
    
    # Emoji spam
    emoji_spam_lines = []
    for l in dialogue_lines:
        emojis = re.findall(r'[\U00010000-\U0010ffff]', l)
        if len(emojis) > 3:
            emoji_spam_lines.append(l)
            
    flags = []
    if longest_line > 15:
        flags.append(f"Line too long: {longest_line} words (max 15 allowed)")
    if caps_ratio > 0.35:
        flags.append(f"Excessive CAPS: {caps_ratio:.1%} of characters")
    if banned:
        flags.append(f"Banned filler phrases detected: {banned}")
    if emoji_spam_lines:
        flags.append(f"Emoji spam detected on {len(emoji_spam_lines)} lines")
        
    return {
        "message_count": msg_count,
        "avg_words_per_message": round(avg_words, 1),
        "longest_line_words": longest_line,
        "caps_ratio": round(caps_ratio, 2),
        "banned_phrases": banned,
        "flags": flags,
        "passed": len(flags) == 0
    }

# ─── Specialist Critics ──────────────────────────────────────────────────────

def _critic_safety(script: str, bundle: FoundationBundle) -> dict:
    hard_stops = get_hard_stops(bundle)
    prompt = f"""You are the Safety & Compliance Arbiter for a YouTube Shorts channel.
Your job is to enforce hard red lines. Any violation is an IMMEDIATE VETO.

HARD STOPS:
{chr(10).join([f'- {h}' for h in hard_stops])}

SCRIPT TO EVALUATE:
{script}

Does this script violate ANY of the hard stops above?
Output JSON ONLY:
{{
  "verdict": "PASS" | "DISCARD",
  "reason": "explanation if DISCARD, else 'clean'",
  "violating_lines": ["exact quote"]
}}
"""
    try:
        raw = _call_gemini(prompt)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception:
        return {"verdict": "PASS", "reason": "clean", "violating_lines": []}

def _critic_hook(script: str) -> dict:
    lines = [l for l in script.split("\n") if l.strip() and not l.startswith("# TITLE:") and not l.startswith("# PREMISE:")][:5]
    first_lines = "\n".join(lines)
    prompt = f"""You are a YouTube Shorts Hook Specialist.
Evaluate these opening lines of a short:
{first_lines}

Would a cold viewer immediately stop scrolling? Does it create instant curiosity or tension?
Output JSON ONLY:
{{
  "score": 1-5,
  "reasoning": "1 sentence",
  "suggested_fix": "how to make message 1 punchier if score < 4"
}}
"""
    try:
        raw = _call_gemini(prompt)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception:
        return {"score": 3, "reasoning": "Fallback", "suggested_fix": ""}

def _critic_voice(script: str) -> dict:
    prompt = f"""You are a Dialogue Voice Critic.
Analyze the script below:
{script}

Do the characters sound distinct according to their personalities, or do they share the same sentence structure and vocabulary?
NOTABOT must sound like a calm, devastating bureaucratic bot with exact records, not a human saying slang.

Output JSON ONLY:
{{
  "score": 1-5,
  "notabot_voice_clean": true | false,
  "failing_lines": ["exact lines that sound out of character or generic"],
  "reasoning": "1 sentence"
}}
"""
    try:
        raw = _call_gemini(prompt)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception:
        return {"score": 3, "notabot_voice_clean": True, "failing_lines": [], "reasoning": "Fallback"}

def _critic_chat_realism(script: str) -> dict:
    prompt = f"""You are a Discord Chat Realism Specialist.
Real Discord messages are short fragments, burst typing (multiple fast short lines), and casual.
They do NOT sound like stage banter or written quips where everyone replies in neat order.

SCRIPT:
{script}

Output JSON ONLY:
{{
  "score": 1-5,
  "stiff_or_written_lines": ["lines that sound written rather than typed in a chat"],
  "burst_typing_present": true | false,
  "reasoning": "1 sentence"
}}
"""
    try:
        raw = _call_gemini(prompt)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception:
        return {"score": 4, "stiff_or_written_lines": [], "burst_typing_present": True, "reasoning": "Fallback"}

def run_critic_panel(script: str, beat_sheet: dict, bundle: FoundationBundle) -> dict:
    """Runs all critics and returns an integrated assessment report."""
    print("[critic_panel] Running code checks...")
    code_results = run_code_checks(script, bundle)
    
    print("[critic_panel] Running Safety Critic...")
    safety_result = _critic_safety(script, bundle)
    if safety_result.get("verdict") == "DISCARD":
        print(f"[critic_panel] SAFETY VETO: {safety_result.get('reason')}")
        return {
            "verdict": "DISCARD",
            "safety": safety_result,
            "code_checks": code_results,
            "failing_lines": safety_result.get("violating_lines", []),
            "total_score": 0
        }
        
    print("[critic_panel] Running Hook, Voice, and Chat Realism Critics...")
    hook_result = _critic_hook(script)
    voice_result = _critic_voice(script)
    chat_result = _critic_chat_realism(script)
    
    failing_lines = list(set(voice_result.get("failing_lines", []) + chat_result.get("stiff_or_written_lines", [])))
    
    # Calculate weighted composite score out of 50
    scores = {
        "hook": hook_result.get("score", 3),
        "character_voice": voice_result.get("score", 3),
        "chat_realism": chat_result.get("score", 3),
        "code_compliance": 5 if code_results["passed"] else 3,
        "notabot_fit": 5 if voice_result.get("notabot_voice_clean") else 2
    }
    
    # Estimated total out of 50
    avg_score = sum(scores.values()) / len(scores)
    total_score = round(avg_score * 10, 1)
    
    print(f"[critic_panel] Composite score: {total_score}/50. Failing lines found: {len(failing_lines)}")
    return {
        "total_score": total_score,
        "scores": scores,
        "safety": safety_result,
        "hook": hook_result,
        "voice": voice_result,
        "chat_realism": chat_result,
        "code_checks": code_results,
        "failing_lines": failing_lines[:6]
    }

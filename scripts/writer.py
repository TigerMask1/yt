"""
writer.py
---------
Stage 5 of the NOTABOT Script Engine.
The strongest available model writes dialogue ONLY.
Receives beat sheet, cast cards, bible, tone anchors, and failure catalog.
Outputs clean dialogue with semantic beat tags (no duration or sound syntax).
"""
import os
import json
import sys
from pathlib import Path
import google.generativeai as genai
import model_config
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
load_dotenv(Path(__file__).parent.parent / ".env")
genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))

import ledger
import trend_checker
from foundation_loader import FoundationBundle, get_cast_cards_for, get_tone_anchors, get_failure_patterns
from showrunner import ConstraintCard

# Model fallbacks from model_config (single source of truth)
MODEL_FALLBACKS = model_config.get_model_fallbacks("writer")

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
    raise RuntimeError("All models exhausted in writer")

def write_dialogue(pitch: dict, beat_sheet: dict, card: ConstraintCard, bundle: FoundationBundle) -> str:
    """Writes the full dialogue draft based on the beat sheet and craft principles."""
    cast_cards = get_cast_cards_for(bundle, card.cast_pair)
    tone_anchors = get_tone_anchors(bundle, n=2)
    failure_patterns = get_failure_patterns(bundle)
    phrases_to_avoid = ledger.get_phrases_to_avoid()[:50]
    trend_vibe = trend_checker.get_vibe_injection_for_prompt()
    
    target_count = "20 to 25 messages total" if card.target_length == "short" else "65 to 80 messages total"
    
    prompt = f"""You are the master Dialogue Writer for NOTABOT YouTube Shorts.
You write dialogue ONLY. You do NOT write sound effects, durations, or timestamps.

EPISODE PREMISE: {pitch.get('premise')}
SETTING/THEME: {card.setting}
NOTABOT ROLE: {card.notabot_role}
COMEDY MECHANISM: {card.comedy_mechanism}

BEAT SHEET TO FOLLOW EXACTLY:
{json.dumps(beat_sheet, indent=2)}

CAST CARDS:
{json.dumps(cast_cards, indent=2)}

VOICE & DIALOGUE STYLE (CRITICAL):
- AUTHENTIC INTERNET ENERGY: Humans talk like real people on Discord / gaming lobbies / streams. Short, snappy, aggressive, funny. They scream and swear casually when things escalate ('fk you', 'what the fk', 'bitch', 'stfu', 'lmao gtfo', 'bro wtf', 'you\'re cooked').
- NO FORMAL ESSAYS: Never write long corporate paragraphs or polite banter. Maximize drama, panic, and fast pacing.
- NOTABOT CONTRAST: NOTABOT NEVER swears, never screams, never uses slang ('bro', 'lol', 'ngl', 'bruh'). It speaks with chilling, deadpan bureaucratic precision (case numbers, audit logs, error codes, calm delivery of ruin). That extreme contrast against screaming swearing humans is the entire comedy engine.
- PACING & BURSTS: Most messages 3-8 words. Split thoughts across 2-4 rapid burst messages under the speaker's name. Use ALL CAPS when ducky or dumby is genuinely screaming in panic.
- TARGET LENGTH: {target_count}.

DO NOT DO (FAILURE CATALOG):
{chr(10).join([f'- {p}' for p in failure_patterns[:8]])}

PHRASES TO AVOID (USED RECENTLY IN OTHER EPISODES):
{', '.join(phrases_to_avoid[:30]) if phrases_to_avoid else 'None yet.'}

CONTEMPORARY INTERNET ENERGY & TRENDS:
{trend_vibe}

BEAT TAGS:
Attach optional tags to key lines in square brackets at the end:
- [beat_tag:hook]
- [beat_tag:plant]
- [beat_tag:escalation]
- [beat_tag:reveal]
- [beat_tag:callback]
- [beat_tag:punchline]
- [beat_tag:button]

OUTPUT FORMAT:
# TITLE: Viral Title Here #shorts
# PREMISE: One-sentence premise

SpeakerName:
first line [beat_tag:hook]
second burst line

OtherSpeaker:
their line [beat_tag:plant]

Write the script now:
"""
    print("[writer] Generating dialogue with primary model...")
    script = _call_gemini(prompt)
    if script.startswith("```"):
        script = script.split("```")[1]
        if script.startswith("txt"):
            script = script[3:]
    return script.strip()

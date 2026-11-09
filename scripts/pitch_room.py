"""
pitch_room.py
-------------
Stage 2 of the NOTABOT Script Engine.
Runs 3 independent pitcher agents with different creative angles.
Injects real-time trend intelligence and recent ledger memory.
Deduplicates pitches among themselves and against past episodes.
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
from foundation_loader import FoundationBundle, get_cast_cards_for
from showrunner import ConstraintCard

# Model fallbacks from model_config (single source of truth)
MODEL_FALLBACKS = model_config.get_model_fallbacks("pitcher_1")

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
    raise RuntimeError("All models exhausted in pitch room")

PITCHER_ANGLES = {
    "A": {
        "name": "Deadpan Bureaucrat",
        "focus": "Focus on NOTABOT acting as a hyper-competent, calm, terrifying administrative menace. Invented policies, audit log receipts, error codes, and treating human catastrophe as an administrative ticket to resolve."
    },
    "B": {
        "name": "Escalation Engineer",
        "focus": "Focus on the steepest possible escalation ladder. A seemingly tiny, innocent misunderstanding or ordinary chat message that snowballs rapidly into an irreversible crisis with extreme stakes."
    },
    "C": {
        "name": "Character Clash",
        "focus": "Focus on the specific interpersonal clash and flaws of the drawn cast. Expose someone's insecurity, fake confidence, or ridiculous habit in a deeply specific and hilarious way."
    }
}

def _run_pitcher(angle_key: str, card: ConstraintCard, bundle: FoundationBundle, trend_vibe: str, ledger_summary: str) -> list:
    angle_info = PITCHER_ANGLES[angle_key]
    cast_cards = get_cast_cards_for(bundle, card.cast_pair)
    
    prompt = f"""You are a comedy Pitch Writer for the NOTABOT Discord-chat YouTube Shorts channel.
Your creative angle: {angle_info['name']}
Angle Focus: {angle_info['focus']}

EPISODE CONSTRAINTS:
- Story Shape: {card.story_shape}
- NOTABOT Role: {card.notabot_role}
- Comedy Mechanism: {card.comedy_mechanism}
- Setting: {card.setting}
- Twist Rule: {card.twist_rule}
- Cast: {', '.join(card.cast_pair)}
{f"- Wild Card: {card.wild_card}" if card.wild_card else ""}

CURRENT INTERNET VIBE & COMEDY TRENDS (use this energy):
{trend_vibe}

PAST EPISODE LEDGER (DO NOT REPEAT THESE TOPICS/PREMISES):
{ledger_summary}

CAST DETAILS:
{json.dumps(cast_cards, indent=2)}

PITCH REQUIREMENTS & VIBE:
- NOTABOT: Bureaucratic, cold, omniscient intelligence. Never swears, never uses slang.
- HUMANS: Highly energetic, funny, unhinged internet dialogue. Real swearing, screams, and fast banter when escalating.
- BROAD THEMES: Move beyond simple Discord server banter! Leverage diverse settings (gaming lobbies, trials, world summits, reality TV, corporate meltdowns, challenges).
- TREND & VIRALITY: Tap into fresh meme concepts, viral behavior archetypes, and comment-worthy hooks to maximize views.
- No real living individuals named directly.

Generate exactly 3 wildly different, hilarious pitches.
Output ONLY a JSON array of 3 objects with this exact schema:
[
  {{
    "premise": "2-sentence summary of the premise and specific conflict",
    "hook_message": "exact first message in the video that stops the scroll",
    "planted_detail": "specific subtle detail planted early that pays off at the end",
    "escalation_ladder": [
      "beat 1: how conflict opens",
      "beat 2: who makes it dumber/worse",
      "beat 3: peak disaster point"
    ],
    "final_message": "exact punchline/button last message of the video",
    "surprise_factor": "why the ending cannot be predicted from the start"
  }}
]
"""
    raw = _call_gemini(prompt)
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    try:
        pitches = json.loads(raw)
        for i, p in enumerate(pitches):
            p["id"] = f"pitch_{angle_key}_{i+1}"
            p["pitcher_angle"] = angle_info["name"]
        return pitches
    except Exception as e:
        print(f"[pitch_room] Error parsing pitches from {angle_key}: {e}")
        return []

def _deduplicate_pitches(pitches: list, ledger_summary: str) -> list:
    if len(pitches) <= 3:
        return pitches
        
    prompt = f"""You are a Head of Story reviewing candidate pitches for a comedy YouTube Shorts channel.
Here are {len(pitches)} candidate pitches:
{json.dumps(pitches, indent=2)}

PAST EPISODES TO AVOID DUPLICATING:
{ledger_summary}

Tasks:
1. Identify any pitches that are too similar to each other or to past episodes.
2. Select the top 5 to 7 most original, distinct, and funny pitches.
3. Eliminate redundant or repetitive pitches.

Return ONLY a JSON array of the surviving pitch IDs, e.g. ["pitch_A_1", "pitch_B_2", "pitch_C_1"]
"""
    try:
        raw = _call_gemini(prompt)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        surviving_ids = json.loads(raw.strip())
        survivors = [p for p in pitches if p.get("id") in surviving_ids]
        return survivors if survivors else pitches[:5]
    except Exception as e:
        print(f"[pitch_room] Deduplication fallback: {e}")
        return pitches[:5]

def generate_pitches(card: ConstraintCard, bundle: FoundationBundle) -> list:
    """Main entrypoint: runs 3 pitchers and deduplicates results."""
    print("[pitch_room] Gathering trend intel and past ledger...")
    trend_vibe = trend_checker.get_vibe_injection_for_prompt()
    ledger_summary = ledger.get_ledger_summary_for_prompt(n=10)
    
    all_pitches = []
    for angle_key in ["A", "B", "C"]:
        print(f"[pitch_room] Running Pitcher {angle_key} ({PITCHER_ANGLES[angle_key]['name']})...")
        pitches = _run_pitcher(angle_key, card, bundle, trend_vibe, ledger_summary)
        all_pitches.extend(pitches)
        
    print(f"[pitch_room] Generated {len(all_pitches)} raw pitches. Deduplicating...")
    surviving = _deduplicate_pitches(all_pitches, ledger_summary)
    print(f"[pitch_room] {len(surviving)} pitches advanced to Pitch Court.")
    return surviving

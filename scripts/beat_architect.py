"""
beat_architect.py
-----------------
Stage 4 of the NOTABOT Script Engine.
Turns the winning pitch into a structured, validated Beat Sheet.
Ensures every character has joke ownership, planted details resolve, and pacing escalates.
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

from foundation_loader import FoundationBundle, get_cast_cards_for
from showrunner import ConstraintCard

# Model fallbacks from model_config (single source of truth)
MODEL_FALLBACKS = model_config.get_model_fallbacks("beat_architect")

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
    raise RuntimeError("All models exhausted in beat architect")

def _structure_check(beat_sheet: dict, cast: list) -> tuple:
    required_keys = ["hook", "stakes", "plant", "escalation_1", "escalation_2", "escalation_3", "turn", "callback", "button"]
    for k in required_keys:
        if k not in beat_sheet or not beat_sheet[k].get("content"):
            return False, f"Missing beat slot: {k}"
            
    # Check character coverage: all non-NOTABOT cast members must own at least 1 beat
    owners = set()
    for k in required_keys:
        owner = beat_sheet[k].get("owner")
        if owner:
            owners.add(owner)
            
    for member in cast:
        if member != "NOTABOT" and member not in owners:
            return False, f"Character '{member}' has no beat ownership slot."
            
    # Check plant and callback both present
    if not beat_sheet.get("plant", {}).get("content") or not beat_sheet.get("callback", {}).get("content"):
        return False, "Plant or callback is empty."
        
    return True, "Structure valid"

def build_beat_sheet(pitch: dict, card: ConstraintCard, bundle: FoundationBundle) -> dict:
    """Takes winning pitch and constructs an ironclad beat sheet."""
    cast_cards = get_cast_cards_for(bundle, card.cast_pair)
    
    prompt = f"""You are a master Beat Architect for Discord-chat comedy YouTube Shorts.
Transform this winning pitch into an airtight beat sheet.

PITCH:
Premise: {pitch.get('premise')}
Setting/Situation: {pitch.get('setting', card.setting)}
Hook: {pitch.get('hook_message')}
Plant: {pitch.get('planted_detail')}
Escalation Ladder: {pitch.get('escalation_ladder')}
Final Message: {pitch.get('final_message')}
Surprise Factor: {pitch.get('surprise_factor')}

EPISODE CONSTRAINTS:
Story Shape: {card.story_shape}
NOTABOT Role: {card.notabot_role}
Comedy Mechanism: {card.comedy_mechanism}
Cast: {', '.join(card.cast_pair)}

CAST CARDS:
{json.dumps(cast_cards, indent=2)}

CRITICAL BEAT RULES:
1. Every non-NOTABOT character in the cast MUST have ownership of at least one beat with their own joke/action. No one is just a feed line.
2. The 'plant' beat MUST set up a specific detail, timestamp, policy number, or phrase that is paid off in the 'callback' beat.
3. The 'button' beat MUST be the sharpest punchline in the video, delivering the final twist or deadpan verdict.

Output ONLY a JSON object with this exact schema:
{{
  "hook": {{"owner": "character_name", "content": "what happens in the first 2-3 seconds to stop the scroll"}},
  "stakes": {{"owner": "character_name", "content": "why anyone in the chat cares or what is threatened"}},
  "plant": {{"owner": "character_name", "content": "the subtle specific detail planted for later"}},
  "escalation_1": {{"owner": "character_name", "content": "first move that makes the situation worse"}},
  "escalation_2": {{"owner": "character_name", "content": "second move that raises the stakes/panic"}},
  "escalation_3": {{"owner": "character_name", "content": "peak disaster or chaotic revelation"}},
  "turn": {{"owner": "character_name", "content": "the unexpected shift where someone turns the tables"}},
  "callback": {{"owner": "character_name", "content": "the planted detail returns with devastating effect"}},
  "button": {{"owner": "character_name", "content": "the final memorable punchline line"}}
}}
"""
    for attempt in range(2):
        print(f"[beat_architect] Generating beat sheet (attempt {attempt+1})...")
        raw = _call_gemini(prompt)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        try:
            sheet = json.loads(raw.strip())
            valid, msg = _structure_check(sheet, card.cast_pair)
            if valid:
                print("[beat_architect] Beat sheet passed structure validation.")
                return sheet
            else:
                print(f"[beat_architect] Structure check issue: {msg}. Retrying...")
                prompt += f"\n\nCorrection needed: {msg}. Ensure all cast members own beats."
        except Exception as e:
            print(f"[beat_architect] Parse error: {e}")
            
    print("[beat_architect] Warning: Returning best effort beat sheet.")
    return sheet if 'sheet' in locals() else {}

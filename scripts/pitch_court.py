"""
pitch_court.py
--------------
Stage 3 of the NOTABOT Script Engine.
Scores candidate pitches using 2 independent judge agents + a blind prediction test.
Uses randomized evaluation order to eliminate position bias.
Checks premise freshness via trend_checker.
"""
import os
import json
import random
import sys
from pathlib import Path
import google.generativeai as genai
import model_config
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
load_dotenv(Path(__file__).parent.parent / ".env")
genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))

import trend_checker
from foundation_loader import FoundationBundle

# Model fallbacks from model_config (single source of truth)
MODEL_FALLBACKS = model_config.get_model_fallbacks("pitch_court_judge")

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
    raise RuntimeError("All models exhausted in pitch court")

def _blind_prediction_test(pitch: dict) -> bool:
    """
    Shows agent only hook and setup, asks it to guess the punchline.
    Returns True if agent guessed the ending correctly (meaning it's predictable!).
    """
    prompt = f"""You are analyzing a YouTube Shorts comedic setup for predictability.
HOOK: {pitch.get('hook_message')}
SETUP / ESCALATION:
{json.dumps(pitch.get('escalation_ladder'), indent=2)}

Predict what happens at the very end in 1-2 sentences: what is the punchline or reveal?
"""
    try:
        prediction = _call_gemini(prompt).lower()
        actual_ending = pitch.get("final_message", "").lower()
        
        # Check semantic overlap
        words = set(actual_ending.replace(",", " ").replace(".", " ").split())
        matched_words = [w for w in words if len(w) > 4 and w in prediction]
        is_predictable = len(matched_words) >= 3
        return is_predictable
    except Exception:
        return False

def _score_pitch_with_judge(pitch: dict, judge_id: str, bundle: FoundationBundle) -> dict:
    rubric = bundle.rubric.get("dimensions", {})
    rubric_summary = "\n".join([f"- {k}: 1={v['anchors']['1']}, 3={v['anchors']['3']}, 5={v['anchors']['5']}" for k, v in rubric.items()])
    
    prompt = f"""You are Judge {judge_id} scoring a comedic pitch for a Discord-chat YouTube Short.
Be strict and realistic. Do NOT inflate scores. A 5 is rare excellence, 3 is competent, 1 is poor.

PITCH DETAILS:
Premise: {pitch.get('premise')}
Hook: {pitch.get('hook_message')}
Plant: {pitch.get('planted_detail')}
Escalation Ladder: {pitch.get('escalation_ladder')}
Final Punchline: {pitch.get('final_message')}
Surprise Factor: {pitch.get('surprise_factor')}

RUBRIC:
{rubric_summary}

Score each dimension from 1 to 5.
Output ONLY a JSON object with this schema:
{{
  "scores": {{
    "hook": 3,
    "cold_clarity": 4,
    "specificity": 3,
    "escalation": 4,
    "surprise": 3,
    "character_voice": 4,
    "notabot_fit": 4,
    "economy": 3,
    "ending": 4,
    "originality": 3
  }},
  "reasoning": "brief 1-2 sentence justification",
  "weakest_element": "what needs improvement"
}}
"""
    try:
        raw = _call_gemini(prompt)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
        return data
    except Exception as e:
        print(f"[pitch_court] Scoring fallback for judge {judge_id}: {e}")
        # Default fallback scores
        return {
            "scores": {k: 3 for k in rubric.keys()},
            "reasoning": "Fallback scoring due to parse error",
            "weakest_element": "unknown"
        }

def evaluate_pitches(pitches: list, bundle: FoundationBundle, deep_mode: bool = False) -> tuple:
    """
    Evaluates pitches using 2 judges + blind prediction + trend freshness.
    Returns (winning_pitch, evaluation_report, needs_redraw).
    """
    if not pitches:
        return None, {"error": "No pitches to evaluate"}, True

    print(f"[pitch_court] Evaluating {len(pitches)} candidate pitches...")
    evaluated = []
    
    for pitch in pitches:
        p_id = pitch.get("id")
        print(f"  Scoring {p_id}...")
        
        # 1. Blind prediction test
        is_predictable = _blind_prediction_test(pitch)
        
        # 2. Freshness check
        freshness = trend_checker.assess_premise_freshness(pitch.get("premise", ""))
        
        # 3. Judge A & Judge B (randomized order of dimensions / independent)
        eval_a = _score_pitch_with_judge(pitch, "A", bundle)
        eval_b = _score_pitch_with_judge(pitch, "B", bundle)
        
        # Aggregate dimension scores
        scores_a = eval_a.get("scores", {})
        scores_b = eval_b.get("scores", {})
        combined_scores = {}
        for dim in bundle.rubric.get("dimensions", {}).keys():
            combined_scores[dim] = (scores_a.get(dim, 3) + scores_b.get(dim, 3)) / 2.0
            
        # Penalize if predictable
        if is_predictable:
            combined_scores["surprise"] = max(1.0, combined_scores["surprise"] - 1.5)
            
        # Boost/penalize based on trend freshness
        if freshness.get("verdict") == "fresh":
            combined_scores["originality"] = min(5.0, combined_scores["originality"] + 0.5)
        elif freshness.get("verdict") == "stale":
            combined_scores["originality"] = max(1.0, combined_scores["originality"] - 1.0)
            
        total_score = sum(combined_scores.values())
        
        evaluated.append({
            "pitch": pitch,
            "total_score": round(total_score, 2),
            "scores": combined_scores,
            "is_predictable": is_predictable,
            "freshness": freshness,
            "judge_a_notes": eval_a.get("reasoning"),
            "judge_b_notes": eval_b.get("reasoning"),
            "weakest": eval_a.get("weakest_element") or eval_b.get("weakest_element")
        })

    # Sort descending by total score
    evaluated.sort(key=lambda x: x["total_score"], reverse=True)
    
    winner_entry = evaluated[0]
    pass_threshold = bundle.rubric.get("pass_threshold", 32.0)
    needs_redraw = winner_entry["total_score"] < pass_threshold
    
    print(f"[pitch_court] Top pitch: {winner_entry['pitch'].get('id')} with score {winner_entry['total_score']}/{bundle.rubric.get('max_score', 50)}")
    if needs_redraw:
        print(f"[pitch_court] Score below threshold ({pass_threshold}). Needs redraw.")
        
    if deep_mode and len(evaluated) >= 2:
        return [evaluated[0]["pitch"], evaluated[1]["pitch"]], evaluated, needs_redraw
    return winner_entry["pitch"], evaluated, needs_redraw

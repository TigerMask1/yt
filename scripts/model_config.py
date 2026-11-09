"""
model_config.py
───────────────
Single source of truth for model IDs and their assignment across the pipeline.

Your 3 models and daily quotas (free tier):
  TIER_CREATIVE  → gemini-3.8-flash        20 req/day  ← use sparingly, highest quality
  TIER_STANDARD  → gemini-3.5-flash-lite  500 req/day  ← workhorse for most calls
  TIER_LIGHT     → gemini-3.1-flash-lite  500 req/day  ← rule-based critics, dedupe, checks

Budget per episode (Standard mode, 22 calls):
  TIER_CREATIVE : ~4 calls  (writer x1, punch-up line judge x2, top pitcher x1)
  TIER_STANDARD : ~9 calls  (beat architect, 2 pitchers, 2 court judges, 4 critics)
  TIER_LIGHT    : ~9 calls  (dedupe, cold-view/safety/struct/repetition critics, assembler checks)

5 episodes/day:
  TIER_CREATIVE : 4 × 5 = 20  ← exactly the limit
  TIER_STANDARD : 9 × 5 = 45  ← well within 500
  TIER_LIGHT    : 9 × 5 = 45  ← well within 500

Override model IDs via environment variables:
  NOTABOT_MODEL_CREATIVE   (default: gemini-3.8-flash)
  NOTABOT_MODEL_STANDARD   (default: gemini-3.5-flash-lite)
  NOTABOT_MODEL_LIGHT      (default: gemini-3.1-flash-lite)
"""
import os

# ── Model IDs ──────────────────────────────────────────────────────────────────
TIER_CREATIVE = os.environ.get("NOTABOT_MODEL_CREATIVE", "gemini-3.8-flash")
TIER_STANDARD = os.environ.get("NOTABOT_MODEL_STANDARD", "gemini-3.5-flash-lite")
TIER_LIGHT    = os.environ.get("NOTABOT_MODEL_LIGHT",    "gemini-3.1-flash-lite")

# Fallback chain for each tier (tries next tier down on 429/quota)
CREATIVE_FALLBACKS = [TIER_CREATIVE, TIER_STANDARD, TIER_LIGHT]
STANDARD_FALLBACKS = [TIER_STANDARD, TIER_LIGHT]
LIGHT_FALLBACKS    = [TIER_LIGHT, TIER_STANDARD]

# ── Per-stage assignments ──────────────────────────────────────────────────────
#
# CREATIVE tier (use 20 req/day wisely):
#   - writer.py          → dialogue generation (the most important creative call)
#   - punch_up.py        → line judge (choosing the best of 5 alternatives)
#   - pitch_room.py      → pitcher #1 / Deadpan Bureaucrat (leads, sets the tone)
#
# STANDARD tier:
#   - beat_architect.py  → beat sheet (structural creativity, needs quality)
#   - pitch_room.py      → pitcher #2 and #3 (Escalation + Character Clash)
#   - pitch_court.py     → both judges + blind predictor
#   - critic_panel.py    → hook, voice, specificity, NOTABOT, chat-realism critics
#
# LIGHT tier:
#   - pitch_room.py      → dedupe agent
#   - critic_panel.py    → cold viewer, structure, predictability, repetition, safety critics
#   - trend_checker.py   → trend assessment (uses training knowledge, no search API needed)
#   - analytics_collector.py → comment classifier
#   - canary.py          → golden-set judge ranking

STAGE_MODEL = {
    "writer":               CREATIVE_FALLBACKS,
    "punch_up_line_judge":  CREATIVE_FALLBACKS,
    "pitcher_1":            CREATIVE_FALLBACKS,   # Deadpan Bureaucrat
    "pitcher_2":            STANDARD_FALLBACKS,   # Escalation Engineer
    "pitcher_3":            STANDARD_FALLBACKS,   # Character Clash
    "dedupe":               LIGHT_FALLBACKS,
    "beat_architect":       STANDARD_FALLBACKS,
    "pitch_court_judge":    STANDARD_FALLBACKS,
    "blind_predictor":      STANDARD_FALLBACKS,
    "critic_hook":          STANDARD_FALLBACKS,
    "critic_voice":         STANDARD_FALLBACKS,
    "critic_specificity":   STANDARD_FALLBACKS,
    "critic_notabot":       STANDARD_FALLBACKS,
    "critic_chat_realism":  STANDARD_FALLBACKS,
    "critic_cold_viewer":   LIGHT_FALLBACKS,
    "critic_structure":     LIGHT_FALLBACKS,
    "critic_predictability":LIGHT_FALLBACKS,
    "critic_repetition":    LIGHT_FALLBACKS,
    "critic_safety":        LIGHT_FALLBACKS,      # rule-based, light model fine
    "trend_checker":        LIGHT_FALLBACKS,
    "comment_classifier":   LIGHT_FALLBACKS,
    "canary":               LIGHT_FALLBACKS,
    "punch_up_writer":      STANDARD_FALLBACKS,   # generates 5 alternatives (not judge)
}


def get_model_fallbacks(stage: str) -> list:
    """Return the ordered model fallback list for a given pipeline stage."""
    return STAGE_MODEL.get(stage, STANDARD_FALLBACKS)


def call_gemini(stage: str, prompt: str, **kwargs):
    """
    Convenience wrapper: tries each model in the stage's fallback chain.
    Passes **kwargs to generate_content (e.g. generation_config, tools).
    Returns (response_text, model_used).
    """
    import google.generativeai as genai
    models = get_model_fallbacks(stage)
    last_err = None
    for model_id in models:
        try:
            model = genai.GenerativeModel(model_id)
            response = model.generate_content(prompt, **kwargs)
            return response.text, model_id
        except Exception as e:
            err = str(e)
            if any(x in err for x in ("429", "quota", "rate", "RESOURCE_EXHAUSTED")):
                print(f"[model_config] {model_id} quota hit for stage '{stage}', trying next...")
                last_err = e
                continue
            raise   # non-quota error: propagate immediately
    raise RuntimeError(
        f"[model_config] All models exhausted for stage '{stage}'. Last error: {last_err}"
    )

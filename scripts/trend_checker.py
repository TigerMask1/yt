"""
trend_checker.py
----------------
Assesses what is fresh, current, or dead for comedy premises.

Strategy (free-tier safe):
  1. TRY Google Search grounding (works on paid tier / some previews).
  2. If unavailable or quota hit, fall back to "Deep Knowledge Mode":
     ask Gemini to reason from its training data with explicit
     uncertainty labelling. This is honest and still useful — Gemini
     has strong knowledge up to its training cut-off and can reason
     about cultural half-lives ("this meme format peaked 2 yrs ago").
  3. All results cached for CACHE_TTL_HOURS so we don't burn quota.

Models used: TIER_LIGHT (gemini-3.1-flash-lite) — trend checks are
analytical, not creative, so we save TIER_CREATIVE for the writer.
"""
import os
import json
import datetime
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv
import model_config

load_dotenv(Path(__file__).parent.parent / ".env")
genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))

CACHE_FILE      = Path(__file__).parent.parent / "assets" / "ledger" / "trend_cache.json"
CACHE_TTL_HOURS = 6     # refresh every 6 hrs
SEARCH_AVAILABLE = None  # None = untested, True/False after first attempt


# ── Cache helpers ──────────────────────────────────────────────────────────────

def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_cache(data: dict):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def _is_cache_fresh(key: str) -> bool:
    cache = _load_cache()
    if key not in cache:
        return False
    cached_at = cache[key].get("cached_at")
    if not cached_at:
        return False
    try:
        age = (datetime.datetime.utcnow()
               - datetime.datetime.fromisoformat(cached_at.replace("Z", "")))
        return age.total_seconds() < CACHE_TTL_HOURS * 3600
    except Exception:
        return False

def _get_cached(key: str) -> dict:
    return _load_cache().get(key, {})

def _set_cached(key: str, data: dict):
    cache = _load_cache()
    cache[key] = {**data, "cached_at": datetime.datetime.utcnow().isoformat() + "Z"}
    _save_cache(cache)


# ── Gemini call with search grounding + graceful fallback ─────────────────────

def _call_gemini(prompt: str, try_search: bool = True) -> tuple:
    """
    Returns (response_text, used_search: bool).
    Tries search grounding first; if unavailable uses plain call.
    Uses TIER_LIGHT — trend checks don't need creative power.
    """
    global SEARCH_AVAILABLE
    models = model_config.get_model_fallbacks("trend_checker")

    # Attempt 1: with search grounding (if not already known to be unavailable)
    if try_search and SEARCH_AVAILABLE is not False:
        for model_id in models:
            try:
                model = genai.GenerativeModel(model_id)
                response = model.generate_content(
                    prompt,
                    tools=[{"google_search": {}}],
                )
                SEARCH_AVAILABLE = True
                return response.text.strip(), True
            except Exception as e:
                err = str(e)
                if any(x in err for x in ("429", "quota", "RESOURCE_EXHAUSTED")):
                    continue
                # Search tool not supported on this tier/model
                if any(x in err.lower() for x in ("tool", "search", "grounding", "not supported")):
                    print("[trend_checker] Search grounding not available on this tier — using knowledge mode.")
                    SEARCH_AVAILABLE = False
                    break
                # Other error — still try without search
                SEARCH_AVAILABLE = False
                break

    # Attempt 2: plain call (Deep Knowledge Mode)
    for model_id in models:
        try:
            model = genai.GenerativeModel(model_id)
            response = model.generate_content(prompt)
            return response.text.strip(), False
        except Exception as e:
            err = str(e)
            if any(x in err for x in ("429", "quota", "RESOURCE_EXHAUSTED")):
                continue
            raise

    raise RuntimeError("[trend_checker] All models exhausted")


def _build_knowledge_mode_prompt(core_prompt: str, today: str) -> str:
    """
    Wraps any trend prompt with explicit instructions for reasoning
    from training knowledge rather than live search.
    Tells the model to be honest about uncertainty.
    """
    return f"""Today's date (approximate): {today}.

IMPORTANT — you do NOT have live web access for this call.
Reason from your training knowledge instead. Be honest:
  - If something was clearly big 1-2 years ago and you can't be sure
    it's still relevant, say so and score it lower.
  - If you're confident something is a durable cultural pattern
    (not tied to a single event), score it higher.
  - Flag anything as "UNCERTAIN" that you're not sure about.

{core_prompt}"""


# ── Core public functions ──────────────────────────────────────────────────────

def get_current_vibe() -> dict:
    """
    Returns what is fresh/trending in internet/YouTube/Discord culture.
    Uses search grounding if available; falls back to Gemini's training knowledge.
    Cached for CACHE_TTL_HOURS.
    """
    cache_key = "current_vibe"
    if _is_cache_fresh(cache_key):
        return _get_cached(cache_key)

    today = datetime.datetime.utcnow().strftime("%B %Y")

    core = f"""Analyze what is currently resonating in these areas for a 15-25 year old Discord/YouTube audience:

1. YouTube Shorts comedy formats — what style/pacing/structure is performing well?
2. Discord / internet culture — what behaviors, archetypes, or situations are meme-worthy?
3. Gaming / tech — any recurring dramas, archetypes, or running jokes that feel current?
4. General internet energy — what is the overall mood and humor style right now?

For each area provide:
- 2-3 DURABLE things (formats/archetypes that are working, not tied to one specific event)
- 1-2 things that feel STALE or peaked recently

Output as JSON ONLY (no markdown, no explanation):
{{
  "hot_right_now": ["thing 1", "thing 2", "thing 3"],
  "comedy_formats_working": ["format 1", "format 2"],
  "stale_avoid": ["stale thing 1", "stale thing 2"],
  "overall_vibe": "one sentence on current internet energy",
  "humor_style": "one sentence on what kind of humor is landing",
  "data_confidence": "search_grounded" or "training_knowledge" or "uncertain"
}}"""

    prompt = _build_knowledge_mode_prompt(core, today)

    try:
        result, used_search = _call_gemini(prompt)
        result = result.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        data = json.loads(result)
        data["_source"] = "search" if used_search else "training_knowledge"
        _set_cached(cache_key, data)
        return data
    except Exception as e:
        print(f"[trend_checker] get_current_vibe failed: {e}")
        return {
            "hot_right_now": [],
            "comedy_formats_working": ["fast-paced dialogue", "unexpected callback"],
            "stale_avoid": [],
            "overall_vibe": "chaotic and fast-paced",
            "humor_style": "deadpan with sudden escalation",
            "data_confidence": "fallback",
            "_source": "fallback",
        }


def assess_premise_freshness(premise: str) -> dict:
    """
    Given a pitch premise, assess whether it feels fresh or stale.
    Returns freshness score, verdict, reasoning, and suggestions.
    """
    cache_key = f"freshness_{abs(hash(premise))}"
    if _is_cache_fresh(cache_key):
        return _get_cached(cache_key)

    today = datetime.datetime.utcnow().strftime("%B %Y")

    core = f"""Evaluate this YouTube Shorts script premise for freshness and cultural timing:

PREMISE: "{premise}"

Questions to answer:
1. Is this type of situation/archetype something the 15-25 YT audience still finds relatable/funny?
2. Has this exact format been OVERDONE in the last 6-12 months on YouTube Shorts?
3. Is there any element of this premise that is tied to a specific event that may have passed?
4. What would make this premise feel MORE timely or more evergreen?

Output as JSON ONLY:
{{
  "freshness_score": <1-10, where 10 = feels completely fresh today>,
  "verdict": "fresh" | "neutral" | "stale",
  "reasoning": "one specific sentence explaining the score",
  "risk_flags": ["specific risk 1 if any"],
  "suggestions": ["one concrete way to sharpen or evergreen-ify the premise"]
}}"""

    prompt = _build_knowledge_mode_prompt(core, today)

    try:
        result, used_search = _call_gemini(prompt)
        result = result.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        data = json.loads(result)
        data["_source"] = "search" if used_search else "training_knowledge"
        _set_cached(cache_key, data)
        return data
    except Exception as e:
        print(f"[trend_checker] assess_premise_freshness failed: {e}")
        return {
            "freshness_score": 5,
            "verdict": "neutral",
            "reasoning": "could not assess",
            "risk_flags": [],
            "suggestions": [],
            "_source": "fallback",
        }


def get_vibe_injection_for_prompt() -> str:
    """
    Returns a short paragraph to inject into writer prompts,
    describing what energy/style/pacing is working right now.
    Does NOT reference specific real people/events.
    Cached for CACHE_TTL_HOURS.
    """
    cache_key = "vibe_injection"
    if _is_cache_fresh(cache_key):
        cached = _get_cached(cache_key)
        return cached.get("text", "")

    today = datetime.datetime.utcnow().strftime("%B %Y")

    core = """Write a 3-4 sentence instruction paragraph for a Discord-chat comedy script writer.
The audience is 15-25 year olds on YouTube Shorts.

Describe:
- The pacing/energy working right now (e.g. "ultra-fast bursts, 1-2 word replies dominate")
- The humor style landing (e.g. "deadpan reactions to absurd bureaucracy")
- One specific thing to AVOID because it feels dated or overused

RULES:
- Do NOT name any real people, games, movies, shows, or events.
- Keep it about STYLE and ENERGY only.
- Write as direct instructions ("Use..." / "Avoid..." / "The audience rewards...")
- 3-4 sentences maximum. No bullet points."""

    prompt = _build_knowledge_mode_prompt(core, today)

    try:
        result, _ = _call_gemini(prompt)
        _set_cached(cache_key, {"text": result})
        return result
    except Exception as e:
        print(f"[trend_checker] get_vibe_injection_for_prompt failed: {e}")
        return (
            "Use ultra-fast pacing — single words and 2-3 word bursts dominate. "
            "The audience rewards deadpan reactions to absurd situations; the funnier character "
            "is usually the quieter one. Avoid any joke that explains itself or uses "
            "all-caps panic as the punchline — that format is fully saturated."
        )


def cross_reference_with_ledger(premise: str, ledger_summary: str) -> str:
    """
    Cross-references a proposed premise against the ledger summary
    to identify repetition risk or missed trend opportunities.
    Returns a short note for the Supervisor's journal.
    """
    today = datetime.datetime.utcnow().strftime("%B %Y")

    core = f"""You are reviewing a YouTube Shorts script premise against past episode history.

PROPOSED PREMISE: {premise}

PAST EPISODE HISTORY (what has already been made):
{ledger_summary}

Assess in 2-3 sentences:
1. Repetition risk — does this premise feel too close to past work? (be specific if yes)
2. Freshness opportunity — is there a durable angle or twist that would make this more original?
3. Clear verdict: proceed / proceed with caution / do not proceed

Do NOT name real people or specific news events. Be direct."""

    prompt = _build_knowledge_mode_prompt(core, today)

    try:
        result, _ = _call_gemini(prompt, try_search=False)   # ledger cross-ref doesn't need search
        return result
    except Exception as e:
        return f"Could not cross-reference: {e}"


def check_archetype_timing(archetype_description: str) -> dict:
    """
    NEW: Given an archetype (e.g. "the orange-guy-in-chief", "the nuke guy"),
    check whether using it feels timely or tired.
    Returns timing score + whether to use it in the next episode.
    """
    today = datetime.datetime.utcnow().strftime("%B %Y")

    core = f"""A comedy script uses public figures as ARCHETYPES (not by name, not referencing specific events).
The archetype described is: "{archetype_description}"

Assess:
1. Is this archetype still culturally legible and funny to a 15-25 audience?
2. Is there any reason it might feel tone-deaf or politically risky right now?
3. What is the safest / funniest angle to use this archetype?

Output as JSON ONLY:
{{
  "timing_score": <1-10, 10 = great time to use this>,
  "verdict": "use" | "use_carefully" | "avoid_for_now",
  "reasoning": "one sentence",
  "safest_angle": "one sentence on the safest / funniest way to use it"
}}"""

    prompt = _build_knowledge_mode_prompt(core, today)

    try:
        result, used_search = _call_gemini(prompt)
        result = result.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        data = json.loads(result)
        data["_source"] = "search" if used_search else "training_knowledge"
        return data
    except Exception as e:
        print(f"[trend_checker] check_archetype_timing failed: {e}")
        return {
            "timing_score": 6,
            "verdict": "use_carefully",
            "reasoning": "could not assess timing",
            "safest_angle": "use behavior pattern only, never reference specific events",
            "_source": "fallback",
        }


if __name__ == "__main__":
    print("Testing trend checker (free-tier safe mode)...")
    vibe = get_current_vibe()
    print(f"Source: {vibe.get('_source', 'unknown')}")
    print(f"Current vibe: {vibe.get('overall_vibe', 'unknown')}")
    print(f"Hot right now: {vibe.get('hot_right_now', [])}")
    injection = get_vibe_injection_for_prompt()
    print(f"\nVibe injection:\n{injection}")

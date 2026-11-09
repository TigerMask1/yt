"""
trend_checker.py
----------------
Uses Gemini with Google Search grounding to assess what is currently
trending, fresh, or dead in internet culture.
This feeds the Showrunner's constraint card and the Writer's prompt.

NO external API keys needed beyond GEMINI_API_KEY.
Uses Gemini's built-in google_search tool for grounding.
"""
import os
import json
import datetime
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))

CACHE_FILE = Path(__file__).parent.parent / "assets" / "ledger" / "trend_cache.json"
CACHE_TTL_HOURS = 6  # refresh trend data every 6 hours

MODEL_FOR_TRENDS = "gemini-2.5-flash"  # needs search grounding support
MODEL_FALLBACK = "gemini-2.0-flash"

# ─── Cache helpers ─────────────────────────────────────────────────────────────

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
        age = datetime.datetime.utcnow() - datetime.datetime.fromisoformat(cached_at.replace("Z", ""))
        return age.total_seconds() < CACHE_TTL_HOURS * 3600
    except Exception:
        return False

def _get_cached(key: str) -> dict:
    return _load_cache().get(key, {})

def _set_cached(key: str, data: dict):
    cache = _load_cache()
    cache[key] = {**data, "cached_at": datetime.datetime.utcnow().isoformat() + "Z"}
    _save_cache(cache)

# ─── Gemini with search grounding ─────────────────────────────────────────────

def _call_with_search(prompt: str) -> str:
    """Call Gemini with Google Search grounding enabled."""
    # Try with search grounding first
    for model_name in [MODEL_FOR_TRENDS, MODEL_FALLBACK]:
        try:
            model = genai.GenerativeModel(model_name)
            # Use google_search as a tool for real-time grounding
            response = model.generate_content(
                prompt,
                tools=[{"google_search": {}}],
            )
            return response.text.strip()
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower():
                continue
            # If search tool isn't supported, fall back without it
            if "tools" in err.lower() or "tool" in err.lower() or "search" in err.lower():
                try:
                    model2 = genai.GenerativeModel(model_name)
                    response2 = model2.generate_content(prompt)
                    return response2.text.strip()
                except Exception:
                    continue
            continue
    
    # Final fallback: call without search
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"[trend_checker] All models failed: {e}")
        return ""

# ─── Core trend functions ──────────────────────────────────────────────────────

def get_current_vibe() -> dict:
    """
    Returns what is currently trending in internet/YouTube/Discord culture.
    Uses search grounding for real-time data.
    Cached for CACHE_TTL_HOURS.
    """
    cache_key = "current_vibe"
    if _is_cache_fresh(cache_key):
        return _get_cached(cache_key)
    
    today = datetime.datetime.utcnow().strftime("%B %Y")
    prompt = f"""Today is {today}. You have access to real-time web search.

Search for and summarize what is CURRENTLY trending (this week) in these areas:
1. YouTube Shorts comedy formats — what style/format is blowing up right now?
2. Discord/internet culture — what memes, jokes, or situations are people talking about?
3. Gaming/tech — any big drama, releases, or controversies in the last 7 days?
4. General internet — any viral moment, tweet, or situation that EVERYONE is talking about right now?

For each area, give me:
- 2-3 specific, concrete things that are HOT right now (things that would get comments like "omg this is so relevant")
- 1-2 things that DIED recently and would feel stale (things that peaked 2-3 months ago)

Output as JSON:
{{
  "hot_right_now": ["specific thing 1", "specific thing 2", "specific thing 3"],
  "comedy_formats_working": ["format 1", "format 2"],
  "stale_avoid": ["dead thing 1", "dead thing 2"],
  "overall_vibe": "one sentence describing the current internet mood/energy",
  "humor_style": "one sentence on what kind of humor is landing right now"
}}

Output ONLY the JSON. No markdown, no explanation."""

    try:
        result = _call_with_search(prompt)
        # Clean JSON
        result = result.strip()
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        data = json.loads(result.strip())
        _set_cached(cache_key, data)
        return data
    except Exception as e:
        print(f"[trend_checker] get_current_vibe failed: {e}")
        fallback = {
            "hot_right_now": [],
            "comedy_formats_working": ["fast-paced dialogue", "unexpected callback"],
            "stale_avoid": [],
            "overall_vibe": "chaotic and fast-paced",
            "humor_style": "deadpan with sudden escalation"
        }
        return fallback

def assess_premise_freshness(premise: str) -> dict:
    """
    Given a pitch premise, assess whether it feels fresh or stale.
    Returns a freshness score and reasoning.
    """
    cache_key = f"freshness_{hash(premise)}"
    if _is_cache_fresh(cache_key):
        return _get_cached(cache_key)
    
    today = datetime.datetime.utcnow().strftime("%B %Y")
    prompt = f"""Today is {today}. You have access to real-time web search.

Evaluate this YouTube Shorts script premise for freshness:
"{premise}"

Search for:
1. Is this topic/premise something people are currently talking about online?
2. Has this exact type of content been OVERDONE in the last 3 months?
3. Would a 15-25 year old watching YouTube Shorts think "this is relevant" or "this is old"?

Output as JSON:
{{
  "freshness_score": 1-10,
  "verdict": "fresh" | "neutral" | "stale",
  "reasoning": "one sentence",
  "suggestions": ["one way to make it feel more current if stale"]
}}

Output ONLY the JSON."""

    try:
        result = _call_with_search(prompt)
        result = result.strip()
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        data = json.loads(result.strip())
        _set_cached(cache_key, data)
        return data
    except Exception as e:
        print(f"[trend_checker] assess_premise_freshness failed: {e}")
        return {"freshness_score": 5, "verdict": "neutral", "reasoning": "could not assess", "suggestions": []}

def get_vibe_injection_for_prompt() -> str:
    """
    Returns a short paragraph to inject into writer prompts,
    giving context on what energy/style is working right now.
    Does NOT reference specific real people/events (to stay evergreen).
    """
    cache_key = "vibe_injection"
    if _is_cache_fresh(cache_key):
        cached = _get_cached(cache_key)
        return cached.get("text", "")
    
    today = datetime.datetime.utcnow().strftime("%B %Y")
    prompt = f"""Today is {today}. You have access to real-time web search.

Look at what YouTube Shorts comedy content is performing well RIGHT NOW (this week).
Specifically: what ENERGY, PACING, and COMEDY STYLE is resonating with the 15-25 age group?

Write a 3-4 sentence instruction paragraph for a script writer.
The paragraph should describe:
- The pacing/energy that is working right now (e.g., "ultra-fast, 1-word responses")
- The kind of humor landing (e.g., "deadpan reactions to absurd situations")  
- What to AVOID because it feels dated

IMPORTANT: Do NOT name any specific real people, games, movies, or events.
Keep it about STYLE and ENERGY only. The instructions should be evergreen-compatible.

Output the paragraph directly. No JSON. No markdown headers."""

    try:
        result = _call_with_search(prompt)
        _set_cached(cache_key, {"text": result})
        return result
    except Exception as e:
        print(f"[trend_checker] get_vibe_injection_for_prompt failed: {e}")
        return "Write with ultra-fast pacing and deadpan energy. Short messages dominate. The humor comes from the gap between what someone says and what they obviously mean. Avoid anything that feels scripted or explains itself."

def cross_reference_with_ledger(premise: str, ledger_summary: str) -> str:
    """
    Cross-references a proposed premise against the ledger summary
    AND current trends to identify if it's too similar to past work
    OR if it's missing a current opportunity.
    Returns a short note for the Supervisor's journal.
    """
    prompt = f"""You are reviewing a YouTube Shorts script premise against past episode history.

PROPOSED PREMISE: {premise}

PAST EPISODE HISTORY:
{ledger_summary}

Assess:
1. Does this premise feel too similar to any past episode? (high risk of repetition)
2. Is there a current trending angle we could add to make it MORE relevant right now?
3. Does the premise have a unique hook that hasn't been done before?

Write a 2-3 sentence assessment for the Supervisor. Be direct and specific.
If there's a repetition risk, say so clearly. If there's a trend opportunity, name it.
Do NOT name real people or specific events."""

    try:
        result = _call_with_search(prompt)
        return result
    except Exception as e:
        return f"Could not cross-reference: {e}"

if __name__ == "__main__":
    print("Testing trend checker...")
    vibe = get_current_vibe()
    print(f"Current vibe: {vibe.get('overall_vibe', 'unknown')}")
    print(f"Hot right now: {vibe.get('hot_right_now', [])}")
    
    injection = get_vibe_injection_for_prompt()
    print(f"\nVibe injection for prompts:\n{injection}")

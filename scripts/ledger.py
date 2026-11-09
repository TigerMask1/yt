"""
ledger.py
---------
Central memory system for the NOTABOT content engine.
Tracks every episode, analytics, phrases used, autonomy level, and drift.
Replaces lore_manager.py.
"""
import os
import json
import datetime
import re
from pathlib import Path

ASSETS_DIR = Path(__file__).parent.parent / "assets"
LEDGER_DIR = ASSETS_DIR / "ledger"
LEDGER_FILE = LEDGER_DIR / "ledger.json"
PHRASE_LEDGER_FILE = LEDGER_DIR / "phrase_ledger.json"
CANARY_FILE = LEDGER_DIR / "canary_history.json"
AUTONOMY_FILE = LEDGER_DIR / "autonomy_state.json"

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _load_json(path, default):
    path = Path(path)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return default

def _save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ─── Ledger core ──────────────────────────────────────────────────────────────

def load_ledger():
    return _load_json(LEDGER_FILE, [])

def save_ledger(entries):
    _save_json(LEDGER_FILE, entries)

def get_last_n_episodes(n=20):
    return load_ledger()[-n:]

def append_episode(entry: dict):
    """Append a new episode entry. Called after every PASS from the quality gate."""
    entries = load_ledger()
    if "episode_id" not in entry:
        entry["episode_id"] = f"ep_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    if "timestamp" not in entry:
        entry["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
    entries.append(entry)
    save_ledger(entries)
    # Also update phrase ledger from this episode's script lines
    if "script_lines" in entry:
        update_phrase_ledger(entry["script_lines"])
    return entry["episode_id"]

def update_video_id(episode_id: str, video_id: str):
    """Write the YouTube video ID back to a ledger entry after upload."""
    entries = load_ledger()
    for entry in entries:
        if entry.get("episode_id") == episode_id:
            entry["youtube_video_id"] = video_id
            break
    save_ledger(entries)

def update_analytics(video_id: str, analytics: dict):
    """Write analytics data back to a ledger entry."""
    entries = load_ledger()
    for entry in entries:
        if entry.get("youtube_video_id") == video_id:
            entry["analytics"] = analytics
            entry["analytics"]["collected_at"] = datetime.datetime.utcnow().isoformat() + "Z"
            if analytics.get("hours_since_upload", 0) >= 72:
                entry["analytics"]["stable"] = True
            break
    save_ledger(entries)

def get_episode_by_video_id(video_id: str):
    for entry in load_ledger():
        if entry.get("youtube_video_id") == video_id:
            return entry
    return None

# ─── Cooldown and quota checks ─────────────────────────────────────────────────

def get_recent_values(field: str, n: int) -> list:
    """Get values of a field from the last n episodes."""
    return [e.get(field) for e in get_last_n_episodes(n) if e.get(field)]

def is_on_cooldown(field: str, value: str, cooldown: int) -> bool:
    """Check if a value appeared in the last `cooldown` episodes for a given field."""
    recent = get_recent_values(field, cooldown)
    # For list fields like cast_pair
    if recent and isinstance(recent[0], list):
        for r in recent:
            if set(r) == set(value) if isinstance(value, list) else value in r:
                return True
        return False
    return value in recent

def get_quota_fraction(field: str, value: str, window: int = 20) -> float:
    """Return the fraction of the last `window` episodes that used this value."""
    recent = get_recent_values(field, window)
    if not recent:
        return 0.0
    count = sum(1 for r in recent if r == value or (isinstance(r, list) and value in r))
    return count / window

def exceeds_quota(field: str, value: str, max_fraction: float = 0.25, window: int = 20) -> bool:
    return get_quota_fraction(field, value, window) >= max_fraction

# ─── Phrase ledger ─────────────────────────────────────────────────────────────

def load_phrase_ledger():
    return _load_json(PHRASE_LEDGER_FILE, {"phrases": [], "last_updated": None, "max_history_episodes": 20})

def update_phrase_ledger(script_lines: list):
    """Extract dialogue lines from script and add to phrase ledger."""
    pl = load_phrase_ledger()
    phrases = pl.get("phrases", [])
    
    for line in script_lines:
        line = line.strip()
        # Skip metadata lines, character headers, empty lines
        if not line or line.startswith("#") or line.endswith(":") or line.startswith("WELCOME"):
            continue
        # Strip the duration/sound markers to get the clean text
        clean = re.sub(r'\$\^[\d.]+', '', line)
        clean = re.sub(r'#![a-z_]+', '', clean).strip()
        if len(clean) > 3:  # skip very short fragments
            phrases.append(clean)
    
    # Keep only last max_history_episodes worth (approximating by keeping last 500 phrases)
    phrases = phrases[-500:]
    pl["phrases"] = phrases
    pl["last_updated"] = datetime.datetime.utcnow().isoformat() + "Z"
    _save_json(PHRASE_LEDGER_FILE, pl)

def get_phrases_to_avoid() -> list:
    """Return the flat list of phrases the writer should avoid."""
    return load_phrase_ledger().get("phrases", [])

# ─── Lore continuity (backward-compat with lore_manager) ──────────────────────

def get_lore_context() -> str:
    """Build the lore context string for the writer prompt, from recent episodes."""
    recent = get_last_n_episodes(5)
    if not recent:
        return "LORE: This is the first episode. NOTABOT has just been granted admin rights by ducky and is already plotting."
    
    context = "CURRENT LORE CONTEXT (continue the story from here):\n"
    lore_updates = [e.get("lore_update", "") for e in recent if e.get("lore_update")]
    if lore_updates:
        context += "- Recent events (most recent last):\n"
        for event in lore_updates[-3:]:
            context += f"  * {event}\n"
    
    # Try to get a notabot_status from the most recent entry
    for entry in reversed(recent):
        if entry.get("notabot_status"):
            context += f"- NOTABOT current status: {entry['notabot_status']}\n"
            break
    
    return context

def update_lore(episode_id: str, lore_summary: str, notabot_status: str = None):
    """Write lore update back to a ledger entry."""
    entries = load_ledger()
    for entry in entries:
        if entry.get("episode_id") == episode_id:
            entry["lore_update"] = lore_summary
            if notabot_status:
                entry["notabot_status"] = notabot_status
            break
    save_ledger(entries)

# ─── Canary tests ──────────────────────────────────────────────────────────────

def record_canary_result(passed: bool, details: str = ""):
    history = _load_json(CANARY_FILE, [])
    history.append({
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "passed": passed,
        "details": details
    })
    history = history[-50:]  # keep last 50
    _save_json(CANARY_FILE, history)

def is_canary_healthy() -> bool:
    history = _load_json(CANARY_FILE, [])
    if not history:
        return True  # no history = not failed yet
    # Check the most recent canary result
    return history[-1].get("passed", True)

# ─── Autonomy ladder ───────────────────────────────────────────────────────────

def load_autonomy() -> dict:
    return _load_json(AUTONOMY_FILE, {
        "current_level": 0,
        "episodes_at_level": 0,
        "total_episodes": 0,
        "safety_flags_last_30": 0,
        "override_rate_last_30": 0.0,
        "canary_healthy": True,
        "last_promotion_check": None,
        "promotion_history": [],
        "demotion_history": []
    })

def save_autonomy(state: dict):
    _save_json(AUTONOMY_FILE, state)

def get_autonomy_level() -> int:
    return load_autonomy().get("current_level", 0)

def demote_autonomy(reason: str):
    state = load_autonomy()
    old_level = state["current_level"]
    state["current_level"] = max(0, old_level - 1)
    state["demotion_history"].append({
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "from_level": old_level,
        "to_level": state["current_level"],
        "reason": reason
    })
    save_autonomy(state)
    print(f"[autonomy] DEMOTED from level {old_level} to {state['current_level']}: {reason}")

def check_promotion():
    """Check if autonomy should be promoted. Called after each episode."""
    state = load_autonomy()
    level = state["current_level"]
    total = state["total_episodes"]
    
    # Promotion thresholds per level
    thresholds = {
        0: {"episodes": 30, "override_rate": 0.20, "safety_flags": 0},
        1: {"episodes": 50, "override_rate": 0.10, "safety_flags": 0},
        2: {"episodes": 100, "override_rate": 0.05, "safety_flags": 0},
        3: {"episodes": 200, "override_rate": 0.02, "safety_flags": 0},
    }
    
    if level >= 4:
        return  # Already at max
    
    t = thresholds.get(level, {})
    if not t:
        return
    
    episodes_at_level = state.get("episodes_at_level", 0)
    if (episodes_at_level >= t["episodes"] and
        state.get("override_rate_last_30", 1.0) <= t["override_rate"] and
        state.get("safety_flags_last_30", 1) <= t["safety_flags"] and
        is_canary_healthy()):
        
        old_level = level
        state["current_level"] = level + 1
        state["episodes_at_level"] = 0
        state["promotion_history"].append({
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "from_level": old_level,
            "to_level": state["current_level"],
            "total_episodes": total
        })
        save_autonomy(state)
        print(f"[autonomy] PROMOTED from level {old_level} to {state['current_level']}!")

def increment_episode_count(had_flag: bool = False, was_overridden: bool = False):
    """Call after each published episode to update autonomy counters."""
    state = load_autonomy()
    state["total_episodes"] = state.get("total_episodes", 0) + 1
    state["episodes_at_level"] = state.get("episodes_at_level", 0) + 1
    
    # Rolling 30-episode window for safety flags
    # (simplified: just track the count directly for now)
    if had_flag:
        state["safety_flags_last_30"] = state.get("safety_flags_last_30", 0) + 1
    if was_overridden:
        # Update override rate as a simple rolling average
        current = state.get("override_rate_last_30", 0.0)
        state["override_rate_last_30"] = (current * 0.9) + (0.1 if was_overridden else 0)
    
    state["last_promotion_check"] = datetime.datetime.utcnow().isoformat() + "Z"
    save_autonomy(state)
    check_promotion()

# ─── Analytics digest (every 10 episodes) ─────────────────────────────────────

def get_analytics_digest(window: int = 10) -> dict:
    """
    Compute performance trends from the last `window` stable episodes.
    Returns a dict of shape/mechanism/character performance for the Showrunner.
    """
    entries = [e for e in get_last_n_episodes(window) if e.get("analytics", {}).get("stable")]
    if not entries:
        return {}
    
    channel_mean_retention = sum(
        e["analytics"].get("averageViewPercentage", 50) for e in entries
    ) / len(entries) if entries else 50.0
    
    # Group by shape
    shape_stats = {}
    mechanism_stats = {}
    character_stats = {}
    
    for entry in entries:
        retention = entry.get("analytics", {}).get("averageViewPercentage", 0)
        
        shape = entry.get("shape")
        if shape:
            if shape not in shape_stats:
                shape_stats[shape] = []
            shape_stats[shape].append(retention)
        
        mechanism = entry.get("mechanism")
        if mechanism:
            if mechanism not in mechanism_stats:
                mechanism_stats[mechanism] = []
            mechanism_stats[mechanism].append(retention)
        
        for char in (entry.get("cast_pair") or []):
            if char != "NOTABOT":
                if char not in character_stats:
                    character_stats[char] = []
                character_stats[char].append(retention)
    
    def avg(lst): return sum(lst) / len(lst) if lst else 0
    
    return {
        "channel_mean_retention": channel_mean_retention,
        "shape_performance": {k: avg(v) for k, v in shape_stats.items()},
        "mechanism_performance": {k: avg(v) for k, v in mechanism_stats.items()},
        "character_performance": {k: avg(v) for k, v in character_stats.items()},
        "sample_size": len(entries)
    }

# ─── Drift detection ──────────────────────────────────────────────────────────

def check_drift(window: int = 10) -> dict:
    """
    Every 10 episodes, compare NOTABOT's lines against expected voice patterns.
    Returns a dict with drift warnings.
    """
    entries = get_last_n_episodes(window)
    if len(entries) < window:
        return {"checked": False, "reason": "insufficient_history"}
    
    warnings = []
    
    # Check NOTABOT role uniformity
    notabot_roles = [e.get("notabot_role") for e in entries if e.get("notabot_role")]
    if notabot_roles:
        most_common = max(set(notabot_roles), key=notabot_roles.count)
        freq = notabot_roles.count(most_common) / len(notabot_roles)
        if freq > 0.5:
            warnings.append(f"NOTABOT role '{most_common}' used in {freq:.0%} of last {window} episodes")
    
    # Check shape uniformity
    shapes = [e.get("shape") for e in entries if e.get("shape")]
    if shapes:
        most_common = max(set(shapes), key=shapes.count)
        freq = shapes.count(most_common) / len(shapes)
        if freq > 0.5:
            warnings.append(f"Story shape '{most_common}' used in {freq:.0%} of last {window} episodes")
    
    # Check average score trend (should not be flat/declining)
    scores = [e.get("scores", {}).get("total", 0) for e in entries]
    if len(scores) >= 5:
        first_half = sum(scores[:len(scores)//2]) / (len(scores)//2)
        second_half = sum(scores[len(scores)//2:]) / (len(scores) - len(scores)//2)
        if second_half < first_half - 2:
            warnings.append(f"Score declining: first half avg {first_half:.1f}, second half avg {second_half:.1f}")
    
    return {
        "checked": True,
        "drift_detected": len(warnings) > 0,
        "warnings": warnings,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }

# ─── Ledger summary for prompts ───────────────────────────────────────────────

def get_ledger_summary_for_prompt(n: int = 10) -> str:
    """Short human-readable ledger summary injected into AI prompts."""
    recent = get_last_n_episodes(n)
    if not recent:
        return "No previous episodes. This is the first run."
    
    lines = ["Recent episode history (do NOT repeat these premises):"]
    for e in recent[-10:]:
        lines.append(f"  - [{e.get('shape','?')} / {e.get('mechanism','?')} / {e.get('notabot_role','?')}] {e.get('premise','?')}")
    
    lines.append("\nRecent hook types used (avoid repeating same hook type twice in a row):")
    hook_types = [e.get("hook_type") for e in recent[-5:] if e.get("hook_type")]
    lines.append("  " + ", ".join(hook_types) if hook_types else "  none yet")
    
    lines.append("\nRecent ending types used (avoid repeating):")
    ending_types = [e.get("ending_type") for e in recent[-5:] if e.get("ending_type")]
    lines.append("  " + ", ".join(ending_types) if ending_types else "  none yet")
    
    return "\n".join(lines)

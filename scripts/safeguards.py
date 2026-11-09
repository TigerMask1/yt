"""
safeguards.py
─────────────
Three missing safeguards added to supervisor.py:
  1. Daily publishing cap  — supervisor refuses to run if too many episodes published today
  2. Quarantine folder     — REWORK/DISCARD scripts saved to assets/quarantine/ for manual review
  3. Kill switch           — if assets/ledger/killswitch.txt exists, supervisor refuses to run

Import and call these at the top of Supervisor.run_episode().
"""
import os
import json
import shutil
import datetime
from pathlib import Path

ASSETS_DIR    = Path(__file__).parent.parent / "assets"
LEDGER_PATH   = ASSETS_DIR / "ledger" / "ledger.json"
QUARANTINE_DIR = ASSETS_DIR / "quarantine"
KILLSWITCH    = ASSETS_DIR / "ledger" / "killswitch.txt"
DAILY_CAP     = int(os.environ.get("NOTABOT_DAILY_CAP", "3"))   # max episodes per day


# ── 1. Kill switch ────────────────────────────────────────────────────────────

def check_killswitch() -> None:
    """
    Raise RuntimeError if the kill switch file exists.
    To activate: create  assets/ledger/killswitch.txt  with any content.
    To deactivate: delete that file.
    """
    if KILLSWITCH.exists():
        reason = KILLSWITCH.read_text(encoding="utf-8").strip() or "no reason given"
        raise RuntimeError(
            f"[safeguards] KILL SWITCH ACTIVE — supervisor will not run.\n"
            f"Reason: {reason}\n"
            f"Delete {KILLSWITCH} to resume."
        )


# ── 2. Daily publishing cap ────────────────────────────────────────────────────

def check_daily_cap() -> None:
    """
    Raise RuntimeError if DAILY_CAP episodes have already been published today.
    Counts ledger entries whose 'created_at' date matches today (UTC).
    """
    today = datetime.datetime.utcnow().date().isoformat()   # e.g. "2026-11-09"

    if not LEDGER_PATH.exists():
        return   # no ledger yet, nothing to count

    try:
        with open(LEDGER_PATH, "r", encoding="utf-8") as f:
            ledger = json.load(f)
    except Exception:
        return   # corrupt ledger — let supervisor deal with it

    todays_episodes = [
        ep for ep in ledger
        if isinstance(ep, dict) and ep.get("created_at", "").startswith(today)
    ]

    if len(todays_episodes) >= DAILY_CAP:
        raise RuntimeError(
            f"[safeguards] DAILY CAP REACHED — {len(todays_episodes)} episodes already "
            f"published today (cap={DAILY_CAP}). "
            f"Set NOTABOT_DAILY_CAP env var to override."
        )


# ── 3. Quarantine folder ───────────────────────────────────────────────────────

def quarantine_script(
    script_path: str,
    verdict: str,
    confidence: float,
    reason: str,
    episode_id: str,
) -> str:
    """
    Copy a failed/flagged script to assets/quarantine/ so it can be reviewed manually
    instead of silently discarded.

    Returns the path of the quarantined copy.
    """
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)

    src = Path(script_path)
    if not src.exists():
        return ""   # nothing to quarantine

    # Filename: <timestamp>_<verdict>_<episode_id>.txt
    ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dest_name = f"{ts}_{verdict}_{episode_id}.txt"
    dest = QUARANTINE_DIR / dest_name

    shutil.copy2(src, dest)

    # Write a sidecar metadata file so a human knows why it was quarantined
    meta = {
        "episode_id":   episode_id,
        "verdict":      verdict,
        "confidence":   confidence,
        "reason":       reason,
        "original_path": str(src),
        "quarantined_at": datetime.datetime.utcnow().isoformat(),
    }
    meta_path = QUARANTINE_DIR / f"{ts}_{verdict}_{episode_id}.meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print(f"[safeguards] Quarantined script → {dest}")
    return str(dest)


def list_quarantine() -> list:
    """Return a list of quarantined episode metadata dicts for review."""
    if not QUARANTINE_DIR.exists():
        return []
    results = []
    for meta_file in sorted(QUARANTINE_DIR.glob("*.meta.json")):
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                results.append(json.load(f))
        except Exception:
            pass
    return results

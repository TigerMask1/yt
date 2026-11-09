"""
punch_up.py
-----------
Stage 7 of the NOTABOT Script Engine: Punch-Up Room.
Takes the draft dialogue and failing lines from critic_panel.py.
For each failing line, generates 5 distinct alternatives under different creative moves:
  1. More specific (concrete invented details, timestamps, error codes)
  2. More deadpan (bureaucratic, calm delivery)
  3. Bigger escalation (higher stakes)
  4. Shorter (tight burst message, Beluga style)
  5. More in-voice (strict character voice)
A line judge picks the best alternative in context.
Applies a regression guard: max 2 loops, ensures changes improve or maintain the voice and score.
A final read-aloud pass trims unnecessary words.
"""

import os
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union
import google.generativeai as genai
import model_config
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
load_dotenv(Path(__file__).parent.parent / ".env")
genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))

import ledger
from foundation_loader import FoundationBundle, load_foundations, get_cast_cards_for
import critic_panel

# Model fallbacks from model_config (single source of truth)
MODEL_FALLBACKS = model_config.get_model_fallbacks("punch_up_line_judge")

def _call_gemini(prompt: str) -> str:
    """Invokes Gemini with fallback models across quota errors."""
    for model_name in MODEL_FALLBACKS:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                continue
            raise
    raise RuntimeError("All models exhausted in punch-up room")


def _clean_json_response(raw: str) -> str:
    """Strips markdown code blocks from model JSON output."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


# ─── Script Line Helpers ───────────────────────────────────────────────────────

def _extract_beat_tag(line: str) -> Tuple[str, Optional[str]]:
    """Extracts beat tag from a line if present, returning (clean_line, beat_tag_str)."""
    match = re.search(r'(\[beat_tag:[a-zA-Z0-9_]+\])', line)
    if match:
        tag = match.group(1)
        clean = line.replace(tag, "").strip()
        return clean, tag
    return line.strip(), None


def _find_speaker_for_line(script: str, target_line: str) -> str:
    """Finds the character speaking the target line in the script."""
    clean_target, _ = _extract_beat_tag(target_line)
    clean_target = clean_target.strip("\"' ").lower()

    current_speaker = "Unknown"
    for raw_line in script.split("\n"):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith(":") and not line.startswith("WELCOME"):
            current_speaker = line[:-1].strip()
            continue
        if ":" in line and not line.startswith("WELCOME"):
            prefix, rest = line.split(":", 1)
            known_speakers = ["NOTABOT", "ducky", "Pablo", "Eugene", "Jaguar", "Pepper", "Vladimir"]
            if prefix.strip() in known_speakers:
                current_speaker = prefix.strip()
                line = rest.strip()

        line_clean, _ = _extract_beat_tag(line)
        line_clean = line_clean.strip("\"' ").lower()
        if clean_target in line_clean or line_clean in clean_target:
            return current_speaker

    return current_speaker


def _get_surrounding_context(script: str, target_line: str, window: int = 3) -> str:
    """Gets surrounding dialogue lines around the target line for contextual judging."""
    clean_target, _ = _extract_beat_tag(target_line)
    clean_target = clean_target.strip("\"' ").lower()

    lines = [l.strip() for l in script.split("\n") if l.strip() and not l.startswith("# TITLE:") and not l.startswith("# PREMISE:")]
    target_idx = -1
    for idx, l in enumerate(lines):
        cl, _ = _extract_beat_tag(l)
        if clean_target in cl.strip("\"' ").lower() or cl.strip("\"' ").lower() in clean_target:
            target_idx = idx
            break

    if target_idx == -1:
        return script[:400]

    start = max(0, target_idx - window)
    end = min(len(lines), target_idx + window + 1)
    context_slice = []
    for i in range(start, end):
        prefix = ">>> " if i == target_idx else "    "
        context_slice.append(f"{prefix}{lines[i]}")
    return "\n".join(context_slice)


def _replace_line_in_script(script: str, target_line: str, replacement_line: str) -> Tuple[str, bool]:
    """
    Replaces a dialogue line in the script, preserving speaker headings
    and attaching any original beat tag if missing from the replacement.
    """
    target_clean, original_tag = _extract_beat_tag(target_line)
    target_norm = target_clean.strip("\"' ").lower()

    rep_clean, rep_tag = _extract_beat_tag(replacement_line)
    final_tag = rep_tag or original_tag
    final_replacement = rep_clean
    if final_tag and final_tag not in final_replacement:
        final_replacement = f"{final_replacement} {final_tag}"

    lines = script.split("\n")
    replaced = False
    new_lines = []

    for line in lines:
        if replaced:
            new_lines.append(line)
            continue

        raw = line.strip()
        if not raw or raw.startswith("#"):
            new_lines.append(line)
            continue

        # Check line with Speaker: prefix
        if ":" in raw and not raw.endswith(":") and not raw.startswith("WELCOME"):
            prefix, rest = raw.split(":", 1)
            rest_clean, script_tag = _extract_beat_tag(rest.strip())
            if target_norm in rest_clean.strip("\"' ").lower() or rest_clean.strip("\"' ").lower() in target_norm:
                tag_to_use = final_tag or script_tag
                line_text = final_replacement
                if tag_to_use and tag_to_use not in line_text:
                    line_text = f"{line_text} {tag_to_use}"
                new_lines.append(f"{prefix.strip()}: {line_text}")
                replaced = True
                continue

        # Standard dialogue line under speaker heading
        line_clean, script_tag = _extract_beat_tag(raw)
        if target_norm in line_clean.strip("\"' ").lower() or line_clean.strip("\"' ").lower() in target_norm:
            indent = line[:len(line) - len(line.lstrip())]
            tag_to_use = final_tag or script_tag
            line_text = final_replacement
            if tag_to_use and tag_to_use not in line_text:
                line_text = f"{line_text} {tag_to_use}"
            new_lines.append(f"{indent}{line_text}")
            replaced = True
            continue

        new_lines.append(line)

    if not replaced:
        if target_clean in script:
            script = script.replace(target_clean, final_replacement, 1)
            return script, True

    return "\n".join(new_lines), replaced


# ─── 5 Creative Moves Generation ──────────────────────────────────────────────

def generate_5_alternatives(
    failing_line: str,
    context: str,
    speaker: str,
    bundle: FoundationBundle
) -> Dict[str, str]:
    """
    Generates 5 distinct alternatives for a failing line under the 5 creative moves:
      1. More specific (concrete invented details, timestamps, error codes)
      2. More deadpan (bureaucratic, calm delivery)
      3. Bigger escalation (higher stakes)
      4. Shorter (tight burst message, Beluga style)
      5. More in-voice (strict character voice)
    """
    clean_line, tag = _extract_beat_tag(failing_line)
    cast_card = bundle.cast_cards.get(speaker, {}) if bundle else {}
    persona_notes = cast_card.get("voice", f"{speaker} character voice")

    prompt = f"""You are an elite YouTube Shorts comedy punch-up writer for NOTABOT.
We are revising a single dialogue line flagged by the critic panel as weak, generic, out-of-character, or stiff.

SPEAKER: {speaker}
SPEAKER VOICE RULES: {persona_notes}

SURROUNDING CONTEXT:
{context}

ORIGINAL FAILING LINE:
"{clean_line}"

Generate exactly 5 distinct rewritten alternatives for this single dialogue line, each demonstrating one of the five specific creative moves:
1. more_specific: Add concrete invented details, exact timestamps, server error codes, case numbers, or absurdly specific items.
2. more_deadpan: Flat, bureaucratic, calm delivery. Zero emotional hype. Deliver catastrophic news as routine maintenance, ticket notes, or policy.
3. bigger_escalation: Significantly raise the stakes or consequences. Turn an annoyance or misunderstanding into a severe crisis.
4. shorter: Ultra-tight burst message (3 to 6 words max). Snappy Discord/Beluga chat style. Cut all fluff.
5. more_in_voice: Strict adherence to {speaker}'s personality quirks, syntax, and verbal rhythm (NOTABOT: calm bureaucratic bot menace; Ducky: erratic panic; Pablo: dismissive foodie; Eugene: aggressive rule-lawyer mod).

OUTPUT JSON ONLY with exactly these 5 keys:
{{
  "more_specific": "...",
  "more_deadpan": "...",
  "bigger_escalation": "...",
  "shorter": "...",
  "more_in_voice": "..."
}}
"""
    try:
        raw = _call_gemini(prompt)
        data = json.loads(_clean_json_response(raw))
        moves = ["more_specific", "more_deadpan", "bigger_escalation", "shorter", "more_in_voice"]
        for m in moves:
            if m not in data or not str(data[m]).strip():
                data[m] = clean_line
        return data
    except Exception as e:
        print(f"[punch_up] Error generating 5 alternatives: {e}. Using deterministic fallbacks.")
        return {
            "more_specific": f"{clean_line} (Incident Log #8492-B)",
            "more_deadpan": f"Per server protocol: {clean_line.lower()}",
            "bigger_escalation": f"{clean_line}. Permanent IP blacklist initiated.",
            "shorter": " ".join(clean_line.split()[:4]),
            "more_in_voice": clean_line,
        }


# ─── Line Judge ────────────────────────────────────────────────────────────────

def judge_best_alternative(
    failing_line: str,
    alternatives: Dict[str, str],
    context: str,
    speaker: str
) -> Dict[str, str]:
    """
    Line judge picks the best alternative in context from the 5 creative moves
    or retains the original if none are genuinely superior.
    """
    clean_line, _ = _extract_beat_tag(failing_line)

    prompt = f"""You are the Senior Line Judge for a viral YouTube Shorts Discord chat comedy channel.
Your task is to select the single best line to replace the flagged dialogue line in context.

SPEAKER: {speaker}
SURROUNDING CONTEXT:
{context}

ORIGINAL LINE: "{clean_line}"

CANDIDATES:
1. [more_specific]: "{alternatives.get('more_specific')}"
2. [more_deadpan]: "{alternatives.get('more_deadpan')}"
3. [bigger_escalation]: "{alternatives.get('bigger_escalation')}"
4. [shorter]: "{alternatives.get('shorter')}"
5. [more_in_voice]: "{alternatives.get('more_in_voice')}"

SELECTION CRITERIA:
- Maximizes comedic punch and timing for a fast-paced Short.
- Authentic Discord chat feel (short, punchy, not theatrical dialogue).
- Strictly maintains character voice.
- Seamless continuity with the surrounding context.
- Keep under 12 words.

Output JSON ONLY:
{{
  "selected_move": "more_specific" | "more_deadpan" | "bigger_escalation" | "shorter" | "more_in_voice" | "keep_original",
  "chosen_line": "exact text of winning line",
  "reasoning": "1 sentence explanation"
}}
"""
    try:
        raw = _call_gemini(prompt)
        result = json.loads(_clean_json_response(raw))
        chosen = result.get("chosen_line", "").strip("\"' ")
        if not chosen or result.get("selected_move") == "keep_original":
            return {"selected_move": "keep_original", "chosen_line": clean_line, "reasoning": "Original retained"}
        return {
            "selected_move": result.get("selected_move", "more_in_voice"),
            "chosen_line": chosen,
            "reasoning": result.get("reasoning", "Best comedic timing and voice consistency")
        }
    except Exception as e:
        print(f"[punch_up] Line judge fallback: {e}")
        fallback_line = alternatives.get("shorter") or alternatives.get("more_specific") or clean_line
        return {
            "selected_move": "shorter",
            "chosen_line": fallback_line,
            "reasoning": "Fallback line selection"
        }


# ─── Final Read-Aloud Pass ─────────────────────────────────────────────────────

def read_aloud_pass(script: str) -> str:
    """
    Simulates a vocal read-aloud pass to trim unnecessary words, eliminate flab,
    and hone Discord burst-message rhythm without altering jokes, plot, or beat tags.
    """
    prompt = f"""You are the Head Script Editor doing the final READ-ALOUD PASS on a Discord comedy short.
Read this dialogue out loud in your head. Real Discord messages are typed quickly, often in 3-8 word bursts.
Trim every unnecessary filler word, clunky conjunction, or over-explanation.

STRICT CONSTRAINTS:
1. DO NOT change speaker names or headers (e.g. 'NOTABOT:', 'ducky:').
2. PRESERVE all beat tags (e.g. '[beat_tag:hook]', '[beat_tag:punchline]', '[beat_tag:button]') on their lines!
3. DO NOT cut the core punchlines, setups, plants, callbacks, or plot turns.
4. ONLY tighten wordy lines to make them punchier and faster to read on screen.
5. Keep the total message count intact.

SCRIPT:
{script}

OUTPUT THE FULL TIGHTENED SCRIPT ONLY. NO EXPLANATIONS. NO MARKDOWN WRAPPERS.
"""
    try:
        trimmed = _call_gemini(prompt)
        if trimmed.startswith("```"):
            trimmed = trimmed.split("```")[1]
            if trimmed.startswith("markdown") or trimmed.startswith("text"):
                trimmed = "\n".join(trimmed.split("\n")[1:])
        trimmed = trimmed.strip("` \n")
        if len(trimmed.split("\n")) >= 8 and ":" in trimmed:
            return trimmed
        return script
    except Exception as e:
        print(f"[punch_up] Read-aloud pass encountered error: {e}. Keeping current script.")
        return script


# ─── Master Punch-Up Engine (Stage 7) ──────────────────────────────────────────

def run_punch_up(
    script: str,
    failing_lines_or_report: Optional[Union[List[str], dict]] = None,
    bundle: Optional[FoundationBundle] = None,
    beat_sheet: Optional[dict] = None,
    max_loops: int = 2
) -> Tuple[str, dict, dict]:
    """
    Executes the Stage 7 Punch-Up Room:
      1. Evaluates baseline script with critic panel if needed.
      2. For each failing line, generates 5 distinct alternatives under creative moves:
         - more_specific, more_deadpan, bigger_escalation, shorter, more_in_voice.
      3. Line judge chooses the optimal replacement in context.
      4. Applies regression guard: max 2 loops, ensures score and voice improve/maintain.
      5. Runs final read-aloud pass to trim unnecessary words.
    
    Returns:
      (final_script, final_critic_report, punch_up_summary)
    """
    if bundle is None:
        bundle = load_foundations()
    if beat_sheet is None:
        beat_sheet = {}

    # Normalize failing lines from list or report dict
    failing_lines: List[str] = []
    initial_report: Optional[dict] = None

    if isinstance(failing_lines_or_report, dict):
        initial_report = failing_lines_or_report
        failing_lines = initial_report.get("failing_lines", [])
    elif isinstance(failing_lines_or_report, list):
        failing_lines = failing_lines_or_report

    print(f"\n{'='*60}\n  STAGE 7: PUNCH-UP ROOM\n{'='*60}")

    # Establish baseline score and initial report
    if initial_report is None or "total_score" not in initial_report:
        baseline_report = critic_panel.run_critic_panel(script, beat_sheet, bundle)
    else:
        baseline_report = initial_report

    current_score = baseline_report.get("total_score", 0.0)
    current_report = baseline_report
    if not failing_lines:
        failing_lines = baseline_report.get("failing_lines", [])

    print(f"[punch_up] Initial Score: {current_score}/50. Failing lines flagged: {len(failing_lines)}")

    current_script = script
    punch_up_log = []
    regressions_blocked = 0
    loops_executed = 0
    lines_to_fix = list(failing_lines)

    # ─── Regression Guard Punch-Up Loop (Max 2 Loops) ──────────────────────────
    for loop_num in range(1, max_loops + 1):
        if not lines_to_fix:
            print(f"[punch_up] Loop {loop_num}: No failing lines left to fix.")
            break

        loops_executed += 1
        print(f"\n[punch_up] -- Loop {loop_num}/{max_loops}: Processing {len(lines_to_fix)} lines --")
        candidate_script = current_script
        loop_replacements = []

        for failing_line in lines_to_fix[:6]:  # Target top flagged lines per loop
            clean_fl, _ = _extract_beat_tag(failing_line)
            if not clean_fl.strip():
                continue

            speaker = _find_speaker_for_line(candidate_script, clean_fl)
            context = _get_surrounding_context(candidate_script, clean_fl)

            print(f"  [Move Gen] Flagged line ({speaker}): \"{clean_fl}\"")
            alternatives = generate_5_alternatives(clean_fl, context, speaker, bundle)

            judge_result = judge_best_alternative(clean_fl, alternatives, context, speaker)
            winning_line = judge_result.get("chosen_line", clean_fl)
            move = judge_result.get("selected_move", "none")

            print(f"  [Judge Pick] Selected '{move}': \"{winning_line}\"")

            if winning_line != clean_fl and move != "keep_original":
                new_candidate, replaced = _replace_line_in_script(candidate_script, clean_fl, winning_line)
                if replaced:
                    candidate_script = new_candidate
                    loop_replacements.append({
                        "original": clean_fl,
                        "replacement": winning_line,
                        "move": move,
                        "reasoning": judge_result.get("reasoning", "")
                    })

        if not loop_replacements:
            print(f"[punch_up] Loop {loop_num}: No replacements selected by line judge.")
            break

        # Regression Guard Check
        print(f"[punch_up] Loop {loop_num}: Running regression guard evaluation...")
        candidate_report = critic_panel.run_critic_panel(candidate_script, beat_sheet, bundle)
        candidate_score = candidate_report.get("total_score", 0.0)
        safety_status = candidate_report.get("safety", {}).get("verdict", "PASS")

        is_safe = (safety_status == "PASS")
        score_maintained = candidate_score >= (current_score - 0.5)
        voice_clean = candidate_report.get("voice", {}).get("notabot_voice_clean", True)

        if is_safe and score_maintained and voice_clean:
            print(f"[punch_up] [OK] Loop {loop_num} ACCEPTED: Score changed {current_score} -> {candidate_score}")
            current_script = candidate_script
            current_score = candidate_score
            current_report = candidate_report
            punch_up_log.extend(loop_replacements)
            lines_to_fix = candidate_report.get("failing_lines", [])
        else:
            print(f"[punch_up] [BLOCKED] REGRESSION in Loop {loop_num}: Candidate score {candidate_score} vs current {current_score} (safe={is_safe}, voice={voice_clean}). Rolling back.")
            regressions_blocked += 1
            break

    # --- Final Read-Aloud Pass ---
    print("\n[punch_up] Running final vocal read-aloud pass to trim unnecessary words...")
    trimmed_script = read_aloud_pass(current_script)

    read_aloud_accepted = False
    if trimmed_script != current_script:
        trimmed_report = critic_panel.run_critic_panel(trimmed_script, beat_sheet, bundle)
        trimmed_score = trimmed_report.get("total_score", 0.0)
        trimmed_safe = trimmed_report.get("safety", {}).get("verdict", "PASS") == "PASS"

        if trimmed_safe and trimmed_score >= current_score - 1.0:
            print(f"[punch_up] [OK] Read-aloud pass accepted (Score: {current_score} -> {trimmed_score}).")
            current_script = trimmed_script
            current_score = trimmed_score
            current_report = trimmed_report
            read_aloud_accepted = True
        else:
            print(f"[punch_up] Read-aloud pass caused regression ({trimmed_score} vs {current_score}). Retaining pre-pass script.")
    else:
        print("[punch_up] Script already concise; read-aloud pass made no modifications.")

    summary = {
        "status": "repaired" if punch_up_log else "unmodified",
        "initial_score": baseline_report.get("total_score", 0.0),
        "final_score": current_score,
        "score_delta": round(current_score - baseline_report.get("total_score", 0.0), 1),
        "loops_executed": loops_executed,
        "replacement_count": len(punch_up_log),
        "replacements": punch_up_log,
        "regressions_blocked": regressions_blocked,
        "read_aloud_applied": read_aloud_accepted
    }

    print(f"[punch_up] Room Complete. Final Score: {current_score}/50 (Delta: {summary['score_delta']:+0.1f}). Replaced: {len(punch_up_log)} lines.")
    return current_script, current_report, summary


if __name__ == "__main__":
    sample_script = """# TITLE: The Audit #shorts
NOTABOT:
Welcome ducky. I have detected an anomaly in your activity. [beat_tag:hook]

ducky:
what do you mean bot lol its totally normal

NOTABOT:
Your activity log indicates 47 consecutive hours of zero productivity. [beat_tag:plant]

ducky:
i am working very hard right now bro

NOTABOT:
Error 404: Hard work not found in server archives. [beat_tag:punchline]
"""
    b = load_foundations()
    punched, rpt, sm = run_punch_up(sample_script, failing_lines_or_report=["what do you mean bot lol its totally normal", "i am working very hard right now bro"], bundle=b)
    print("\n--- PUNCHED SCRIPT ---")
    print(punched)
    print("\n--- SUMMARY ---")
    print(json.dumps(sm, indent=2))

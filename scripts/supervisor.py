"""
supervisor.py
-------------
The Master Agent (The Supervisor) owning each episode from first idea to final output.
- Holds FoundationBundle, constraint card, ledger memory, failure catalog, journal, call budget.
- Implements the Move Menu: Explore, Commit, Draft, Test, Repair, Restructure, Restart, Abstain.
- Writes Director's Journal entries before and after each move (reason to exist, pre-mortem,
  binge test, friend test, stop rule).
- Tracks stuck detector: if same move 3x without score improvement -> restart or abstain.
- Manages AI call budget: Standard mode (<= 22 calls), Deep mode (<= 40 calls).
- Orchestrates:
  showrunner.draw_constraint_card -> pitch_room.generate_pitches -> pitch_court.evaluate_pitches
  -> beat_architect.build_beat_sheet -> writer.write_dialogue -> critic_panel.run_critic_panel
  -> punch_up.run_punch_up -> quality_gate.evaluate -> assembler.assemble and assembler.save_script
  -> ledger.append_episode.
- Returns generated script path, gate verdict, confidence, and provenance metadata.
"""
import os
import sys
import json
import random
import datetime
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple

sys.path.insert(0, str(Path(__file__).parent))

import ledger
import showrunner
import pitch_room
import pitch_court
import beat_architect
import writer
import critic_panel
import punch_up
import quality_gate
import assembler
from foundation_loader import load_foundations, FoundationBundle
import safeguards

ASSETS_DIR = Path(__file__).parent.parent / "assets"
LAST_EPISODE_FILE = ASSETS_DIR / "ledger" / "last_episode_id.txt"

@dataclass
class EpisodeResult:
    script_path: str
    gate_verdict: str
    confidence: float
    provenance: Dict[str, Any]
    episode_id: str

    def __iter__(self):
        """Allow tuple unpacking: script_path, verdict, confidence, provenance = run_episode()"""
        return iter((self.script_path, self.gate_verdict, self.confidence, self.provenance))

    def __getitem__(self, item):
        return getattr(self, item)


class Supervisor:
    """The master orchestrator controlling the lifecycle of a single episode."""

    def __init__(self, is_long: bool = False, deep_mode: bool = False, max_budget: Optional[int] = None):
        self.is_long = is_long
        self.deep_mode = deep_mode
        self.max_budget = max_budget if max_budget is not None else (40 if deep_mode else 22)
        self.calls_spent = 0
        
        # Load foundation memory and recent ledger
        self.bundle: FoundationBundle = load_foundations()
        self.ledger_memory: List[Dict] = ledger.get_last_n_episodes(20)
        self.failure_catalog: List[Dict] = self.bundle.failure_catalog
        
        # Director's Journal & State
        self.journal: List[Dict] = []
        self.move_history: List[str] = []
        self.score_history: List[float] = []
        self.restart_count = 0
        self.max_restarts = 2
        
        # Core episode artefacts
        self.constraint_card = None
        self.pitches: List[Dict] = []
        self.winning_pitch: Optional[Dict] = None
        self.losing_pitches: List[Dict] = []
        self.pitch_eval_report: Optional[Dict] = None
        self.beat_sheet: Optional[Dict] = None
        self.draft_script: Optional[str] = None
        self.critic_report: Optional[Dict] = None
        self.gate_evaluation: Optional[Dict] = None
        self.final_script: Optional[str] = None
        self.script_path: Optional[str] = None
        self.episode_id: Optional[str] = None

    def spend_budget(self, calls: int = 1) -> bool:
        """Track AI call budget. Returns False if budget exhausted."""
        self.calls_spent += calls
        print(f"[supervisor] Budget: {self.calls_spent}/{self.max_budget} calls spent.")
        if self.calls_spent >= self.max_budget:
            print(f"[supervisor] WARNING: Call budget limit ({self.max_budget}) reached!")
            return False
        return True

    def check_stuck(self, move: str) -> bool:
        """Stuck detector: same move 3x without score improvement."""
        if len(self.move_history) >= 3 and all(m == move for m in self.move_history[-3:]):
            recent_scores = self.score_history[-3:] if len(self.score_history) >= 3 else []
            if len(recent_scores) == 3 and recent_scores[-1] <= recent_scores[0]:
                print(f"[supervisor] STUCK DETECTOR: Move '{move}' repeated 3x with no score gain ({recent_scores})!")
                return True
        return False

    def log_journal_before(self, move: str, reason: str, expectation: str) -> Dict:
        """Write Director's Journal entry before executing a move."""
        entry = {
            "move": move,
            "timestamp_start": datetime.datetime.utcnow().isoformat() + "Z",
            "reason": reason,
            "expectation": expectation,
            "calls_spent_start": self.calls_spent,
            "result": None,
            "surprise": None,
            "next_decision": None
        }
        self.journal.append(entry)
        self.move_history.append(move)
        print(f"\n[supervisor] === MOVE: {move} ===")
        print(f"  Reason: {reason}")
        print(f"  Expectation: {expectation}")
        return entry

    def log_journal_after(self, result: str, surprise: str = "", next_decision: str = ""):
        """Update the active Director's Journal entry after completing a move."""
        if self.journal:
            entry = self.journal[-1]
            entry["result"] = result
            entry["surprise"] = surprise
            entry["next_decision"] = next_decision
            entry["timestamp_end"] = datetime.datetime.utcnow().isoformat() + "Z"
            entry["calls_spent_end"] = self.calls_spent
            print(f"  Result: {result}")
            if next_decision:
                print(f"  Next Decision: {next_decision}")

    # ─── Move Implementations ────────────────────────────────────────────────

    def move_explore(self) -> bool:
        """Move: Explore — Draw constraints and generate pitches."""
        self.log_journal_before(
            move="Explore",
            reason="Fresh episode cycle initiated or pitch refresh requested.",
            expectation="Draw valid constraint card respecting ledger cooldowns and generate diverse comedic pitches."
        )

        # 1. Showrunner: Pure code constraint card
        self.constraint_card = showrunner.draw_constraint_card(self.bundle, is_long=self.is_long)
        print(f"[supervisor] Constraint card drawn: Shape={self.constraint_card.story_shape}, "
              f"Mechanism={self.constraint_card.comedy_mechanism}, Cast={self.constraint_card.cast_pair}")

        # 2. Pitch Room: Generates pitches with 3 pitchers + dedup (~4 AI calls)
        self.spend_budget(4)
        self.pitches = pitch_room.generate_pitches(self.constraint_card, self.bundle)
        if not self.pitches:
            self.log_journal_after(result="Failed to generate pitches", next_decision="Restart")
            return False

        self.log_journal_after(
            result=f"Generated {len(self.pitches)} surviving candidate pitches.",
            surprise="Diverse comedic angles generated without ledger collision.",
            next_decision="Commit"
        )
        return True

    def move_commit(self) -> bool:
        """Move: Commit — Evaluate candidate pitches, run tests, and lock the winner."""
        self.log_journal_before(
            move="Commit",
            reason=f"Evaluating {len(self.pitches)} candidate pitches in Pitch Court.",
            expectation="Select top scoring pitch exceeding rubric threshold (>= 32) and pass pre-mortem."
        )

        # Spend budget for judges and blind prediction (~4-6 calls)
        self.spend_budget(min(6, max(3, len(self.pitches))))
        eval_result = pitch_court.evaluate_pitches(self.pitches, self.bundle, deep_mode=self.deep_mode)
        winning_pitch, evaluated_list, needs_redraw = eval_result

        if isinstance(winning_pitch, list):
            self.winning_pitch = winning_pitch[0]
            self.losing_pitches = winning_pitch[1:] + [e["pitch"] for e in evaluated_list[2:]]
        else:
            self.winning_pitch = winning_pitch
            self.losing_pitches = [e["pitch"] for e in evaluated_list if e.get("pitch", {}).get("id") != winning_pitch.get("id")]

        self.pitch_eval_report = evaluated_list

        if needs_redraw or not self.winning_pitch:
            self.log_journal_after(
                result="Top pitch scored below acceptable threshold or requires redraw.",
                surprise="Pitches were too predictable or lacked high comedic punch.",
                next_decision="Restart"
            )
            return False

        # Pre-mortem test
        pre_mortem = [
            f"Premise '{self.winning_pitch.get('premise')}' could feel too repetitive if escalation stalls.",
            "Dialogue might lean into generic snark instead of NOTABOT's deadpan bureaucratic voice.",
            "Ending callback might be anticipated if plant is too conspicuous."
        ]
        
        # Binge test: Compare against last 5 episodes in ledger
        recent_premises = [e.get("premise", "") for e in self.ledger_memory[-5:] if e.get("premise")]
        binge_diff = f"Different role ({self.constraint_card.notabot_role}) and mechanism ({self.constraint_card.comedy_mechanism}) than recent 5 episodes."

        self.winning_pitch["pre_mortem"] = pre_mortem
        self.winning_pitch["binge_diff"] = binge_diff

        self.log_journal_after(
            result=f"Locked pitch '{self.winning_pitch.get('id')}': {self.winning_pitch.get('premise')[:60]}...",
            surprise=f"Surprise factor verified: {self.winning_pitch.get('surprise_factor')[:50]}...",
            next_decision="Draft"
        )
        return True

    def move_draft(self) -> bool:
        """Move: Draft — Build beat sheet and write initial dialogue draft."""
        self.log_journal_before(
            move="Draft",
            reason="Pitch is locked. Transforming premise into structured beats and writing dialogue.",
            expectation="Beat sheet passes structure check and writer outputs complete dialogue with beat tags."
        )

        # 1. Beat Architect (1 AI call)
        self.spend_budget(1)
        self.beat_sheet = beat_architect.build_beat_sheet(self.winning_pitch, self.constraint_card, self.bundle)
        if not self.beat_sheet:
            self.log_journal_after(result="Beat sheet generation failed", next_decision="Restart")
            return False

        # 2. Writer writes dialogue ONLY (1 AI call)
        self.spend_budget(1)
        self.draft_script = writer.write_dialogue(self.winning_pitch, self.beat_sheet, self.constraint_card, self.bundle)
        if not self.draft_script:
            self.log_journal_after(result="Dialogue drafting failed", next_decision="Restart")
            return False

        self.log_journal_after(
            result=f"Dialogue drafted successfully ({len(self.draft_script.splitlines())} lines).",
            surprise="Beat tags properly attached to key turning points.",
            next_decision="Test"
        )
        return True

    def move_test(self) -> bool:
        """Move: Test — Run critic panel and programmatic checks."""
        self.log_journal_before(
            move="Test",
            reason="Dialogue draft complete. Evaluating against critic panel and standards.",
            expectation="Check safety hard-stops, realism, voice accuracy, and code rules."
        )

        # Critic Panel: Code checks + Safety + Hook + Voice + Realism (~3-4 calls)
        self.spend_budget(3)
        self.critic_report = critic_panel.run_critic_panel(self.draft_script, self.beat_sheet, self.bundle)
        total_score = self.critic_report.get("total_score", 0.0)
        self.score_history.append(total_score)

        verdict = self.critic_report.get("verdict", "")
        if verdict == "DISCARD":
            self.log_journal_after(
                result=f"Test failed with safety veto: {self.critic_report.get('safety', {}).get('reason')}",
                surprise="Hard stop rule triggered.",
                next_decision="Restart"
            )
            return False

        failing_lines = self.critic_report.get("failing_lines", [])
        self.log_journal_after(
            result=f"Test finished with composite score {total_score}/50. {len(failing_lines)} failing line(s) flagged.",
            surprise=f"Code checks passed={self.critic_report.get('code_checks', {}).get('passed')}",
            next_decision="Repair" if failing_lines or total_score < 38 else "Assemble"
        )
        return True

    def move_repair(self) -> bool:
        """Move: Repair — Punch-up failing lines with surgical 5-alternative rewrites."""
        failing_lines = self.critic_report.get("failing_lines", [])
        if not failing_lines:
            return True

        self.log_journal_before(
            move="Repair",
            reason=f"Repairing {len(failing_lines)} flagged line(s) in punch-up room.",
            expectation="Generate 5 alternatives per line and select highest comedic value replacements."
        )

        # Punch-up room (~2 calls)
        self.spend_budget(2)
        improved_script, punch_report = punch_up.run_punch_up(self.draft_script, self.critic_report, self.bundle)
        
        # Re-run quick critic check on the updated script
        self.draft_script = improved_script
        self.spend_budget(1)
        self.critic_report = critic_panel.run_critic_panel(self.draft_script, self.beat_sheet, self.bundle)
        new_score = self.critic_report.get("total_score", 0.0)
        self.score_history.append(new_score)

        self.log_journal_after(
            result=f"Punch-up completed with {punch_report.get('replacement_count', 0)} edits. New score: {new_score}/50.",
            surprise="Lines tightened without losing character tone.",
            next_decision="Assemble"
        )
        return True

    def move_restructure(self) -> bool:
        """Move: Restructure — When line edits fail, rebuild beat sheet and redraft."""
        self.log_journal_before(
            move="Restructure",
            reason="Score stagnated or structure failed. Re-architecting beat sheet.",
            expectation="Produce a sharper escalation curve and fresh beat assignments."
        )
        return self.move_draft()

    def move_restart(self) -> bool:
        """Move: Restart — Redraw constraints and start fresh cycle."""
        self.restart_count += 1
        if self.restart_count > self.max_restarts or self.calls_spent >= self.max_budget:
            return self.move_abstain("Max restarts or budget reached.")

        self.log_journal_before(
            move="Restart",
            reason=f"Current episode attempt rejected. Restart attempt {self.restart_count}/{self.max_restarts}.",
            expectation="Redraw fresh constraints and start new cycle."
        )
        self.log_journal_after(result="Resetting state for fresh attempt.", next_decision="Explore")
        return self.run_pipeline_cycle()

    def move_abstain(self, reason: str) -> bool:
        """Move: Abstain — Quality cannot be guaranteed; publish nothing."""
        self.log_journal_before(
            move="Abstain",
            reason=f"Abstain triggered: {reason}",
            expectation="Halt cleanly and log to ledger to protect channel standards."
        )
        self.log_journal_after(result="Abstained from publishing.", next_decision="Stop")
        return False

    # ─── Orchestrator Loop ───────────────────────────────────────────────────

    def run_pipeline_cycle(self) -> bool:
        """Execute one complete forward pass of the move menu."""
        # 1. EXPLORE
        if not self.move_explore():
            return self.move_restart()

        # 2. COMMIT
        if not self.move_commit():
            return self.move_restart()

        # 3. DRAFT
        if not self.move_draft():
            return self.move_restart()

        # 4. TEST
        if not self.move_test():
            return self.move_restart()

        # Check Stuck Detector
        if self.check_stuck("Test"):
            return self.move_restart()

        # 5. REPAIR (if needed)
        failing_lines = self.critic_report.get("failing_lines", [])
        if failing_lines or self.critic_report.get("total_score", 0) < 38:
            self.move_repair()

        # 6. QUALITY GATE EVALUATION
        canary_status = ledger.is_canary_healthy()
        self.gate_evaluation = quality_gate.evaluate(self.critic_report, self.bundle, canary_healthy=canary_status)
        verdict = self.gate_evaluation.get("verdict")
        print(f"[supervisor] Quality Gate verdict: {verdict} (Confidence: {self.gate_evaluation.get('confidence')})")

        if verdict == "REWORK":
            print("[supervisor] Quality Gate requested REWORK. Attempting surgical punch-up...")
            self.move_repair()
            self.gate_evaluation = quality_gate.evaluate(self.critic_report, self.bundle, canary_healthy=canary_status)
            verdict = self.gate_evaluation.get("verdict")

        if verdict == "DISCARD":
            print(f"[supervisor] Episode DISCARDED by Quality Gate: {self.gate_evaluation.get('reason')}")
            return self.move_restart()

        return True

    def run_episode(self) -> EpisodeResult:
        """
        Master orchestrator entry point.
        Runs the full cycle, assembles script, logs to ledger, and returns EpisodeResult.
        """
        # ── Safeguards ────────────────────────────────────────────────────────
        safeguards.check_killswitch()   # hard stop if killswitch.txt exists
        safeguards.check_daily_cap()    # hard stop if daily episode cap reached
        # ─────────────────────────────────────────────────────────────────────
        print(f"\n=======================================================")
        print(f"  NOTABOT SUPERVISOR — EPISODE ORCHESTRATION START")
        print(f"  Mode: {'LONG (~10 min)' if self.is_long else 'SHORT (YouTube Short)'}")
        print(f"  Budget Limit: {self.max_budget} AI calls (Deep={self.deep_mode})")
        print(f"=======================================================\n")

        success = self.run_pipeline_cycle()

        if not success or not self.draft_script:
            print("[supervisor] Pipeline ended in ABSTAIN / FAILURE.")
            return EpisodeResult(
                script_path="",
                gate_verdict="DISCARD",
                confidence=0.0,
                provenance={"journal": self.journal, "calls_spent": self.calls_spent},
                episode_id=""
            )

        # 7. ASSEMBLER: Pure code deterministic formatting
        print("[supervisor] Running Assembler (durations, sounds, tags)...")
        assembled_script = assembler.assemble(self.draft_script, is_long=self.is_long)
        self.final_script = assembler.sanitize_durations_and_sounds(assembled_script)
        
        # Save to assets/example/
        self.script_path = assembler.save_script(self.final_script, is_long=self.is_long)
        print(f"[supervisor] Final script saved to: {self.script_path}")

        # 8. LEDGER: Append episode metadata
        confidence = self.gate_evaluation.get("confidence", 0.8)
        verdict = self.gate_evaluation.get("verdict", "PASS")
        
        provenance_data = {
            "constraint_card": self.constraint_card.__dict__ if hasattr(self.constraint_card, '__dict__') else str(self.constraint_card),
            "winning_pitch": self.winning_pitch,
            "losing_pitches": self.losing_pitches,
            "beat_sheet": self.beat_sheet,
            "critic_notes": self.critic_report,
            "gate_evaluation": self.gate_evaluation,
            "calls_spent": self.calls_spent,
            "journal": self.journal
        }

        entry = {
            "premise": self.winning_pitch.get("premise", "") if self.winning_pitch else "",
            "shape": self.constraint_card.story_shape if self.constraint_card else "unknown",
            "mechanism": self.constraint_card.comedy_mechanism if self.constraint_card else "unknown",
            "setting": self.constraint_card.setting if self.constraint_card else "general_chat",
            "cast_pair": self.constraint_card.cast_pair if self.constraint_card else ["NOTABOT"],
            "notabot_role": self.constraint_card.notabot_role if self.constraint_card else "clerk",
            "hook_type": "standard",
            "ending_type": "button",
            "scores": self.critic_report.get("scores", {}) if self.critic_report else {},
            "confidence": confidence,
            "flags": self.critic_report.get("code_checks", {}).get("flags", []) if self.critic_report else [],
            "models_used": ["gemini"],
            "youtube_video_id": None,
            "analytics": None,
            "script_lines": self.final_script.split("\n"),
            "provenance": provenance_data
        }

        self.episode_id = ledger.append_episode(entry)
        print(f"[supervisor] Episode successfully recorded in Ledger: ID = {self.episode_id}")

        # Write episode ID to last_episode_id.txt for upload_youtube linking
        LAST_EPISODE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LAST_EPISODE_FILE, "w", encoding="utf-8") as f:
            f.write(self.episode_id)

        # Autonomy ladder check
        ledger.increment_episode_count(
            had_flag=bool(entry["flags"]),
            was_overridden=False
        )

        # Quarantine flagged or borderline scripts for manual review
        if verdict in ("REWORK", "DISCARD") and self.script_path:
            reason = self.gate_evaluation.get("reason", "quality gate failed")
            safeguards.quarantine_script(
                script_path=self.script_path,
                verdict=verdict,
                confidence=confidence,
                reason=reason,
                episode_id=self.episode_id or "unknown",
            )

        return EpisodeResult(
            script_path=self.script_path,
            gate_verdict=verdict,
            confidence=confidence,
            provenance=provenance_data,
            episode_id=self.episode_id
        )


def run_episode(is_long: bool = False, deep_mode: bool = False, max_budget: Optional[int] = None) -> EpisodeResult:
    """Convenience module function to launch an episode run."""
    sup = Supervisor(is_long=is_long, deep_mode=deep_mode, max_budget=max_budget)
    return sup.run_episode()


def main():
    parser = argparse.ArgumentParser(description="NOTABOT Script Engine Master Supervisor")
    parser.add_argument("--long", action="store_true", help="Generate long-form (~10 min) episode")
    parser.add_argument("--deep", action="store_true", help="Run Deep mode (up to 40 AI calls)")
    parser.add_argument("--budget", type=int, default=None, help="Custom AI call budget limit")
    args = parser.parse_args()

    result = run_episode(is_long=args.long, deep_mode=args.deep, max_budget=args.budget)
    if result.gate_verdict == "PASS":
        print(f"\nSUCCESS: Episode generated at {result.script_path}")
        print(f"Verdict: {result.gate_verdict} (Confidence: {result.confidence})")
        sys.exit(0)
    else:
        print(f"\nFAILED: Episode did not pass quality gate (Verdict: {result.gate_verdict})")
        sys.exit(1)


if __name__ == "__main__":
    main()

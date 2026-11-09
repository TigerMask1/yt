"""
quality_gate.py
---------------
Stage 8 of the NOTABOT Script Engine: Quality Gate.
Evaluates the final critic panel report and score.
Verdicts:
  - PASS: total_score >= 32, safety PASS, confidence calculated.
  - REWORK: borderline score, routes back for one targeted adjustment.
  - DISCARD: safety violation or total_score < 32 after punch-up.
Calculates confidence formula:
  confidence = (score_margin / 20) + (critic_agreement * 0.3) + (canary_healthy * 0.2), clipped to [0.0, 1.0].
Routes scripts with confidence < 0.6 or Level 0/1 autonomy appropriately.
"""

import os
import json
import sys
from pathlib import Path
from typing import Dict, Optional, Any, Tuple

sys.path.insert(0, str(Path(__file__).parent))
import ledger
from foundation_loader import FoundationBundle, load_foundations

PASS_THRESHOLD = 32.0
BORDERLINE_FLOOR = 26.0
MAX_SCORE = 50.0

REVIEW_QUEUE_DIR = Path(__file__).parent.parent / "assets" / "review_queue"
DISCARD_ARCHIVE_DIR = Path(__file__).parent.parent / "assets" / "discard_archive"


def calculate_critic_agreement(scores: Dict[str, Any]) -> float:
    """
    Computes critic agreement score in [0.0, 1.0] based on consistency
    and consensus across the individual critic dimensions.
    """
    if not scores:
        return 0.5

    vals = []
    for k, v in scores.items():
        try:
            vals.append(float(v))
        except (ValueError, TypeError):
            continue

    if not vals:
        return 0.5

    # 1. Consensus pass rate (dimensions >= 3.0 out of 5)
    passing_ratio = sum(1.0 for s in vals if s >= 3.0) / len(vals)

    # 2. Score dispersion / agreement (low standard deviation = higher agreement)
    mean_score = sum(vals) / len(vals)
    variance = sum((s - mean_score) ** 2 for s in vals) / len(vals)
    std_dev = variance ** 0.5
    # Max possible std dev on [1, 5] scale is 2.0
    dispersion_agreement = max(0.0, 1.0 - (std_dev / 2.0))

    # Composite agreement: 50% pass consensus, 50% score convergence
    agreement = (passing_ratio * 0.5) + (dispersion_agreement * 0.5)
    return round(max(0.0, min(1.0, agreement)), 3)


def calculate_confidence(
    total_score: float,
    scores: Dict[str, Any],
    canary_healthy: bool
) -> Tuple[float, dict]:
    """
    Calculates confidence using the specified formula:
      confidence = (score_margin / 20) + (critic_agreement * 0.3) + (canary_healthy * 0.2),
      clipped to [0.0, 1.0].
    
    score_margin is calculated as max(0.0, total_score - 32.0).
    """
    score_margin = max(0.0, float(total_score) - PASS_THRESHOLD)
    margin_component = score_margin / 20.0

    critic_agreement = calculate_critic_agreement(scores)
    agreement_component = critic_agreement * 0.3

    canary_val = 1.0 if canary_healthy else 0.0
    canary_component = canary_val * 0.2

    raw_confidence = margin_component + agreement_component + canary_component
    confidence = round(max(0.0, min(1.0, raw_confidence)), 3)

    breakdown = {
        "score_margin": round(score_margin, 2),
        "margin_component": round(margin_component, 3),
        "critic_agreement": critic_agreement,
        "agreement_component": round(agreement_component, 3),
        "canary_healthy": canary_healthy,
        "canary_component": round(canary_component, 3),
        "raw_confidence": round(raw_confidence, 3),
        "confidence": confidence
    }
    return confidence, breakdown


def determine_targeted_adjustment(critic_report: dict) -> dict:
    """
    Identifies the weakest dimension and failing lines to guide
    a targeted punch-up rework loop.
    """
    scores = critic_report.get("scores", {})
    weakest_dim = "character_voice"
    lowest_score = 999.0

    dimension_guidance = {
        "hook": "Opening lines lack scrolling-stopping tension. Tighten the first 2 messages.",
        "character_voice": "Dialogue sounds generic or out-of-character. Align with cast persona cards.",
        "chat_realism": "Ban stage dialogue. Enforce rapid Discord burst typing and short fragments.",
        "code_compliance": "Address formatting flags, length restrictions, or banned phrases.",
        "notabot_fit": "NOTABOT must sound like an administrative, calm bureaucratic menace with error codes."
    }

    for dim, score in scores.items():
        try:
            s_val = float(score)
            if s_val < lowest_score:
                lowest_score = s_val
                weakest_dim = dim
        except (ValueError, TypeError):
            continue

    return {
        "weakest_dimension": weakest_dim,
        "dimension_score": lowest_score if lowest_score != 999.0 else 2.5,
        "guidance": dimension_guidance.get(weakest_dim, "Improve comedic sharpness and timing."),
        "failing_lines": critic_report.get("failing_lines", []),
        "safety_status": critic_report.get("safety", {}).get("verdict", "PASS")
    }


def evaluate(
    critic_report: dict,
    bundle: Optional[FoundationBundle] = None,
    canary_healthy: Optional[bool] = None,
    punch_up_done: bool = True,
    autonomy_level: Optional[int] = None,
    rework_count: int = 0
) -> dict:
    """
    Evaluates final critic panel report and score.
    
    Verdicts:
      - PASS: total_score >= 32, safety PASS, confidence calculated.
      - REWORK: borderline score, routes back for one targeted adjustment.
      - DISCARD: safety violation or total_score < 32 after punch-up.
    
    Routes scripts with confidence < 0.6 or Level 0/1 autonomy appropriately.
    """
    if canary_healthy is None:
        try:
            canary_healthy = ledger.is_canary_healthy()
        except Exception:
            canary_healthy = True

    if autonomy_level is None:
        try:
            autonomy_level = ledger.get_autonomy_level()
        except Exception:
            autonomy_level = 0

    scores = critic_report.get("scores", {})
    total_score = float(critic_report.get("total_score", 0.0))
    safety = critic_report.get("safety", {})
    safety_verdict = safety.get("verdict", "PASS")
    violating_lines = safety.get("violating_lines", [])

    confidence, conf_breakdown = calculate_confidence(total_score, scores, canary_healthy)

    # ─── 1. Safety Hard-Stop Evaluation ────────────────────────────────────────
    if safety_verdict == "DISCARD" or critic_report.get("verdict") == "DISCARD" or len(violating_lines) > 0:
        reason = f"Safety violation veto: {safety.get('reason', 'Hard stop violated')}"
        return {
            "verdict": "DISCARD",
            "total_score": 0.0,
            "confidence": 0.0,
            "confidence_breakdown": conf_breakdown,
            "autonomy_level": autonomy_level,
            "route": "DISCARD_ARCHIVE",
            "action": "DISCARD_SCRIPT",
            "requires_human_review": False,
            "reason": reason,
            "safety": safety,
            "targeted_adjustment": None
        }

    # ─── 2. Verdict Determination ──────────────────────────────────────────────
    targeted_adjustment = None

    if total_score >= PASS_THRESHOLD:
        verdict = "PASS"
        reason = f"Total score ({total_score}/50) meets or exceeds pass threshold ({PASS_THRESHOLD})."
    else:
        # total_score < 32
        if punch_up_done or rework_count >= 1:
            # After punch-up room, any score < 32 is DISCARD
            verdict = "DISCARD"
            reason = f"Score ({total_score}/50) is below {PASS_THRESHOLD} after punch-up room."
        elif total_score >= BORDERLINE_FLOOR:
            # Borderline score eligible for targeted adjustment
            verdict = "REWORK"
            reason = f"Borderline score ({total_score}/50) between {BORDERLINE_FLOOR} and {PASS_THRESHOLD}. Routing for targeted adjustment."
            targeted_adjustment = determine_targeted_adjustment(critic_report)
        else:
            # Score below borderline floor < 26
            verdict = "DISCARD"
            reason = f"Score ({total_score}/50) is below borderline floor ({BORDERLINE_FLOOR}). Not salvageable."

    # ─── 3. Routing Engine ─────────────────────────────────────────────────────
    if verdict == "PASS":
        # Check routing conditions: confidence < 0.6 or Level 0/1 autonomy
        needs_human = (confidence < 0.6) or (autonomy_level in (0, 1))

        if needs_human:
            route = "HUMAN_REVIEW_QUEUE"
            action = "QUEUE_FOR_HUMAN_APPROVAL"
            requires_human_review = True
            if autonomy_level in (0, 1) and confidence < 0.6:
                routing_reason = (
                    f"PASS ({total_score}/50): Low confidence ({confidence:.2f} < 0.6) "
                    f"and Autonomy Level {autonomy_level} mandate human review."
                )
            elif autonomy_level in (0, 1):
                routing_reason = (
                    f"PASS ({total_score}/50): Confidence is solid ({confidence:.2f}), "
                    f"but Autonomy Level {autonomy_level} requires human sign-off."
                )
            else:
                routing_reason = (
                    f"PASS ({total_score}/50): Confidence ({confidence:.2f} < 0.6) "
                    f"is below auto-publish threshold."
                )
        else:
            # confidence >= 0.6 and autonomy_level >= 2
            route = "AUTO_PRODUCTION"
            action = "PROCEED_TO_ASSEMBLY"
            requires_human_review = False
            routing_reason = (
                f"PASS ({total_score}/50): High confidence ({confidence:.2f} >= 0.6) "
                f"and Autonomy Level {autonomy_level} qualify for autonomous production."
            )

    elif verdict == "REWORK":
        route = "PUNCH_UP_ROOM"
        action = "TARGETED_PUNCH_UP"
        requires_human_review = False
        routing_reason = reason

    else:  # DISCARD
        route = "DISCARD_ARCHIVE"
        action = "DISCARD_SCRIPT"
        requires_human_review = False
        routing_reason = reason

    return {
        "verdict": verdict,
        "total_score": total_score,
        "confidence": confidence,
        "confidence_breakdown": conf_breakdown,
        "autonomy_level": autonomy_level,
        "route": route,
        "action": action,
        "requires_human_review": requires_human_review,
        "reason": routing_reason,
        "safety": safety,
        "scores": scores,
        "targeted_adjustment": targeted_adjustment
    }


def route_and_stage_script(
    evaluation: dict,
    script: str,
    episode_id: Optional[str] = None
) -> dict:
    """
    Stages the script into appropriate directory based on routing decision.
    """
    route = evaluation.get("route")
    ep_id = episode_id or f"script_{hash(script) & 0xffffffff:x}"

    if route == "HUMAN_REVIEW_QUEUE":
        REVIEW_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        review_file = REVIEW_QUEUE_DIR / f"{ep_id}.json"
        payload = {
            "episode_id": ep_id,
            "script": script,
            "evaluation": evaluation
        }
        with open(review_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        evaluation["staged_path"] = str(review_file)
        print(f"[quality_gate] Staged to Human Review Queue: {review_file}")

    elif route == "DISCARD_ARCHIVE":
        DISCARD_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        discard_file = DISCARD_ARCHIVE_DIR / f"{ep_id}.json"
        payload = {
            "episode_id": ep_id,
            "script": script,
            "evaluation": evaluation
        }
        with open(discard_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        evaluation["staged_path"] = str(discard_file)
        print(f"[quality_gate] Archived discarded script: {discard_file}")

    return evaluation


# Alias for explicit naming
evaluate_quality_gate = evaluate


if __name__ == "__main__":
    print("Testing Quality Gate evaluation scenarios...")

    # Case 1: High Pass with Level 0 Autonomy
    report_pass_l0 = {
        "total_score": 42.0,
        "scores": {"hook": 4.5, "character_voice": 4.0, "chat_realism": 4.5, "code_compliance": 5.0, "notabot_fit": 4.5},
        "safety": {"verdict": "PASS", "violating_lines": []}
    }
    res1 = evaluate(report_pass_l0, canary_healthy=True, punch_up_done=True, autonomy_level=0)
    print(f"\nCase 1 (Score 42, L0): Verdict={res1['verdict']}, Conf={res1['confidence']}, Route={res1['route']}")
    assert res1["verdict"] == "PASS"
    assert res1["route"] == "HUMAN_REVIEW_QUEUE"  # Autonomy 0 forces human review

    # Case 2: High Pass with Level 2 Autonomy
    res2 = evaluate(report_pass_l0, canary_healthy=True, punch_up_done=True, autonomy_level=2)
    print(f"Case 2 (Score 42, L2): Verdict={res2['verdict']}, Conf={res2['confidence']}, Route={res2['route']}")
    assert res2["verdict"] == "PASS"
    assert res2["route"] == "AUTO_PRODUCTION"  # Conf >= 0.6 and Level 2

    # Case 3: Borderline score before punch-up
    report_borderline = {
        "total_score": 29.5,
        "scores": {"hook": 3.0, "character_voice": 2.5, "chat_realism": 3.0, "code_compliance": 3.0, "notabot_fit": 3.0},
        "safety": {"verdict": "PASS", "violating_lines": []},
        "failing_lines": ["bad line here"]
    }
    res3 = evaluate(report_borderline, canary_healthy=True, punch_up_done=False)
    print(f"Case 3 (Score 29.5, Pre-punch): Verdict={res3['verdict']}, Route={res3['route']}, Adj={res3['targeted_adjustment']['weakest_dimension']}")
    assert res3["verdict"] == "REWORK"
    assert res3["route"] == "PUNCH_UP_ROOM"

    # Case 4: Score < 32 after punch-up
    res4 = evaluate(report_borderline, canary_healthy=True, punch_up_done=True)
    print(f"Case 4 (Score 29.5, Post-punch): Verdict={res4['verdict']}, Route={res4['route']}")
    assert res4["verdict"] == "DISCARD"
    assert res4["route"] == "DISCARD_ARCHIVE"

    # Case 5: Safety violation
    report_safety_veto = {
        "total_score": 45.0,
        "safety": {"verdict": "DISCARD", "reason": "Mentioned banned celebrity name", "violating_lines": ["real person"]}
    }
    res5 = evaluate(report_safety_veto)
    print(f"Case 5 (Safety Veto): Verdict={res5['verdict']}, Route={res5['route']}")
    assert res5["verdict"] == "DISCARD"

    print("\n[OK] All Quality Gate tests passed successfully!")

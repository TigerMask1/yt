"""
showrunner.py
-------------
Draws the constraint card for each episode.
Pure code — no AI calls.
Applies cooldowns, quotas, and wild-card rules against the ledger.
"""
import random
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

import ledger
from foundation_loader import FoundationBundle

@dataclass
class ConstraintCard:
    seed: int
    story_shape: str
    notabot_role: str
    comedy_mechanism: str
    setting: str
    twist_rule: str
    cast_pair: List[str]  # always includes NOTABOT + 1-2 others
    target_length: str  # "short" or "long"
    wild_card: Optional[str] = None  # extra surprise constraint if drawn

def _pick_without_cooldown(library: list, field_name: str, cooldown: int, quota: float = 0.25) -> str:
    """Pick a random item from library, respecting cooldowns and quotas."""
    candidates = [
        item for item in library
        if not ledger.is_on_cooldown(field_name, item, cooldown)
        and not ledger.exceeds_quota(field_name, item, quota)
    ]
    if not candidates:
        # Relax cooldown constraint if nothing is available
        candidates = [
            item for item in library
            if not ledger.exceeds_quota(field_name, item, quota)
        ]
    if not candidates:
        candidates = library  # fallback: use everything
    return random.choice(candidates)

def draw_constraint_card(bundle: FoundationBundle, is_long: bool = False) -> ConstraintCard:
    """Draw a fresh constraint card for this episode."""
    seed = random.randint(0, 999999)
    random.seed(seed)
    
    libs = bundle.showrunner_libraries
    
    # Wild card: 1 in 5 runs draws a constraint outside cooldown zone on purpose
    is_wild = random.random() < 0.20
    
    story_shape = _pick_without_cooldown(libs["story_shapes"], "shape", cooldown=5)
    notabot_role = _pick_without_cooldown(libs["notabot_roles"], "notabot_role", cooldown=2)
    comedy_mechanism = _pick_without_cooldown(libs["comedy_mechanisms"], "mechanism", cooldown=4)
    sparks = libs.get("situational_sparks", libs.get("settings", ["general_chat"]))
    setting = _pick_without_cooldown(sparks, "setting", cooldown=3)
    twist_rule = random.choice(libs["twist_rules"])
    
    # Cast pair: NOTABOT + 1-2 from the pool
    # Avoid repeating the same cast pair for 3 episodes
    cast_pool = libs["cast_pool"]
    n_others = 1 if not is_long else random.choice([1, 2])
    
    cast_candidates = [
        combo for combo in _get_cast_combos(cast_pool, n_others)
        if not ledger.is_on_cooldown("cast_pair", ["NOTABOT"] + list(combo), cooldown=3)
    ]
    if not cast_candidates:
        cast_candidates = _get_cast_combos(cast_pool, n_others)
    
    chosen_others = list(random.choice(cast_candidates)) if cast_candidates else [random.choice(cast_pool)]
    cast_pair = ["NOTABOT"] + chosen_others
    
    wild_card = None
    if is_wild:
        wild_card_options = [
            "Start the script with NOTABOT's message, not a human's.",
            "The first line must be a WELCOME join message.",
            "NOTABOT's role in this episode must expose its own mistake.",
            "One character must have no lines after the halfway point.",
            "The plant must be a number or timestamp.",
        ]
        wild_card = random.choice(wild_card_options)
    
    return ConstraintCard(
        seed=seed,
        story_shape=story_shape,
        notabot_role=notabot_role,
        comedy_mechanism=comedy_mechanism,
        setting=setting,
        twist_rule=twist_rule,
        cast_pair=cast_pair,
        target_length="long" if is_long else "short",
        wild_card=wild_card,
    )

def _get_cast_combos(pool: list, n: int) -> list:
    """Return all combinations of n characters from pool."""
    from itertools import combinations
    return list(combinations(pool, n))

def constraint_card_to_dict(card: ConstraintCard) -> dict:
    return {
        "seed": card.seed,
        "shape": card.story_shape,
        "notabot_role": card.notabot_role,
        "mechanism": card.comedy_mechanism,
        "setting": card.setting,
        "twist_rule": card.twist_rule,
        "cast_pair": card.cast_pair,
        "target_length": card.target_length,
        "wild_card": card.wild_card,
    }

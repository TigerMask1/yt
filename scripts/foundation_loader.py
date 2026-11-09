"""
foundation_loader.py
--------------------
Loads and validates all foundation files on startup.
Returns a FoundationBundle that the Supervisor carries throughout each episode run.
"""
import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional

FOUNDATIONS_DIR = Path(__file__).parent.parent / "assets" / "foundations"

@dataclass
class FoundationBundle:
    bible: str = ""  # raw markdown text
    cast_cards: Dict = field(default_factory=dict)
    rubric: Dict = field(default_factory=dict)
    golden_set: Dict = field(default_factory=dict)
    standards: Dict = field(default_factory=dict)
    failure_catalog: List = field(default_factory=list)
    chat_realism_guide: str = ""
    exemplar_bank: Dict = field(default_factory=dict)
    showrunner_libraries: Dict = field(default_factory=dict)

def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _load_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def load_foundations() -> FoundationBundle:
    """Load all foundation files and return a validated FoundationBundle."""
    missing = []
    required = [
        "bible.md", "cast_cards.json", "rubric.json", "golden_set.json",
        "standards.json", "failure_catalog.json", "chat_realism_guide.md",
        "exemplar_bank.json", "showrunner_libraries.json"
    ]
    for fname in required:
        if not (FOUNDATIONS_DIR / fname).exists():
            missing.append(fname)
    
    if missing:
        raise FileNotFoundError(
            f"Missing foundation files: {missing}. "
            f"Expected in {FOUNDATIONS_DIR}"
        )
    
    bundle = FoundationBundle(
        bible=_load_text(FOUNDATIONS_DIR / "bible.md"),
        cast_cards=_load_json(FOUNDATIONS_DIR / "cast_cards.json"),
        rubric=_load_json(FOUNDATIONS_DIR / "rubric.json"),
        golden_set=_load_json(FOUNDATIONS_DIR / "golden_set.json"),
        standards=_load_json(FOUNDATIONS_DIR / "standards.json"),
        failure_catalog=_load_json(FOUNDATIONS_DIR / "failure_catalog.json"),
        chat_realism_guide=_load_text(FOUNDATIONS_DIR / "chat_realism_guide.md"),
        exemplar_bank=_load_json(FOUNDATIONS_DIR / "exemplar_bank.json"),
        showrunner_libraries=_load_json(FOUNDATIONS_DIR / "showrunner_libraries.json"),
    )
    return bundle

def get_cast_card(bundle: FoundationBundle, character: str) -> dict:
    return bundle.cast_cards.get(character, {})

def get_cast_cards_for(bundle: FoundationBundle, characters: list) -> dict:
    return {c: bundle.cast_cards[c] for c in characters if c in bundle.cast_cards}

def get_failure_patterns(bundle: FoundationBundle) -> list:
    return [f["pattern"] + ": " + f["description"] for f in bundle.failure_catalog]

def get_banned_phrases(bundle: FoundationBundle) -> list:
    phrases = []
    for item in bundle.failure_catalog:
        phrases.extend(item.get("banned_phrases", []))
    return phrases

def get_hard_stops(bundle: FoundationBundle) -> list:
    return bundle.standards.get("hard_stops", [])

def get_exemplars_for_mechanism(bundle: FoundationBundle, mechanism: str, n: int = 2) -> list:
    """Return n exemplar contrast pairs relevant to a mechanism."""
    pairs = bundle.exemplar_bank.get("contrast_pairs", [])
    # Try to find pairs matching the mechanism
    relevant = [p for p in pairs if p.get("behavior") and mechanism in p.get("behavior", "")]
    if not relevant:
        relevant = pairs
    return relevant[:n]

def get_tone_anchors(bundle: FoundationBundle, n: int = 2) -> list:
    """Return n golden set items as tone anchors for the writer."""
    return bundle.golden_set.get("golden", [])[:n]

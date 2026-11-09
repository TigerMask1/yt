"""
assembler.py
------------
Takes approved plain dialogue with beat tags and converts it
to the final script format: Author:\nLine$^duration#!sound
No AI calls. Pure deterministic rules.
"""
import re
import json
import os
from pathlib import Path

ASSETS_DIR = Path(__file__).parent.parent / "assets"
VALID_SOUNDS = [
    "click", "confusion", "error", "explosion", "hamburger", "hehascome",
    "join", "knock", "leave", "message", "modeugene", "modpablo", "pop",
    "scary", "softmessage", "typing", "vineboom", "zap",
    "i_got_this", "yeah_yeah_boy", "fahh", "among_us_sus"
]
BEAT_TAG_RE = re.compile(r'\[beat_tag:(\w+)\]')
DURATION_RE = re.compile(r'\$\^([\d.]+)')
SOUND_RE = re.compile(r'#!(\w+)')

BEAT_DURATIONS = {
    "button": 2.5,
    "punchline": 2.0,
    "reveal": 2.2,
    "callback": 2.0,
    "plant": 1.5,
    "escalation": 1.8,
    "hook": 2.0,
    "default": 1.5,
    "burst": 1.0,
}

BEAT_SOUNDS = {
    "button": "vineboom",
    "punchline": "vineboom",
    "reveal": "scary",
    "callback": "explosion",
    "plant": "message",
    "escalation": "message",
    "hook": "message",
    "default": "message",
    "burst": "message",
}

FOOD_KEYWORDS = ["eat", "food", "hungry", "snack", "meal", "burger", "pizza", "lunch", "dinner", "salt", "sauce", "kale", "diet"]
CONFIDENT_PHRASES = ["i got this", "trust me", "easy", "watch this", "i'll handle", "i can fix"]
CELEBRATION_PHRASES = ["lets go", "yesss", "won", "got em", "nailed it"]
DISMISSAL_PHRASES = ["whatever", "doesn't matter", "ignore", "not my problem", "anyway"]
SUSPICIOUS_PHRASES = ["sus", "suspicious", "caught", "got you", "exposed", "found out"]

def _pick_duration(beat_tag: str, is_burst: bool = False) -> float:
    if is_burst:
        return BEAT_DURATIONS["burst"]
    return BEAT_DURATIONS.get(beat_tag, BEAT_DURATIONS["default"])

def _pick_sound(beat_tag: str, speaker: str, line_text: str, is_notabot_first: bool = False) -> str:
    line_lower = line_text.lower()
    
    if is_notabot_first and speaker == "NOTABOT":
        return "hehascome"
    
    if speaker == "fatas" and any(kw in line_lower for kw in FOOD_KEYWORDS):
        return "hamburger"
    
    if any(p in line_lower for p in CONFIDENT_PHRASES):
        return "i_got_this"
    
    if any(p in line_lower for p in CELEBRATION_PHRASES):
        return "yeah_yeah_boy"
    
    if any(p in line_lower for p in DISMISSAL_PHRASES):
        return "fahh"
    
    if any(p in line_lower for p in SUSPICIOUS_PHRASES):
        return "among_us_sus"
    
    sound = BEAT_SOUNDS.get(beat_tag, BEAT_SOUNDS["default"])
    if beat_tag == "reveal" and "error" in line_lower:
        sound = "error"
    
    return sound

def assemble(dialogue_text: str, is_long: bool = False) -> str:
    """
    Takes raw dialogue with optional [beat_tag:X] markers.
    Returns a fully formatted script string.
    """
    lines = dialogue_text.strip().split("\n")
    output = []
    
    current_speaker = None
    speaker_line_count = {}
    notabot_appeared = False
    sound_count = 0
    message_count = 0
    
    for line in lines:
        line = line.rstrip()
        if line.startswith("# TITLE:") or line.startswith("# PREMISE:"):
            output.append(line)
    
    for line in lines:
        line = line.rstrip()
        
        if line.startswith("# TITLE:") or line.startswith("# PREMISE:"):
            continue
        
        if line.startswith("#"):
            output.append(line)
            continue
        
        if not line:
            if output and output[-1] != "":
                output.append("")
            current_speaker = None
            continue
        
        # Check if line already has duration & sound (e.g. from pass-through)
        if line.endswith(":") and " " not in line.strip()[:-1]:
            speaker = line.rstrip(":")
            if speaker != current_speaker:
                if output and output[-1] != "":
                    output.append("")
                output.append(line)
                current_speaker = speaker
                speaker_line_count[speaker] = 0
            continue
        
        if line.startswith("WELCOME "):
            output.append(line if ("$^" in line) else f"{line}$^1.5#!join")
            continue
        
        # If line already formatted with $^ and #!
        if "$^" in line and "#!" in line:
            output.append(line)
            message_count += 1
            continue

        beat_match = BEAT_TAG_RE.search(line)
        beat_tag = beat_match.group(1) if beat_match else "default"
        clean_line = BEAT_TAG_RE.sub("", line).strip()
        
        speaker_line_count[current_speaker] = speaker_line_count.get(current_speaker, 0) + 1
        is_burst = speaker_line_count.get(current_speaker, 1) >= 3
        
        duration = _pick_duration(beat_tag, is_burst)
        
        is_notabot_first = (current_speaker == "NOTABOT" and not notabot_appeared)
        if current_speaker == "NOTABOT":
            notabot_appeared = True
        
        sound = _pick_sound(beat_tag, current_speaker or "", clean_line, is_notabot_first)
        
        if sound != "message":
            sound_count += 1
            if sound_count > (message_count + 1) / 2:
                sound = "message"
        
        message_count += 1
        output.append(f"{clean_line}$^{duration}#!{sound}")
    
    result = "\n".join(output)
    result = _validate_and_fix(result)
    return result

def _validate_and_fix(script: str) -> str:
    lines = script.split("\n")
    fixed = []
    
    for line in lines:
        if "#!" in line and not line.startswith("#"):
            sound_match = SOUND_RE.search(line)
            if sound_match:
                sound = sound_match.group(1)
                if sound not in VALID_SOUNDS:
                    line = line[:sound_match.start()] + "#!message"
        
        dur_match = DURATION_RE.search(line)
        if dur_match:
            dur = float(dur_match.group(1))
            if dur < 1.0:
                line = line[:dur_match.start(1)] + "1.0" + line[dur_match.end(1):]
        
        fixed.append(line)
    
    return "\n".join(fixed)

def save_script(script: str, is_long: bool = False) -> str:
    name = "generated_long_script.txt" if is_long else "generated_script.txt"
    output_path = ASSETS_DIR / "example" / name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(script)
    
    try:
        import ledger
        ledger.update_phrase_ledger(script.split("\n"))
    except Exception as e:
        print(f"[assembler] Warning updating phrase ledger: {e}")
    
    auto_register_characters(script)
    return str(output_path)

def auto_register_characters(script: str):
    char_json_path = ASSETS_DIR / "profile_pictures" / "characters.json"
    if not char_json_path.exists():
        return
    
    try:
        with open(char_json_path, "r", encoding="utf-8") as f:
            chars_db = json.load(f)
    except Exception:
        chars_db = {}
    
    unique_chars = set()
    for line in script.split("\n"):
        if line.startswith("WELCOME "):
            name = line.split(" ")[1].split("$^")[0]
            unique_chars.add(name)
        elif ":" in line and not line.startswith("#") and not line.strip().startswith("#"):
            name = line.split(":")[0].strip()
            if name and " " not in name:
                unique_chars.add(name)
    
    added = False
    for char in unique_chars:
        if char and char not in chars_db:
            import random
            color = "#{:06x}".format(random.randint(0, 0xFFFFFF))
            chars_db[char] = {"profile_pic": "perm/billy.jpeg", "role_color": color}
            added = True
    
    if added:
        with open(char_json_path, "w", encoding="utf-8") as f:
            json.dump(chars_db, f, indent=4)

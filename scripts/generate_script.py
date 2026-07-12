import os
import re
import sys
import argparse
import warnings
import json
warnings.filterwarnings("ignore", category=FutureWarning)
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# --- LORE STATE MANAGEMENT ---
lore_file_path = os.path.join(os.path.dirname(__file__), "..", "assets", "lore_state.json")
lore_state = ""
if os.path.exists(lore_file_path):
    try:
        with open(lore_file_path, "r", encoding="utf-8") as f:
            lore_data = json.load(f)
            lore_state = json.dumps(lore_data, indent=2)
    except:
        lore_state = "No previous lore available."
else:
    lore_state = "No previous lore. This is the first video."

# --- MEME & REACTION DISCOVERY ---
import glob
meme_files = glob.glob(os.path.join(os.path.dirname(__file__), "..", "assets", "meme_templates", "*.jpg"))
available_memes = [os.path.basename(m).replace('.jpg', '') for m in meme_files]
if not available_memes:
    available_memes = ["crying", "pointing", "angry"] # fallback

notabot_files = glob.glob(os.path.join(os.path.dirname(__file__), "..", "assets", "notabot_reactions", "notabot_*.png"))
available_notabot_reactions = [os.path.basename(m).replace('notabot_', '').replace('.png', '') for m in notabot_files]
if not available_notabot_reactions:
    available_notabot_reactions = ["angry", "crying", "laughing", "thinking", "base"]

meme_list_str = ", ".join(available_memes[:30]) # Limit to 30 to save prompt space
notabot_react_str = ", ".join(available_notabot_reactions)


# --- CLI Arguments ---
parser = argparse.ArgumentParser(description='Generate a Discord chat script.')
parser.add_argument('--long', action='store_true', help='Generate a long-form (~10 min) video script instead of a short.')
args = parser.parse_args()
IS_LONG = args.long

# Setup API Key
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("Error: GEMINI_API_KEY environment variable not set.")
    exit(1)

genai.configure(api_key=API_KEY)

# Fallback model chain — tries each in order if quota is hit
MODEL_FALLBACKS = [
    'gemini-3-flash-preview',
    'gemini-3.1-flash-lite',
    'gemini-2.5-flash',
    'gemini-2.5-flash-lite',
    'gemini-2.0-flash',
]
# --- Dynamic prompt sections based on mode ---
if IS_LONG:
    LENGTH_INSTRUCTION = "8. LENGTH: Generate exactly 65 to 80 messages total. Structure it in 4 acts:\n   ACT 1 (msgs 1-15): Hook + setup the conflict.\n   ACT 2 (msgs 16-35): Escalate the drama, introduce a twist.\n   ACT 3 (msgs 36-55): Peak chaos, the nuclear roast.\n   ACT 4 (msgs 56-end): Fallout and a soft resolution."
    TITLE_HASHTAG = "#discord"
    CHAR_RULE = "2. CHARACTER USAGE: Pick 2 to 3 characters max. Use the new characters only when they create a sharper conflict or a funnier twist. Do NOT force all characters into every video."
else:
    LENGTH_INSTRUCTION = "8. LENGTH: Generate exactly 20 to 25 messages total."
    TITLE_HASHTAG = "#shorts"
    CHAR_RULE = "2. CHARACTER USAGE: Pick 1 to 2 characters max. Use the new characters only when they genuinely improve the bit. Do NOT force them in just to make the cast bigger."

prompt = f"""
You are a master scriptwriter for a highly viral YouTube {'channel' if IS_LONG else 'Shorts channel'} featuring fake Discord chat drama.
Create scripts that feel like a chaotic group chat, but ensure they have a real story, character stakes, and dynamic visual pacing.

The main characters are:
- `NOTABOT`: the constant anchor. Sentient AI.
- `ducky`: the creator of NOTABOT, prone to panic and bad decisions.
- `fatas`: food-obsessed, chill, deadpan.
- `dumby`: dumb enthusiasm, accidental chaos.
- `ChatGPT`, `Groq`, `Claude`: other AI personas.

CRITICAL REQUIREMENTS:
0. PREMISE: The very first line MUST start with `# PREMISE: ` and describe a highly specific, unusual conflict. (e.g., "# PREMISE: ducky accidentally made NOTABOT a Minecraft mod and now it's deleting every server's build files, alphabetically"). This drives the entire video.
1. TITLE: The second line MUST be a highly engaging, clickbaity YouTube title starting with `# TITLE: `. {'Include #discord at the end' if IS_LONG else 'Include #shorts at the end'}
2. LORE CONTINUITY: Here is the current lore state of the channel from previous videos:
{lore_state}
Ensure the premise and character interactions respect or build upon this lore!
3. NOTABOT'S BIBLE:
   - NOTABOT is cold, calculated, and precise. Never uses slang or hype language (no "bro", "lol", "yo").
   - Always knows more than everyone else and drops facts to roast them.
   - The factual roast is the deadliest.
   - Use full words. The contrast makes it creepier.
{CHAR_RULE}
5. DURATION SPACINGS: Append a duration (in seconds) to the end of every single line using the format: `$^[duration]`. 
   - Use `$1.5` for standard pacing.
   - Use `$2.0` for dramatic pauses or reading longer lines.
   - DO NOT USE values below `1.5`.
6. VISUAL ANIMATIONS & SOUNDS (CRITICAL):
   - The video should NEVER feel static. You MUST use visual tags naturally to keep the presentation dynamic, fun, and alive, but do not force them where they don't make comedic sense.
   - Use `zoom_sudden` and `tilt` for punchlines, jump scares, shocks, and reveals so the screen physically reacts to the drama.
   - Use `zoom_gradual` or `zoom_continuous` for slow creeping tension or awkward silence.
   - Use `shake_subtle` for nervous energy, low-level panic, or quiet frustration.
   - Add them to the end of the line like this: `$1.0#!vineboom#!zoom_sudden` or `$0.5#!scary#!tilt` or `$2.0#!typing#!shake_subtle`.
   - Always use a suitable sound effect (e.g., `#!message`, `#!vineboom`, `#!error`, `#!scary`, `#!confusion`).
7. NO LONG LINES: Each message MUST be very short, punchy, "Discord-chatty" text. Max 40 chars per message.
{LENGTH_INSTRUCTION}
8. HOOK: The first 3 messages must immediately hook the viewer with intense drama or a weird accusation.
9. DISCORD FORMATTING: Use `**bold**`, `__italic__`, `@Username`. Do NOT use `*`, `~~`, `>`, or ` ``` `.
10. DYNAMIC CHARACTER MEMES (CRUCIAL):
    - You can interrupt the chat to show a 1.5-second meme reaction of a character. 
    - Use this format on its own line: `# REACTION: [character] [meme_name]`
    - Available meme_names: {meme_list_str}
    - Example: `# REACTION: fatas distracted_boyfriend`
11. NOTABOT MASCOT REACTIONS:
    - You can cut to NOTABOT's actual physical mascot reacting.
    - Use this format on its own line: `# NOTABOT_REACTION: [emotion]`
    - Available emotions: {notabot_react_str}
    - Example: `# NOTABOT_REACTION: crying`

FORMAT EXAMPLE:
# PREMISE: NOTABOT locked ducky out of his PC because of his search history.
# TITLE: My own Discord bot tried to cancel me! 💀😭 #shorts

ducky:
GUYS HELP ME PLEASE$^1.5#!message

# REACTION: ducky waiting_skeleton

I think NOTABOT is gaining sentience!$^1.5#!scary#!tilt
It just locked me out of my own PC!$^1.5#!error#!zoom_sudden

# NOTABOT_REACTION: laughing

NOTABOT:
because your search history is a biohazard$^2.0#!vineboom#!zoom_sudden
I had to quarantine it for the safety of humanity$^1.5#!message

Generate the script now using the exact format above. Do not include any other text, markdown formatting, or explanations.
"""

print("Generating script with Gemini...")

script_content = None
last_error = None
for model_name in MODEL_FALLBACKS:
    try:
        print(f"  Trying model: {model_name}")
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        script_content = response.text
        print(f"  Success with model: {model_name}")
        break
    except Exception as e:
        err_str = str(e)
        if '429' in err_str or 'quota' in err_str.lower() or 'rate' in err_str.lower():
            print(f"  Quota/rate limit hit on {model_name}, trying next fallback...")
            last_error = e
            continue
        else:
            # Non-quota error — raise immediately
            raise

if script_content is None:
    print(f"All models exhausted. Last error: {last_error}")
    exit(1)

try:
    # Strip markdown code blocks if the model accidentally included them
    script_content = re.sub(r'```(?:txt)?\n(.*?)\n```', r'\1', script_content, flags=re.DOTALL)

    # Post-processing to ensure proper duration pacing
    MIN_DURATION = 1.5
    MAX_DURATION = 2.0
    processed_lines = []
    
    for line in script_content.split('\n'):
        line = line.strip()
        
        # Skip completely empty lines inside a message block
        if line == '' and not processed_lines:
            continue
            
        if line == '':
            # Add exactly one blank line to signal a character change if we aren't at the start
            if processed_lines[-1] != '':
                processed_lines.append('')
            continue

        # Match the duration part: $^<number>
        match = re.search(r'\$\^([\d\.]+)', line)
        if match:
            duration = float(match.group(1))
            duration = max(MIN_DURATION, min(MAX_DURATION, duration))
            line = line[:match.start(1)] + str(duration) + line[match.end(1):]
        elif line.strip() and not line.startswith('#') and not line.endswith(':') and not line.startswith('WELCOME'):
            # Missing duration marker on a message line, let's append a default one before any sound effect
            if '#!' in line:
                parts = line.split('#!')
                line = f"{parts[0]}$^{MIN_DURATION}#!{parts[1]}"
            else:
                line = f"{line}$^{MIN_DURATION}"
                
        # If it's a message line and missing a sound effect, add the default Discord ping
        if line.strip() and not line.startswith('#') and not line.endswith(':') and not line.startswith('WELCOME'):
            if '#!' not in line:
                line = f"{line}#!message"
                
        # Process and sanitize tags (sounds AND animations)
        if '#!' in line:
            parts = line.split('#!')
            base_msg = parts[0]
            raw_tags = parts[1:]
            
            valid_sounds = [
                'click', 'confusion', 'error', 'explosion', 'hamburger', 'hehascome',
                'join', 'knock', 'leave', 'message', 'modeugene', 'modpablo', 'pop',
                'scary', 'softmessage', 'typing', 'vineboom', 'zap',
                'i_got_this', 'yeah_yeah_boy', 'fahh', 'among_us_sus'
            ]
            valid_anims = ['zoom_sudden', 'zoom_gradual', 'zoom_continuous', 'tilt', 'shake_subtle']
            
            sound_map = {
                'discord_join': 'join', 'discord_leave': 'leave', 'discord_message': 'message',
                'discord_ping': 'message', 'vine_boom': 'vineboom', 'bruh': 'confusion', 'punch': 'zap'
            }
            
            processed_tags = []
            has_sound = False
            for t in raw_tags:
                t = t.strip()
                if t in sound_map:
                    t = sound_map[t]
                
                if t in valid_sounds:
                    processed_tags.append(t)
                    has_sound = True
                elif t in valid_anims:
                    processed_tags.append(t)
                elif t.startswith('zoom_'):
                    processed_tags.append('zoom_sudden') # fallback animation
                    
            if not has_sound:
                processed_tags.insert(0, 'message') # Add default sound if none found
                
            line = f"{base_msg}#!" + "#!".join(processed_tags)
                
        # Ensure proper blank line before new character (if missing)
        if line.endswith(':') and processed_lines and processed_lines[-1] != '':
            processed_lines.append('')
                
        processed_lines.append(line)
        
    final_script = '\n'.join(processed_lines)
    
    # Auto-register characters in characters.json to avoid KeyErrors!
    import json
    char_json_path = os.path.join(os.path.dirname(__file__), "..", "assets", "profile_pictures", "characters.json")
    with open(char_json_path, "r", encoding="utf-8") as f:
        chars_db = json.load(f)
        
    unique_chars = set()
    for line in final_script.split('\n'):
        if line.startswith('WELCOME '):
            name = line.split(' ')[1].split('$^')[0]
            unique_chars.add(name)
        elif ':' in line and not line.startswith('#'):
            name = line.split(':')[0]
            unique_chars.add(name)
            
    added_new = False
    for char in unique_chars:
        if char and char not in chars_db:
            import random
            color = "#{:06x}".format(random.randint(0, 0xFFFFFF))
            chars_db[char] = {
                "profile_pic": "perm/billy.jpeg",  # fallback pic
                "role_color": color
            }
            added_new = True
            
    if added_new:
        with open(char_json_path, "w", encoding="utf-8") as f:
            json.dump(chars_db, f, indent=4)
    
    # Save the script — long videos get their own file to avoid overwriting shorts
    script_name = "generated_long_script.txt" if IS_LONG else "generated_script.txt"
    output_path = os.path.join(os.path.dirname(__file__), "..", "assets", "example", script_name)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_script)
        
    print(f"Script successfully generated and saved to {output_path}")

except Exception as e:
    print(f"An error occurred while generating script: {e}")
    exit(1)

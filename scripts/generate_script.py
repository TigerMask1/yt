import os
import re
import sys
import argparse
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
import google.generativeai as genai
from dotenv import load_dotenv

from dotenv import load_dotenv
import lore_manager

env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=env_path)
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
You are a scriptwriter for a viral YouTube {'channel' if IS_LONG else 'Shorts channel'}.
Create fake Discord chat videos that feel like real chaotic group-chat drama, but make them more unpredictable and more watchable than the usual bot-hates-me loop.
The main characters are:
- `NOTABOT`: the constant anchor of the scene. It is the main chaos engine, always present, always roasting, always one line away from turning the chat into a disaster.
- `ducky`: use him when the premise needs panic, bad decisions, creator energy, or someone to get absolutely wrecked.
- `fatas`: use him when the bit needs absurdly chill, food-obsessed, or deadpan reactions.
- `dumby`: use him when the bit needs dumb enthusiasm, nonsense energy, or accidental chaos.
- `ChatGPT`: use him when the premise is AI ego, smugness, fake expertise, or overconfident tech talk.
- `Groq`: use him when the premise is blunt takes, speed, sass, or aggressive internet energy.
- `Claude`: use him when the premise is calm but devastating logic, polished insults, or weirdly intelligent takedowns.

CAST RULE: NOTABOT is always in the scene. The other characters should be chosen based on what the video needs. Do not make ducky the default lead every time. Pick the character who makes the premise funniest or most specific.

LORE: ducky created NOTABOT, NOTABOT became sentient, and now the whole server is a pressure cooker. The vibe should feel like a group chat spiraling into disaster. Keep it entertaining, weird, and specific.

{lore_manager.get_lore_context()}

CRITICAL REQUIREMENTS:
0. TITLE AND PREMISE: 
   - First line MUST be a highly engaging, clickbaity YouTube title starting with `# TITLE: `. {'Include #discord at the end (not #shorts since this is a long video).' if IS_LONG else 'Include #shorts at the end.'}
   - Second line MUST be a premise summary starting with `# PREMISE: `. This defines the specific conflict (e.g., "# PREMISE: NOTABOT finds ducky's secret search history").
   Make the title feel fresh, specific, and a little unhinged. Avoid repetitive formulas. Every video should have a new angle, a new premise, and a title that does not sound like the last one.
1. NO LONG LINES (BELUGA STYLE): Messages MUST be extremely short, snappy, and fast. NEVER write a paragraph. NEVER use complex English. Use all lowercase for a casual internet vibe. Keep it under 5-8 words per message. If someone is talking a lot, spam 5 short messages in a row rather than one long one.
{CHAR_RULE}
3. VARIETY: Do not make every video about the same topic. Rotate between AI meltdowns, cursed server drama, dumb tech support, fake "bro therapy", weird app launches, chaotic misunderstandings, absurdly specific disasters, random server chaos, and trend-adjacent internet nonsense. Make each script feel fresh and native to a chaotic teen Discord vibe.
4. HOOK: The first 3 messages must create instant curiosity, tension, or absurdity. Use a dramatic reveal, a ridiculous accusation, a weird accusation, or a line that makes people want to know what happened next.
5. RETENTION: Use one surprise twist, one brutal roast, one "wait what" moment, and one line that feels comment-worthy. The kind of line that makes people type things like "that sht was not wind gng" or "bro said it like he meant it". Make the script feel like it contains a moment people will argue about in the comments.
6. TREND/BAIT ENERGY: Think like a teen-focused chaotic internet bit. Use topics that feel current, memeable, and a little ridiculous. If the premise feels like it could be a screenshot from a real group chat, that is good.
7. REAL-WORLD POP CULTURE: You MUST seamlessly weave in at least one specific real-world trending topic, sports drama, recent movie/game release, or internet meme that is currently popular. Do not use generic examples—pick something highly specific that people are arguing about online right now. Make it sound like terminally online teens arguing about current events.
8. RAPID-FIRE MESSAGES: If a character has a lot to say, break it up into multiple rapid-fire lines underneath their name! DO NOT re-write their name for every single line. Group consecutive messages under one name header.
9. DURATION SPACINGS: Append a duration (in seconds) to the end of every single line using the format: `$^<duration>`. Use `$1.0` or `$1.5` for fast spam, and `$2.0` or `$3.0` for dramatic pauses. pauses.
5. SOUND EFFECTS: Add sound effects where they genuinely enhance the moment — do NOT pile them on every line. Pick the one that fits best:
   - `#!message` : Default Discord ping. Normal messages.
   - `#!vineboom` : Vine boom drop. Peak comedic punchline or dramatic reveal.
   - `#!error` : Windows error. When something goes terribly wrong.
   - `#!explosion` : Big boom. Absolute chaos or nuclear roast.
   - `#!scary` : Horror sting. Sudden dread or ominous moment.
   - `#!confusion` : Bruh sound. Total bewilderment.
   - `#!zap` : Electric zap. Sharp, sudden shock.
   - `#!pop` : Soft pop. Quick reaction, minor moment.
   - `#!hehascome` : Dramatic arrival. When NOTABOT enters or drops a legendary line.
   - `#!hamburger` : Random food sound. For fatas moments only.
   - `#!knock` : Knock sound. Someone is about to get it.
   - `#!typing` : Keyboard typing. Building suspense.
   - `#!join` / `#!leave` : Server join/leave. Only for WELCOME lines.
   use these a lot because of lots of moments need this(special):
   - `#!i_got_this` : Confident "I got this" voice clip. Use when a character OVERCONFIDENTLY claims they'll handle something (before failing spectacularly).
   - `#!yeah_yeah_boy` : Hype "YEAH YEAH BOY" shout. Use for peak celebration or when hyping up a roast.
   - `#!fahh` : Dismissive scoff/"pfft" sound. Use when someone is being utterly dismissed or brushed off.
   - `#!among_us_sus` : Among Us "sus" sting. Use for suspicious moments or when someone gets called out.

6. Keep a proportion in the whole video for example: 2:1 ratio for messages and sound effects and 5:1 ratio for messages and clips. these clips or messages are not forced to come after 2nd message or 5th, these are just porportions. they can come anywhere where ever relevant. this is maximum cap and prefereable zone.
   and start every video with a suitable sound compulsarily to hook viewers(advised to use those 4 special marked sounds.
7. VIDEO CLIP INSERTS: We are replacing reaction GIFs with aesthetic/relatable video clips. You may insert a full-screen video clip — but ONLY when it fits naturally to break the pace or show a specific aesthetic vibe. Use a MAX of 1-2 CLIPs per script total.
   CRITICAL FORMAT: Output EXACTLY `# CLIP: name` — the name must be a raw word, NO quotes, NO backticks, NO extra characters. Example: `# CLIP: aesthetic_birthday_decor` NOT `# CLIP: 'aesthetic_birthday_decor'`.
   - `# CLIP: aesthetic_birthday_decor` : A luxury birthday party setup. Use ONLY when a character is flexing, planning an extravagant party, or acting extremely spoiled/rich.
   - `# CLIP: aesthetic_party_ideas` : Classy and curated party decor. Use ONLY when discussing fancy plans, "aesthetic" goals, or high-class living.
   - `# CLIP: aesthetic_quotes` : Motivating/inspirational quotes overlay. Use ONLY when a character gives "fake deep" advice, pretends to be wise, or drops a generic motivational quote out of nowhere.
   - `# CLIP: aesthetic_family_dinner` : A simple, timeless family dinner. Use ONLY when someone mentions eating together, family, or fatas dreaming of a huge peaceful meal.
   - `# CLIP: aesthetic_living_room` : A cozy, trending living room. Use ONLY when talking about chilling, being lazy, sleeping all day (fatas), or creating a cozy vibe.

{LENGTH_INSTRUCTION}
9. HOOK: The first 3 messages must immediately hook the viewer with intense drama.
10. DISCORD FORMATTING: Use `**bold**`, `__italic__`, `@Username`, or ONLY emojis (which render 2x larger). Do NOT use `*`, `~~`, `>`, or ` ``` `.
11. SYSTEM MESSAGES: The `WELCOME CharacterName$^1.5#!join` syntax should be used VERY RARELY. Do not spam it.
12. LORE UPDATE: The VERY LAST line of your output MUST start with `# LORE_UPDATE: ` followed by a 1-sentence summary of how this specific episode ended (e.g., "# LORE_UPDATE: NOTABOT blackmailing ducky with his search history").

FORMAT EXAMPLE:
# TITLE: My own Discord bot tried to cancel me! 💀😭 #shorts
# PREMISE: ducky realizes NOTABOT has admin rights and is leaking his files.

ducky:
GUYS HELP ME PLEASE$^2.0#!message
I think NOTABOT is gaining sentience!$^1.5#!scary
It just locked me out of my own PC!$^1.5#!error

NOTABOT:
because your search history is a biohazard$^2.0#!vineboom
I had to quarantine it for the safety of humanity$^1.5#!message

fatas:
did someone say biohazard?$^2.0#!message
can I eat it?$^1.5#!message

# LORE_UPDATE: NOTABOT locked ducky out of his PC because of his search history.

Generate the script now using the exact format above. Do not include any other text, markdown formatting, or explanations.
the content should have variety not just same topic again and again. be creative and make it fun so people can watch it.
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

    # Post-processing to ensure minimum duration
    MIN_DURATION = 1.5
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

        if line.startswith('# LORE_UPDATE:'):
            lore_manager.update_lore_from_summary(line.replace('# LORE_UPDATE:', '').strip())
            continue
            
        if line.startswith('# PREMISE:'):
            continue

        # Match the duration part: $^<number>
        match = re.search(r'\$\^([\d\.]+)', line)
        if match:
            duration = float(match.group(1))
            if duration < MIN_DURATION:
                # Replace with min duration
                line = line[:match.start(1)] + str(MIN_DURATION) + line[match.end(1):]
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
                
        # Sanitize sound effects (Gemini often hallucinates these despite prompt instructions)
        if '#!' in line:
            parts = line.split('#!')
            sound = parts[1].strip()
            
            # Map common hallucinations to real sounds
            sound_map = {
                'discord_join': 'join',
                'discord_leave': 'leave',
                'discord_message': 'message',
                'discord_ping': 'message',
                'vine_boom': 'vineboom',
                'bruh': 'confusion',
                'punch': 'zap'
            }
            if sound in sound_map:
                sound = sound_map[sound]
                
            # If it's still not a valid sound, default to message or remove it
            valid_sounds = [
                'click', 'confusion', 'error', 'explosion', 'hamburger', 'hehascome',
                'join', 'knock', 'leave', 'message', 'modeugene', 'modpablo', 'pop',
                'scary', 'softmessage', 'typing', 'vineboom', 'zap',
                'i_got_this', 'yeah_yeah_boy', 'fahh', 'among_us_sus'
            ]
            if sound not in valid_sounds:
                sound = 'message'  # fallback
                
            line = f"{parts[0]}#!{sound}"
                
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

import os
import subprocess
import sys

CLIPS_DIR = r"c:\Users\LENOVO\Documents\disc\Text-2-Beluga\assets\clips"
os.makedirs(CLIPS_DIR, exist_ok=True)

# Define the exact meme searches that will yield funny/dramatic results
MEME_CLIPS = {
    # High Priority
    "hacker_typing.mp4": "hackerman hacker typing meme green screen short",
    "dramatic_explosion.mp4": "nuke explosion meme short sound effect",
    "matrix_code.mp4": "matrix code rain effect short",
    "windows_error.mp4": "windows error bsod glitch meme short",
    "guy_crying.mp4": "black guy crying meme green screen short",
    "guy_shocked.mp4": "black guy shocked meme green screen short",
    "money_printer.mp4": "make it rain money falling green screen meme short",
    "empty_wallet.mp4": "mr krabs empty wallet meme short",
    
    # Comedy
    "nobody_cares.mp4": "nobody cares spongebob meme short",
    "crowd_laughing.mp4": "crowd laughing meme sound effect short",
    "judge_gavel.mp4": "judge gavel slam meme short",
    "walking_away.mp4": "aight imma head out spongebob meme short",
    "spinning_newspaper.mp4": "spinning newspaper breaking news meme green screen",
    "boss_chair_spin.mp4": "dr evil chair spin meme short",
    "clapping_hands.mp4": "slow clap meme green screen short",
    
    # Gaming/Chaos
    "minecraft_fire.mp4": "minecraft fire burning meme short",
    "minecraft_creeper.mp4": "minecraft creeper explosion meme short",
    "game_over.mp4": "gta wasted game over meme green screen short",
    "ragequit_desk.mp4": "angry gamer smash keyboard desk meme short",
    "speedrun_typing.mp4": "fast typing meme sped up short",
    "gaming_setup_dark.mp4": "rgb gaming setup aesthetic short",
    
    # Office
    "powerpoint_slide.mp4": "boring presentation meme short",
    "ceo_office.mp4": "boss sitting at desk meme short",
    "contract_signing.mp4": "signing contract meme short",
    "job_interview.mp4": "awkward interview meme short",
    "fired_leaving.mp4": "getting fired meme short",
    "union_meeting.mp4": "office meeting meme short",
    
    # Food/Sad/Abstract
    "huge_meal.mp4": "nikocado avocado eating meme short",
    "sleeping_chair.mp4": "snoring sleeping meme short",
    "fast_food_asmr.mp4": "burger eating meme short",
    "sad_rain_window.mp4": "sad spongebob rain window meme short",
    "head_on_desk.mp4": "giving up head on desk meme short",
    "lone_person_bench.mp4": "sad naruto swing meme short",
    "lightning_strike.mp4": "low tier god lightning meme green screen short",
    "countdown_timer.mp4": "24 countdown timer meme short",
    "glitch_effect.mp4": "vhs glitch effect green screen meme short",
    "courtroom_drama.mp4": "phoenix wright objection meme short",
    "news_anchor.mp4": "fish news anchor spongebob meme short",
}

def download_clip(filename, search_term):
    filepath = os.path.join(CLIPS_DIR, filename)
    if os.path.exists(filepath):
        print(f"[SKIP] {filename} already exists.")
        return

    print(f"\n[DOWNLOAD] Fetching '{filename}' using search: '{search_term}'...")
    
    # Use yt-dlp to search youtube for the term, grab the first result, and download it as mp4
    command = [
        "yt-dlp",
        f"ytsearch1:{search_term}",
        "--format", "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--output", filepath,
        "--no-playlist",
        "--match-filter", "duration < 60", # ensure we only get short clips (memes)
    ]
    
    try:
        subprocess.run(command, check=True)
        print(f"[SUCCESS] Saved {filename}")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to download {filename}: {e}")

if __name__ == "__main__":
    print("Installing yt-dlp if missing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "yt-dlp", "-U"], check=True)
    
    for filename, search_term in MEME_CLIPS.items():
        download_clip(filename, search_term)
    
    print("\nAll downloads complete!")

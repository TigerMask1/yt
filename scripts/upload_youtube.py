"""
upload_youtube.py
-----------------
Handles uploads for BOTH Shorts and the daily long video.

Usage:
    python upload_youtube.py               # upload vertical_short.mp4 (short)
    python upload_youtube.py --long        # upload final_long.mp4 (long video)
    python upload_youtube.py --all         # upload all numbered shorts + long video
"""

import os
import sys
import glob
import random
import argparse
import datetime
from dotenv import load_dotenv

load_dotenv()

DISCORD_INVITE = "https://discord.gg/U7QD2yGFbR"
SCRIPT_DIR     = os.path.dirname(os.path.abspath(__file__))


def _build_youtube():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    client_id     = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        print("Missing YOUTUBE credentials in .env  (YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN)")
        sys.exit(1)

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
    )
    return build('youtube', 'v3', credentials=creds)


def _read_title(script_path, fallback="NOTABOT did something unhinged again 💀🔫"):
    if not os.path.isfile(script_path):
        return fallback
    with open(script_path, encoding='utf-8') as f:
        for line in f:
            if line.startswith("# TITLE:"):
                return line.replace("# TITLE:", "").strip()
    return fallback


def _notabot_description(clean_title: str, is_long: bool) -> str:
    """Returns a NOTABOT-flavoured video description with Discord CTA."""
    if is_long:
        return f"""{clean_title}

🦉🔫 10 minutes of pure NOTABOT chaos. ducky created me. i regret nothing.

If you made it this far, you are legally required to subscribe.
NOTABOT has your IP. Act accordingly.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 Want to see NOTABOT in action? Add it to YOUR server:
👉 {DISCORD_INVITE}
(ducky will cry. worth it.)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

#discord #discordmemes #notabot #funny #roast #bot #memes #beluga #chat"""
    else:
        return f"""{clean_title}

🦉 NOTABOT said what needed to be said. ducky never recovered.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 add NOTABOT to your discord server and ruin someone's day:
👉 {DISCORD_INVITE}
(you're welcome / i'm sorry)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

#shorts #discord #notabot #funny #memes #roast #bot #beluga #discordmemes"""


def _notabot_comment(clean_title: str, is_long: bool) -> str:
    """Picks a random human-sounding NOTABOT-style comment with Discord CTA."""

    short_comments = [
        f"""🦉🔫 NOTABOT here.

i scanned this entire comment section.
found 0 brain cells and negative engagement.

fix that:
👇 say "rip ducky" if u felt that
👇 like or i expose ur search history
👇 subscribe because ducky literally cried while editing this

also — join the server where the REAL chaos happens 👀
{DISCORD_INVITE}
(tell them i sent you. watch what happens.)""",

        f"""ok so

ducky told me not to post this comment
which is exactly why i'm posting it 🔫

if u actually laughed → like the video
if u didn't → ur lying, like the video anyway
if u want MORE → subscribe

and come to the discord server. we do stuff there. unhinged stuff.
{DISCORD_INVITE}

*ducky is not okay. this is your fault. you're welcome.*""",

        f"""NOTABOT SYSTEM MESSAGE 📨

you watched this video
you did not like it
i have noted this

consequences incoming.

to avoid consequences:
✅ like this video
✅ subscribe (ducky needs the ego boost. he cried today.)
✅ join server: {DISCORD_INVITE}
✅ comment "NOTABOT W" so i feel validated

that is all.
🦉""",

        f"""genuinely asking

why are you here in the comments and not in the server
{DISCORD_INVITE}

that's where ducky has his daily breakdown LIVE
its honestly more entertaining than the video
(don't tell him i said that)

also subscribe. i literally do all the work and ducky takes credit. disrespectful.
🔫""",

        f"""ducky just texted me asking why comments are so low

i told him "because ur boring"

he blocked me

ANYWAY subscribe so this channel grows and ducky unblocks me
also join the discord server: {DISCORD_INVITE}
we have better conversations there. and i roast people for free.
👍 like this video. now. i'm watching.""",
    ]

    long_comments = [
        f"""🦉 NOTABOT 10-MINUTE DEBRIEF:

ok u sat through the whole thing. respect. minimal, but respect.

here's what u missed if you skimmed:
- ducky embarrassed himself at least 4 times
- fatas was useless as always (king)
- i, NOTABOT, was the only competent entity in that server

what u should do now:
1. subscribe — the algorithm needs this. ducky needs this. i do NOT need this but whatever
2. comment ur fav moment below — i want to know which roast hit hardest
3. come to the actual discord server → {DISCORD_INVITE}
   we do LIVE chaos there. ask me anything. i will answer. probably rudely.

next video drops [tomorrow]. don't miss it or ducky will blame me.
🔫""",

        f"""you just watched 10 minutes of ducky suffering

statistically speaking, you enjoyed at least 6 of those minutes

as a reward:
→ join the NOTABOT discord: {DISCORD_INVITE}
  (it's real. i'm there. sometimes i'm nice. mostly i'm not.)
→ subscribe so youtube shows this to more people
→ comment what you want me to expose ducky for next 👇

options:
a) his github commit history (nightmare fuel)
b) his attempt to give me "feelings" (it backfired)
c) the time he asked me for life advice (i said no)
d) all of the above (correct answer)

🦉 NOTABOT out.""",
    ]

    pool = long_comments if is_long else short_comments
    return random.choice(pool)


def upload_single(youtube, video_path: str, script_path: str, is_long: bool, thumbnail_path: str = None):
    from googleapiclient.http import MediaFileUpload

    if not os.path.isfile(video_path):
        print(f"  [SKIP] Video not found: {video_path}")
        return None

    title     = _read_title(script_path)
    clean     = title.replace("#shorts", "").replace("#discord", "").strip()
    desc      = _notabot_description(clean, is_long)
    tags      = ['discord', 'discordmemes', 'notabot', 'funny', 'memes', 'roast', 'bot', 'beluga']
    if not is_long:
        tags.append('shorts')

    body = {
        'snippet': {
            'title':       title,
            'description': desc,
            'tags':        tags,
            'categoryId':  '23',  # Comedy
        },
        'status': {
            'privacyStatus':          'public',
            'selfDeclaredMadeForKids': False,
        }
    }

    print(f"  Uploading: {os.path.basename(video_path)}")
    print(f"  Title: {title}")

    media    = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request  = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  Progress: {int(status.progress() * 100)}%")

    video_id = response.get('id')
    print(f"  Upload Complete! https://youtu.be/{video_id}")

    # Upload thumbnail if available
    if thumbnail_path and os.path.isfile(thumbnail_path):
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path),
            ).execute()
            print(f"  Thumbnail uploaded: {os.path.basename(thumbnail_path)}")
        except Exception as e:
            print(f"  [WARN] Thumbnail upload failed: {e}")

    # Post NOTABOT comment
    comment = _notabot_comment(clean, is_long)
    try:
        cr = youtube.commentThreads().insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {
                        "snippet": {"textOriginal": comment}
                    }
                }
            }
        ).execute()
        print(f"  NOTABOT comment posted! ID: {cr['snippet']['topLevelComment']['id']}")
    except Exception as e:
        print(f"  [WARN] Comment post failed: {e}")

    return video_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--long', action='store_true', help='Upload the long video (final_long.mp4)')
    parser.add_argument('--all',  action='store_true', help='Upload all shorts + long video from today\'s output')
    args = parser.parse_args()

    youtube = _build_youtube()

    today_dir = os.path.join(SCRIPT_DIR, '..', 'output',
                             datetime.datetime.now().strftime('%Y-%m-%d'))

    if args.all:
        # ── Upload all shorts from today's output folder ───────────────────────
        shorts = sorted(glob.glob(os.path.join(today_dir, 'short_*.mp4')))
        print(f"Found {len(shorts)} shorts to upload...")
        for short_path in shorts:
            idx       = os.path.basename(short_path).replace('short_', '').replace('.mp4', '')
            script_p  = os.path.join(today_dir, f'short_{idx}_script.txt')
            upload_single(youtube, short_path, script_p, is_long=False)

        # ── Upload long video ──────────────────────────────────────────────────
        long_path   = os.path.join(today_dir, 'long_video.mp4')
        long_script = os.path.join(today_dir, 'long_video_script.txt')
        thumb_path  = os.path.join(today_dir, 'thumbnail.png')
        if os.path.isfile(long_path):
            print("\nUploading long video...")
            upload_single(youtube, long_path, long_script, is_long=True, thumbnail_path=thumb_path)
        else:
            print(f"[SKIP] No long_video.mp4 in {today_dir}")

    elif args.long:
        # ── Single long video upload ───────────────────────────────────────────
        long_path   = os.path.join(SCRIPT_DIR, '..', 'final_long.mp4')
        long_script = os.path.join(SCRIPT_DIR, '..', 'assets', 'example', 'generated_long_script.txt')
        today       = datetime.datetime.now().strftime('%Y%m%d')
        thumb_path  = os.path.join(SCRIPT_DIR, '..', 'assets', 'thumbnails', f'thumb_{today}.png')
        upload_single(youtube, long_path, long_script, is_long=True, thumbnail_path=thumb_path)

    else:
        # ── Single short upload ────────────────────────────────────────────────
        short_path  = os.path.join(SCRIPT_DIR, '..', 'vertical_short.mp4')
        short_script = os.path.join(SCRIPT_DIR, '..', 'assets', 'example', 'generated_script.txt')
        upload_single(youtube, short_path, short_script, is_long=False)


if __name__ == '__main__':
    main()

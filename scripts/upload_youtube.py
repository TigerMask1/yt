import os
import google.auth
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

load_dotenv()


def get_discord_invite():
    invite = os.environ.get("DISCORD_SERVER_INVITE", "").strip()
    return invite if invite else "https://discord.gg/example"


def upload_video():
    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        print("Missing YOUTUBE credentials in environment variables.")
        exit(1)

    # Reconstruct credentials using refresh token
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token"
    )

    youtube = build('youtube', 'v3', credentials=creds)

    video_candidates = [
        os.path.join(os.path.dirname(__file__), "..", "vertical_short.mp4"),
        os.path.join(os.path.dirname(__file__), "..", "final_long.mp4")
    ]
    existing_videos = [path for path in video_candidates if os.path.exists(path)]
    if not existing_videos:
        print("No generated video file found. Generate a short or long video first.")
        exit(1)
    video_path = max(existing_videos, key=os.path.getmtime)

    print(f"Uploading to YouTube video: {os.path.basename(video_path)}...")
    
    # Dynamic title extraction from the generated script
    title = "OMG IS THIS EVEN A BOT?! 🤖🔥"  # fallback
    script_files = [
        os.path.join(os.path.dirname(__file__), "..", "assets", "example", "generated_script.txt"),
        os.path.join(os.path.dirname(__file__), "..", "assets", "example", "generated_long_script.txt")
    ]
    existing_scripts = [path for path in script_files if os.path.exists(path)]
    if existing_scripts:
        script_path = max(existing_scripts, key=os.path.getmtime)
        with open(script_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("# TITLE:"):
                    title = line.replace("# TITLE:", "").strip()
                    break
    discord_invite = get_discord_invite()
    description = f"NOTABOT roasts another victim! 💀🔥 Join the chaos on Discord: {discord_invite}\n\n#discord #memes #beluga #notabot #roast #shorts"

    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': ['discord', 'memes', 'beluga', 'funny', 'shorts', 'bot', 'roast'],
            'categoryId': '23' # Comedy
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False
        }
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")

    video_id = response.get('id')
    print(f"Upload Complete! Video ID: {video_id}")
    
    # Post a pinned NOTABOT-style comment
    post_comment(youtube, video_id, title)


def post_comment(youtube, video_id, title):
    """Post a funny NOTABOT-style engagement comment on the uploaded video."""
    import random
    
    # Strip #shorts and emojis from title for cleaner reference
    clean_title = title.replace("#shorts", "").replace("#Shorts", "").strip()
    
    discord_invite = get_discord_invite()
    comment_templates = [
        f"""yo this one had me like... that sht was not wind gng.
if you watched this far, you already know the bot is unhinged.
join the Discord before NOTABOT starts roasting your name next: {discord_invite}
drop a "NO WAY" if you felt that one.""",

        f"""🦉 NOTABOT here.
this was not a normal roast, this was a full server disaster.
if you want more chaos, join the Discord and see what happens next: {discord_invite}
comment your reaction below and tell me who should get roasted next.""",

        f"""bro this video had me locked in.
that was way too specific, way too mean, and somehow still funny.
come join the Discord if you want the next one before it gets posted: {discord_invite}
comment "rip ducky" if you felt that one 💀""",

        f"""i scanned the comments and found a serious lack of commitment.
so here is your reminder: this bot is still unhinged, the server is still active, and the next episode might be worse.
join the Discord here: {discord_invite}
comment your favorite line below and let me know if you want more."""
    ]
    
    comment_text = random.choice(comment_templates)
    
    try:
        comment_response = youtube.commentThreads().insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {
                        "snippet": {
                            "textOriginal": comment_text
                        }
                    }
                }
            }
        ).execute()
        
        comment_id = comment_response["snippet"]["topLevelComment"]["id"]
        print(f"NOTABOT comment posted! Comment ID: {comment_id}")
        
    except Exception as e:
        print(f"Warning: Could not post comment: {e}")


if __name__ == "__main__":
    upload_video()

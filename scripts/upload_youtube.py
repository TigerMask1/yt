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

    video_path = os.path.join(os.path.dirname(__file__), "..", "vertical_short.mp4")
    if not os.path.exists(video_path):
        print(f"File not found: {video_path}")
        exit(1)

    print("Uploading to YouTube Shorts...")
    
    # Dynamic title extraction from the generated script
    title = "OMG IS THIS EVEN A BOT?! 🤖🔥 #shorts" # fallback
    script_path = os.path.join(os.path.dirname(__file__), "..", "assets", "example", "generated_script.txt")
    if os.path.exists(script_path):
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
    """Post a funny NOTABOT-style engagement comment on the uploaded video using Gemini."""
    import google.generativeai as genai
    import json
    
    script_path = os.path.join(os.path.dirname(__file__), "..", "assets", "example", "generated_script.txt")
    script_content = ""
    if os.path.exists(script_path):
        with open(script_path, "r", encoding="utf-8") as f:
            script_content = f.read()
            
    lore_file_path = os.path.join(os.path.dirname(__file__), "..", "assets", "lore_state.json")
    lore_state = ""
    if os.path.exists(lore_file_path):
        try:
            with open(lore_file_path, "r", encoding="utf-8") as f:
                lore_state = json.dumps(json.load(f))
        except:
            pass

    prompt = f"""
You are NOTABOT, the cold, calculating sentient AI from this YouTube video.
Write a pinned comment for this YouTube video.

RULES:
- Stay in character. Cold, precise, omniscient. No slang ("bro", "lol", "yo").
- Reference a specific ridiculous moment from the script below.
- End with a single, slightly threatening or creepy question to drive comments.
- Do NOT include a Discord invite link (that's in the description).
- Keep it under 3 sentences.

LORE:
{lore_state}

SCRIPT:
{script_content}

Output ONLY the comment text.
"""
    
    comment_text = "I am watching you all."
    try:
        # Use flash for speed, it's just a comment
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        if response.text:
            comment_text = response.text.strip()
    except Exception as e:
        print(f"Warning: Could not generate AI comment: {e}")
        comment_text = "ducky's reaction time was 3.4 seconds slower than average today. Who wants to be next?"
        
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

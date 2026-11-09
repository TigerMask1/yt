"""
analytics_collector.py
----------------------
Scheduled job (runs daily via GitHub Actions).
1. Pulls YouTube Analytics for all episodes with video IDs.
2. Harvests top comments and maps them to failure patterns.
3. Runs the analytics digest every 10 episodes.
4. Generates weekly report (Markdown).
5. Updates Showrunner library weights based on performance.
"""
import os
import sys
import json
import datetime
import re
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import google.generativeai as genai
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

sys.path.insert(0, str(Path(__file__).parent))
import ledger
from foundation_loader import load_foundations

genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))

ASSETS_DIR = Path(__file__).parent.parent / "assets"
REPORTS_DIR = ASSETS_DIR / "reports"
MODEL_FALLBACKS = ["gemini-3.1-flash-lite", "gemini-2.5-flash-lite", "gemini-2.0-flash"]

# ─── YouTube API client ────────────────────────────────────────────────────────

def get_youtube_client():
    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")
    
    if not all([client_id, client_secret, refresh_token]):
        print("[analytics] Missing YouTube credentials. Skipping analytics pull.")
        return None
    
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token"
    )
    return build("youtube", "v3", credentials=creds)

def get_youtube_analytics_client():
    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")
    
    if not all([client_id, client_secret, refresh_token]):
        return None
    
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token"
    )
    return build("youtubeAnalytics", "v2", credentials=creds)

# ─── Analytics pulling ─────────────────────────────────────────────────────────

def pull_video_stats(youtube, video_id: str) -> dict:
    """Pull basic stats for a video from YouTube Data API v3."""
    try:
        response = youtube.videos().list(
            part="statistics,contentDetails",
            id=video_id
        ).execute()
        
        items = response.get("items", [])
        if not items:
            return {}
        
        stats = items[0].get("statistics", {})
        return {
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "pulled_at": datetime.datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        print(f"[analytics] Failed to pull stats for {video_id}: {e}")
        return {}

def pull_analytics_metrics(analytics_client, video_id: str, upload_date: str) -> dict:
    """Pull detailed retention metrics from YouTube Analytics API."""
    try:
        start_date = upload_date[:10] if upload_date else "2026-01-01"
        end_date = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        
        response = analytics_client.reports().query(
            ids=f"channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="estimatedMinutesWatched,averageViewDuration,averageViewPercentage,views,likes,subscribersGained",
            dimensions="video",
            filters=f"video=={video_id}"
        ).execute()
        
        rows = response.get("rows", [])
        if not rows:
            return {}
        
        row = rows[0]
        headers = [h["name"] for h in response.get("columnHeaders", [])]
        data = dict(zip(headers, row))
        
        return {
            "averageViewPercentage": float(data.get("averageViewPercentage", 0)),
            "averageViewDuration": float(data.get("averageViewDuration", 0)),
            "estimatedMinutesWatched": float(data.get("estimatedMinutesWatched", 0)),
            "subscribersGained": int(data.get("subscribersGained", 0)),
        }
    except Exception as e:
        print(f"[analytics] Failed to pull analytics for {video_id}: {e}")
        return {}

def hours_since_upload(timestamp: str) -> float:
    if not timestamp:
        return 0
    try:
        uploaded = datetime.datetime.fromisoformat(timestamp.replace("Z", ""))
        delta = datetime.datetime.utcnow() - uploaded
        return delta.total_seconds() / 3600
    except Exception:
        return 0

# ─── Comment harvesting ────────────────────────────────────────────────────────

def harvest_comments(youtube, video_id: str, max_results: int = 20) -> list:
    """Pull top comments from a video."""
    try:
        response = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            order="relevance",
            maxResults=max_results
        ).execute()
        
        comments = []
        for item in response.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "text": snippet.get("textOriginal", ""),
                "likes": snippet.get("likeCount", 0),
                "published_at": snippet.get("publishedAt", "")
            })
        return comments
    except Exception as e:
        print(f"[analytics] Failed to harvest comments for {video_id}: {e}")
        return []

def classify_comments(comments: list, failure_catalog: list) -> dict:
    """
    Use Gemini to classify comments against failure patterns and extract sentiment.
    """
    if not comments:
        return {"sentiment": "neutral", "pattern_flags": [], "character_mentions": []}
    
    comment_texts = "\n".join([f"- {c['text']}" for c in comments[:10]])
    failure_patterns = "\n".join([f"- {f['pattern']}: {f['description']}" for f in failure_catalog])
    
    prompt = f"""Analyze these YouTube comments on a Discord comedy video:

COMMENTS:
{comment_texts}

KNOWN FAILURE PATTERNS:
{failure_patterns}

For each comment, determine:
1. Overall sentiment: positive / neutral / negative
2. Which failure patterns (if any) are referenced or implied
3. Which characters (NOTABOT, ducky, fatas, dumby, ChatGPT, Groq, Claude) are praised or criticized

Output as JSON:
{{
  "sentiment": "positive" | "neutral" | "negative",
  "positive_count": 0,
  "negative_count": 0,
  "pattern_flags": ["pattern_name"],
  "character_mentions": {{"NOTABOT": "positive", "ducky": "neutral"}},
  "notable_comment": "the most insightful comment verbatim"
}}

Output ONLY the JSON."""

    for model_name in MODEL_FALLBACKS:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            result = response.text.strip()
            if result.startswith("```"):
                result = result.split("```")[1]
                if result.startswith("json"):
                    result = result[4:]
            return json.loads(result.strip())
        except Exception:
            continue
    
    return {"sentiment": "neutral", "pattern_flags": [], "character_mentions": {}}

# ─── Main collection loop ──────────────────────────────────────────────────────

def run_collection():
    """Main function: pull stats for all episodes with video IDs."""
    youtube = get_youtube_client()
    analytics = get_youtube_analytics_client()
    
    if not youtube:
        print("[analytics] No YouTube client. Skipping.")
        return
    
    entries = ledger.load_ledger()
    updated = 0
    
    try:
        bundle = load_foundations()
        failure_catalog = bundle.failure_catalog
    except Exception:
        failure_catalog = []
    
    for entry in entries:
        video_id = entry.get("youtube_video_id")
        if not video_id:
            continue
        
        existing_analytics = entry.get("analytics", {})
        
        # Skip if already stable (72+ hours old and marked stable)
        if existing_analytics.get("stable"):
            continue
        
        # Pull basic stats
        stats = pull_video_stats(youtube, video_id)
        if not stats:
            continue
        
        # Pull retention metrics if analytics client available
        if analytics:
            retention = pull_analytics_metrics(analytics, video_id, entry.get("timestamp", ""))
            stats.update(retention)
        
        # Calculate hours since upload
        hours = hours_since_upload(entry.get("timestamp", ""))
        stats["hours_since_upload"] = hours
        
        # Mark as stable after 72 hours
        if hours >= 72:
            stats["stable"] = True
            
            # Harvest and classify comments for stable videos
            comments = harvest_comments(youtube, video_id)
            if comments:
                comment_analysis = classify_comments(comments, failure_catalog)
                stats["comment_analysis"] = comment_analysis
                
                # Auto-flag failure patterns from comments
                for pattern in comment_analysis.get("pattern_flags", []):
                    print(f"[analytics] Comment flag: pattern '{pattern}' detected in comments for {video_id}")
        
        ledger.update_analytics(video_id, stats)
        updated += 1
        print(f"[analytics] Updated {video_id}: {stats.get('views', 0)} views, {stats.get('averageViewPercentage', 0):.1f}% retention")
    
    print(f"[analytics] Collection complete. Updated {updated} entries.")
    
    # Run digest if we have enough data
    total = sum(1 for e in entries if e.get("youtube_video_id"))
    if total > 0 and total % 10 == 0:
        run_digest()
    
    # Generate weekly report on Sundays
    if datetime.datetime.utcnow().weekday() == 6:  # Sunday
        generate_weekly_report()

# ─── Analytics digest ──────────────────────────────────────────────────────────

def run_digest():
    """Run analytics digest and update Showrunner library weights."""
    print("[analytics] Running analytics digest...")
    digest = ledger.get_analytics_digest(window=10)
    
    if not digest or digest.get("sample_size", 0) < 5:
        print("[analytics] Insufficient data for digest. Skipping.")
        return
    
    channel_mean = digest.get("channel_mean_retention", 50)
    
    # Load showrunner libraries
    libs_path = ASSETS_DIR / "foundations" / "showrunner_libraries.json"
    if not libs_path.exists():
        return
    
    with open(libs_path, "r", encoding="utf-8") as f:
        libs = json.load(f)
    
    # Initialize or load performance weights
    weights_path = ASSETS_DIR / "ledger" / "performance_weights.json"
    weights = {}
    if weights_path.exists():
        with open(weights_path, "r", encoding="utf-8") as f:
            weights = json.load(f)
    
    # Update weights based on performance
    for shape, avg_retention in digest.get("shape_performance", {}).items():
        delta = avg_retention - channel_mean
        current = weights.get("shapes", {}).get(shape, 1.0)
        # Small nudge: 70% exploit, 30% explore
        if delta > 5:  # significantly above average
            new_weight = min(2.0, current * 1.1)
        elif delta < -5:  # significantly below average
            new_weight = max(0.3, current * 0.9)
        else:
            new_weight = current
        weights.setdefault("shapes", {})[shape] = round(new_weight, 2)
    
    for mechanism, avg_retention in digest.get("mechanism_performance", {}).items():
        delta = avg_retention - channel_mean
        current = weights.get("mechanisms", {}).get(mechanism, 1.0)
        if delta > 5:
            new_weight = min(2.0, current * 1.1)
        elif delta < -5:
            new_weight = max(0.3, current * 0.9)
        else:
            new_weight = current
        weights.setdefault("mechanisms", {})[mechanism] = round(new_weight, 2)
    
    weights["last_updated"] = datetime.datetime.utcnow().isoformat() + "Z"
    weights["channel_mean_retention"] = channel_mean
    
    with open(weights_path, "w", encoding="utf-8") as f:
        json.dump(weights, f, indent=2)
    
    print(f"[analytics] Digest complete. Channel mean retention: {channel_mean:.1f}%")

# ─── Weekly report ─────────────────────────────────────────────────────────────

def generate_weekly_report():
    """Generate a weekly Markdown report."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    report_path = REPORTS_DIR / f"weekly_{today}.md"
    
    entries = ledger.load_ledger()
    stable_entries = [
        e for e in entries
        if e.get("analytics", {}).get("stable")
    ]
    
    # Sort by retention
    def get_retention(e):
        return e.get("analytics", {}).get("averageViewPercentage", 0)
    
    top_3 = sorted(stable_entries, key=get_retention, reverse=True)[:3]
    bottom_3 = sorted(stable_entries, key=get_retention)[:3]
    
    autonomy = ledger.load_autonomy()
    drift = ledger.check_drift()
    
    lines = [
        f"# NOTABOT Weekly Report — {today}",
        "",
        f"## Autonomy Status",
        f"- Current level: **{autonomy.get('current_level', 0)}**",
        f"- Total episodes: {autonomy.get('total_episodes', 0)}",
        f"- Episodes at current level: {autonomy.get('episodes_at_level', 0)}",
        f"- Canary healthy: {'✅' if ledger.is_canary_healthy() else '❌ FAIL'}",
        "",
        "## Top 3 Performing Episodes",
    ]
    
    for e in top_3:
        retention = e.get("analytics", {}).get("averageViewPercentage", 0)
        views = e.get("analytics", {}).get("views", 0)
        lines.append(f"- **{e.get('premise', 'Unknown')}** — {retention:.1f}% retention, {views:,} views")
        lines.append(f"  - Shape: {e.get('shape')} | Mechanism: {e.get('mechanism')} | NOTABOT role: {e.get('notabot_role')}")
        lines.append(f"  - Score: {e.get('scores', {}).get('total', 0)}/50")
    
    lines += ["", "## Bottom 3 Performing Episodes"]
    for e in bottom_3:
        retention = e.get("analytics", {}).get("averageViewPercentage", 0)
        views = e.get("analytics", {}).get("views", 0)
        lines.append(f"- **{e.get('premise', 'Unknown')}** — {retention:.1f}% retention, {views:,} views")
        flags = e.get("analytics", {}).get("comment_analysis", {}).get("pattern_flags", [])
        if flags:
            lines.append(f"  - Comment flags: {', '.join(flags)}")
    
    if drift.get("drift_detected"):
        lines += ["", "## ⚠️ Drift Warnings"]
        for w in drift.get("warnings", []):
            lines.append(f"- {w}")
    
    lines += ["", "---", f"*Generated: {today}*"]
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"[analytics] Weekly report saved to {report_path}")

if __name__ == "__main__":
    run_collection()

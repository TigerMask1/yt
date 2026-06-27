"""
fix_clips.py
------------
1. Merges all split .mp4 + .m4a pairs into proper mp4 files with audio
2. Deletes old aesthetic clips + all leftover split fragments
3. Verifies final clip list
"""
import os
import subprocess
import sys
import glob
import imageio_ffmpeg

CLIPS_DIR = r"c:\Users\LENOVO\Documents\disc\Text-2-Beluga\assets\clips"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FFPROBE = FFMPEG.replace("ffmpeg-win", "ffprobe-win").replace("ffmpeg.exe", "ffprobe.exe")
# fallback: use ffprobe from same folder
if not os.path.exists(FFPROBE):
    FFPROBE = os.path.join(os.path.dirname(FFMPEG), "ffprobe.exe")
if not os.path.exists(FFPROBE):
    # moviepy bundles ffmpeg but not ffprobe — use ffmpeg as ffprobe workaround
    FFPROBE = FFMPEG.replace("ffmpeg-win-x86_64", "ffprobe-win-x86_64")

print(f"Using ffmpeg: {FFMPEG}")

# ── 1. Delete old/wrong clips ────────────────────────────────────────────────
JUNK_PATTERNS = [
    "aesthetic_*.mp4",
]

print("=" * 60)
print("STEP 1: Deleting junk clips...")
for pattern in JUNK_PATTERNS:
    for f in glob.glob(os.path.join(CLIPS_DIR, pattern)):
        os.remove(f)
        print(f"  [DELETED] {os.path.basename(f)}")

# ── 2. Find all split pairs and merge them ───────────────────────────────────
print("\nSTEP 2: Merging split video+audio pairs...")

# Find all .mp4 files with format codes like "hacker_typing.f398.mp4"
split_videos = glob.glob(os.path.join(CLIPS_DIR, "*.f[0-9]*.mp4"))
split_audios = glob.glob(os.path.join(CLIPS_DIR, "*.f[0-9]*.m4a"))

# Build a map: base_name -> {video: path, audio: path}
pairs = {}
for v in split_videos:
    base = os.path.basename(v)
    # e.g. "hacker_typing.f398.mp4" -> "hacker_typing"
    name = base.rsplit('.f', 1)[0]
    pairs.setdefault(name, {})['video'] = v

for a in split_audios:
    base = os.path.basename(a)
    name = base.rsplit('.f', 1)[0]
    pairs.setdefault(name, {})['audio'] = a

for name, files in pairs.items():
    out_path = os.path.join(CLIPS_DIR, f"{name}.mp4")
    
    video = files.get('video')
    audio = files.get('audio')
    
    if not video:
        print(f"  [SKIP] {name} — no video stream found")
        continue
    
    if os.path.exists(out_path):
        # Already merged — delete fragments
        if video: os.remove(video)
        if audio: os.remove(audio)
        print(f"  [EXISTS] {name}.mp4 already merged, fragments cleaned")
        continue
    
    if audio:
        # Merge video + audio
        cmd = [
            FFMPEG, '-y',
            '-i', video,
            '-i', audio,
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-shortest',
            out_path
        ]
        print(f"  [MERGING] {name}.mp4 (video + audio)...")
    else:
        # Only video — just rename
        cmd = [
            FFMPEG, '-y',
            '-i', video,
            '-c', 'copy',
            out_path
        ]
        print(f"  [CONVERTING] {name}.mp4 (video only, no audio found)...")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        # Delete fragments after successful merge
        if video and os.path.exists(video): os.remove(video)
        if audio and os.path.exists(audio): os.remove(audio)
        size_kb = os.path.getsize(out_path) // 1024
        print(f"  [OK] {name}.mp4 ({size_kb} KB)")
    else:
        print(f"  [ERROR] Failed to merge {name}: {result.stderr[-200:]}")

# ── 3. Clean leftover .m4a files (audio only, no matching video) ─────────────
print("\nSTEP 3: Cleaning up orphan audio files...")
for f in glob.glob(os.path.join(CLIPS_DIR, "*.m4a")):
    os.remove(f)
    print(f"  [DELETED] {os.path.basename(f)}")

# ── 4. Also delete tiny broken files (< 20KB = probably corrupt) ─────────────
print("\nSTEP 4: Removing broken/tiny files...")
for f in glob.glob(os.path.join(CLIPS_DIR, "*.mp4")):
    size = os.path.getsize(f)
    if size < 20 * 1024:  # Less than 20KB = definitely broken
        os.remove(f)
        print(f"  [DELETED] {os.path.basename(f)} ({size} bytes — too small)")

# ── 5. Final inventory ───────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("FINAL CLIPS IN FOLDER:")
print("=" * 60)

clips = sorted(glob.glob(os.path.join(CLIPS_DIR, "*.mp4")))
for c in clips:
    size_kb = os.path.getsize(c) // 1024
    
    # Check if clip has audio
    probe = subprocess.run(
        [FFMPEG, '-v', 'quiet', '-i', c, '-hide_banner'],
        capture_output=True, text=True
    )
    has_audio = 'Audio' in probe.stderr
    audio_flag = "🔊" if has_audio else "🔇 NO AUDIO"
    
    print(f"  {audio_flag}  {os.path.basename(c)}  ({size_kb} KB)")

print(f"\nTotal: {len(clips)} clips")

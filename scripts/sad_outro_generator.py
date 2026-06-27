"""
sad_outro_generator.py
----------------------
Generates a 3-second vertical (1080x1920) MP4 outro clip with:
  - Pure black background
  - Centered self-deprecating white text with fade in/out
  - Subtle background music from assets/sounds/mp3/

Run once to produce:
    ../assets/outros/sad_outro.mp4

Usage:
    python sad_outro_generator.py
"""

# ---------------------------------------------------------------------------
# Pillow 10+ compatibility
# ---------------------------------------------------------------------------
from PIL import Image as _PIL_Image
if not hasattr(_PIL_Image, 'ANTIALIAS'):
    _PIL_Image.ANTIALIAS = _PIL_Image.LANCZOS

import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoClip, AudioFileClip, CompositeAudioClip

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WIDTH, HEIGHT = 1080, 1920
DISCORD_INVITE = "discord.gg/U7QD2yGFbR"

DURATION = 6.0          # 6s total: 3s sad msg + 3s discord CTA

FADE_IN_END    = 0.6
FADE_OUT_START = 5.2

# ── Sad messages (shown first 3 seconds) ──────────────────────────────────────
MESSAGES = [
    "everyone says discord content\ndoesn't work in 2026...\nhelp me",
    "nobody watches these\nbut i keep making them...\nwhy",
    "pls just one sub...\ni'm begging u",
    "they said bots can't be funny.\nthey were right.\nsubscribe anyway",
    "i make these every day\nand still can't afford\na better pc 😭",
]

# ── Discord CTA lines (shown second 3 seconds) in NOTABOT voice ───────────────
DISCORD_CTAS = [
    f"also... add NOTABOT to ur server\nand ruin someone's day\n{DISCORD_INVITE}",
    f"NOTABOT is real. it's live.\nadd it to ur server:\n{DISCORD_INVITE}",
    f"want the bot that made this?\njoin the server:\n{DISCORD_INVITE}\n(ducky will cry. worth it.)",
    f"tired of boring servers?\nlet NOTABOT fix that:\n{DISCORD_INVITE}",
    f"if u liked this chaos\nthe server has MORE:\n{DISCORD_INVITE}",
]

FONT_SIZE = 52
FPS       = 24

# Background music candidates (from assets/sounds/mp3/) — pick softest/most emotional
MUSIC_CANDIDATES = [
    'softmessage.mp3',   # soft, ambient — perfect for sad outro
    'hehascome.mp3',     # dramatic/ominous — works for dark comedy
    'confusion.mp3',     # confused helpless vibe
]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(SCRIPT_DIR, '..', 'assets')
FONTS_DIR  = os.path.join(ASSETS_DIR, 'fonts')
SOUNDS_DIR = os.path.join(ASSETS_DIR, 'sounds', 'mp3')


# ---------------------------------------------------------------------------
# Font helper
# ---------------------------------------------------------------------------
def _find_font(size: int):
    preferred = [
        os.path.join(FONTS_DIR, 'whitney', 'medium.ttf'),
        os.path.join(FONTS_DIR, 'whitney', 'semibold.ttf'),
        os.path.join(FONTS_DIR, 'whitney', 'bold.ttf'),
    ]
    for p in preferred:
        if os.path.isfile(p):
            return ImageFont.truetype(p, size)
    if os.path.isdir(FONTS_DIR):
        for root, _, files in os.walk(FONTS_DIR):
            for fname in files:
                if fname.lower().endswith('.ttf'):
                    return ImageFont.truetype(os.path.join(root, fname), size)
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Word-wrap helper
# ---------------------------------------------------------------------------
def _wrap(text, font, max_width):
    dummy = Image.new('RGB', (1, 1))
    draw  = ImageDraw.Draw(dummy)
    words, lines, current = text.split(), [], ''
    for word in words:
        trial = (current + ' ' + word).strip()
        w = draw.textbbox((0, 0), trial, font=font)[2]
        if w <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Frame factory
# ---------------------------------------------------------------------------
def _make_frame_factory(message: str, cta_text: str):
    """Two-card outro: sad message for first half, Discord CTA for second half."""
    font       = _find_font(FONT_SIZE)
    font_small = _find_font(30)
    font_url   = _find_font(36)

    HALF = DURATION / 2.0   # 3.0s each card
    XFADE = 0.4             # crossfade duration between cards

    # ── Pre-compute card 1: sad message ───────────────────────────────────────
    wrapped1 = _wrap(message, font, 900)
    probe    = Image.new('RGBA', (WIDTH, HEIGHT), (0,0,0,0))
    draw     = ImageDraw.Draw(probe)
    bbox1    = draw.multiline_textbbox((0, 0), wrapped1, font=font, align='center')
    tx1 = (WIDTH  - (bbox1[2]-bbox1[0])) // 2
    ty1 = (HEIGHT - (bbox1[3]-bbox1[1])) // 2
    sub_text = "-- NOTABOT  |  one sub won't hurt... right?"
    sub_bbox = draw.textbbox((0,0), sub_text, font=font_small)
    sx1 = (WIDTH - (sub_bbox[2]-sub_bbox[0])) // 2
    sy1 = ty1 + (bbox1[3]-bbox1[1]) + 50

    # ── Pre-compute card 2: Discord CTA ───────────────────────────────────────
    # Split cta_text: last line is the URL (render in different color)
    cta_lines = cta_text.strip().split('\n')
    url_line  = cta_lines[-1] if len(cta_lines) > 1 else ''
    body_lines = '\n'.join(cta_lines[:-1]) if len(cta_lines) > 1 else cta_text
    wrapped2  = _wrap(body_lines, font, 900)
    bbox2     = draw.multiline_textbbox((0, 0), wrapped2, font=font, align='center')
    tx2 = (WIDTH  - (bbox2[2]-bbox2[0])) // 2
    ty2 = (HEIGHT - (bbox2[3]-bbox2[1])) // 2 - 60
    url_bbox  = draw.textbbox((0,0), url_line, font=font_url)
    ux2 = (WIDTH  - (url_bbox[2]-url_bbox[0])) // 2
    uy2 = ty2 + (bbox2[3]-bbox2[1]) + 30

    def _render_card1(alpha: float) -> Image.Image:
        a      = int(max(0,min(1,alpha)) * 255)
        bg     = Image.new('RGBA', (WIDTH, HEIGHT), (0,0,0,255))
        layer  = Image.new('RGBA', (WIDTH, HEIGHT), (0,0,0,0))
        d      = ImageDraw.Draw(layer)
        d.multiline_text((tx1, ty1), wrapped1, font=font,
                         fill=(255,255,255,a), align='center')
        d.text((sx1, sy1), sub_text, font=font_small, fill=(140,140,140,int(a*0.6)))
        return Image.alpha_composite(bg, layer)

    def _render_card2(alpha: float) -> Image.Image:
        a     = int(max(0,min(1,alpha)) * 255)
        bg    = Image.new('RGBA', (WIDTH, HEIGHT), (0,0,0,255))
        layer = Image.new('RGBA', (WIDTH, HEIGHT), (0,0,0,0))
        d     = ImageDraw.Draw(layer)
        # Body text in white
        d.multiline_text((tx2, ty2), wrapped2, font=font,
                         fill=(255,255,255,a), align='center')
        # URL line in Discord blurple
        d.text((ux2, uy2), url_line, font=font_url, fill=(88,101,242,a))
        # Faint "🤖 NOTABOT" watermark
        d.text((40, HEIGHT-80), "🤖 NOTABOT", font=font_small, fill=(60,60,60,a))
        return Image.alpha_composite(bg, layer)

    def make_frame(t: float) -> np.ndarray:
        if t < HALF - XFADE:
            # Pure card 1
            if t <= FADE_IN_END:
                a = t / FADE_IN_END
            else:
                a = 1.0
            img = _render_card1(a)
        elif t < HALF + XFADE:
            # Crossfade
            prog = (t - (HALF - XFADE)) / (2 * XFADE)  # 0→1
            img1 = _render_card1(1.0 - prog)
            img2 = _render_card2(prog)
            img  = Image.alpha_composite(img1, img2)
        else:
            # Pure card 2
            if t >= FADE_OUT_START:
                a = (DURATION - t) / (DURATION - FADE_OUT_START)
            else:
                a = 1.0
            img = _render_card2(a)
        return np.array(img.convert('RGB'))

    return make_frame


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    message  = random.choice(MESSAGES)
    cta_text = random.choice(DISCORD_CTAS)
    print(f'[sad_outro] Sad msg: "{message.splitlines()[0]}..."')
    print(f'[sad_outro] CTA: "{cta_text.splitlines()[0]}..."')

    make_frame = _make_frame_factory(message, cta_text)
    clip = VideoClip(make_frame, duration=DURATION)

    # ── Background music ──────────────────────────────────────────────────────
    music_clip = None
    for candidate in MUSIC_CANDIDATES:
        path = os.path.join(SOUNDS_DIR, candidate)
        if os.path.isfile(path):
            try:
                raw = AudioFileClip(path)
                # Loop or trim to match video duration, then fade out
                if raw.duration < DURATION:
                    # Just use what we have, no looping needed for 4s
                    music_clip = raw.volumex(0.25).audio_fadeout(0.8)
                else:
                    music_clip = raw.subclip(0, DURATION).volumex(0.25).audio_fadeout(0.8)
                print(f'[sad_outro] Music: {candidate}')
                break
            except Exception as e:
                print(f'[sad_outro] Could not load {candidate}: {e}')

    if music_clip:
        clip = clip.set_audio(music_clip)

    # ── Output ────────────────────────────────────────────────────────────────
    outro_dir   = os.path.join(ASSETS_DIR, 'outros')
    os.makedirs(outro_dir, exist_ok=True)
    output_path = os.path.join(outro_dir, 'sad_outro.mp4')

    clip.write_videofile(
        output_path,
        fps=FPS,
        codec='libx264',
        audio_codec='aac',
        logger='bar',
    )
    print('sad_outro.mp4 generated successfully!')


if __name__ == '__main__':
    main()

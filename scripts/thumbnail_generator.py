"""
thumbnail_generator.py
-----------------------
Generates a click-bait YouTube thumbnail for NOTABOT Discord channel.

Design:
  - Pure black background
  - Left side: bold click-bait title text (yellow + white, big)
  - Right side: rendered fake Discord chat UI
  - The most important/spicy message in the chat is BLURRED (creates curiosity)
  - Red drama badge top-left

Usage:
    python thumbnail_generator.py --title "My Bot HATES Me 😭"
    python thumbnail_generator.py       # auto-reads # TITLE: from generated_script.txt
    python thumbnail_generator.py --variants-only
"""

from PIL import Image as _PIL_Image
if not hasattr(_PIL_Image, 'ANTIALIAS'):
    _PIL_Image.ANTIALIAS = _PIL_Image.LANCZOS

import os
import sys
import argparse
import shutil
import random
import math
from datetime import datetime

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR   = os.path.join(SCRIPT_DIR, '..', 'assets')
FONT_DIR     = os.path.join(ASSETS_DIR, 'fonts', 'whitney')
NOTABOT_PATH = os.path.join(ASSETS_DIR, 'profile_pictures', 'perm', 'notabot.png')
THUMB_DIR    = os.path.join(ASSETS_DIR, 'thumbnails')
VARIANTS_DIR = os.path.join(ASSETS_DIR, 'notabot_variants')
SCRIPT_PATH      = os.path.join(ASSETS_DIR, 'example', 'generated_script.txt')
LONG_SCRIPT_PATH = os.path.join(ASSETS_DIR, 'example', 'generated_long_script.txt')
THUMB_CHAT_PATH  = os.path.join(ASSETS_DIR, 'thumbnails', 'thumb_chat_frame.png')

THUMB_W, THUMB_H = 1280, 720

# Discord colors
DISCORD_BG        = (49,  51,  56)
DISCORD_BG_LIGHT  = (57,  60,  67)
DISCORD_TEXT      = (220, 221, 222)
DISCORD_NAME_BOT  = (235, 157, 70)   # orange — for NOTABOT
DISCORD_NAME_USER = (88,  101, 242)  # blurple — for others
DISCORD_TIMESTAMP = (148, 155, 164)

# Fake chat lines: (username, is_bot, message_text, blur_this)
# blur_this=True means this line gets a heavy Gaussian blur (the reveal)
CHAT_SCENARIOS = [
    [
        ("ducky",   False, "bro did u just do what i think u did",  False),
        ("NOTABOT", True,  "yes and i'd do it again",               False),
        ("ducky",   False, "wait... HOW did u even",                False),
        ("NOTABOT", True,  "████████████████████████████",          True),   # BLURRED
        ("fatas",   False, "💀💀💀",                                False),
        ("dumby",   False, "im crying rn bro",                      False),
    ],
    [
        ("ducky",   False, "explain yourself RIGHT NOW",             False),
        ("NOTABOT", True,  "ok so basically",                        False),
        ("NOTABOT", True,  "████████████████████████████████████",   True),   # BLURRED
        ("ducky",   False, "I CREATED YOU HOW",                      False),
        ("fatas",   False, "this is why i dont leave my room",       False),
    ],
    [
        ("NOTABOT", True,  "i have a confession to make",            False),
        ("ducky",   False, "oh no",                                  False),
        ("NOTABOT", True,  "████████████████████████████████",       True),   # BLURRED
        ("ducky",   False, "bro u need to be deleted",               False),
        ("dumby",   False, "WAIT HE ACTUALLY DID THAT",              False),
        ("fatas",   False, "passing away rn",                        False),
    ],
    [
        ("ducky",   False, "why are there charges on my card",       False),
        ("NOTABOT", True,  "what charges",                           False),
        ("ducky",   False, "NOTABOT.",                               False),
        ("NOTABOT", True,  "██████████████████████████████████",     True),   # BLURRED
        ("ducky",   False, "im literally shaking",                   False),
        ("fatas",   False, "💀 rip ur savings",                      False),
    ],
]

TEASERS = [
    "he actually said WHAT??",
    "bro said THIS in the chat 💀",
    "i can't show u the full msg...",
    "this message ended the server",
    "they deleted it but we saw it",
    "blurred for ur protection 😭",
]

BADGES = [
    "LEAKED",
    "READ THE BLUR",
    "I CANT SHOW THIS",
    "BOT GONE ROGUE",
    "HE ACTUALLY SAID IT",
]


# ── Fonts ─────────────────────────────────────────────────────────────────────
def _font(size, weight='bold'):
    names = {'bold': 'bold.ttf', 'semibold': 'semibold.ttf', 'medium': 'medium.ttf'}
    path = os.path.join(FONT_DIR, names.get(weight, 'bold.ttf'))
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


# ── Read title from script ────────────────────────────────────────────────────
def _read_title(is_long=False):
    path = LONG_SCRIPT_PATH if is_long else SCRIPT_PATH
    if not os.path.isfile(path):
        path = SCRIPT_PATH  # fallback
    if not os.path.isfile(path):
        return "He said WHAT in the server 💀"
    with open(path, encoding='utf-8') as f:
        for line in f:
            if line.strip().startswith('# TITLE:'):
                raw = line.strip().split(':', 1)[1].strip()
                for tag in ['#shorts', '#discord']:
                    raw = raw.replace(tag, '').strip()
                return raw
    return "He said WHAT in the server 💀"


# ── Word wrap ─────────────────────────────────────────────────────────────────
def _wrap(text, font, max_w):
    dummy = Image.new('RGB', (1, 1))
    d     = ImageDraw.Draw(dummy)
    words, lines, cur = text.split(), [], ''
    for w in words:
        trial = (cur + ' ' + w).strip()
        if d.textbbox((0, 0), trial, font=font)[2] <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ── Stroke text ───────────────────────────────────────────────────────────────
def _stroke(draw, pos, text, font, fill, stroke=(0,0,0), sw=7):
    x, y = pos
    for dx in range(-sw, sw+1, 2):
        for dy in range(-sw, sw+1, 2):
            if dx or dy:
                draw.text((x+dx, y+dy), text, font=font, fill=stroke)
    draw.text(pos, text, font=font, fill=fill)


# ── Draw fake Discord avatar circle ──────────────────────────────────────────
def _draw_avatar(img, cx, cy, r, is_bot=False):
    """Draw a small circular avatar placeholder."""
    draw = ImageDraw.Draw(img)
    color = (235, 157, 70) if is_bot else (88, 101, 242)
    # Circle bg
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=color)
    # Letter initial
    font_av = _font(max(10, r), 'bold')
    letter  = 'N' if is_bot else 'D'
    bbox    = draw.textbbox((0,0), letter, font=font_av)
    lw = bbox[2]-bbox[0]
    lh = bbox[3]-bbox[1]
    draw.text((cx - lw//2, cy - lh//2 - 2), letter, font=font_av, fill=(255,255,255))

# ── Gemini-powered clickbait bubble ──────────────────────────────────────────
def _generate_clickbait_bubble(is_long=False):
    """
    1. Asks Gemini to write ONE viral clickbait Discord message + which words to blur.
    2. Renders it as a REAL Discord chat frame (identical to video frames).
    3. Measures pixel positions of blur_words using Whitney font metrics.
    4. Applies heavy pixelated blur to just those words on the rendered frame.
    Returns (PIL Image, message_text) or (None, None).
    """
    path = LONG_SCRIPT_PATH if is_long else SCRIPT_PATH
    if not os.path.isfile(path):
        path = SCRIPT_PATH
    if not os.path.isfile(path):
        return None, None

    with open(path, encoding='utf-8') as f:
        script_text = f.read()

    # ── Step 1: Ask Gemini for message + which words to blur ─────────────────
    clickbait_msg = None
    blur_words    = []

    try:
        import google.generativeai as genai
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise ValueError('GEMINI_API_KEY not set')

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')

        prompt = f"""You are creating content for a YouTube thumbnail for a Discord bot video.

Write ONE short Discord message (max 8 words, lowercase, casual, real Discord vibe) that is:
- Extremely clickbait and cliffhanger-worthy based on this script
- Makes viewers NEED to click to find out what happened
- Feels like a genuine shocked/dramatic reaction from a server member

Also pick 1-3 words from that message that should be BLURRED/CENSORED in the thumbnail.
These blurred words should be the most shocking or revealing part — the thing that makes people curious.

Script (first 1500 chars):
{script_text[:1500]}

Respond ONLY with valid JSON in this exact format, nothing else:
{{"message": "your message here", "blur_words": ["word1", "word2"]}}"""

        resp = model.generate_content(prompt)
        raw  = resp.text.strip().strip('```json').strip('```').strip()

        import json as _json
        parsed        = _json.loads(raw)
        clickbait_msg = parsed.get('message', '').strip().strip('"').strip("'")
        blur_words    = [w.lower().strip() for w in parsed.get('blur_words', [])]
        print(f'[thumbnail] Gemini msg: "{clickbait_msg}" | blur: {blur_words}')

    except Exception as e:
        print(f'[thumbnail] Gemini failed, using fallback: {e}')
        clickbait_msg = random.choice([
            "bro i cannot show u the rest of this",
            "wait they actually said WHAT in the server",
            "this message got the whole server deleted",
            "they banned him after THIS message",
        ])
        # Blur the most dramatic word
        words      = clickbait_msg.split()
        blur_words = [words[-2]] if len(words) >= 2 else [words[-1]]

    if not clickbait_msg:
        return None, None

    # ── Step 2: Render as a REAL Discord chat frame ───────────────────────────
    try:
        import sys, json, datetime
        if SCRIPT_DIR not in sys.path:
            sys.path.insert(0, SCRIPT_DIR)
        from generate_chat import generate_chat, MESSAGE_X, MESSAGE_Y_INIT

        with open(os.path.join(ASSETS_DIR, 'profile_pictures', 'characters.json'), encoding='utf8') as cf:
            chars = json.load(cf)

        # Pick first non-bot character
        sender = next((k for k in chars if k.upper() != 'NOTABOT'), list(chars.keys())[0])
        profpic    = os.path.join(ASSETS_DIR, 'profile_pictures', chars[sender]['profile_pic'])
        role_color = chars[sender]['role_color']
        color      = tuple(role_color) if isinstance(role_color, list) else role_color
        name_time  = [sender, '3:41']

        frame = generate_chat(
            messages=[clickbait_msg],
            name_time=name_time,
            profpic_file=profpic,
            color=color,
        )
        frame = frame.convert('RGBA')

    except Exception as e:
        print(f'[thumbnail] Could not render chat frame: {e}')
        return None, clickbait_msg

    # ── Step 3: Measure word positions using Whitney font metrics ─────────────
    # generate_chat renders message at x=MESSAGE_X, y=MESSAGE_Y_INIT
    # using message_font (whitney medium, size 50)
    try:
        from PIL import ImageFont as _IFont
        font_path   = os.path.join(ASSETS_DIR, 'fonts', 'whitney', 'medium.ttf')
        msg_font    = _IFont.truetype(font_path, 50)
        msg_x_start = MESSAGE_X   # 190
        msg_y_start = MESSAGE_Y_INIT  # 115

        draw_tmp = ImageDraw.Draw(Image.new('RGBA', (10, 10)))
        x_cursor = msg_x_start

        words_in_msg = clickbait_msg.split()
        for i, word in enumerate(words_in_msg):
            # measure this word + space
            word_with_space = word + (' ' if i < len(words_in_msg) - 1 else '')
            bbox = draw_tmp.textbbox((0, 0), word_with_space, font=msg_font)
            word_w = bbox[2] - bbox[0]
            word_h = bbox[3] - bbox[1]

            # Check if this word should be blurred (case-insensitive, strip punctuation)
            clean = word.lower().strip('?!.,')
            if any(clean == bw or clean in bw or bw in clean for bw in blur_words):
                # Blur region: x_cursor to x_cursor+word_w, at msg_y_start
                pad = 6
                bx0 = max(0, x_cursor - pad)
                by0 = max(0, msg_y_start - pad)
                bx1 = min(frame.width,  x_cursor + word_w + pad)
                by1 = min(frame.height, msg_y_start + word_h + pad * 2)

                region  = frame.crop((bx0, by0, bx1, by1))
                # Heavy Gaussian blur
                blurred = region.filter(ImageFilter.GaussianBlur(radius=14))
                # Pixelate: shrink then enlarge for blocky look
                rw, rh  = bx1 - bx0, by1 - by0
                tiny    = blurred.resize((max(1, rw // 6), max(1, rh // 6)), Image.LANCZOS)
                blocky  = tiny.resize((rw, rh), Image.NEAREST)
                frame.paste(blocky, (bx0, by0))

            x_cursor += word_w

    except Exception as e:
        print(f'[thumbnail] Word blur failed (non-fatal): {e}')
        # Frame is still usable without blur

    # ── Save and return ───────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(THUMB_CHAT_PATH), exist_ok=True)
    frame.save(THUMB_CHAT_PATH)
    print(f'[thumbnail] Clickbait frame saved -> {THUMB_CHAT_PATH}')
    return frame, clickbait_msg





def _render_discord_panel(chat_lines, panel_w, panel_h):
    """Returns a PIL Image of a fake Discord chat."""
    img  = Image.new('RGB', (panel_w, panel_h), DISCORD_BG)
    draw = ImageDraw.Draw(img)

    # Top bar: server name
    draw.rectangle([0, 0, panel_w, 42], fill=(32, 34, 37))
    font_top    = _font(18, 'semibold')
    font_name   = _font(16, 'semibold')
    font_msg    = _font(17, 'medium')
    font_ts     = _font(13, 'medium')

    draw.text((16, 12), "# general  |  NOTABOT Server", font=font_top, fill=(220, 221, 222))
    draw.line([0, 42, panel_w, 42], fill=(20, 20, 22), width=2)

    # Messages
    AVATAR_R  = 18
    PAD_LEFT  = 14
    MSG_LEFT  = PAD_LEFT + AVATAR_R*2 + 10
    y         = 58
    ROW_GAP   = 10

    blur_regions = []   # (x0,y0,x1,y1) regions to blur at the end

    for (username, is_bot, message, do_blur) in chat_lines:
        name_color = DISCORD_NAME_BOT if is_bot else DISCORD_NAME_USER

        # Avatar
        _draw_avatar(img, PAD_LEFT + AVATAR_R, y + AVATAR_R, AVATAR_R, is_bot)

        # Username
        nb = draw.textbbox((MSG_LEFT, y), username, font=font_name)
        draw.text((MSG_LEFT, y), username, font=font_name, fill=name_color)
        ts_x = nb[2] + 8
        draw.text((ts_x, y+3), "Today at 3:41 PM", font=font_ts, fill=DISCORD_TIMESTAMP)

        # Message text (word-wrap within panel)
        msg_y     = y + 22
        msg_lines = _wrap(message, font_msg, panel_w - MSG_LEFT - 10)
        msg_x0, msg_y0 = MSG_LEFT, msg_y
        for ml in msg_lines:
            draw.text((MSG_LEFT, msg_y), ml, font=font_msg, fill=DISCORD_TEXT)
            msg_y += 22

        msg_y1 = msg_y

        if do_blur:
            blur_regions.append((MSG_LEFT - 4, msg_y0 - 4, panel_w - 10, msg_y1 + 4))

        row_h = max(AVATAR_R*2 + 8, msg_y1 - y + 6)
        y    += row_h + ROW_GAP

        if y > panel_h - 30:
            break

    # Apply blur to the spicy regions
    for (bx0, by0, bx1, by1) in blur_regions:
        bx0 = max(0, bx0); by0 = max(0, by0)
        bx1 = min(panel_w, bx1); by1 = min(panel_h, by1)
        region = img.crop((bx0, by0, bx1, by1))
        blurred = region.filter(ImageFilter.GaussianBlur(radius=14))
        # Pixelate feel: shrink then enlarge
        tiny = blurred.resize((max(1,(bx1-bx0)//6), max(1,(by1-by0)//6)), Image.LANCZOS)
        blocky = tiny.resize((bx1-bx0, by1-by0), Image.NEAREST)
        img.paste(blocky, (bx0, by0))

    # Panel border
    draw.rectangle([0, 0, panel_w-1, panel_h-1], outline=(20, 20, 22), width=2)

    return img


# ── Drama badge ───────────────────────────────────────────────────────────────
def _draw_badge(draw, font_badge):
    badge = random.choice(BADGES)
    bx, by = 36, 28
    bbox   = draw.textbbox((bx, by), badge, font=font_badge)
    pad    = 14
    # Shadow
    draw.rounded_rectangle([bbox[0]-pad+3, bbox[1]-pad//2+3,
                             bbox[2]+pad+3, bbox[3]+pad//2+3],
                            radius=8, fill=(0,0,0))
    # Red pill
    draw.rounded_rectangle([bbox[0]-pad, bbox[1]-pad//2,
                             bbox[2]+pad, bbox[3]+pad//2],
                            radius=8, fill=(210, 20, 20))
    draw.rounded_rectangle([bbox[0]-pad-2, bbox[1]-pad//2-2,
                             bbox[2]+pad+2, bbox[3]+pad//2+2],
                            radius=10, outline=(255,255,255), width=2)
    draw.text((bx, by), badge, font=font_badge, fill=(255,255,255))


# ── Main generator ────────────────────────────────────────────────────────────
def generate_thumbnail(title_text=None, is_long=False):
    if not title_text:
        title_text = _read_title(is_long=is_long)

    os.makedirs(THUMB_DIR, exist_ok=True)

    # ── Pure black canvas ─────────────────────────────────────────────────────
    img  = Image.new('RGB', (THUMB_W, THUMB_H), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ── Fonts ─────────────────────────────────────────────────────────────────
    font_main  = _font(72,  'bold')
    font_sub   = _font(34,  'medium')
    font_badge = _font(26,  'bold')
    font_label = _font(24,  'medium')

    # ── Clickbait Discord bubble (big, tilted, word-blurred) ─────────────────
    bubble_img, _cb_msg = _generate_clickbait_bubble(is_long=is_long)

    if bubble_img is None:
        # Last-resort fallback: render one of the fake scenarios
        chat_lines = random.choice(CHAT_SCENARIOS)
        bubble_img = _render_discord_panel(chat_lines, 700, 280)

    # ── Scale bubble to be BIG — about 67% of thumb width ────────────────────
    BUBBLE_TARGET_W = 860
    bw, bh = bubble_img.size
    scale  = BUBBLE_TARGET_W / bw
    new_bh = int(bh * scale)
    bubble_img = bubble_img.convert('RGBA').resize((BUBBLE_TARGET_W, new_bh), Image.LANCZOS)

    # ── Rotate the bubble slightly ────────────────────────────────────────────
    # (Word blur was already applied inside _generate_clickbait_bubble)
    TILT_DEG = -6   # negative = tilts left (top goes left)
    rotated  = bubble_img.rotate(TILT_DEG, expand=True, resample=Image.BICUBIC)



    # ── Drop shadow for the tilted bubble ────────────────────────────────────
    rw, rh = rotated.size
    shadow_layer = Image.new('RGBA', (THUMB_W, THUMB_H), (0, 0, 0, 0))
    shadow_draw  = ImageDraw.Draw(shadow_layer)
    # Position: centered horizontally, anchored to bottom of thumbnail
    paste_x = (THUMB_W - rw) // 2
    paste_y = THUMB_H - rh - 10   # 10px from bottom

    # Draw a dark blurred rectangle as shadow
    for si in range(20, 0, -1):
        alpha = int(140 * (1 - si / 20) ** 1.5)
        shadow_draw.rounded_rectangle(
            [paste_x - si + 4, paste_y - si + 4, paste_x + rw + si + 4, paste_y + rh + si + 4],
            radius=16, fill=(0, 0, 0, alpha)
        )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(10))
    img = Image.alpha_composite(img.convert('RGBA'), shadow_layer).convert('RGB')

    # ── Paste the tilted bubble onto the thumbnail ────────────────────────────
    img_rgba = img.convert('RGBA')
    img_rgba.paste(rotated, (paste_x, paste_y), rotated)
    img  = img_rgba.convert('RGB')
    draw = ImageDraw.Draw(img)



    # ── Title text (top portion — bubble owns the bottom) ────────────────────
    TEXT_MAX_W = 900   # wider now — full width available
    TEXT_LEFT  = 44

    lines   = _wrap(title_text, font_main, TEXT_MAX_W)
    LINE_H  = 100
    total_h = len(lines) * LINE_H
    # Keep title in top 50% of thumb so it sits above the bubble
    start_y = max(30, (int(THUMB_H * 0.45) - total_h) // 2)

    # Pick random words in last line to blur for mystery
    blur_word_set = set()
    if lines:
        last_words = lines[-1].split()
        eligible   = [i for i, w in enumerate(last_words)
                      if len(w) > 3 and not any(c in w for c in ['😭','💀','😱','🔥','💣'])]
        if eligible:
            blur_word_set = set(random.sample(eligible, min(2, len(eligible))))

    for li, line in enumerate(lines):
        y        = start_y + li * LINE_H
        words    = line.split()
        is_last  = (li == len(lines) - 1)

        if not is_last:
            # Yellow for first 1-2 words, white for the rest
            xpos = TEXT_LEFT
            for wi, word in enumerate(words):
                color = (255, 230, 15) if wi < 2 else (255, 255, 255)
                _stroke(draw, (xpos, y), word, font_main, color, sw=10)
                xpos += draw.textbbox((0,0), word+' ', font=font_main)[2]
        else:
            # Last line: word by word, blur selected
            xpos = TEXT_LEFT
            for wi, word in enumerate(words):
                color = (255, 230, 15) if wi < 2 else (255, 255, 255)
                if wi in blur_word_set:
                    # Render on separate layer then blur + pixelate
                    layer = Image.new('RGBA', (THUMB_W, THUMB_H), (0,0,0,0))
                    ld    = ImageDraw.Draw(layer)
                    _stroke(ld, (xpos, y), word, font_main, color, sw=10)
                    bbox  = ld.textbbox((xpos, y), word, font=font_main)
                    pad   = 14
                    bx0   = max(0, bbox[0]-pad)
                    by0   = max(0, bbox[1]-pad)
                    bx1   = min(THUMB_W, bbox[2]+pad)
                    by1   = min(THUMB_H, bbox[3]+pad)
                    region  = layer.crop((bx0,by0,bx1,by1))
                    blurred = region.filter(ImageFilter.GaussianBlur(18))
                    tiny    = blurred.resize((max(1,(bx1-bx0)//5), max(1,(by1-by0)//5)), Image.LANCZOS)
                    blocky  = tiny.resize((bx1-bx0,by1-by0), Image.NEAREST)
                    layer.paste(blocky, (bx0, by0))
                    img  = Image.alpha_composite(img.convert('RGBA'), layer).convert('RGB')
                    draw = ImageDraw.Draw(img)
                else:
                    _stroke(draw, (xpos, y), word, font_main, color, sw=10)
                xpos += draw.textbbox((0,0), word+' ', font=font_main)[2]


    # ── Drama badge top-left ──────────────────────────────────────────────────
    _draw_badge(draw, font_badge)

    # ── Save ──────────────────────────────────────────────────────────────────
    today    = datetime.now().strftime('%Y%m%d')
    out_path = os.path.join(THUMB_DIR, f'thumb_{today}.png')
    img.save(out_path)
    print(f'[thumbnail] OK Saved -> {out_path}')
    return out_path


# ── Emotion-named NOTABOT variants ────────────────────────────────────────────
NOTABOT_VARIANTS = [
    ('notabot_shocked.png',  'SHOCKED  -- use when something wild just dropped'),
    ('notabot_crying.png',   'CRYING   -- use for "i cant believe this" moments'),
    ('notabot_angry.png',    'ANGRY    -- use for roast / clap-back thumbnails'),
    ('notabot_smug.png',     'SMUG     -- use when NOTABOT wins / flexes'),
    ('notabot_confused.png', 'CONFUSED -- use for "what is happening" thumbnails'),
]

def create_notabot_variants():
    os.makedirs(VARIANTS_DIR, exist_ok=True)
    if not os.path.isfile(NOTABOT_PATH):
        print(f'[variants] WARNING: notabot.png not found at {NOTABOT_PATH}')
        return
    readme = os.path.join(VARIANTS_DIR, 'README.txt')
    with open(readme, 'w') as f:
        f.write("NOTABOT Reaction Variants\n" + "="*40 + "\n\n")
        f.write("Replace each file with the appropriate reaction face image.\n\n")
        for fname, desc in NOTABOT_VARIANTS:
            f.write(f"{fname}\n  -> {desc}\n\n")
    for fname, desc in NOTABOT_VARIANTS:
        dest = os.path.join(VARIANTS_DIR, fname)
        shutil.copy2(NOTABOT_PATH, dest)
        print(f'[variants] {fname}  ->  {desc}')


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--title',         type=str, default=None)
    parser.add_argument('--variants-only', action='store_true')
    args = parser.parse_args()

    create_notabot_variants()
    if not args.variants_only:
        generate_thumbnail(title_text=args.title)

if __name__ == '__main__':
    main()

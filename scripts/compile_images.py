import os
from PIL import ImageFont, ImageDraw

# Pillow 10+ removed Image.ANTIALIAS — patch it back so moviepy's resize works.
from PIL import Image as _PIL_Image
if not hasattr(_PIL_Image, 'ANTIALIAS'):
    _PIL_Image.ANTIALIAS = _PIL_Image.LANCZOS

from moviepy.editor import ImageClip, VideoFileClip, AudioFileClip, CompositeAudioClip, CompositeVideoClip, concatenate_videoclips

def create_title_image(text, width=900):
    """Generates an image of the title text using Pillow to avoid ImageMagick dependency."""
    img_path = "../chat/title_hook.png"
    # Create a transparent image
    img = _PIL_Image.new('RGBA', (width, 300), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    font_path = "../assets/fonts/whitney/bold.ttf"
    if not os.path.exists(font_path):
        return None
        
    font = ImageFont.truetype(font_path, 65)
    
    # Simple text wrapping
    words = text.split()
    lines = []
    current_line = []
    for word in words:
        current_line.append(word)
        bbox = draw.textbbox((0,0), " ".join(current_line), font=font)
        if bbox[2] - bbox[0] > width:
            current_line.pop()
            lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
        
    y = 0
    for line in lines:
        bbox = draw.textbbox((0,0), line, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (width - text_w) / 2
        # Outline
        stroke = 4
        draw.text((x-stroke, y), line, font=font, fill='black')
        draw.text((x+stroke, y), line, font=font, fill='black')
        draw.text((x, y-stroke), line, font=font, fill='black')
        draw.text((x, y+stroke), line, font=font, fill='black')
        # Text
        draw.text((x, y), line, font=font, fill='white')
        y += text_h + 10
        
    img.save(img_path)
    return img_path

def gen_vid(filename, output_path="../vertical_short.mp4"):
    input_folder = '../chat/'
    
    # 1080x1920 is standard vertical shorts resolution
    VIDEO_W, VIDEO_H = 1080, 1920
    
    clips = []
    audio_clips = []
    current_time = 0.0
    image_idx = 1
    title_hook = ""
    
    with open(filename, encoding="utf8") as f:
        lines = f.read().splitlines()
        
    for line in lines:
        if line.startswith("# TITLE:"):
            title_hook = line.replace("# TITLE:", "").replace("#shorts", "").replace("#discord", "").strip()
            break
            
    # Removed 1.4x scale per user request, defaulting back to VIDEO_W
            
    name_up_next = True
    for line in lines:
        line = line.strip()
        if not line:
            name_up_next = True
            continue
            
        if line.startswith("# TITLE:") or line.startswith("# PREMISE:"):
            continue
            
        if line.startswith("# CLIP:"):
            # Strip quotes, backticks, and whitespace
            clip_name = line.split(":", 1)[1].strip().strip("'`\"").strip()
            clip_path = f"../assets/clips/{clip_name}.mp4"
            if os.path.exists(clip_path):
                vid_clip = VideoFileClip(clip_path)
                vid_duration = vid_clip.duration
                vid_clip = vid_clip.subclip(0, vid_duration).set_start(current_time)
                # Crop center to 9:16
                vid_w, vid_h = vid_clip.size
                if vid_w/vid_h > VIDEO_W/VIDEO_H:
                    new_w = int(vid_h * (VIDEO_W/VIDEO_H))
                    vid_clip = vid_clip.crop(x_center=vid_w/2, y_center=vid_h/2, width=new_w, height=vid_h)
                vid_clip = vid_clip.resize(height=VIDEO_H).set_position('center')
                
                if vid_clip.audio is not None:
                    audio_clips.append(vid_clip.audio.set_start(current_time))
                clips.append(vid_clip)
                current_time += vid_duration
            continue

        if line.startswith("# REACTION:"):
            parts = line.replace("# REACTION:", "").strip().split(" ", 1)
            if len(parts) == 2:
                character, meme_name = parts
                import glob
                meme_matches = glob.glob(f"../assets/meme_templates/{meme_name}*.jpg")
                if meme_matches:
                    meme_path = meme_matches[0]
                    import json as _json
                    char_db_path = "../assets/profile_pictures/characters.json"
                    pfp_path = None
                    pfp_x, pfp_y, pfp_size = None, None, 130
                    if os.path.exists(char_db_path):
                        with open(char_db_path, "r", encoding="utf-8") as f:
                            chars_db = _json.load(f)
                            if character in chars_db:
                                pfp_path = os.path.join("../assets/profile_pictures", chars_db[character]["profile_pic"])
                    
                    # Load placement config per meme if it exists
                    meme_cfg_path = "../assets/meme_templates/placements.json"
                    if os.path.exists(meme_cfg_path):
                        with open(meme_cfg_path, "r", encoding="utf-8") as f:
                            placements = _json.load(f)
                            meme_key = os.path.basename(meme_path)
                            if meme_key in placements:
                                cfg = placements[meme_key]
                                pfp_x = cfg.get("pfp_x")
                                pfp_y = cfg.get("pfp_y")
                                pfp_size = cfg.get("pfp_size", 130)

                    if pfp_path and os.path.exists(pfp_path):
                        from PIL import Image as PIL_Image
                        bg = PIL_Image.open(meme_path).convert("RGBA")
                        pfp = PIL_Image.open(pfp_path).convert("RGBA")
                        
                        # Resize PFP to configured size
                        pfp = pfp.resize((pfp_size, pfp_size), PIL_Image.LANCZOS)
                        
                        # White border
                        from PIL import ImageDraw as _IDraw
                        border = 6
                        bordered = PIL_Image.new('RGBA', (pfp_size + border*2, pfp_size + border*2), (255,255,255,255))
                        bordered.paste(pfp, (border, border), pfp)
                        pfp = bordered
                        
                        # Use configured coords or fallback to bottom-right corner
                        if pfp_x is None:
                            pfp_x = bg.width - pfp.width - 10
                        if pfp_y is None:
                            pfp_y = bg.height - pfp.height - 10
                        
                        bg.paste(pfp, (pfp_x, pfp_y), pfp)
                        
                        temp_path = f"../chat/temp_meme_{image_idx}.png"
                        bg.save(temp_path)
                        
                        # --- FIT meme fully inside video without cropping ---
                        clip = ImageClip(temp_path).set_start(current_time).set_duration(2.0)
                        mw, mh = clip.size
                        scale = min(VIDEO_W / mw, VIDEO_H / mh)
                        new_w = int(mw * scale)
                        new_h = int(mh * scale)
                        clip = clip.resize((new_w, new_h))
                        clip = clip.set_position('center')
                        clips.append(clip)
                        
                        snd_path = '../assets/sounds/mp3/vineboom.mp3'
                        if os.path.exists(snd_path):
                            audio_clips.append(AudioFileClip(snd_path).set_start(current_time))
                        current_time += 2.0
                        image_idx += 1
            continue
            
        if line.startswith("#"):
            continue
            
        if line.startswith("WELCOME"):
            parts = line.split('$^')
            duration_part = parts[1].split('#!')[0]
            duration = float(duration_part)
            
            img_path = f"{input_folder}{image_idx:03d}.png"
            if os.path.exists(img_path):
                clip = ImageClip(img_path).set_start(current_time).set_duration(duration)
                clip = clip.crop(x1=0, y1=0, x2=min(1200, clip.w), y2=clip.h)
                clip = clip.resize(width=VIDEO_W)
                
                # Reverted dynamic positioning back to center
                clip = clip.set_position(('center', 'center'))
                clips.append(clip)
            image_idx += 1
            
            if "#!" in line:
                tags = line.split('#!')[1:]
                for tag in tags:
                    tag = tag.strip()
                    snd_path = f"../assets/sounds/mp3/{tag}.mp3"
                    if os.path.exists(snd_path):
                        audio_clips.append(AudioFileClip(snd_path).set_start(current_time))
            current_time += duration
            continue
            
        if name_up_next:
            name_up_next = False
            continue
            
        parts = line.split('$^')
        if len(parts) < 2:
            continue
            
        duration_part = parts[1].split('#!')[0]
        duration = float(duration_part)
        tags = line.split('#!')[1:] if '#!' in line else []
        
        img_path = f"{input_folder}{image_idx:03d}.png"
        if os.path.exists(img_path):
            # Dynamic Cropping (Beluga style): Crop to the actual text content bounding box
            # so short messages scale up to be huge on screen.
            from PIL import Image as _PIL_chk, ImageChops
            try:
                with _PIL_chk.open(img_path) as _im:
                    # Convert to grayscale and find bounding box of anything not black (bg is 15,15,15 usually)
                    bg = _PIL_chk.new(_im.mode, _im.size, (15, 15, 15))
                    diff = ImageChops.difference(_im, bg)
                    diff = ImageChops.add(diff, diff, 2.0, -100)
                    bbox = diff.getbbox()
                    
                if bbox:
                    # Add some padding around the text
                    pad = 20
                    x1 = max(0, bbox[0] - pad)
                    y1 = max(0, bbox[1] - pad)
                    x2 = min(_im.width, bbox[2] + pad)
                    y2 = min(_im.height, bbox[3] + pad)
                    
                    clip = ImageClip(img_path).set_start(current_time).set_duration(duration)
                    clip = clip.crop(x1=x1, y1=y1, x2=x2, y2=y2)
                else:
                    clip = ImageClip(img_path).set_start(current_time).set_duration(duration)
                    clip = clip.crop(x1=0, y1=0, x2=min(1200, clip.w), y2=clip.h)
            except Exception as e:
                print(f"Crop error on {img_path}: {e}")
                clip = ImageClip(img_path).set_start(current_time).set_duration(duration)
                clip = clip.crop(x1=0, y1=0, x2=min(1200, clip.w), y2=clip.h)
                
            clip = clip.resize(width=VIDEO_W)
            clip = clip.set_position(('center', 'center'))
            clips.append(clip)
            
            # Fire sound effects from #! tags (ignore animation tags)
            ANIM_TAGS = {"zoom_sudden", "zoom_gradual", "zoom_continuous", "tilt", "shake_subtle"}
            for tag in tags:
                tag = tag.strip()
                if tag and tag not in ANIM_TAGS:
                    snd_path = f"../assets/sounds/mp3/{tag}.mp3"
                    if os.path.exists(snd_path):
                        audio_clips.append(AudioFileClip(snd_path).set_start(current_time))
            
            current_time += duration
        else:
            current_time += duration
            
        image_idx += 1

    # Add persistent Title Hook at the top
    if title_hook:
        title_img_path = create_title_image(title_hook)
        if title_img_path and os.path.exists(title_img_path):
            title_clip = ImageClip(title_img_path).set_start(0).set_duration(current_time)
            title_clip = title_clip.set_position(('center', 150))
            clips.append(title_clip)

    if not clips:
        print("Error: No valid clips generated.")
        return

    final_video = CompositeVideoClip(clips, size=(VIDEO_W, VIDEO_H), bg_color=(15, 15, 15))
    
    if audio_clips:
        final_audio = CompositeAudioClip(audio_clips)
        final_audio = final_audio.set_duration(current_time)
        final_video = final_video.set_audio(final_audio)

    outro_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'outros', 'sad_outro.mp4')
    if os.path.exists(outro_path):
        try:
            outro_clip = VideoFileClip(outro_path).resize((VIDEO_W, VIDEO_H))
            final_video = concatenate_videoclips([final_video, outro_clip], method='compose')
            print('[compile] OK Sad outro appended.')
        except Exception as e:
            print(f'[compile] WARNING Could not append outro: {e}')

    final_video.write_videofile(output_path, fps=30, codec="libx264", audio_codec="aac")

if __name__ == "__main__":
    gen_vid("../assets/example/generated_script.txt")
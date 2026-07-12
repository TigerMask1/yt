import os
import math
from PIL import ImageFont, ImageDraw

# Pillow 10+ removed Image.ANTIALIAS — patch it back so moviepy's resize works.
from PIL import Image as _PIL_Image
if not hasattr(_PIL_Image, 'ANTIALIAS'):
    _PIL_Image.ANTIALIAS = _PIL_Image.LANCZOS

from moviepy.editor import ImageClip, VideoFileClip, AudioFileClip, CompositeAudioClip, CompositeVideoClip, concatenate_videoclips

def ease_in_out_sine(t, b, c, d):
    return -c / 2 * (math.cos(math.pi * t / d) - 1) + b

def ease_out_cubic(t, b, c, d):
    t /= d
    t -= 1
    return c * (t * t * t + 1) + b

def get_animation_func(anim_type, duration):
    if anim_type == "zoom_gradual":
        return lambda t: ease_in_out_sine(t, 1.0, 0.15, duration)
    elif anim_type == "zoom_sudden":
        # Snappy zoom using ease out
        return lambda t: ease_out_cubic(min(t, 0.3), 1.0, 0.2, 0.3)
    elif anim_type == "zoom_continuous":
        return lambda t: 1 + 0.2 * (t / duration)
    elif anim_type == "tilt":
        return lambda t: math.sin(t * 15) * 3 # Faster, sharper shake
    elif anim_type == "shake_subtle":
        return lambda t: math.sin(t * 8) * 1.5 # Slow, nervous wobble
    return None

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
            
        if line.startswith("# NOTABOT_REACTION:"):
            emotion = line.replace("# NOTABOT_REACTION:", "").strip().lower()
            import glob
            matches = glob.glob(f"../assets/notabot_reactions/notabot_{emotion}*.png")
            if matches:
                clip = ImageClip(matches[0]).set_start(current_time).set_duration(1.5)
                clip = clip.resize(height=VIDEO_H).set_position('center')
                # Zoom in slightly over the duration for dynamic feel
                clip = clip.resize(lambda t: 1 + 0.1 * (t / 1.5))
                clips.append(clip)
                snd_path = '../assets/sounds/mp3/vineboom.mp3'
                if os.path.exists(snd_path):
                    audio_clips.append(AudioFileClip(snd_path).set_start(current_time))
                current_time += 1.5
            continue

        if line.startswith("# REACTION:"):
            parts = line.replace("# REACTION:", "").strip().split(" ", 1)
            if len(parts) == 2:
                character, meme_name = parts
                import glob
                meme_matches = glob.glob(f"../assets/meme_templates/{meme_name}*.jpg")
                if meme_matches:
                    meme_path = meme_matches[0]
                    import json
                    char_db_path = "../assets/profile_pictures/characters.json"
                    pfp_path = None
                    if os.path.exists(char_db_path):
                        with open(char_db_path, "r", encoding="utf-8") as f:
                            chars_db = json.load(f)
                            if character in chars_db:
                                pfp_path = os.path.join("../assets/profile_pictures", chars_db[character]["profile_pic"])
                    
                    if pfp_path and os.path.exists(pfp_path):
                        from PIL import Image as PIL_Image
                        bg = PIL_Image.open(meme_path).convert("RGBA")
                        pfp = PIL_Image.open(pfp_path).convert("RGBA")
                        
                        target_size = int(bg.height / 3)
                        pfp = pfp.resize((target_size, target_size), PIL_Image.LANCZOS)
                        
                        # Add a simple border to the PFP to make it pop
                        from PIL import ImageDraw
                        bordered = PIL_Image.new('RGBA', (target_size+10, target_size+10), (255, 255, 255, 255))
                        bordered.paste(pfp, (5, 5), pfp if pfp.mode == 'RGBA' else None)
                        pfp = bordered
                        
                        paste_x = int((bg.width - pfp.width) / 2)
                        paste_y = int(bg.height / 4)
                        bg.paste(pfp, (paste_x, paste_y), pfp)
                        
                        temp_path = f"../chat/temp_meme_{image_idx}.png"
                        bg.save(temp_path)
                        
                        clip = ImageClip(temp_path).set_start(current_time).set_duration(1.5)
                        
                        vid_w, vid_h = clip.size
                        if vid_w/vid_h > VIDEO_W/VIDEO_H:
                            new_w = int(vid_h * (VIDEO_W/VIDEO_H))
                            clip = clip.crop(x_center=vid_w/2, y_center=vid_h/2, width=new_w, height=vid_h)
                        clip = clip.resize(height=VIDEO_H).set_position('center')
                        
                        clip = clip.resize(lambda t: 1 + 0.1 * (t / 1.5))
                        clips.append(clip)
                        
                        snd_path = '../assets/sounds/mp3/vineboom.mp3'
                        if os.path.exists(snd_path):
                            audio_clips.append(AudioFileClip(snd_path).set_start(current_time))
                        current_time += 1.5
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
            clip = ImageClip(img_path).set_start(current_time).set_duration(duration)
            clip = clip.crop(x1=0, y1=0, x2=min(1200, clip.w), y2=clip.h)
            clip = clip.resize(width=VIDEO_W)
            
            anim_func = None
            anim_type = None
            for tag in tags:
                tag = tag.strip()
                if tag.startswith("zoom_") or tag in ["tilt", "shake_subtle"]:
                    anim_type = tag
                    anim_func = get_animation_func(tag, duration)
                    
            if anim_func and anim_type and anim_type.startswith("zoom"):
                clip = clip.resize(anim_func)
                
            # Reverted dynamic positioning back to center
            clip = clip.set_position(('center', 'center'))
            clips.append(clip)
            
        image_idx += 1
        
        default_snd = '../assets/sounds/mp3/message.mp3'
        if os.path.exists(default_snd):
            audio_clips.append(AudioFileClip(default_snd).set_start(current_time))
            
        for tag in tags:
            tag = tag.strip()
            if not tag.startswith("zoom_") and tag not in ["tilt", "shake_subtle", "message"]:
                snd_path = f"../assets/sounds/mp3/{tag}.mp3"
                if os.path.exists(snd_path):
                    audio_clips.append(AudioFileClip(snd_path).set_start(current_time))
        
        current_time += duration

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
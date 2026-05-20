import os
import math
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np

# Fallback font list (used if the user's chosen font is not found)
FALLBACK_FONTS = [
    "comicbd.ttf",     # Comic Sans MS Bold
    "comic.ttf",       # Comic Sans MS
    "msyh.ttc",        # Microsoft YaHei (Chinese)
    "msgothic.ttc",    # MS Gothic (Japanese)
    "malgun.ttf",      # Malgun Gothic (Korean)
    "arial.ttf",       # Arial
    "segoeui.ttf",     # Segoe UI
]

def get_font(size, font_name=None):
    """Load a font by name, falling back through a list of common fonts."""
    # Try the user-specified font first
    if font_name:
        # Try as-is (full path or system-registered name)
        for attempt in [font_name, font_name + ".ttf", font_name + ".otf", font_name + ".ttc"]:
            try:
                return ImageFont.truetype(attempt, size)
            except (IOError, OSError):
                continue
    
    # Fall back through common fonts
    for fallback in FALLBACK_FONTS:
        try:
            return ImageFont.truetype(fallback, size)
        except (IOError, OSError):
            continue
    
    # Ultimate fallback
    return ImageFont.load_default()

def wrap_text(text, font, max_width):
    """Simple text wrapping."""
    lines = []
    words = text.split()
    if not words:
        return []
        
    current_line = []
    
    for word in words:
        current_line.append(word)
        line_str = " ".join(current_line)
        # Calculate width
        if hasattr(font, 'getbbox'):
            w = font.getbbox(line_str)[2]
        else:
            w = font.getsize(line_str)[0]
            
        if w > max_width and len(current_line) > 1:
            current_line.pop()
            lines.append(" ".join(current_line))
            current_line = [word]
            
    if current_line:
        lines.append(" ".join(current_line))
        
    return lines

def is_dark(color):
    """Returns True if the background color is dark, so text should be white."""
    r, g, b = color
    # Using relative luminance formula
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return luminance < 0.5

def inpaint_text_regions(image, box_infos):
    """
    Uses OpenCV's Fast Marching method to erase original text regions,
    synthesizing and blending texture organically from surrounding pixels.
    """
    try:
        # Convert PIL RGB to OpenCV BGR
        cv_img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        mask = np.zeros(cv_img.shape[:2], dtype=np.uint8)
        
        for info in box_infos:
            # Pad mask slightly (3px) to fully cover text outlines and anti-aliasing edges
            pad = 3
            x0 = max(0, int(info["x_min"]) - pad)
            y0 = max(0, int(info["y_min"]) - pad)
            x1 = min(cv_img.shape[1], int(info["x_max"]) + pad)
            y1 = min(cv_img.shape[0], int(info["y_max"]) + pad)
            
            cv2.rectangle(mask, (x0, y0), (x1, y1), 255, -1)
            
        # Run inpainting
        inpainted = cv2.inpaint(cv_img, mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA)
        
        # Convert back to PIL Image RGB
        return Image.fromarray(cv2.cvtColor(inpainted, cv2.COLOR_BGR2RGB))
    except Exception as e:
        print(f"OpenCV Inpainting failed, falling back to original background: {e}")
        return image

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    if len(hex_str) != 6:
        return (255, 255, 255)
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def get_text_advance(text, font):
    if hasattr(font, 'getlength'):
        try:
            return font.getlength(text)
        except:
            pass
    if hasattr(font, 'getbbox'):
        bbox = font.getbbox(text)
        return bbox[2] - bbox[0]
    return font.getsize(text)[0]

def create_overlay(image, extracted_data, font_name=None):
    """
    Overlays translated text on the image using inpainting, size bucketing, and text strokes.
    Supports advanced rotation rendering and variable per-word font colors.
    """
    img_copy = image.copy()
    
    # ── Pass 1: Calculate the maximum font size that fits each box ──
    box_infos = []
    for item in extracted_data:
        bbox = item["bbox"]
        text = item.get("text", "")
        bg_color = tuple(item.get("background_color", (255, 255, 255)))
        text_color = tuple(item.get("text_color", (0, 0, 0)))
        angle = item.get("angle", 0.0)
        color_spans = item.get("color_spans", [])
        
        x_min = min(p[0] for p in bbox)
        x_max = max(p[0] for p in bbox)
        y_min = min(p[1] for p in bbox)
        y_max = max(p[1] for p in bbox)
        
        # Rotated size bounds
        x1, y1 = bbox[0]
        x2, y2 = bbox[1]
        x3, y3 = bbox[2]
        x4, y4 = bbox[3]
        
        if abs(angle) >= 2.0:
            width = int(math.sqrt((x2 - x1)**2 + (y2 - y1)**2))
            height = int(math.sqrt((x4 - x1)**2 + (y4 - y1)**2))
        else:
            width = x_max - x_min
            height = y_max - y_min
            
        if width <= 0 or height <= 0:
            continue
        
        # Find the largest font size that fits this box
        font_size = max(10, int(height * 0.8))
        while font_size > 8:
            font = get_font(font_size, font_name)
            lines = wrap_text(text, font, width)
            if not lines:
                break
            if hasattr(font, 'getbbox'):
                line_height = font.getbbox("A")[3] - font.getbbox("A")[1]
            else:
                line_height = font.getsize("A")[1]
            total_height = line_height * len(lines)
            if total_height <= height:
                break
            font_size -= 2
        
        box_infos.append({
            "bbox": bbox,
            "x_min": x_min, "x_max": x_max, "y_min": y_min, "y_max": y_max,
            "width": width, "height": height,
            "text": text, "bg_color": bg_color,
            "text_color": text_color,
            "angle": angle,
            "color_spans": color_spans,
            "fitted_font_size": max(font_size, 8)
        })
    
    if not box_infos:
        # Save and return as-is if no text is found
        os.makedirs("translated", exist_ok=True)
        filepath = os.path.join("translated", datetime.now().strftime("%Y-%m-%d_%H-%M-%S.png"))
        img_copy.save(filepath)
        return filepath
        
    # ── OpenCV Inpainting: Organic texture erasure of original text ──
    img_copy = inpaint_text_regions(img_copy, box_infos)
    draw = ImageDraw.Draw(img_copy)
    
    # ── Pass 2: Normalize sizes by bucketing to preserve visual hierarchy ──
    large_group = [info for info in box_infos if info["fitted_font_size"] >= 20]
    medium_group = [info for info in box_infos if 13 <= info["fitted_font_size"] < 20]
    small_group = [info for info in box_infos if info["fitted_font_size"] < 13]
    
    unified_large = min(info["fitted_font_size"] for info in large_group) if large_group else 0
    unified_medium = min(info["fitted_font_size"] for info in medium_group) if medium_group else 0
    unified_small = min(info["fitted_font_size"] for info in small_group) if small_group else 0
    
    # Enforce hierarchical constraints (Large >= Medium >= Small)
    if unified_medium < unified_small:
        unified_medium = max(unified_medium, unified_small)
    if unified_large < unified_medium:
        unified_large = max(unified_large, unified_medium)
        
    for info in large_group:
        info["unified_font_size"] = unified_large
    for info in medium_group:
        info["unified_font_size"] = unified_medium
    for info in small_group:
        info["unified_font_size"] = unified_small
        
    # ── Pass 3: Draw text overlays with custom dynamic strokes ──
    for info in box_infos:
        font_size = info["unified_font_size"]
        font = get_font(font_size, font_name)
        
        if hasattr(font, 'getbbox'):
            line_height = font.getbbox("A")[3] - font.getbbox("A")[1]
        else:
            line_height = font.getsize("A")[1]
            
        width = info["width"]
        height = info["height"]
        bbox = info["bbox"]
        angle = info["angle"]
        text_color = info["text_color"]
        color_spans = info["color_spans"]
        translated_text = info["text"]
        
        lines = wrap_text(translated_text, font, width)
        total_height = line_height * len(lines)
        
        # Build character color map
        char_colors = [text_color] * len(translated_text)
        for span_obj in color_spans:
            span_str = span_obj["span"]
            hex_color = span_obj["color"]
            rgb_color = hex_to_rgb(hex_color)
            
            start_idx = 0
            while True:
                idx = translated_text.lower().find(span_str.lower(), start_idx)
                if idx == -1:
                    break
                for k in range(idx, idx + len(span_str)):
                    if k < len(char_colors):
                        char_colors[k] = rgb_color
                start_idx = idx + 1
        
        # Dynamically scale stroke width relative to the active font size
        if font_size < 12:
            stroke_w = 1
        elif font_size < 24:
            stroke_w = 2
        else:
            stroke_w = 3
            
        def draw_lines_on_canvas(draw_obj, base_x, base_y):
            y_offset = base_y
            current_search_idx = 0
            
            for line in lines:
                line_idx = translated_text.find(line, current_search_idx)
                if line_idx == -1:
                    line_idx = 0
                current_search_idx = line_idx + len(line)
                
                # Segment line into contiguous color chunks
                segments = []
                if line:
                    start_char_idx = line_idx
                    current_segment_text = [line[0]]
                    current_color = char_colors[min(start_char_idx, len(char_colors)-1)]
                    
                    for char_in_line_idx, char in enumerate(line[1:], start=1):
                        global_char_idx = start_char_idx + char_in_line_idx
                        color = char_colors[min(global_char_idx, len(char_colors)-1)]
                        if color == current_color:
                            current_segment_text.append(char)
                        else:
                            segments.append({
                                "text": "".join(current_segment_text),
                                "color": current_color
                            })
                            current_color = color
                            current_segment_text = [char]
                            
                    segments.append({
                        "text": "".join(current_segment_text),
                        "color": current_color
                    })
                
                # Calculate total line width
                if hasattr(font, 'getbbox'):
                    line_width = font.getbbox(line)[2]
                else:
                    line_width = font.getsize(line)[0]
                    
                x_offset = base_x + max(0, (width - line_width) // 2)
                
                # Draw segments
                x_cursor = x_offset
                for seg in segments:
                    seg_color = seg["color"]
                    seg_stroke = (255, 255, 255) if is_dark(seg_color) else (0, 0, 0)
                    draw_obj.text(
                        (x_cursor, y_offset),
                        seg["text"],
                        font=font,
                        fill=seg_color,
                        stroke_width=stroke_w,
                        stroke_fill=seg_stroke
                    )
                    x_cursor += get_text_advance(seg["text"], font)
                    
                y_offset += line_height

        # Render rotated vs normal
        if abs(angle) < 2.0:
            y_start = info["y_min"] + max(0, (height - total_height) // 2)
            draw_lines_on_canvas(draw, info["x_min"], y_start)
        else:
            # Render to transparent temporary canvas
            txt_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            txt_draw = ImageDraw.Draw(txt_img)
            
            y_start = max(0, (height - total_height) // 2)
            draw_lines_on_canvas(txt_draw, 0, y_start)
            
            # Rotate temporary image
            rotated_txt_img = txt_img.rotate(-angle, resample=Image.Resampling.BICUBIC, expand=True)
            
            # Bounding box center
            cx = sum(p[0] for p in bbox) / len(bbox)
            cy = sum(p[1] for p in bbox) / len(bbox)
            
            # Rotated image center
            rcx = rotated_txt_img.width / 2
            rcy = rotated_txt_img.height / 2
            
            paste_x = int(cx - rcx)
            paste_y = int(cy - rcy)
            
            # Paste with alpha mask
            img_copy.paste(rotated_txt_img, (paste_x, paste_y), rotated_txt_img)
            
    # Save the file
    os.makedirs("translated", exist_ok=True)
    filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S.png")
    filepath = os.path.join("translated", filename)
    img_copy.save(filepath)
        
    return filepath

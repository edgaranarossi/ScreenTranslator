import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

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
    # If the font does not have getbbox, use getsize (older Pillow)
    # Pillow 10+ requires getbbox or getlength
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
    # Using luminance formula
    r, g, b = color
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return luminance < 0.5

def create_overlay(image, extracted_data, font_name=None):
    """
    Overlays translated text on the image.
    extracted_data contains list of dicts: bbox, text, background_color
    font_name: optional font name/path to use
    """
    img_copy = image.copy()
    draw = ImageDraw.Draw(img_copy)
    
    # ── Pass 1: Calculate the maximum font size that fits each box ──
    box_infos = []
    for item in extracted_data:
        bbox = item["bbox"]
        text = item.get("text", "")
        bg_color = tuple(item.get("background_color", (255, 255, 255)))
        
        x_min = min(p[0] for p in bbox)
        x_max = max(p[0] for p in bbox)
        y_min = min(p[1] for p in bbox)
        y_max = max(p[1] for p in bbox)
        
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
            "x_min": x_min, "x_max": x_max, "y_min": y_min, "y_max": y_max,
            "width": width, "height": height,
            "text": text, "bg_color": bg_color,
            "fitted_font_size": max(font_size, 8)
        })
    
    # ── Normalize: use the smallest fitted font size for all boxes ──
    if not box_infos:
        pass  # nothing to draw
    else:
        unified_size = min(info["fitted_font_size"] for info in box_infos)
        unified_font = get_font(unified_size, font_name)
        
        if hasattr(unified_font, 'getbbox'):
            line_height = unified_font.getbbox("A")[3] - unified_font.getbbox("A")[1]
        else:
            line_height = unified_font.getsize("A")[1]
    
        # ── Pass 2: Draw with the unified font size ──
        for info in box_infos:
            # Draw background rectangle
            draw.rectangle([info["x_min"], info["y_min"], info["x_max"], info["y_max"]], fill=info["bg_color"])
            
            # Determine text color based on background
            text_color = (255, 255, 255) if is_dark(info["bg_color"]) else (0, 0, 0)
            
            lines = wrap_text(info["text"], unified_font, info["width"])
            total_height = line_height * len(lines)
            y_offset = info["y_min"] + max(0, (info["height"] - total_height) // 2)
            
            for line in lines:
                if hasattr(unified_font, 'getbbox'):
                    line_width = unified_font.getbbox(line)[2]
                else:
                    line_width = unified_font.getsize(line)[0]
                x_offset = info["x_min"] + max(0, (info["width"] - line_width) // 2)
                draw.text((x_offset, y_offset), line, font=unified_font, fill=text_color)
                y_offset += line_height
            
    # Save the file
    os.makedirs("translated", exist_ok=True)
    filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S.png")
    filepath = os.path.join("translated", filename)
    img_copy.save(filepath)
    
    # Open the image with default viewer
    try:
        os.startfile(filepath)
    except Exception as e:
        print(f"Error opening image: {e}")
        
    return filepath

import os
import math
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np


# Anchor output to the source directory so saved overlays land in a stable
# location regardless of the working directory the app was launched from.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _output_path():
    """Return a fresh, collision-free path under <BASE_DIR>/translated/."""
    out_dir = os.path.join(BASE_DIR, "translated")
    os.makedirs(out_dir, exist_ok=True)
    # Microsecond suffix prevents sub-second recaptures from overwriting output.
    name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f") + ".png"
    return os.path.join(out_dir, name)


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

# Maps the GUI's font display names to their actual Windows font filenames.
# PIL's truetype lookup is case-sensitive here ("Arial" fails, "arial.ttf"
# works), so a display name like "Arial" or "Segoe UI" would otherwise fall
# through to the fallback list (Comic Sans), silently ignoring the user's choice.
_FONT_NAME_TO_FILE = {
    "wild words": "wildwords.ttf",
    "cc wild words roman": "wildwords.ttf",
    "anime ace": "animeace.ttf",
    "comic sans ms": "comic.ttf",
    "arial": "arial.ttf",
    "segoe ui": "segoeui.ttf",
    "ms gothic": "msgothic.ttc",
    "meiryo": "meiryo.ttc",
}

def get_font(size, font_name=None):
    """Load a font by name, falling back through a list of common fonts."""
    # Try the user-specified font first
    if font_name:
        attempts = [font_name, font_name + ".ttf", font_name + ".otf", font_name + ".ttc"]
        # PIL is case-sensitive on the filename: also try a known display-name
        # mapping and lowercase/space-stripped variants.
        mapped = _FONT_NAME_TO_FILE.get(font_name.strip().lower())
        if mapped:
            attempts.insert(0, mapped)
        low = font_name.strip().lower()
        attempts += [low + ".ttf", low.replace(" ", "") + ".ttf",
                     low + ".ttc", low.replace(" ", "") + ".ttc"]
        for attempt in attempts:
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

# Unicode ranges that Latin fonts (e.g. Arial) cannot render -> tofu rectangles.
import re
_CJK_RE = re.compile(
    "[　-〿"   # CJK symbols & punctuation
    "぀-ゟ"    # Hiragana
    "゠-ヿ"    # Katakana
    "㐀-䶿"    # CJK Ext A
    "一-鿿"    # CJK Unified Ideographs
    "豈-﫿"    # CJK Compatibility Ideographs
    "＀-￯"    # Halfwidth/Fullwidth forms (incl. 。！？)
    "가-힯]"   # Hangul
)

# CJK-capable fonts that ALSO include Latin glyphs, in preference order.
_CJK_FONTS = ["meiryo.ttc", "YuGothM.ttc", "YuGothR.ttc", "msgothic.ttc",
              "msyh.ttc", "malgun.ttf", "simsun.ttc"]

def _has_cjk(text):
    return bool(_CJK_RE.search(text or ""))

def _get_cjk_font(size):
    for fname in _CJK_FONTS:
        try:
            return ImageFont.truetype(fname, size)
        except (IOError, OSError):
            continue
    return None

# Glyph-coverage cache: {font_path: set_of_codepoints | None}.
# None means coverage couldn't be determined (fontTools missing/unreadable).
_cmap_cache = {}

def _font_codepoints(path):
    if path in _cmap_cache:
        return _cmap_cache[path]
    cps = None
    try:
        from fontTools.ttLib import TTFont, TTCollection
        if path.lower().endswith(".ttc"):
            cps = set()
            for f in TTCollection(path).fonts:
                cps |= set(f.getBestCmap().keys())
        else:
            cps = set(TTFont(path).getBestCmap().keys())
    except Exception:
        cps = None
    _cmap_cache[path] = cps
    return cps

def _covers(font, text):
    """True/False if `font` can render every glyph in `text`; None if unknown."""
    path = getattr(font, "path", None)
    if not path:
        return None
    cps = _font_codepoints(path)
    if cps is None:
        return None
    for ch in text or "":
        if ord(ch) < 32:
            continue
        if ord(ch) not in cps:
            return False
    return True

def get_font_for_text(text, size, font_name=None):
    """Pick a font that can render EVERY glyph in `text`.

    The user's chosen font (e.g. Arial) is Latin-only and lacks both CJK
    characters (from untranslated blocks / OCR kana) and many symbols actually
    present in stream UIs (℃, ☆, ※, ◆ ...). Any uncovered glyph renders as a
    tofu rectangle. So: if the user font covers the text, use it; otherwise fall
    back to a broad CJK font (Meiryo et al. cover Latin + CJK + symbols). When
    fontTools is unavailable, degrade to a CJK-presence heuristic.
    """
    user_font = get_font(size, font_name)
    cov = _covers(user_font, text)
    if cov is True:
        return user_font
    if cov is None:
        # Coverage undeterminable: use the cheap CJK heuristic.
        if _has_cjk(text):
            return _get_cjk_font(size) or user_font
        return user_font
    # cov is False -> user font is missing glyphs; find a fallback that covers them.
    for fname in _CJK_FONTS:
        try:
            cand = ImageFont.truetype(fname, size)
        except (IOError, OSError):
            continue
        if _covers(cand, text):
            return cand
    return _get_cjk_font(size) or user_font

def _hard_break(token, font, max_width):
    """Break a single over-wide token into character-level chunks that each fit
    max_width. Returns (completed_lines, trailing_remainder)."""
    lines = []
    chunk = ""
    for ch in token:
        trial = chunk + ch
        # Always keep at least one char per line, even if it alone overflows.
        if chunk and get_text_advance(trial, font) > max_width:
            lines.append(chunk)
            chunk = ch
        else:
            chunk = trial
    return lines, chunk

def wrap_text(text, font, max_width):
    """Wrap text to fit max_width, hard-breaking tokens too long to fit on their
    own line (long URLs, or space-less CJK runs from untranslated blocks) at the
    character level so they never overflow the box."""
    if max_width <= 0 or not text:
        return [text] if text else []
    words = text.split()
    if not words:
        return []

    lines = []
    current = ""
    for word in words:
        candidate = word if not current else current + " " + word
        if get_text_advance(candidate, font) <= max_width:
            current = candidate
            continue
        # The candidate doesn't fit: flush the current line first.
        if current:
            lines.append(current)
            current = ""
        if get_text_advance(word, font) <= max_width:
            current = word
        else:
            # The word itself is wider than the box -> hard-break it.
            pieces, leftover = _hard_break(word, font, max_width)
            lines.extend(pieces)
            current = leftover

    if current:
        lines.append(current)
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
            # Pad mask slightly (5px) to fully cover text outlines and anti-aliasing edges
            pad = 5
            for obox in info.get("original_bboxes", [info["bbox"]]):
                x_min_o = min(p[0] for p in obox)
                x_max_o = max(p[0] for p in obox)
                y_min_o = min(p[1] for p in obox)
                y_max_o = max(p[1] for p in obox)
                
                x0 = max(0, int(x_min_o) - pad)
                y0 = max(0, int(y_min_o) - pad)
                x1 = min(cv_img.shape[1], int(x_max_o) + pad)
                y1 = min(cv_img.shape[0], int(y_max_o) + pad)
                
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
            font = get_font_for_text(text, font_size, font_name)
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
            "original_bboxes": item.get("original_bboxes", [bbox]),
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
        filepath = _output_path()
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
        font = get_font_for_text(info.get("text", ""), font_size, font_name)
        
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
                    
                x_offset = base_x + (width - line_width) // 2
                
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
            y_start = info["y_min"] + (height - total_height) // 2
            draw_lines_on_canvas(draw, info["x_min"], y_start)
        else:
            # Render to transparent temporary canvas
            # Find the maximum width among all wrapped lines to define canvas width
            line_widths = []
            for line in lines:
                if hasattr(font, 'getbbox'):
                    w = font.getbbox(line)[2]
                else:
                    w = font.getsize(line)[0]
                line_widths.append(w)
            max_line_w = max(line_widths) if line_widths else width
            
            canvas_w = max(width, max_line_w)
            canvas_h = max(height, total_height)
            
            txt_img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            txt_draw = ImageDraw.Draw(txt_img)
            
            base_x = (canvas_w - width) // 2
            y_start = (canvas_h - total_height) // 2
            draw_lines_on_canvas(txt_draw, base_x, y_start)
            
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
    filepath = _output_path()
    img_copy.save(filepath)

    return filepath

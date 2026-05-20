import numpy as np
import cv2
from PIL import Image

# Global reader instances (lazy-loaded)
_easyocr_reader = None
_easyocr_langs = None
_paddle_ocr = None
_paddle_lang = None
_manga_ocr_model = None

try:
    import winocr
    _winocr_available = True
except ImportError:
    _winocr_available = False

# ─── EasyOCR ────────────────────────────────────────────────────────────

def _get_easyocr_lang_list(source_language):
    lang_map = {
        "ja": ['ja', 'en'],
        "zh": ['ch_sim', 'en'],
        "ko": ['ko', 'en'],
        "en": ['en']
    }
    return lang_map.get(source_language.lower(), ['en'])

def _init_easyocr(source_language):
    global _easyocr_reader, _easyocr_langs
    import easyocr
    langs = _get_easyocr_lang_list(source_language)
    if _easyocr_reader is None or _easyocr_langs != langs:
        print(f"Loading EasyOCR model for {langs}...")
        _easyocr_reader = easyocr.Reader(langs, gpu=True)
        _easyocr_langs = langs
    return _easyocr_reader

def _extract_easyocr(img, img_np, source_language):
    reader = _init_easyocr(source_language)
    results = reader.readtext(img_np, paragraph=True)
    
    extracted_data = []
    for i, res in enumerate(results):
        if len(res) == 2:
            bbox, text = res
        else:
            bbox, text, _ = res
        bg_color = get_dominant_color(img, bbox)
        
        bbox_list = [[int(pt[0]), int(pt[1])] for pt in bbox]
        text_color = get_text_color(img, bbox_list, bg_color)
        angle = get_bbox_angle(bbox_list)
        word_colors = [{"word": text, "color": rgb_to_hex(text_color)}]
        
        extracted_data.append({
            "id": i,
            "text": text,
            "bbox": bbox_list,
            "background_color": [int(c) for c in bg_color],
            "text_color": [int(c) for c in text_color],
            "angle": angle,
            "word_colors": word_colors
        })
    return extracted_data

# ─── PaddleOCR ───────────────────────────────────────────────────────────

def _get_paddle_lang(source_language):
    lang_map = {
        "ja": "japan",
        "zh": "ch",
        "ko": "korean",
        "en": "en"
    }
    return lang_map.get(source_language.lower(), "en")

def _init_paddle(source_language):
    global _paddle_ocr, _paddle_lang
    from paddleocr import PaddleOCR
    lang = _get_paddle_lang(source_language)
    if _paddle_ocr is None or _paddle_lang != lang:
        print(f"Loading PaddleOCR model for '{lang}'...")
        _paddle_ocr = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
        _paddle_lang = lang
    return _paddle_ocr

def _extract_paddle(img, img_np, source_language):
    ocr_engine = _init_paddle(source_language)
    results = ocr_engine.ocr(img_np, cls=True)
    
    extracted_data = []
    if results is None or results[0] is None:
        return extracted_data
        
    idx = 0
    for line in results[0]:
        bbox_raw = line[0]   # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
        text = line[1][0]
        # score = line[1][1]
        
        bbox = [[int(pt[0]), int(pt[1])] for pt in bbox_raw]
        bg_color = get_dominant_color(img, bbox)
        
        text_color = get_text_color(img, bbox, bg_color)
        angle = get_bbox_angle(bbox)
        word_colors = [{"word": text, "color": rgb_to_hex(text_color)}]
        
        extracted_data.append({
            "id": idx,
            "text": text,
            "bbox": bbox,
            "background_color": [int(c) for c in bg_color],
            "text_color": [int(c) for c in text_color],
            "angle": angle,
            "word_colors": word_colors
        })
        idx += 1
    return extracted_data

# ─── MangaOCR ────────────────────────────────────────────────────────────

def _init_manga_ocr():
    global _manga_ocr_model
    if _manga_ocr_model is None:
        from manga_ocr import MangaOcr
        print("Loading MangaOCR model (first run will download ~450MB)...")
        _manga_ocr_model = MangaOcr()
    return _manga_ocr_model

def _extract_manga(img, img_np, source_language):
    """
    MangaOCR is a recognizer only (no text detection).
    We use EasyOCR to detect bounding boxes, then pass each
    cropped region to MangaOCR for superior Japanese text recognition.
    """
    mocr = _init_manga_ocr()
    
    # Use EasyOCR just for bounding box detection
    reader = _init_easyocr(source_language)
    results = reader.readtext(img_np, paragraph=True)
    
    extracted_data = []
    for i, res in enumerate(results):
        if len(res) == 2:
            bbox, _ = res
        else:
            bbox, _, _ = res
        
        # Crop the bounding box region from the PIL image
        pts = np.array(bbox, dtype=np.int32)
        x_min = max(0, np.min(pts[:, 0]))
        x_max = min(img.width, np.max(pts[:, 0]))
        y_min = max(0, np.min(pts[:, 1]))
        y_max = min(img.height, np.max(pts[:, 1]))
        
        cropped = img.crop((x_min, y_min, x_max, y_max))
        
        # MangaOCR recognizes text from a PIL Image
        text = mocr(cropped)
        
        bg_color = get_dominant_color(img, bbox)
        
        bbox_list = [[int(pt[0]), int(pt[1])] for pt in bbox]
        text_color = get_text_color(img, bbox_list, bg_color)
        angle = get_bbox_angle(bbox_list)
        word_colors = [{"word": text, "color": rgb_to_hex(text_color)}]
        
        extracted_data.append({
            "id": i,
            "text": text,
            "bbox": bbox_list,
            "background_color": [int(c) for c in bg_color],
            "text_color": [int(c) for c in text_color],
            "angle": angle,
            "word_colors": word_colors
        })
    return extracted_data

# ─── Windows Media OCR ───────────────────────────────────────────────────

def _extract_windows_ocr(img, img_np, source_language):
    global _winocr_available
    if not _winocr_available:
        print("winocr package is not available. Falling back to EasyOCR.")
        return _extract_easyocr(img, img_np, source_language)
        
    # Map source language to BCP-47 tags
    lang_map = {
        "ja": "ja",
        "zh": "zh-Hans",
        "ko": "ko",
        "en": "en"
    }
    
    lang_tag = lang_map.get(source_language.lower(), "en")
    
    is_supported = False
    try:
        is_supported = winocr.OcrEngine.is_language_supported(winocr.Language(lang_tag))
    except Exception as e:
        print(f"Error checking support for language '{lang_tag}': {e}")
        
    if not is_supported:
        # Graceful fallbacks for 'auto'
        if source_language.lower() == "auto":
            for fallback_lang in ["ja", "en"]:
                try:
                    if winocr.OcrEngine.is_language_supported(winocr.Language(fallback_lang)):
                        lang_tag = fallback_lang
                        is_supported = True
                        break
                except Exception:
                    pass
        
        if not is_supported:
            print(f"Windows OCR does not support language '{lang_tag}' on this system. Falling back to EasyOCR.")
            return _extract_easyocr(img, img_np, source_language)
            
    print(f"Using Windows OCR with language '{lang_tag}'...")
    try:
        result = winocr.recognize_pil_sync(img, lang=lang_tag)
    except Exception as e:
        print(f"Windows OCR recognition failed: {e}. Falling back to EasyOCR.")
        return _extract_easyocr(img, img_np, source_language)
        
    extracted_data = []
    lines = result.get("lines", [])
    
    for i, line in enumerate(lines):
        text = line.get("text", "").strip()
        if not text:
            continue
            
        words = line.get("words", [])
        if not words:
            continue
            
        x_coords = []
        y_coords = []
        for w in words:
            rect = w.get("bounding_rect")
            if rect:
                x = rect.get("x", 0)
                y = rect.get("y", 0)
                width = rect.get("width", 0)
                height = rect.get("height", 0)
                x_coords.extend([x, x + width])
                y_coords.extend([y, y + height])
                
        if not x_coords or not y_coords:
            continue
            
        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)
        
        # Clamp to image boundaries
        x_min = max(0, min(int(x_min), img.width))
        x_max = max(0, min(int(x_max), img.width))
        y_min = max(0, min(int(y_min), img.height))
        y_max = max(0, min(int(y_max), img.height))
        
        if x_max <= x_min or y_max <= y_min:
            continue
        
        bbox = [
            [x_min, y_min],
            [x_max, y_min],
            [x_max, y_max],
            [x_min, y_max]
        ]
        
        bg_color = get_dominant_color(img, bbox)
        text_color = get_text_color(img, bbox, bg_color)
        angle = get_bbox_angle(bbox)
        
        word_colors = []
        for w in words:
            rect = w.get("bounding_rect")
            if rect:
                wx = max(0, min(int(rect.get("x", 0)), img.width))
                wy = max(0, min(int(rect.get("y", 0)), img.height))
                ww = max(0, min(int(rect.get("width", 0)), img.width - wx))
                wh = max(0, min(int(rect.get("height", 0)), img.height - wy))
                if ww > 0 and wh > 0:
                    w_bbox = [
                        [wx, wy],
                        [wx + ww, wy],
                        [wx + ww, wy + wh],
                        [wx, wy + wh]
                    ]
                    w_color = get_text_color(img, w_bbox, bg_color)
                    word_colors.append({
                        "word": w.get("text", ""),
                        "color": rgb_to_hex(w_color)
                    })
                    
        if not word_colors:
            word_colors = [{"word": text, "color": rgb_to_hex(text_color)}]
            
        extracted_data.append({
            "id": i,
            "text": text,
            "bbox": bbox,
            "background_color": [int(c) for c in bg_color],
            "text_color": [int(c) for c in text_color],
            "angle": angle,
            "word_colors": word_colors
        })
        
    return extracted_data

# ─── Shared Utilities ────────────────────────────────────────────────────

def get_dominant_color(image, bbox):
    """
    Samples pixels from the edges of the bounding box to find a dominant background color.
    bbox is in format [[x1, y1], [x2, y1], [x2, y2], [x1, y2]] (top-left, top-right, bottom-right, bottom-left)
    """
    img_np = np.array(image.convert("RGB"))
    
    pts = np.array(bbox, dtype=np.int32)
    x_min = max(0, np.min(pts[:, 0]))
    x_max = min(img_np.shape[1], np.max(pts[:, 0]))
    y_min = max(0, np.min(pts[:, 1]))
    y_max = min(img_np.shape[0], np.max(pts[:, 1]))
    
    crop = img_np[y_min:y_max, x_min:x_max]
    
    if crop.size == 0:
        return (255, 255, 255)
        
    h, w, _ = crop.shape
    
    border_pixels = []
    if h > 0 and w > 0:
        border_pixels.append(crop[0, :])
        border_pixels.append(crop[-1, :])
        border_pixels.append(crop[:, 0])
        border_pixels.append(crop[:, -1])
    
    if not border_pixels:
        return (255, 255, 255)
        
    border_pixels = np.concatenate(border_pixels, axis=0)
    median_color = np.median(border_pixels, axis=0).astype(int)
    
    return tuple(median_color)

def is_dark(color):
    r, g, b = color
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return luminance < 0.5

def get_bbox_angle(bbox):
    """
    Computes the rotation angle in degrees from a 4-corner polygon:
    [[x1,y1],[x2,y2],[x3,y3],[x4,y4]] (usually top-left, top-right, bottom-right, bottom-left)
    """
    if not bbox or len(bbox) < 4:
        return 0.0
        
    import math
    dx = bbox[1][0] - bbox[0][0]  # top-right minus top-left
    dy = bbox[1][1] - bbox[0][1]
    angle_rad = math.atan2(dy, dx)
    angle_deg = math.degrees(angle_rad)
    
    # Avoid small angle jitter
    if abs(angle_deg) < 2.0:
        return 0.0
    return angle_deg

def rgb_to_hex(rgb):
    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"

def get_text_color(image, bbox, bg_color):
    """
    Extracts the dominant text (foreground) color from a bounding box region.
    """
    pts = np.array(bbox, dtype=np.int32)
    x_min = max(0, np.min(pts[:, 0]))
    x_max = min(image.width, np.max(pts[:, 0]))
    y_min = max(0, np.min(pts[:, 1]))
    y_max = min(image.height, np.max(pts[:, 1]))
    
    if x_max <= x_min or y_max <= y_min:
        return (255, 255, 255) if is_dark(bg_color) else (0, 0, 0)
        
    crop = image.crop((x_min, y_min, x_max, y_max))
    pixels = np.array(crop.convert("RGB")).reshape(-1, 3)
    
    # Calculate Euclidean distance from bg_color
    bg = np.array(bg_color)
    distances = np.linalg.norm(pixels - bg, axis=1)
    
    # Select foreground pixels
    fg_pixels = pixels[distances > 45]
    
    if len(fg_pixels) < 5:
        fg_pixels = pixels[distances > 20]
        
    if len(fg_pixels) < 5:
        return (255, 255, 255) if is_dark(bg_color) else (0, 0, 0)
        
    median_color = np.median(fg_pixels, axis=0).astype(int)
    return tuple(median_color)

# ─── Public API ──────────────────────────────────────────────────────────

def initialize_ocr(engine="WindowsOCR"):
    """Pre-downloads models for the selected engine on startup."""
    print(f"Initializing OCR engine: {engine}...")
    if engine == "WindowsOCR":
        print("Windows OCR initialized successfully (using native system APIs).")
    elif engine == "EasyOCR":
        import easyocr
        lang_groups = [['en'], ['ja', 'en'], ['ch_sim', 'en'], ['ch_tra', 'en'], ['ko', 'en']]
        for langs in lang_groups:
            try:
                print(f"Checking/Downloading models for {langs}...")
                temp_reader = easyocr.Reader(langs, gpu=True)
                del temp_reader
            except Exception as e:
                print(f"Warning: Failed to initialize {langs}: {e}")
    elif engine == "PaddleOCR":
        print("PaddleOCR models will be downloaded on first use.")
    elif engine == "MangaOCR":
        print("MangaOCR model will be downloaded on first use.")
        # Also need EasyOCR for bounding box detection
        import easyocr
        print("Checking/Downloading EasyOCR models for bbox detection...")
        try:
            temp_reader = easyocr.Reader(['ja', 'en'], gpu=True)
            del temp_reader
        except Exception as e:
            print(f"Warning: Failed to initialize EasyOCR for bbox detection: {e}")
    print("OCR initialization complete.")

def extract_text(image_path_or_pil, source_language="auto", engine="WindowsOCR"):
    """
    Extracts text from an image using the selected OCR engine.
    Returns a list of dicts: {id, text, bbox, background_color}
    """
    if isinstance(image_path_or_pil, str):
        img = Image.open(image_path_or_pil)
    else:
        img = image_path_or_pil
    img_np = np.array(img.convert("RGB"))
    
    if engine == "PaddleOCR":
        return _extract_paddle(img, img_np, source_language)
    elif engine == "MangaOCR":
        return _extract_manga(img, img_np, source_language)
    elif engine == "WindowsOCR":
        return _extract_windows_ocr(img, img_np, source_language)
    else:
        return _extract_easyocr(img, img_np, source_language)

# ─── Multi-OCR Consensus ─────────────────────────────────────────────────

def _recognize_crop_winocr(crop_pil, source_language):
    """Run Windows OCR on a small cropped PIL image, return recognized text."""
    global _winocr_available
    if not _winocr_available:
        return None
    
    lang_map = {"ja": "ja", "zh": "zh-Hans", "ko": "ko", "en": "en"}
    lang_tag = lang_map.get(source_language.lower(), "en")
    
    try:
        result = winocr.recognize_pil_sync(crop_pil, lang=lang_tag)
        lines = result.get("lines", [])
        text = " ".join(line.get("text", "") for line in lines).strip()
        return text if text else None
    except Exception:
        return None

def _recognize_crop_easyocr(crop_pil, source_language):
    """Run EasyOCR on a small cropped PIL image, return recognized text."""
    try:
        reader = _init_easyocr(source_language)
        crop_np = np.array(crop_pil.convert("RGB"))
        results = reader.readtext(crop_np, paragraph=True)
        
        texts = []
        for res in results:
            if len(res) == 2:
                _, text = res
            else:
                _, text, _ = res
            texts.append(text)
        
        combined = " ".join(texts).strip()
        return combined if combined else None
    except Exception:
        return None

def _get_secondary_engine(primary_engine):
    """Determine which secondary OCR engine to use for multi-OCR consensus."""
    if primary_engine == "WindowsOCR":
        return "EasyOCR"
    elif primary_engine in ("EasyOCR", "PaddleOCR", "MangaOCR"):
        return "WindowsOCR"
    return "EasyOCR"

def extract_text_multi(image_path_or_pil, source_language="auto", engine="WindowsOCR"):
    """
    Multi-OCR consensus extraction.
    1. Runs the primary engine for bounding box detection + text.
    2. For each detected bbox, crops the image and runs a secondary engine 
       to get an alternative text proposal.
    3. Returns the same format as extract_text(), but each item gains a
       "proposals" list: [{"engine": "...", "text": "..."}, ...].
    """
    if isinstance(image_path_or_pil, str):
        img = Image.open(image_path_or_pil)
    else:
        img = image_path_or_pil
    
    # Step 1: Run primary engine
    extracted_data = extract_text(img, source_language, engine)
    
    if not extracted_data:
        return extracted_data
    
    # Step 2: Determine secondary engine
    secondary = _get_secondary_engine(engine)
    
    # Step 3: For each bbox, crop and run secondary recognition
    pad = 5  # Small padding around the crop for context
    for item in extracted_data:
        bbox = item["bbox"]
        x_min = max(0, min(p[0] for p in bbox) - pad)
        y_min = max(0, min(p[1] for p in bbox) - pad)
        x_max = min(img.width, max(p[0] for p in bbox) + pad)
        y_max = min(img.height, max(p[1] for p in bbox) + pad)
        
        crop = img.crop((x_min, y_min, x_max, y_max))
        
        proposals = [{"engine": engine, "text": item["text"]}]
        
        # Run secondary OCR on the crop
        secondary_text = None
        if secondary == "WindowsOCR":
            secondary_text = _recognize_crop_winocr(crop, source_language)
        elif secondary == "EasyOCR":
            secondary_text = _recognize_crop_easyocr(crop, source_language)
        
        if secondary_text and secondary_text != item["text"]:
            proposals.append({"engine": secondary, "text": secondary_text})
        
        item["proposals"] = proposals
    
    return extracted_data


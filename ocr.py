import numpy as np
import cv2
from PIL import Image

# Global reader instances (lazy-loaded)
_easyocr_reader = None
_easyocr_langs = None
_paddle_ocr = None
_paddle_lang = None
_manga_ocr_model = None

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
        extracted_data.append({
            "id": i,
            "text": text,
            "bbox": [[int(pt[0]), int(pt[1])] for pt in bbox],
            "background_color": [int(c) for c in bg_color]
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
        extracted_data.append({
            "id": idx,
            "text": text,
            "bbox": bbox,
            "background_color": [int(c) for c in bg_color]
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
        extracted_data.append({
            "id": i,
            "text": text,
            "bbox": [[int(pt[0]), int(pt[1])] for pt in bbox],
            "background_color": [int(c) for c in bg_color]
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

# ─── Public API ──────────────────────────────────────────────────────────

def initialize_ocr(engine="EasyOCR"):
    """Pre-downloads models for the selected engine on startup."""
    print(f"Initializing OCR engine: {engine}...")
    if engine == "EasyOCR":
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

def extract_text(image_path_or_pil, source_language="auto", engine="EasyOCR"):
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
    else:
        return _extract_easyocr(img, img_np, source_language)

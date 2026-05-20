import random
from PIL import Image, ImageDraw, ImageFont
import ocr
import translator
import overlay
import os

def create_test_image(size=(800, 800)):
    # Create a white background image
    img = Image.new('RGB', size, color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to load a Japanese-compatible font
    font_path = None
    for f in ["msgothic.ttc", "meiryo.ttc", "msyh.ttc", "malgun.ttf", "arial.ttf"]:
        try:
            # Check if font can be loaded
            ImageFont.truetype(f, 40)
            font_path = f
            break
        except Exception:
            continue
            
    if font_path is None:
        print("Could not find a valid CJK font. Text might not render correctly.")
        font = ImageFont.load_default()
    else:
        font = ImageFont.truetype(font_path, 40)

    # List of Japanese words to draw
    words = ["こんにちは", "猫", "ありがとう", "さようなら", "本", "水", "空", "太陽", "月"]
    
    placed_boxes = []
    
    for word in words:
        # Try finding a non-overlapping position
        for _ in range(50):
            if hasattr(font, 'getbbox'):
                bbox = font.getbbox(word)
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
            else:
                w, h = font.getsize(word)
                
            x = random.randint(50, size[0] - w - 50)
            y = random.randint(50, size[1] - h - 50)
            
            # Check overlap
            overlap = False
            for (px, py, pw, ph) in placed_boxes:
                if not (x + w < px or x > px + pw or y + h < py or y > py + ph):
                    overlap = True
                    break
                    
            if not overlap:
                placed_boxes.append((x, y, w, h))
                draw.text((x, y), word, fill="black", font=font)
                break

    # Save the test image
    os.makedirs("source", exist_ok=True)
    test_img_path = os.path.join("source", "test_japanese_image.png")
    img.save(test_img_path)
    print(f"Created test image at: {test_img_path}")
    return img

def main():
    print("Initializing OCR...")
    ocr.initialize_ocr()
    
    print("\nCreating test image...")
    img = create_test_image()
    
    print("\nExtracting text from image (Source: Japanese)...")
    extracted_data = ocr.extract_text(img, "ja")
    
    print(f"Extracted {len(extracted_data)} regions:")
    for d in extracted_data:
        try:
            print(f" - [{d['id']}] {d['text']}")
        except UnicodeEncodeError:
            print(f" - [{d['id']}] <non-ascii text>")
        
    print("\nTranslating with Ollama...")
    translated_data = translator.translate_texts(
        extracted_data=extracted_data,
        target_language="en",
        ollama_url="http://localhost:11434/api/chat",
        ollama_model="aya-expanse:8b",
        batch_size=10
    )
    
    print("\nTranslation Results:")
    final_data = []
    for item in translated_data:
        try:
            print(f" - [{item['id']}] {item['text']}")
        except UnicodeEncodeError:
            print(f" - [{item['id']}] <non-ascii text>")
        # Same check as main.py
        # Need to find the original text to compare
        orig_text = next((x['text'] for x in extracted_data if x['id'] == item['id']), "")
        
        orig_clean = "".join(orig_text.split()).lower()
        trans_clean = "".join(item["text"].split()).lower()
        
        if orig_clean != trans_clean:
            final_data.append(item)
            
    print(f"\nRegions to overlay: {len(final_data)}")
            
    if not final_data:
        print("Nothing to overlay.")
        return
        
    print("\nCreating overlay...")
    filepath = overlay.create_overlay(img, final_data)
    print(f"Done! Saved overlay image to {filepath} and opened it.")

if __name__ == "__main__":
    main()

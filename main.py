import threading
import keyboard
import time
import sys
import os
import ctypes
from datetime import datetime

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per monitor aware
except (AttributeError, OSError):
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass

import config
import ocr
import capture
import translator
import overlay
import gui

# Seconds to wait for the settings window to finish hiding before capture.
# The hide is scheduled asynchronously on the Tk main loop, so we give it a beat.
GUI_HIDE_DELAY = 0.4

# A non-blocking lock gates the pipeline: two near-simultaneous triggers (e.g.
# mashing the recapture hotkey) can't kick off concurrent captures.
_translation_lock = threading.Lock()

def do_translation(custom_area):
    if not _translation_lock.acquire(blocking=False):
        return  # a translation is already in progress
    print("\nStarting translation process...")
    try:
        cfg = config.load_config()

        # 1. Capture screen
        gui.hide_gui()
        time.sleep(GUI_HIDE_DELAY)  # wait for the GUI to finish hiding
        print(f"Capturing custom area: {custom_area}")
        try:
            img = capture.capture_screen("Custom Area", custom_area)
        finally:
            gui.restore_gui()
        
        # Save source image for verification
        source_dir = os.path.join(config.BASE_DIR, "source")
        os.makedirs(source_dir, exist_ok=True)
        src_filename = datetime.now().strftime("source_%Y-%m-%d_%H-%M-%S.png")
        src_filepath = os.path.join(source_dir, src_filename)
        img.save(src_filepath)
        print(f"Saved source capture to {src_filepath}")
        if cfg.get("open_source_image", False):
            try:
                os.startfile(src_filepath)
            except OSError:
                pass
        
        # Show captured image in preview panel immediately
        gui.update_preview(src_filepath, None)
        
        # 2. Extract text and bboxes
        ocr_engine = cfg.get("ocr_engine", "EasyOCR")
        use_multi_ocr = cfg.get("multi_ocr", True)
        print(f"Extracting text (engine: {ocr_engine}, multi-OCR: {use_multi_ocr}, source language: {cfg.get('source_language', 'auto')})...")
        if use_multi_ocr:
            extracted_data = ocr.extract_text_multi(img, cfg.get("source_language", "auto"), engine=ocr_engine)
        else:
            extracted_data = ocr.extract_text(img, cfg.get("source_language", "auto"), engine=ocr_engine)
        print(f"Found {len(extracted_data)} text regions:")
        for d in extracted_data:
            try:
                print(f" - [{d['id']}] {d['text']}")
            except UnicodeEncodeError:
                print(f" - [{d['id']}] <non-ascii text>")
        
        if not extracted_data:
            print("No text found.")
            return
            
        if cfg.get("filter_alphabet_only", True):
            print("Filtering out alphabet-only text...")
            filtered_data = []
            for d in extracted_data:
                # isascii() returns True if string is empty or all characters are ASCII
                # We filter it out if it's purely ascii (English letters, numbers, punctuation)
                # because we assume the user only wants to translate CJK text
                if not d["text"].strip().isascii():
                    filtered_data.append(d)
                else:
                    print(f" - Filtered out: [{d['id']}] {d['text']}")
            extracted_data = filtered_data
            print(f"Remaining regions after filtering: {len(extracted_data)}")
            
        if not extracted_data:
            print("No non-alphabet text found after filtering.")
            return
            
        # 3. Translate
        print("Translating with Ollama...")
        translated_data = translator.translate_texts(
            extracted_data, 
            cfg["target_language"], 
            cfg["ollama_url"], 
            cfg["ollama_model"], 
            cfg.get("batch_size", 10)
        )
        
        print(f"Translated {len(translated_data)} regions that require rendering:")
        for d in translated_data:
            print(f"[{d['id']}] {d['text']}")
            
        if not translated_data:
            print("No text required translation (or OCR/Translation failed).")
            return
        
        # 4. Create overlay and open
        print("Creating overlay...")
        filepath = overlay.create_overlay(img, translated_data, font_name=cfg.get("font_name"))
        print(f"Done! Saved to {filepath}")
        
        # Update preview with both original + processed overlay
        gui.update_preview(src_filepath, filepath)
        
    except Exception as e:
        print(f"An error occurred: {e}")
        try:
            gui.show_warning("Translation failed", f"{type(e).__name__}: {e}")
        except Exception:
            pass
    finally:
        _translation_lock.release()

def on_area_selected(area):
    if area:
        # Save the captured area coordinates to config.json for persistence
        try:
            cfg = config.load_config()
            cfg["custom_area"] = area
            config.save_config(cfg)
            print(f"Saved custom area coordinates to config: {area}")
        except Exception as e:
            print(f"Error saving custom area to config: {e}")
            
        # Run translation in a separate thread so it doesn't block the GUI
        threading.Thread(target=do_translation, args=(area,), daemon=True).start()

def on_recapture():
    print("Recapture hotkey/button triggered! Recapturing previous area...")
    cfg = config.load_config()
    area = cfg.get("custom_area")
    
    # Validate the custom_area structure
    if area and isinstance(area, (list, tuple)) and len(area) == 4 and area[2] > 10 and area[3] > 10:
        threading.Thread(target=do_translation, args=(area,), daemon=True).start()
    else:
        msg = "No previous area coordinates found to recapture. Please select an area first using the main hotkey."
        print(msg)
        gui.show_warning("No Previous Area", msg)

def on_hotkey():
    print("Hotkey pressed! Select area to translate...")
    gui.trigger_capture(on_area_selected)

def setup_hotkey(cfg):
    keyboard.unhook_all()
    
    # 1. Main area selection hotkey
    hotkey = cfg.get("hotkey", "ctrl+alt+t")
    print(f"Registering main hotkey: {hotkey}")
    try:
        keyboard.add_hotkey(hotkey, on_hotkey)
    except Exception as e:
        print(f"Failed to register hotkey {hotkey}: {e}")
        
    # 2. Recapture hotkey
    recapture_hotkey = cfg.get("recapture_hotkey", "ctrl+alt+r")
    print(f"Registering recapture hotkey: {recapture_hotkey}")
    try:
        keyboard.add_hotkey(recapture_hotkey, on_recapture)
    except Exception as e:
        print(f"Failed to register recapture hotkey {recapture_hotkey}: {e}")

def on_config_saved(new_cfg):
    setup_hotkey(new_cfg)

def main():
    print("Starting ScreenTranslator...")
    
    # Load config and setup hotkey
    cfg = config.load_config()
    
    # Initialize OCR models for the selected engine
    ocr.initialize_ocr(cfg.get("ocr_engine", "EasyOCR"))
    setup_hotkey(cfg)
    
    print("Showing GUI... Close the GUI to exit the application.")
    # Show settings GUI with callbacks
    gui.show_gui(on_save_callback=on_config_saved, on_recapture_callback=on_recapture, on_capture_callback=on_hotkey)
    
    # When GUI is closed, unhook and exit
    keyboard.unhook_all()
    print("Exiting.")
    sys.exit(0)

if __name__ == "__main__":
    main()

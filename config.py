import json
import os

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "hotkey": "ctrl+alt+t",
    "recapture_hotkey": "ctrl+alt+r",
    "capture_mode": "Custom Area",
    "custom_area": [0, 0, 800, 600],  # x, y, width, height
    "source_language": "ja",
    "target_language": "en",
    "ocr_engine": "EasyOCR",
    "font_name": "Wild Words",
    "filter_alphabet_only": True,
    "open_source_image": False,
    "ollama_url": "http://localhost:11434/api/chat",
    "ollama_model": "aya-expanse:8b",
    "batch_size": 10
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            # Merge with defaults to ensure all keys exist
            needs_save = False
            for k, v in DEFAULT_CONFIG.items():
                if k not in config:
                    config[k] = v
                    needs_save = True
            
            if needs_save:
                save_config(config)
                
            return config
    except Exception as e:
        print(f"Error loading config: {e}")
        return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

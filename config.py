import json
import os
import time

# Anchor the config to the source directory so the app reads/writes the SAME
# file regardless of the working directory it was launched from (Start Menu
# shortcut, scheduled task, etc. inherit different CWDs).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

# Single authoritative schema. Every key any consumer reads or writes must be
# declared here so load_config can seed and type-repair it.
DEFAULT_CONFIG = {
    "hotkey": "ctrl+alt+t",
    "recapture_hotkey": "ctrl+alt+r",
    "capture_mode": "Custom Area",
    "custom_area": [0, 0, 800, 600],  # x, y, width, height
    "source_language": "ja",
    "target_language": "en",
    "ocr_engine": "WindowsOCR",
    "font_name": "Arial",
    "filter_alphabet_only": True,
    "multi_ocr": True,
    "open_source_image": False,
    "ollama_url": "http://localhost:11434/api/chat",
    "ollama_model": "aya-expanse:8b",
    "batch_size": 10,
    "window_geometry": "920x620",
}


def load_config():
    """Load config.json, merging/repairing it against DEFAULT_CONFIG.

    Missing keys are seeded, empty strings are restored to their defaults, and
    values whose type drifted from the default are repaired. A corrupt file is
    preserved (renamed aside) rather than silently overwritten, so the user can
    recover it.
    """
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError, ValueError) as e:
        # Don't destroy a corrupt file — move it aside so it can be recovered.
        backup = f"{CONFIG_FILE}.bad-{time.strftime('%Y%m%d-%H%M%S')}"
        try:
            os.replace(CONFIG_FILE, backup)
            print(f"Config unreadable ({e}); preserved as {backup}, using defaults.")
        except OSError:
            print(f"Config unreadable ({e}); using defaults.")
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    if not isinstance(config, dict):
        config = {}

    needs_save = False
    for k, default in DEFAULT_CONFIG.items():
        if k not in config:
            config[k] = default
            needs_save = True
            continue
        v = config[k]
        # Empty string almost always means a stale auto-save of an unpopulated
        # field; restore the (non-empty) default.
        if isinstance(default, str) and default != "" and v == "":
            config[k] = default
            needs_save = True
        # Type drift (e.g. batch_size saved as "10" or null) -> repair to default.
        elif not _type_compatible(v, default):
            config[k] = default
            needs_save = True

    # batch_size must be a positive int.
    if not isinstance(config.get("batch_size"), int) or config["batch_size"] <= 0:
        config["batch_size"] = DEFAULT_CONFIG["batch_size"]
        needs_save = True

    if needs_save:
        save_config(config)

    return config


def _type_compatible(value, default):
    """True if `value` is an acceptable type for the slot defined by `default`.

    bool is treated separately from int (bool is a subclass of int in Python),
    and int/float are interchangeable for numeric slots.
    """
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, (int, float)):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, type(default))


def save_config(config):
    """Atomically persist config to disk. Returns True on success, False on failure.

    Writes to a temp file in the same directory, fsyncs, then os.replace()s it
    over the target — so a crash mid-write can never leave a truncated/corrupt
    config.json.
    """
    tmp = f"{CONFIG_FILE}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, CONFIG_FILE)
        return True
    except OSError as e:
        print(f"Error saving config: {e}")
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        return False

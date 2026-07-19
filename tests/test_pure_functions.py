"""Regression tests for the pure (no-I/O, no-GUI) logic.

Runs with pytest if installed, otherwise standalone:
    python tests/test_pure_functions.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import translator
import overlay


# ── translator.normalize_ollama_url ──────────────────────────────────────
def test_normalize_ollama_url_appends_chat_endpoint():
    f = translator._normalize_ollama_url
    assert f("http://localhost:11434") == "http://localhost:11434/api/chat"
    assert f("http://localhost:11434/") == "http://localhost:11434/api/chat"
    assert f("http://localhost:11434/api/chat") == "http://localhost:11434/api/chat"
    assert f("  http://host:11434  ") == "http://host:11434/api/chat"
    assert f("") == ""


# ── translator.rgb_to_hex ─────────────────────────────────────────────────
def test_rgb_to_hex():
    assert translator.rgb_to_hex([60, 66, 75]) == "#3C424B"
    assert translator.rgb_to_hex([0, 0, 0]) == "#000000"
    assert translator.rgb_to_hex(None) == "#FFFFFF"     # defensive default
    assert translator.rgb_to_hex([1, 2]) == "#FFFFFF"   # too short


# ── overlay._has_cjk / hex_to_rgb ─────────────────────────────────────────
def test_has_cjk():
    assert overlay._has_cjk("声いいね")
    assert overlay._has_cjk("mixed 声 text")
    assert not overlay._has_cjk("Hello world")
    assert not overlay._has_cjk("")


def test_hex_to_rgb_robust():
    assert overlay.hex_to_rgb("#3C424B") == (60, 66, 75)
    assert overlay.hex_to_rgb("3C424B") == (60, 66, 75)
    assert overlay.hex_to_rgb("bad") == (255, 255, 255)  # malformed -> white


# ── overlay.wrap_text hard-break ──────────────────────────────────────────
def test_wrap_text_hard_breaks_long_tokens():
    font = overlay.get_font(24, "Arial")
    # A space-less token far wider than the box must be broken, not dropped.
    lines = overlay.wrap_text("A" * 200, font, 120)
    assert len(lines) > 1
    assert "".join(lines) == "A" * 200            # nothing lost
    for ln in lines:
        assert overlay.get_text_advance(ln, font) <= 122  # each line fits


def test_wrap_text_cjk_no_overflow():
    font = overlay.get_font_for_text("これは長い日本語", 28, "Arial")
    text = "これはとても長い日本語のテキストです" * 2
    lines = overlay.wrap_text(text, font, 200)
    assert lines
    for ln in lines:
        assert overlay.get_text_advance(ln, font) <= 205


def test_wrap_text_empty_and_degenerate():
    font = overlay.get_font(24, "Arial")
    assert overlay.wrap_text("", font, 100) == []
    assert overlay.wrap_text("hi", font, 0) == ["hi"]   # no width -> don't drop


# ── overlay.get_font_for_text coverage routing ────────────────────────────
def test_font_routing_covers_all_glyphs():
    cases = ["Hello world", "1 ℃ 1:15", "Sea ☆ ※ ◆", "声いいね", "Mix 声 ☆ x"]
    for t in cases:
        f = overlay.get_font_for_text(t, 24, "Arial")
        assert overlay._covers(f, t) is True, f"font fails to cover: {t!r}"


# ── config load / merge / repair / atomicity ──────────────────────────────
def _with_temp_config(fn):
    """Run fn() with config pointed at a throwaway file; restore afterward."""
    orig = config.CONFIG_FILE
    d = tempfile.mkdtemp()
    config.CONFIG_FILE = os.path.join(d, "config.json")
    try:
        fn()
    finally:
        config.CONFIG_FILE = orig


def test_config_seeds_defaults_when_missing():
    def body():
        c = config.load_config()
        for k in config.DEFAULT_CONFIG:
            assert k in c
        assert c["ollama_url"] == config.DEFAULT_CONFIG["ollama_url"]
    _with_temp_config(body)


def test_config_coerces_empty_and_repairs_types():
    def body():
        bad = dict(config.DEFAULT_CONFIG)
        bad["ollama_url"] = ""        # empty string -> default
        bad["batch_size"] = "10"      # wrong type -> default
        bad["multi_ocr"] = "yes"      # wrong type -> default
        config.save_config(bad)
        c = config.load_config()
        assert c["ollama_url"] == config.DEFAULT_CONFIG["ollama_url"]
        assert isinstance(c["batch_size"], int) and c["batch_size"] > 0
        assert isinstance(c["multi_ocr"], bool)
    _with_temp_config(body)


def test_config_atomic_save_roundtrip():
    def body():
        c = dict(config.DEFAULT_CONFIG)
        c["ollama_model"] = "aya-expanse:32b"
        assert config.save_config(c) is True
        assert config.load_config()["ollama_model"] == "aya-expanse:32b"
        # no leftover temp file
        assert not os.path.exists(config.CONFIG_FILE + ".tmp")
    _with_temp_config(body)


def test_config_corrupt_file_preserved_not_wiped():
    def body():
        with open(config.CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write("{ this is not valid json ")
        c = config.load_config()
        assert c["ollama_url"] == config.DEFAULT_CONFIG["ollama_url"]  # recovered
        d = os.path.dirname(config.CONFIG_FILE)
        assert any(n.startswith("config.json.bad-") for n in os.listdir(d))
    _with_temp_config(body)


# ── standalone runner (no pytest required) ────────────────────────────────
def _run_standalone():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_standalone())

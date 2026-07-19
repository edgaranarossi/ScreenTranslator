# ScreenTranslator

**2026-07-19:** Working Windows desktop tool (capture → OCR → local-Ollama translate → overlay). Last commit 2026-05-21; a substantial batch of uncommitted improvements from 2026-06-26 (config self-repair + atomic saves, GUI/preview rework, overlay fixes, torch/winocr import-order fix, Ollama URL normalization, `tests/` suite, requirements cleanup) sits in the working tree awaiting commit. Doc set backfilled today per the projects constitution — see `PLAN.md` / `DECISIONS.md`.

A local Windows desktop translation tool that overlays translated text onto your screen. Powered by local Ollama Large Language Models and OCR engines. Fully offline-capable: no cloud APIs, no accounts, no keys.

---

## Features

* **Dark Mode Settings GUI:** A settings window designed with visual panels, hover effects, and dark-mode compatible dropdowns, with an interactive wipe-comparison preview panel (original vs. translated).
* **Overlay Inpainting:** Blends background textures using OpenCV's inpainting (`cv2.inpaint`) to erase the original foreign text before rendering the new text.
* **Context-Aware Translation:** Batches text regions into a single request sent to a local Ollama instance, allowing the LLM to use the full surrounding context for translation and OCR correction.
* **Multiple OCR engines + consensus:** Windows Media OCR (winocr), EasyOCR, PaddleOCR, and MangaOCR, with an optional multi-OCR consensus mode that merges proposals from several engines.
* **Visual Sizing Hierarchy:** Groups bounding boxes by size categories (Header, Subheading, and Body) so that dense paragraphs scale down without shrinking your headers.
* **Persistent Coordinates & Recapture:** Remembers your captured region in `config.json`. Press `ctrl+alt+t` to draw a new region, or `ctrl+alt+r` (or click a GUI button) to instantly recapture the previous one.
* **Outline Strokes & rotated text:** Draws translated text with high-contrast outlines scaled to the font size, supports rotated text regions and per-word font color.

## Repository layout

| Path | What it is |
|---|---|
| `main.py` | Entry point: hotkeys, pipeline orchestration (capture → OCR → translate → overlay) |
| `capture.py` | Screen capture via `mss` (monitors / custom area) |
| `ocr.py` | OCR engines (winocr / EasyOCR / PaddleOCR / MangaOCR) + multi-OCR consensus |
| `translator.py` | Ollama chat-API client, batching, text-block merging, color grouping |
| `overlay.py` | Inpainting, font selection/wrapping, rendering the translated overlay |
| `gui.py` | Tkinter settings window + preview panel |
| `config.py` | `config.json` schema, load/repair, atomic save |
| `tests/` | Pure-function regression tests (pytest or standalone) |
| `test_translation.py` | End-to-end smoke script (generates a synthetic Japanese image, runs the full pipeline; needs Ollama running) |
| `source/`, `translated/` | Generated capture/output images (gitignored) |

---

## Installation & Setup

### 1. Prerequisites
Ensure you have **Python 3.10+** (Conda recommended) and **Ollama** running locally.

### 2. Set Up the Environment
Create and activate your Conda environment:
```bash
# Create environment
conda create -n translator python=3.10 -y

# Activate environment
conda activate translator
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```
> The last three entries (paddlepaddle / paddleocr / manga-ocr) are optional extra OCR engines with large installs — trim them if you only use winocr/EasyOCR.

### 4. Running the Application
```bash
python main.py
```
> **Note:** The first time you run this, your selected OCR engine (e.g., MangaOCR) will automatically download its base weights (~450MB).

### Running the tests
```bash
python tests/test_pure_functions.py   # standalone, no pytest needed
# or: pytest tests/
```

---

## How to Use

1. **Configure:** Open the settings window, select your **languages**, **OCR engine**, **font**, and your local **Ollama URL & Model**. Click **Save Settings**.
2. **Select & Translate (`ctrl+alt+t`):** Press the hotkey and drag a box over any Japanese, Chinese, or Korean text on your screen.
3. **Instant Recapture (`ctrl+alt+r`):** Press the recapture hotkey (or click `"Recapture Previous"` in the GUI) to immediately translate the exact same area again.
4. **View:** The captured and translated images appear in the GUI preview panel (wipe slider to compare); an **Open** button launches the result in your default image viewer.

---

## License
This project is licensed under the [MIT License](LICENSE).

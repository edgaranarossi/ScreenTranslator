# 🔍 ScreenTranslator

A local Windows desktop translation tool that overlays translated text onto your screen. Powered by local Ollama Large Language Models and OCR engines.

---

## ✨ Features

* 🎨 **Dark Mode Settings GUI:** A settings window designed with visual panels, hover effects, and dark-mode compatible dropdowns.
* 🔮 **Overlay Inpainting:** Blends background textures using OpenCV's inpainting (`cv2.inpaint`) to erase the original foreign text before rendering the new text.
* 🧠 **Context-Aware Translation:** Batches text regions into a single request sent to a local Ollama instance, allowing the LLM to use the full surrounding context for translation and OCR correction.
* 📐 **Visual Sizing Hierarchy:** Groups bounding boxes by size categories (Header, Subheading, and Body) so that dense paragraphs scale down without shrinking your headers.
* ⚡ **Persistent Coordinates & Recapture:** Remembers your captured region in `config.json`. Press `ctrl+alt+t` to draw a new region, or `ctrl+alt+r` (or click a GUI button) to instantly recapture the previous one.
* 💬 **Outline Strokes:** Draws translated text with high-contrast outlines (e.g. white text with a black stroke) scaled to the font size to ensure legibility on busy backgrounds.

---

## 🛠️ Installation & Setup

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

### 4. Running the Application
```bash
python main.py
```
> **Note:** The first time you run this, your selected OCR engine (e.g., MangaOCR) will automatically download its base weights (~450MB).

---

## 🚀 How to Use

1. **Configure:** Open the settings window, select your **languages**, **OCR engine**, **font**, and your local **Ollama URL & Model**. Click **Save Settings**.
2. **Select & Translate (`ctrl+alt+t`):** Press the hotkey and drag a box over any Japanese, Chinese, or Korean text on your screen.
3. **Instant Recapture (`ctrl+alt+r`):** Press the recapture hotkey (or click `"Recapture Previous"` in the GUI) to immediately translate the exact same area again.
4. **View:** The translated image will open automatically in your default Windows image viewer.

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).

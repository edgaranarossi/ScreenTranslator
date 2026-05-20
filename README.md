# 🔍 ScreenTranslator

A state-of-the-art, local Windows desktop translation tool that brings **Google Lens-style image translation** directly to your desktop. Powered by local Ollama Large Language Models and GPU-accelerated OCR engines.

---

## ✨ Key Features

* 🎨 **Obsidian Dark Mode Settings GUI:** A beautifully customized system-tray-compatible GUI designed with flat visual cards, dynamic hover micro-animations, and styled dark-mode dropdowns.
* 🔮 **Google Lens-Style Inpainting:** Erases foreign characters organically using OpenCV's **Fast Marching Inpainting** (`cv2.inpaint`), blending underlying artwork textures and gradients instead of using blocky colored rectangles.
* 🧠 **Context-Aware Local LLM Translation:** Groups and batches OCR detections into a single JSON context array sent to your local Ollama instance (DeepSeek-R1, Aya-Expanse, etc.). The LLM reviews the entire image's sentences to fix OCR typos and perform highly contextual CJK translations.
* 📐 **Hierarchical Typography Bucketing:** Automatically clusters text bounding boxes into Large (Heading), Medium (Subheading), and Small (Body) categories, ensuring large headings remain dominant and compact body paragraphs never shrink your titles.
* ⚡ **Persistent Bounding Box & Recapture:** Instantly capture regions with `ctrl+alt+t` (using a high-tech indigo bounding selector canvas). Bounding coordinates are saved persistently to `config.json`, letting you recapture the exact same spot instantly with `ctrl+alt+r` or a GUI button.
* 💬 **Dynamic High-Contrast Outline Strokes:** Overlay text is rendered with contrasting stroke borders (e.g. bold white letters with a solid black outline) that scale dynamically (`1px` to `3px`) based on font size to guarantee **100% legibility** on busy or multi-colored frames.

---

## 🛠️ Installation & Setup

### 1. Prerequisites
Ensure you have **Python 3.10+** (Conda recommended) and a local instance of **Ollama** running.

### 2. Set Up the Environment
Create and activate a isolated Conda environment:
```bash
# Create environment
conda create -n translator python=3.10 -y

# Activate environment
conda activate translator
```

### 3. Install Dependencies
Install the required OCR, Image manipulation, and hotkey libraries:
```bash
pip install -r requirements.txt
```

### 4. Running the Application
Launch the main setup and configuration GUI:
```bash
python main.py
```
> **Note:** On your very first run, the selected OCR engine (e.g., MangaOCR) will take a moment to download its base weights (~450MB) and configure itself for CUDA/CPU acceleration automatically.

---

## 🚀 How to Use

1. **Configure:** Open the obsidian GUI, choose your **Source/Target languages**, select your favorite **OCR Engine** (MangaOCR, PaddleOCR, or EasyOCR), specify your desired **Overlay Font**, and key in your local **Ollama URL & Model** (e.g. `deepseek-r1:14b`). Click **Save Settings**.
2. **Select & Translate (`ctrl+alt+t`):** Press your main hotkey anywhere on your screen. The screen will dim slightly with a crosshair. Drag to select any Japanese, Chinese, or Korean text on your screen. 
3. **Instant Recapture (`ctrl+alt+r`):** Click the `"Recapture Previous"` button or press the recapture shortcut to translate the exact same area again instantly—the settings window will automatically flash-hide, snap the screen, and restore itself!
4. **Enjoy:** The translation will render onto your screen's background canvas and open automatically in your default Windows image viewer.

---

## ⚙️ Configuration Schema (`config.json`)
The application auto-merges defaults and updates dynamically:
```json
{
    "hotkey": "ctrl+alt+t",
    "recapture_hotkey": "ctrl+alt+r",
    "capture_mode": "Custom Area",
    "custom_area": [237.0, -966.0, 1593.0, 899.0],
    "source_language": "ja",
    "target_language": "en",
    "ocr_engine": "MangaOCR",
    "font_name": "CC Wild Words Roman",
    "ollama_url": "http://localhost:11434/api/chat",
    "ollama_model": "deepseek-r1:14b",
    "batch_size": 10,
    "filter_alphabet_only": true,
    "open_source_image": false
}
```

---

## 📄 License
This project is open-source and licensed under the [MIT License](LICENSE).

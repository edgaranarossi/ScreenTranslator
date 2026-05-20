import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import config
import capture
import mss
import ctypes
import requests
from urllib.parse import urlparse

_app_instance = None

class CustomAreaSelector(tk.Toplevel):
    def __init__(self, parent, callback):
        # Hide settings GUI immediately to make the screen underneath visible
        if parent:
            parent.withdraw()
            
        super().__init__(parent)
        self.callback = callback
        
        self.attributes("-alpha", 0.3)
        self.attributes("-topmost", True)
        self.overrideredirect(True)
        self.configure(cursor="cross")
        
        self.canvas = tk.Canvas(self, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.start_x = None
        self.start_y = None
        self.rect = None
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Escape>", self.on_escape)
        
        with mss.mss() as sct:
            self.monitor = sct.monitors[0]
            self.geometry(f"{self.monitor['width']}x{self.monitor['height']}+0+0")
            
        self.after(10, self._set_position)
        
    def _set_position(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            ctypes.windll.user32.SetWindowPos(hwnd, 0, self.monitor['left'], self.monitor['top'], self.monitor['width'], self.monitor['height'], 0x0040)
        except Exception as e:
            print(f"Window pos error: {e}")
            
    def on_press(self, event):
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        # Indigo outline border (#6366f1) for a modern, sleek capture selection
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='#6366f1', width=3, fill="white")

    def on_drag(self, event):
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_escape(self, event):
        self.destroy()
        if self.master:
            self.master.deiconify()

    def on_release(self, event):
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)
        
        x = min(self.start_x, end_x) + self.monitor['left']
        y = min(self.start_y, end_y) + self.monitor['top']
        w = abs(end_x - self.start_x)
        h = abs(end_y - self.start_y)
        
        self.destroy()
        if w > 10 and h > 10:
            self.callback([x, y, w, h])
        else:
            if self.master:
                self.master.deiconify()

# Custom modern styling color constants
BG_MAIN = "#09090b"        # Deep rich zinc background
BG_CARD = "#18181b"        # Card panels background
BG_INPUT = "#27272a"       # Fields / Entries background
BORDER_COLOR = "#27272a"   # Subtle card outline
TEXT_MAIN = "#f4f4f5"      # High contrast white
TEXT_MUTED = "#a1a1aa"     # Description and label gray
ACCENT_COLOR = "#6366f1"   # Vibrant indigo highlight
ACCENT_HOVER = "#4f46e5"   # Hover state indigo
FONT_FAMILY = "Segoe UI"   # Sleek modern system font

def get_local_ollama_models(ollama_chat_url):
    """
    Queries the local Ollama tags API and falls back to running the 'ollama list' CLI
    to fetch the list of installed models.
    """
    default_models = ["deepseek-r1:14b", "aya-expanse:8b", "llama3.2", "phi3"]
    discovered_models = set()
    
    # 1. Try to query the local REST API
    try:
        parsed = urlparse(ollama_chat_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        tags_url = f"{base_url}/api/tags"
        
        print(f"Fetching local Ollama models from: {tags_url}")
        # Small timeout to prevent hanging the GUI startup if Ollama is offline
        response = requests.get(tags_url, timeout=1.5)
        if response.status_code == 200:
            data = response.json()
            models = data.get("models", [])
            for m in models:
                name = m.get("name")
                if name:
                    discovered_models.add(name)
            if discovered_models:
                print(f"Discovered {len(discovered_models)} models via Ollama API.")
    except Exception as e:
        print(f"Could not connect to Ollama REST API: {e}")
        
    # 2. If REST API didn't return anything or failed, try the CLI command "ollama list"
    if not discovered_models:
        try:
            print("Checking local models via 'ollama list' command...")
            import subprocess
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=2.0)
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1: # first line is header
                    for line in lines[1:]:
                        parts = line.split()
                        if parts:
                            discovered_models.add(parts[0])
                    print(f"Discovered {len(discovered_models)} models via 'ollama list' CLI.")
        except Exception as e:
            print(f"Could not execute 'ollama list' command: {e}")

    if not discovered_models:
        return default_models
        
    return sorted(list(discovered_models))


class SettingsGUI(tk.Tk):
    def __init__(self, on_save_callback=None, on_recapture_callback=None, on_capture_callback=None):
        super().__init__()
        global _app_instance
        _app_instance = self
        
        self.title("ScreenTranslator Settings")
        self.configure(bg=BG_MAIN)
        self.resizable(True, True)
        self.minsize(700, 500)
        
        self.on_save_callback = on_save_callback
        self.on_recapture_callback = on_recapture_callback
        self.on_capture_callback = on_capture_callback
        
        self.cfg = config.load_config()
        
        # Restore saved window geometry or use default
        saved_geom = self.cfg.get("window_geometry", "920x620")
        self.geometry(saved_geom)
        
        # Save geometry on close
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Preview state
        self._orig_pil = None       # Original captured PIL image
        self._proc_pil = None       # Processed overlay PIL image
        self._orig_display = None   # Scaled original for canvas
        self._proc_display = None   # Scaled processed for canvas
        self._orig_tk = None        # ImageTk reference (prevent GC)
        self._proc_tk = None
        self._split_x = 0.5         # Split position as ratio 0..1
        self._dragging = False
        self._last_proc_path = None # Last processed overlay file path
        self._last_src_path = None  # Last source capture file path
        
        self._apply_modern_theme()
        self._create_widgets()
        self._load_values()
        self._draw_placeholder()
    
    def _on_close(self):
        """Save window geometry to config before exiting."""
        try:
            self.cfg["window_geometry"] = self.geometry()
            config.save_config(self.cfg)
        except Exception:
            pass
        self.destroy()
        
    def _apply_modern_theme(self):
        """Configure standard TTK styles to match modern Dark Mode palette."""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Style Frames
        style.configure("TFrame", background=BG_MAIN)
        
        # Style Entries
        style.configure("TEntry", 
                        fieldbackground=BG_INPUT, 
                        background=BG_INPUT, 
                        foreground=TEXT_MAIN, 
                        bordercolor=BG_INPUT, 
                        lightcolor=BG_INPUT, 
                        darkcolor=BG_INPUT, 
                        padding=4,
                        insertcolor="white")
        style.map("TEntry", 
                  bordercolor=[("focus", ACCENT_COLOR)])
                  
        # Style Comboboxes
        style.configure("TCombobox", 
                        fieldbackground=BG_INPUT, 
                        background=BG_INPUT, 
                        foreground=TEXT_MAIN, 
                        bordercolor=BG_INPUT, 
                        lightcolor=BG_INPUT, 
                        darkcolor=BG_INPUT, 
                        arrowcolor=TEXT_MUTED,
                        padding=4)
        style.map("TCombobox", 
                  fieldbackground=[("readonly", BG_INPUT)],
                  foreground=[("readonly", TEXT_MAIN)])
                  
        # Global drop-down list box colors for TCombobox popups
        self.option_add("*TCombobox*Listbox.background", BG_INPUT)
        self.option_add("*TCombobox*Listbox.foreground", TEXT_MAIN)
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT_COLOR)
        self.option_add("*TCombobox*Listbox.selectForeground", TEXT_MAIN)
        self.option_add("*TCombobox*Listbox.font", (FONT_FAMILY, 9))
        self.option_add("*TCombobox*Listbox.relief", "flat")
        self.option_add("*TCombobox*Listbox.borderWidth", "0")

    def _create_widgets(self):
        # ── Master horizontal split container ──
        master = tk.Frame(self, bg=BG_MAIN)
        master.pack(fill="both", expand=True)
        
        # LEFT PANEL: Settings (fixed width)
        left_panel = tk.Frame(master, bg=BG_MAIN, width=400)
        left_panel.pack(side="left", fill="y")
        left_panel.pack_propagate(False)
        
        # RIGHT PANEL: Preview canvas (expandable)
        right_panel = tk.Frame(master, bg=BG_CARD)
        right_panel.pack(side="right", fill="both", expand=True)
        
        self._build_preview_panel(right_panel)
        
        # Outer padding container inside the left panel
        main_frame = ttk.Frame(left_panel, padding="15")
        main_frame.pack(fill="both", expand=True)
        
        # --- HEADER SECTION ---
        header_frame = tk.Frame(main_frame, bg=BG_MAIN)
        header_frame.pack(fill="x", pady=(0, 10))
        
        title_lbl = tk.Label(header_frame, text="SCREEN TRANSLATOR", bg=BG_MAIN, fg=ACCENT_COLOR, font=(FONT_FAMILY, 14, "bold"))
        title_lbl.pack(anchor="w")
        
        sub_lbl = tk.Label(header_frame, text="v2.2 • Local LLM OCR & Translation", bg=BG_MAIN, fg=TEXT_MUTED, font=(FONT_FAMILY, 9))
        sub_lbl.pack(anchor="w", pady=(2, 5))
        
        sep_line = tk.Frame(header_frame, bg=ACCENT_COLOR, height=2)
        sep_line.pack(fill="x", pady=(5, 0))
        
        # --- CARD 1: CAPTURE & HOTKEYS ---
        card1 = tk.Frame(main_frame, bg=BG_CARD, padx=12, pady=10, highlightthickness=1, highlightbackground=BORDER_COLOR)
        card1.pack(fill="x", pady=6)
        
        tk.Label(card1, text="Capture & Hotkeys", bg=BG_CARD, fg=TEXT_MAIN, font=(FONT_FAMILY, 10, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        
        # Main Hotkey
        tk.Label(card1, text="Main Hotkey:", bg=BG_CARD, fg=TEXT_MUTED, font=(FONT_FAMILY, 9)).grid(row=1, column=0, sticky="w", pady=4)
        self.hotkey_var = tk.StringVar()
        self.entry_hotkey = ttk.Entry(card1, textvariable=self.hotkey_var, width=12)
        self.entry_hotkey.grid(row=1, column=1, sticky="ew", pady=4, padx=(0, 6))
        
        self.btn_capture_now = tk.Button(card1, 
                                         text="Capture", 
                                         bg=ACCENT_COLOR, 
                                         fg="white", 
                                         activebackground=ACCENT_HOVER, 
                                         activeforeground="white", 
                                         bd=0, 
                                         relief="flat", 
                                         padx=8, 
                                         pady=2, 
                                         font=(FONT_FAMILY, 8, "bold"), 
                                         cursor="hand2", 
                                         command=self._capture_now)
        self.btn_capture_now.grid(row=1, column=2, sticky="e", pady=4)
        
        # Recapture Hotkey
        tk.Label(card1, text="Recapture Hotkey:", bg=BG_CARD, fg=TEXT_MUTED, font=(FONT_FAMILY, 9)).grid(row=2, column=0, sticky="w", pady=4)
        self.recapture_hotkey_var = tk.StringVar()
        self.entry_rehotkey = ttk.Entry(card1, textvariable=self.recapture_hotkey_var, width=12)
        self.entry_rehotkey.grid(row=2, column=1, sticky="ew", pady=4, padx=(0, 6))
        
        self.btn_recap_now = tk.Button(card1, 
                                       text="Recapture", 
                                       bg="#27272a", 
                                       fg=TEXT_MAIN, 
                                       activebackground="#3f3f46", 
                                       activeforeground=TEXT_MAIN, 
                                       bd=0, 
                                       relief="flat", 
                                       padx=8, 
                                       pady=2, 
                                       font=(FONT_FAMILY, 8, "bold"), 
                                       cursor="hand2", 
                                       command=self._recapture)
        self.btn_recap_now.grid(row=2, column=2, sticky="e", pady=4)
        
        # Checkboxes
        self.filter_var = tk.BooleanVar()
        self.chk_filter = tk.Checkbutton(card1, text="Filter out Alphabet-only text", variable=self.filter_var, 
                                         bg=BG_CARD, fg=TEXT_MAIN, activebackground=BG_CARD, activeforeground=TEXT_MAIN, 
                                         selectcolor=BG_INPUT, bd=0, highlightthickness=0, font=(FONT_FAMILY, 9), cursor="hand2")
        self.chk_filter.grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 2))
        
        self.open_src_var = tk.BooleanVar()
        self.chk_open = tk.Checkbutton(card1, text="Open captured image before translation", variable=self.open_src_var, 
                                       bg=BG_CARD, fg=TEXT_MAIN, activebackground=BG_CARD, activeforeground=TEXT_MAIN, 
                                       selectcolor=BG_INPUT, bd=0, highlightthickness=0, font=(FONT_FAMILY, 9), cursor="hand2")
        self.chk_open.grid(row=4, column=0, columnspan=3, sticky="w", pady=2)
        
        # --- CARD 2: OCR & LANGUAGE SETTINGS ---
        card2 = tk.Frame(main_frame, bg=BG_CARD, padx=12, pady=10, highlightthickness=1, highlightbackground=BORDER_COLOR)
        card2.pack(fill="x", pady=6)
        
        tk.Label(card2, text="OCR & Languages", bg=BG_CARD, fg=TEXT_MAIN, font=(FONT_FAMILY, 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        
        # Source Language
        tk.Label(card2, text="Source Language:", bg=BG_CARD, fg=TEXT_MUTED, font=(FONT_FAMILY, 9)).grid(row=1, column=0, sticky="w", pady=4)
        self.src_lang_var = tk.StringVar()
        self.cmb_src = ttk.Combobox(card2, textvariable=self.src_lang_var, values=["auto", "en", "ja", "zh", "ko"], state="readonly", width=16)
        self.cmb_src.grid(row=1, column=1, sticky="e", pady=4)
        
        # Target Language
        tk.Label(card2, text="Target Language:", bg=BG_CARD, fg=TEXT_MUTED, font=(FONT_FAMILY, 9)).grid(row=2, column=0, sticky="w", pady=4)
        self.tgt_lang_var = tk.StringVar()
        self.cmb_tgt = ttk.Combobox(card2, textvariable=self.tgt_lang_var, values=["en", "ja", "zh", "ko"], state="readonly", width=16)
        self.cmb_tgt.grid(row=2, column=1, sticky="e", pady=4)
        
        # OCR Engine
        tk.Label(card2, text="OCR Engine:", bg=BG_CARD, fg=TEXT_MUTED, font=(FONT_FAMILY, 9)).grid(row=3, column=0, sticky="w", pady=4)
        self.ocr_engine_var = tk.StringVar()
        self.cmb_ocr = ttk.Combobox(card2, textvariable=self.ocr_engine_var, values=["WindowsOCR", "EasyOCR", "PaddleOCR", "MangaOCR"], state="readonly", width=16)
        self.cmb_ocr.grid(row=3, column=1, sticky="e", pady=4)
        
        # Font Name
        tk.Label(card2, text="Overlay Font Family:", bg=BG_CARD, fg=TEXT_MUTED, font=(FONT_FAMILY, 9)).grid(row=4, column=0, sticky="w", pady=4)
        self.font_var = tk.StringVar()
        font_choices = ["Wild Words", "Anime Ace", "CC Wild Words Roman", "Comic Sans MS", "Arial", "Segoe UI", "MS Gothic", "Meiryo"]
        self.cmb_font = ttk.Combobox(card2, textvariable=self.font_var, values=font_choices, width=16)
        self.cmb_font.grid(row=4, column=1, sticky="e", pady=4)
        
        # --- CARD 3: OLLAMA LLM SETTINGS ---
        card3 = tk.Frame(main_frame, bg=BG_CARD, padx=12, pady=10, highlightthickness=1, highlightbackground=BORDER_COLOR)
        card3.pack(fill="x", pady=6)
        
        tk.Label(card3, text="Ollama LLM", bg=BG_CARD, fg=TEXT_MAIN, font=(FONT_FAMILY, 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        
        # Ollama URL
        tk.Label(card3, text="Ollama API URL:", bg=BG_CARD, fg=TEXT_MUTED, font=(FONT_FAMILY, 9)).grid(row=1, column=0, sticky="w", pady=4)
        self.url_var = tk.StringVar()
        self.entry_url = ttk.Entry(card3, textvariable=self.url_var, width=22)
        self.entry_url.grid(row=1, column=1, sticky="e", pady=4)
        
        # Ollama Model (Editable Combobox populated from local Ollama tags list)
        tk.Label(card3, text="Ollama Model:", bg=BG_CARD, fg=TEXT_MUTED, font=(FONT_FAMILY, 9)).grid(row=2, column=0, sticky="w", pady=4)
        self.model_var = tk.StringVar()
        
        # Load local models dynamically
        url = self.cfg.get("ollama_url", "http://localhost:11434/api/chat")
        local_models = get_local_ollama_models(url)
        current_model = self.cfg.get("ollama_model", "aya-expanse:8b")
        if current_model not in local_models:
            local_models.insert(0, current_model)
            
        self.cmb_model = ttk.Combobox(card3, textvariable=self.model_var, values=local_models, width=20)
        self.cmb_model.grid(row=2, column=1, sticky="e", pady=4)
        
        # Batch Size
        tk.Label(card3, text="Batch Size:", bg=BG_CARD, fg=TEXT_MUTED, font=(FONT_FAMILY, 9)).grid(row=3, column=0, sticky="w", pady=4)
        self.batch_var = tk.StringVar()
        self.entry_batch = ttk.Entry(card3, textvariable=self.batch_var, width=22)
        self.entry_batch.grid(row=3, column=1, sticky="e", pady=4)
        
        # Frame column configs
        card1.columnconfigure(1, weight=1)
        card2.columnconfigure(1, weight=1)
        card3.columnconfigure(1, weight=1)
        
        # --- BOTTOM ACTION BUTTONS ---
        btn_frame = tk.Frame(main_frame, bg=BG_MAIN)
        btn_frame.pack(fill="x", side="bottom", pady=(15, 0))
        
        # Recapture button (Sleek dark secondary button)
        self.btn_recap = tk.Button(btn_frame, 
                                   text="Recapture Previous", 
                                   bg="#27272a", 
                                   fg=TEXT_MAIN, 
                                   activebackground="#3f3f46", 
                                   activeforeground=TEXT_MAIN, 
                                   bd=0, 
                                   relief="flat", 
                                   padx=12, 
                                   pady=8, 
                                   font=(FONT_FAMILY, 9, "bold"), 
                                   cursor="hand2", 
                                   command=self._recapture)
        self.btn_recap.pack(side="left", fill="x", expand=True, padx=(0, 6))
        
        # Save Settings button (Vibrant Indigo accent primary button)
        self.btn_save = tk.Button(btn_frame, 
                                  text="Save Settings", 
                                  bg=ACCENT_COLOR, 
                                  fg="white", 
                                  activebackground=ACCENT_HOVER, 
                                  activeforeground="white", 
                                  bd=0, 
                                  relief="flat", 
                                  padx=12, 
                                  pady=8, 
                                  font=(FONT_FAMILY, 9, "bold"), 
                                  cursor="hand2", 
                                  command=self._save)
        self.btn_save.pack(side="right", fill="x", expand=True, padx=(6, 0))
        
        # Bind hover micro-animations
        def bind_hover(btn, normal_bg, hover_bg):
            btn.bind("<Enter>", lambda e: btn.configure(bg=hover_bg))
            btn.bind("<Leave>", lambda e: btn.configure(bg=normal_bg))
            
        bind_hover(self.btn_recap, "#27272a", "#3f3f46")
        bind_hover(self.btn_save, ACCENT_COLOR, ACCENT_HOVER)
        bind_hover(self.btn_capture_now, ACCENT_COLOR, ACCENT_HOVER)
        bind_hover(self.btn_recap_now, "#27272a", "#3f3f46")

    def _load_values(self):
        self.hotkey_var.set(self.cfg.get("hotkey", "ctrl+alt+t"))
        self.recapture_hotkey_var.set(self.cfg.get("recapture_hotkey", "ctrl+alt+r"))
        self.src_lang_var.set(self.cfg.get("source_language", "auto"))
        self.tgt_lang_var.set(self.cfg.get("target_language", "en"))
        self.url_var.set(self.cfg.get("ollama_url", "http://localhost:11434/api/chat"))
        self.model_var.set(self.cfg.get("ollama_model", "aya-expanse:8b"))
        self.batch_var.set(str(self.cfg.get("batch_size", 10)))
        self.ocr_engine_var.set(self.cfg.get("ocr_engine", "EasyOCR"))
        self.font_var.set(self.cfg.get("font_name", "Wild Words"))
        self.filter_var.set(self.cfg.get("filter_alphabet_only", True))
        self.open_src_var.set(self.cfg.get("open_source_image", False))
        
    def _capture_now(self):
        if self.on_capture_callback:
            self.on_capture_callback()

    def _recapture(self):
        if self.on_recapture_callback:
            self.on_recapture_callback()

    def _save(self):
        self.cfg["hotkey"] = self.hotkey_var.get()
        self.cfg["recapture_hotkey"] = self.recapture_hotkey_var.get()
        self.cfg["source_language"] = self.src_lang_var.get()
        self.cfg["target_language"] = self.tgt_lang_var.get()
        self.cfg["ollama_url"] = self.url_var.get()
        self.cfg["ollama_model"] = self.model_var.get()
        self.cfg["ocr_engine"] = self.ocr_engine_var.get()
        self.cfg["font_name"] = self.font_var.get()
        self.cfg["filter_alphabet_only"] = self.filter_var.get()
        self.cfg["open_source_image"] = self.open_src_var.get()
        try:
            self.cfg["batch_size"] = int(self.batch_var.get())
        except ValueError:
            self.cfg["batch_size"] = 10
            
        config.save_config(self.cfg)
        
        # Display custom styled dialog info box
        messagebox.showinfo("Saved", "Settings saved successfully!")
        
        if self.on_save_callback:
            self.on_save_callback(self.cfg)

    # ─── Preview Panel ─────────────────────────────────────────────────
    
    def _build_preview_panel(self, parent):
        """Build the right-side preview canvas with wipe comparison."""
        # Header bar
        hdr = tk.Frame(parent, bg=BG_CARD)
        hdr.pack(fill="x", padx=12, pady=(12, 0))
        tk.Label(hdr, text="Preview", bg=BG_CARD, fg=TEXT_MAIN, font=(FONT_FAMILY, 10, "bold")).pack(side="left")
        self._status_lbl = tk.Label(hdr, text="No capture yet", bg=BG_CARD, fg=TEXT_MUTED, font=(FONT_FAMILY, 8))
        self._status_lbl.pack(side="right", padx=(6, 0))
        
        # Open in Viewer button
        self._btn_open = tk.Button(
            hdr, text="↗ Open", bg="#27272a", fg=TEXT_MUTED,
            activebackground="#3f3f46", activeforeground=TEXT_MAIN,
            bd=0, relief="flat", padx=6, pady=1,
            font=(FONT_FAMILY, 8), cursor="hand2",
            command=self._open_in_viewer, state="disabled"
        )
        self._btn_open.pack(side="right")
        self._btn_open.bind("<Enter>", lambda e: self._btn_open.configure(bg="#3f3f46"))
        self._btn_open.bind("<Leave>", lambda e: self._btn_open.configure(bg="#27272a"))
        
        # Canvas
        self._canvas = tk.Canvas(parent, bg="#111113", highlightthickness=0, cursor="sb_h_double_arrow")
        self._canvas.pack(fill="both", expand=True, padx=12, pady=(8, 12))
        
        # Bindings
        self._canvas.bind("<Motion>", self._on_canvas_motion)
        self._canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self._canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self._canvas.bind("<Configure>", self._on_canvas_resize)
    
    def _open_in_viewer(self):
        """Open the latest processed image in the OS default viewer."""
        import os
        path = self._last_proc_path or self._last_src_path
        if path and os.path.exists(path):
            try:
                os.startfile(path)
            except Exception as e:
                print(f"Error opening image: {e}")
    
    def _draw_placeholder(self):
        """Draw an elegant placeholder when no capture exists."""
        self._canvas.delete("all")
        self._canvas.update_idletasks()
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw < 2 or ch < 2:
            cw, ch = 480, 580
        
        cx, cy = cw // 2, ch // 2
        
        # Dashed border rectangle
        pad = 30
        self._canvas.create_rectangle(
            pad, pad, cw - pad, ch - pad,
            outline="#3f3f46", width=2, dash=(8, 4)
        )
        
        # Icon-like viewfinder crosshair
        sz = 20
        self._canvas.create_line(cx - sz, cy, cx + sz, cy, fill="#52525b", width=2)
        self._canvas.create_line(cx, cy - sz, cx, cy + sz, fill="#52525b", width=2)
        self._canvas.create_oval(cx - sz, cy - sz, cx + sz, cy + sz, outline="#52525b", width=2)
        
        self._canvas.create_text(
            cx, cy + 50,
            text="No Screen Capture Yet",
            fill=TEXT_MUTED, font=(FONT_FAMILY, 11, "bold")
        )
        self._canvas.create_text(
            cx, cy + 75,
            text="Use the Capture button or press your hotkey",
            fill="#52525b", font=(FONT_FAMILY, 9)
        )
    
    def _resize_preview_images(self):
        """Scale both images to fit the current canvas size, preserving aspect ratio."""
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw < 2 or ch < 2:
            return
        
        if self._orig_pil:
            self._orig_display = self._fit_image(self._orig_pil, cw, ch)
            self._orig_tk = ImageTk.PhotoImage(self._orig_display)
        if self._proc_pil:
            self._proc_display = self._fit_image(self._proc_pil, cw, ch)
            self._proc_tk = ImageTk.PhotoImage(self._proc_display)
    
    def _fit_image(self, pil_img, max_w, max_h):
        """Return a copy of pil_img scaled to fit inside max_w x max_h."""
        iw, ih = pil_img.size
        scale = min(max_w / iw, max_h / ih)
        new_w = max(1, int(iw * scale))
        new_h = max(1, int(ih * scale))
        return pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    def _draw_split(self):
        """Draw the wipe comparison on the canvas."""
        self._canvas.delete("all")
        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw < 2 or ch < 2:
            return
        
        # If we only have the original (capture done, processing pending)
        if self._orig_tk and not self._proc_tk:
            # Center the original image
            iw, ih = self._orig_display.size
            ox = (cw - iw) // 2
            oy = (ch - ih) // 2
            self._canvas.create_image(ox, oy, anchor="nw", image=self._orig_tk)
            # Pulsing status text at the bottom
            self._canvas.create_text(
                cw // 2, ch - 16,
                text="⏳ Translating...",
                fill=ACCENT_COLOR, font=(FONT_FAMILY, 9, "bold")
            )
            return
        
        # Full wipe comparison mode
        if not self._orig_tk or not self._proc_tk:
            self._draw_placeholder()
            return
        
        iw, ih = self._orig_display.size
        ox = (cw - iw) // 2
        oy = (ch - ih) // 2
        
        # Split pixel position within the image
        split_px = int(self._split_x * iw)
        split_px = max(0, min(split_px, iw))
        
        # Left side: processed (translated)
        if split_px > 0:
            left_crop = self._proc_display.crop((0, 0, split_px, ih))
            self._left_tk = ImageTk.PhotoImage(left_crop)
            self._canvas.create_image(ox, oy, anchor="nw", image=self._left_tk)
        
        # Right side: original
        if split_px < iw:
            right_crop = self._orig_display.crop((split_px, 0, iw, ih))
            self._right_tk = ImageTk.PhotoImage(right_crop)
            self._canvas.create_image(ox + split_px, oy, anchor="nw", image=self._right_tk)
        
        # Draw the split line
        line_x = ox + split_px
        self._canvas.create_line(
            line_x, oy, line_x, oy + ih,
            fill=ACCENT_COLOR, width=3
        )
        
        # Draw handle circle at center of line
        handle_y = oy + ih // 2
        r = 12
        self._canvas.create_oval(
            line_x - r, handle_y - r, line_x + r, handle_y + r,
            fill=ACCENT_COLOR, outline="white", width=2
        )
        # Arrow hints inside the handle
        self._canvas.create_text(
            line_x, handle_y,
            text="◀▶", fill="white", font=(FONT_FAMILY, 7, "bold")
        )
        
        # Labels
        self._canvas.create_text(
            ox + 8, oy + 8, anchor="nw",
            text="Translated", fill=ACCENT_COLOR, font=(FONT_FAMILY, 8, "bold")
        )
        self._canvas.create_text(
            ox + iw - 8, oy + 8, anchor="ne",
            text="Original", fill=TEXT_MUTED, font=(FONT_FAMILY, 8, "bold")
        )
    
    def _canvas_x_to_split(self, event_x):
        """Convert a canvas x coordinate to a split ratio."""
        if not self._orig_display:
            return 0.5
        cw = self._canvas.winfo_width()
        iw, _ = self._orig_display.size
        ox = (cw - iw) // 2
        rel = (event_x - ox) / iw
        return max(0.0, min(1.0, rel))
    
    def _on_canvas_motion(self, event):
        """Update split on hover when both images are loaded."""
        if self._orig_tk and self._proc_tk and not self._dragging:
            self._split_x = self._canvas_x_to_split(event.x)
            self._draw_split()
    
    def _on_canvas_press(self, event):
        if self._orig_tk and self._proc_tk:
            self._dragging = True
            self._split_x = self._canvas_x_to_split(event.x)
            self._draw_split()
    
    def _on_canvas_drag(self, event):
        if self._dragging and self._orig_tk and self._proc_tk:
            self._split_x = self._canvas_x_to_split(event.x)
            self._draw_split()
    
    def _on_canvas_release(self, event):
        self._dragging = False
    
    def _on_canvas_resize(self, event):
        """Re-scale images and redraw on window resize."""
        if self._orig_pil:
            self._resize_preview_images()
            self._draw_split()
        else:
            self._draw_placeholder()
    
    def set_preview(self, src_path, proc_path):
        """Load preview images. Called from the main thread via after()."""
        try:
            if src_path:
                self._last_src_path = src_path
                self._orig_pil = Image.open(src_path).convert("RGB")
                self._btn_open.configure(state="normal")
            if proc_path:
                self._last_proc_path = proc_path
                self._proc_pil = Image.open(proc_path).convert("RGB")
                self._split_x = 0.5
                self._status_lbl.configure(text="Drag to compare")
            else:
                self._proc_pil = None
                self._proc_display = None
                self._proc_tk = None
                self._status_lbl.configure(text="Processing...")
            
            self._resize_preview_images()
            self._draw_split()
        except Exception as e:
            print(f"Preview load error: {e}")

# --- GLOBAL THREAD-SAFE GUI HELPER PROCEDURES ---

def hide_gui():
    """Hides the settings GUI window safely from the main thread."""
    global _app_instance
    if _app_instance:
        _app_instance.after(0, _app_instance.withdraw)

def restore_gui():
    """Restores the settings GUI window safely from the main thread."""
    global _app_instance
    if _app_instance:
        _app_instance.after(0, _app_instance.deiconify)

def show_warning(title, message):
    """Triggers a graphical warning box securely across thread contexts."""
    global _app_instance
    if _app_instance:
        _app_instance.after(0, lambda: messagebox.showwarning(title, message))
    else:
        print(f"Warning [{title}]: {message}")

def trigger_capture(callback):
    global _app_instance
    if _app_instance:
        _app_instance.after(0, lambda: CustomAreaSelector(_app_instance, callback))

def update_preview(src_path, proc_path=None):
    """Thread-safe: schedule a preview update on the Tk main loop."""
    global _app_instance
    if _app_instance:
        _app_instance.after(0, lambda: _app_instance.set_preview(src_path, proc_path))

def show_gui(on_save_callback=None, on_recapture_callback=None, on_capture_callback=None):
    app = SettingsGUI(on_save_callback, on_recapture_callback, on_capture_callback)
    app.mainloop()

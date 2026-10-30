#!/usr/bin/env python3
"""
AI Metadata Manager (Complete & Fixed)
======================================
Batch metadata + rename + duplicate detection (SQLite DB) + drag & drop + dark mode
+ Validasi 4MP, Auto-Upscale (2x/3x/4x), Suara Notifikasi, Simpan Config, 
+ Auto-Convert JPEG, NLP Keyword Generation (Ollama + Optional NLTK),
+ dan Organize Subfolder untuk portofolio besar.
"""

import os
import re
import csv
import sys
import json
import shutil
import hashlib
import sqlite3
import subprocess
import threading
import warnings
import time
import datetime
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

# ---------- Optional imports ---------- #
try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False

try:
    import wordninja
    HAS_WORDNINJA = True
except Exception:
    HAS_WORDNINJA = False

try:
    import nltk
    from nltk.corpus import wordnet
    HAS_NLTK = True
except ImportError:
    HAS_NLTK = False

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

warnings.filterwarnings("ignore", category=DeprecationWarning)

try:
    import ttkbootstrap as ttkb
    HAS_TTKBOOTSTRAP = True
except ImportError:
    import tkinter.ttk as ttkb
    HAS_TTKBOOTSTRAP = False

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False
    DND_FILES = None

try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# ============================================================ #
#  KONFIG
# ============================================================ #
APP_NAME = "AI Metadata Manager"
SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}

if getattr(sys, 'frozen', False):
    _base_dir = Path(sys._MEIPASS)
else:
    _base_dir = Path(__file__).parent
_nltk_path = _base_dir / "nltk_data"
if _nltk_path.exists() and HAS_NLTK:
    nltk.data.path.insert(0, str(_nltk_path))

ADOBE_CATEGORIES = [
    "— none —", "1 · Animals", "2 · Buildings and Architecture", "3 · Business",
    "4 · Drinks", "5 · The Environment", "6 · States of Mind", "7 · Food",
    "8 · Graphic Resources", "9 · Hobbies and Leisure", "10 · Industry",
    "11 · Landscapes", "12 · Lifestyle", "13 · People", "14 · Plants and Flowers",
    "15 · Culture and Religion", "16 · Science", "17 · Social Issues",
    "18 · Sports", "19 · Technology", "20 · Transport", "21 · Travel",
]

UPSCALER_MODELS = ["realesrgan-x4plus", "realesrgan-x4plus-anime", "realesr-animevideov3"]

TARGET_KEYWORDS = 49

ORGANIZE_MODES = [
    ("None (Flat)", "none"),
    ("Batch of 100 (100, 200, 300...)", "batch_100"),
    ("Batch of 500", "batch_500"),
    ("Batch of 1000", "batch_1000"),
    ("Monthly (YYYY-MM)", "monthly"),
    ("Daily (YYYY-MM-DD)", "daily"),
]

KEYWORD_BLACKLIST = {
    "objects", "subjects", "image", "images", "formats", "styles", "aesthetics",
    "colors", "audience", "visual", "forms", "safe", "diverse", "no", "punctuation",
    "lowercase", "nsfw", "hate", "speech", "drugs", "inappropriate", "good", "bad",
    "example", "output", "format", "rule", "rules", "critical", "strict", "task",
    "generate", "extract", "focus", "include", "must", "only", "word", "words",
    "keyword", "keywords", "single", "comma", "separated", "list", "json", "quote",
    "quotes", "bullet", "points", "numbering", "true", "false", "null", "none",
    "type", "types", "content", "concept", "concepts", "noun", "nouns", "adjective",
    "chickenhearted", "xanthous", "viridity", "orangeness", "unseamed",
    "nestling", "transmitter", "iterate", "restate", "flatbed", "unconditional",
    "pawpaw", "papaia", "ananas", "medallion", "yellowness"
}


# ============================================================ #
#  NLP FUNCTIONS
# ============================================================ #
def get_ollama_models() -> list[str]:
    if not HAS_OLLAMA: return []
    try:
        response = ollama.list()
        models = []
        if isinstance(response, dict) and 'models' in response:
            for m in response['models']:
                name = m.get('name') or m.get('model')
                if name: models.append(name)
        elif hasattr(response, 'models'):
            for m in response.models:
                name = m.model if hasattr(m, 'model') else m.name
                if name: models.append(name)
        return sorted(list(set(models)))
    except Exception: return []

def split_concatenated_word(word: str) -> list[str]:
    if not HAS_WORDNINJA or len(word) < 8: return [word]
    try:
        parts = wordninja.split(word)
        if len(parts) > 1 and all(len(p) >= 3 for p in parts): return parts
    except Exception: pass
    return [word]

def parse_comma_list(raw_text: str) -> list[str]:
    if ":" in raw_text: raw_text = raw_text.split(":", 1)[1]
    raw_text = raw_text.replace("'", "").replace('"', "")
    items = [k.strip() for k in raw_text.split(',') if k.strip()]
    final_keywords = []
    seen = set()
    for item in items:
        item = re.sub(r'(?<!^)(?=[A-Z])', ' ', item)
        item = re.sub(r'[-_/]', ' ', item)
        for w in item.split():
            w = w.strip().lower()
            if w in KEYWORD_BLACKLIST: continue
            for sw in split_concatenated_word(w):
                if len(sw) > 2 and sw not in seen and sw not in KEYWORD_BLACKLIST:
                    final_keywords.append(sw); seen.add(sw)
    return final_keywords

def get_nltk_synonyms(word: str, max_per_word: int = 1) -> list[str]:
    if not HAS_NLTK: return []
    synonyms = set()
    try:
        synsets = wordnet.synsets(word)
        if not synsets: return []
        syn = synsets[0]
        for lemma in syn.lemmas():
            name = lemma.name().replace('_', ' ').lower()
            if ' ' in name or name == word.lower() or not name.isalpha() or len(name) <= 3: continue
            if name not in KEYWORD_BLACKLIST: synonyms.add(name)
    except Exception: pass
    return list(synonyms)[:max_per_word]

def extract_base_keywords(title: str, model_name: str) -> list[str]:
    prompt = (
        f"Image Title: '{title}'\n\n"
        f"Task: Write 20 single-word keywords for this image. Focus on the actual objects, colors, style, mood, and target audience visible in the title.\n\n"
        f"Rules:\n- ONLY one word per keyword.\n- NO compound words like 'happykids'.\n"
        f"- Use lowercase letters.\n- Output ONLY a comma-separated list.\n\nOutput:"
    )
    try:
        r = ollama.chat(model=model_name, messages=[{'role': 'user', 'content': prompt}], options={'think': False, 'num_predict': 250, 'temperature': 0.3})
        return parse_comma_list(r['message']['content'].strip())
    except Exception: return []

def expand_keywords_iteratively(title: str, existing_kws: list[str], model_name: str, 
                                 log_callback=None, target: int = TARGET_KEYWORDS, max_iter: int = 3) -> list[str]:
    all_kws = list(existing_kws)
    for iteration in range(1, max_iter + 1):
        if len(all_kws) >= target: break
        needed = target - len(all_kws)
        request_count = min(needed + 5, 25)
        existing_str = ", ".join(all_kws[-30:])
        prompt = (
            f"Image Title: '{title}'\nExisting Keywords: {existing_str}\n\n"
            f"Task: I need {request_count} more keywords. Find RELATED CONCEPTS.\n"
            f"Rules:\n- ONLY one word per keyword.\n- Do not repeat existing.\n- Output ONLY comma-separated.\n\nOutput:"
        )
        try:
            r = ollama.chat(model=model_name, messages=[{'role': 'user', 'content': prompt}], options={'think': False, 'num_predict': 400, 'temperature': 0.6})
            new_kws = parse_comma_list(r['message']['content'].strip())
            seen = set(k.lower().strip() for k in all_kws)
            added = 0
            for k in new_kws:
                if k.lower() not in seen and k.lower() not in KEYWORD_BLACKLIST:
                    all_kws.append(k); seen.add(k.lower()); added += 1
            msg = f"  → Ollama Iterasi {iteration}: +{added} (total {len(all_kws)})"
            if log_callback: log_callback(msg)
            if added == 0: break
        except Exception as e:
            if log_callback: log_callback(f"Ollama Error: {e}")
            break
    return all_kws[:target]


# ============================================================ #
#  HELPERS
# ============================================================ #
def play_finish_sound(is_error=False):
    if not HAS_WINSOUND: return
    def _play():
        try:
            if is_error:
                for _ in range(4): winsound.Beep(480, 200); time.sleep(0.2)
            else:
                winsound.Beep(440, 600); time.sleep(0.2)
                winsound.Beep(941, 100); time.sleep(0.05)
                winsound.Beep(697, 100); time.sleep(0.05)
                winsound.Beep(852, 100); time.sleep(0.05)
                winsound.Beep(770, 100); time.sleep(0.1)
                winsound.Beep(2100, 150); time.sleep(0.05)
                winsound.Beep(1200, 100); time.sleep(0.05)
                winsound.Beep(2225, 150); time.sleep(0.05)
                for _ in range(4):
                    winsound.Beep(1500, 30); winsound.Beep(1800, 30)
                    winsound.Beep(1100, 30); winsound.Beep(2400, 30)
                    winsound.Beep(1300, 30)
                winsound.Beep(1000, 100); winsound.Beep(1500, 100); winsound.Beep(2000, 300)
        except Exception: pass
    threading.Thread(target=_play, daemon=True).start()

def ensure_icon():
    icon_path = Path(__file__).with_name("icon.ico")
    if icon_path.exists(): return str(icon_path)
    if not HAS_PIL: return None
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([20, 70, 236, 222], radius=28, fill=(41, 98, 200, 255))
    d.rounded_rectangle([86, 42, 156, 92], radius=12, fill=(41, 98, 200, 255))
    d.ellipse([70, 100, 186, 216], fill=(255, 255, 255, 255))
    d.ellipse([96, 126, 160, 190], fill=(41, 98, 200, 255))
    d.ellipse([106, 136, 130, 160], fill=(224, 238, 255, 255))
    d.rounded_rectangle([176, 78, 214, 100], radius=5, fill=(255, 208, 63, 255))
    img.save(icon_path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return str(icon_path)

def format_text(stem, mode):
    if mode == "As-is": return stem
    text = re.sub(r"[_\-]+", " ", stem)
    text = re.sub(r"\s+", " ", text).strip()
    if mode == "Title Case": return text.title()
    if mode == "Sentence case": return text[:1].upper() + text[1:].lower() if text else text
    if mode == "UPPERCASE": return text.upper()
    if mode == "lowercase": return text.lower()
    return stem

def split_keywords(raw):
    seen, out = set(), []
    for k in raw.split(","):
        k = k.strip()
        if k and k.lower() not in seen:
            seen.add(k.lower()); out.append(k)
    return out

def find_images(folder, recursive):
    p = Path(folder)
    it = p.rglob("*") if recursive else p.glob("*")
    return sorted(f for f in it if f.is_file() and f.suffix.lower() in SUPPORTED_EXT)

def get_exiftool_path():
    script_dir = Path(__file__).parent
    for name in ("exiftool.exe", "exiftool"):
        local_exe = script_dir / name
        if local_exe.exists(): return str(local_exe)
    return shutil.which("exiftool")

def check_exiftool():
    exe = get_exiftool_path()
    if not exe: return False, "ExifTool tidak ditemukan."
    exe_path = Path(exe)
    if exe_path.parent == Path(__file__).parent:
        files_dir = exe_path.parent / "exiftool_files"
        if not files_dir.exists() or not files_dir.is_dir():
            return False, "Folder 'exiftool_files' tidak ditemukan."
    return True, ""

def file_hash(path):
    h = hashlib.md5()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(65536), b""): h.update(chunk)
    return h.hexdigest()

def get_next_number(scan_dir, prefix, start):
    if not scan_dir or not Path(scan_dir).exists(): return start
    max_num = start - 1
    for f in Path(scan_dir).rglob("*"):
        if not f.is_file(): continue
        m = re.match(rf"^{re.escape(prefix)}(\d+)$", f.stem)
        if m: max_num = max(max_num, int(m.group(1)))
    return max(max_num + 1, start)

def find_upscaler():
    for name in ("realesrgan-ncnn-vulkan.exe", "realesrgan-ncnn-vulkan", "upscayl-bin.exe", "upscayl-bin"):
        p = shutil.which(name)
        if p: return p
    for p in (r"C:\Program Files\Upscayl\resources\bin\upscayl-bin.exe", r"C:\realesrgan\realesrgan-ncnn-vulkan.exe"):
        if os.path.exists(p): return p
    return None

def get_organize_subfolder(mode: str, file_id: int = None) -> Path:
    if mode == "none": return Path(".")
    if mode.startswith("batch_"):
        chunk = int(mode.split("_")[1])
        if file_id is not None:
            folder_num = ((file_id - 1) // chunk) * chunk + chunk
            return Path(str(folder_num))
        return Path(datetime.datetime.now().strftime("%Y-%m"))
    if mode == "monthly": return Path(datetime.datetime.now().strftime("%Y-%m"))
    if mode == "daily": return Path(datetime.datetime.now().strftime("%Y-%m-%d"))
    return Path(".")


# ============================================================ #
#  BASE WINDOW
# ============================================================ #
if HAS_DND:
    class BaseWindow(TkinterDnD.Tk): pass
else:
    class BaseWindow(tk.Tk): pass


class App(BaseWindow):
    def __init__(self):
        super().__init__()
        if HAS_TTKBOOTSTRAP:
            self.style = ttkb.Style()
            self.style.theme_use("darkly")
            self._current_theme = "darkly"
        else:
            self._current_theme = "default"
        self.title(APP_NAME)
        self.geometry("1280x980")
        self.minsize(1080, 800)
        icon = ensure_icon()
        if icon:
            try: self.iconbitmap(icon)
            except Exception: pass
        self._processing = False
        self._total_files = 0
        self._last_results = []
        self.tree_items = {}
        
        if getattr(sys, 'frozen', False): self.app_dir = Path(sys.executable).parent
        else: self.app_dir = Path(__file__).parent
            
        self.config_file = self.app_dir / "config.json"
        self.db_file = self.app_dir / "riwayat_proses.db"
        self._init_db()
        self._build_ui()
        self._load_config()
        self._refresh_ollama_models()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS history (
                        original_filename TEXT PRIMARY KEY,
                        output_filename TEXT,
                        output_path TEXT,
                        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )""")
                try:
                    cursor.execute("ALTER TABLE history ADD COLUMN output_path TEXT")
                except sqlite3.OperationalError:
                    pass
                conn.commit()
        except Exception as e: print(f"Gagal init DB: {e}")

    def _refresh_ollama_models(self):
        models = get_ollama_models()
        if models:
            self.ollama_combo['values'] = models
            if self.ollama_model_var.get() not in models:
                self.ollama_model_var.set(models[0])
            self._log(f"✅ {len(models)} model Ollama dimuat.")
        else:
            self._log("⚠ Model Ollama tidak ditemukan.")

    def _on_close(self):
        self._save_config(); self.destroy()

    def _load_config(self):
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f: data = json.load(f)
                self.input_var.set(data.get("input_folder", ""))
                self.output_var.set(data.get("output_folder", ""))
                self.ollama_model_var.set(data.get("ollama_model", ""))
                self.organize_mode_var.set(data.get("organize_mode", "batch_100"))
                saved_upscaler = data.get("upscaler_path", "")
                if saved_upscaler and Path(saved_upscaler).exists():
                    self.upscaler_path_var.set(saved_upscaler)
            except Exception as e: print(f"Gagal memuat config: {e}")

    def _save_config(self):
        try:
            data = {
                "input_folder": self.input_var.get().strip(),
                "output_folder": self.output_var.get().strip(),
                "upscaler_path": self.upscaler_path_var.get().strip(),
                "ollama_model": self.ollama_model_var.get().strip(),
                "organize_mode": self.organize_mode_var.get(),
            }
            with open(self.config_file, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)
        except Exception as e: self._log(f"⚠ Gagal simpan config: {e}")

    def _build_ui(self):
        topbar = ttkb.Frame(self, padding=(12, 8)); topbar.pack(fill="x")
        ttkb.Label(topbar, text=APP_NAME, font=("Segoe UI", 14, "bold")).pack(side="left")
        if HAS_TTKBOOTSTRAP:
            ttkb.Button(topbar, text="🌙 Toggle Theme", command=self._toggle_theme, width=15).pack(side="right", padx=4)
        nb = ttkb.Notebook(self); nb.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.main_tab = ttkb.Frame(nb, padding=12)
        self.adv_tab = ttkb.Frame(nb, padding=12)
        nb.add(self.main_tab, text="  Main  "); nb.add(self.adv_tab, text="  Advanced  ")
        self._build_main_tab(); self._build_advanced_tab()

    def _build_main_tab(self):
        f = self.main_tab; f.columnconfigure(1, weight=1); row = 0
        drop_box = ttkb.LabelFrame(f, text="Drop Folder / File di sini (atau Browse)", padding=10)
        drop_box.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        self.drop_label = ttkb.Label(drop_box, text="📁  Drag & Drop folder ke sini", anchor="center", font=("Segoe UI", 11))
        self.drop_label.pack(fill="x", pady=12)
        if HAS_DND:
            self.drop_label.drop_target_register(DND_FILES); self.drop_label.dnd_bind("<<Drop>>", self._on_drop_input)

        row += 1
        ttkb.Label(f, text="Input folder:").grid(row=row, column=0, sticky="w", pady=4)
        self.input_var = tk.StringVar()
        self.input_entry = ttkb.Entry(f, textvariable=self.input_var)
        self.input_entry.grid(row=row, column=1, sticky="ew", padx=6)
        ttkb.Button(f, text="Browse…", command=self._pick_input, width=10).grid(row=row, column=2)
        if HAS_DND:
            self.input_entry.drop_target_register(DND_FILES); self.input_entry.dnd_bind("<<Drop>>", self._on_drop_input)

        row += 1
        ttkb.Label(f, text="Output folder:").grid(row=row, column=0, sticky="w", pady=4)
        self.output_var = tk.StringVar()
        self.output_entry = ttkb.Entry(f, textvariable=self.output_var)
        self.output_entry.grid(row=row, column=1, sticky="ew", padx=6)
        out_btns = ttkb.Frame(f); out_btns.grid(row=row, column=2)
        ttkb.Button(out_btns, text="Browse…", command=self._pick_output, width=10).pack(side="left")
        ttkb.Button(out_btns, text="⇄", command=self._swap_folders, width=3).pack(side="left", padx=(2, 0))
        if HAS_DND:
            self.output_entry.drop_target_register(DND_FILES); self.output_entry.dnd_bind("<<Drop>>", self._on_drop_output)

        row += 1
        ttkb.Label(f, text="Mode:").grid(row=row, column=0, sticky="w", pady=4)
        self.mode_var = tk.StringVar(value="copy")
        mframe = ttkb.Frame(f); mframe.grid(row=row, column=1, columnspan=2, sticky="w", padx=6)
        for text, val in [("Copy (aman)", "copy"), ("Move", "move"), ("In-place (overwrite)", "inplace")]:
            ttkb.Radiobutton(mframe, text=text, value=val, variable=self.mode_var).pack(side="left", padx=4)

        row += 1
        ttkb.Separator(f, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)

        row += 1
        ttkb.Label(f, text="Author / Creator:").grid(row=row, column=0, sticky="w", pady=4)
        self.author_var = tk.StringVar(value="AI Generated")
        ttkb.Entry(f, textvariable=self.author_var).grid(row=row, column=1, sticky="ew", padx=6, columnspan=2)

        row += 1
        self.ai_tag_var = tk.BooleanVar(value=True)
        ttkb.Checkbutton(f, text='Tambahkan keyword "AI, AI Generated"', variable=self.ai_tag_var).grid(row=row, column=1, columnspan=2, sticky="w", padx=6, pady=4)

        row += 1
        ttkb.Label(f, text="Extra keywords:").grid(row=row, column=0, sticky="nw", pady=4)
        self.extra_kw_var = tk.StringVar()
        ttkb.Entry(f, textvariable=self.extra_kw_var).grid(row=row, column=1, sticky="ew", padx=6, columnspan=2)
        row += 1
        ttkb.Label(f, text="(Opsional)", foreground="#888").grid(row=row, column=1, columnspan=2, sticky="w", padx=6)

        row += 1
        ttkb.Label(f, text="Format Title:").grid(row=row, column=0, sticky="w", pady=4)
        self.title_fmt_var = tk.StringVar(value="Title Case")
        ttkb.Combobox(f, textvariable=self.title_fmt_var, state="readonly", values=["As-is", "Title Case", "Sentence case", "UPPERCASE", "lowercase"]).grid(row=row, column=1, sticky="w", padx=6)

        row += 1
        self.recursive_var = tk.BooleanVar(value=False)
        ttkb.Checkbutton(f, text="Proses sub-folder (recursive)", variable=self.recursive_var).grid(row=row, column=1, columnspan=2, sticky="w", padx=6)

        row += 1
        btns = ttkb.Frame(f); btns.grid(row=row, column=0, columnspan=3, sticky="ew", pady=12)
        ttkb.Button(btns, text="🔍  Preview", command=self._preview).pack(side="left", padx=(0, 8))
        self.process_btn = ttkb.Button(btns, text="▶  Mulai Proses", command=self._start)
        self.process_btn.pack(side="left", padx=4)
        ttkb.Button(btns, text="📄  Export CSV", command=self._export_csv).pack(side="right")

        row += 1
        bottom_frame = ttkb.Frame(f)
        bottom_frame.grid(row=row, column=0, columnspan=3, sticky="nsew")
        bottom_frame.columnconfigure(0, weight=2); bottom_frame.columnconfigure(1, weight=1); bottom_frame.rowconfigure(0, weight=1)

        table_frame = ttkb.Frame(bottom_frame); table_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        table_frame.columnconfigure(0, weight=1); table_frame.rowconfigure(0, weight=1)
        style = ttkb.Style(); style.configure("Treeview", rowheight=25)
        cols = ("new_filename", "title", "keywords")
        self.tree = ttkb.Treeview(table_frame, columns=cols, show="headings", height=8)
        self.tree.heading("new_filename", text="New Filename"); self.tree.column("new_filename", width=250, minwidth=200, stretch=False)
        self.tree.heading("title", text="Title"); self.tree.column("title", width=350, minwidth=250, stretch=False)
        self.tree.heading("keywords", text="Keywords"); self.tree.column("keywords", width=400, minwidth=250, stretch=False)
        self.tree.bind("<Double-1>", self._show_full_text)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb_v = ttkb.Scrollbar(table_frame, orient="vertical", command=self.tree.yview); sb_v.grid(row=0, column=1, sticky="ns")
        sb_h = ttkb.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview); sb_h.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)

        log_frame = ttkb.LabelFrame(bottom_frame, text="Log", padding=5)
        log_frame.grid(row=0, column=1, sticky="nsew")
        log_frame.columnconfigure(0, weight=1); log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, wrap="word", font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4", insertbackground="white")
        self.log_text.tag_config("success", foreground="#4CAF50")
        self.log_text.tag_config("error", foreground="#F44336")
        self.log_text.tag_config("warning", foreground="#FFC107")
        self.log_text.tag_config("info", foreground="#2196F3")
        self.log_text.tag_config("normal", foreground="#d4d4d4")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_sb = ttkb.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview); log_sb.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=log_sb.set)

        row += 1
        self.progress = ttkb.Progressbar(f, mode="determinate")
        self.progress.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(4, 2))
        row += 1
        self.progress_label = ttkb.Label(f, text="Siap.", foreground="#888")
        self.progress_label.grid(row=row, column=0, columnspan=3, sticky="w")
        f.rowconfigure(row - 2, weight=1)

    def _build_advanced_tab(self):
        f = self.adv_tab; f.columnconfigure(0, weight=1); row = 0
        box_res = ttkb.LabelFrame(f, text="Validasi & Kualitas (Adobe Stock)", padding=10)
        box_res.grid(row=row, column=0, sticky="ew", pady=(0, 10)); box_res.columnconfigure(0, weight=1)
        self.validate_mp_var = tk.BooleanVar(value=True)
        ttkb.Checkbutton(box_res, text="Validasi minimal 4 Megapiksel", variable=self.validate_mp_var).grid(row=0, column=0, sticky="w", pady=2)
        self.auto_upscale_small_var = tk.BooleanVar(value=True)
        ttkb.Checkbutton(box_res, text="Auto-Upscale JIKA resolusi di bawah 4 MP", variable=self.auto_upscale_small_var).grid(row=1, column=0, sticky="w", pady=2)
        self.convert_jpeg_var = tk.BooleanVar(value=True)
        ttkb.Checkbutton(box_res, text="Konversi ke JPEG", variable=self.convert_jpeg_var).grid(row=2, column=0, sticky="w", pady=2)

        row += 1
        box_nlp = ttkb.LabelFrame(f, text="NLP Keyword Generation", padding=10)
        box_nlp.grid(row=row, column=0, sticky="ew", pady=(0, 10)); box_nlp.columnconfigure(1, weight=1)
        self.nlp_enable_var = tk.BooleanVar(value=True)
        ttkb.Checkbutton(box_nlp, text="Aktifkan Hybrid NLP (Ollama + Optional NLTK)", variable=self.nlp_enable_var).grid(row=0, column=0, columnspan=3, sticky="w", pady=2)
        self.use_nltk_var = tk.BooleanVar(value=False)
        ttkb.Checkbutton(box_nlp, text="Gunakan NLTK WordNet (Opsional)", variable=self.use_nltk_var).grid(row=1, column=0, columnspan=3, sticky="w", pady=2)
        ttkb.Label(box_nlp, text="Ollama Model:").grid(row=2, column=0, sticky="w", pady=2)
        self.ollama_model_var = tk.StringVar(value="")
        self.ollama_combo = ttkb.Combobox(box_nlp, textvariable=self.ollama_model_var, width=25)
        self.ollama_combo.grid(row=2, column=1, sticky="w", padx=6)
        ttkb.Button(box_nlp, text="🔄", command=self._refresh_ollama_models, width=3).grid(row=2, column=2)

        row += 1
        box_org = ttkb.LabelFrame(f, text="📁 Organize Subfolder (untuk 100.000+ File)", padding=10)
        box_org.grid(row=row, column=0, sticky="ew", pady=(0, 10)); box_org.columnconfigure(1, weight=1)
        ttkb.Label(box_org, text="Mode:").grid(row=0, column=0, sticky="w", pady=2)
        self.organize_mode_var = tk.StringVar(value="batch_100")
        
        mode_labels = [label for label, _ in ORGANIZE_MODES]
        mode_values = {label: val for label, val in ORGANIZE_MODES}
        current_label = "Batch of 100 (100, 200, 300...)"
        
        self.organize_combo = ttkb.Combobox(box_org, state="readonly", values=mode_labels, width=35)
        self.organize_combo.set(current_label)
        self.organize_combo.grid(row=0, column=1, sticky="w", padx=6)
        
        def on_org_change(event=None):
            self.organize_mode_var.set(mode_values.get(self.organize_combo.get(), "none"))
        self.organize_combo.bind("<<ComboboxSelected>>", on_org_change)
        
        ttkb.Label(box_org, text="File 1-100 → folder '100/', file 101-200 → folder '200/', dst.\nMemudahkan navigasi saat portofolio sudah sangat besar.",
                   foreground="#888").grid(row=1, column=0, columnspan=2, sticky="w", padx=2, pady=4)

        row += 1
        box4 = ttkb.LabelFrame(f, text="Manual Upscale (Real-ESRGAN / Upscayl)", padding=10)
        box4.grid(row=row, column=0, sticky="ew", pady=(0, 10)); box4.columnconfigure(1, weight=1)
        self.upscale_var = tk.BooleanVar(value=False)
        ttkb.Checkbutton(box4, text="Paksa Upscale SEMUA gambar", variable=self.upscale_var).grid(row=0, column=0, columnspan=3, sticky="w", pady=2)
        ttkb.Label(box4, text="Upscaler exe:").grid(row=1, column=0, sticky="w", pady=2)
        self.upscaler_path_var = tk.StringVar(value="")
        ttkb.Entry(box4, textvariable=self.upscaler_path_var).grid(row=1, column=1, sticky="ew", padx=6)
        ttkb.Button(box4, text="Browse…", command=self._pick_upscaler, width=10).grid(row=1, column=2)
        ttkb.Label(box4, text="Model:").grid(row=2, column=0, sticky="w", pady=2)
        self.upscale_model_var = tk.StringVar(value=UPSCALER_MODELS[0])
        ttkb.Combobox(box4, textvariable=self.upscale_model_var, state="readonly", values=UPSCALER_MODELS, width=30).grid(row=2, column=1, sticky="w", padx=6)
        ttkb.Label(box4, text="Scale:").grid(row=3, column=0, sticky="w", pady=2)
        self.upscale_scale_var = tk.StringVar(value="4x")
        ttkb.Combobox(box4, textvariable=self.upscale_scale_var, state="readonly", values=["2x", "3x", "4x"], width=10).grid(row=3, column=1, sticky="w", padx=6)

        row += 1
        box1 = ttkb.LabelFrame(f, text="Metadata Tambahan", padding=10)
        box1.grid(row=row, column=0, sticky="ew", pady=(0, 10)); box1.columnconfigure(1, weight=1)
        ttkb.Label(box1, text="Category:").grid(row=0, column=0, sticky="w", pady=2)
        self.category_var = tk.StringVar(value="— none —")
        ttkb.Combobox(box1, textvariable=self.category_var, state="readonly", values=ADOBE_CATEGORIES, width=40).grid(row=0, column=1, sticky="w", padx=6)
        ttkb.Label(box1, text="Alt Text:").grid(row=1, column=0, sticky="w", pady=2)
        self.alt_var = tk.StringVar(value="")
        ttkb.Entry(box1, textvariable=self.alt_var).grid(row=1, column=1, sticky="ew", padx=6)

        row += 1
        box_sec = ttkb.LabelFrame(f, text="Keamanan & Database", padding=10)
        box_sec.grid(row=row, column=0, sticky="ew", pady=(0, 10)); box_sec.columnconfigure(0, weight=1)
        self.dup_check_var = tk.BooleanVar(value=True)
        ttkb.Checkbutton(box_sec, text="Deteksi duplikat (Cek Database Riwayat)", variable=self.dup_check_var).grid(row=0, column=0, sticky="w", pady=2)
        ttkb.Button(box_sec, text="🗑️ Reset Database Riwayat", command=self._reset_db, bootstyle="danger-outline").grid(row=1, column=0, sticky="w", pady=6)
        self.backup_var = tk.BooleanVar(value=False)
        ttkb.Checkbutton(box_sec, text="Buat backup _original (mode in-place)", variable=self.backup_var).grid(row=2, column=0, sticky="w", pady=2)

        row += 1
        box2 = ttkb.LabelFrame(f, text="Batch Rename", padding=10)
        box2.grid(row=row, column=0, sticky="ew", pady=(0, 10)); box2.columnconfigure(1, weight=1)
        self.rename_enable_var = tk.BooleanVar(value=True)
        ttkb.Checkbutton(box2, text="Aktifkan batch rename", variable=self.rename_enable_var).grid(row=0, column=0, columnspan=2, sticky="w", pady=2)
        ttkb.Label(box2, text="Pattern:").grid(row=1, column=0, sticky="w", pady=2)
        self.rename_pattern_var = tk.StringVar(value="demhndAIStock_{num:05d}")
        ttkb.Entry(box2, textvariable=self.rename_pattern_var).grid(row=1, column=1, sticky="ew", padx=6)
        ttkb.Label(box2, text="Start Number:").grid(row=3, column=0, sticky="w", pady=2)
        self.start_num_var = tk.IntVar(value=1)
        ttkb.Spinbox(box2, from_=1, to=999999, textvariable=self.start_num_var, width=12).grid(row=3, column=1, sticky="w", padx=6)

    def _reset_db(self):
        if messagebox.askyesno("Konfirmasi", "Hapus semua riwayat di database?"):
            try:
                with sqlite3.connect(self.db_file) as conn: conn.execute("DELETE FROM history")
                self._log("🗑️ Database di-reset.")
            except Exception as e: self._log(f"⚠ Gagal: {e}")

    def _toggle_theme(self):
        if not HAS_TTKBOOTSTRAP: return
        if self._current_theme == "darkly":
            self.style.theme_use("cosmo"); self._current_theme = "cosmo"
        else:
            self.style.theme_use("darkly"); self._current_theme = "darkly"

    def _swap_folders(self):
        a = self.input_var.get(); b = self.output_var.get()
        self.input_var.set(b); self.output_var.set(a); self._save_config()

    def _pick_input(self):
        d = filedialog.askdirectory()
        if d: self.input_var.set(d); self._save_config()

    def _pick_output(self):
        d = filedialog.askdirectory()
        if d: self.output_var.set(d); self._save_config()

    def _pick_upscaler(self):
        p = filedialog.askopenfilename(filetypes=[("Executable", "*.exe"), ("All files", "*.*")])
        if p: self.upscaler_path_var.set(p); self._save_config()

    def _parse_drop_paths(self, data):
        return [a or b for a, b in re.findall(r'\{([^}]+)\}|(\S+)', data)]

    def _on_drop_input(self, event):
        paths = self._parse_drop_paths(event.data)
        if paths:
            p = paths[0]
            self.input_var.set(p if os.path.isdir(p) else os.path.dirname(p))
            self._save_config()

    def _on_drop_output(self, event):
        paths = self._parse_drop_paths(event.data)
        if paths:
            p = paths[0]
            self.output_var.set(p if os.path.isdir(p) else os.path.dirname(p))
            self._save_config()

    def _log(self, msg):
        def _append():
            tag = "normal"
            if "✔" in msg or "✅" in msg or "⬆" in msg or "🖼️" in msg or "📝" in msg or "📁" in msg: tag = "success"
            elif "✗" in msg or "Error" in msg: tag = "error"
            elif "⚠" in msg: tag = "warning"
            elif "⏭" in msg or "🔄" in msg or "ℹ" in msg or "▶" in msg or "🧠" in msg: tag = "info"
            self.log_text.insert("end", msg + "\n", tag)
            self.log_text.see("end")
            lines = int(self.log_text.index('end-1c').split('.')[0])
            if lines > 200: self.log_text.delete('1.0', f'{lines-200}.0')
        self.after(0, _append)

    def _set_progress(self, value):
        self.progress["value"] = value
        pct = int(value / self._total_files * 100) if self._total_files else 0
        self.progress_label.config(text=f"{value} / {self._total_files} ({pct}%)")

    def _update_status(self, msg): self.progress_label.config(text=msg)

    def _update_tree_row(self, orig_name, new_name, title, kw_str):
        item_id = self.tree_items.get(orig_name)
        if item_id and self.tree.exists(item_id):
            self.tree.item(item_id, values=(new_name, title, kw_str))

    def _collect_keywords(self):
        kw = (["AI", "AI Generated"] if self.ai_tag_var.get() else []) + split_keywords(self.extra_kw_var.get())
        seen, out = set(), []
        for k in kw:
            if k.lower() not in seen:
                seen.add(k.lower()); out.append(k)
        return out

    def _preview(self):
        input_dir = self.input_var.get().strip()
        if not os.path.isdir(input_dir): messagebox.showerror("Error", "Folder input tidak valid."); return
        files = find_images(input_dir, self.recursive_var.get())
        for i in self.tree.get_children(): self.tree.delete(i)
        kw_str = ", ".join(self._collect_keywords())
        self.tree_items = {}
        for f in files:
            item_id = self.tree.insert("", "end", values=("-", "-", kw_str))
            self.tree_items[f.name] = item_id
        self.progress_label.config(text=f"Preview: {len(files)} file")

    def _show_full_text(self, event):
        item = self.tree.identify_row(event.y)
        if not item: return
        values = self.tree.item(item, "values")
        detail_win = tk.Toplevel(self)
        detail_win.title("Detail File"); detail_win.geometry("600x350")
        txt = tk.Text(detail_win, wrap="word", padx=10, pady=10, bg="#1e1e1e", fg="#d4d4d4", font=("Segoe UI", 10))
        txt.pack(fill="both", expand=True)
        txt.insert("end", f"NEW FILENAME:\n{values[0]}\n\nTITLE:\n{values[1]}\n\nKEYWORDS:\n{values[2]}\n")
        txt.config(state="disabled")

    def _start(self):
        if self._processing: return
        self._save_config()
        ok, err_msg = check_exiftool()
        if not ok: messagebox.showerror("ExifTool tidak siap", err_msg); return
        input_dir = self.input_var.get().strip()
        if not os.path.isdir(input_dir): messagebox.showerror("Error", "Folder input tidak valid."); return
        mode = self.mode_var.get()
        output_dir = self.output_var.get().strip()
        if mode != "inplace":
            if not output_dir: messagebox.showerror("Error", "Folder output wajib diisi."); return
            try: os.makedirs(output_dir, exist_ok=True)
            except OSError as e: messagebox.showerror("Error", f"Tidak bisa membuat folder:\n{e}"); return
        if self.upscale_var.get() or self.auto_upscale_small_var.get():
            upscaler = self.upscaler_path_var.get().strip() or find_upscaler()
            if not upscaler: messagebox.showerror("Upscaler tidak ditemukan", "Pilih path upscaler exe."); return
        if self.nlp_enable_var.get() and not HAS_OLLAMA:
            messagebox.showerror("Ollama Error", "Library 'ollama' belum terinstall."); return
        if self.nlp_enable_var.get() and not self.ollama_model_var.get().strip():
            messagebox.showerror("Model Kosong", "Pilih model Ollama."); return
        files = find_images(input_dir, self.recursive_var.get())
        if not files: messagebox.showinfo("Info", "Tidak ada gambar."); return
        self._processing = True
        self.process_btn.config(state="disabled")
        self._total_files = len(files)
        self.progress["maximum"] = len(files); self.progress["value"] = 0
        self.progress_label.config(text=f"0 / {len(files)} (0%)")
        self._log(f"▶ Mulai {len(files)} file…")
        threading.Thread(target=self._worker, args=(files,), daemon=True).start()

    def _upscale_image(self, src, dst, scale, model):
        upscaler = self.upscaler_path_var.get().strip() or find_upscaler()
        if not upscaler: return False
        exe_name = Path(upscaler).name.lower()
        cmd = [upscaler, "-i", str(src), "-o", str(dst), "-s", "4", "-m" if "upscayl" in exe_name else "-n", model]
        try:
            flags = (subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, creationflags=flags)
            if r.returncode != 0: return False
            if not Path(dst).exists(): return False
            if scale < 4 and HAS_PIL:
                try:
                    with Image.open(dst) as img:
                        w, h = img.size
                        resized = img.resize((int(w * (scale / 4)), int(h * (scale / 4))), Image.LANCZOS)
                        resized.save(dst)
                except Exception: pass
            return True
        except Exception: return False

    def _worker(self, files):
        author = self.author_var.get().strip() or "AI Generated"
        title_fmt = self.title_fmt_var.get()
        alt_text = self.alt_var.get().strip()
        category = self.category_var.get()
        cat_num = category.split("·")[0].strip() if category and category != "— none —" else None

        manual_kw_list = self._collect_keywords()
        mode = self.mode_var.get()
        in_dir = Path(self.input_var.get())
        out_dir = Path(self.output_var.get()) if mode != "inplace" else None
        
        do_dup = self.dup_check_var.get()
        do_upscale_force = self.upscale_var.get()
        do_upscale_auto = self.auto_upscale_small_var.get()
        do_validate_mp = self.validate_mp_var.get()
        do_convert_jpeg = self.convert_jpeg_var.get()
        
        do_nlp = self.nlp_enable_var.get()
        use_nltk = self.use_nltk_var.get()
        ollama_model = self.ollama_model_var.get().strip()
        upscale_model = self.upscale_model_var.get()
        upscale_scale = int(self.upscale_scale_var.get().replace("x", ""))
        do_rename = self.rename_enable_var.get()
        rename_pattern = self.rename_pattern_var.get().strip()
        start_num = self.start_num_var.get()
        organize_mode = self.organize_mode_var.get()

        db_history = {}
        if do_dup:
            self._log("🔎 Memuat riwayat DB...")
            try:
                with sqlite3.connect(self.db_file) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT original_filename, output_filename FROM history")
                    for row in cursor.fetchall(): db_history[row[0]] = row[1]
            except Exception as e: self._log(f"⚠ Gagal load DB: {e}")
            self._log(f"✅ Memuat {len(db_history)} riwayat.")

        existing_files = set()
        if do_dup and out_dir and out_dir.exists():
            self._log("🔎 Memindai file di folder output...")
            try:
                for p in out_dir.rglob("*"):
                    if p.is_file(): existing_files.add(p.name)
            except Exception as e: self._log(f"⚠ Gagal scan output: {e}")
            self._log(f"✅ {len(existing_files)} file ditemukan di output.")

        next_num = start_num
        if do_rename:
            scan_dir = out_dir if mode != "inplace" else in_dir
            prefix = (rename_pattern.split("{")[0] if "{" in rename_pattern else rename_pattern)
            next_num = get_next_number(scan_dir, prefix, start_num)
            self._log(f"📛 Rename dimulai dari: {next_num}")

        success, errors, results = 0, [], []

        for i, f in enumerate(files, 1):
            try:
                self.after(0, self._update_status, f"Memproses ({i}/{len(files)}): {f.name[:30]}...")
                
                if do_dup and f.name in db_history:
                    expected_out_name = db_history[f.name]
                    if expected_out_name in existing_files:
                        self._log(f"⏭ SKIP (Sudah ada di output): {f.name[:30]}...")
                        self.after(0, self._update_tree_row, f.name, expected_out_name, "-", "-")
                        self.after(0, self._set_progress, i)
                        continue

                if mode == "inplace": target = f
                else:
                    try: rel = f.parent.relative_to(in_dir)
                    except ValueError: rel = Path(".")
                    target = out_dir / rel / f.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if mode == "copy": shutil.copy2(f, target)
                    elif mode == "move": shutil.move(f, target)

                real_ext = None
                try:
                    with open(target, "rb") as fp:
                        header = fp.read(12)
                        if header.startswith(b"\x89PNG\r\n\x1a\n"): real_ext = ".png"
                        elif header.startswith(b"\xff\xd8\xff"): real_ext = ".jpg"
                        elif header.startswith(b"RIFF") and header[8:12] == b"WEBP": real_ext = ".webp"
                except Exception: pass

                if real_ext and target.suffix.lower() not in (real_ext, ".jpeg" if real_ext == ".jpg" else real_ext):
                    new_target = target.with_suffix(real_ext)
                    if new_target.exists(): new_target.unlink()
                    target.rename(new_target)
                    self._log(f"🔄 Fix Ekstensi: {target.name[:30]}... → {new_target.name[:30]}...")
                    target = new_target

                if do_convert_jpeg and target.suffix.lower() not in (".jpg", ".jpeg"):
                    if HAS_PIL:
                        try:
                            new_target = target.with_suffix(".jpg")
                            with Image.open(target) as img:
                                if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                                    bg = Image.new("RGB", img.size, (255, 255, 255))
                                    bg.paste(img, mask=img.split()[-1]) 
                                    img = bg
                                else: img = img.convert("RGB")
                                img.save(new_target, "JPEG", quality=100, subsampling=0)
                            target.unlink(); old_name = target.name; target = new_target
                            self._log(f"🖼️ Convert JPEG: {old_name[:30]}... → {target.name}")
                        except Exception as e: self._log(f"⚠ Gagal JPEG: {e}")

                original_stem = target.stem
                
                # --- SANITIZE TEXT (Hapus ? ! dan em-dash —) ---
                clean_stem = re.sub(r'[?!—–]', ' ', original_stem)
                clean_stem = re.sub(r'\s+', ' ', clean_stem).strip()
                
                title = format_text(clean_stem, title_fmt)
                # Perbaiki Children'S -> Children's SETELAH di-title-case
                title = re.sub(r"'S\b", "'s", title)
                title = re.sub(r"\s+", " ", title).strip()

                desc_text = re.sub(r"[_\-—–]+", " ", clean_stem)
                description = re.sub(r"\s+", " ", desc_text).strip()
                alt = alt_text or title

                if do_rename:
                    final_id = next_num
                    for _guard in range(10000):
                        new_name = rename_pattern.format(num=final_id) if "{" in rename_pattern else f"{rename_pattern}_{final_id}"
                        subfolder = get_organize_subfolder(organize_mode, final_id) if mode != "inplace" else Path(".")
                        if mode == "inplace":
                            base_dir = target.parent
                        else:
                            base_dir = out_dir / subfolder / rel
                        new_path = base_dir / (new_name + target.suffix)
                        if not new_path.exists() or new_path == target: break
                        final_id += 1
                    
                    if new_path != target:
                        new_path.parent.mkdir(parents=True, exist_ok=True)
                        old_name = target.name
                        target.rename(new_path)
                        if mode != "inplace":
                            self._log(f"📝 {old_name[:20]}... → {new_path.relative_to(out_dir)}")
                        else:
                            self._log(f"📝 {old_name[:20]}... → {new_path.name}")
                        target = new_path
                    next_num = final_id + 1

                need_upscale = do_upscale_force
                if HAS_PIL:
                    try:
                        with Image.open(target) as img:
                            w, h = img.size; mp = (w * h) / 1_000_000
                            self._log(f"ℹ {target.name}: {w}x{h} ({mp:.1f} MP)")
                            if do_validate_mp and mp < 4.0 and do_upscale_auto:
                                self._log(f"⚠ {target.name} di bawah 4MP. Auto-Upscale aktif.")
                                need_upscale = True
                    except Exception as e: self._log(f"⚠ Gagal cek resolusi: {e}")

                if need_upscale:
                    self.after(0, self._update_status, f"Upscaling {upscale_scale}x: {target.name}...")
                    upscaled = target.with_name(f"{target.stem}_upsc{target.suffix}")
                    if self._upscale_image(target, upscaled, upscale_scale, upscale_model):
                        try:
                            target.unlink(); upscaled.rename(target)
                            self._log(f"⬆ Upscaled: {target.name}")
                        except Exception as e: self._log(f"⚠ Gagal replace: {e}")

                final_kw_list = list(manual_kw_list)
                if do_nlp and ollama_model:
                    self.after(0, self._update_status, f"🧠 NLP Ollama: {target.name[:20]}...")
                    self._log(f"🧠 [Tahap 1] Ekstrak keyword dasar via Ollama...")
                    base_kws = extract_base_keywords(title, ollama_model)
                    seen_kw = set(k.lower().strip() for k in final_kw_list)
                    for k in base_kws:
                        if k.lower().strip() not in seen_kw:
                            final_kw_list.append(k); seen_kw.add(k.lower().strip())
                    self._log(f"  ↳ Base keywords: {len(final_kw_list)}")
                    
                    if use_nltk and HAS_NLTK and len(final_kw_list) < TARGET_KEYWORDS:
                        self.after(0, self._update_status, f"🧠 NLP NLTK: {target.name[:20]}...")
                        self._log(f"🧠 [Tahap 2] Sinonim via WordNet...")
                        for base_word in base_kws[:10]:
                            if len(final_kw_list) >= TARGET_KEYWORDS: break
                            for s in get_nltk_synonyms(base_word, max_per_word=1):
                                if s.lower() not in seen_kw and len(final_kw_list) < TARGET_KEYWORDS:
                                    final_kw_list.append(s); seen_kw.add(s.lower())
                        self._log(f"  ↳ Setelah NLTK: {len(final_kw_list)} keyword.")
                    
                    if len(final_kw_list) < TARGET_KEYWORDS:
                        self.after(0, self._update_status, f"🧠 NLP Expand: {target.name[:20]}...")
                        self._log(f"🧠 [Tahap 3] Melengkapi konsep via Ollama...")
                        final_kw_list = expand_keywords_iteratively(title, final_kw_list, ollama_model, log_callback=self._log, target=TARGET_KEYWORDS)
                    
                    self._log(f"  ✅ Total Final: {len(final_kw_list)} keyword.")

                final_kw_list = final_kw_list[:TARGET_KEYWORDS]
                kw_str = ", ".join(final_kw_list)

                exe = get_exiftool_path()
                cmd = [exe, "-charset", "utf8", "-overwrite_original", "-m", "-sep", ", "]
                cmd += ["-Keywords=", "-Subject=", "-IPTC:Keywords=", "-XMP-dc:Subject="]
                cmd += [
                    f"-XMP-dc:Identifier={f.name.strip()}", 
                    f"-Title={title}", f"-XMP-dc:Title={title}",
                    f"-Description={description}", f"-XMP-dc:Description={description}", f"-IPTC:Caption-Abstract={description}",
                    f"-XMP-photoshop:Headline={title}", f"-Author={author}", f"-XMP-dc:Creator={author}", f"-IPTC:By-line={author}",
                    f"-XMP-iptcCore:AltTextAccessibility={alt}",
                ]
                if kw_str: cmd.append(f"-XMP-dc:Subject={kw_str}")
                if cat_num: cmd += [f"-XMP-photoshop:Category={cat_num}"]
                cmd.append(str(target))

                flags = (subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                r = subprocess.run(cmd, capture_output=True, text=True, creationflags=flags)
                if r.returncode != 0: raise RuntimeError((r.stderr or r.stdout).strip())

                try:
                    rel_path = str(target.relative_to(out_dir)) if mode != "inplace" else ""
                    with sqlite3.connect(self.db_file) as conn:
                        conn.execute("INSERT OR REPLACE INTO history (original_filename, output_filename, output_path) VALUES (?, ?, ?)",
                                     (f.name, target.name, rel_path))
                        conn.commit()
                    existing_files.add(target.name)
                except Exception as e: self._log(f"⚠ Gagal simpan DB: {e}")

                self.after(0, self._update_tree_row, f.name, target.name, title, kw_str)
                success += 1
                results.append({
                    "filename": f.name, "new_filename": target.name, "title": title,
                    "description": description, "keywords": kw_str, "author": author,
                    "category": cat_num or "", "alt": alt, "path": str(target),
                })
            except Exception as e:
                errors.append(f"{f.name[:30]}: {e}"); self._log(f"✗ {f.name[:30]}: {e}")
            self.after(0, self._set_progress, i)

        self._last_results = results
        self.after(0, self._on_done, success, errors)

    def _on_done(self, success, errors):
        self._processing = False
        self.process_btn.config(state="normal")
        self.progress_label.config(text="Selesai.")
        self._log(f"✔ Selesai. Sukses={success}, Error={len(errors)}")
        if errors:
            play_finish_sound(is_error=True)
            messagebox.showwarning("Selesai dengan error", f"Sukses: {success}\nGagal: {len(errors)}\n\n" + "\n".join(errors[:5]))
        else:
            play_finish_sound(is_error=False)
            messagebox.showinfo("Selesai", f"Berhasil memproses {success} file.")

    def _export_csv(self):
        if not self._last_results: messagebox.showinfo("Info", "Belum ada hasil."); return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="adobe_stock_metadata.csv")
        if not path: return
        with open(path, "w", newline="", encoding="utf-8-sig") as fp:
            w = csv.DictWriter(fp, fieldnames=["Filename", "Title", "Description", "Keywords", "Category", "Author", "Alt Text"])
            w.writeheader()
            for r in self._last_results:
                w.writerow({
                    "Filename": r["new_filename"], "Title": r["title"], "Description": r["description"],
                    "Keywords": r["keywords"], "Category": r["category"], "Author": r["author"], "Alt Text": r["alt"],
                })
        messagebox.showinfo("Sukses", f"CSV tersimpan:\n{path}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
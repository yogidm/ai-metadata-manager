#!/usr/bin/env python3
"""
AI Metadata Manager (Complete & Fixed)
======================================
Batch metadata + rename + duplicate detection + drag & drop + dark mode
+ optional upscale 4x untuk AI-generated stock images.
"""

import os
import re
import csv
import sys
import shutil
import hashlib
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

# ---------- Optional imports ---------- #
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

ADOBE_CATEGORIES = [
    "— none —", "1 · Animals", "2 · Buildings and Architecture", "3 · Business",
    "4 · Drinks", "5 · The Environment", "6 · States of Mind", "7 · Food",
    "8 · Graphic Resources", "9 · Hobbies and Leisure", "10 · Industry",
    "11 · Landscapes", "12 · Lifestyle", "13 · People", "14 · Plants and Flowers",
    "15 · Culture and Religion", "16 · Science", "17 · Social Issues",
    "18 · Sports", "19 · Technology", "20 · Transport", "21 · Travel",
]

UPSCALER_MODELS = [
    "realesrgan-x4plus",
    "realesrgan-x4plus-anime",
    "realesr-animevideov3",
]


# ============================================================ #
#  ICON (auto-generate sekali)
# ============================================================ #
def ensure_icon():
    icon_path = Path(__file__).with_name("icon.ico")
    if icon_path.exists():
        return str(icon_path)
    if not HAS_PIL:
        return None
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([20, 70, 236, 222], radius=28, fill=(41, 98, 200, 255))
    d.rounded_rectangle([86, 42, 156, 92], radius=12, fill=(41, 98, 200, 255))
    d.ellipse([70, 100, 186, 216], fill=(255, 255, 255, 255))
    d.ellipse([96, 126, 160, 190], fill=(41, 98, 200, 255))
    d.ellipse([106, 136, 130, 160], fill=(224, 238, 255, 255))
    d.rounded_rectangle([176, 78, 214, 100], radius=5, fill=(255, 208, 63, 255))
    img.save(icon_path, sizes=[(16, 16), (32, 32), (48, 48),
                               (64, 64), (128, 128), (256, 256)])
    return str(icon_path)


# ============================================================ #
#  HELPERS
# ============================================================ #
def format_text(stem, mode):
    if mode == "As-is":
        return stem
    text = re.sub(r"[_\-]+", " ", stem)
    text = re.sub(r"\s+", " ", text).strip()
    if mode == "Title Case":
        return text.title()
    if mode == "Sentence case":
        return text[:1].upper() + text[1:].lower() if text else text
    if mode == "UPPERCASE":
        return text.upper()
    if mode == "lowercase":
        return text.lower()
    return stem


def split_keywords(raw):
    seen, out = set(), []
    for k in raw.split(","):
        k = k.strip()
        if k and k.lower() not in seen:
            seen.add(k.lower())
            out.append(k)
    return out


def find_images(folder, recursive):
    p = Path(folder)
    it = p.rglob("*") if recursive else p.glob("*")
    return sorted(f for f in it
                  if f.is_file() and f.suffix.lower() in SUPPORTED_EXT)


def get_exiftool_path():
    script_dir = Path(__file__).parent
    for name in ("exiftool.exe", "exiftool"):
        local_exe = script_dir / name
        if local_exe.exists():
            return str(local_exe)
    return shutil.which("exiftool")


def check_exiftool():
    exe = get_exiftool_path()
    if not exe:
        return False, "ExifTool tidak ditemukan."
    exe_path = Path(exe)
    if exe_path.parent == Path(__file__).parent:
        files_dir = exe_path.parent / "exiftool_files"
        if not files_dir.exists() or not files_dir.is_dir():
            return False, ("Folder 'exiftool_files' tidak ditemukan di samping "
                           "exiftool.exe. Pastikan seluruh isi file ZIP "
                           "ExifTool sudah diekstrak ke folder ini.")
    return True, ""


def file_hash(path):
    h = hashlib.md5()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def get_next_number(scan_dir, prefix, start):
    if not scan_dir or not Path(scan_dir).exists():
        return start
    max_num = start - 1
    for f in Path(scan_dir).rglob("*"):
        if not f.is_file():
            continue
        m = re.match(rf"^{re.escape(prefix)}(\d+)$", f.stem)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return max(max_num + 1, start)


def find_upscaler():
    for name in ("realesrgan-ncnn-vulkan.exe", "realesrgan-ncnn-vulkan",
                 "upscayl-bin.exe", "upscayl-bin"):
        p = shutil.which(name)
        if p:
            return p
    for p in (
        r"C:\Program Files\Upscayl\resources\bin\upscayl-bin.exe",
        r"C:\realesrgan\realesrgan-ncnn-vulkan.exe",
    ):
        if os.path.exists(p):
            return p
    return None


# ============================================================ #
#  BASE WINDOW
# ============================================================ #
if HAS_DND:
    class BaseWindow(TkinterDnD.Tk):
        pass
else:
    class BaseWindow(tk.Tk):
        pass


# ============================================================ #
#  APP
# ============================================================ #
class App(BaseWindow):
    def __init__(self):
        super().__init__()

        if HAS_TTKBOOTSTRAP:
            self.style = ttkb.Style()
            self.style.theme_use("superhero")
            self._current_theme = "superhero"
        else:
            self._current_theme = "default"

        self.title(APP_NAME)
        self.geometry("1080x880")
        self.minsize(960, 720)

        icon = ensure_icon()
        if icon:
            try:
                self.iconbitmap(icon)
            except Exception:
                pass

        self._processing = False
        self._total_files = 0
        self._last_results = []

        self._build_ui()

    # -------------------- UI -------------------- #
    def _build_ui(self):
        topbar = ttkb.Frame(self, padding=(12, 8))
        topbar.pack(fill="x")
        ttkb.Label(topbar, text=APP_NAME,
                   font=("Segoe UI", 14, "bold")).pack(side="left")
        if HAS_TTKBOOTSTRAP:
            ttkb.Button(topbar, text="🌙 Toggle Theme",
                        command=self._toggle_theme,
                        width=15).pack(side="right", padx=4)

        nb = ttkb.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.main_tab = ttkb.Frame(nb, padding=12)
        self.adv_tab = ttkb.Frame(nb, padding=12)
        nb.add(self.main_tab, text="  Main  ")
        nb.add(self.adv_tab, text="  Advanced  ")

        self._build_main_tab()
        self._build_advanced_tab()

    def _build_main_tab(self):
        f = self.main_tab
        f.columnconfigure(1, weight=1)
        row = 0

        drop_box = ttkb.LabelFrame(f, text="Drop Folder / File di sini "
                                            "(atau Browse)", padding=10)
        drop_box.grid(row=row, column=0, columnspan=3,
                      sticky="ew", pady=(0, 10))
        self.drop_label = ttkb.Label(drop_box,
                                     text="📁  Drag & Drop folder ke sini",
                                     anchor="center",
                                     font=("Segoe UI", 11))
        self.drop_label.pack(fill="x", pady=12)
        if HAS_DND:
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind("<<Drop>>", self._on_drop_input)

        row += 1
        ttkb.Label(f, text="Input folder:").grid(row=row, column=0,
                                                 sticky="w", pady=4)
        self.input_var = tk.StringVar()
        self.input_entry = ttkb.Entry(f, textvariable=self.input_var)
        self.input_entry.grid(row=row, column=1, sticky="ew", padx=6)
        ttkb.Button(f, text="Browse…", command=self._pick_input,
                    width=10).grid(row=row, column=2)
        if HAS_DND:
            self.input_entry.drop_target_register(DND_FILES)
            self.input_entry.dnd_bind("<<Drop>>", self._on_drop_input)

        row += 1
        ttkb.Label(f, text="Output folder:").grid(row=row, column=0,
                                                  sticky="w", pady=4)
        self.output_var = tk.StringVar()
        self.output_entry = ttkb.Entry(f, textvariable=self.output_var)
        self.output_entry.grid(row=row, column=1, sticky="ew", padx=6)
        out_btns = ttkb.Frame(f)
        out_btns.grid(row=row, column=2)
        ttkb.Button(out_btns, text="Browse…", command=self._pick_output,
                    width=10).pack(side="left")
        ttkb.Button(out_btns, text="⇄", command=self._swap_folders,
                    width=3).pack(side="left", padx=(2, 0))
        if HAS_DND:
            self.output_entry.drop_target_register(DND_FILES)
            self.output_entry.dnd_bind("<<Drop>>", self._on_drop_output)

        row += 1
        ttkb.Label(f, text="Mode:").grid(row=row, column=0,
                                         sticky="w", pady=4)
        self.mode_var = tk.StringVar(value="copy")
        mframe = ttkb.Frame(f)
        mframe.grid(row=row, column=1, columnspan=2,
                    sticky="w", padx=6)
        for text, val in [("Copy (aman)", "copy"),
                          ("Move", "move"),
                          ("In-place (overwrite)", "inplace")]:
            ttkb.Radiobutton(mframe, text=text, value=val,
                             variable=self.mode_var).pack(side="left", padx=4)

        row += 1
        ttkb.Separator(f, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=10)

        row += 1
        ttkb.Label(f, text="Author / Creator:").grid(row=row, column=0,
                                                      sticky="w", pady=4)
        self.author_var = tk.StringVar(value="AI Generated")
        ttkb.Entry(f, textvariable=self.author_var).grid(
            row=row, column=1, sticky="ew", padx=6, columnspan=2)

        row += 1
        self.ai_tag_var = tk.BooleanVar(value=True)
        ttkb.Checkbutton(
            f,
            text='Tambahkan keyword "AI, AI Generated" (Adobe Stock AI rule)',
            variable=self.ai_tag_var,
        ).grid(row=row, column=1, columnspan=2,
               sticky="w", padx=6, pady=4)

        row += 1
        ttkb.Label(f, text="Extra keywords:").grid(row=row, column=0,
                                                    sticky="nw", pady=4)
        self.extra_kw_var = tk.StringVar()
        ttkb.Entry(f, textvariable=self.extra_kw_var).grid(
            row=row, column=1, sticky="ew", padx=6, columnspan=2)
        row += 1
        ttkb.Label(f, text="(Opsional. Bisa dikosongkan jika akan dilengkapi via ImStocker Studio)",
                   foreground="#888").grid(row=row, column=1,
                                            columnspan=2,
                                            sticky="w", padx=6)

        row += 1
        ttkb.Label(f, text="Format Title:").grid(row=row, column=0,
                                                  sticky="w", pady=4)
        self.title_fmt_var = tk.StringVar(value="Title Case")
        ttkb.Combobox(f, textvariable=self.title_fmt_var, state="readonly",
                      values=["As-is", "Title Case", "Sentence case",
                              "UPPERCASE", "lowercase"]).grid(
            row=row, column=1, sticky="w", padx=6)

        row += 1
        self.recursive_var = tk.BooleanVar(value=False)
        ttkb.Checkbutton(f, text="Proses sub-folder (recursive)",
                         variable=self.recursive_var).grid(
            row=row, column=1, columnspan=2, sticky="w", padx=6)

        row += 1
        btns = ttkb.Frame(f)
        btns.grid(row=row, column=0, columnspan=3,
                  sticky="ew", pady=12)
        ttkb.Button(btns, text="🔍  Preview",
                    command=self._preview).pack(side="left", padx=(0, 8))
        self.process_btn = ttkb.Button(btns, text="▶  Mulai Proses",
                                       command=self._start)
        self.process_btn.pack(side="left", padx=4)
        ttkb.Button(btns, text="📄  Export CSV",
                    command=self._export_csv).pack(side="right")

        row += 1
        style = ttkb.Style()
        style.configure("Treeview", rowheight=25)
        cols = ("filename", "title", "keywords")
        self.tree = ttkb.Treeview(f, columns=cols, show="headings", height=8)
        self.tree.heading("filename", text="Filename")
        self.tree.column("filename", width=250, minwidth=200, stretch=False)
        self.tree.heading("title", text="Title")
        self.tree.column("title", width=350, minwidth=250, stretch=False)
        self.tree.heading("keywords", text="Keywords")
        self.tree.column("keywords", width=300, minwidth=200, stretch=False)
        self.tree.bind("<Double-1>", self._show_full_text)

        self.tree.grid(row=row, column=0, columnspan=3, sticky="nsew", pady=(6, 0))
        sb_v = ttkb.Scrollbar(f, orient="vertical", command=self.tree.yview)
        sb_v.grid(row=row, column=3, sticky="ns", pady=(6, 0))
        row += 1
        sb_h = ttkb.Scrollbar(f, orient="horizontal", command=self.tree.xview)
        sb_h.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        self.tree.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)
        f.rowconfigure(row - 1, weight=1)

        row += 1
        self.progress = ttkb.Progressbar(f, mode="determinate")
        self.progress.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(4, 2))
        row += 1
        self.progress_label = ttkb.Label(f, text="Siap.", foreground="#888")
        self.progress_label.grid(row=row, column=0, columnspan=3, sticky="w")

    def _build_advanced_tab(self):
        f = self.adv_tab
        f.columnconfigure(0, weight=1)
        row = 0

        box1 = ttkb.LabelFrame(f, text="Adobe Stock", padding=10)
        box1.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        box1.columnconfigure(1, weight=1)

        ttkb.Label(box1, text="Category:").grid(row=0, column=0,
                                                 sticky="w", pady=2)
        self.category_var = tk.StringVar(value="— none —")
        ttkb.Combobox(box1, textvariable=self.category_var,
                      state="readonly",
                      values=ADOBE_CATEGORIES, width=40).grid(
            row=0, column=1, sticky="w", padx=6)

        ttkb.Label(box1, text="Alt Text:").grid(row=1, column=0,
                                                 sticky="w", pady=2)
        self.alt_var = tk.StringVar(value="")
        ttkb.Entry(box1, textvariable=self.alt_var).grid(
            row=1, column=1, sticky="ew", padx=6)
        ttkb.Label(box1, text="(kosongkan = sama dengan Title)",
                   foreground="#888").grid(row=2, column=1,
                                            sticky="w", padx=6)

        row += 1
        box2 = ttkb.LabelFrame(f, text="Batch Rename", padding=10)
        box2.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        box2.columnconfigure(1, weight=1)

        self.rename_enable_var = tk.BooleanVar(value=True)
        ttkb.Checkbutton(box2, text="Aktifkan batch rename",
                         variable=self.rename_enable_var).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=2)

        ttkb.Label(box2, text="Pattern:").grid(row=1, column=0,
                                                sticky="w", pady=2)
        self.rename_pattern_var = tk.StringVar(
            value="demhndAIStock_{num:05d}")
        ttkb.Entry(box2, textvariable=self.rename_pattern_var).grid(
            row=1, column=1, sticky="ew", padx=6)
        ttkb.Label(box2,
                   text="Pakai {num:05d} untuk zero-padded number. "
                        "Nomor otomatis lanjut dari file terakhir.",
                   foreground="#888", wraplength=700).grid(
            row=2, column=1, sticky="w", padx=6)

        ttkb.Label(box2, text="Start Number:").grid(row=3, column=0,
                                                     sticky="w", pady=2)
        self.start_num_var = tk.IntVar(value=1)
        ttkb.Spinbox(box2, from_=1, to=99999,
                     textvariable=self.start_num_var,
                     width=12).grid(row=3, column=1,
                                    sticky="w", padx=6)

        row += 1
        box3 = ttkb.LabelFrame(f, text="Keamanan", padding=10)
        box3.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        box3.columnconfigure(0, weight=1)

        self.dup_check_var = tk.BooleanVar(value=True)
        ttkb.Checkbutton(box3,
                         text="Deteksi duplikat (skip file dengan hash sama)",
                         variable=self.dup_check_var).grid(
            row=0, column=0, sticky="w", pady=2)

        self.backup_var = tk.BooleanVar(value=False)
        ttkb.Checkbutton(box3,
                         text="Buat backup _original (mode in-place)",
                         variable=self.backup_var).grid(
            row=1, column=0, sticky="w", pady=2)

        row += 1
        box4 = ttkb.LabelFrame(f,
                               text="Upscale (Real-ESRGAN / Upscayl)",
                               padding=10)
        box4.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        box4.columnconfigure(1, weight=1)

        self.upscale_var = tk.BooleanVar(value=False)
        ttkb.Checkbutton(box4,
                         text="Upscale 4x setelah proses "
                              "(butuh realesrgan-ncnn-vulkan / upscayl-bin)",
                         variable=self.upscale_var).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=2)

        ttkb.Label(box4, text="Upscaler exe:").grid(row=1, column=0,
                                                     sticky="w", pady=2)
        self.upscaler_path_var = tk.StringVar(value="")
        ttkb.Entry(box4, textvariable=self.upscaler_path_var).grid(
            row=1, column=1, sticky="ew", padx=6)
        ttkb.Button(box4, text="Browse…", command=self._pick_upscaler,
                    width=10).grid(row=1, column=2)

        ttkb.Label(box4, text="Model:").grid(row=2, column=0,
                                              sticky="w", pady=2)
        self.upscale_model_var = tk.StringVar(value=UPSCALER_MODELS[0])
        ttkb.Combobox(box4, textvariable=self.upscale_model_var,
                      state="readonly",
                      values=UPSCALER_MODELS, width=30).grid(
            row=2, column=1, sticky="w", padx=6)

        detected = find_upscaler()
        info = f"Detected: {detected}" if detected else \
               "Belum terdeteksi — Browse manual."
        ttkb.Label(box4, text=info, foreground="#888").grid(
            row=3, column=0, columnspan=3, sticky="w", pady=4)

        row += 1
        ttkb.Label(f, text="Log:", font=("Segoe UI", 10, "bold")).grid(
            row=row, column=0, sticky="w")
        row += 1
        self.log_text = tk.Text(f, height=12, wrap="word",
                                 font=("Consolas", 9),
                                 bg="#1e1e1e", fg="#d4d4d4",
                                 insertbackground="white")
        self.log_text.grid(row=row, column=0, sticky="nsew", pady=4)
        f.rowconfigure(row, weight=1)

    # -------------------- Actions -------------------- #
    def _toggle_theme(self):
        if not HAS_TTKBOOTSTRAP:
            return
        if self._current_theme == "superhero":
            self.style.theme_use("cosmo")
            self._current_theme = "cosmo"
        else:
            self.style.theme_use("superhero")
            self._current_theme = "superhero"

    def _swap_folders(self):
        a = self.input_var.get()
        b = self.output_var.get()
        self.input_var.set(b)
        self.output_var.set(a)

    def _pick_input(self):
        d = filedialog.askdirectory(title="Pilih folder input")
        if d:
            self.input_var.set(d)

    def _pick_output(self):
        d = filedialog.askdirectory(title="Pilih folder output")
        if d:
            self.output_var.set(d)

    def _pick_upscaler(self):
        p = filedialog.askopenfilename(
            title="Pilih upscaler executable",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")])
        if p:
            self.upscaler_path_var.set(p)

    def _parse_drop_paths(self, data):
        matches = re.findall(r'\{([^}]+)\}|(\S+)', data)
        return [a or b for a, b in matches]

    def _on_drop_input(self, event):
        paths = self._parse_drop_paths(event.data)
        if not paths:
            return
        p = paths[0]
        if os.path.isdir(p):
            self.input_var.set(p)
        elif os.path.isfile(p):
            self.input_var.set(os.path.dirname(p))

    def _on_drop_output(self, event):
        paths = self._parse_drop_paths(event.data)
        if not paths:
            return
        p = paths[0]
        if os.path.isdir(p):
            self.output_var.set(p)
        elif os.path.isfile(p):
            self.output_var.set(os.path.dirname(p))

    def _log(self, msg):
        def _append():
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
        self.after(0, _append)

    def _set_progress(self, value):
        self.progress["value"] = value
        pct = int(value / self._total_files * 100) if self._total_files else 0
        self.progress_label.config(
            text=f"{value} / {self._total_files} ({pct}%)")

    # -------------------- Keywords helper -------------------- #
    def _collect_keywords(self):
        kw = (["AI", "AI Generated"] if self.ai_tag_var.get() else []) \
             + split_keywords(self.extra_kw_var.get())
        seen, out = set(), []
        for k in kw:
            if k.lower() not in seen:
                seen.add(k.lower())
                out.append(k)
        return out

    # -------------------- Preview -------------------- #
    def _preview(self):
        input_dir = self.input_var.get().strip()
        if not os.path.isdir(input_dir):
            messagebox.showerror("Error", "Folder input tidak valid.")
            return
        files = find_images(input_dir, self.recursive_var.get())
        for i in self.tree.get_children():
            self.tree.delete(i)

        title_fmt = self.title_fmt_var.get()
        kw_str = ", ".join(self._collect_keywords())
        for f in files:
            title = format_text(f.stem, title_fmt)
            self.tree.insert("", "end", values=(f.name, title, kw_str))
        self.progress_label.config(text=f"Preview: {len(files)} file")

    def _show_full_text(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        values = self.tree.item(item, "values")
        
        detail_win = tk.Toplevel(self)
        detail_win.title("Detail File")
        detail_win.geometry("600x300")
        
        txt = tk.Text(detail_win, wrap="word", padx=10, pady=10, 
                      bg="#1e1e1e", fg="#d4d4d4", font=("Segoe UI", 10))
        txt.pack(fill="both", expand=True)
        
        txt.insert("end", f"FILENAME:\n{values[0]}\n\n")
        txt.insert("end", f"TITLE:\n{values[1]}\n\n")
        txt.insert("end", f"KEYWORDS:\n{values[2]}\n")
        txt.config(state="disabled")

    # -------------------- Start -------------------- #
    def _start(self):
        if self._processing:
            return
        ok, err_msg = check_exiftool()
        if not ok:
            messagebox.showerror("ExifTool tidak siap", err_msg)
            return

        input_dir = self.input_var.get().strip()
        if not os.path.isdir(input_dir):
            messagebox.showerror("Error", "Folder input tidak valid.")
            return

        mode = self.mode_var.get()
        output_dir = self.output_var.get().strip()

        if mode != "inplace":
            if not output_dir:
                messagebox.showerror("Error",
                                     "Folder output wajib diisi.")
                return
            try:
                os.makedirs(output_dir, exist_ok=True)
            except OSError as e:
                messagebox.showerror(
                    "Error", f"Tidak bisa membuat output folder:\n{e}")
                return

        if self.upscale_var.get():
            upscaler = self.upscaler_path_var.get().strip() or find_upscaler()
            if not upscaler:
                messagebox.showerror(
                    "Upscaler tidak ditemukan",
                    "Pilih path upscaler exe di Advanced tab.\n\n"
                    "Download Real-ESRGAN:\n"
                    "https://github.com/xinntao/Real-ESRGAN/releases")
                return

        files = find_images(input_dir, self.recursive_var.get())
        if not files:
            messagebox.showinfo("Info",
                                "Tidak ada gambar yang didukung.")
            return

        self._processing = True
        self.process_btn.config(state="disabled")
        self._total_files = len(files)
        self.progress["maximum"] = len(files)
        self.progress["value"] = 0
        self.progress_label.config(text=f"0 / {len(files)} (0%)")
        self._log(f"▶ Mulai {len(files)} file…")
        
        threading.Thread(target=self._worker, args=(files,),
                         daemon=True).start()

    # -------------------- Upscale -------------------- #
    def _upscale_image(self, src, dst, scale, model):
        upscaler = self.upscaler_path_var.get().strip() or find_upscaler()
        if not upscaler:
            return False
        exe_name = Path(upscaler).name.lower()
        if "upscayl" in exe_name:
            cmd = [upscaler, "-i", str(src), "-o", str(dst),
                   "-s", str(scale), "-m", model]
        else:
            cmd = [upscaler, "-i", str(src), "-o", str(dst),
                   "-s", str(scale), "-n", model]
        try:
            flags = (subprocess.CREATE_NO_WINDOW
                     if sys.platform == "win32" else 0)
            r = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=1200, creationflags=flags)
            if r.returncode != 0:
                self._log(f"✗ Upscale {Path(src).name}: "
                          f"{r.stderr.strip()[:200]}")
                return False
            return Path(dst).exists()
        except subprocess.TimeoutExpired:
            self._log(f"✗ Upscale timeout: {Path(src).name}")
            return False
        except Exception as e:
            self._log(f"✗ Upscale error: {e}")
            return False

    # -------------------- Worker -------------------- #
    def _worker(self, files):
        author = self.author_var.get().strip() or "AI Generated"
        title_fmt = self.title_fmt_var.get()
        alt_text = self.alt_var.get().strip()
        category = self.category_var.get()
        cat_num = None
        if category and category != "— none —":
            cat_num = category.split("·")[0].strip()

        kw_list = self._collect_keywords()
        kw_str = ", ".join(kw_list)

        mode = self.mode_var.get()
        in_dir = Path(self.input_var.get())
        out_dir = (Path(self.output_var.get())
                   if mode != "inplace" else None)
        do_backup = self.backup_var.get() and mode == "inplace"
        do_dup = self.dup_check_var.get()
        do_upscale = self.upscale_var.get()
        upscale_model = self.upscale_model_var.get()
        do_rename = self.rename_enable_var.get()
        rename_pattern = self.rename_pattern_var.get().strip()
        start_num = self.start_num_var.get()

        seen_hashes = {}
        if do_dup and out_dir and out_dir.exists():
            for existing in out_dir.rglob("*"):
                if existing.is_file() and \
                        existing.suffix.lower() in SUPPORTED_EXT:
                    try:
                        seen_hashes[file_hash(existing)] = str(existing)
                    except Exception:
                        pass
            self._log(f"🔎 Duplikat terindeks di output: "
                      f"{len(seen_hashes)}")

        next_num = start_num
        if do_rename:
            scan_dir = out_dir if mode != "inplace" else in_dir
            prefix = (rename_pattern.split("{")[0]
                      if "{" in rename_pattern else rename_pattern)
            next_num = get_next_number(scan_dir, prefix, start_num)
            self._log(f"📛 Rename dimulai dari nomor: {next_num}")

        success, errors, results = 0, [], []

        for i, f in enumerate(files, 1):
            try:
                if do_dup:
                    h = file_hash(f)
                    if h in seen_hashes:
                        self._log(f"⏭ SKIP duplikat: {f.name}")
                        self.after(0, self._set_progress, i)
                        continue
                    seen_hashes[h] = f.name

                if mode == "inplace":
                    target = f
                else:
                    try:
                        rel = f.parent.relative_to(in_dir)
                    except ValueError:
                        rel = Path(".")
                    target = out_dir / rel / f.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if mode == "copy":
                        shutil.copy2(f, target)
                    elif mode == "move":
                        shutil.move(f, target)

                # FIX EXTENSION
                real_ext = None
                try:
                    with open(target, "rb") as fp:
                        header = fp.read(12)
                        if header.startswith(b"\x89PNG\r\n\x1a\n"):
                            real_ext = ".png"
                        elif header.startswith(b"\xff\xd8\xff"):
                            real_ext = ".jpg"
                        elif header.startswith(b"RIFF") and header[8:12] == b"WEBP":
                            real_ext = ".webp"
                except Exception:
                    pass

                if real_ext and target.suffix.lower() not in (real_ext, ".jpeg" if real_ext == ".jpg" else real_ext):
                    new_target = target.with_suffix(real_ext)
                    if new_target.exists():
                        new_target.unlink()
                    target.rename(new_target)
                    self._log(f"🔄 Fix Ekstensi: {target.name} → {new_target.name}")
                    target = new_target

                if do_backup:
                    bak = target.with_suffix(
                        target.suffix + "_original")
                    if not bak.exists():
                        shutil.copy2(target, bak)

                if do_upscale:
                    upscaled = target.with_name(
                        f"{target.stem}_upsc{target.suffix}")
                    if self._upscale_image(target, upscaled, 4,
                                            upscale_model):
                        try:
                            target.unlink()
                            upscaled.rename(target)
                            self._log(f"⬆ Upscaled: {target.name}")
                        except Exception as e:
                            self._log(f"⚠ Gagal replace upscaled: {e}")

                # METADATA VIA EXIFTOOL
                title = format_text(target.stem, title_fmt)
                
                # Format deskripsi: ganti _ dan - menjadi spasi, rapikan spasi ganda
                desc_text = re.sub(r"[_\-]+", " ", target.stem)
                description = re.sub(r"\s+", " ", desc_text).strip()
                
                alt = alt_text or title

                exe = get_exiftool_path()
                cmd = [exe, "-charset", "utf8",
                       "-overwrite_original", "-m", "-sep", ", "]
                
                # HAPUS DULU semua tag keyword lama untuk mencegah duplikasi
                cmd += [
                    "-Keywords=", 
                    "-Subject=", 
                    "-IPTC:Keywords=", 
                    "-XMP-dc:Subject="
                ]
                
                cmd += [
                    f"-Title={title}",
                    f"-XMP-dc:Title={title}",
                    f"-Description={description}",
                    f"-XMP-dc:Description={description}",
                    f"-IPTC:Caption-Abstract={description}",
                    f"-XMP-photoshop:Headline={title}",
                    f"-Author={author}",
                    f"-XMP-dc:Creator={author}",
                    f"-IPTC:By-line={author}",
                    f"-XMP-iptcCore:AltTextAccessibility={alt}",
                ]
                
                if kw_str:
                    # HANYA tulis ke XMP-dc:Subject untuk mencegah ImStocker membaca ganda
                    cmd.append(f"-XMP-dc:Subject={kw_str}")
                    
                if cat_num:
                    cmd += [f"-XMP-photoshop:Category={cat_num}"]
                cmd.append(str(target))

                flags = (subprocess.CREATE_NO_WINDOW
                         if sys.platform == "win32" else 0)
                r = subprocess.run(cmd, capture_output=True,
                                   text=True, creationflags=flags)
                if r.returncode != 0:
                    raise RuntimeError(
                        (r.stderr or r.stdout).strip())

                if do_rename:
                    new_path = target
                    for _guard in range(10000):
                        if "{" in rename_pattern:
                            new_name = rename_pattern.format(
                                num=next_num)
                        else:
                            new_name = f"{rename_pattern}_{next_num}"
                        new_path = target.parent / \
                                   (new_name + target.suffix)
                        if not new_path.exists() or \
                                new_path == target:
                            break
                        next_num += 1
                    if new_path != target:
                        old_name = target.name
                        target.rename(new_path)
                        self._log(f"📝 {old_name} → {new_path.name}")
                        target = new_path
                    next_num += 1

                success += 1
                results.append({
                    "filename": target.name,
                    "title": title,
                    "description": description,
                    "keywords": kw_str,
                    "author": author,
                    "category": cat_num or "",
                    "alt": alt,
                    "path": str(target),
                })

            except Exception as e:
                errors.append(f"{f.name}: {e}")
                self._log(f"✗ {f.name}: {e}")

            self.after(0, self._set_progress, i)

        self._last_results = results
        self.after(0, self._on_done, success, errors)

    # -------------------- Done -------------------- #
    def _on_done(self, success, errors):
        self._processing = False
        self.process_btn.config(state="normal")
        self._log(f"✔ Selesai. Sukses={success}, Error={len(errors)}")
        if errors:
            messagebox.showwarning(
                "Selesai dengan error",
                f"Sukses: {success}\nGagal: {len(errors)}\n\n"
                f"5 error pertama:\n" + "\n".join(errors[:5]))
        else:
            messagebox.showinfo(
                "Selesai", f"Berhasil memproses {success} file.")

    # -------------------- CSV -------------------- #
    def _export_csv(self):
        if not self._last_results:
            messagebox.showinfo(
                "Info", "Belum ada hasil. Jalankan proses dulu.")
            return
        path = filedialog.asksaveasfilename(
            title="Simpan CSV (Adobe Stock)",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="adobe_stock_metadata.csv")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as fp:
            w = csv.DictWriter(fp, fieldnames=[
                "Filename", "Title", "Description", "Keywords",
                "Category", "Author", "Alt Text"])
            w.writeheader()
            for r in self._last_results:
                w.writerow({
                    "Filename": r["filename"],
                    "Title": r["title"],
                    "Description": r["description"],
                    "Keywords": r["keywords"],
                    "Category": r["category"],
                    "Author": r["author"],
                    "Alt Text": r["alt"],
                })
        messagebox.showinfo("Sukses", f"CSV tersimpan:\n{path}")


# ============================================================ #
if __name__ == "__main__":
    app = App()
    app.mainloop()
# AI Metadata Manager

Aplikasi desktop (Windows) untuk memproses batch metadata gambar AI (Adobe Stock workflow). Dilengkapi dengan **auto-rename**, **validasi resolusi 4MP**, **deteksi duplikat (SQLite)**, **auto-upscale**, **NLP keyword generation (Ollama + NLTK)**, **organize subfolder**, dan **smart text truncation**.

---

## ✨ Fitur Utama

| Fitur | Deskripsi |
|---|---|
| **Batch Metadata** | Title, Description, Keywords, Author, Alt Text, Category |
| **Auto-Rename** | Pattern `demhndAIStock_{num:05d}` (bisa diubah) |
| **Duplicate Detection** | Berbasis SQLite (anti-file-tumpuk) |
| **Auto-Convert JPEG** | Konversi otomatis ke JPEG (wajib untuk ilustrasi Adobe Stock) |
| **Validasi 4 MP** | Deteksi resolusi < 4 MP (standar minimum Adobe Stock) |
| **Auto-Upscale 2x/3x/4x** | Menggunakan Real-ESRGAN (realcugan / upscayl support) |
| **NLP Hybrid** | Ollama (konteks) + NLTK WordNet (sinonim) opsional |
| **Keyword Blacklist** | Filter otomatis merek dagang, artis, isu sensitif, dll |
| **Smart Truncate** | Potong Description/Title < 200 char di batas kata |
| **Organize Subfolder** | File 1-100 → `100/`, 101-200 → `200/`, dst |
| **Drag & Drop** | Drag folder langsung ke aplikasi |
| **Dark Mode** | UI modern dengan `ttkbootstrap` |
| **Notifikasi Suara** | Bunyi modem dial-up saat selesai |

---

## 📥 File Pendukung (Wajib / Opsional)

Aplikasi ini membutuhkan file pihak ketiga yang harus diunduh secara terpisah.

### 1. **ExifTool** (Wajib)
- Download: [https://exiftool.org/](https://exiftool.org/) → pilih **Windows Executable**
- Ekstrak ZIP, lalu taruh `exiftool.exe` **beserta folder `exiftool_files`** di folder yang sama dengan `AI-Metadata-Manager.exe`.
- ⚠️ **Jangan pisahkan `exiftool.exe` dengan folder `exiftool_files`** — keduanya harus selalu berdampingan.

### 2. **Ollama** (Opsional - untuk NLP Keyword Generation)
- Download: [https://ollama.com/](https://ollama.com/)
- Setelah install, unduh model yang direkomendasikan untuk GPU 6GB (GTX 1660 Super ke atas):

  ```powershell
  ollama pull llama3.2
  # atau alternatif:
  ollama pull qwen2.5:3b
  ollama pull phi4-mini
  ```

- Aplikasi akan otomatis mendeteksi model yang terinstall di dropdown.

### 3. **Real-ESRGAN** (Opsional - untuk fitur Upscale)
- Download: [Real-ESRGAN Windows](https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip)
- Ekstrak ke folder mana saja (mis. `D:\Tools\realesrgan\`).
- Di aplikasi (tab Advanced), arahkan path ke `realesrgan-ncnn-vulkan.exe`.

### 4. **WordNinja Data + NLTK Data** (Hanya untuk Developer / Build dari Source)
Dibutuhkan agar fitur pemecah kata dan sinonim NLTK bisa berjalan di `.exe`. Lihat bagian **Build dari Source** di bawah.

---

## 🚀 Cara Menggunakan

1. Buka `AI-Metadata-Manager.exe`.
2. Tentukan **Input folder** (gambar asli AI) dan **Output folder** (hasil).
3. Isi **Author** (default: `demhnd`) dan pastikan centang keyword **"AI, AI Generated"**.
4. (Opsional) Di tab **Advanced**:
   - Centang **Validasi 4 MP** & **Auto-Upscale** jika ingin memperbesar gambar otomatis.
   - Centang **Konversi ke JPEG** (wajib untuk Adobe Stock Ilustrasi).
   - Aktifkan **NLP Hybrid** dan pilih model Ollama.
   - Centang **Gunakan NLTK WordNet** jika ingin ekspansi sinonim (opsional, bisa menghasilkan kata aneh).
   - Atur **Max Title & Description Length** (default: 200 untuk Adobe Stock).
   - Atur **Organize Subfolder** (Batch of 100 / 500 / 1000, Monthly, Daily).
   - Atur pola **Batch Rename** dan **Start Number**.
5. Klik **▶ Mulai Proses**. Tunggu hingga bunyi notifikasi selesai berbunyi.
6. (Opsional) Klik **📄 Export CSV** untuk mendapatkan file metadata siap-upload ke Adobe Stock Contributor.

---

## 📁 Struktur Folder Output (Contoh)

Jika memilih **"Batch of 100"**, folder output akan otomatis terorganisir:

```
📁 Output/
   📁 100/       ← file ID 1-100
   📁 200/       ← file ID 101-200
   📁 300/       ← file ID 201-300
   ...
```

Sangat berguna untuk mengelola portofolio **100.000+ file** — memudahkan upload batch, backup, dan pencarian.

---

## 🛠️ Build dari Source Code (Untuk Developer)

### Prasyarat
- Python 3.10+ (install dari [python.org](https://www.python.org/downloads/) — centang "Add to PATH")
- Git (opsional, untuk clone repo)
- ExifTool + Real-ESRGAN (seperti di atas)

### 1. Clone & Install Dependencies

```powershell
git clone <repo-url> ai-metadata-manager
cd ai-metadata-manager

python -m venv .venv
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

Isi `requirements.txt`:

```txt
Pillow>=10.0.0
ttkbootstrap>=1.14.0
tkinterdnd2>=0.4.0
ollama>=0.4.0
nltk>=3.9.0
wordninja>=2.1.0
```

### 2. Download Data WordNinja

```powershell
mkdir wn_data -Force
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/keredson/wordninja/master/wordninja/wordninja_words.txt.gz" -OutFile "wn_data\wordninja_words.txt.gz"
```

### 3. Download Data NLTK (WordNet)

```powershell
python -c "import nltk; nltk.download('wordnet', download_dir='nltk_data'); nltk.download('omw-1.4', download_dir='nltk_data')"
```

### 4. Build ke EXE

```powershell
pip install pyinstaller

pyinstaller --onefile --windowed ^
  --name "AI-Metadata-Manager" ^
  --icon=icon.ico ^
  --collect-all tkinterdnd2 ^
  --collect-all ttkbootstrap ^
  --add-data "wn_data\wordninja_words.txt.gz;wordninja" ^
  --add-data "nltk_data;nltk_data" ^
  ai_metadata_manager.py
```

File `.exe` akan tersedia di folder `dist/`.

> ⚠️ **Penting:** Flag `--add-data` wajib disertakan. Tanpa flag ini, aplikasi akan error saat dijalankan karena file data `wordninja` dan `nltk` tidak ikut ter-bundle.

---

## 🎯 Tips Workflow Profesional

1. **Jangan hapus folder Output** — aplikasi menggunakan database `riwayat_proses.db` untuk cek duplikat. Jika dihapus, aplikasi akan menganggap semua file sebagai "baru".
2. **Backup `riwayat_proses.db`** secara berkala — berisi "memori" aplikasi.
3. **Upload per batch** — setiap folder `100/`, `200/`, dst bisa di-upload terpisah ke Adobe Stock Contributor agar mudah tracking.
4. **Selalu Export CSV** setiap batch — backup metadata dalam bentuk spreadsheet.
5. **Cek keyword di ImStocker Studio** — untuk melengkapi sampai 49 keyword dan review visual.

---

## 📄 Lisensi

MIT License — bebas digunakan dan dimodifikasi.

---

## 🐛 Troubleshooting

| Error | Solusi |
|---|---|
| `ExifTool tidak ditemukan` | Pastikan `exiftool.exe` + folder `exiftool_files` ada di folder `.exe` |
| `FileNotFoundError: wordninja_words.txt.gz` | Build ulang dengan flag `--add-data "wn_data\wordninja_words.txt.gz;wordninja"` |
| `FileNotFoundError: nltk_data` | Build ulang dengan flag `--add-data "nltk_data;nltk_data"` |
| `Ollama Error: Connection refused` | Jalankan `ollama serve` atau pastikan Ollama berjalan di background |
| `Model Kosong` | Pilih model di dropdown tab Advanced (klik tombol 🔄 untuk refresh) |
| Keyword aneh muncul | Tambahkan ke `KEYWORD_BLACKLIST` atau matikan NLTK |
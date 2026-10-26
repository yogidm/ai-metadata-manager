# AI Metadata Manager

Aplikasi desktop (Windows) untuk memproses batch metadata gambar AI (Adobe Stock workflow). Dilengkapi dengan auto-rename, validasi resolusi 4MP, deteksi duplikat, dan auto-upscale.

## 📥 File Pendukung (Wajib Download)

Aplikasi ini membutuhkan file pihak ketiga yang harus diunduh secara terpisah:

1. **ExifTool** (Wajib - untuk menulis metadata)
   - Download: [https://exiftool.org/](https://exiftool.org/) (Pilih *Windows Executable*)
   - Ekstrak file ZIP, lalu taruh `exiftool.exe` dan folder `exiftool_files` di folder yang sama dengan `AI-Metadata-Manager.exe`.

2. **Real-ESRGAN** (Opsional - untuk fitur Upscale 4x)
   - Download: [Real-ESRGAN Windows](https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip)
   - Ekstrak ke folder mana saja. Nanti arahkan path-nya ke `realesrgan-ncnn-vulkan.exe` melalui aplikasi (tab Advanced).

## 🚀 Cara Menggunakan

1. Buka `AI-Metadata-Manager.exe`.
2. Tentukan **Input folder** (gambar asli AI) dan **Output folder** (hasil).
3. Isi **Author** (default: "AI Generated") dan pastikan centang keyword "AI, AI Generated".
4. (Opsional) Di tab **Advanced**:
   - Centang *Auto-Upscale* jika ingin memperbesar gambar di bawah 4 MP.
   - Atur pola *Batch Rename* (default: `demhndAIStock_{num:05d}`).
5. Klik **▶ Mulai Proses**. Tunggu hingga bunyi notifikasi selesai berbunyi.
6. (Opsional) Klik **📄 Export CSV** untuk mendapatkan file metadata yang siap di-upload massal ke Adobe Stock Contributor.

## 🛠️ Build dari Source Code (Untuk Developer)

Jika ingin melakukan *build* ulang dari file Python:

```powershell
# Install dependencies
pip install -r requirements.txt

# Build ke EXE
pyinstaller --onefile --windowed --name "AI-Metadata-Manager" --icon=icon.ico --collect-all tkinterdnd2 --collect-all ttkbootstrap ai_metadata_manager.py
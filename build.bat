@echo off
pip install pyinstaller
pyinstaller --onefile --windowed ^
  --name "AI-Metadata-Manager" ^
  --icon=icon.ico ^
  --collect-all tkinterdnd2 ^
  --collect-all ttkbootstrap ^
  ai_metadata_manager.py
echo.
echo Selesai. File .exe ada di folder "dist\"
pause
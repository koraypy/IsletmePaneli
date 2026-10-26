@echo off
chcp 65001 >nul
echo === Isletme Paneli: .exe olusturuluyor ===
python --version >nul 2>&1 || (echo Python bulunamadi. https://www.python.org/downloads/ adresinden kurun ^(Add python.exe to PATH kutusunu isaretleyin^). & pause & exit /b 1)
python -m pip install --upgrade pip pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --windowed --name IsletmePaneli app.py
echo.
echo Hazir: dist\IsletmePaneli.exe
pause

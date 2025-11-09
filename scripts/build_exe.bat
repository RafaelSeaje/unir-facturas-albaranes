@echo off
REM =========================================================
REM Script de compilación para crear ejecutable con PyInstaller
REM =========================================================
cd ..
pyinstaller --onefile --noconsole --name "Unir facturas con albaranes" src/procesa_facturas_y_albaranes.py
pause

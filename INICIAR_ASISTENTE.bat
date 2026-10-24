@echo off
title Asistente de Voz Local - RTX 4060
cd /d "%~dp0"
echo =======================================================
echo    INICIANDO ASISTENTE DE VOZ LOCAL (WHISPER + OLLAMA)
echo =======================================================
echo.

where uv >nul 2>nul
if %ERRORLEVEL% equ 0 (
    uv run python asistente.py
    goto fin
)

if exist "%USERPROFILE%\.local\bin\uv.exe" (
    "%USERPROFILE%\.local\bin\uv.exe" run python asistente.py
    goto fin
)

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" asistente.py
    goto fin
)

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    python asistente.py
    goto fin
)

echo [ERROR] No se encontro 'uv' ni 'python' en el sistema.

:fin
pause

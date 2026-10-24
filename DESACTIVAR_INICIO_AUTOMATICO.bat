@echo off
chcp 65001 > nul
set "LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Asistente de Voz.lnk"
if exist "%LNK%" (
    del /f /q "%LNK%"
    echo [OK] Inicio automatico desactivado correctamente.
) else (
    echo [INFO] El asistente no estaba configurado en el inicio de Windows.
)
pause

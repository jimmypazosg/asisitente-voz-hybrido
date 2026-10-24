$WshShell = New-Object -ComObject WScript.Shell
$rutaStartup = [System.Environment]::GetFolderPath('Startup')
$lnkPath = Join-Path $rutaStartup 'Asistente de Voz.lnk'

$targetBat = Join-Path $PSScriptRoot 'INICIAR_ASISTENTE.bat'

$Shortcut = $WshShell.CreateShortcut($lnkPath)
$Shortcut.TargetPath = $targetBat
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.WindowStyle = 7 # 7 = Minimizada en segundo plano
$Shortcut.Save()

Write-Host "========================================================"
Write-Host " [OK] Acceso directo de inicio automatico creado en:"
Write-Host " $lnkPath"
Write-Host "========================================================"

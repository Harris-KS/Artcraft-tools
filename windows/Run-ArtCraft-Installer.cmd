@echo off
setlocal
powershell.exe -NoLogo -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0Install-ArtCraft.ps1" %*
set "installer_result=%errorlevel%"
echo.
pause
exit /b %installer_result%

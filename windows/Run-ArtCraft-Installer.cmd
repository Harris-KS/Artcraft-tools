@echo off
setlocal
if exist "%~dp0Install-ArtCraft.ps1" goto run_installer
echo The complete Windows installer folder is required.
echo Install-ArtCraft.ps1 must be beside this launcher.
echo.
echo Download the complete ZIP:
echo https://github.com/Harris-KS/Artcraft-tools/archive/refs/heads/main.zip
echo Extract All, open the windows folder, and run this launcher there.
echo.
pause
exit /b 2
:run_installer
powershell.exe -NoLogo -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0Install-ArtCraft.ps1" %*
set "installer_result=%errorlevel%"
echo.
pause
exit /b %installer_result%

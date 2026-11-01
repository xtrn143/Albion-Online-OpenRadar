@echo off
cd /d "%~dp0"
sc query npcap >nul 2>&1 || (
  echo Npcap is not installed. Please install it from https://npcap.com
  pause
)
start "" "%~dp0OpenRadar\OpenRadar.exe"
timeout /t 4 >nul
start "" "%~dp0AlbionAware.exe"

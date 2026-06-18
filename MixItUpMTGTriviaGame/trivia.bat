@echo off
REM Wrapper script for the MTG Trivia Game server.
REM Double-click to start the local trivia server. Close this window to stop.

cd /d "%~dp0"

REM Prefer the Python launcher (py), fall back to python on PATH.
REM This avoids the Microsoft Store stub when Python isn't actually installed.
where py >nul 2>nul
if %errorlevel%==0 (
    py trivia_server.py %*
    exit /b %errorlevel%
)

where python >nul 2>nul
if %errorlevel%==0 (
    python trivia_server.py %*
    exit /b %errorlevel%
)

echo Python is not installed on this machine. Install from https://www.python.org/downloads/ and tick "Add Python to PATH".
pause
exit /b 1

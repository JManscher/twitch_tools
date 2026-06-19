@echo off
REM Wrapper for the MTG Trivia question editor (localhost-only web app).
REM Double-click to start. Open http://localhost:8766/ in your browser.
REM Close this window to stop. Restart the trivia server to apply edits.

cd /d "%~dp0"

REM Prefer the Python launcher (py), fall back to python on PATH.
REM This avoids the Microsoft Store stub when Python isn't actually installed.
where py >nul 2>nul
if %errorlevel%==0 (
    py editor_server.py %*
    exit /b %errorlevel%
)

where python >nul 2>nul
if %errorlevel%==0 (
    python editor_server.py %*
    exit /b %errorlevel%
)

echo Python is not installed on this machine. Install from https://www.python.org/downloads/ and tick "Add Python to PATH".
pause
exit /b 1

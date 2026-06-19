@echo off
REM Wrapper script for Mix It Up external program
REM Usage: ask.bat [optional question text]

cd /d "%~dp0"

REM Prefer the Python launcher (py), fall back to python on PATH.
REM This avoids the Microsoft Store stub when Python isn't actually installed.
where py >nul 2>nul
if %errorlevel%==0 (
    py ask_command.py %*
    exit /b %errorlevel%
)

where python >nul 2>nul
if %errorlevel%==0 (
    python ask_command.py %*
    exit /b %errorlevel%
)

echo The cards are silent (Python is not installed on this machine).
exit /b 1

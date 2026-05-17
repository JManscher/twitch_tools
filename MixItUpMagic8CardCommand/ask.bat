@echo off
REM Wrapper script for Mix It Up external program
REM Usage: ask.bat [optional question text]

cd /d "%~dp0"
python ask_command.py %*

@echo off
REM Wrapper script for Mix It Up external program
REM Usage: game.bat [optional game name]

cd /d "%~dp0"
python game_command.py %*

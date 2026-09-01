@echo off
REM Copy to the consumer repo root. Humans on Windows may double-click this file.
REM Agents must not run it. Use: python doqs/scripts/syson.py ui
cd /d "%~dp0"
echo Starting SysON control panel. Close this window to quit.
python doqs\scripts\syson.py ui

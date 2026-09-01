@echo off
REM Copy to the consumer repo root. Humans on Windows may double-click this file.
REM Agents must not run it (pause waits for a key). Use: bash setup-tooling.sh
cd /d "%~dp0"
git submodule sync --recursive
if errorlevel 1 exit /b 1
git submodule update --init --recursive --remote
if errorlevel 1 exit /b 1
pause

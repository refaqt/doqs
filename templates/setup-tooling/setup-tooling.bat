@echo off
REM SPDX-License-Identifier: GPL-3.0-or-later
REM Copy to the consumer repo root. Humans on Windows may double-click this file.
REM Agents must not run it (pause waits for a key). Use: bash setup-tooling.sh
cd /d "%~dp0"
git submodule sync --recursive
if errorlevel 1 exit /b 1
REM Check out every submodule at its recorded pin. Extracted modules under
REM modules\ stay SHA-pinned, so this must not use --remote.
git submodule update --init --recursive
if errorlevel 1 exit /b 1
REM Only the tooling submodules track main. No --recursive here: it would reach
REM doqs\.agents and move it off the pin doqs records.
git submodule update --remote -- doqs .agents
if errorlevel 1 exit /b 1
python doqs\scripts\install_root_tools.py
if errorlevel 1 exit /b 1
pause

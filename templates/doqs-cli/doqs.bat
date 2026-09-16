@echo off
REM SPDX-License-Identifier: GPL-3.0-or-later
REM The one doqs command. Run from the repo root:
REM   doqs.bat check
REM   doqs.bat list
REM Installed by doqs\scripts\install_root_tools.py.
cd /d "%~dp0"
python doqs\doqs.py %*
if errorlevel 1 exit /b 1

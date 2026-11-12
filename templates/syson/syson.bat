@echo off
REM SPDX-FileCopyrightText: 2025-2026 Refaqt (BE 0804.145.539) and contributors
REM SPDX-License-Identifier: GPL-3.0-or-later
REM Copy to the consumer repo root. Humans on Windows may double-click this file.
REM Agents must not run it. Use: python doqs/scripts/syson.py ui
cd /d "%~dp0"
echo Starting SysON control panel. Close this window to quit.
python doqs\scripts\syson.py ui

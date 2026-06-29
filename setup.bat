@echo off
REM ------------------------------------------------------------------
REM  ITECH PSU Driver — Windows Setup
REM  Creates a Python virtual environment, installs dependencies,
REM  and generates a run.bat launcher script.
REM ------------------------------------------------------------------

setlocal
set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%PSUvenv"

echo ========================================
echo   ITECH PSU Driver — Environment Setup
echo ========================================
echo.

REM 1. Create virtual environment
if exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [*] Virtual environment already exists at %VENV_DIR%
) else (
    echo [+] Creating virtual environment...
    python -m venv "%VENV_DIR%"
)

REM 2. Activate and install dependencies
echo [+] Installing dependencies...
call "%VENV_DIR%\Scripts\activate.bat"
pip install --upgrade pip --quiet
pip install pyvisa pyvisa-py pyusb tabulate asciichartpy --quiet

echo [✓] Dependencies installed: pyvisa, pyvisa-py, pyusb, tabulate, asciichartpy

REM 3. Generate run.bat
echo [+] Creating run.bat...
(
echo @echo off
echo REM ------------------------------------------------------------------
echo REM  ITECH PSU Driver — Launcher
echo REM  Activates the virtual environment and runs the CLI.
echo REM  All arguments are forwarded to psu_cli.py.
echo REM
echo REM  Usage:
echo REM    run.bat --live                  Launch interactive dashboard
echo REM    run.bat --set 24 5 --enable 1   One-shot command
echo REM    run.bat --measure               Read telemetry
echo REM    run.bat --help                  Show all options
echo REM ------------------------------------------------------------------
echo setlocal
echo set "SCRIPT_DIR=%%~dp0"
echo call "%%SCRIPT_DIR%%PSUvenv\Scripts\activate.bat"
echo python "%%SCRIPT_DIR%%psu_cli.py" %%*
) > "%SCRIPT_DIR%run.bat"

echo [✓] Created run.bat
echo.
echo ========================================
echo   Setup complete!
echo   Launch with:  run.bat --live
echo ========================================

endlocal

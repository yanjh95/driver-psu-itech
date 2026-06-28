#!/usr/bin/env bash
# ------------------------------------------------------------------
#  ITECH PSU Driver — Linux / macOS Setup
#  Creates a Python virtual environment, installs dependencies,
#  and generates a run.sh launcher script.
# ------------------------------------------------------------------
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/PSUvenv"

echo "========================================"
echo "  ITECH PSU Driver — Environment Setup"
echo "========================================"
echo ""

# 1. Create virtual environment
if [ -d "$VENV_DIR" ]; then
    echo "[*] Virtual environment already exists at $VENV_DIR"
else
    echo "[+] Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# 2. Install system-level USB library (required for USB TMC instruments)
if command -v apt-get &> /dev/null; then
    echo "[+] Installing libusb (system dependency for USB instruments)..."
    sudo apt-get install -y libusb-1.0-0-dev > /dev/null 2>&1 || echo "[!] Could not install libusb — USB instruments may not be detected. Run: sudo apt-get install libusb-1.0-0-dev"
elif command -v brew &> /dev/null; then
    echo "[+] Installing libusb (system dependency for USB instruments)..."
    brew install libusb > /dev/null 2>&1 || echo "[!] Could not install libusb — USB instruments may not be detected. Run: brew install libusb"
fi

# 3. Activate and install Python dependencies
echo "[+] Installing Python dependencies..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip --quiet
pip install pyvisa pyvisa-py pyusb tabulate --quiet

echo "[✓] Dependencies installed: pyvisa, pyvisa-py, pyusb, tabulate"

# 4. Install udev rule for ITECH USB access without sudo (Linux only)
UDEV_RULE="/etc/udev/rules.d/99-itech-psu.rules"
if [ -f /etc/udev/rules.d ] || [ -d /etc/udev/rules.d ]; then
    if [ ! -f "$UDEV_RULE" ]; then
        echo "[+] Installing udev rule for ITECH USB instruments (requires sudo)..."
        echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="2ec7", MODE="0666"' | sudo tee "$UDEV_RULE" > /dev/null
        sudo udevadm control --reload-rules 2>/dev/null || true
        sudo udevadm trigger 2>/dev/null || true
        echo "[✓] Udev rule installed — ITECH PSUs are now accessible without sudo"
        echo "[!] If the PSU is already plugged in, unplug and replug it (or re-attach via usbipd)"
    else
        echo "[*] Udev rule already installed"
    fi
fi

# 3. Generate run.sh
RUN_SCRIPT="$SCRIPT_DIR/run.sh"
cat > "$RUN_SCRIPT" << 'RUNEOF'
#!/usr/bin/env bash
# ------------------------------------------------------------------
#  ITECH PSU Driver — Launcher
#  Activates the virtual environment and runs the CLI.
#  All arguments are forwarded to psu_cli.py.
#
#  Usage:
#    ./run.sh --live                  Launch interactive dashboard
#    ./run.sh --set 24 5 --enable 1   One-shot command
#    ./run.sh --measure               Read telemetry
#    ./run.sh --help                  Show all options
# ------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/PSUvenv/bin/activate"
python3 "$SCRIPT_DIR/psu_cli.py" "$@"
RUNEOF
chmod +x "$RUN_SCRIPT"

echo "[✓] Created run.sh"
echo ""
echo "========================================"
echo "  Setup complete!"
echo "  Launch with:  ./run.sh --live"
echo "========================================"

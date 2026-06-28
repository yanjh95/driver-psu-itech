# ITECH PSU Python Driver & TUI

A terminal application for remotely controlling ITECH Programmable Power Supplies over USB. Provides a real-time interactive dashboard and one-shot CLI commands.

## Setup

### Quick Setup (Recommended)
Run the setup script to create a virtual environment, install dependencies, and generate a launcher script.

**Windows (PowerShell):**
```powershell
setup.bat
```

**Linux / macOS / WSL:**
```bash
chmod +x setup.sh
./setup.sh
```

> **WSL Users:** You must attach the PSU to WSL via `usbipd` before running:
> ```powershell
> # In PowerShell (Admin)
> usbipd list                          # Find the PSU bus ID
> usbipd attach --wsl --busid <BUS_ID>
> ```

### Registering a New PSU
Before first use, register the physical safety limits of your power supply. This is a one-time interactive process.
```bash
python3 register_psu.py
```
You will be prompted for the model name, max voltage, max current, and max power ratings. These limits are stored in `psu_registry.json` and enforced at runtime to prevent exceeding hardware capabilities.

---

## Interactive Dashboard

Launch the live TUI dashboard to control the PSU like a front panel:

```bash
./run.sh --live       # Linux / WSL
run.bat --live        # Windows
```

**Controls:**
| Key | Action |
|:---|:---|
| **↑ / ↓** | Navigate parameter fields (Voltage, Current, OV Limit, OC Limit) |
| **0-9 / .** | Enter edit mode and type a new setpoint value |
| **Enter** | Submit the edited value to the PSU |
| **E** | Toggle output ON / OFF |
| **ESC** | Cancel current edit |
| **Q** | Safely power down and exit |

---

## CLI Commands

Execute one-off commands without launching the dashboard.

| Flag | Arguments | Description |
|:---|:---|:---|
| `-s`, `--set` | `VOLTS AMPS` | Set voltage and current setpoints |
| `-p`, `--protect` | `OV OC` | Set overvoltage and overcurrent protection limits |
| `-e`, `--enable` | `0` or `1` | Disable or enable the output |
| `-m`, `--measure` | — | Print voltage, current, and power telemetry |
| `--errors` | — | Sweep the hardware error queue |
| `--live` | — | Launch the interactive TUI dashboard |
| `--device` | `VISA_STRING` | Target a specific PSU when multiple are connected |

**Examples:**
```bash
# Set 24V / 5A and enable output
./run.sh --set 24 5 --enable 1

# Read live telemetry
./run.sh --measure

# Set protection limits (26V OVP, 5.5A OCP)
./run.sh -p 26 5.5

# Check for hardware errors
./run.sh --errors

# Target a specific PSU by VISA resource string
./run.sh --device "USB0::0x2EC7::0x6900::800776011807210025::INSTR" --measure
```

---

## Developer Reference

For driver API documentation and code integration examples, see [DEVELOPER.md](DEVELOPER.md).

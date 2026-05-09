# ITECH PSU Python Driver & TUI

A Python Hardware Abstraction Layer (HAL) and interactive Text User Interface (TUI) for remotely controlling ITECH Programmable Power Supplies over a SCPI connection.

## Features

- **Driver API**: Standardized Python methods for interacting with the hardware (`set()`, `enable()`, `measure_voltage()`).
- **Hardware Registry**: Enforces physical boundaries (voltage, current, power limits) based on connected hardware profiles mapped in `psu_registry.json`.
- **Fault Handling**: Actively polls the SCPI error queue and raises exceptions on hardware faults to prevent cascading sequence propagation.
- **Live Dashboard**: A terminal-based user interface that provides real-time telemetry mapping and active parameter modification.

## Setup & Installation

This project requires `pyvisa` for USB/Serial SCPI transport, and `tabulate` for the terminal interface.

### Environment Setup
```bash
python3 -m venv PSUvenv
source PSUvenv/bin/activate
pip install pyvisa tabulate
```

## Usage

### 1. Registering Hardware
Before using the driver, register the physical safety limits of the power supply. This ensures the interface cannot push the hardware beyond its design capabilities.
```bash
python3 register_psu.py
```

### 2. Interactive TUI Dashboard
The interactive UI provides an environment mimicking the physical front panel of the power supply.
```bash
python3 psu_cli.py --live
```
- **Up/Down Arrows**: Navigate through parameter fields.
- **Number Keys**: Enter edit mode and modify a target setpoint on the fly.
- **'q' Key**: Close the VISA connection and safely exit the interface.

### 3. Command Line Execution
Execute one-off commands from standard shell scripts without launching the dashboard interface.
```bash
# Enable output and assign basic Setpoints (24V, 5A)
python3 psu_cli.py --set 24 5 --enable 1

# Measure physical output
python3 psu_cli.py --measure

# Ensure OverVoltage and OverCurrent protection limits
python3 psu_cli.py -p 26 5.5

# Sweep instrument error queue
python3 psu_cli.py --errors
```

### 4. Code Integration
The driver can be directly instantiated in automation scripts or external atomizer test modules.
```python
from ITECH_PSU import ITECH_PSU
import time

# Discovers the first registered PSU on the local hardware ports
psu = ITECH_PSU()

# Set boundaries and target variables
psu.set_protection(OV=26.0, OC=5.5)
psu.set(voltage=24.0, amps=5.0)

# Energize load
psu.enable(1)

# Retrieve telemetry strings
print(f"Drawing {psu.measure_current()} A at {psu.measure_voltage()} V")
print(f"Total Wattage: {psu.measure_power()} W")

psu.close()
```

# Developer Reference

This document covers the `ITECH_PSU` driver API for integrating the power supply into automation scripts and test modules.

## Project Structure

| File | Purpose |
|:---|:---|
| `ITECH_PSU.py` | Core driver class — wraps PyVISA/SCPI commands into Python methods with hardware limit enforcement |
| `psu_cli.py` | CLI + interactive curses TUI dashboard |
| `register_psu.py` | One-time setup script to register PSU hardware limits |
| `psu_registry.json` | JSON store of registered PSUs and their safety limits |
| `setup.sh` / `setup.bat` | Automated environment setup scripts |

## Code Integration

```python
from ITECH_PSU import ITECH_PSU

# Discovers the first registered PSU on the local hardware ports
psu = ITECH_PSU()

# Set protection limits (can be set independently)
psu.set_protection(OV=26.0, OC=5.5)

# Set voltage and current setpoints
psu.set(voltage=24.0, amps=5.0)

# Enable output
psu.enable(1)

# Read telemetry
print(f"Drawing {psu.measure_current()} A at {psu.measure_voltage()} V")
print(f"Total Wattage: {psu.measure_power()} W")

# Disable and disconnect
psu.enable(0)
psu.close()
```

## API Reference

### Connection

| Method | Description |
|:---|:---|
| `ITECH_PSU(resource_name=None)` | Connect to PSU. Auto-discovers from registry if no resource string given. |
| `close()` | Safely close the VISA connection |

### Output Control

| Method | Description |
|:---|:---|
| `set(voltage=None, amps=None)` | Set voltage/current setpoints (either or both). Validates against registry limits. |
| `enable(state)` | Enable (`1`) or disable (`0`) the output |
| `set_protection(OV=None, OC=None)` | Set overvoltage/overcurrent protection limits (either or both) |

### Telemetry

| Method | Description |
|:---|:---|
| `measure_voltage()` | Read actual output voltage (V) |
| `measure_current()` | Read actual output current (A) |
| `measure_power()` | Read calculated output power (W) |
| `get_target_voltage()` | Read programmed voltage setpoint (V) |
| `get_target_current()` | Read programmed current setpoint (A) |
| `measure_ovp()` | Read current OVP limit (V) |
| `measure_ocp()` | Read current OCP limit (A) |

### Diagnostics

| Method | Description |
|:---|:---|
| `check_errors()` | Flush the hardware error queue. Raises `RuntimeError` if errors found. |
| `reset()` | Reset instrument to factory defaults (`*RST`) |
| `self_test()` | Run instrument self-test (`*TST?`) |

## Safety Model

All `set()` and `set_protection()` calls validate against the hardware limits defined in `psu_registry.json`:

- **Voltage**: Must be within `0 – maxV`
- **Current**: Must be within `0 – maxA`
- **Power**: `V × A` must not exceed `maxP`
- **OVP**: Must be greater than the current voltage setpoint
- **OCP**: Must be greater than the current current setpoint

If any check fails, a `ValueError` is raised before any SCPI command is sent. After every write, the hardware error queue is flushed via `check_errors()`.

"""
ITECH PSU Driver
Author: Yan Jie Hui
Date: May 8, 2026
Description: SCPI-based PyVISA driver wrapper for ITECH power supplies.
"""

# pyrefly: ignore [missing-import]
import pyvisa
import time


class ITECH_PSU:
    def __init__(self, resource_name=None, registry_file="psu_registry.json"):
        import json
        import os

        self.resource_name = ""
        self.inst = None
        self.maxV = 0
        self.maxA = 0
        self.maxP = 0
        self.state = 0

        # Load registry
        registry = {}
        if os.path.exists(registry_file):
            with open(registry_file, "r") as f:
                registry = json.load(f)
        else:
            raise FileNotFoundError(f"Registry file '{registry_file}' not found. Please run 'python3 register_psu.py' first to initialize the registry!")

        rm = pyvisa.ResourceManager()
        target_resource = None
        matched_registry_key = None

        if resource_name:
            target_resource = resource_name
        else:
            resources = rm.list_resources()
            print(f"Discovered instruments: {resources}")
            for res in resources:
                # Try exact match first
                if res in registry:
                    print(f"Found known PSU in registry: {res}")
                    target_resource = res
                    matched_registry_key = res
                    break
                # Fall back to VID/PID matching (handles hex vs decimal and serial differences)
                res_vid_pid = self._extract_vid_pid(res)
                if res_vid_pid:
                    for reg_key in registry:
                        reg_vid_pid = self._extract_vid_pid(reg_key)
                        if reg_vid_pid and res_vid_pid == reg_vid_pid:
                            print(f"Matched PSU by VID/PID: {res} → registry entry {reg_key}")
                            target_resource = res
                            matched_registry_key = reg_key
                            break
                if target_resource:
                    break
            
            if not target_resource:
                raise RuntimeError("No known PSUs from the registry were found connected!")

        self.resource_name = target_resource
        
        # Apply limits if found in registry
        lookup_key = matched_registry_key or self.resource_name
        if lookup_key in registry:
            params = registry[lookup_key]
            self.maxV = params.get("maxV", 0)
            self.maxA = params.get("maxA", 0)
            self.maxP = params.get("maxP", 0)
            print(f"Loaded limits for {self.resource_name}: {self.maxV}V, {self.maxA}A, {self.maxP}W")
        else:
            print(f"Warning: '{self.resource_name}' not found in registry. Limits are set to 0.")

        self.inst = rm.open_resource(self.resource_name)


    @staticmethod
    def _extract_vid_pid(resource_string):
        """Extracts (VID, PID) as integers from a USB VISA resource string.
        Handles both hex (0x2EC7) and decimal (11975) formats.
        Returns None if not a USB resource."""
        import re
        match = re.match(r'USB\d*::([^:]+)::([^:]+)::', resource_string, re.IGNORECASE)
        if not match:
            return None
        try:
            vid = int(match.group(1), 0)  # auto-detects hex (0x...) or decimal
            pid = int(match.group(2), 0)
            return (vid, pid)
        except ValueError:
            return None


    def close(self):
        """Safely disables output and releases the PyVISA USB lock"""
        if self.inst is not None:
            print("Safely powering down and closing connection...")
            self.inst.close()


    def self_test(self):
        print("starting self test")
        self.inst.write('*RST')
        self.inst.write('*CLS')
        if self.inst.query('*TST?').strip() == "0":
            print("Passed self-test")
        else:
            print("Failed self test")


    def reset(self):
        print("resetting")
        self.inst.write('*RST')
        self.inst.write('*CLS')
        

    def check_errors(self):
        # Reads all errors in the instrument's error queue until it is empty.
        errors_found = []
        
        while True:
            # Query the first error in the queue
            error_str = self.inst.query("SYST:ERR?").strip()
            
            # Usually the string looks like: +0,"No Error" or 0,"No Error"
            if error_str.startswith("0"):
                break # Queue is empty
                
            errors_found.append(error_str)
            
        if errors_found:
            # We found errors, so crash python AFTER flushing the queue
            raise RuntimeError(f"Hardware reported {len(errors_found)} error(s): {errors_found}")


    def set(self, voltage=None, amps=None):
        if voltage is None and amps is None:
            raise ValueError("You must specify either voltage or amps (or both) when calling set().")

        # Query existing values if one is missing so we can do the math
        target_v = voltage if voltage is not None else float(self.inst.query("VOLT?").strip())
        target_a = amps if amps is not None else float(self.inst.query("CURR?").strip())

        # 1. Check max power
        if target_v * target_a > self.maxP:
            raise ValueError(f"Error: {target_v}V * {target_a}A = {target_v*target_a}W (Exceeds {self.maxP}W limit!)")

        # 2. Check individual limits
        if voltage is not None and not (0 <= voltage <= self.maxV):
            raise ValueError(f"Error: Voltage {voltage}V is outside of range 0 - {self.maxV}V")
            
        if amps is not None and not (0 <= amps <= self.maxA):
            raise ValueError(f"Error: Current {amps}A is outside of range 0 - {self.maxA}A")

        # 3. If everything is safe, send the specific strings!
        if voltage is not None:
            self.inst.write(f'VOLT {voltage}')
        if amps is not None:
            self.inst.write(f'CURR {amps}')
        
        # 4. Confirm the hardware agreed
        self.check_errors()
    

    def enable(self,state):
        if state not in (0, 1):
            raise ValueError(f"Error: Enable state must be 0 or 1, but received '{state}'.")

        #Checks current state
        self.state = int(self.inst.query("OUTP?").strip())

        if self.state != state:
            self.inst.write(f'OUTP {state}')
            self.check_errors()
        



    def measure_ovp(self):
        """Reads the hardware OverVoltage Protection limit"""
        return float(self.inst.query("VOLT:PROT?").strip())

    def measure_ocp(self):
        """Reads the hardware OverCurrent Protection limit"""
        return float(self.inst.query("CURR:PROT?").strip())

    def set_protection(self, OV=None, OC=None):
        if OV is None and OC is None:
            raise ValueError("You must specify either OV or OC (or both) when calling set_protection().")

        if OV is not None:
            if not (0 < OV <= self.maxV):
                raise ValueError(f"Error: OverVoltage needs to be <= {self.maxV}")
            setV = float(self.inst.query("VOLT?").strip())
            if not (setV < OV):
                raise ValueError(f"OverVoltage({OV}V) needs to be > setV({setV}V)")
            self.inst.write(f"VOLT:PROT {OV}")

        if OC is not None:
            if not (0 < OC <= self.maxA):
                raise ValueError(f"Error: OverCurrent needs to be <= {self.maxA}")
            setA = float(self.inst.query("CURR?").strip())
            if not (setA < OC):
                raise ValueError(f"OverCurrent({OC}A) needs to be > setA({setA}A)")
            self.inst.write(f"CURR:PROT {OC}")

        self.check_errors()

    def query_protection_status(self):
        """Checks if any protection has tripped (OVP, OCP, etc).
        Returns a list of tripped protection names, or empty list if all clear.
        Uses the SCPI Questionable Status Register."""
        tripped = []
        try:
            # STAT:QUES? returns a bitmask of questionable conditions
            # Bit 0: Over Voltage Protection
            # Bit 1: Over Current Protection
            # Bit 4: Over Temperature Protection
            # Bit 9: Over Power Protection
            status = int(self.inst.query("STAT:QUES?").strip())
            if status & 0x01:
                tripped.append("OVP")
            if status & 0x02:
                tripped.append("OCP")
            if status & 0x10:
                tripped.append("OTP")
            if status & 0x200:
                tripped.append("OPP")
        except:
            pass
        return tripped

    def get_target_voltage(self) -> float:
        """Returns the programmed voltage setpoint"""
        return float(self.inst.query("VOLT?").strip())

    def get_target_current(self) -> float:
        """Returns the programmed current limit setpoint"""
        return float(self.inst.query("CURR?").strip())

    def measure_voltage(self) -> float:
        """Returns the actual voltage currently being output by the PSU"""
        return float(self.inst.query("MEAS:VOLT?").strip())
    
    def measure_current(self) -> float:
        """Returns the actual current currently flowing to the load"""
        return float(self.inst.query("MEAS:CURR?").strip())
        
    def measure_power(self) -> float:
        """Returns the real-time calculated power consumption (in Watts)"""
        return float(self.inst.query("MEAS:POW?").strip())

def main():

    psu = None
    try:
        psu = ITECH_PSU()
        psu.set_protection(OV=2, OC=2)
        psu.set(1, 1)
        psu.enable(1)

        # A simple telemetry loop!
    
        for i in range(10):
            volts = psu.measure_voltage()
            amps = psu.measure_current()
            watts = psu.measure_power()
            
            print(f"Time: {i}s | {volts}V, {amps}A ({watts}W)")
            time.sleep(1)
            
    finally:
        if psu is not None:
            psu.close()


if __name__ == "__main__":
    main()
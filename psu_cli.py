from os import stat_result
from ITECH_PSU import ITECH_PSU
import argparse


def main():

    # Set up help menu
    parser = argparse.ArgumentParser("How to control PSU on the terminal")
    parser.add_argument("--device", type=str, help="Specific Visa string if more multiple devices present")
    parser.add_argument("-s", "--set", nargs=2, type=float, metavar=('VOLTS', 'AMPS'), help="Set Voltage and Current limits (e.g. -s 24 5)")
    parser.add_argument("-p", "--protect", nargs=2, type=float, metavar=('OV', 'OC'), help="Set OverVoltage and OverCurrent protection (e.g. -p 26 5.5)")
    parser.add_argument("-e", "--enable", type=int, choices=[0, 1], help="Enable (1) or Disable (0) the output")
    parser.add_argument("-m", "--measure", action="store_true", help="Print current telemetry data")
    parser.add_argument("--errors", action="store_true", help="Manually check the hardware error queue")
    
    # parse what the user types in the terminal
    args = parser.parse_args()

    try:
        if args.device is not None:
            # Connect to the specified PSU
            psu = ITECH_PSU(resource_name=args.device)
        else:
            # Connect to the only PSU or first PSU found
            psu = ITECH_PSU()

        # Execute actions based on arguments
        if args.protect:
            psu.set_protection(OV=args.protect[0], OC=args.protect[1])

        if args.set:
            psu.set(voltage=args.set[0], amps=args.set[1])

        if args.enable is not None:
            psu.enable(args.enable)

        if args.measure:
            print("\n--- Telemetry ---")
            print(f"Volts: {psu.measure_voltage()} V")
            print(f"Amps:  {psu.measure_current()} A")
            print(f"Watts: {psu.measure_power()} W\n")

        if args.errors:
            psu.check_errors()


    finally:
        psu.close()




if __name__ == "__main__":
    main()

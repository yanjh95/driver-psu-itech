from os import stat_result
from ITECH_PSU import ITECH_PSU
import argparse
import time
import curses
from tabulate import tabulate


def main():

    # Set up help menu
    parser = argparse.ArgumentParser("How to control PSU on the terminal")
    parser.add_argument("--device", type=str, help="Specific Visa string if more multiple devices present")
    parser.add_argument("-s", "--set", nargs=2, type=float, metavar=('VOLTS', 'AMPS'), help="Set Voltage and Current limits (e.g. -s 24 5)")
    parser.add_argument("-p", "--protect", nargs=2, type=float, metavar=('OV', 'OC'), help="Set OverVoltage and OverCurrent protection (e.g. -p 26 5.5)")
    parser.add_argument("-e", "--enable", type=int, choices=[0, 1], help="Enable (1) or Disable (0) the output")
    parser.add_argument("-m", "--measure", action="store_true", help="Print current telemetry data")
    parser.add_argument("--errors", action="store_true", help="Manually check the hardware error queue")
    parser.add_argument("--live", action="store_true", help="Launch interactive Curses dashboard")
    
    # parse what the user types in the terminal
    args = parser.parse_args()

    try:
        if args.device is not None:
            # Connect to the specified PSU
            psu = ITECH_PSU(resource_name=args.device)
        else:
            # Connect to the only PSU or first PSU found
            psu = ITECH_PSU()

        if args.live:
            curses.wrapper(run_live_dashboard, psu)
        else:
            # Execute standard CLI actions based on arguments
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




def run_live_dashboard(stdscr, psu):
    stdscr.nodelay(True)
    curses.curs_set(0) # Hide cursor during normal operations
    
    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)
        curses.init_pair(2, curses.COLOR_RED, -1)
        
    stdscr.clear()

    fields = ["Voltage", "Current", "OV Limit", "OC Limit", "Output"]
    
    # Internal cache speeds up rendering
    state = {
        "Set Voltage": "? V",  "Set Current": "? A",
        "Actual V": "? V",     "Actual A": "? A",
        "OV Limit": "? V",     "OC Limit": "? A",
        "Output": "?"
    }

    selected = 0
    edit_mode = False
    edit_string = ""
    error_msg = ""
    last_update = 0

    while True:
        try:
            key = stdscr.getch()
        except:
            key = -1

        if key != -1:
            if not edit_mode:
                if key == ord('q'):
                    break
                elif key == curses.KEY_DOWN:
                    selected = (selected + 1) % len(fields)
                    error_msg = ""
                elif key == curses.KEY_UP:
                    selected = (selected - 1) % len(fields)
                    error_msg = ""
                elif key == ord('\n') or (ord('0') <= key <= ord('9')) or key == ord('.'):
                    edit_mode = True
                    curses.curs_set(1) # Show cursor in edit mode
                    error_msg = ""
                    if key != ord('\n'):
                        edit_string = chr(key)
                    else:
                        edit_string = ""
            else:
                # We are in Edit Mode
                if key == ord('\n'): # User pressed Enter to submit
                    try:
                        field_name = fields[selected]
                        if field_name == "Output":
                            psu.enable(int(edit_string))
                        elif field_name == "Voltage":
                            psu.set(voltage=float(edit_string))
                        elif field_name == "Current":
                            psu.set(amps=float(edit_string))
                        elif field_name == "OV Limit":
                            old_oc = float(state["OC Limit"].replace(" A", ""))
                            psu.set_protection(OV=float(edit_string), OC=old_oc)
                        elif field_name == "OC Limit":
                            old_ov = float(state["OV Limit"].replace(" V", ""))
                            psu.set_protection(OV=old_ov, OC=float(edit_string))
                        
                        edit_mode = False
                        curses.curs_set(0)
                        last_update = 0 # Force a fast telemetry refresh
                    except Exception as e:
                        error_msg = f"ERR: {str(e)}"
                        edit_mode = False
                        curses.curs_set(0)

                elif key == 27: # Escape key to cancel
                    edit_mode = False
                    curses.curs_set(0)
                elif key in (curses.KEY_BACKSPACE, 127, 8):
                    edit_string = edit_string[:-1]
                else:
                    try:
                        char = chr(key)
                        if char.isprintable():
                            edit_string += char
                    except: pass
        
        # Background Telemetry Puller (approx 0.5s intervals)
        # We pause telemetry querying during edit_mode to prevent typing lag
        current_time = time.time()
        if not edit_mode and current_time - last_update > 0.5:
            try:
                state["Set Voltage"] = f"{psu.get_target_voltage():.2f} V"
                state["Set Current"] = f"{psu.get_target_current():.2f} A"
                state["Actual V"] = f"{psu.measure_voltage():.2f} V"
                state["Actual A"] = f"{psu.measure_current():.2f} A"
                state["OV Limit"] = f"{psu.measure_ovp():.2f} V"
                state["OC Limit"] = f"{psu.measure_ocp():.2f} A"
                out_int = int(psu.inst.query("OUTP?").strip())
                state["Output"] = "ON" if out_int == 1 else "OFF"
            except Exception as e:
                 error_msg = "COMMUNICATION ERROR"
            last_update = current_time

        # Render Table
        stdscr.erase()
        stdscr.addstr(0, 0, "=== ITECH PSU LIVE DASHBOARD ===", curses.A_BOLD)
        stdscr.addstr(1, 0, "Navigate: [Arrows] | Edit: [Numbers] | Cancel: [ESC] | Quit: [q]")
        
        table_list = [
            ["Voltage", state["Set Voltage"], state["Actual V"]],
            ["Current", state["Set Current"], state["Actual A"]],
            ["OV Limit", state["OV Limit"], "---"],
            ["OC Limit", state["OC Limit"], "---"],
            ["Output", state["Output"], "---"]
        ]
        tab_str = tabulate(table_list, headers=["Parameter", "Setpoint", "Actual Out"], tablefmt="grid")
        lines = tab_str.split("\n")
        
        line_offset = 3
        try:
            for i, text in enumerate(lines):
                # We only want to highlight the row that contains the data, not the borders!
                # Using grid format, the data rows exist on odd lines starting at 3.
                style = curses.A_NORMAL
                is_data_row = (i >= 3 and (i - 3) % 2 == 0)
                
                if is_data_row:
                    row_index = (i - 3) // 2
                    if row_index == selected:
                        style |= curses.A_REVERSE
                        
                    if fields[row_index] == "Output" and curses.has_colors():
                        if "ON" in text:
                            style |= curses.color_pair(1) | curses.A_BOLD
                        elif "OFF" in text:
                            style |= curses.color_pair(2) | curses.A_BOLD
                            
                stdscr.addstr(i + line_offset, 0, text, style)

            # Bottom Input Bar
            prompt_y = len(lines) + line_offset + 1
            if edit_mode:
                stdscr.addstr(prompt_y, 0, f"Enter new {fields[selected]}: {edit_string}")
            elif error_msg:
                 stdscr.addstr(prompt_y, 0, error_msg, curses.A_BOLD | curses.A_REVERSE)
        except curses.error:
            pass # Safe fallback for small terminal windows
            
            
        stdscr.refresh()
        time.sleep(0.02)

if __name__ == "__main__":
    main()

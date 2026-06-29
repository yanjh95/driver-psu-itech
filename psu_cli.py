from ITECH_PSU import ITECH_PSU
import argparse
import time
import curses
import csv
import os
from tabulate import tabulate
import asciichartpy


def load_profile(filepath):
    """Parses a PSU profile CSV file.
    Metadata rows: description, ov_limit (optional), oc_limit (optional)
    Data header: time_s,voltage,current
    Data rows: float values
    Returns (description, steps, ov_limit, oc_limit) where steps is a list of (time_s, voltage, current) tuples.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Profile not found: {filepath}")

    with open(filepath, 'r') as f:
        reader = csv.reader(f)
        
        description = "No description"
        ov_limit = None
        oc_limit = None
        
        # Parse metadata rows (description, ov_limit, oc_limit) until we hit the data header
        for row in reader:
            if not row:
                continue
            key = row[0].strip().lower()
            if key == 'description' and len(row) >= 2:
                description = row[1].strip()
            elif key == 'ov_limit' and len(row) >= 2:
                ov_limit = float(row[1].strip())
            elif key == 'oc_limit' and len(row) >= 2:
                oc_limit = float(row[1].strip())
            elif key == 'time_s':
                break  # Reached the data header
        
        # Remaining rows are data
        steps = []
        for row in reader:
            if len(row) >= 3:
                t = float(row[0].strip())
                v = float(row[1].strip())
                a = float(row[2].strip())
                steps.append((t, v, a))
    
    if not steps:
        raise ValueError(f"Profile '{filepath}' has no steps!")
    
    # Sort by time
    steps.sort(key=lambda x: x[0])
    return description, steps, ov_limit, oc_limit


def list_profiles(profiles_dir="profiles"):
    """Scans the profiles directory and returns a list of (filepath, filename, description)."""
    profiles = []
    if not os.path.isdir(profiles_dir):
        return profiles
    for fname in sorted(os.listdir(profiles_dir)):
        if fname.endswith('.csv'):
            fpath = os.path.join(profiles_dir, fname)
            try:
                desc, _, _, _ = load_profile(fpath)
                profiles.append((fpath, fname, desc))
            except:
                profiles.append((fpath, fname, "(could not parse)"))
    return profiles


def pick_profile_curses(stdscr):
    """Shows a profile selection menu inside curses. Returns (steps, filename, description, ov_limit, oc_limit) or None."""
    stdscr.nodelay(False)  # Block for input
    curses.curs_set(0)
    
    profiles = list_profiles()
    if not profiles:
        stdscr.nodelay(True)
        return None
    
    selected = 0
    while True:
        stdscr.erase()
        stdscr.addstr(0, 0, "=== SELECT PROFILE ===", curses.A_BOLD)
        stdscr.addstr(1, 0, "Use [↑/↓] to navigate, [Enter] to select, [ESC] to cancel")
        
        for i, (fpath, fname, desc) in enumerate(profiles):
            y = i + 3
            style = curses.A_REVERSE if i == selected else curses.A_NORMAL
            label = f"  {fname:<30s}  {desc}"
            try:
                stdscr.addstr(y, 0, label, style)
            except curses.error:
                pass
        
        stdscr.refresh()
        key = stdscr.getch()
        
        if key == curses.KEY_DOWN:
            selected = (selected + 1) % len(profiles)
        elif key == curses.KEY_UP:
            selected = (selected - 1) % len(profiles)
        elif key == ord('\n'):
            fpath, fname, desc = profiles[selected]
            try:
                description, steps, ov_limit, oc_limit = load_profile(fpath)
                stdscr.nodelay(True)
                return steps, fname, description, ov_limit, oc_limit
            except Exception as e:
                stdscr.nodelay(True)
                return None
        elif key == 27:  # ESC
            stdscr.nodelay(True)
            return None


def interpolate_profile(steps, elapsed):
    """Given a list of (time_s, voltage, current) steps and the current elapsed time,
    returns the linearly interpolated (voltage, current) values.
    Before the first step: returns first step values.
    After the last step: returns last step values."""
    if elapsed <= steps[0][0]:
        return steps[0][1], steps[0][2]
    if elapsed >= steps[-1][0]:
        return steps[-1][1], steps[-1][2]
    
    # Find the two bounding steps
    for i in range(len(steps) - 1):
        t0, v0, a0 = steps[i]
        t1, v1, a1 = steps[i + 1]
        if t0 <= elapsed < t1:
            # Linear interpolation factor
            frac = (elapsed - t0) / (t1 - t0)
            v = v0 + (v1 - v0) * frac
            a = a0 + (a1 - a0) * frac
            return round(v, 3), round(a, 3)
    
    return steps[-1][1], steps[-1][2]


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
    parser.add_argument("--profile", type=str, metavar='CSV_FILE', help="Load and execute a profile (e.g. --profile profiles/example_24v_soak.csv)")
    
    # parse what the user types in the terminal
    args = parser.parse_args()

    psu = None
    try:
        if args.device is not None:
            # Connect to the specified PSU
            psu = ITECH_PSU(resource_name=args.device)
        else:
            # Connect to the only PSU or first PSU found
            psu = ITECH_PSU()

        if args.profile:
            profile_desc, profile_steps, ov_limit, oc_limit = load_profile(args.profile)
            filename = os.path.basename(args.profile)
            if args.live:
                curses.wrapper(run_live_dashboard, psu, profile_steps, filename, profile_desc, ov_limit, oc_limit)
            else:
                run_profile_cli(psu, profile_steps, filename, profile_desc, ov_limit, oc_limit)
        elif args.live:
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
        if psu is not None:
            psu.close()


def run_profile_cli(psu, steps, filename, description, ov_limit=None, oc_limit=None):
    """Executes a profile in CLI mode (no dashboard), printing progress with interpolation."""
    total_duration = steps[-1][0]
    print(f"\n{'='*50}")
    print(f"Loading profile: {filename}")
    print(f"Description: {description}")
    print(f"Steps: {len(steps)} | Total duration: {total_duration}s")
    if ov_limit:
        print(f"OV Protection: {ov_limit}V")
    if oc_limit:
        print(f"OC Protection: {oc_limit}A")
    print(f"{'='*50}")

    # Reset setpoints before applying profile limits
    psu.enable(0)
    psu.set(voltage=0, amps=0)
    print("[RESET] Setpoints zeroed")

    # Set protection limits if specified
    if ov_limit is not None:
        psu.set_protection(OV=ov_limit)
        print(f"[PROTECT] OV limit set to {ov_limit}V")
    if oc_limit is not None:
        psu.set_protection(OC=oc_limit)
        print(f"[PROTECT] OC limit set to {oc_limit}A")

    # Set first step values, then enable output
    v0, a0 = interpolate_profile(steps, 0)
    psu.set(voltage=v0, amps=a0)
    psu.enable(1)
    print("[OUTPUT] Enabled")

    start_time = time.time()
    last_v, last_a = None, None
    next_print_step = 0

    try:
        while True:
            elapsed = time.time() - start_time
            if elapsed > total_duration:
                break

            v, a = interpolate_profile(steps, elapsed)

            # Send interpolated setpoint to PSU (only if changed)
            if v != last_v or a != last_a:
                psu.set(voltage=v, amps=a)
                last_v, last_a = v, a

            # Print when we pass a step timestamp
            if next_print_step < len(steps) and elapsed >= steps[next_print_step][0]:
                sv, sa = steps[next_print_step][1], steps[next_print_step][2]
                print(f"[{elapsed:>7.1f}s] Step {next_print_step+1}/{len(steps)}: {sv:.2f}V, {sa:.2f}A")
                next_print_step += 1

            time.sleep(0.1)  # 100ms ramp resolution

    except KeyboardInterrupt:
        print("\n[!] Profile interrupted by user.")
    finally:
        psu.enable(0)
        print("[OUTPUT] Disabled")
        print(f"Profile complete.\n")




def run_live_dashboard(stdscr, psu, profile_steps=None, profile_name=None, profile_desc=None, profile_ov=None, profile_oc=None):
    stdscr.nodelay(True)
    curses.curs_set(0) # Hide cursor during normal operations
    
    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)
        curses.init_pair(2, curses.COLOR_RED, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
        curses.init_pair(4, curses.COLOR_CYAN, -1)
        
    stdscr.clear()

    fields = ["Voltage", "Current", "OV Limit", "OC Limit"]
    
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
    expected_output_on = False  # Tracks whether WE turned the output on

    # Rolling telemetry history for live plots
    DEFAULT_HISTORY_SIZE = 20  # 10-second window at 0.5s polling
    history_size = DEFAULT_HISTORY_SIZE
    voltage_history = []
    current_history = []

    # Profile state
    profile_active = profile_steps is not None
    profile_triggered = profile_steps is not None and profile_name == "__cli_trigger__"
    profile_start_time = None
    profile_step_index = 0
    profile_complete = False
    profile_ov_limit = profile_ov
    profile_oc_limit = profile_oc

    while True:
        try:
            key = stdscr.getch()
        except:
            key = -1

        if key != -1:
            if key == ord('q'):
                try:
                    psu.enable(0)
                except:
                    pass
                break

            if profile_active:
                # Profile mode: only P, T, Q
                if key == ord('p') and (not profile_triggered or profile_complete):
                    # Re-open profile picker (or pick a new one)
                    result = pick_profile_curses(stdscr)
                    if result:
                        profile_steps, profile_name, profile_desc, profile_ov_limit, profile_oc_limit = result
                        profile_active = True
                        profile_triggered = False
                        profile_start_time = None
                        profile_step_index = 0
                        profile_complete = False
                        history_size = max(int(profile_steps[-1][0] / 0.5), 2)
                        voltage_history.clear()
                        current_history.clear()
                        error_msg = ""
                        expected_output_on = False
                    else:
                        # ESC pressed — go back to normal mode
                        profile_active = False
                        profile_steps = None
                        profile_name = None
                        profile_desc = None
                        history_size = DEFAULT_HISTORY_SIZE
                        error_msg = ""
                elif key == ord('t') and profile_active and not profile_triggered:
                    # Trigger the profile
                    profile_triggered = True
                    profile_start_time = None
                    profile_step_index = 0
                    profile_complete = False
                    voltage_history.clear()
                    current_history.clear()
                    error_msg = ""
            else:
                # Normal dashboard mode
                if not edit_mode:
                    if key == ord('e'):
                        try:
                            current_state = int(psu.inst.query("OUTP?").strip())
                            new_state = 0 if current_state == 1 else 1
                            psu.enable(new_state)
                            expected_output_on = (new_state == 1)
                            last_update = 0
                            error_msg = ""
                        except Exception as e:
                            error_msg = f"ERR: {str(e)}"
                    elif key == ord('p'):
                        result = pick_profile_curses(stdscr)
                        if result:
                            profile_steps, profile_name, profile_desc, profile_ov_limit, profile_oc_limit = result
                            profile_active = True
                            profile_triggered = False
                            profile_start_time = None
                            profile_step_index = 0
                            profile_complete = False
                            history_size = max(int(profile_steps[-1][0] / 0.5), 2)
                            voltage_history.clear()
                            current_history.clear()
                            error_msg = ""
                            expected_output_on = False
                    elif key == curses.KEY_DOWN:
                        selected = (selected + 1) % len(fields)
                        error_msg = ""
                    elif key == curses.KEY_UP:
                        selected = (selected - 1) % len(fields)
                        error_msg = ""
                    elif key == ord('\n') or (ord('0') <= key <= ord('9')) or key == ord('.'):
                        edit_mode = True
                        curses.curs_set(1)
                        error_msg = ""
                        if key != ord('\n'):
                            edit_string = chr(key)
                        else:
                            edit_string = ""
                else:
                    # Edit Mode
                    if key == ord('\n'):
                        try:
                            field_name = fields[selected]
                            if field_name == "Voltage":
                                psu.set(voltage=float(edit_string))
                            elif field_name == "Current":
                                psu.set(amps=float(edit_string))
                            elif field_name == "OV Limit":
                                psu.set_protection(OV=float(edit_string))
                            elif field_name == "OC Limit":
                                psu.set_protection(OC=float(edit_string))
                            
                            edit_mode = False
                            curses.curs_set(0)
                            last_update = 0
                        except Exception as e:
                            error_msg = f"ERR: {str(e)}"
                            edit_mode = False
                            curses.curs_set(0)

                    elif key == 27:
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
        current_time = time.time()
        if not edit_mode and current_time - last_update > 0.5:
            try:
                state["Set Voltage"] = f"{psu.get_target_voltage():.2f} V"
                state["Set Current"] = f"{psu.get_target_current():.2f} A"
                actual_v = psu.measure_voltage()
                actual_a = psu.measure_current()
                state["Actual V"] = f"{actual_v:.2f} V"
                state["Actual A"] = f"{actual_a:.2f} A"
                state["OV Limit"] = f"{psu.measure_ovp():.2f} V"
                state["OC Limit"] = f"{psu.measure_ocp():.2f} A"
                out_int = int(psu.inst.query("OUTP?").strip())
                state["Output"] = "ON" if out_int == 1 else "OFF"

                # Append to rolling history (round to suppress ADC noise spikes)
                voltage_history.append(round(actual_v, 2))
                current_history.append(round(actual_a, 2))
                if len(voltage_history) > history_size:
                    voltage_history.pop(0)
                if len(current_history) > history_size:
                    current_history.pop(0)

                # Detect protection trips by output state change
                # If we expect output ON but hardware says OFF, a protection tripped
                if expected_output_on and out_int == 0:
                    error_msg = "⚠ PROTECTION TRIPPED — Output was shut off by hardware!"
                    state["Output"] = "TRIP"
                    expected_output_on = False
            except Exception as e:
                 error_msg = "COMMUNICATION ERROR"
            last_update = current_time

        # Profile interpolation and advancement
        if profile_active and profile_triggered and not profile_complete:
            if profile_start_time is None:
                # First tick — reset setpoints, set protection, enable output, and start the clock
                try:
                    # Ensure output is off and setpoints are zeroed before applying new limits
                    psu.enable(0)
                    psu.set(voltage=0, amps=0)

                    # Now safe to set protection (OV/OC > 0V/0A setpoints)
                    if profile_ov_limit is not None:
                        psu.set_protection(OV=profile_ov_limit)
                    if profile_oc_limit is not None:
                        psu.set_protection(OC=profile_oc_limit)

                    # Set first step values, then enable
                    v, a = interpolate_profile(profile_steps, 0)
                    psu.set(voltage=v, amps=a)
                    psu.enable(1)
                    expected_output_on = True
                    profile_start_time = time.time()
                    last_update = 0
                except Exception as e:
                    error_msg = f"Profile ERR: {str(e)}"
            else:
                elapsed = time.time() - profile_start_time
                total_duration = profile_steps[-1][0]
                
                if elapsed <= total_duration:
                    try:
                        v, a = interpolate_profile(profile_steps, elapsed)
                        psu.set(voltage=v, amps=a)
                        profile_step_index = sum(1 for s in profile_steps if elapsed >= s[0])
                    except Exception as e:
                        error_msg = f"Profile ERR: {str(e)}"
                else:
                    try:
                        psu.enable(0)
                    except:
                        pass
                    expected_output_on = False
                    profile_complete = True
                    error_msg = "Profile complete — output disabled. [P] New profile | [Q] Quit"

        # Render Header
        stdscr.erase()
        stdscr.addstr(0, 0, "=== ITECH PSU LIVE DASHBOARD ===", curses.A_BOLD)
        
        if profile_active:
            stdscr.addstr(1, 0, f"Profile: {profile_name} | {profile_desc}",
                          curses.color_pair(3) | curses.A_BOLD if curses.has_colors() else curses.A_BOLD)
            if profile_start_time and not profile_complete:
                elapsed = time.time() - profile_start_time
                total = profile_steps[-1][0]
                pct = min(elapsed / total * 100, 100) if total > 0 else 100
                bar_width = 30
                filled = int(bar_width * pct / 100)
                bar = "█" * filled + "░" * (bar_width - filled)
                stdscr.addstr(2, 0, f"Progress: [{bar}] {pct:.0f}% ({elapsed:.1f}s / {total:.0f}s)",
                              curses.color_pair(3) if curses.has_colors() else curses.A_NORMAL)
                step_info = f"Step {min(profile_step_index, len(profile_steps))}/{len(profile_steps)}"
                stdscr.addstr(2, 55, step_info)
            elif profile_complete:
                stdscr.addstr(2, 0, "✓ Profile complete",
                              curses.color_pair(1) | curses.A_BOLD if curses.has_colors() else curses.A_BOLD)
            elif not profile_triggered:
                stdscr.addstr(2, 0, "▶ Press [T] to trigger profile",
                              curses.color_pair(3) if curses.has_colors() else curses.A_NORMAL)
            header_line = 3
        else:
            header_line = 1
        
        # Context-appropriate controls bar
        if profile_active:
            if not profile_triggered:
                controls = "Trigger: [T] | Change Profile: [P] | Quit: [Q]"
            elif profile_complete:
                controls = "New Profile: [P] | Quit: [Q]"
            else:
                controls = "Profile running... | Quit: [Q]"
        else:
            controls = "Navigate: [Arrows] | Edit: [Numbers] | Enable/Disable: [E] | Profile: [P] | Quit: [Q]"
        
        stdscr.addstr(header_line, 0, controls)
        
        table_list = [
            ["Voltage", state["Set Voltage"], state["Actual V"]],
            ["Current", state["Set Current"], state["Actual A"]],
            ["OV Limit", state["OV Limit"], "---"],
            ["OC Limit", state["OC Limit"], "---"],
            ["Output", state["Output"], "---"]
        ]
        tab_str = tabulate(table_list, headers=["Parameter", "Setpoint", "Actual Out"], tablefmt="grid")
        lines = tab_str.split("\n")
        
        line_offset = header_line + 2
        try:
            for i, text in enumerate(lines):
                # We only want to highlight the row that contains the data, not the borders!
                # Using grid format, the data rows exist on odd lines starting at 3.
                style = curses.A_NORMAL
                is_data_row = (i >= 3 and (i - 3) % 2 == 0)
                
                if is_data_row:
                    row_index = (i - 3) // 2
                    if row_index < len(fields) and row_index == selected:
                        style |= curses.A_REVERSE
                        
                    # Color the Output row (last data row, not in fields list)
                    if "Output" in text and curses.has_colors():
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

            # Live Telemetry Charts
            if len(voltage_history) >= 2:
                chart_y = prompt_y + 2
                max_height, max_width = stdscr.getmaxyx()
                chart_height = 8
                half_width = max(max_width // 2 - 2, 20)

                # Voltage chart (green)
                try:
                    v_chart = asciichartpy.plot(voltage_history, {
                        'height': chart_height,
                        'format': '{:>8.2f}'
                    })
                    v_lines = v_chart.split('\n')
                    v_label_time = f"{int(history_size * 0.5)}s" if not profile_active else f"{int(profile_steps[-1][0])}s"
                    v_label = f"── Voltage (V) ── [{v_label_time} window]"
                    if chart_y < max_height:
                        stdscr.addstr(chart_y, 0, v_label,
                                      curses.color_pair(1) | curses.A_BOLD if curses.has_colors() else curses.A_BOLD)
                    for j, vline in enumerate(v_lines):
                        y = chart_y + 1 + j
                        if y < max_height - 1:
                            display_line = vline[:half_width]
                            stdscr.addstr(y, 0, display_line,
                                          curses.color_pair(1) if curses.has_colors() else curses.A_NORMAL)
                except:
                    pass

                # Current chart (yellow/red)
                try:
                    a_chart = asciichartpy.plot(current_history, {
                        'height': chart_height,
                        'format': '{:>8.2f}'
                    })
                    a_lines = a_chart.split('\n')
                    a_label_time = f"{int(history_size * 0.5)}s" if not profile_active else f"{int(profile_steps[-1][0])}s"
                    a_label = f"── Current (A) ── [{a_label_time} window]"
                    col_offset = half_width + 4
                    if chart_y < max_height:
                        stdscr.addstr(chart_y, col_offset, a_label,
                                      curses.color_pair(2) | curses.A_BOLD if curses.has_colors() else curses.A_BOLD)
                    for j, aline in enumerate(a_lines):
                        y = chart_y + 1 + j
                        if y < max_height - 1:
                            display_line = aline[:half_width]
                            stdscr.addstr(y, col_offset, display_line,
                                          curses.color_pair(2) if curses.has_colors() else curses.A_NORMAL)
                except:
                    pass

            # Profile Preview Charts (shown when a profile is loaded)
            if profile_active and profile_steps:
                total_dur = profile_steps[-1][0]
                num_samples = history_size  # Match live chart sample count for aligned X axis
                sample_times = [total_dur * i / (num_samples - 1) for i in range(num_samples)]
                preview_v = [interpolate_profile(profile_steps, t)[0] for t in sample_times]
                preview_a = [interpolate_profile(profile_steps, t)[1] for t in sample_times]

                # Position below live charts
                if len(voltage_history) >= 2:
                    preview_y = chart_y + chart_height + 3
                else:
                    preview_y = prompt_y + 2
                
                max_height, max_width = stdscr.getmaxyx()
                preview_height = 8
                half_width = max(max_width // 2 - 2, 20)

                # Profile Voltage Preview (yellow)
                try:
                    pv_chart = asciichartpy.plot(preview_v, {
                        'height': preview_height,
                        'format': '{:>8.2f}'
                    })
                    pv_lines = pv_chart.split('\n')
                    pv_label = f"── Profile Voltage (V) ── [0-{total_dur:.0f}s]"
                    if preview_y < max_height:
                        stdscr.addstr(preview_y, 0, pv_label,
                                      curses.color_pair(3) | curses.A_BOLD if curses.has_colors() else curses.A_BOLD)
                    for j, line in enumerate(pv_lines):
                        y = preview_y + 1 + j
                        if y < max_height - 1:
                            stdscr.addstr(y, 0, line[:half_width],
                                          curses.color_pair(3) if curses.has_colors() else curses.A_NORMAL)
                except:
                    pass

                # Profile Current Preview (cyan)
                try:
                    pa_chart = asciichartpy.plot(preview_a, {
                        'height': preview_height,
                        'format': '{:>8.2f}'
                    })
                    pa_lines = pa_chart.split('\n')
                    pa_label = f"── Profile Current (A) ── [0-{total_dur:.0f}s]"
                    col_offset = half_width + 4
                    if preview_y < max_height:
                        stdscr.addstr(preview_y, col_offset, pa_label,
                                      curses.color_pair(4) | curses.A_BOLD if curses.has_colors() else curses.A_BOLD)
                    for j, line in enumerate(pa_lines):
                        y = preview_y + 1 + j
                        if y < max_height - 1:
                            stdscr.addstr(y, col_offset, line[:half_width],
                                          curses.color_pair(4) if curses.has_colors() else curses.A_NORMAL)
                except:
                    pass

        except curses.error:
            pass # Safe fallback for small terminal windows
            
            
        stdscr.refresh()
        time.sleep(0.02)

if __name__ == "__main__":
    main()

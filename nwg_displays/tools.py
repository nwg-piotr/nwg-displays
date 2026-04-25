# !/usr/bin/env python3
import datetime
import json
import os
import shutil
import socket
import subprocess
import sys

import gi

gi.require_version('Gdk', '3.0')
from gi.repository import Gdk

if os.getenv("SWAYSOCK"):
    from i3ipc import Connection


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def get_config_home():
    xdg_config_home = os.getenv('XDG_CONFIG_HOME')
    config_home = xdg_config_home if xdg_config_home else os.path.join(
        os.getenv("HOME"), ".config")

    return config_home


def get_config_dir():
    xdg_config_home = os.getenv("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(xdg_config_home, "nwg-displays")


def niri_msg(cmd):
    """Execute niri msg command and return output"""
    niri_socket = os.getenv("NIRI_SOCKET")
    if not niri_socket:
        return None
    
    if not os.path.exists(niri_socket):
        eprint(f"[niri] Socket file not found: {niri_socket}")
        return None
    
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(niri_socket)
        request = cmd + "\n"
        s.send(request.encode("utf-8"))
        s.shutdown(socket.SHUT_WR)
        output = ""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            output += chunk.decode('utf-8')
        s.close()
        return output.strip()
    except Exception as e:
        eprint(f"Error communicating with niri: {e}")
        return None


def niri_reload_config():
    """Reload niri configuration via niri msg CLI"""
    try:
        subprocess.run(['niri', 'msg', 'action', 'load-config-file', 
                       os.path.join(get_config_home(), "niri", "config.kdl")],
                      capture_output=True, text=True, timeout=5)
        print("[niri] Config reloaded")
    except Exception as e:
        eprint(f"[niri] Failed to reload config: {e}")


def get_config():
    config_dir = get_config_dir()
    config_file = os.path.join(config_dir, "config")

    if not os.path.isfile(config_file):
        print(f"[Error] Config file not found at {config_file}")
        sys.exit(1)

    config = load_json(config_file)
    if config is None:
        print("[Error] Failed to load configuration")
        sys.exit(1)

    return config, config_file


def hyprctl(cmd):
    # /tmp/hypr moved to $XDG_RUNTIME_DIR/hypr in #5788
    xdg_runtime_dir = os.getenv("XDG_RUNTIME_DIR")
    hypr_dir = f"{xdg_runtime_dir}/hypr" if xdg_runtime_dir and os.path.isdir(
        f"{xdg_runtime_dir}/hypr") else "/tmp/hypr"

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(f"{hypr_dir}/{os.getenv('HYPRLAND_INSTANCE_SIGNATURE')}/.socket.sock")

    s.send(cmd.encode("utf-8"))
    output = s.recv(20480).decode('utf-8')
    s.close()

    return output


def is_command(cmd):
    return shutil.which(cmd) is not None


def list_outputs():
    if os.getenv("NIRI_SOCKET"):
        outputs_dict = {}
        eprint("Running on niri")
        
        try:
            try:
                result = subprocess.run(['niri', 'msg', '-j', 'outputs'], 
                                      capture_output=True, text=True, timeout=5)
                output = result.stdout
            except Exception as e:
                eprint(f"[niri] Failed to run niri msg: {e}")
                # Fallback to socket communication
                output = niri_msg('{"Outputs":null}')
                
            if not output:
                eprint("[niri] Could not communicate with niri compositor")
                return {}
                
            data = json.loads(output)
            
            # niri msg returns dict directly: {"eDP-1": {...}}
            # Or via IPC: {"Ok":{"Outputs":{"eDP-1":{...}}}}
            monitors_dict = None
            if isinstance(data, dict):
                if "Ok" in data:
                    monitors_dict = data.get("Outputs", {})
                elif "Err" in data:
                    eprint(f"[niri] Error from compositor: {data['Err']}")
                    return {}
                else:
                    # Direct response from niri msg
                    monitors_dict = data
            
            if monitors_dict is None or not isinstance(monitors_dict, dict):
                eprint(f"[niri] Unexpected response format: {data}")
                return {}
            
            # monitors_dict is a dict keyed by output name
            transforms = {"Normal": "normal", "90": "90", "180": "180", "270": "270", 
                         "Flipped": "flipped", "Flipped90": "flipped-90", 
                         "Flipped180": "flipped-180", "Flipped270": "flipped-270"}
            
            for name, mon in monitors_dict.items():
                # Get current mode info
                current_mode_idx = mon.get("current_mode", 0)
                modes_list = mon.get("modes", [])
                current_mode = modes_list[current_mode_idx] if modes_list and current_mode_idx < len(modes_list) else {}
                
                logical = mon.get("logical", {})
                
                # Store raw make/model for accurate matching (not just description)
                raw_make = mon.get("make", "")
                raw_model = mon.get("model", "")
                raw_serial = mon.get("serial")
                physical_size = mon.get("physical_size", [])
                
                # Format description for backward compatibility
                description = f'{raw_make} {raw_model} {raw_serial or ""}'.strip()
                
                outputs_dict[name] = {
                    "active": True,  # If it's in the list, it's active
                    "dpms": True,
                    "description": description,
                    "x": int(logical.get("x", 0)),
                    "y": int(logical.get("y", 0)),
                    "logical-width": int(logical.get("width", 0)),
                    "logical-height": int(logical.get("height", 0)),
                    "physical-width": int(current_mode.get("width", 0)),
                    "physical-height": int(current_mode.get("height", 0)),
                    "transform": transforms.get(logical.get("transform", "Normal"), "normal"),
                    "scale": float(logical.get("scale", 1.0)),
                    "scale_filter": "linear",
                    "refresh": round(float(current_mode.get("refresh_rate", 60000)) / 1000, 2),
                    "modes": [],
                    "focused": mon.get("is_focused", False),
                    "adaptive_sync_status": "enabled" if mon.get("vrr_enabled", False) else "disabled",
                    "mirror": "",
                    "ten_bit": False,
                    "monitor": None,
                    # Store raw make/model for matching
                    "__niri_make": raw_make,
                    "__niri_model": raw_model,
                    "__niri_serial": raw_serial,
                    "__niri_physical_size": physical_size,
                }
                
                # Parse available modes
                for mode in modes_list:
                    try:
                        outputs_dict[name]["modes"].append({
                            "width": int(mode.get("width", 0)),
                            "height": int(mode.get("height", 0)),
                            "refresh": float(mode.get("refresh_rate", 60000))
                        })
                    except:
                        pass
        except json.JSONDecodeError as e:
            eprint(f"[niri] JSON decode error: {e}")
            return {}
        except Exception as e:
            eprint(f"Error parsing niri outputs: {e}")
            # Return empty dict if parsing fails
            return {}
            
    elif os.getenv("SWAYSOCK"):
        outputs_dict = {}
        eprint("Running on sway")
        i3 = Connection()
        tree = i3.get_tree()
        for item in tree:
            if item.type == "output" and not item.name.startswith("__"):
                outputs_dict[item.name] = {"x": item.rect.x,
                                           "y": item.rect.y,
                                           "logical-width": item.rect.width,
                                           "logical-height": item.rect.height,
                                           "physical-width": item.ipc_data["current_mode"]["width"],
                                           "physical-height": item.ipc_data["current_mode"]["height"]}

                outputs_dict[item.name]["active"] = item.ipc_data["active"]
                outputs_dict[item.name]["dpms"] = item.ipc_data["dpms"]
                outputs_dict[item.name]["transform"] = item.ipc_data[
                    "transform"] if "transform" in item.ipc_data else None
                outputs_dict[item.name]["scale"] = float(item.ipc_data["scale"]) if "scale" in item.ipc_data else None
                outputs_dict[item.name]["scale_filter"] = item.ipc_data["scale_filter"]
                outputs_dict[item.name]["adaptive_sync_status"] = item.ipc_data["adaptive_sync_status"]
                outputs_dict[item.name]["refresh"] = \
                    item.ipc_data["current_mode"]["refresh"] / 1000 if "refresh" in item.ipc_data[
                        "current_mode"] else None
                outputs_dict[item.name]["modes"] = item.ipc_data["modes"] if "modes" in item.ipc_data else []
                outputs_dict[item.name]["description"] = "{} {} {}".format(item.ipc_data["make"],
                                                                           item.ipc_data["model"],
                                                                           item.ipc_data["serial"])
                outputs_dict[item.name]["focused"] = item.ipc_data["focused"]

                outputs_dict[item.name]["mirror"] = ""  # We only use it on Hyprland
                outputs_dict[item.name]["ten_bit"] = False  # We have no way to check it on sway
                outputs_dict[item.name]["monitor"] = None

    elif os.getenv("HYPRLAND_INSTANCE_SIGNATURE"):
        monitors_all = json.loads(hyprctl("j/monitors all"))
        monitors = json.loads(hyprctl("j/monitors"))
        active = []
        for item in monitors:
            active.append(item["name"])
        outputs_dict = {}
        for mon in monitors_all:
            name = mon["name"]
            outputs_dict[name] = {"active": True} if name in active else {"active": False}

        eprint("Running on Hyprland")

        # 1. Mirroring is impossible to check in any way. We need to parse back the monitors.conf file, and it sucks.
        mirrors = {}
        hypr_config_dir = os.path.join(get_config_home(), "hypr")
        monitors_file = os.path.join(hypr_config_dir, "monitors.conf")
        if os.path.isfile(monitors_file):
            lines = load_text_file(monitors_file).splitlines()
            for line in lines:
                if line and not line.startswith("#"):  # skip comments
                    if "mirror" in line:
                        settings = line.split("=")[1].split(",")
                        mirrors[settings[0].strip()] = settings[-1].strip()

        # 2. This won't work w/ Hyprland <= 0.36.0
        output = hyprctl("j/monitors all")
        monitors = json.loads(output)
        transforms = {0: "normal", 1: "90", 2: "180", 3: "270", 4: "flipped", 5: "flipped-90", 6: "flipped-180",
                      7: "flipped-270"}
        for m in monitors:
            outputs_dict[m["name"]]["mirror"] = mirrors[name] if name in mirrors else ""

            outputs_dict[m["name"]]["scale_filter"] = None
            outputs_dict[m["name"]]["modes"] = []
            outputs_dict[m["name"]]["focused"] = m["focused"]
            outputs_dict[m["name"]]["adaptive_sync_status"] = "enabled" if m["vrr"] else "disabled"

            outputs_dict[m["name"]]["description"] = f'{m["description"]}'
            outputs_dict[m["name"]]["x"] = int(m["x"])
            outputs_dict[m["name"]]["y"] = int(m["y"])

            outputs_dict[m["name"]]["refresh"] = round(m["refreshRate"], 2)

            outputs_dict[m["name"]]["logical-width"] = m["width"] / m["scale"]
            outputs_dict[m["name"]]["logical-height"] = m["height"] / m["scale"]

            outputs_dict[m["name"]]["physical-width"] = m["width"]
            outputs_dict[m["name"]]["physical-height"] = m["height"]

            outputs_dict[m["name"]]["transform"] = transforms[m["transform"]]
            outputs_dict[m["name"]]["scale"] = m["scale"]
            outputs_dict[m["name"]]["focused"] = m["focused"]
            outputs_dict[m["name"]]["dpms"] = m["dpmsStatus"]

            outputs_dict[name]["modes"] = []

            for item in m["availableModes"]:
                line = item[:-2]  # split "Hz"
                w_h, r = line.split("@")
                w, h = w_h.split("x")
                try:
                    mode = {"width": int(w), "height": int(h), "refresh": float(r) * 1000}
                except ValueError as e:
                    eprint(e)
                outputs_dict[m["name"]]["modes"].append(mode)

            outputs_dict[m["name"]]["ten_bit"] = True if m["currentFormat"] in ["XRGB2101010", "XBGR2101010"] else False

            # to identify Gdk.Monitor
            outputs_dict[m["name"]]["model"] = m["model"]

            outputs_dict[m["name"]]["monitor"] = None

    else:
        eprint("This program only supports sway, Hyprland and niri, and we seem to be elsewhere, terminating.")
        sys.exit(1)

    # We used to assign Gdk.Monitor to output on the basis of x and y coordinates, but it no longer works,
    # starting from gtk3-1:3.24.42: all monitors have x=0, y=0. This is most likely a bug, but from now on
    # we must rely on gdk monitors order.
    # For niri, we use property-based matching to avoid order issues after config reload.
    monitors = []
    display = Gdk.Display.get_default()
    for i in range(display.get_n_monitors()):
        monitor = display.get_monitor(i)
        monitors.append(monitor)

    if os.getenv("NIRI_SOCKET"):
        # Niri: Use property-based matching (manufacturer + model + physical_size)
        # Note: GdkWaylandMonitor doesn't have get_serial(), only manufacturer+model+size
        gdk_lookup = {}
        for m in monitors:
            manufacturer = m.get_manufacturer() or ""
            model = m.get_model() or ""
            width_mm = m.get_width_mm()
            height_mm = m.get_height_mm()
            physical_size = f"{width_mm}x{height_mm}" if width_mm and height_mm else ""
            # Use manufacturer + model + physical_size for matching
            key = f"{manufacturer}|{model}|{physical_size}"
            if key not in gdk_lookup:
                gdk_lookup[key] = m

        for key in outputs_dict:
            if key in outputs_dict:
                data = outputs_dict[key]
                
                # Use raw niri data if available (preferred)
                make = data.get("__niri_make", "")
                model = data.get("__niri_model", "")
                
                # Get physical size from output data (try multiple sources)
                physical_size = data.get("__niri_physical_size", [])
                if not physical_size:
                    # Fallback to physical-width/physical-height if no physical_size
                    physical_size = [data.get("physical_width", 0), data.get("physical_height", 0)]
                
                size_str = f"{physical_size[0]}x{physical_size[1]}" if len(physical_size) >= 2 else ""
                
                match_key = f"{make}|{model}|{size_str}"
                if match_key in gdk_lookup:
                    outputs_dict[key]["monitor"] = gdk_lookup[match_key]
                else:
                    # Fallback to index matching if no match found
                    idx = 0
                    for k in outputs_dict:
                        if k == key:
                            break
                        idx += 1
                    if idx < len(monitors):
                        outputs_dict[key]["monitor"] = monitors[idx]
    else:
        # Sway/Hyprland: Keep original index-based matching
        idx = 0
        for key in outputs_dict:
            try:
                outputs_dict[key]["monitor"] = monitors[idx]
            except IndexError:
                print(f"Couldn't assign a Gdk.Monitor to {outputs_dict[key]}")
            idx += 1

    for key in outputs_dict:
        eprint(key, outputs_dict[key])
    return outputs_dict


def list_outputs_activity():
    result = {}
    if os.getenv("NIRI_SOCKET"):
        outputs = list_outputs()
        for name in outputs:
            result[name] = outputs[name].get("active", True)
    elif os.getenv("SWAYSOCK"):
        i3 = Connection()
        outputs = i3.get_outputs()
        for o in outputs:
            result[o.name] = o.active

    elif os.getenv("HYPRLAND_INSTANCE_SIGNATURE"):
        monitors_all = json.loads(hyprctl("j/monitors all"))
        monitors = json.loads(hyprctl("j/monitors"))
        active = []
        for item in monitors:
            active.append(item["name"])

        for mon in monitors_all:
            name = mon["name"]
            result[name] = True if name in active else False

    return result


def max_window_height():
    if os.getenv("SWAYSOCK"):
        i3 = Connection()
        outputs = i3.get_outputs()
        for o in outputs:
            if o.focused:
                if o.rect.width > o.rect.height:
                    return o.rect.height * 0.9
                else:
                    return o.rect.height / 2 * 0.9
    return None


def scale_if_floating():
    pid = os.getpid()
    if os.getenv("SWAYSOCK"):
        i3 = Connection()
        node = i3.get_tree().find_by_pid(pid)[0]
        if node.type == "floating_con":
            h = int(max_window_height())
            if h:
                i3.command("resize set height {}".format(h))


def min_val(a, b):
    if b < a:
        return b
    return a


def max_val(a, b):
    if b > a:
        return b
    return a


def round_down_to_multiple(i, m):
    return i / m * m


def round_to_nearest_multiple(i, m):
    if i % m > m / 2:
        return (i / m + 1) * m
    return i / m * m


def orientation_changed(transform, transform_old):
    return (is_rotated(transform) and not is_rotated(transform_old)) or (
            is_rotated(transform_old) and not is_rotated(transform))


def is_rotated(transform):
    return "90" in transform or "270" in transform


def inactive_output_description(name):
    if os.getenv("SWAYSOCK"):
        i3 = Connection()
        for item in i3.get_outputs():
            if item.name == name:
                return "{} {} {}".format(item.ipc_data["make"], item.ipc_data["model"],
                                         item.ipc_data["serial"])
    return None


def config_keys_missing(config, config_file):
    key_missing = False
    defaults = {
        "view-scale": 0.15,
        "snap-threshold": 10,
        "indicator-timeout": 500,
        "custom-mode": [],
        "use-desc": False,
        "confirm-timeout": 10,
        "profile-bound-wallpapers": True,
    }
    for key in defaults:
        if key not in config:
            config[key] = defaults[key]
            print("Added missing config key: '{}'".format(key), file=sys.stderr)
            key_missing = True

    if key_missing:
        save_json(config, config_file)

    return key_missing


def load_json(path):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print("Error loading json: {}".format(e))
        return None


def save_json(src_dict, path):
    with open(path, 'w') as f:
        json.dump(src_dict, f, indent=2)


def save_list_to_text_file(data, file_path):
    text_file = open(file_path, "w")
    for line in data:
        text_file.write(line + "\n")
    text_file.close()


def save_kdl_output(data, file_path):
    """Save output configuration in KDL format for niri"""
    text_file = open(file_path, "w")
    now = datetime.datetime.now()
    line = "// Generated by nwg-displays on {} at {}. Do not edit manually.\n".format(
        datetime.datetime.strftime(now, '%Y-%m-%d'),
        datetime.datetime.strftime(now, '%H:%M:%S'))
    text_file.write(line + "\n")
    
    for d in data:
        name = d["name"]
        if not d["active"]:
            text_file.write(f'output "{name}" {{\n    off\n}}\n\n')
            continue
        
        text_file.write(f'output "{name}" {{\n')
        
        # Mode
        text_file.write(f'    mode "{d["physical_width"]}x{d["physical_height"]}@{d["refresh"]}"\n')
        
        # Scale
        text_file.write(f'    scale {d["scale"]}\n')
        
        # Transform
        if d["transform"] != "normal":
            text_file.write(f'    transform "{d["transform"]}"\n')
        
        # Position
        text_file.write(f'    position x={d["x"]} y={d["y"]}\n')
        
        # Variable refresh rate (adaptive sync)
        if d.get("adaptive_sync", False):
            text_file.write(f'    variable-refresh-rate\n')
        
        text_file.write(f'}}\n\n')
    
    text_file.close()


def ensure_niri_config_include(config_dir, monitors_file):
    """Ensure that config.kdl includes monitor.kdl"""
    config_kdl = os.path.join(config_dir, "config.kdl")
    monitors_rel_path = "monitor.kdl"
    
    # Check if config.kdl exists
    if not os.path.isfile(config_kdl):
        # Create a minimal config.kdl with include
        with open(config_kdl, "w") as f:
            f.write(f'// Include monitor configuration generated by nwg-displays\n')
            f.write(f'include "{monitors_rel_path}"\n')
        eprint(f"[niri] Created {config_kdl} with include directive")
        return
    
    # Read existing config
    content = load_text_file(config_kdl)
    if content is None:
        return
    
    lines = content.splitlines()
    
    # Check if include already exists
    include_pattern = f'include "{monitors_rel_path}"'
    include_pattern_single = f"include '{monitors_rel_path}'"
    
    for line in lines:
        if include_pattern in line or include_pattern_single in line:
            # Already included
            return
    
    # Add include directive at the beginning
    new_content = f'// Include monitor configuration generated by nwg-displays\ninclude "{monitors_rel_path}"\n\n{content}'
    
    with open(config_kdl, "w") as f:
        f.write(new_content)
    
    eprint(f"[niri] Added include directive to {config_kdl}")


def create_empty_file(file_path):
    if not os.path.isfile(file_path):
        with open(file_path, "w") as file:
            pass


def load_text_file(path):
    try:
        with open(path, 'r') as file:
            data = file.read()
            return data
    except Exception as e:
        print(e)
        return None


def load_workspaces(path, use_desc=False):
    result = {}
    try:
        with open(path, 'r') as file:
            data = file.read().splitlines()
            for i in range(len(data)):
                if data[i] and not data[i].startswith("#"):  # skip comments
                    info = data[i].split("workspace ")[1].split()
                    num = int(info[0])
                    if not use_desc:
                        result[num] = info[2]
                    else:
                        result[num] = data[i].split("output ")[1][1:-1]
            return result
    except Exception as e:
        print(e)
        return result


# We will read all the meaningful lines if -n argument not given or >= number of lines.
def load_workspaces_hypr(path, num_ws=0):
    ws_binds = {}
    meaningful_lines_read = 0
    try:
        with open(path, 'r') as file:
            data = file.read().splitlines()
            r = len(data)
            for i in range(r):
                line = data[i]
                if line and not line.startswith("#"):  # skip comments
                    meaningful_lines_read += 1
                    # Binding workspaces to a monitor, e.g.:
                    # 'workspace=1,monitor:desc:AOC 2475WR F17H4QA000449' or
                    # 'workspace=1,monitor:HDMI-A-1'
                    ws_num = None
                    parts = line.split(",")
                    try:
                        ws_num = int(parts[0].split("=")[1])
                    except:
                        pass
                    mon = parts[1].split(":")[-1]
                    if ws_num:
                        ws_binds[ws_num] = mon

                    if num_ws > 0:
                        if meaningful_lines_read == num_ws:
                            break

            return ws_binds

    except Exception as e:
        eprint("Error parsing workspaces.conf file: {}".format(e))
        return {}


def save_workspaces(data_dict, path, use_desc=False):
    text_file = open(path, "w")
    now = datetime.datetime.now()
    line = "# Generated by nwg-displays on {} at {}. Do not edit manually.\n".format(
        datetime.datetime.strftime(now, '%Y-%m-%d'),
        datetime.datetime.strftime(now, '%H:%M:%S'))
    text_file.write(line + "\n")
    for key in data_dict:
        if not use_desc:
            line = "workspace {} output {}".format(key, data_dict[key])
        else:
            line = "workspace {} output '{}'".format(key, data_dict[key])
        text_file.write(line + "\n")
    text_file.close()


def notify(summary, body, timeout=3000):
    cmd = "notify-send '{}' '{}' -i /usr/share/pixmaps/nwg-displays.svg -t {}".format(summary, body, timeout)
    subprocess.call(cmd, shell=True)


def get_shell_data_dir():
    data_dir = ""
    home = os.getenv("HOME")
    xdg_data_home = os.getenv("XDG_DATA_HOME")

    if xdg_data_home:
        data_dir = os.path.join(xdg_data_home, "nwg-shell/")
    else:
        if home:
            data_dir = os.path.join(home, ".local/share/nwg-shell/")

    return data_dir


def load_shell_data():
    shell_data_file = os.path.join(get_shell_data_dir(), "data")
    shell_data = load_json(shell_data_file) if os.path.isfile(shell_data_file) else {}

    defaults = {
        "interface-locale": ""
    }

    for key in defaults:
        if key not in shell_data:
            shell_data[key] = defaults[key]

    return shell_data

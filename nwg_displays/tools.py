# !/usr/bin/env python3
import datetime
import json
import os
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


def hyprctl(cmd):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect("/tmp/hypr/{}/.socket.sock".format(os.getenv("HYPRLAND_INSTANCE_SIGNATURE")))

    s.send(cmd.encode("utf-8"))
    output = s.recv(20480).decode('utf-8')
    s.close()

    return output


def is_command(cmd):
    cmd = cmd.split()[0]
    cmd = "command -v {}".format(cmd)
    try:
        is_cmd = subprocess.check_output(
            cmd, shell=True).decode("utf-8").strip()
        if is_cmd:
            return True

    except subprocess.CalledProcessError:
        return False


def list_outputs():
    outputs_dict = {}

    if os.getenv("SWAYSOCK"):
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
                outputs_dict[item.name]["monitor"] = None

    elif os.getenv("HYPRLAND_INSTANCE_SIGNATURE"):
        eprint("Running on Hyprland")
        # This will be tricky. The `hyprctl monitors` command returns just a part of the output attributes we need.
        # The `wlr-randr` command returns almost everything, but not "focused". We need to use both commands. :/

        # 1. Mirroring is impossible to check in any way. We need to parse back the monitors.conf file, and it sucks.
        mirrors = {}
        monitors_file = os.path.join(os.getenv("HOME"), ".config/hypr/monitors.conf")
        if os.path.isfile(monitors_file):
            lines = load_text_file(monitors_file).splitlines()
            for line in lines:
                if line and not line.startswith("#"):  # skip comments
                    if "mirror" in line:
                        settings = line.split("=")[1].split(",")
                        mirrors[settings[0].strip()] = settings[-1].strip()

        # 2. Read all the available values from wlr-randr
        if not is_command("wlr-randr"):
            eprint("wlr-randr package required, but not found, terminating.")
            sys.exit(1)
        lines = subprocess.check_output("wlr-randr", shell=True).decode("utf-8").strip().splitlines()
        name = ""
        for line in lines:
            if not line.startswith(" "):
                name = line.split()[0]
                description = line.replace(name, "")[2:-4]
                # It may happen that the description contains the adapter translations in parens, e.g.:
                # LG Electronics LG ULTRAGEAR 1231234F (DP-2 via HDMI)"
                description = description.split(" (")[0]
                # Just grab the pure description, e.g. "LG Electronics LG ULTRAGEAR 1231234F"
                outputs_dict[name] = {"description": description,
                                      "active": False,
                                      "focused": False,
                                      "modes": [],
                                      "scale_filter": None,  # unavailable via wlr-randr nor hyprctl
                                      "dpms": None,  # unavailable via wlr-randr nor hyprctl
                                      "mirror": "",
                                      "monitor": None,  # we'll assign a Gdk monitor here later
                                      # Prevent from crashing in case we couldn't get it w/ wlr-randr nor hyprctl.
                                      # On Hyprland we make no use of it anyway, as there's no way to turn it on/off.
                                      "adaptive_sync_status": False
                                      }

            if name in mirrors:
                outputs_dict[name]["mirror"] = mirrors[name]

            if "Position" in line:
                x_y = line.split()[1].split(',')
                outputs_dict[name]["x"] = int(x_y[0])
                outputs_dict[name]["y"] = int(x_y[1])
            if line.startswith("  Enabled"):
                outputs_dict[name]["active"] = line.split()[1] == "yes"
            if line.startswith("    "):
                parts = line.split()
                mode = {"width": int(parts[0].split("x")[0]), "height": int(parts[0].split("x")[1]),
                        "refresh": float(parts[2]) * 1000}
                modes = outputs_dict[name]["modes"]
                modes.append(mode)
                outputs_dict[name]["modes"] = modes
                if "current" in line:
                    w_h = line.split()[0].split('x')
                    outputs_dict[name]["physical-width"] = int(w_h[0])
                    outputs_dict[name]["physical-height"] = int(w_h[1])
                    outputs_dict[name]["refresh"] = float(parts[2])

            # This may or may not work. We'll try to read the value again from hyprctl -j monitors.
            if name and line.startswith("  Adaptive Sync:"):
                outputs_dict[name]["adaptive_sync_status"] = line.split()[1]

            if "Transform:" in line:
                outputs_dict[name]["transform"] = line.split()[1]
            if "Scale" in line:
                s = float(line.split()[1])
                outputs_dict[name]["scale"] = s
                outputs_dict[name]["logical-width"] = outputs_dict[name]["physical-width"] / s
                outputs_dict[name]["logical-height"] = outputs_dict[name]["physical-height"] / s

        # 3. Read missing/possibly missing values from hyprctl
        output = hyprctl("j/monitors")
        monitors = json.loads(output)
        for m in monitors:
            # wlr-rand does not return this value
            outputs_dict[m["name"]]["focused"] = m["focused"] == "yes"
            # This may be missing from wlr-rand output, see https://github.com/nwg-piotr/nwg-displays/issues/21
            outputs_dict[m["name"]]["adaptive_sync_status"] = "enabled" if m["vrr"] else "disabled"

    else:
        eprint("This program only supports sway and Hyprland, and we seem to be elsewhere, terminating.")
        sys.exit(1)

    # assign Gdk monitors
    display = Gdk.Display.get_default()
    for i in range(display.get_n_monitors()):
        monitor = display.get_monitor(i)
        geometry = monitor.get_geometry()

        for key in outputs_dict:
            if int(outputs_dict[key]["x"]) == geometry.x and int(outputs_dict[key]["y"]) == geometry.y:
                outputs_dict[key]["monitor"] = monitor
                break

    for key in outputs_dict:
        eprint(key, outputs_dict[key])
    return outputs_dict


def list_outputs_activity():
    result = {}
    if os.getenv("SWAYSOCK"):
        i3 = Connection()
        outputs = i3.get_outputs()
        for o in outputs:
            result[o.name] = o.active

    elif os.getenv("HYPRLAND_INSTANCE_SIGNATURE"):
        lines = subprocess.check_output("wlr-randr", shell=True).decode("utf-8").strip().splitlines()
        name = ""
        for line in lines:
            if not line.startswith(" "):
                name = line.split()[0]
            if name and line.startswith("  Enabled"):
                result[name] = line.split()[1] == "yes"

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
    defaults = {"view-scale": 0.15,
                "snap-threshold": 10,
                "indicator-timeout": 500,
                "custom-mode": [],
                "use-desc": False, }
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

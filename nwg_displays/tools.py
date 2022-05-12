# !/usr/bin/env python3

import json
import os
import subprocess
import sys
import time

import gi

gi.require_version('Gdk', '3.0')
from gi.repository import Gdk

from i3ipc import Connection


def get_config_home():
    xdg_config_home = os.getenv('XDG_CONFIG_HOME')
    config_home = xdg_config_home if xdg_config_home else os.path.join(
        os.getenv("HOME"), ".config")

    return config_home


def list_outputs():
    outputs_dict = {}

    i3 = Connection()
    tree = i3.get_tree()
    for item in tree:
        if item.type == "output" and not item.name.startswith("__"):
            outputs_dict[item.name] = {"x": item.rect.x,
                                       "y": item.rect.y,
                                       "width": item.rect.width,
                                       "height": item.rect.height}

            outputs_dict[item.name]["active"] = item.ipc_data["active"]
            outputs_dict[item.name]["dpms"] = item.ipc_data["dpms"]
            outputs_dict[item.name]["transform"] = item.ipc_data["transform"] if "transform" in item.ipc_data else None
            outputs_dict[item.name]["scale"] = float(item.ipc_data["scale"]) if "scale" in item.ipc_data else None
            outputs_dict[item.name]["scale_filter"] = item.ipc_data["scale_filter"]
            outputs_dict[item.name]["adaptive_sync_status"] = item.ipc_data["adaptive_sync_status"]
            outputs_dict[item.name]["refresh"] = \
                item.ipc_data["current_mode"]["refresh"] / 1000 if "refresh" in item.ipc_data["current_mode"] else None
            outputs_dict[item.name]["modes"] = item.ipc_data["modes"] if "modes" in item.ipc_data else []
            outputs_dict[item.name]["description"] = "{} {} {}".format(item.ipc_data["make"], item.ipc_data["model"],
                                                                       item.ipc_data["serial"])
            outputs_dict[item.name]["focused"] = item.ipc_data["focused"]

            outputs_dict[item.name]["monitor"] = None

    display = Gdk.Display.get_default()
    for i in range(display.get_n_monitors()):
        monitor = display.get_monitor(i)
        geometry = monitor.get_geometry()

        for key in outputs_dict:
            if int(outputs_dict[key]["x"]) == geometry.x and int(outputs_dict[key]["y"]) == geometry.y and int(
                    outputs_dict[key]["width"]) == geometry.width and int(
                    outputs_dict[key]["height"]) == geometry.height:
                outputs_dict[key]["monitor"] = monitor
                break

    return outputs_dict


def list_outputs_activity():
    result = {}
    i3 = Connection()
    outputs = i3.get_outputs()
    for o in outputs:
        result[o.name] = o.active

    return result


def max_window_height():
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


def apply_settings(display_buttons, outputs_activity, outputs_path, g_names=False):
    lines = []
    cmds = []
    db_names = []
    # just active outputs have their buttons
    for db in display_buttons:
        name = db.name if not g_names else db.description
        db_names.append(name)

        lines.append('output "%s" {' % name)
        cmd = 'output "{}"'.format(name)

        custom_mode_str = "--custom" if db.custom_mode else ""
        lines.append("    mode {} {}x{}@{}Hz".format(custom_mode_str, db.width, db.height, db.refresh))
        cmd += " mode {} {}x{}@{}Hz".format(custom_mode_str, db.width, db.height, db.refresh)

        lines.append("    pos {} {}".format(db.x, db.y))
        cmd += " pos {} {}".format(db.x, db.y)

        lines.append("    transform {}".format(db.transform))
        cmd += " transform {}".format(db.transform)

        lines.append("    scale {}".format(db.scale))
        cmd += " scale {}".format(db.scale)

        lines.append("    scale_filter {}".format(db.scale_filter))
        cmd += " scale_filter {}".format(db.scale_filter)

        a_s = "on" if db.adaptive_sync else "off"
        lines.append("    adaptive_sync {}".format(a_s))
        cmd += " adaptive_sync {}".format(a_s)

        dpms = "on" if db.dpms else "off"
        lines.append("    dpms {}".format(dpms))
        cmd += " dpms {}".format(dpms)

        lines.append("}")
        cmds.append(cmd)

    if not g_names:
        for key in outputs_activity:
            if key not in db_names:
                lines.append('output "{}" disable'.format(key))
                cmds.append('output "{}" disable'.format(key))
    else:
        for key in outputs_activity:
            desc = inactive_output_description(key)
            if desc not in db_names:
                lines.append('output "{}" disable'.format(desc))
                cmds.append('output "{}" disable'.format(desc))

    print("[Saving]")
    for line in lines:
        print(line)

    save_list_to_text_file(lines, outputs_path)

    print("[Executing]")
    for cmd in cmds:
        print(cmd)

    i3 = Connection()
    for cmd in cmds:
        i3.command(cmd)


def inactive_output_description(name):
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
                "custom-mode": [],}
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


def load_workspaces(path):
    result = {}
    try:
        with open(path, 'r') as file:
            data = file.read().splitlines()
            for i in range(len(data)):
                result[i + 1] = data[i].split()[3]
            return result
    except Exception as e:
        print(e)
        return result


def save_workspaces(data_dict, path):
    text_file = open(path, "w")
    for key in data_dict:
        line = "workspace {} output {}".format(key, data_dict[key])
        text_file.write(line + "\n")
    text_file.close()


def notify(summary, body, timeout=3000):
    cmd = "notify-send '{}' '{}' -i /usr/share/pixmaps/nwg-displays.svg -t {}".format(summary, body, timeout)
    subprocess.call(cmd, shell=True)

# !/usr/bin/env python3

import os
import json
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
    """
    Get output names and geometry from i3 tree, assign to Gdk.Display monitors.
    :return: {"name": str, "x": int, "y": int, "width": int, "height": int, "monitor": Gkd.Monitor}
    """
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

    display = Gdk.Display.get_default()
    for i in range(display.get_n_monitors()):
        monitor = display.get_monitor(i)
        geometry = monitor.get_geometry()

        for key in outputs_dict:
            if int(outputs_dict[key]["x"]) == geometry.x and int(outputs_dict[key]["y"]) == geometry.y:
                outputs_dict[key]["monitor"] = monitor

    return outputs_dict


def list_outputs_activity():
    result = {}
    i3 = Connection()
    outputs = i3.get_outputs()
    for o in outputs:
        result[o.name] = o.active

    return result


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


def apply_settings(display_buttons, outputs_activity, output_path, g_names=False):
    lines = []
    cmds = []
    db_names = []
    # just active outputs have their buttons
    for db in display_buttons:
        name = db.name if not g_names else db.description
        db_names.append(name)

        lines.append('output "%s" {' % name)
        cmd = 'output "{}"'.format(name)

        lines.append("    mode {}x{}@{}Hz".format(db.width, db.height, db.refresh))
        cmd + " mode {}x{}@{}Hz".format(db.width, db.height, db.refresh)

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

    # Append inactive outputs, if any. Note: if Thunderbolt output names actually are different after every reboot
    # (wish I knew), we have no way to disable them on startup.
    if not g_names:
        for key in outputs_activity:
            if key not in db_names:
                lines.append('output "{}" disable'.format(key))
                cmds.append('output "{}" disable'.format(key))

    print("\nSaving: \n")
    for line in lines:
        print(line)

    save_list_to_text_file(lines, output_path)

    print("\nExecuting: \n")
    for cmd in cmds:
        print(cmd)

    i3 = Connection()
    for cmd in cmds:
        i3.command(cmd)


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

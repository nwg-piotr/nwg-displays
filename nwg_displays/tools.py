# !/usr/bin/env python3

import sys
import gi

gi.require_version('Gdk', '3.0')
from gi.repository import Gdk


def list_outputs():
    """
    Get output names and geometry from i3 tree, assign to Gdk.Display monitors.
    :return: {"name": str, "x": int, "y": int, "width": int, "height": int, "monitor": Gkd.Monitor}
    """
    outputs_dict = {}
    try:
        from i3ipc import Connection
    except ModuleNotFoundError:
        print("'python-i3ipc' package required on sway, terminating")
        sys.exit(1)

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

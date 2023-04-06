#!/usr/bin/env python

"""
Output management utility for sway Wayland compositor, inspired by wdisplays and wlay
Project: https://github.com/nwg-piotr/nwg-displays
Author's email: nwg.piotr@gmail.com
Copyright (c) 2022 Piotr Miller
License: MIT
Depends on: 'python-i3ipc' 'gtk-layer-shell'

All the code below was built around this glorious snippet:
https://gist.github.com/KurtJacobson/57679e5036dc78e6a7a3ba5e0155dad1
Thank you, Kurt Jacobson!
"""

import argparse
import os.path
import sys

import gi

gi.require_version('Gtk', '3.0')
try:
    gi.require_version('GtkLayerShell', '0.1')
except ValueError:
    raise RuntimeError('\n\n' +
                       'If you haven\'t installed GTK Layer Shell, you need to point Python to the\n' +
                       'library by setting GI_TYPELIB_PATH and LD_LIBRARY_PATH to <build-dir>/src/.\n' +
                       'For example you might need to run:\n\n' +
                       'GI_TYPELIB_PATH=build/src LD_LIBRARY_PATH=build/src python3 ' + ' '.join(sys.argv))

from gi.repository import Gtk, GLib, GtkLayerShell

from nwg_displays.tools import *

from nwg_displays.__about__ import __version__

dir_name = os.path.dirname(__file__)
sway = os.getenv("SWAYSOCK") is not None
hypr = os.getenv("HYPRLAND_INSTANCE_SIGNATURE") is not None

config_dir = os.path.join(get_config_home(), "nwg-displays")
# This was done by mistake, and the config file need to be migrated to the proper path
old_config_dir = os.path.join(get_config_home(), "nwg-outputs")

sway_config_dir = os.path.join(get_config_home(), "sway")
if not os.path.isdir(sway_config_dir):
    print("WARNING: Couldn't find sway config directory '{}'".format(sway_config_dir), file=sys.stderr)
    sway_config_dir = ""

hypr_config_dir = os.path.join(os.getenv("HOME"), ".config/hypr/")
if not os.path.isdir(hypr_config_dir):
    print("WARNING: Couldn't find Hyprland config directory '{}'".format(hypr_config_dir), file=sys.stderr)
    hypr_config_dir = ""

config = {}
outputs_path = ""
generic_names = False
num_ws = 0

"""
i3.get_outputs() does not return some output attributes, especially when connected via hdmi.
i3.get_tree() on the other hand does not return inactive outputs. So we'll list attributes with .get_tree(),
and the add inactive outputs, if any, from what we detect with .get_outputs()
"""
outputs = {}  # Active outputs, listed from the sway tree; stores name and all attributes.
outputs_activity = {}  # Just a dictionary "name": is_active - from get_outputs()
workspaces = {}  # "workspace_num": "display_name"
default_workspaces_hypr = {}

display_buttons = []
selected_output_button = None

# Glade form fields
form_name = None
form_description = None
form_dpms = None
form_adaptive_sync = None
form_custom_mode = None
form_view_scale = None
form_x = None
form_y = None
form_width = None
form_height = None
form_scale = None
form_scale_filter = None
form_refresh = None
form_modes = None
form_transform = None
form_wrapper_box = None
form_workspaces = None
form_close = None
form_apply = None
form_version = None
form_mirror = None

dialog_win = None

"""
We need to rebuild the modes GtkComboBoxText on each DisplayButton click. Unfortunately appending an item fires the
"change" event every time (and we have no "value-changed" event here). Setting `on_mode_changed_silent` True will 
prevent the `on_mode_changed` function from working.
"""
on_mode_changed_silent = False

# Value from config adjusted to current view scale
snap_threshold_scaled = None

fixed = Gtk.Fixed()

SENSITIVITY = 1

EvMask = Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON1_MOTION_MASK

offset_x = 0
offset_y = 0
px = 0
py = 0
max_x = 0
max_y = 0

voc = {}


def load_vocabulary():
    global voc
    # basic vocabulary (for en_US)
    voc = load_json(os.path.join(dir_name, "langs", "en_US.json"))
    if not voc:
        eprint("Failed loading vocabulary, terminating")
        sys.exit(1)

    shell_data = load_shell_data()
    lang = os.getenv("LANG").split(".")[0] if not shell_data["interface-locale"] else shell_data["interface-locale"]
    # translate if translation available
    if lang != "en_US":
        loc_file = os.path.join(dir_name, "langs", "{}.json".format(lang))
        if os.path.isfile(loc_file):
            # localized vocabulary
            loc = load_json(loc_file)
            if not loc:
                eprint("Failed loading translation into '{}'".format(lang))
            else:
                for key in loc:
                    voc[key] = loc[key]


def on_button_press_event(widget, event):
    if widget != selected_output_button:
        widget.indicator.show_up()

    if event.button == 1:
        for db in display_buttons:
            if db.name == widget.name:
                db.select()
            else:
                db.unselect()

        p = widget.get_parent()
        # offset == distance of parent widget from edge of screen ...
        global offset_x, offset_y
        offset_x, offset_y = p.get_window().get_position()
        # plus distance from pointer to edge of widget
        offset_x += event.x
        offset_y += event.y
        # max_x, max_y both relative to the parent
        # note that we're rounding down now so that these max values don't get
        # rounded upward later and push the widget off the edge of its parent.
        global max_x, max_y
        max_x = round_down_to_multiple(p.get_allocation().width - widget.get_allocation().width, SENSITIVITY)
        max_y = round_down_to_multiple(p.get_allocation().height - widget.get_allocation().height, SENSITIVITY)

        update_form_from_widget(widget)


def on_motion_notify_event(widget, event):
    # x_root,x_root relative to screen
    # x,y relative to parent (fixed widget)
    # px,py stores previous values of x,y

    global px, py
    global offset_x, offset_y

    # get starting values for x,y
    x = event.x_root - offset_x
    y = event.y_root - offset_y
    # make sure the potential coordinates x,y:
    #   1) will not push any part of the widget outside of its parent container
    #   2) is a multiple of SENSITIVITY
    x = round_to_nearest_multiple(max_val(min_val(x, max_x), 0), SENSITIVITY)
    y = round_to_nearest_multiple(max_val(min_val(y, max_y), 0), SENSITIVITY)

    if x != px or y != py:
        px = x
        py = y
        snap_x, snap_y = [0], [0]
        for db in display_buttons:
            if db.name == widget.name:
                continue

            val = db.x * config["view-scale"]
            if val not in snap_x:
                snap_x.append(val)

            val = (db.x + db.logical_width) * config["view-scale"]
            if val not in snap_x:
                snap_x.append(val)

            val = db.y * config["view-scale"]
            if val not in snap_y:
                snap_y.append(val)

            val = (db.y + db.logical_height) * config["view-scale"]
            if val not in snap_y:
                snap_y.append(val)

        snap_h, snap_v = None, None
        for value in snap_x:
            if abs(x - value) < snap_threshold_scaled:
                snap_h = value
                break

        for value in snap_x:
            w = widget.logical_width * config["view-scale"]
            if abs(w + x - value) < snap_threshold_scaled:
                snap_h = value - w
                break

        for value in snap_y:
            if abs(y - value) < snap_threshold_scaled:
                snap_v = value
                break

        for value in snap_y:
            h = widget.logical_height * config["view-scale"]
            if abs(h + y - value) < snap_threshold_scaled:
                snap_v = value - h
                break

        # Just in case ;)
        if snap_h and snap_h < 0:
            snap_h = 0

        if snap_v and snap_v < 0:
            snap_v = 0

        if snap_h is None and snap_v is None:
            fixed.move(widget, x, y)
            widget.x = round(x / config["view-scale"])
            widget.y = round(y / config["view-scale"])
        else:

            if snap_h is not None and snap_v is not None:
                fixed.move(widget, snap_h, snap_v)
                widget.x = round(snap_h / config["view-scale"])
                widget.y = round(snap_v / config["view-scale"])

            elif snap_h is not None:
                fixed.move(widget, snap_h, y)
                widget.x = round(snap_h / config["view-scale"])
                widget.y = round(y / config["view-scale"])

            elif snap_v is not None:
                fixed.move(widget, x, snap_v)
                widget.x = round(x / config["view-scale"])
                widget.y = round(snap_v / config["view-scale"])

    update_form_from_widget(widget)


def update_form_from_widget(widget):
    form_name.set_text(widget.name)
    form_description.set_text(widget.description)
    form_dpms.set_active(widget.dpms)
    form_adaptive_sync.set_active(widget.adaptive_sync)
    form_custom_mode.set_active(widget.custom_mode)
    form_view_scale.set_value(config["view-scale"])  # not really from the widget, but from the global value
    form_x.set_value(widget.x)
    form_y.set_value(widget.y)
    form_width.set_value(widget.physical_width)
    form_height.set_value(widget.physical_height)
    form_scale.set_value(widget.scale)
    form_scale_filter.set_active_id(widget.scale_filter)
    form_refresh.set_value(widget.refresh)
    if form_mirror:
        form_mirror.remove_all()
        form_mirror.append("", voc["none"])
        for key in outputs:
            if key != widget.name:
                form_mirror.append(key, key)
        form_mirror.set_active_id(widget.mirror)
        form_mirror.show_all()

    global on_mode_changed_silent
    on_mode_changed_silent = True

    form_modes.remove_all()
    active = ""
    for mode in widget.modes:
        m = "{}x{}@{}Hz".format(mode["width"], mode["height"], mode["refresh"] / 1000, mode[
            "refresh"] / 1000, widget.refresh)
        form_modes.append(m, m)
        # This is just to set active_id

        if mode["width"] == widget.physical_width and mode["height"] == widget.physical_height and mode[
            "refresh"] / 1000 == widget.refresh:
            active = m
    if active:
        form_modes.set_active_id(active)

    form_transform.set_active_id(widget.transform)

    on_mode_changed_silent = False


class DisplayButton(Gtk.Button):
    def __init__(self, name, description, x, y, physical_width, physical_height, transform, scale, scale_filter,
                 refresh, modes, active, dpms, adaptive_sync_status, custom_mode_status, focused, monitor, mirror=""):
        super().__init__()
        # Output properties
        self.name = name
        self.description = description
        self.x = x
        self.y = y
        self.physical_width = physical_width
        self.physical_height = physical_height
        self.transform = transform
        self.scale = scale
        self.scale_filter = scale_filter
        self.refresh = refresh
        self.modes = []
        for m in modes:
            if m not in self.modes:
                self.modes.append(m)
        # self.modes = modes
        self.active = active
        self.dpms = dpms
        self.adaptive_sync = adaptive_sync_status == "enabled"  # converts "enabled | disabled" to bool
        self.custom_mode = custom_mode_status
        self.focused = focused
        self.mirror = mirror

        # Button properties
        self.selected = False
        self.set_can_focus(False)
        self.set_events(EvMask)
        self.connect("button_press_event", on_button_press_event)
        self.connect("motion_notify_event", on_motion_notify_event)
        self.set_always_show_image(True)
        self.set_label(self.name)

        self.rescale_transform()
        self.set_property("name", "output")

        self.indicator = Indicator(monitor, name, round(self.physical_width * config["view-scale"]),
                                   round(self.physical_height * config["view-scale"]), config["indicator-timeout"])

        self.show()

    @property
    def logical_width(self):
        if is_rotated(self.transform):
            return self.physical_height / self.scale
        else:
            return self.physical_width / self.scale

    @property
    def logical_height(self):
        if is_rotated(self.transform):
            return self.physical_width / self.scale
        else:
            return self.physical_height / self.scale

    def select(self):
        self.selected = True
        self.set_property("name", "selected-output")
        global selected_output_button
        selected_output_button = self

    def unselect(self):
        self.set_property("name", "output")

    def rescale_transform(self):
        self.set_size_request(round(self.logical_width * config["view-scale"]),
                              round(self.logical_height * config["view-scale"]))

    def on_active_check_button_toggled(self, w):
        self.active = w.get_active()
        if not self.active:
            self.set_property("name", "inactive-output")
        else:
            if self == selected_output_button:
                self.set_property("name", "selected-output")
            else:
                self.set_property("name", "output")


def on_view_scale_changed(*args):
    config["view-scale"] = round(form_view_scale.get_value(), 2)

    global snap_threshold_scaled
    snap_threshold_scaled = round(config["snap-threshold"] * config["view-scale"] * 10)

    for b in display_buttons:
        b.rescale_transform()
        fixed.move(b, b.x * config["view-scale"], b.y * config["view-scale"])


def on_transform_changed(*args):
    if selected_output_button:
        transform = form_transform.get_active_id()
        selected_output_button.transform = transform
        selected_output_button.rescale_transform()


def on_dpms_toggled(widget):
    if selected_output_button:
        selected_output_button.dpms = widget.get_active()


def on_adaptive_sync_toggled(widget):
    if selected_output_button:
        selected_output_button.adaptive_sync = widget.get_active()


def on_custom_mode_toggle(widget):
    if selected_output_button:
        outputs = set(config["custom-mode"])
        turned_on = widget.get_active()
        selected_output_button.custom_mode = turned_on
        if turned_on:
            outputs.add(selected_output_button.name)
        else:
            outputs.discard(selected_output_button.name)
        config["custom-mode"] = tuple(outputs)


def on_pos_x_changed(widget):
    if selected_output_button:
        selected_output_button.x = round(widget.get_value())
        fixed.move(selected_output_button, selected_output_button.x * config["view-scale"],
                   selected_output_button.y * config["view-scale"])


def on_pos_y_changed(widget):
    if selected_output_button:
        selected_output_button.y = round(widget.get_value())
        fixed.move(selected_output_button, selected_output_button.x * config["view-scale"],
                   selected_output_button.y * config["view-scale"])


def on_width_changed(widget):
    if selected_output_button:
        selected_output_button.physical_width = round(widget.get_value())
        selected_output_button.rescale_transform()


def on_height_changed(widget):
    if selected_output_button:
        selected_output_button.physical_height = round(widget.get_value())
        selected_output_button.rescale_transform()


def on_scale_changed(widget):
    if selected_output_button:
        selected_output_button.scale = widget.get_value()
        selected_output_button.rescale_transform()


def on_scale_filter_changed(widget):
    if selected_output_button:
        selected_output_button.scale_filter = widget.get_active_id()


def on_refresh_changed(widget):
    if selected_output_button:
        selected_output_button.refresh = widget.get_value()

        update_form_from_widget(selected_output_button)


def on_mode_changed(widget):
    if selected_output_button and not on_mode_changed_silent:
        mode = selected_output_button.modes[widget.get_active()]
        selected_output_button.physical_width = mode["width"]
        selected_output_button.physical_height = mode["height"]
        selected_output_button.refresh = mode["refresh"] / 1000
        selected_output_button.rescale_transform()

        update_form_from_widget(selected_output_button)


def on_mirror_selected(widget):
    if selected_output_button and widget.get_active_id() is not None:
        selected_output_button.mirror = widget.get_active_id()


def on_apply_button(widget):
    global outputs_activity
    apply_settings(display_buttons, outputs_activity, outputs_path, g_names=generic_names)
    # save config file
    save_json(config, os.path.join(config_dir, "config"))


def on_output_toggled(check_btn, name):
    global outputs_activity
    outputs_activity[name] = check_btn.get_active()


def on_toggle_button(btn):
    i3 = Connection()
    global outputs_activity
    for key in outputs_activity:
        toggle = "enable" if outputs_activity[key] else "disable"
        cmd = "output {} {}".format(key, toggle)
        i3.command(cmd)

    # If the output has just been turned back on, Gdk.Display.get_default() may need some time
    GLib.timeout_add(1000, create_display_buttons)


def create_display_buttons():
    global display_buttons
    for item in display_buttons:
        item.destroy()
    display_buttons = []

    global outputs
    outputs = list_outputs()
    for key in outputs:
        item = outputs[key]
        custom_mode = key in config["custom-mode"]
        b = DisplayButton(key, item["description"], item["x"], item["y"], round(item["physical-width"]),
                          round(item["physical-height"]),
                          item["transform"], item["scale"], item["scale_filter"], item["refresh"], item["modes"],
                          item["active"], item["dpms"], item["adaptive_sync_status"], custom_mode, item["focused"],
                          item["monitor"], mirror=item["mirror"])

        display_buttons.append(b)

        fixed.put(b, round(item["x"] * config["view-scale"]), round(item["y"] * config["view-scale"]))

    display_buttons[0].select()
    update_form_from_widget(display_buttons[0])


class Indicator(Gtk.Window):
    def __init__(self, monitor, name, width, height, timeout):
        super().__init__()
        self.timeout = timeout
        self.monitor = monitor
        self.set_property("name", "indicator")

        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        if monitor:
            GtkLayerShell.set_monitor(self, monitor)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(box)
        label = Gtk.Label()
        box.set_property("name", "indicator-label")
        label.set_text(name)
        box.pack_start(label, True, True, 10)

        self.set_size_request(width, height)
        if self.timeout > 0:
            self.show_up(self.timeout * 2)

    def show_up(self, timeout=None):
        if self.timeout > 0 and self.monitor:
            self.show_all()
            if timeout:
                GLib.timeout_add(timeout, self.hide)
            else:
                GLib.timeout_add(self.timeout, self.hide)


def handle_keyboard(window, event):
    if event.type == Gdk.EventType.KEY_RELEASE and event.keyval == Gdk.KEY_Escape:
        window.close()


def create_workspaces_window(btn):
    global sway_config_dir
    global workspaces
    workspaces = load_workspaces(os.path.join(sway_config_dir, "workspaces"))
    old_workspaces = workspaces.copy()
    global dialog_win
    if dialog_win:
        dialog_win.destroy()
    dialog_win = Gtk.Window()
    dialog_win.set_resizable(False)
    dialog_win.set_modal(True)
    dialog_win.connect("key-release-event", handle_keyboard)
    grid = Gtk.Grid()
    for prop in ["margin_start", "margin_end", "margin_top", "margin_bottom"]:
        grid.set_property(prop, 10)
    grid.set_column_spacing(12)
    grid.set_row_spacing(12)
    dialog_win.add(grid)
    global num_ws
    global outputs
    last_row = 0
    for i in range(num_ws):
        lbl = Gtk.Label()
        lbl.set_text("workspace {} output ".format(i + 1))
        grid.attach(lbl, 0, i, 1, 1)
        combo = Gtk.ComboBoxText()
        for key in outputs:
            combo.append(key, key)
            if i + 1 in workspaces:
                combo.set_active_id(workspaces[i + 1])
            combo.connect("changed", on_ws_combo_changed, i + 1)
        grid.attach(combo, 1, i, 1, 1)
        last_row = i

    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    grid.attach(box, 0, last_row + 1, 2, 1)

    btn_apply = Gtk.Button()
    btn_apply.set_label(voc["apply"])
    if sway_config_dir:
        btn_apply.connect("clicked", on_workspaces_apply_btn, dialog_win, old_workspaces)
    else:
        btn_apply.set_sensitive(False)
        btn_apply.set_tooltip_text("Config dir not found")
    box.pack_end(btn_apply, False, False, 0)

    btn_close = Gtk.Button()
    btn_close.set_label(voc["close"])
    btn_close.connect("clicked", close_dialog, dialog_win)
    box.pack_end(btn_close, False, False, 6)

    dialog_win.show_all()


def create_workspaces_window_hypr(btn):
    global workspaces, default_workspaces_hypr
    workspaces, default_workspaces_hypr = load_workspaces_hypr(
        os.path.join(os.getenv("HOME"), ".config", "hypr", "workspaces.conf"))
    eprint("WS->Mon:", workspaces)
    eprint("Mon->def_WS:", default_workspaces_hypr)
    global dialog_win
    if dialog_win:
        dialog_win.destroy()
    dialog_win = Gtk.Window()
    dialog_win.set_resizable(False)
    dialog_win.set_modal(True)
    dialog_win.connect("key-release-event", handle_keyboard)
    grid = Gtk.Grid()
    for prop in ["margin_start", "margin_end", "margin_top", "margin_bottom"]:
        grid.set_property(prop, 10)
    grid.set_column_spacing(12)
    grid.set_row_spacing(6)
    dialog_win.add(grid)
    global outputs
    last_row = 0
    for i in range(10):
        lbl = Gtk.Label()
        lbl.set_text("wsbind={},".format(i + 1))
        lbl.set_property("halign", Gtk.Align.END)
        grid.attach(lbl, 0, i, 1, 1)
        combo = Gtk.ComboBoxText()
        for key in outputs:
            combo.append(key, key)
            if i + 1 in workspaces:
                combo.set_active_id(workspaces[i + 1])
            combo.connect("changed", on_ws_combo_changed, i + 1)
        grid.attach(combo, 1, i, 1, 1)
        last_row = i

    for key in outputs:
        lbl = Gtk.Label.new("workspace={},".format(key))
        lbl.set_property("halign", Gtk.Align.END)
        grid.attach(lbl, 0, last_row+1, 1, 1)

        combo = Gtk.ComboBoxText()
        for n in range(1,11):
            combo.append(str(n), str(n))
        if key in default_workspaces_hypr:
            combo.set_active_id(str(default_workspaces_hypr[key]))
        combo.connect("changed", on_default_ws2mon_changed, key)
        grid.attach(combo, 1, last_row + 1, 1, 1)

        last_row += 1


    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    grid.attach(box, 0, last_row + 1, 2, 1)

    btn_apply = Gtk.Button()
    btn_apply.set_label(voc["apply"])
    if hypr_config_dir:
        btn_apply.connect("clicked", on_workspaces_apply_btn_hypr, dialog_win)
    else:
        btn_apply.set_sensitive(False)
        btn_apply.set_tooltip_text("Config dir not found")
    box.pack_end(btn_apply, False, False, 0)

    btn_close = Gtk.Button()
    btn_close.set_label(voc["close"])
    btn_close.connect("clicked", close_dialog, dialog_win)
    box.pack_end(btn_close, False, False, 6)

    dialog_win.show_all()


def on_ws_combo_changed(combo, ws_num):
    global workspaces
    workspaces[ws_num] = combo.get_active_id()


def on_default_ws2mon_changed(combo, monitor):
    global default_workspaces_hypr
    default_workspaces_hypr[monitor] = combo.get_active_id()


def close_dialog(w, win):
    win.close()


def on_workspaces_apply_btn(w, win, old_workspaces):
    global workspaces
    if workspaces != old_workspaces:
        save_workspaces(workspaces, os.path.join(sway_config_dir, "workspaces"))
        notify("Workspaces assignment", "Restart sway for changes to take effect")

    close_dialog(w, win)


def on_workspaces_apply_btn_hypr(w, win):
    global workspaces, default_workspaces_hypr
    # save_workspaces(workspaces, os.path.join(sway_config_dir, "workspaces"))
    text_file = open(os.path.join(os.getenv("HOME"), ".config/hypr/workspaces.conf"), "w")
    for key in workspaces:
        line = "wsbind={},{}".format(key, workspaces[key])
        text_file.write(line + "\n")

    for key in default_workspaces_hypr:
        line = "workspace={},{}".format(key, default_workspaces_hypr[key])
        text_file.write(line + "\n")

    text_file.close()

    close_dialog(w, win)


def main():
    GLib.set_prgname('nwg-displays')

    parser = argparse.ArgumentParser()
    parser.add_argument("-g",
                        "--generic_names",
                        action="store_true",
                        help="use Generic output names")

    if sway:
        parser.add_argument("-o",
                            "--outputs_path",
                            type=str,
                            default="{}/outputs".format(sway_config_dir),
                            help="path to save Outputs config to, default: {}".format(
                                "{}/outputs".format(sway_config_dir)))
    elif hypr:
        parser.add_argument("-m",
                            "--monitors_path",
                            type=str,
                            default="{}/monitors.conf".format(hypr_config_dir),
                            help="path to save the monitors.conf file to, default: {}".format(
                                "{}/.config/hypr/monitors.conf".format(os.getenv("HOME"))))

    parser.add_argument("-n",
                        "--num_ws",
                        type=int,
                        default=8,
                        help="number of Workspaces in use, default: 8")

    parser.add_argument("-v",
                        "--version",
                        action="version",
                        version="%(prog)s version {}".format(__version__),
                        help="display version information")
    args = parser.parse_args()

    load_vocabulary()

    global outputs_path
    if sway:
        if os.path.isdir(sway_config_dir):
            outputs_path = args.outputs_path
        else:
            eprint("sway config directory not found!")
            outputs_path = ""
    elif hypr:
        if os.path.isdir(hypr_config_dir):
            outputs_path = args.monitors_path
        else:
            eprint("Hyprland config directory not found!")
            outputs_path = ""

    global generic_names
    generic_names = args.generic_names

    global num_ws
    num_ws = args.num_ws
    if sway:
        print("Number of workspaces: {}".format(num_ws))

    config_file = os.path.join(config_dir, "config")
    global config
    if not os.path.isfile(config_file):
        # migrate old config file, if not yet migrated
        if os.path.isfile(os.path.join(old_config_dir, "config")):
            print("Migrating config to the proper path...")
            os.rename(old_config_dir, config_dir)
        else:
            if not os.path.isdir(config_dir):
                os.makedirs(config_dir, exist_ok=True)
            print("'{}' file not found, creating default".format(config_file))
            save_json(config, config_file)
    else:
        config = load_json(config_file)

    if config_keys_missing(config, config_file):
        config = load_json(config_file)

    eprint("Settings: {}".format(config))

    global snap_threshold_scaled
    snap_threshold_scaled = config["snap-threshold"]

    builder = Gtk.Builder()
    builder.add_from_file(os.path.join(dir_name, "resources/main.glade"))

    window = builder.get_object("window")
    screen = Gdk.Screen.get_default()
    provider = Gtk.CssProvider()
    style_context = Gtk.StyleContext()
    style_context.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    try:
        file = os.path.join(dir_name, "resources/style.css")
        provider.load_from_path(file)
    except:
        sys.stderr.write("ERROR: {} file not found, using GTK styling\n".format(os.path.join(dir_name,
                                                                                             "resources/style.css")))

    window.connect("key-release-event", handle_keyboard)
    window.connect('destroy', Gtk.main_quit)

    builder.get_object("lbl-modes").set_label("{}:".format(voc["modes"]))
    builder.get_object("lbl-position-x").set_label("{}:".format(voc["position-x"]))
    builder.get_object("lbl-refresh").set_label("{}:".format(voc["refresh"]))
    builder.get_object("lbl-scale").set_label("{}:".format(voc["scale"]))
    builder.get_object("lbl-scale-filter").set_label("{}:".format(voc["scale-filter"]))
    builder.get_object("lbl-size").set_label("{}:".format(voc["size"]))
    builder.get_object("lbl-transform").set_label("{}:".format(voc["transform"]))
    builder.get_object("lbl-zoom").set_label("{}:".format(voc["zoom"]))

    global form_name
    form_name = builder.get_object("name")

    global form_description
    form_description = builder.get_object("description")

    global form_dpms
    form_dpms = builder.get_object("dpms")
    if sway:
        form_dpms.set_tooltip_text(voc["dpms-tooltip"])
        form_dpms.connect("toggled", on_dpms_toggled)
    else:
        form_dpms.set_sensitive(False)

    global form_adaptive_sync
    form_adaptive_sync = builder.get_object("adaptive-sync")
    if sway:
        form_adaptive_sync.set_label(voc["adaptive-sync"])
        form_adaptive_sync.set_tooltip_text(voc["adaptive-sync-tooltip"])
        form_adaptive_sync.connect("toggled", on_adaptive_sync_toggled)
    else:
        form_adaptive_sync.set_sensitive(False)

    global form_custom_mode
    form_custom_mode = builder.get_object("custom-mode")
    if sway:
        form_custom_mode.set_label(voc["custom-mode"])
        form_custom_mode.set_tooltip_text(voc["custom-mode-tooltip"])
        form_custom_mode.connect("toggled", on_custom_mode_toggle)
    else:
        form_custom_mode.set_sensitive(False)

    global form_view_scale
    form_view_scale = builder.get_object("view-scale")
    form_view_scale.set_tooltip_text(voc["view-scale-tooltip"])
    adj = Gtk.Adjustment(lower=0.1, upper=0.6, step_increment=0.05, page_increment=0.1, page_size=0.1)
    form_view_scale.configure(adj, 1, 2)
    form_view_scale.connect("changed", on_view_scale_changed)

    global form_x
    form_x = builder.get_object("x")
    adj = Gtk.Adjustment(lower=0, upper=60000, step_increment=1, page_increment=10, page_size=1)
    form_x.configure(adj, 1, 0)
    form_x.connect("value-changed", on_pos_x_changed)

    global form_y
    form_y = builder.get_object("y")
    adj = Gtk.Adjustment(lower=0, upper=40000, step_increment=1, page_increment=10, page_size=1)
    form_y.configure(adj, 1, 0)
    form_y.connect("value-changed", on_pos_y_changed)

    global form_width
    form_width = builder.get_object("width")
    adj = Gtk.Adjustment(lower=0, upper=7680, step_increment=1, page_increment=10, page_size=1)
    form_width.configure(adj, 1, 0)
    form_width.connect("value-changed", on_width_changed)

    global form_height
    form_height = builder.get_object("height")
    adj = Gtk.Adjustment(lower=0, upper=4320, step_increment=1, page_increment=10, page_size=1)
    form_height.configure(adj, 1, 0)
    form_height.connect("value-changed", on_height_changed)

    global form_scale
    form_scale = builder.get_object("scale")
    adj = Gtk.Adjustment(lower=0.1, upper=10, step_increment=0.1, page_increment=10, page_size=1)
    form_scale.configure(adj, 0.1, 2)
    form_scale.connect("value-changed", on_scale_changed)

    global form_scale_filter
    form_scale_filter = builder.get_object("scale-filter")
    if sway:
        form_scale_filter.set_tooltip_text(voc["scale-filter-tooltip"])
        form_scale_filter.connect("changed", on_scale_filter_changed)
    else:
        form_scale_filter.set_sensitive(False)

    global form_refresh
    form_refresh = builder.get_object("refresh")
    adj = Gtk.Adjustment(lower=1, upper=1200, step_increment=1, page_increment=10, page_size=1)
    form_refresh.configure(adj, 1, 3)
    form_refresh.connect("changed", on_refresh_changed)

    global form_modes
    form_modes = builder.get_object("modes")
    form_modes.set_tooltip_text(voc["modes-tooltip"])
    form_modes.connect("changed", on_mode_changed)

    global form_transform
    form_transform = builder.get_object("transform")
    form_transform.set_tooltip_text(voc["transform-tooltip"])
    form_transform.connect("changed", on_transform_changed)

    global form_wrapper_box
    form_wrapper_box = builder.get_object("wrapper-box")

    global form_workspaces
    form_workspaces = builder.get_object("workspaces")
    form_workspaces.set_label(voc["workspaces"])
    form_workspaces.set_tooltip_text(voc["workspaces-tooltip"])
    if sway:
        form_workspaces.connect("clicked", create_workspaces_window)
    elif hypr:
        form_workspaces.connect("clicked", create_workspaces_window_hypr)

    global form_close
    form_close = builder.get_object("close")
    form_close.set_label(voc["close"])
    form_close.connect("clicked", Gtk.main_quit)
    form_close.grab_focus()

    global form_apply
    form_apply = builder.get_object("apply")
    form_apply.set_label(voc["apply"])
    if (sway and sway_config_dir) or (hypr and hypr_config_dir):
        form_apply.connect("clicked", on_apply_button)
    else:
        form_apply.set_sensitive(False)
        form_apply.set_tooltip_text("Config dir not found")

    global form_version
    form_version = builder.get_object("version")
    form_version.set_text("v{}".format(__version__))

    wrapper = builder.get_object("wrapper")
    wrapper.set_property("name", "wrapper")

    global fixed
    fixed = builder.get_object("fixed")

    create_display_buttons()

    global outputs_activity
    outputs_activity = list_outputs_activity()
    lbl = Gtk.Label()
    lbl.set_text("{}:".format(voc["active"]))
    form_wrapper_box.pack_start(lbl, False, False, 3)
    for key in outputs_activity:
        cb = Gtk.CheckButton()
        cb.set_label(key)
        cb.set_active(outputs_activity[key])
        cb.connect("toggled", on_output_toggled, key)
        form_wrapper_box.pack_start(cb, False, False, 3)

    btn = Gtk.Button.new_with_label(voc["toggle"])
    if sway:
        btn.set_tooltip_text(voc["toggle-tooltip"])
        btn.connect("clicked", on_toggle_button)
        form_wrapper_box.pack_start(btn, False, False, 3)
    else:
        btn.destroy()

    if hypr:
        grid = builder.get_object("grid")
        lbl = Gtk.Label.new("Mirror:")
        lbl.set_property("halign", Gtk.Align.END)
        grid.attach(lbl, 6, 4, 1, 1)

        global form_mirror
        form_mirror = Gtk.ComboBoxText()
        form_mirror.connect("changed", on_mirror_selected)
        grid.attach(form_mirror, 7, 4, 1, 1)


    if display_buttons:
        update_form_from_widget(display_buttons[0])
        display_buttons[0].select()

    window.show_all()

    # Gtk.Fixed does not respect expand properties. That's why we need
    # to scale the window automagically if opened as a floating_con
    Gdk.threads_add_timeout(GLib.PRIORITY_LOW, 100, scale_if_floating)

    Gtk.main()


if __name__ == '__main__':
    sys.exit(main())

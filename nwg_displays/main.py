#!/usr/bin/env python

"""
https://gist.github.com/KurtJacobson/57679e5036dc78e6a7a3ba5e0155dad1
"""

import os
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

dir_name = os.path.dirname(__file__)

from nwg_displays.tools import *

# higher values make movement more performant
# lower values make movement smoother
SENSITIVITY = 1
view_scale = 0.1

EvMask = Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON1_MOTION_MASK

outputs = {}
fixed = Gtk.Fixed()

offset_x = 0
offset_y = 0
px = 0
py = 0
max_x = 0
max_y = 0

# Glade form fields
form_description = None
form_active = None
form_x = None
form_y = None
form_width = None
form_height = None
form_scale = None
form_refresh = None

display_buttons = []


def on_button_press_event(widget, event):
    if event.button == 1:
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
        snap_x, snap_y = [], []
        for db in display_buttons:
            if db.name == widget.name:
                continue

            val = int(db.x * view_scale)
            if val not in snap_x:
                snap_x.append(val)
                print("x >>", db.name, val)

            val = int((db.x + db.width) * view_scale)
            if val not in snap_x:
                snap_x.append(val)
                print("x >>", db.name, val)

            val = int(db.y * view_scale)
            if val not in snap_y:
                snap_y.append(val)
                print("y >>", db.name, val)

            val = int((db.y + db.height) * view_scale)
            if val not in snap_y:
                snap_y.append(val)
                print("y >>", db.name, val)

            snap_x.sort()
            snap_y.sort()
            print("snap_x", snap_x)
            print("snap_y", snap_y)

        snap_h, snap_v = None, None
        for value in snap_x:
            if abs(x - value) < 20:
                snap_h = value
                print("snap_h", snap_h)
                #break

        for value in snap_y:
            if abs(y - value) < 20:
                snap_v = value
                print("snap_v", snap_v)
                #break

        if snap_h is None and snap_v is None:
            fixed.move(widget, x, y)
            widget.x = int(x / view_scale)
            widget.y = int(y / view_scale)
        else:

            if snap_h is not None and snap_v is not None:
                fixed.move(widget, snap_h, snap_v)
                widget.x = int(snap_h / view_scale)
                widget.y = int(snap_v / view_scale)

            elif snap_h is not None:
                fixed.move(widget, snap_h, y)
                widget.x = int(snap_h / view_scale)
                widget.y = int(y / view_scale)

            elif snap_v is not None:
                fixed.move(widget, x, snap_v)
                widget.x = int(x / view_scale)
                widget.y = int(snap_v / view_scale)

    update_form_from_widget(widget)


def update_form_from_widget(widget, *args):
    form_description.set_text("{} ({})".format(widget.description, widget.name))
    form_active.set_active(widget.active)
    form_x.set_value(widget.x)
    form_y.set_value(widget.y)
    form_width.set_value(widget.width)
    form_height.set_value(widget.height)
    form_scale.set_value(widget.scale)
    form_refresh.set_value(widget.refresh)


class DisplayButton(Gtk.Button):
    def __init__(self, name, description, x, y, width, height, transform, scale, refresh, modes, active):
        super().__init__()
        self.name = name
        self.description = description
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.transform = transform
        self.scale = scale
        self.refresh = refresh
        self.modes = modes
        self.active = active

        self.set_events(EvMask)
        self.connect("button_press_event", on_button_press_event)
        self.connect("motion_notify_event", on_motion_notify_event)
        self.connect("button-press-event", update_form_from_widget)
        self.connect("button-release-event", update_form_from_widget)
        self.set_always_show_image(True)
        self.set_label(self.name)
        self.set_size_request(int(self.width * view_scale), int(self.height * view_scale))

        self.show()


def main():
    builder = Gtk.Builder()
    builder.add_from_file("main.glade")

    window = builder.get_object("window")
    screen = Gdk.Screen.get_default()
    provider = Gtk.CssProvider()
    style_context = Gtk.StyleContext()
    style_context.add_provider_for_screen(screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    try:
        file = os.path.join(dir_name, "style.css")
        provider.load_from_path(file)
        print("Using style: {}".format(file))
    except:
        sys.stderr.write("ERROR: {} file not found, using GTK styling\n".format(os.path.join(dir_name, "style.css")))

    window.connect('destroy', Gtk.main_quit)

    global form_description
    form_description = builder.get_object("description")

    global form_active
    form_active = builder.get_object("active")

    global form_x
    form_x = builder.get_object("x")
    adj = Gtk.Adjustment(lower=0, upper=60000, step_increment=1, page_increment=10, page_size=1)
    form_x.configure(adj, 1, 0)

    global form_y
    form_y = builder.get_object("y")
    adj = Gtk.Adjustment(lower=0, upper=40000, step_increment=1, page_increment=10, page_size=1)
    form_y.configure(adj, 1, 0)

    global form_width
    form_width = builder.get_object("width")
    adj = Gtk.Adjustment(lower=0, upper=7680, step_increment=1, page_increment=10, page_size=1)
    form_width.configure(adj, 1, 0)

    global form_height
    form_height = builder.get_object("height")
    adj = Gtk.Adjustment(lower=0, upper=4320, step_increment=1, page_increment=10, page_size=1)
    form_height.configure(adj, 1, 0)

    global form_scale
    form_scale = builder.get_object("scale")
    adj = Gtk.Adjustment(lower=0.1, upper=1000, step_increment=0.1, page_increment=10, page_size=1)
    form_scale.configure(adj, 0.1, 1)

    global form_refresh
    form_refresh = builder.get_object("refresh")
    adj = Gtk.Adjustment(lower=1, upper=1200, step_increment=1, page_increment=10, page_size=1)
    form_refresh.configure(adj, 1, 3)

    global fixed
    fixed = builder.get_object("fixed")

    global outputs
    outputs = list_outputs()
    global display_buttons
    for key in outputs:
        item = outputs[key]
        b = DisplayButton(key, item["description"], item["x"], item["y"], int(item["width"]), int(item["height"]),
                          item["transform"], item["scale"], item["refresh"], item["modes"],
                          item["active"])
        display_buttons.append(b)

        fixed.put(b, int(item["x"] * view_scale), int(item["y"] * view_scale))

    if display_buttons:
        update_form_from_widget(display_buttons[0])

    window.show_all()
    Gtk.main()


if __name__ == '__main__':
    sys.exit(main())

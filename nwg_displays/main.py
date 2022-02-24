#!/usr/bin/env python

"""
https://gist.github.com/KurtJacobson/57679e5036dc78e6a7a3ba5e0155dad1
"""

import gi

gi.require_version('Gtk', '3.0')

from gi.repository import Gtk, Gdk

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
snap_x = []
snap_y = []


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

        for db in display_buttons:
            if widget != db:
                if abs(widget.x - db.x) < 100:
                    fixed.move(widget, db.x * view_scale, y)
                    widget.x = db.x / view_scale
                    break
                else:
                    fixed.move(widget, x, y)

        widget.x = int(x / view_scale)
        widget.y = int(y / view_scale)
        widget.update_form(None, None)


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
        self.connect("button-press-event", self.update_form)
        self.connect("button-release-event", self.update_form)
        self.set_always_show_image(True)
        self.set_label(self.name)
        self.set_size_request(int(self.width * view_scale), int(self.height * view_scale))

        self.show()

    def update_form(self, w, e):
        form_description.set_text("{} ({})".format(self.description, self.name))
        form_active.set_active(self.active)
        form_x.set_value(self.x)
        form_y.set_value(self.y)
        form_width.set_value(self.width)
        form_height.set_value(self.height)
        form_scale.set_value(self.scale)
        form_refresh.set_value(self.refresh)


def main():
    builder = Gtk.Builder()
    builder.add_from_file("main.glade")

    window = builder.get_object("window")
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
        display_buttons[0].update_form(None, None)

    window.show_all()
    Gtk.main()


if __name__ == '__main__':
    sys.exit(main())

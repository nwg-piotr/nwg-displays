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

EvMask = Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON1_MOTION_MASK

outputs = {}
fixed = Gtk.Fixed()

offset_x = 0
offset_y = 0
px = 0
py = 0
max_x = 0
max_y = 0


def on_button_press_event(w, event):
    if event.button == 1:
        p = w.get_parent()
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
        max_x = round_down_to_multiple(p.get_allocation().width - w.get_allocation().width, SENSITIVITY)
        max_y = round_down_to_multiple(p.get_allocation().height - w.get_allocation().height, SENSITIVITY)


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
        fixed.move(widget, x, y)


class DisplayButton(Gtk.Button):
    def __init__(self, name, description, width, height, transform, scale, refresh, modes, active):
        super().__init__()
        self.name = name
        self.description = description
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
        self.set_always_show_image(True)
        self.set_label(self.name)
        self.set_size_request(self.width, self.height)
        self.show()


def main():
    builder = Gtk.Builder()
    builder.add_from_file("main.glade")

    window = builder.get_object("window")
    window.connect('destroy', Gtk.main_quit)

    global fixed
    fixed = builder.get_object("fixed")

    global outputs
    outputs = list_outputs()
    for key in outputs:
        item = outputs[key]
        b = DisplayButton(key, item["description"], int(item["width"] / 10), int(item["height"] / 10),
                          item["transform"], item["scale"], item["refresh"], item["modes"], item["active"])

        fixed.put(b, int(item["x"] / 10), int(item["y"] / 10))

    window.show_all()
    Gtk.main()


if __name__ == '__main__':
    sys.exit(main())

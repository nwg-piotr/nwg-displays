#!/usr/bin/env python

"""
Profile management for nwg-displays
"""

import os
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from nwg_displays.tools import save_json, load_json, notify


class ProfileManager:
    def __init__(self, config_dir, config, voc):
        self.profiles_dir = os.path.join(config_dir, "profiles")
        self.current_profile = None
        self.config = config
        self.voc = voc
        self.btn_save_profile = None
        self.display_buttons = None
        self.fixed = None
        self.update_callback = None
        self.profile_label = None

        # Ensure profiles directory exists
        if not os.path.isdir(self.profiles_dir):
            os.makedirs(self.profiles_dir, exist_ok=True)

    def set_save_button(self, button):
        """Store reference to the save button to enable/disable it"""
        self.btn_save_profile = button

    def set_display_buttons(self, buttons):
        """Store reference to display buttons"""
        self.display_buttons = buttons

    def set_fixed(self, fixed):
        """Store reference to the fixed container"""
        self.fixed = fixed

    def set_update_callback(self, callback):
        """Store reference to form update callback"""
        self.update_callback = callback

    def set_profile_label(self, label):
        """Store reference to the profile label"""
        self.profile_label = label

    def _update_profile_label(self):
        """Update profile label text with current profile name"""
        if self.profile_label:
            if self.current_profile:
                self.profile_label.set_text(
                    self.voc.get("current-profile", "Profile")
                    + ": "
                    + self.current_profile
                )
            else:
                self.profile_label.set_text(
                    self.voc.get("current-profile", "Profile")
                    + ": "
                    + self.voc.get("none", "None")
                )

    def create_profile(self, widget):
        """Create a new profile with the current display configuration"""
        if not self.display_buttons:
            notify(
                self.voc.get("error", "Error"),
                self.voc.get("no-displays", "No displays available"),
            )
            return

        # Create a dialog to get the profile name
        dialog = Gtk.Dialog(
            title=self.voc.get("new-profile", "New Profile"),
            parent=widget.get_toplevel(),
            flags=Gtk.DialogFlags.MODAL,
        )

        dialog.add_button(self.voc.get("cancel", "Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(self.voc.get("create", "Create"), Gtk.ResponseType.OK)

        content_area = dialog.get_content_area()
        content_area.set_property("margin", 10)

        grid = Gtk.Grid()
        grid.set_column_spacing(10)
        grid.set_row_spacing(10)
        content_area.add(grid)

        name_label = Gtk.Label(label=self.voc.get("profile-name", "Profile Name:"))
        grid.attach(name_label, 0, 0, 1, 1)

        name_entry = Gtk.Entry()
        grid.attach(name_entry, 1, 0, 1, 1)

        dialog.show_all()
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            profile_name = name_entry.get_text().strip()
            if profile_name:
                # Save profile
                profile_path = os.path.join(self.profiles_dir, f"{profile_name}.json")
                self.save_profile_to_file(profile_path)
                self.current_profile = profile_name
                if self.btn_save_profile:
                    self.btn_save_profile.set_sensitive(True)
                # Update the profile label
                self._update_profile_label()
                notify(
                    self.voc.get("profile-created", "Profile Created"),
                    self.voc.get(
                        "profile-created-message",
                        f"Profile '{profile_name}' has been created",
                    ),
                )

        dialog.destroy()

    def _add_button_with_padding(self, dialog, text, response_id):
        """Helper method to add buttons with proper padding to dialogs"""
        button = dialog.add_button(text, response_id)
        button.set_property("margin", 5)  # Add margin around the button
        button.set_property("margin-start", 10)
        button.set_property("margin-end", 10)
        return button

    def select_profile(self, widget):
        """Select an existing profile to load"""
        # Get list of profile files
        profile_files = [
            f for f in os.listdir(self.profiles_dir) if f.endswith(".json")
        ]

        if not profile_files:
            notify(
                self.voc.get("no-profiles", "No Profiles"),
                self.voc.get(
                    "no-profiles-message", "No profiles found. Create one first."
                ),
            )
            return

        # Create dialog to select profile
        dialog = Gtk.Dialog(
            title=self.voc.get("select-profile", "Select Profile"),
            parent=widget.get_toplevel(),
            flags=Gtk.DialogFlags.MODAL,
        )

        # Set the Load button as the default response when Enter is pressed
        dialog.set_default_response(Gtk.ResponseType.OK)

        # Set spacing between action buttons
        action_area = dialog.get_action_area()
        action_area.set_property("spacing", 10)
        action_area.set_property("margin", 10)

        # Use the helper method to add padded buttons
        cancel_btn = self._add_button_with_padding(
            dialog, self.voc.get("cancel", "Cancel"), Gtk.ResponseType.CANCEL
        )
        load_btn = self._add_button_with_padding(
            dialog, self.voc.get("load", "Load"), Gtk.ResponseType.OK
        )
        delete_btn = self._add_button_with_padding(
            dialog, self.voc.get("delete", "Delete"), Gtk.ResponseType.REJECT
        )

        # Set the Load button as the default widget to visually indicate it's the default action
        load_btn.set_can_default(True)
        load_btn.grab_default()

        content_area = dialog.get_content_area()
        content_area.set_property("margin", 15)  # Increase content margin too

        profile_combo = Gtk.ComboBoxText()
        for file in profile_files:
            name = file.replace(".json", "")
            profile_combo.append(name, name)

        if self.current_profile and self.current_profile in [
            f.replace(".json", "") for f in profile_files
        ]:
            profile_combo.set_active_id(self.current_profile)
        else:
            profile_combo.set_active(0)

        content_area.add(profile_combo)
        dialog.show_all()

        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            selected_profile = profile_combo.get_active_id()
            if selected_profile:
                profile_path = os.path.join(
                    self.profiles_dir, f"{selected_profile}.json"
                )
                self.load_profile_from_file(profile_path)
                self.current_profile = selected_profile
                if self.btn_save_profile:
                    self.btn_save_profile.set_sensitive(True)
                # Update the profile label
                self._update_profile_label()
        elif response == Gtk.ResponseType.REJECT:
            selected_profile = profile_combo.get_active_id()
            if selected_profile:
                # Confirm deletion
                confirm_dialog = Gtk.MessageDialog(
                    parent=dialog,
                    flags=Gtk.DialogFlags.MODAL,
                    type=Gtk.MessageType.QUESTION,
                    buttons=Gtk.ButtonsType.YES_NO,
                    message_format=self.voc.get(
                        "confirm-delete", f"Delete profile '{selected_profile}'?"
                    ),
                )

                confirm_response = confirm_dialog.run()
                if confirm_response == Gtk.ResponseType.YES:
                    profile_path = os.path.join(
                        self.profiles_dir, f"{selected_profile}.json"
                    )
                    try:
                        os.remove(profile_path)
                        notify(
                            self.voc.get("profile-deleted", "Profile Deleted"),
                            self.voc.get(
                                "profile-deleted-message",
                                f"Profile '{selected_profile}' has been deleted",
                            ),
                        )

                        # If current profile was deleted, reset it
                        if self.current_profile == selected_profile:
                            self.current_profile = None
                            if self.btn_save_profile:
                                self.btn_save_profile.set_sensitive(False)
                            # Update the profile label
                            self._update_profile_label()
                    except OSError as e:
                        notify(
                            self.voc.get("error", "Error"),
                            self.voc.get(
                                "delete-error-message", f"Could not delete profile: {e}"
                            ),
                        )

                confirm_dialog.destroy()

        dialog.destroy()

    def save_profile(self, widget):
        """Save current settings to the selected profile"""
        if not self.current_profile:
            return

        profile_path = os.path.join(self.profiles_dir, f"{self.current_profile}.json")
        self.save_profile_to_file(profile_path)
        notify(
            self.voc.get("profile-saved", "Profile Saved"),
            self.voc.get(
                "profile-saved-message",
                f"Profile '{self.current_profile}' has been updated",
            ),
        )

    def save_profile_to_file(self, profile_path):
        """Save the current display configuration to a profile file"""
        if not self.display_buttons:
            return

        profile_data = {"displays": [], "config": self.config}

        for db in self.display_buttons:
            display = {
                "name": db.name,
                "description": db.description,
                "x": db.x,
                "y": db.y,
                "physical_width": db.physical_width,
                "physical_height": db.physical_height,
                "transform": db.transform,
                "scale": db.scale,
                "scale_filter": db.scale_filter,
                "refresh": db.refresh,
                "dpms": db.dpms,
                "adaptive_sync": db.adaptive_sync,
                "custom_mode": db.custom_mode,
                "mirror": db.mirror,
                "ten_bit": db.ten_bit,
                "active": db.active,
            }
            profile_data["displays"].append(display)

        save_json(profile_data, profile_path)

    def load_profile_from_file(self, profile_path):
        """Load display configuration from a profile file"""
        if not self.display_buttons or not self.fixed or not self.update_callback:
            notify(
                self.voc.get("error", "Error"),
                self.voc.get(
                    "load-error-missing-data", "Missing data for loading profile"
                ),
            )
            return

        profile_data = load_json(profile_path)
        if not profile_data:
            notify(
                self.voc.get("error", "Error"),
                self.voc.get("load-error-message", "Could not load profile"),
            )
            return

        # Update config
        if "config" in profile_data:
            for key, value in profile_data["config"].items():
                self.config[key] = value

        if "displays" in profile_data:
            # First apply transforms to ensure correct dimensions before positioning
            for db in self.display_buttons:
                for display in profile_data["displays"]:
                    if db.name == display["name"]:
                        # Update transform first so the sizing is correct
                        db.transform = display["transform"]
                        db.physical_width = display["physical_width"]
                        db.physical_height = display["physical_height"]
                        db.scale = display["scale"]
                        # Update the button's size according to the new transform
                        db.rescale_transform()
                        break

            # Now update positions and other settings
            for db in self.display_buttons:
                for display in profile_data["displays"]:
                    if db.name == display["name"]:
                        # Update all other display settings
                        db.x = display["x"]
                        db.y = display["y"]
                        db.scale_filter = display["scale_filter"]
                        db.refresh = display["refresh"]
                        db.dpms = display["dpms"]
                        db.adaptive_sync = display["adaptive_sync"]
                        db.custom_mode = display["custom_mode"]
                        db.mirror = display["mirror"]
                        db.ten_bit = display["ten_bit"]
                        db.active = display["active"]

                        # Update button position with the correct dimensions
                        self.fixed.move(
                            db,
                            db.x * self.config["view-scale"],
                            db.y * self.config["view-scale"],
                        )
                        break

        # Update the form if a display is selected
        selected_button = next((db for db in self.display_buttons if db.selected), None)
        if selected_button:
            self.update_callback(selected_button)

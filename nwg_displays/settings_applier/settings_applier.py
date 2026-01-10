import os
import datetime
import json
import time

# Assuming these tools exist based on original code structure
from nwg_displays.tools import (
    hyprctl,
    save_list_to_text_file,
    load_text_file,
    inactive_output_description,
)
from nwg_displays.wallpaper_manager import WallpaperManager

# If create_confirm_win is in main or ui, you might need to pass it as a callback
# or import it if circular imports aren't an issue.
# from nwg_displays.main import create_confirm_win


class SettingsApplier:
    @staticmethod
    def apply_from_json(profile_data, outputs_path, config_dir, profile_name):
        """Applies configuration based on a Profile JSON file."""
        SettingsApplier._save_current_state_to_previous_profile(config_dir)

        displays = profile_data["displays"]
        config = profile_data["config"]
        use_desc = config.get("use-desc", False)

        if os.getenv("HYPRLAND_INSTANCE_SIGNATURE"):
            SettingsApplier._apply_hyprland_json(
                displays, use_desc, outputs_path, profile_data
            )

        elif os.getenv("SWAYSOCK"):
            SettingsApplier._apply_sway_json(displays, use_desc)

        SettingsApplier._set_active_profile(config_dir, profile_name)

    @staticmethod
    def _apply_hyprland_json(displays, use_desc, outputs_path, profile_data):
        transforms = {
            "normal": 0,
            "90": 1,
            "180": 2,
            "270": 3,
            "flipped": 4,
            "flipped-90": 5,
            "flipped-180": 6,
            "flipped-270": 7,
        }

        print(f"[Profile] Applying {len(displays)} displays for Hyprland...")
        lines = [SettingsApplier._get_header("Profile Loader")]

        for d in displays:
            if not use_desc:
                name = d["name"]
            else:
                desc_safe = d["description"].replace("#", "##")
                name = f"desc:{desc_safe}"

            if not d["active"]:
                lines.append(f"monitor={name},disable")
                hyprctl(f"dispatch dpms off {d['name']}")
                continue

            line = "monitor={},{}x{}@{},{}x{},{}".format(
                name,
                d["physical_width"],
                d["physical_height"],
                d["refresh"],
                d["x"],
                d["y"],
                d["scale"],
            )

            if d.get("mirror"):
                line += ",mirror,{}".format(d["mirror"])

            if d.get("ten_bit"):
                line += ",bitdepth,10"

            lines.append(line)

            if d["transform"] != "normal":
                t_code = transforms.get(d["transform"], 0)
                lines.append(f"monitor={name},transform,{t_code}")

            cmd = "on" if d["dpms"] else "off"
            hyprctl(f"dispatch dpms {cmd} {d['name']}")

        save_list_to_text_file(lines, outputs_path)
        hyprctl("reload")

        if "wallpapers" in profile_data:
            print("[Profile] Applying wallpapers...")
            time.sleep(1)
            WallpaperManager.apply_wallpapers(profile_data["wallpapers"])

    @staticmethod
    def _apply_sway_json(displays, use_desc):
        from i3ipc import Connection

        cmds = []
        for d in displays:
            name = d["description"] if use_desc else d["name"]
            if not d["active"]:
                cmds.append(f'output "{name}" disable')
                continue

            cmd = 'output "{}"'.format(name)
            custom = "--custom" if d["custom_mode"] else ""
            cmd += " mode {} {}x{}@{}Hz".format(
                custom, d["physical_width"], d["physical_height"], d["refresh"]
            )
            cmd += " pos {} {}".format(d["x"], d["y"])
            cmd += " transform {}".format(d["transform"])
            cmd += " scale {}".format(d["scale"])

            if d.get("scale_filter"):
                cmd += " scale_filter {}".format(d["scale_filter"])

            a_s = "on" if d["adaptive_sync"] else "off"
            cmd += " adaptive_sync {}".format(a_s)

            dpms = "on" if d["dpms"] else "off"
            cmd += " dpms {}".format(dpms)
            cmds.append(cmd)

        i3 = Connection()
        for cmd in cmds:
            i3.command(cmd)

    @staticmethod
    def apply_from_gui(
        display_buttons,
        outputs_activity,
        outputs_path,
        use_desc=False,
        create_confirm_win_callback=None,
        config_dir=None,
        profile_name=None,
    ):
        """
        Applies configuration based on GUI buttons state.
        Refactored from original 'apply_settings'.
        """
        if config_dir:
            SettingsApplier._save_current_state_to_previous_profile(config_dir)

        if os.getenv("SWAYSOCK"):
            SettingsApplier._apply_sway_gui(
                display_buttons,
                outputs_activity,
                outputs_path,
                use_desc,
                create_confirm_win_callback,
                config_dir,
                profile_name,
            )

        elif os.getenv("HYPRLAND_INSTANCE_SIGNATURE"):
            SettingsApplier._apply_hyprland_gui(
                display_buttons,
                outputs_activity,
                outputs_path,
                use_desc,
                create_confirm_win_callback,
                config_dir,
                profile_name,
            )

        if config_dir and profile_name:
            SettingsApplier._set_active_profile(config_dir, profile_name)

    @staticmethod
    def _apply_sway_gui(
        display_buttons,
        outputs_activity,
        outputs_path,
        use_desc,
        create_confirm_win_callback,
        config_dir=None,
        profile_name=None,
    ):
        from i3ipc import Connection

        lines = [SettingsApplier._get_header()]
        cmds = []
        db_names = []

        for db in display_buttons:
            name = db.name if not use_desc else db.description
            db_names.append(name)

            lines.append('output "%s" {' % name)
            cmd = 'output "{}"'.format(name)

            custom_mode_str = "--custom" if db.custom_mode else ""
            lines.append(
                "    mode {} {}x{}@{}Hz".format(
                    custom_mode_str,
                    db.physical_width,
                    db.physical_height,
                    db.refresh,
                )
            )
            cmd += " mode {} {}x{}@{}Hz".format(
                custom_mode_str, db.physical_width, db.physical_height, db.refresh
            )

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

        if not use_desc:
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

        if os.path.isfile(outputs_path):
            backup = load_text_file(outputs_path).splitlines()
        else:
            backup = []

        save_list_to_text_file(lines, outputs_path)

        print("[Executing]")
        for cmd in cmds:
            print(cmd)

        i3 = Connection()
        for cmd in cmds:
            i3.command(cmd)

        if create_confirm_win_callback:
            create_confirm_win_callback(backup, outputs_path, config_dir, profile_name)

    @staticmethod
    def _apply_hyprland_gui(
        display_buttons,
        outputs_activity,
        outputs_path,
        use_desc,
        create_confirm_win_callback,
        config_dir=None,
        profile_name=None,
    ):
        transforms = {
            "normal": 0,
            "90": 1,
            "180": 2,
            "270": 3,
            "flipped": 4,
            "flipped-90": 5,
            "flipped-180": 6,
            "flipped-270": 7,
        }
        lines = [SettingsApplier._get_header()]

        for db in display_buttons:
            name = (
                db.name
                if not use_desc
                else "desc:{}".format(db.description.replace("#", "##"))
            )

            # Format: monitor=name,resolution@refresh,position,scale
            line = "monitor={},{}x{}@{},{}x{},{}".format(
                name,
                db.physical_width,
                db.physical_height,
                db.refresh,
                db.x,
                db.y,
                db.scale,
            )
            if db.mirror:
                line += ",mirror,{}".format(db.mirror)
            if db.ten_bit:
                line += ",bitdepth,10"

            lines.append(line)
            if db.transform != "normal":
                lines.append(
                    "monitor={},transform,{}".format(name, transforms[db.transform])
                )

            # avoid looking up the hardware name
            if db.name in outputs_activity and not outputs_activity[db.name]:
                lines.append("monitor={},disable".format(name))

            cmd = "on" if db.dpms else "off"
            hyprctl(f"dispatch dpms {cmd} {db.name}")

        print("[Saving]")
        for line in lines:
            print(line)

        backup = []
        if os.path.isfile(outputs_path):
            backup = load_text_file(outputs_path).splitlines()
        save_list_to_text_file(lines, outputs_path)

        if create_confirm_win_callback:
            create_confirm_win_callback(backup, outputs_path, config_dir, profile_name)

    @staticmethod
    def _get_header(source="nwg-displays"):
        now = datetime.datetime.now()
        return "# Generated by {} on {} at {}. Do not edit manually.\n".format(
            source,
            datetime.datetime.strftime(now, "%Y-%m-%d"),
            datetime.datetime.strftime(now, "%H:%M:%S"),
        )

    @staticmethod
    def _save_current_state_to_previous_profile(config_dir):
        """
        Reads the last active profile name, gets current wallpapers,
        and updates that profile's JSON file.
        """
        state_file = os.path.join(config_dir, "active_profile")

        if not os.path.isfile(state_file):
            return

        try:
            with open(state_file, "r") as f:
                last_profile_name = f.read().strip()

            if not last_profile_name:
                return

            prev_profile_path = os.path.join(
                config_dir, "profiles", f"{last_profile_name}.json"
            )

            if not os.path.isfile(prev_profile_path):
                print(
                    f"[Warning] Previous profile '{last_profile_name}' file not found. Skipping save."
                )
                return

            current_walls = WallpaperManager.get_current_wallpapers()
            print(f"[Persistence] Current wallpapers: {current_walls}")
            if not current_walls:
                return

            with open(prev_profile_path, "r") as f:
                data = json.load(f)

            if "wallpapers" not in data:
                data["wallpapers"] = {}

            data["wallpapers"].update(current_walls)
            print("Wallpaper saved!")

            with open(prev_profile_path, "w") as f:
                json.dump(data, f, indent=2)

            print(f"[Persistence] Saved current wallpapers to '{last_profile_name}'")

        except Exception as e:
            print(f"[Error] Failed to save previous state: {e}")

    @staticmethod
    def _set_active_profile(config_dir, profile_name):
        state_file = os.path.join(config_dir, "active_profile")
        try:
            with open(state_file, "w") as f:
                f.write(profile_name)
        except Exception as e:
            print(f"[Error] Failed to set active profile: {e}")

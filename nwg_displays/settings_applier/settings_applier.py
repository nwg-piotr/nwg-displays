import os
import shutil
import datetime
import json
import time
from nwg_displays.tools import (
    hyprctl,
    niri_msg,
    niri_reload_config,
    save_list_to_text_file,
    save_kdl_output,
    ensure_niri_config_include,
    load_text_file,
    inactive_output_description,
    load_json,
    save_json,
)
from nwg_displays.wallpaper_manager import WallpaperManager
from nwg_displays.tools import get_config

class SettingsApplier:
    @staticmethod
    def apply_from_json(profile_data, outputs_path, config_dir, profile_name):
        """Applies configuration based on a Profile JSON file."""
        SettingsApplier._save_current_state_to_previous_profile(config_dir)

        displays = profile_data["displays"]
        config = profile_data["config"]
        use_desc = config.get("use-desc", False)

        if os.getenv("NIRI_SOCKET"):
            SettingsApplier._apply_niri_json(
                displays, use_desc, outputs_path, profile_data
            )

        elif os.getenv("HYPRLAND_INSTANCE_SIGNATURE"):
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

        header = SettingsApplier._get_header("Profile Loader")
        lines_conf = [header]
        lines_lua = [header.replace("#", "--")]

        for d in displays:
            if not use_desc:
                name = d["name"]
            else:
                desc_safe = d["description"].replace("#", "##")
                name = f"desc:{desc_safe}"

            lua_props = [f'    output = "{name}"']

            if not d["active"]:
                lines_conf.append(f"monitor={name},disable")
                lua_props.append("    disabled = true")
                hyprctl(f"dispatch dpms off {d['name']}")
            else:
                conf_line = "monitor={},{}x{}@{},{}x{},{}".format(
                    name,
                    d["physical_width"],
                    d["physical_height"],
                    d["refresh"],
                    d["x"],
                    d["y"],
                    d["scale"],
                )

                mode = f"{d['physical_width']}x{d['physical_height']}@{d['refresh']}"
                pos = f"{d['x']}x{d['y']}"
                lua_props.extend([
                    f'    mode = "{mode}"',
                    f'    position = "{pos}"',
                    f'    scale = {d["scale"]}',
                ])

                if d.get("mirror"):
                    conf_line += f",mirror,{d['mirror']}"
                    lua_props.append(f'    mirror = "{d["mirror"]}"')

                color_mode = d.get("color_mode") or ""
                hdr = color_mode in ("hdr", "hdredid")

                # HDR requires 10-bit; force it even if not explicitly stored
                if d.get("ten_bit") or hdr:
                    conf_line += ",bitdepth,10"
                    lua_props.append("    bitdepth = 10")

                if color_mode:
                    conf_line += f",cm,{color_mode}"
                    lua_props.append(f'    cm = "{color_mode}"')
                    if hdr:
                        sdr_brightness = d.get("sdr_brightness", 1.0)
                        sdr_saturation = d.get("sdr_saturation", 1.0)
                        if sdr_brightness != 1.0:
                            conf_line += f",sdrbrightness,{sdr_brightness}"
                            lua_props.append(f"    sdrbrightness = {sdr_brightness}")
                        if sdr_saturation != 1.0:
                            conf_line += f",sdrsaturation,{sdr_saturation}"
                            lua_props.append(f"    sdrsaturation = {sdr_saturation}")

                # Adaptive sync (VRR). The toggle mirrors the monitor's effective
                # state, so writing it explicitly is safe and keeps the toggle working.
                # note: hyprland can also accept 2 or 3 to enable fullscreen-only VRR;
                # may need to add that in the future
                vrr = "1" if d.get("adaptive_sync") else "0"
                conf_line += f",vrr,{vrr}"
                lua_props.append(f"    vrr = {vrr}")

                lines_conf.append(conf_line)

                if d["transform"] != "normal":
                    t_code = transforms.get(d["transform"], 0)
                    lines_conf.append(f"monitor={name},transform,{t_code}")
                    lua_props.append(f"    transform = {t_code}")

                cmd = "on" if d["dpms"] else "off"
                hyprctl(f"dispatch dpms {cmd} {d['name']}")

            lua_table = ",\n".join(lua_props)
            lines_lua.append(f"hl.monitor({{\n{lua_table}\n}})")

        outputs_path_lua = (
            outputs_path.removesuffix(".conf") + ".lua"
            if outputs_path.endswith(".conf")
            else "~/.config/hypr/monitors.lua"
        )

        save_list_to_text_file(lines_conf, outputs_path)
        save_list_to_text_file(lines_lua, outputs_path_lua)

        hyprctl("reload")

        config, config_file = get_config()

        if "wallpapers" in profile_data and config.get(
            "profile-bound-wallpapers", True
        ):
            print("[Profile] Applying wallpapers...")
            time.sleep(1)
            WallpaperManager.apply_wallpapers(profile_data["wallpapers"])

    @staticmethod
    def _apply_niri_json(displays, use_desc, outputs_path, profile_data):
        """Apply niri configuration by writing monitor.kdl file"""
        print(f"[Profile] Applying {len(displays)} displays for niri...")
        
        kdl_data = []
        for d in displays:
            name = d["name"]
            
            display_config = {
                "name": name,
                "active": d["active"],
                "physical_width": d["physical_width"],
                "physical_height": d["physical_height"],
                "refresh": d["refresh"],
                "x": d["x"],
                "y": d["y"],
                "scale": d["scale"],
                "transform": d["transform"],
                "adaptive_sync": d.get("adaptive_sync", False)
            }
            kdl_data.append(display_config)
        
        # Save to monitor.kdl
        save_kdl_output(kdl_data, outputs_path)
        
        # Ensure config.kdl includes monitor.kdl
        niri_config_dir = os.path.dirname(outputs_path)
        ensure_niri_config_include(niri_config_dir, outputs_path)
        
        # Reload niri configuration
        niri_reload_config()
        
        config, config_file = get_config()
        
        if "wallpapers" in profile_data and config.get(
            "profile-bound-wallpapers", True
        ):
            print("[Profile] Applying wallpapers...")
            import time
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

        if os.getenv("NIRI_SOCKET"):
            print(f"[DEBUG] Applying niri config to {outputs_path}")
            SettingsApplier._apply_niri_gui(
                display_buttons,
                outputs_activity,
                outputs_path,
                use_desc,
                create_confirm_win_callback,
                config_dir,
                profile_name,
            )

        elif os.getenv("SWAYSOCK"):
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
        else:
            print("[Error] No compositor detected (Sway/Hyprland/Niri)")

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

        if os.path.isfile(outputs_path):
            backup = load_text_file(outputs_path).splitlines()
        else:
            backup = []

        save_list_to_text_file(lines, outputs_path)

        i3 = Connection()
        for cmd in cmds:
            i3.command(cmd)

        if create_confirm_win_callback:
            create_confirm_win_callback(backup, outputs_path, config_dir, profile_name)

    @staticmethod
    def _apply_niri_gui(
        display_buttons,
        outputs_activity,
        outputs_path,
        use_desc,
        create_confirm_win_callback,
        config_dir=None,
        profile_name=None,
    ):
        """Apply niri configuration from GUI by writing monitor.kdl file"""
        print(f"[niri] Applying {len(display_buttons)} displays...")
        
        # Save backup BEFORE applying new settings
        backup_path = outputs_path + ".bak"
        if os.path.isfile(outputs_path):
            shutil.copy2(outputs_path, backup_path)
            print(f"[niri] Backup saved to {backup_path}")
        else:
            backup_path = None
        
        kdl_data = []
        for db in display_buttons:
            display_config = {
                "name": db.name,
                "active": db.name not in outputs_activity or outputs_activity.get(db.name, True),
                "physical_width": db.physical_width,
                "physical_height": db.physical_height,
                "refresh": db.refresh,
                "x": db.x,
                "y": db.y,
                "scale": db.scale,
                "transform": db.transform,
                "adaptive_sync": db.adaptive_sync
            }
            kdl_data.append(display_config)
        
        # Save to monitor.kdl in KDL format
        save_kdl_output(kdl_data, outputs_path)
        
        # Ensure config.kdl includes monitor.kdl
        niri_config_dir = os.path.dirname(outputs_path)
        ensure_niri_config_include(niri_config_dir, outputs_path)
        
        # Reload niri configuration
        niri_reload_config()
        
        # Pass backup file path and current file path to confirm window
        if create_confirm_win_callback:
            create_confirm_win_callback(backup_path, outputs_path, config_dir, profile_name)

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

        header = SettingsApplier._get_header()
        lines_conf = [header]
        lines_lua = [header.replace("#", "--")]

        for db in display_buttons:
            name = (
                db.name
                if not use_desc
                else "desc:{}".format(db.description.replace("#", "##"))
            )

            lua_props = [f'    output = "{name}"']

            if db.name in outputs_activity and not outputs_activity[db.name]:
                lines_conf.append(f"monitor={name},disable")
                lua_props.append("    disabled = true")
                hyprctl(f"dispatch dpms off {db.name}")
            else:
                conf_line = f"monitor={name},{db.physical_width}x{db.physical_height}@{db.refresh},{db.x}x{db.y},{db.scale}"

                mode = f"{db.physical_width}x{db.physical_height}@{db.refresh}"
                pos = f"{db.x}x{db.y}"
                lua_props.extend([
                    f'    mode = "{mode}"',
                    f'    position = "{pos}"',
                    f"    scale = {db.scale}",
                ])

                if db.mirror:
                    conf_line += f",mirror,{db.mirror}"
                    lua_props.append(f'    mirror = "{db.mirror}"')

                color_mode = getattr(db, "color_mode", "") or ""
                hdr = color_mode in ("hdr", "hdredid")

                # HDR requires 10-bit; force it even if the checkbox is off
                if db.ten_bit or hdr:
                    conf_line += ",bitdepth,10"
                    lua_props.append("    bitdepth = 10")

                if color_mode:
                    conf_line += f",cm,{color_mode}"
                    lua_props.append(f'    cm = "{color_mode}"')
                    if hdr:
                        sdr_brightness = getattr(db, "sdr_brightness", 1.0)
                        sdr_saturation = getattr(db, "sdr_saturation", 1.0)
                        if sdr_brightness != 1.0:
                            conf_line += f",sdrbrightness,{sdr_brightness}"
                            lua_props.append(f"    sdrbrightness = {sdr_brightness}")
                        if sdr_saturation != 1.0:
                            conf_line += f",sdrsaturation,{sdr_saturation}"
                            lua_props.append(f"    sdrsaturation = {sdr_saturation}")

                # Adaptive sync (VRR). The toggle mirrors the monitor's effective
                # state, so writing it explicitly is safe and keeps the toggle working.
                vrr = "1" if db.adaptive_sync else "0"
                conf_line += f",vrr,{vrr}"
                lua_props.append(f"    vrr = {vrr}")

                lines_conf.append(conf_line)

                if db.transform != "normal":
                    t_code = transforms.get(db.transform, 0)
                    lines_conf.append(f"monitor={name},transform,{t_code}")
                    lua_props.append(f"    transform = {t_code}")

                cmd = "on" if db.dpms else "off"
                hyprctl(f"dispatch dpms {cmd} {db.name}")

            lua_table = ",\n".join(lua_props)
            lines_lua.append(f"hl.monitor({{\n{lua_table}\n}})")

        backup_conf = []
        if os.path.isfile(outputs_path):
            backup_conf = load_text_file(outputs_path).splitlines()

        outputs_path_lua = (
            outputs_path.removesuffix(".conf") + ".lua"
            if outputs_path.endswith(".conf")
            else "~/.config/hypr/monitors.lua"
        )

        backup_lua = []
        if os.path.isfile(outputs_path_lua):
            backup_lua = load_text_file(outputs_path_lua).splitlines()

        save_list_to_text_file(lines_conf, outputs_path)
        save_list_to_text_file(lines_lua, outputs_path_lua)

        hyprctl("reload")

        backup = (backup_conf, backup_lua)

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
        state_file = os.path.join(config_dir, "active_profile.json")

        if not os.path.isfile(state_file):
            return

        try:
            data = load_json(state_file)
            last_profile_name = data.get("active_profile") if data else None

            if not last_profile_name:
                return

            config, _ = get_config()
            if not config.get("profile-bound-wallpapers", True):
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
            if not current_walls:
                return

            with open(prev_profile_path, "r") as f:
                data = json.load(f)

            if "wallpapers" not in data:
                data["wallpapers"] = {}

            data["wallpapers"].update(current_walls)

            with open(prev_profile_path, "w") as f:
                json.dump(data, f, indent=2)

            print(f"[Persistence] Saved current wallpapers to '{last_profile_name}'")

        except Exception as e:
            print(f"[Error] Failed to save previous state: {e}")

    @staticmethod
    def _set_active_profile(config_dir, profile_name):
        state_file = os.path.join(config_dir, "active_profile.json")
        try:
            save_json({"active_profile": profile_name}, state_file)
        except Exception as e:
            print(f"[Error] Failed to set active profile: {e}")

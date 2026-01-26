import os
import stat
import subprocess
import json
import time

# from nwg_displays.main import sway
from nwg_displays.tools import is_command, load_text_file


class WallpaperManager:
    @staticmethod
    def get_current_wallpapers():
        """Returns a dict containing path and mode fields attached to monitor names. For swww mode fields are empty."""
        if not is_command("nwg-shell") and not is_command("swww"):
            return {}

        # Firstly we need to support nwg-shell-related wallpapers, and we use Azote Wallpaper Manager here.
        # Let's parse the ~/.azotebg or ~/azotebg-hyprland batch file.
        if is_command("nwg-shell") and (os.getenv("SWAYSOCK") or os.getenv("HYPRLAND_INSTANCE_SIGNATURE")):
            if os.getenv("SWAYSOCK"):
                azotebg_file = os.path.join(os.getenv("HOME"), ".azotebg")
            else:
                azotebg_file = os.path.join(os.getenv("HOME"), ".azotebg-hyprland")
            azotebg_content = load_text_file(azotebg_file)
            if azotebg_content:
                return WallpaperManager.parse_azotebg_content(azotebg_content)
            else:
                print(f"[Error] Couldn't find ~/.azotebg* file")
                return {}
        else:
            try:
                output = subprocess.check_output(["swww", "query"], text=True)
                return WallpaperManager._parse_swww_output(output)
            except Exception as e:
                print(f"[Error] Failed to query swww: {e}")
                return {}

    @staticmethod
    def parse_azotebg_content(content):
        """Parses the azotebg content and returns a dict containing path and mode for each output."""
        # The content of the batch file written by Azote will look something like this:
        # pkill swaybg
        # swaybg -o 'DP-1' -i "/home/piotr/Obrazy/Wallpapers/nwg_3a_3840x2160px.jpg" -m fill &
        # swaybg -o 'DP-2' -i "/home/piotr/Obrazy/Wallpapers/nwg_3a_3840x2160px.jpg" -m fill &
        current_walls = {}
        for line in content.splitlines():
            fields = line.split()
            if line.startswith("swaybg"):
                try:
                    monitor = fields[2][1:-1]
                    path = fields[4][1:-1]
                    mode = fields[6]
                    current_walls[monitor] = {"path": path, "mode": mode}
                except IndexError:
                    print(f"[Error parsing line] {line}")
        return current_walls


    @staticmethod
    def _parse_swww_output(output):
        current_walls = {}
        for line in output.splitlines():
            if "currently displaying: " in line:
                # New swww format: <namespace>: <monitor>: <resolution>, ... currently displaying: <path>
                path = line.split("currently displaying: ")[-1].strip()
                if path.startswith("image: "):
                    path = path[7:]
                parts = line.split(": ")
                monitor = None
                # Look for the resolution field (starts with digit) and take the preceding field as monitor
                for i, part in enumerate(parts):
                    if len(part) > 0 and part[0].isdigit() and i > 0:
                        candidate = parts[i - 1].strip()
                        if candidate != "scale":
                            monitor = candidate
                            break
                if monitor:
                    # for the sake of Azote compatibility, we also need to store the mode value, that will be empty here
                    current_walls[monitor] = {"path": path, "mode": ""}
            elif ": " in line:
                parts = line.split(": ", 1)
                if len(parts) == 2:
                    monitor = parts[0].strip()
                    if monitor.startswith("Output "):
                        monitor = monitor[7:]
                    # swww sometimes returns extra info, ensure we just get the path
                    path = parts[1].strip().split(" ")[0]
                    current_walls[monitor] = {"path": path, "mode": ""}
        return current_walls

    @staticmethod
    def apply_wallpapers(wallpaper_data):
        if not wallpaper_data:
            return

        if is_command("nwg-shell"):
            WallpaperManager._apply_azotebg(wallpaper_data)
            return

        if is_command("swww"):
            WallpaperManager._apply_swww(wallpaper_data)
            return

        if is_command("hyprpaper"):
            WallpaperManager._apply_hyprpaper()
            return

        print("[Error] No wallpaper daemon found (swww/hyprpaper/swaybg)")

    @staticmethod
    def _apply_azotebg(wallpaper_data):
        print("[Wallpapers] Using nwg-shell/Azote/swaybg backend")
        batch_content = ['#!/usr/bin/env bash', 'pkill swaybg']
        for key in wallpaper_data:
            batch_content.append(f"swaybg -o '{key}' -i \"{wallpaper_data[key]['path']}\" -m {wallpaper_data[key]['mode']} &")
        print("\n".join(batch_content))

        if os.getenv("SWAYSOCK"):
            azotebg_file = os.path.join(os.getenv("HOME"), ".azotebg")
        else:
            azotebg_file = os.path.join(os.getenv("HOME"), ".azotebg-hyprland")

        # write to .azotebg* file
        with open(azotebg_file, 'w') as f:
            for item in batch_content:
                f.write("%s\n" % item)
        # make the file executable
        st = os.stat(azotebg_file)
        os.chmod(azotebg_file, st.st_mode | stat.S_IEXEC)
        # execute
        subprocess.call(azotebg_file, shell=True)

    @staticmethod
    def _apply_swww(wallpaper_data):
        print("[Wallpapers] Using swww backend")
        # for monitor, path in wallpaper_data.items():
        for key in wallpaper_data:
            path = wallpaper_data[key]["path"]
            path = os.path.expanduser(os.path.expandvars(path))
            if os.path.isfile(path):
                print(f"[Wallpapers] Setting {key} to {path}")
                # Using 'grow' transition for smooth profile switching
                cmd = f"swww img -o {key} '{path}' --transition-type grow --transition-pos 0.8,0.9 --transition-step 90"
                os.system(cmd)
            else:
                print(f"[Warning] Wallpaper file not found: {path}")

    @staticmethod
    def _apply_hyprpaper():
        print("[Wallpapers] Hyprpaper detected (swww is recommended for profiles)")
        pass

    @staticmethod
    def apply_profile_wallpapers(config_dir, profile_name):
        profile_path = os.path.join(config_dir, "profiles", f"{profile_name}.json")
        if os.path.isfile(profile_path):
            try:
                with open(profile_path, "r") as f:
                    profile_data = json.load(f)
                if "wallpapers" in profile_data:
                    print("[Profile] Applying wallpapers...")
                    time.sleep(1)
                    WallpaperManager.apply_wallpapers(profile_data["wallpapers"])
            except Exception as e:
                print(f"[Error] Failed to apply wallpapers from profile: {e}")

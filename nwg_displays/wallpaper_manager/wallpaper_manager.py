import os
import shutil
import subprocess


class WallpaperManager:
    @staticmethod
    def get_current_wallpapers():
        """Returns a dict of {monitor: path} from running swww instances."""
        if not shutil.which("swww"):
            return {}

        try:
            # swww query returns format: "Output: /path/to/image ..."
            output = subprocess.check_output(["swww", "query"], text=True)
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
                        current_walls[monitor] = path
                elif ": " in line:
                    parts = line.split(": ", 1)
                    if len(parts) == 2:
                        monitor = parts[0].strip()
                        # swww sometimes returns extra info, ensure we just get the path
                        path = parts[1].strip().split(" ")[0]
                        current_walls[monitor] = path
            return current_walls
        except Exception as e:
            print(f"[Error] Failed to query swww: {e}")
            return {}

    @staticmethod
    def apply_wallpapers(wallpaper_data):
        if not wallpaper_data:
            return

        if shutil.which("swww"):
            print("[Wallpapers] Using swww backend")
            for monitor, path in wallpaper_data.items():
                path = os.path.expanduser(os.path.expandvars(path))
                if os.path.isfile(path):
                    print(f"[Wallpapers] Setting {monitor} to {path}")
                    # Using 'grow' transition for smooth profile switching
                    cmd = f"swww img -o {monitor} '{path}' --transition-type grow --transition-pos 0.8,0.9 --transition-step 90"
                    os.system(cmd)
                else:
                    print(f"[Warning] Wallpaper file not found: {path}")

        elif shutil.which("hyprpaper"):
            print("[Wallpapers] Hyprpaper detected (swww is recommended for profiles)")
            pass

        else:
            print("[Error] No wallpaper daemon found (swww/hyprpaper/swaybg)")

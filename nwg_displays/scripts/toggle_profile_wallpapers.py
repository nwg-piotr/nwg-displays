import os
import sys
from nwg_displays.tools import save_json
from nwg_displays.utils.get_config import get_config


def main():
    config, config_file = get_config()

    # Toggle the value, defaulting to True if not present
    current_value = config.get("profile-bound-wallpapers", True)
    new_value = not current_value
    config["profile-bound-wallpapers"] = new_value

    save_json(config, config_file)
    print(f"[Config] Saved configuration to {config_file}")

    status = "enabled" if new_value else "disabled"
    print(f"[Config] Profile-bound wallpapers {status}")


if __name__ == "__main__":
    main()

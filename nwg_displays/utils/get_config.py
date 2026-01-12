import os
import sys
from nwg_displays.utils.get_config_dir import get_config_dir
from nwg_displays.tools import load_json


def get_config():
    config_dir = get_config_dir()
    config_file = os.path.join(config_dir, "config")

    if not os.path.isfile(config_file):
        print(f"[Error] Config file not found at {config_file}")
        sys.exit(1)

    config = load_json(config_file)
    if config is None:
        print("[Error] Failed to load configuration")
        sys.exit(1)

    return config, config_file

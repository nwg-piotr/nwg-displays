import os
import sys
import json
import argparse
from nwg_displays.settings_applier import SettingsApplier
from nwg_displays.utils import get_config_dir

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load nwg-displays profile directly.")
    parser.add_argument(
        "-p", "--profile", type=str, required=True, help="Name of the profile to load"
    )
    parser.add_argument(
        "-c", "--config", type=str, help="Path to monitors.conf override"
    )

    args = parser.parse_args()

    config_dir = get_config_dir()
    profile_path = os.path.join(config_dir, "profiles", f"{args.profile}.json")

    if args.config:
        outputs_path = args.config
    else:
        outputs_path = os.path.join(
            os.path.expanduser("~/.config/hypr/"), "monitors.conf"
        )

    if not os.path.isfile(profile_path):
        print(f"Error: Profile file not found at {profile_path}")
        sys.exit(1)

    try:
        # Load and Apply new profile
        with open(profile_path, "r") as f:
            profile_data = json.load(f)

        print(f"Loading profile: '{args.profile}'")
        SettingsApplier.apply_from_json(
            profile_data, outputs_path, config_dir, args.profile
        )

        print("Done.")

    except json.JSONDecodeError:
        print(f"Error: Failed to parse {profile_path}. Invalid JSON.")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

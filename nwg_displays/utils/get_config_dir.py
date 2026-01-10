import os


def get_config_dir():
    xdg_config_home = os.getenv("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(xdg_config_home, "nwg-displays")

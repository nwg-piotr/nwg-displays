# nwg-displays

Output management utility for sway Wayland compositor, inspired by wdisplays and wlay.

This program is a part of the [nwg-shell](https://github.com/nwg-piotr/nwg-shell) project.

**nwg-displays is expected to:**

- provide an intuitive GUI to manage multiple displays;
- apply settings on the fly;
- save outputs configuration to a text file;
- support sway only.

![2022-03-10-033822_screenshot](https://user-images.githubusercontent.com/20579136/157577549-f921b9a3-d0f3-4747-8585-5e6a1da63925.png)

## Usage

```text
$ nwg-displays -h
usage: nwg-displays [-h] [-o OUTPUT_PATH] [-g] [-v]

options:
  -h, --help            show this help message and exit
  -o OUTPUT_PATH, --output_path OUTPUT_PATH
                        path to save Outputs config to, default: /home/piotr/.config/sway/outputs
  -g, --generic_names   use Generic output names
  -v, --version         display version information
```

The configuration saved to a file may be easily used in the sway config:

```text
...
include ~/.config/sway/outputs
...
```

Use `--generic_names` if your output names happen to be different on every restart, e.g. when you use Thunderbolt outputs. 

## Settings

The runtime configuration file is placed in your config directory, like `~/.config/nwg-displays/config`. 
It's a simple `jsnon` file:

```json
{
  "view-scale": 0.15,
  "snap-threshold": 10,
  "indicator-timeout": 300
}
```

- `view-scale` does not need to be changed manually. The GUI takes care of that.
- `snap-threshold` specifies the flush margin of widgets representing displays. I added this value just in case, as I have no hi DPI display to test the stuff on.
- `indicator-timeout` determines how long (in milliseconds) the overlay identifying screens should be visible. Set 0 to turn overlays off.
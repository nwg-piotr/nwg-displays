# nwg-displays

This application is a part of the [nwg-shell](https://nwg-piotr.github.io/nwg-shell) project.

**Contributing:** please read the [general contributing rules for the nwg-shell project](https://nwg-piotr.github.io/nwg-shell/contribution).

Output management utility for sway Wayland compositor, inspired by wdisplays and wlay.

[![Packaging status](https://repology.org/badge/vertical-allrepos/nwg-displays.svg)](https://repology.org/project/nwg-displays/versions)

**nwg-displays is expected to:**

- provide an intuitive GUI to manage multiple displays;
- apply settings;
- save outputs configuration to a text file;
- save workspace -> output assignments to a text file;
- support sway and Hyprland only.

![2022-03-12-110614_screenshot](https://user-images.githubusercontent.com/20579136/158013748-5b27f742-0e6a-4d82-a5ac-06368b4df008.png)


## Usage

```text
$ nwg-displays -h
usage: nwg-displays [-h] [-g] [-o OUTPUTS_PATH] [-n NUM_WS] [-v]

options:
  -h, --help            show this help message and exit
  -g, --generic_names   use Generic output names
  -o OUTPUTS_PATH, --outputs_path OUTPUTS_PATH
                        path to save Outputs config to, default: /home/piotr/.config/sway/outputs
  -n NUM_WS, --num_ws NUM_WS
                        number of Workspaces in use, default: 8
  -v, --version         display version information
```

### sway

The configuration saved to a file may be easily used in the sway config:

```text
...
include ~/.config/sway/outputs
...
```

The program also saves the `~/.config/sway/workspaces` file, which defines the workspace -> output associations.

```text
workspace 1 output DP-1
workspace 2 output DP-1
workspace 3 output DP-1
workspace 4 output eDP-1
workspace 5 output eDP-1
workspace 6 output eDP-1
workspace 7 output HDMI-A-1
workspace 8 output HDMI-A-1
```

You may include it in the sway config file, instead of editing associations manually:

```text
...
include ~/.config/sway/workspaces
...
```

Use `--generic_names` if your output names happen to be different on every restart, e.g. when you use Thunderbolt outputs.

Use `--num_ws` if you use workspaces in a number other than 8.

### Hyprland

[Monitors](https://wiki.hyprland.org/Configuring/Monitors):

Instead of configuring as described in Wiki, insert this line:

```text
source = ~/.config/hypr/monitors.conf
```

[Default workspace](http://wiki.hyprland.org/Configuring/Monitors/#default-workspace) and [Binding workspaces to a monitor](https://wiki.hyprland.org/Configuring/Monitors/#binding-workspaces-to-a-monitor):

Insert:

```text
source = ~/.config/hypr/workspaces.conf
```

## Settings

The runtime configuration file is placed in your config directory, like `~/.config/nwg-displays/config`. 
It's a simple `jsnon` file:

```json
{
  "view-scale": 0.15,
  "snap-threshold": 10,
  "indicator-timeout": 500
}
```

- `view-scale` does not need to be changed manually. The GUI takes care of that.
- `snap-threshold` specifies the flush margin of widgets representing displays. I added this value just in case, as I have no hi DPI display to test the stuff on.
- `indicator-timeout` determines how long (in milliseconds) the overlay identifying screens should be visible. Set 0 to turn overlays off.

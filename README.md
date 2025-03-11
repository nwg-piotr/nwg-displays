<img src="https://github.com/nwg-piotr/nwg-displays/assets/20579136/b7c31822-8846-44be-8028-af3f3af4acd8" width="90" style="margin-right:10px" align=left alt="nwg-shell logo">
<H1>nwg-displays</H1><br>

This application is a part of the [nwg-shell](https://nwg-piotr.github.io/nwg-shell) project.

**Nwg-displays** is an output management utility for [sway](https://github.com/swaywm/sway) and [Hyprland](https://github.com/hyprwm/Hyprland) 
Wayland compositor, inspired by wdisplays and wlay. The program is expected to:

- provide an intuitive GUI to manage multiple displays;
- apply settings;
- save outputs configuration to a text file;
- save workspace -> output assignments to a text file;
- support sway and Hyprland only.

<img src="https://user-images.githubusercontent.com/20579136/158013748-5b27f742-0e6a-4d82-a5ac-06368b4df008.png" width=640, alt="screenshot"><br>

## Installation

Install from your linux distribution repository if possible.

[![Packaging status](https://repology.org/badge/vertical-allrepos/nwg-displays.svg)](https://repology.org/project/nwg-displays/versions)

Otherwise, clone this repository and run the `install.sh` script.

### Dependencies

- gtk-layer-shell
- gtk3
- python
- python-gobject
- python-i3ipc
- python-build (make)
- python-installer (make)
- python-setuptools (make)
- python-wheel (make)

## Usage

```text
$  nwg-displays -h
usage: nwg-displays [-h] [-m MONITORS_PATH] [-n NUM_WS] [-v]

options:
  -h, --help            show this help message and exit
  -m MONITORS_PATH, --monitors_path MONITORS_PATH
                        path to save the monitors.conf file to, default: ~/.config/hypr/monitors.conf
  -n NUM_WS, --num_ws NUM_WS
                        number of Workspaces in use, default: 10
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

Do not set `disable_autoreload true` in Hyprland settings, or you'll have to reload Hyprland manually after applying chages.

## Settings

The runtime configuration file is placed in your config directory, like `~/.config/nwg-displays/config`. 
It's a simple JSON file:

```json
{
  "view-scale": 0.15,
  "snap-threshold": 10,
  "indicator-timeout": 500
}
```

- `view-scale` does not need to be changed manually. The GUI takes care of that.
- `snap-threshold` specifies the flush margin of widgets representing displays. I added this value just in case, as I have no high-DPI display to test the stuff on.
- `indicator-timeout` determines how long (in milliseconds) the overlay identifying screens should be visible. Set 0 to turn overlays off.

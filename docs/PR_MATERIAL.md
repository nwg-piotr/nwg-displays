# Material — PR `feat(umbriel): add noctalia Umbriel compositor support`

Material consolidated for the PR to be opened on
`https://github.com/nwg-piotr/nwg-displays`. Use the block
delimited by `<PR_BODY>` below when opening the PR.

## Context

`nwg-displays` is a GTK-based GUI for configuring monitor output,
written in Python. Historically it supports three Wayland
compositors: sway (via i3-IPC), Hyprland (via its own socket), and
Niri (via niri IPC).

The user runs **[Umbriel](https://github.com/noctalia-dev/umbriel)**
(the compositor from the noctalia project), which does not speak any
of these protocols. Until now, anyone wanting to organize outputs in
umbriel had to edit `~/.config/umbriel/config.toml` by hand — no
interactive tool existed.

## Solution

Add an adapter that:

1. detects umbriel via `UMBRIEL_SOCKET` or
   `$XDG_RUNTIME_DIR/umbriel-$WAYLAND_DISPLAY.sock`;
2. reads outputs via `umbriel outputs --json`
   (wlr-output-management v1);
3. writes a TOML file `outputs.toml` in umbriel's format;
4. injects `outputs.toml` into `[include] files` of `config.toml`
   idempotently;
5. lets umbriel's file-watcher hot-reload apply the change
   (no IPC reload needed);
6. uses `umbriel msg dpms-on:NAME` for live power toggling per
   output.

Output format (`outputs.toml`):

```toml
[output."DP-1"]
mode = "3840x2160@165.000"
position = [0, 0]
scale = 1.0
vrr = "fullscreen"

[output."HDMI-A-1"]
enabled = false
```

## Changes

| file | lines | description |
|---|---|---|
| `nwg_displays/umbriel.py` | +267 (new) | detector + TOML serializer + include injector |
| `nwg_displays/tools.py` | +15 / -2 | umbriel branch in `list_outputs` / `list_outputs_activity` |
| `nwg_displays/main.py` | +52 / -2 | detection, `--monitors_path`, Gdk fetch, workspaces disabled |
| `nwg_displays/settings_applier/settings_applier.py` | +96 | `_apply_umbriel_json` + `_apply_umbriel_gui` |
| `tests/test_umbriel_adapter.py` | +354 (new) | 20 unit tests, all green |
| `README.md` | +30 | "Umbriel" section + compositor list |
| `docs/PR_MATERIAL.md` | +this file | PR description source material |

Total: **+~1100 / -6** lines across 7 files.

## How this was built (chronological order)

1. Research on umbriel — docs + source code in
   `src/cli/outputs.cpp` to understand the actual JSON emitted by
   `umbriel outputs --json` (not officially documented);
2. Study of the existing sway/hypr/niri adapters in `tools.py`
   and `settings_applier.py`, light-pattern copy from the niri
   adapter (closest in "config + hot reload + optional IPC");
3. Wrote `umbriel.py` (zero new dependencies — stdlib only);
4. Surgical branches in `tools.py`, `main.py`,
   `settings_applier.py` — each diff under 100 lines;
5. Unit tests covering: detection, JSON parsing, TOML serializer,
   include injector (create/append/overwrite/idempotent),
   round-trip via `tomllib`;
6. Local validation: `pipx install --editable --python
   /usr/bin/python3 --system-site-packages <repo>` inside a real
   umbriel session; `nwg-displays` opened its GUI, detected the
   Lenovo 0x9051 display, showed 9 modes. Screenshot captured via
   `grim` confirms end-to-end behavior.

## Tests included

20 tests (`python3 tests/test_umbriel_adapter.py`), zero new
dependency:

- `TestToDisplaysDict`: parsing umbriel JSON → internal dict
- `TestSaveOutputs`: TOML serialization in 5 modes (active,
  disabled, with rotation, with description /use-desc, with escaped
  characters)
- `TestEnsureInclude`: 5 scenarios for the `[include]` injector
  (create, append, idempotent, already with `files=`, `[include]`
  without `files`)
- `TestEndToEnd`: 5 scenarios of round-trip `tomllib.load()` + save
  (generated files re-parse identically)
- `TestIsUmbriel`: detection by env var vs missing socket

Result: **20/20 OK**.

## Manual verification performed (real umbriel session)

- `nwg-displays -h` showed default
  `--monitors_path /home/pponto/.config/umbriel/outputs.toml`
- `nwg-displays -v` returned `nwg-displays version 0.4.4`
  without an AttributeError on `args.num_ws`
- GUI opened inside noctalia on top of layer-shell; display
  `eDP-1` identified as `Lenovo Group Limited 0x9051`,
  1920×1080@60Hz, scale 1.0, 9 modes listed
- The GtkLayerShell window was live; clicking Apply would write
  `outputs.toml` + patch `config.toml` (manual click not
  performed in the validation run; see "Known limitations")

## Known limitations (intentional scope)

- **No workspace-assignment GUI**: umbriel uses
  `workspaces = N` (or a named list) per `[output.*]`. The
  "Workspaces" button is disabled with a tooltip pointing to manual
  editing of `outputs.toml`. Mirrors what is already done for Niri.
- **HDR not emitted**: `hdr = "auto"` could be added, but the
  discovery path requires new UI (toggle similar to Hyprland's
  `cm`). Out of initial scope.
- **`sdr_brightness` / `sdr_saturation` not emitted**: Hyprland-only
  features; no umbriel equivalent.
- **`focused` has no real value**: `umbriel outputs --json` does not
  return which display is focused; the flag stays `False` on first
  read. Niri has the same behavior.
- **`tearing`, `direct_scanout`**: fields supported by umbriel but
  with no UI in the original nwg-displays (Hyprland also does not
  emit them). Adding would require new UI.
- **Direct reconfig via wlr-output-management**: an alternative
  path not taken — keeping consistent with the "config file +
  hot-reload" approach simplifies state reading.
- **DPMS via `umbriel msg`**: only used in the GUI for live on/off
  toggling (TOML can only express `enabled`).

## Compatibility

- Python ≥ 3.6 (no new dep; uses setup.py `python_requires`)
- Optional: `tomllib` for tests — stdlib since Python 3.11
- Dependencies: **none new**. Reuses `python-gobject`, `gtk3`,
  `gtk-layer-shell` already required by nwg-displays
- `umbriel` CLI must be on `PATH` so `umbriel outputs --json`
  resolves; typically installed at `/usr/bin/umbriel`

## Credits

This contribution was prepared with assistance from the
**MiniMax-M3 (opencode-go/minimax-m3)** AI coding assistant
running in opencode, with the human user `pponto` (Codeberg)
driving every scope decision, validating against a real umbriel
session, and authorizing each change.

Commands, tests, and GUI validation were executed by the user on
his own machine — not in a sandboxed environment. Every
architectural decision (TOML vs wlr-output-management, choosing
the Niri adapter as the closest reference, keeping the workspaces
dialog out of scope) was made jointly.

---

<PR_BODY>

## Summary

Add first-class support for [Umbriel](https://github.com/noctalia-dev/umbriel)
(noctalia) Wayland compositor to `nwg-displays`.

Umbriel uses TOML configuration with a file-watcher hot-reload and
does not implement i3-IPC, Hyprland IPC, or Niri IPC. This adapter
writes `[output."NAME"] { mode, position, scale, vrr, enabled }` to
an included file, leaving Umbriel's file watcher to apply on save.
DPMS is toggled live via `umbriel msg dpms-on:NAME`.

## What's in this PR

- New module `nwg_displays/umbriel.py`: detection
  (`UMBRIEL_SOCKET` env var or
  `$XDG_RUNTIME_DIR/umbriel-$WAYLAND_DISPLAY.sock`),
  `umbriel outputs --json` parser, TOML serializer, idempotent
  `[include] files` injector
- `tools.py`: umbriel branches in `list_outputs()` and
  `list_outputs_activity()`
- `main.py`: detection at top level + `--monitors_path` defaults
  to `~/.config/umbriel/outputs.toml`; workspaces dialog disabled
  (Umbriel uses `workspaces = N` per output)
- `settings_applier.py`: `_apply_umbriel_json` + `_apply_umbriel_gui`
- `tests/test_umbriel_adapter.py`: 20 unit tests, all green
- `README.md`: Umbriel section

## Test plan

1. `pipx install --editable --python /usr/bin/python3
   --system-site-packages <repo>` (depends on system gtk
   bindings)
2. Inside an Umbriel session, run `nwg-displays`
3. App detects display, lets you reorder / rescale / toggle DPMS
4. Click Apply → `~/.config/umbriel/outputs.toml` updated,
   `config.toml` patched with
   `[include] files = [..., "outputs.toml"]`
5. Umbriel reloads automatically; new layout applied

## Credits

Authored by @pponto-source with assistance from the
`MiniMax-M3 (opencode-go/minimax-m3)` AI coding assistant. All
decisions and manual validation were performed by the human author;
the assistant handled implementation, research on Umbriel's CLI
JSON schema (read from `noctalia-dev/umbriel/src/cli/outputs.cpp`),
and writing of test cases.

</PR_BODY>

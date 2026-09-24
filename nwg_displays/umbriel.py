"""Umbriel (noctalia) Wayland compositor adapter for nwg-displays.

Umbriel exposes:
  - `umbriel outputs --json`  → wlr-output-management v1 JSON array
  - `umbriel msg dpms-on[:name] | dpms-off[:name]` for power toggling
  - TOML config (~/.config/umbriel/config.toml) with file-watcher hot-reload

`save_outputs()` writes `[output."NAME"] { mode, position, scale, vrr }`
to an included file. Umbriel picks up changes via its watcher; no IPC
reload command is required (unlike niri's `load-config-file` action).

POC scope: detect, list, TOML serialize, include injection.
Workspace assignment GUI: TODO (umbriel uses `workspaces = N` per output;
mirror niri's "not available" README note).
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime

# Late import to avoid circular references; tools.py imports this module too.
def _eprint(*a, **kw):
    print(*a, file=sys.stderr, **kw)


def is_umbriel():
    """True when running inside an Umbriel session."""
    if os.getenv("UMBRIEL_SOCKET"):
        return True
    runtime = os.getenv("XDG_RUNTIME_DIR", "/run/user/" + str(os.getuid()))
    wayland = os.getenv("WAYLAND_DISPLAY", "wayland-0")
    return os.path.exists(os.path.join(runtime, f"umbriel-{wayland}.sock"))


def cli_outputs():
    """Return parsed list from `umbriel outputs --json` (or None on failure)."""
    try:
        result = subprocess.run(
            ["umbriel", "outputs", "--json"],
            capture_output=True, text=True, timeout=5,
        )
    except FileNotFoundError:
        _eprint("[umbriel] 'umbriel' CLI not on PATH")
        return None
    except Exception as e:
        _eprint(f"[umbriel] outputs query error: {e}")
        return None
    if result.returncode != 0:
        _eprint(f"[umbriel] outputs failed: {result.stderr.strip()}")
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        _eprint(f"[umbriel] JSON decode error: {e}")
        return None


def cli_dpms(name, on):
    """Toggle power on an output via `umbriel msg`."""
    action = "dpms-on" if on else "dpms-off"
    try:
        subprocess.run(
            ["umbriel", "msg", f"{action}:{name}"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception as e:
        _eprint(f"[umbriel] dpms failed for {name}: {e}")


_TRANSFORMS = {
    "normal": "normal",
    "90": "90", "180": "180", "270": "270",
    "flipped": "flipped",
    "flipped-90": "flipped-90",
    "flipped-180": "flipped-180",
    "flipped-270": "flipped-270",
}


def to_displays_dict(heads):
    """Reshape umbriel's JSON output to nwg-displays' internal dict format.

    Returned shape matches the sway/hyprland/niri branches in tools.list_outputs().
    """
    out = {}
    if not heads:
        return out
    for h in heads:
        name = h.get("name")
        if not name:
            continue
        enabled = bool(h.get("enabled"))
        modes = h.get("modes") or []
        current = next((m for m in modes if m.get("current")), modes[0] if modes else {})
        pos = h.get("position") or {}
        ps = h.get("physical_size") or {}
        adaptive = h.get("adaptive_sync")

        width = int(current.get("width", 0))
        height = int(current.get("height", 0))
        refresh_hz = float(current.get("refresh_mhz", 60000)) / 1000.0
        scale = float(h.get("scale", 1.0))
        logical_w = int(round(width / scale)) if scale else width
        logical_h = int(round(height / scale)) if scale else height

        make = h.get("make") or ""
        model = h.get("model") or ""
        serial = h.get("serial") or ""
        description = (
            " ".join(filter(None, [make, model, serial])).strip()
            or h.get("config_name")
            or name
        )

        out[name] = {
            "active": enabled,
            "dpms": enabled,  # umbriel has no separate dpms vs enabled toggle
            "description": description,
            "x": int(pos.get("x", 0)),
            "y": int(pos.get("y", 0)),
            "logical-width": logical_w,
            "logical-height": logical_h,
            "physical-width": width,
            "physical-height": height,
            "transform": _TRANSFORMS.get(h.get("transform", "normal"), "normal"),
            "scale": scale,
            "scale_filter": "linear",
            "refresh": round(refresh_hz, 2),
            "modes": [
                {
                    "width": int(m.get("width", 0)),
                    "height": int(m.get("height", 0)),
                    "refresh": float(m.get("refresh_mhz", 60000)),
                }
                for m in modes
            ],
            "focused": False,  # not exposed in --json; left False (matches niri on first read)
            "adaptive_sync_status": (
                "enabled" if adaptive else "disabled"
            ) if adaptive is not None else "disabled",
            "mirror": "",
            "ten_bit": False,
            "color_mode": "",
            "sdr_brightness": 1.0,
            "sdr_saturation": 1.0,
            "monitor": None,
            # extras preserved for matching/--use-desc
            "__umbriel_make": make,
            "__umbriel_model": model,
            "__umbriel_serial": serial,
            "__umbriel_config_name": h.get("config_name") or "",
            "__umbriel_size_mm": (
                int(ps.get("width_mm", 0)),
                int(ps.get("height_mm", 0)),
            ),
        }
    return out


# ── TOML serializer ────────────────────────────────────────────────────────
# Hand-rolled formatter: avoids adding tomli_w dep. Only emits flat
# [output."NAME"] tables; the supported key set is small and stable.

def _toml_value(v):
    """Render a TOML scalar/array value."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        # Always render as float to keep semantics (1 vs 1.0 round-trip).
        if v != v:  # NaN guard
            return "nan"
        if v == float("inf"):
            return "inf"
        # Round-trip-preserving: trim excess precision, but keep at least one decimal.
        s = f"{v:.6f}".rstrip("0").rstrip(".")
        if "." not in s:
            s = s + ".0"
        return s
    if isinstance(v, str):
        return json.dumps(v)  # always emits double-quoted, escapes correctly
    if isinstance(v, list):
        if not v:
            return "[]"
        if all(isinstance(x, (int, float)) for x in v):
            return "[" + ", ".join(str(x) if isinstance(x, int) else _toml_value(x)
                                   for x in v) + "]"
        if all(isinstance(x, str) for x in v):
            return "[" + ", ".join(json.dumps(x) for x in v) + "]"
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    return json.dumps(str(v))


def _entry_key(name, use_desc, override=None):
    """Render the TOML table key for an output.

    use_desc=True yields [output."Make Model Serial"], else [output."DP-1"].
    """
    label = override if override else name
    return f'output.{json.dumps(label)}'


def save_outputs(displays, use_desc, path):
    """Write a TOML file Umbriel can hot-reload.

    `displays` follows the niri/KDL schema:
        {name, active, physical_width, physical_height, refresh, x, y,
         scale, transform, adaptive_sync, description}
    """
    now = datetime.now()
    header = (
        f"# Generated by nwg-displays on "
        f"{now.strftime('%Y-%m-%d')} at "
        f"{now.strftime('%H:%M:%S')}. Do not edit manually.\n\n"
    )
    blocks = []
    for d in displays:
        key = _entry_key(
            d["name"], use_desc,
            override=d.get("description") if use_desc else None,
        )
        fields = {}
        if not d.get("active", True):
            fields["enabled"] = False
        else:
            fields["mode"] = (
                f'{d["physical_width"]}x{d["physical_height"]}'
                f'@{float(d["refresh"]):.3f}'
            )
            fields["position"] = [int(d["x"]), int(d["y"])]
            fields["scale"] = float(d["scale"])
            t = d.get("transform", "normal")
            if t != "normal":
                fields["transform"] = t
            if d.get("adaptive_sync"):
                fields["vrr"] = "fullscreen"
        lines = [f"[{key}]"]
        for k, v in fields.items():
            lines.append(f"{k} = {_toml_value(v)}")
        blocks.append("\n".join(lines))

    with open(path, "w") as f:
        f.write(header + "\n\n".join(blocks) + "\n")


# ── Include injection ──────────────────────────────────────────────────────

def ensure_include(config_path, included_filename="outputs.toml"):
    """Idempotently ensure `[include] files` lists `included_filename`.

    Walks text directly to preserve user comments and unrelated sections.
    """
    if not os.path.isfile(config_path):
        with open(config_path, "w") as f:
            f.write(f'[include]\nfiles = ["{included_filename}"]\n')
        _eprint(f"[umbriel] created {config_path} with [include]")
        return

    text = open(config_path).read()

    # Already present? bail.
    needle = f'"{included_filename}"'
    if needle in text:
        return

    # Look for an [include] section (start of line, until next [section] or EOF).
    section_re = re.compile(
        r"^\[include\]\s*\n((?:^[^\[].*\n?)*)", re.MULTILINE
    )
    m = section_re.search(text)
    if m:
        block = m.group(1)
        files_m = re.search(r"^files\s*=\s*\[(.*?)\]\s*$", block, re.MULTILINE | re.DOTALL)
        if files_m:
            inner = files_m.group(1).strip()
            sep = ", " if inner else ""
            new_inner = (inner.rstrip(",") + sep + f'"{included_filename}"').strip()
            new_files_line = f"files = [{new_inner}]"
            new_block = block.replace(files_m.group(0), new_files_line) + (
                "" if block.endswith("\n") else "\n"
            )
            text = text[:m.start(1)] + new_block + text[m.end(1):]
        else:
            # [include] without files — append files line
            insert = f'files = ["{included_filename}"]\n'
            text = text[:m.end(1)] + insert + text[m.end(1):]
    else:
        text = text.rstrip() + f'\n\n[include]\nfiles = ["{included_filename}"]\n'

    with open(config_path, "w") as f:
        f.write(text)
    _eprint(f"[umbriel] added {included_filename} to [include] in {config_path}")


def config_dir():
    """Return umbriel's config directory (XDG-aware)."""
    base = os.getenv("XDG_CONFIG_HOME") or os.path.join(
        os.path.expanduser("~"), ".config"
    )
    return os.path.join(base, "umbriel")

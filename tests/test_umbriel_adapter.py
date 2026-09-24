"""Smoke tests for the umbriel adapter (pure-Python, no GTK/i3ipc).

Run: python3 tests/test_umbriel_adapter.py
"""

import json
import os
import sys
import tempfile
import unittest

# Run from project root OR set PYTHONPATH
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from nwg_displays import umbriel  # noqa: E402


SAMPLE_HEADS = [
    {
        "name": "DP-1",
        "description": "Microstep MSI G2712F",
        "make": "Microstep",
        "model": "MSI G2712F",
        "serial": "CD6T084401192",
        "config_name": "Microstep MSI G2712F CD6T084401192",
        "physical_size": {"width_mm": 600, "height_mm": 340},
        "enabled": True,
        "position": {"x": 0, "y": 0},
        "transform": "normal",
        "scale": 1.0,
        "adaptive_sync": True,
        "modes": [
            {"width": 1920, "height": 1080, "refresh_mhz": 180000,
             "preferred": True, "current": True},
            {"width": 1280, "height": 720, "refresh_mhz": 60000,
             "preferred": False, "current": False},
        ],
    },
    {
        "name": "HDMI-A-1",
        "description": "AOC 2475WR",
        "make": "AOC",
        "model": "2475WR",
        "serial": "F17H4QA000449",
        "config_name": "AOC 2475WR F17H4QA000449",
        "physical_size": {"width_mm": 530, "height_mm": 300},
        "enabled": False,
        "position": {"x": 1920, "y": 0},
        "transform": "90",
        "scale": 1.25,
        "adaptive_sync": None,
        "modes": [
            {"width": 1920, "height": 1080, "refresh_mhz": 60000,
             "preferred": True, "current": False},
        ],
    },
]


SAMPLE_DISPLAYS = [
    {
        "name": "DP-1",
        "active": True,
        "physical_width": 1920,
        "physical_height": 1080,
        "refresh": 180.0,
        "x": 0,
        "y": 0,
        "scale": 1.0,
        "transform": "normal",
        "adaptive_sync": True,
        "description": "Microstep MSI G2712F CD6T084401192",
    },
    {
        "name": "HDMI-A-1",
        "active": False,
        "physical_width": 1920,
        "physical_height": 1080,
        "refresh": 60.0,
        "x": 0,
        "y": 0,
        "scale": 1.25,
        "transform": "normal",
        "adaptive_sync": False,
        "description": "",
    },
]


class TestToDisplaysDict(unittest.TestCase):
    def test_basic_shape(self):
        d = umbriel.to_displays_dict(SAMPLE_HEADS)
        self.assertEqual(set(d.keys()), {"DP-1", "HDMI-A-1"})
        self.assertTrue(d["DP-1"]["active"])
        self.assertFalse(d["HDMI-A-1"]["active"])
        self.assertEqual(d["DP-1"]["physical-width"], 1920)
        self.assertEqual(d["DP-1"]["physical-height"], 1080)
        self.assertEqual(d["DP-1"]["refresh"], 180.0)
        self.assertEqual(d["DP-1"]["scale"], 1.0)
        self.assertEqual(d["DP-1"]["transform"], "normal")
        self.assertEqual(d["DP-1"]["adaptive_sync_status"], "enabled")
        self.assertEqual(d["HDMI-A-1"]["adaptive_sync_status"], "disabled")
        self.assertEqual(d["HDMI-A-1"]["transform"], "90")
        self.assertEqual(d["HDMI-A-1"]["logical-width"], 1536)
        self.assertEqual(d["HDMI-A-1"]["logical-height"], 864)
        self.assertEqual(len(d["DP-1"]["modes"]), 2)

    def test_empty_input(self):
        self.assertEqual(umbriel.to_displays_dict([]), {})
        self.assertEqual(umbriel.to_displays_dict(None), {})

    def test_skips_headless(self):
        self.assertNotIn("missing", umbriel.to_displays_dict([{"name": ""}]))


class TestSaveOutputs(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_active_output(self):
        path = os.path.join(self.tmpdir, "outputs.toml")
        umbriel.save_outputs([SAMPLE_DISPLAYS[0]], use_desc=False, path=path)
        text = open(path).read()
        self.assertIn("[output.\"DP-1\"]", text)
        self.assertIn('mode = "1920x1080@180.000"', text)
        self.assertIn("position = [0, 0]", text)
        self.assertIn("scale = 1.0", text)
        self.assertIn("vrr = \"fullscreen\"", text)
        # no transform line for normal
        self.assertNotIn("transform", text)

    def test_use_desc_uses_config_name(self):
        path = os.path.join(self.tmpdir, "outputs.toml")
        umbriel.save_outputs(
            [SAMPLE_DISPLAYS[0]], use_desc=True, path=path
        )
        text = open(path).read()
        self.assertIn("[output.\"Microstep MSI G2712F CD6T084401192\"]", text)
        self.assertNotIn("[output.\"DP-1\"]", text)

    def test_disabled_output(self):
        path = os.path.join(self.tmpdir, "outputs.toml")
        umbriel.save_outputs([SAMPLE_DISPLAYS[1]], use_desc=False, path=path)
        text = open(path).read()
        self.assertIn("[output.\"HDMI-A-1\"]", text)
        self.assertIn("enabled = false", text)
        self.assertNotIn("position", text)

    def test_transform_emitted(self):
        path = os.path.join(self.tmpdir, "outputs.toml")
        disp = dict(SAMPLE_DISPLAYS[0], transform="90")
        umbriel.save_outputs([disp], use_desc=False, path=path)
        text = open(path).read()
        self.assertIn('transform = "90"', text)

    def test_escapes_quotes_in_description(self):
        path = os.path.join(self.tmpdir, "outputs.toml")
        disp = dict(
            SAMPLE_DISPLAYS[0], description='Brand "ACME" Display 9000'
        )
        umbriel.save_outputs([disp], use_desc=True, path=path)
        text = open(path).read()
        self.assertIn(r'"Brand \"ACME\" Display 9000"', text)


class TestEnsureInclude(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_creates_when_missing(self):
        cfg = os.path.join(self.tmpdir, "config.toml")
        umbriel.ensure_include(cfg, "outputs.toml")
        text = open(cfg).read()
        self.assertIn("[include]", text)
        self.assertIn("outputs.toml", text)

    def test_appends_when_no_section(self):
        cfg = os.path.join(self.tmpdir, "config.toml")
        open(cfg, "w").write(
            "[general]\nmod_key = \"Super\"\n[appearance.blur]\n"
            "radius = 3\n"
        )
        umbriel.ensure_include(cfg, "outputs.toml")
        text = open(cfg).read()
        self.assertIn("[general]", text)
        self.assertIn("mod_key", text)
        self.assertIn("[appearance.blur]", text)
        self.assertIn("radius = 3", text)
        self.assertIn("[include]", text)
        self.assertIn("outputs.toml", text)

    def test_idempotent(self):
        cfg = os.path.join(self.tmpdir, "config.toml")
        umbriel.ensure_include(cfg, "outputs.toml")
        first = open(cfg).read()
        umbriel.ensure_include(cfg, "outputs.toml")
        second = open(cfg).read()
        self.assertEqual(first, second)

    def test_appends_to_existing_files_list(self):
        cfg = os.path.join(self.tmpdir, "config.toml")
        open(cfg, "w").write(
            "[include]\nfiles = [\"keybinds.toml\"]\n"
        )
        umbriel.ensure_include(cfg, "outputs.toml")
        text = open(cfg).read()
        self.assertIn("keybinds.toml", text)
        self.assertIn("outputs.toml", text)
        # exactly one of each
        self.assertEqual(text.count("keybinds.toml"), 1)

    def test_appends_when_section_exists_without_files(self):
        cfg = os.path.join(self.tmpdir, "config.toml")
        open(cfg, "w").write(
            "[include]\n"
            "[general]\nmod_key = \"Super\"\n"
        )
        umbriel.ensure_include(cfg, "outputs.toml")
        text = open(cfg).read()
        self.assertIn("[include]", text)
        self.assertIn("[general]", text)
        self.assertIn("outputs.toml", text)


class TestIsUmbriel(unittest.TestCase):
    def test_socket_env_var(self):
        old = os.environ.get("UMBRIEL_SOCKET")
        os.environ["UMBRIEL_SOCKET"] = "/tmp/fake.sock"
        try:
            self.assertTrue(umbriel.is_umbriel())
        finally:
            if old is None:
                os.environ.pop("UMBRIEL_SOCKET", None)
            else:
                os.environ["UMBRIEL_SOCKET"] = old

    def test_no_env(self):
        old = os.environ.pop("UMBRIEL_SOCKET", None)
        old_wayland = os.environ.get("WAYLAND_DISPLAY")
        os.environ["WAYLAND_DISPLAY"] = "wayland-99"
        os.environ["XDG_RUNTIME_DIR"] = "/nonexistent-xyz"
        try:
            self.assertFalse(umbriel.is_umbriel())
        finally:
            if old is not None:
                os.environ["UMBRIEL_SOCKET"] = old
            if old_wayland is None:
                os.environ.pop("WAYLAND_DISPLAY", None)
            else:
                os.environ["WAYLAND_DISPLAY"] = old_wayland


if __name__ == "__main__":
    unittest.main(verbosity=2)

import importlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class HyprlandWorkspacePathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.hypr_dir = Path(cls.directory.name) / "hypr"
        cls.hypr_dir.mkdir()
        environment = dict(os.environ)
        environment.pop("SWAYSOCK", None)
        environment.pop("NIRI_SOCKET", None)
        environment.update(XDG_CONFIG_HOME=cls.directory.name,
                           HYPRLAND_INSTANCE_SIGNATURE="workspace-path-test")
        with patch.dict(os.environ, environment, clear=True):
            cls.main = importlib.import_module("nwg_displays.main")
        if not cls.main.Gtk.init_check()[0]:
            raise unittest.SkipTest("A display is required for the GTK workspace dialog")

    def setUp(self):
        self.main.hypr_config_dir = str(self.hypr_dir)
        self.main.num_ws = 2
        self.main.config = {"use-desc": False}
        self.main.voc = {"apply": "Apply", "close": "Close"}
        self.main.outputs = {"HDMI-A-1": {}, "DP-1": {}}
        self.canonical = self.hypr_dir / "workspaces.conf"
        self.custom = self.hypr_dir / "custom-workspaces.conf"
        self.canonical.write_text("workspace=1,monitor:HDMI-A-1\n")
        self.custom.write_text("workspace=1,monitor:DP-1\nworkspace=2,monitor:HDMI-A-1\n")

    def tearDown(self):
        if self.main.dialog_win:
            self.main.dialog_win.destroy()
            self.main.dialog_win = None

    def test_custom_path_overrides_canonical_assignments(self):
        self.main.workspaces_path = str(self.custom)
        self.main.create_workspaces_window_hypr(None)
        self.assertEqual(self.main.workspaces, {1: "DP-1", 2: "HDMI-A-1"})

    def test_default_path_keeps_canonical_assignments(self):
        self.main.workspaces_path = str(self.canonical)
        self.main.create_workspaces_window_hypr(None)
        self.assertEqual(self.main.workspaces, {1: "HDMI-A-1"})

    def test_workspace_limit_applies_to_custom_path(self):
        self.main.workspaces_path = str(self.custom)
        self.main.num_ws = 1
        self.main.create_workspaces_window_hypr(None)
        self.assertEqual(self.main.workspaces, {1: "DP-1"})

    def test_apply_and_reopen_reads_custom_file(self):
        self.main.workspaces_path = str(self.custom)
        self.main.create_workspaces_window_hypr(None)
        old = self.main.workspaces.copy()
        self.main.workspaces = {1: "HDMI-A-1", 2: "DP-1"}
        with patch.object(self.main, "notify"):
            self.main.on_workspaces_apply_btn_hypr(None, self.main.dialog_win, old)
        self.main.create_workspaces_window_hypr(None)
        self.assertEqual(self.main.workspaces, {1: "HDMI-A-1", 2: "DP-1"})
        self.assertEqual(self.canonical.read_text(), "workspace=1,monitor:HDMI-A-1\n")
        self.assertIn('workspace = "2"', self.custom.with_suffix(".lua").read_text())


if __name__ == "__main__":
    unittest.main()

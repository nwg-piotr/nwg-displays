import json
import os
import unittest
from unittest.mock import Mock, patch

from nwg_displays.tools import list_outputs


class EmptyDisplay:
    def get_n_monitors(self):
        return 0


class NiriOutputsTest(unittest.TestCase):
    @patch("nwg_displays.tools.Gdk.Display.get_default", return_value=EmptyDisplay())
    @patch("nwg_displays.tools.subprocess.run")
    def test_disabled_output_with_null_current_mode(self, run, _get_default):
        run.return_value = Mock(
            stdout=json.dumps(
                {
                    "eDP-1": {
                        "name": "eDP-1",
                        "make": "LG Display",
                        "model": "0x07BF",
                        "serial": "0x0000FFA1",
                        "physical_size": [300, 190],
                        "modes": [
                            {
                                "width": 1920,
                                "height": 1200,
                                "refresh_rate": 60001,
                                "is_preferred": True,
                            }
                        ],
                        "current_mode": None,
                        "vrr_supported": True,
                        "vrr_enabled": False,
                        "logical": None,
                    }
                }
            )
        )

        with patch.dict(os.environ, {"NIRI_SOCKET": "/tmp/niri.sock"}, clear=False):
            outputs = list_outputs()

        output = outputs["eDP-1"]
        self.assertFalse(output["active"])
        self.assertFalse(output["dpms"])
        self.assertEqual(output["physical-width"], 1920)
        self.assertEqual(output["physical-height"], 1200)
        self.assertEqual(output["refresh"], 60.001)
        self.assertEqual(output["logical-width"], 0)
        self.assertEqual(output["logical-height"], 0)


if __name__ == "__main__":
    unittest.main()

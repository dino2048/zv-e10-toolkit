#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))

import zve10_usb_stream_probe as probe  # noqa: E402


class UsbStreamProbeTests(unittest.TestCase):
    def test_parses_only_zve10_video_nodes(self):
        listing = """Other Camera (usb-x):
\t/dev/video0

ZV-E10 (usb-y):
\t/dev/video4
\t/dev/video5

Loopback (platform:z):
\t/dev/video10
"""
        self.assertEqual(probe.parse_video_nodes(listing), ["/dev/video4", "/dev/video5"])

    def test_selects_mjpeg_capture_not_metadata(self):
        formats = {
            "/dev/video4": "[0]: 'MJPG'\nSize: Discrete 1280x720\nInterval: Discrete 0.033s (30.000 fps)",
            "/dev/video5": "Type: Metadata Capture",
        }
        self.assertEqual(
            probe.select_mjpeg_node(["/dev/video4", "/dev/video5"], formats),
            "/dev/video4",
        )

    def test_parses_audio_card_without_serial(self):
        output = "card 7: ZVE10 [ZV-E10], device 0: USB Audio [USB Audio]\n"
        self.assertEqual(probe.parse_audio_card(output), 7)

    def test_uses_final_ffmpeg_frame_count(self):
        output = "frame= 15 fps=30\rframe= 149 fps=30\n"
        self.assertEqual(probe.parse_frame_count(output), 149)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Validate ZV-E10 USB Streaming without exposing its USB serial number."""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path


STREAM_USB_ID = "054c:0de3"


def run(command: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def parse_video_nodes(output: str) -> list[str]:
    nodes: list[str] = []
    in_camera = False
    for line in output.splitlines():
        if line and not line[0].isspace():
            in_camera = line.startswith("ZV-E10 ") or line == "ZV-E10:"
            continue
        value = line.strip()
        if in_camera and value.startswith("/dev/video"):
            nodes.append(value)
    return nodes


def select_mjpeg_node(nodes: list[str], formats: dict[str, str]) -> str | None:
    for node in nodes:
        output = formats.get(node, "")
        if "'MJPG'" in output and "1280x720" in output and "30.000 fps" in output:
            return node
    return None


def parse_audio_card(output: str) -> int | None:
    match = re.search(r"^card\s+(\d+):\s+ZVE10\b", output, flags=re.MULTILINE)
    return int(match.group(1)) if match else None


def parse_frame_count(output: str) -> int:
    matches = re.findall(r"frame=\s*(\d+)", output)
    return int(matches[-1]) if matches else 0


def require_commands(names: tuple[str, ...]) -> None:
    missing = [name for name in names if shutil.which(name) is None]
    if missing:
        raise RuntimeError("missing host commands: " + ", ".join(missing))


def probe(duration: int) -> dict[str, object]:
    require_commands(("lsusb", "v4l2-ctl", "arecord", "ffmpeg"))

    usb = run(["lsusb", "-d", STREAM_USB_ID + ":"])
    if usb.returncode != 0 or STREAM_USB_ID not in usb.stdout.lower():
        raise RuntimeError(
            "ZV-E10 USB Streaming device 054c:0de3 not found; start USB Streaming "
            "on the disconnected camera, then connect the cable"
        )

    listing = run(["v4l2-ctl", "--list-devices"])
    nodes = parse_video_nodes(listing.stdout)
    formats: dict[str, str] = {}
    for node in nodes:
        result = run(["v4l2-ctl", "-d", node, "--list-formats-ext"])
        if result.returncode == 0:
            formats[node] = result.stdout
    video = select_mjpeg_node(nodes, formats)
    if video is None:
        raise RuntimeError("Sony UVC node with MJPEG 1280x720 at 30 fps not found")

    cards = run(["arecord", "-l"])
    card = parse_audio_card(cards.stdout)
    if card is None:
        raise RuntimeError("Sony USB Audio capture card not found")
    audio_device = "hw:%d,0" % card

    audio = run(
        [
            "arecord", "-q", "-D", audio_device, "-d", str(duration),
            "-f", "S16_LE", "-r", "48000", "-c", "2", "/dev/null",
        ],
        timeout=duration + 10,
    )
    if audio.returncode != 0:
        raise RuntimeError("Sony USB Audio capture failed: " + audio.stderr.strip())

    video_run = run(
        [
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "info",
            "-f", "v4l2", "-input_format", "mjpeg", "-video_size", "1280x720",
            "-framerate", "30", "-i", video, "-t", str(duration), "-an",
            "-f", "null", "-",
        ],
        timeout=duration + 15,
    )
    frames = parse_frame_count(video_run.stderr)
    minimum = int(duration * 30 * 0.95)
    if video_run.returncode != 0 or frames < minimum:
        raise RuntimeError(
            "Sony UVC delivery failed: %d frames, expected at least %d" %
            (frames, minimum)
        )

    obs_version = None
    if shutil.which("obs"):
        obs = run(["obs", "--version"])
        if obs.returncode == 0:
            obs_version = obs.stdout.strip()

    return {
        "usb_id": STREAM_USB_ID,
        "video_device": video,
        "video_format": "MJPEG 1280x720 30 fps",
        "frames": frames,
        "duration_seconds": duration,
        "audio_device": audio_device,
        "audio_format": "PCM S16_LE 2ch 48000 Hz",
        "obs_version": obs_version,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--duration", type=int, default=5,
        help="seconds to validate each null-sink capture (1-60; default: 5)",
    )
    args = parser.parse_args()
    if not 1 <= args.duration <= 60:
        parser.error("--duration must be between 1 and 60")

    try:
        result = probe(args.duration)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        raise SystemExit("FAIL: " + str(exc)) from exc

    print("PASS USB: " + str(result["usb_id"]))
    print(
        "PASS video: %(video_device)s %(video_format)s, %(frames)s frames/%(duration_seconds)ss"
        % result
    )
    print("PASS audio: %(audio_device)s %(audio_format)s" % result)
    if result["obs_version"]:
        print("OBS available: " + str(result["obs_version"]))
    print("No camera serial, frames, or audio were saved.")


if __name__ == "__main__":
    main()

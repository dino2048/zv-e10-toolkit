# USB Streaming

[简体中文](usb-streaming.zh-CN.md)

The original ZV-E10 exposes USB Streaming separately from **USB Connection**.
The latter contains only Auto, Mass Storage and MTP.

## Start the official mode

1. Disconnect the USB cable.
2. Switch the camera to movie mode and choose the desired focus and exposure.
3. Select **MENU → Camera Settings2 → USB Streaming**.
4. Reconnect the cable when the display reports `USB Streaming: Not Connect`.

Sony documents 1280×720 MJPEG at 30 or 25 fps and stereo PCM audio at 48 kHz,
16 bit. Recording, menu access, playback, PC Remote and smartphone connection
are unavailable while streaming. See the
[official ZV-E10 Help Guide](https://helpguide.sony.net/ilc/2070/v1/en/contents/TP1000201566.html).

## Serial-safe host validation

On Linux, run:

```sh
./scripts/probe_usb_streaming.sh --duration 10
```

The probe requires `lsusb`, `v4l2-ctl`, `arecord` and `ffmpeg`. It confirms the
streaming USB identity, selects the MJPEG capture node, captures video and audio
to null sinks, and reports the delivered frame count. It does not print the
camera serial or save frames or audio. Avoid publishing unfiltered
`v4l2-ctl --all`, `pactl` or udev output because those can contain the serial.

## Validated Linux result

Firmware `30110_05.2025031501` was validated over the same regular USB-C cable
used for service access:

- USB identity `054c:0de3` at USB 2 high speed;
- UVC MJPEG, 1280×720, 30 fps;
- 299 frames delivered during a 10-second null-sink test with no transport
  error;
- USB Audio PCM, signed 16-bit little-endian, two channels, 48 kHz;
- OBS Studio 33 detected on the host; the UVC and ALSA devices are directly
  usable as Video Capture Device and Audio Input Capture sources.

This test proves host delivery, not glass-to-glass latency. Measuring latency
requires the camera to view a changing reference clock and comparing that clock
with the received frame.

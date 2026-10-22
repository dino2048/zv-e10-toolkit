# Service mode

The toolkit talks to the camera through Sony's service mode ("Senser"
protocol), implemented by Sony-PMCA-RE. This page describes what the host
does and what the camera experiences.

## Prerequisites

- Camera connected by USB and set to **mass storage** (not auto, not MTP).
- The camera enumerates as `054c:0d95` in mass-storage mode.
- On macOS, the host process needs raw USB access: run the launchers, which
  use one administrator popup via `osascript` + `launchctl asuser`.
- `libusb` must be available. `zve10_common` prefers `LIBUSB_PATH`, then the
  Homebrew locations, before falling back to the system lookup.

## Flow

1. **StartSenser** — a vendor request is sent to the mass-storage device
   (`SONY_VendorRequest_StartSenser`).
2. **Re-enumeration** — the camera leaves mass-storage mode and appears as a
   Senser device (`054c:0336`).
3. **Authentication** — challenge/response implemented by
   `SonySenserAuthDevice.authenticate()` in PMCA-RE.
4. **Callback** — the tool receives a `SonySenserCamera` object and issues its
   fixed read-only requests.
5. **StopSenser** — on exit, PMCA-RE sends the stop request. The camera
   returns to mass-storage mode; this may take a few seconds. If it does not
   reappear, unplug and reconnect the USB cable.

## Side effects

- Service authentication itself may update `/setting/.etools` and
  `/setting/.hasp` on the camera. This toolkit does not perform those writes;
  they are part of the vendor authentication path.
- No files are uploaded, no mount is created by this toolkit, and no block
  device is written.
- The service session is transient. It does not install anything persistent.

## What authentication buys

The authenticated session exposes Sony's service functions: product info,
adjust control, file control, memory dump, and a debug terminal. The tools in
this repository use only:

- FileControl READ (pFunc `0xff01`) to read `/version.txt` and block-device
  nodes;
- the service terminal for fixed metadata commands and (optionally) an
  owner-authorized shell.

## Boundaries

- Service mode requires the camera firmware to boot far enough to accept the
  session. It is not a BootROM path and cannot help a camera that fails early
  in boot.
- The protocol is undocumented and version-dependent. Only firmware
  `30110_05.2025031501` on the ZV-E10 is tested here.

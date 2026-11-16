# Service mode

For 2.03, use [the Jiritsu backend](jiritsu.md). The legacy terminal/FileControl procedure below remains the 2.02 route.

The toolkit uses Sony's service mode ("Senser" protocol), implemented by
Sony-PMCA-RE.

## Prerequisites

- Camera in **USB mass storage** mode (not auto, not MTP); it enumerates as
  `054c:0d95`.
- macOS: raw USB access, granted by the launchers through one administrator
  popup (`osascript` + `launchctl asuser`).
- Linux: raw USB access, granted by the launchers through `pkexec`, or through
  `sudo` when polkit is unavailable. The same privileged process remains active
  while the camera re-enumerates in service mode.
- Windows: a `libusb-win32` driver for both camera identities (`054c:0d95` and
  `054c:0336`), installed with Zadig. The validated read-only session ran in a
  normal, non-elevated PowerShell; use an elevated one only if opening the
  device reports access denied. Run `host/zve10_terminal_server.py` directly;
  the `.sh` launchers are macOS/Linux-only.
- `libusb`. `zve10_common` checks `LIBUSB_PATH`, then Homebrew's locations,
  before falling back to the system lookup.

## Flow

1. **StartSenser** — a vendor request is sent to the mass-storage device.
2. **Re-enumeration** — the camera appears as a Senser device (`054c:0336`).
3. **Authentication** — challenge/response in
   `SonySenserAuthDevice.authenticate()` (PMCA-RE).
4. **Callback** — the tool receives a `SonySenserCamera` and issues its fixed
   read-only requests.
5. **StopSenser** — on exit PMCA-RE sends the stop request. The camera returns
   to mass-storage mode; if it does not reappear, replug USB.

## Side effects

Service authentication itself may update `/setting/.etools` and
`/setting/.hasp`. The toolkit does not perform those writes. It does not upload
files, create mounts, or write block devices, and ordinary one-shot callbacks end the service connection when they return. The terminal server keeps its callback open until close/timeout; structured Backup actions can write settings only with explicit write mode. See [Backup properties](backup-properties.md).

## Boundaries

- Requires firmware that boots far enough to accept a service session. It is
  not a BootROM path.
- The protocol is undocumented and version-dependent. Only
  `30110_05.2025031501` on the ZV-E10 is tested.

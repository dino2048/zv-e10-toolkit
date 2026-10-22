# Service mode

The toolkit uses Sony's service mode ("Senser" protocol), implemented by
Sony-PMCA-RE.

## Prerequisites

- Camera in **USB mass storage** mode (not auto, not MTP); it enumerates as
  `054c:0d95`.
- macOS: raw USB access, granted by the launchers through one administrator
  popup (`osascript` + `launchctl asuser`).
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
files, create mounts, or write block devices, and the session is not persistent.

## Boundaries

- Requires firmware that boots far enough to accept a service session. It is
  not a BootROM path.
- The protocol is undocumented and version-dependent. Only
  `30110_05.2025031501` on the ZV-E10 is tested.

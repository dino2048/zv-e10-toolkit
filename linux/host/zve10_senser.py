"""Length-delimited reading of Sony service (senser) responses.

Sony-PMCA-RE's stock reader (``pmca.usb.sony.SonySenserDevice``) issues an extra
512-byte read after every 32 KiB response chunk whose length is a multiple of
512 and discards whatever comes back.  The ZV-E10 ends such a chunk with an
empty transfer: the extra read returns immediately on macOS, but the first
Windows session (2026-11-16, libusb-win32 driver) blocked in it and the whole
service channel failed at the first 32 KiB of a 17.7 MB GET_FILE.

This transport reads exactly the length declared in each response header, skips
zero-length transfers, and rejects a reply whose sequence number or function
code does not match the request.  A failed exchange disables the channel, so a
desynchronised stream is never used for a following request.

The behaviour was cross-checked against the public A7C2 FL2/FL3 research
(https://github.com/QAQLeonard/a7c2-tools, PolyForm Noncommercial 1.0.0).
That project is not MIT-licensed, so this module is an independent
implementation written against the Sony-PMCA-RE class above and contains no
code from it.  The selection policy keeps the vendor
reader on POSIX hosts, whose camera-tested throughput record uses it, and
switches to this reader on Windows.  ``ZVE10_SENSER_FRAMING=length`` or
``stock`` overrides the choice for a controlled test.

This module only changes how responses are framed on the host.  It sends no
camera command of its own.
"""
from __future__ import annotations

import os
import sys
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor" / "Sony-PMCA-RE"
if VENDOR.is_dir() and str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

from pmca.usb.sony import SonySenserDevice as StockSenserDevice

CHOICES = ("auto", "stock", "length")


class LengthDelimitedSenserDevice(StockSenserDevice):
    """Read the declared response length; never discard a trailing packet."""

    def __init__(self, driver):
        super().__init__(driver)
        self._failed = False

    def _read_nonempty(self, length):
        """Return between 1 and ``length`` bytes, ignoring empty transfers."""
        while True:
            data = self.driver.read(length)
            if data:
                return data

    def _read_all(self, length):
        parts, done = [], 0
        while done < length:
            data = self._read_nonempty(length - done)
            if len(data) > length - done:
                raise RuntimeError("Senser reply exceeds the requested length")
            parts.append(data)
            done += len(data)
        return b"".join(parts)

    def sendSenserPacket(self, pFunc, data, oData=None):
        if self._failed:
            raise RuntimeError("Senser channel unusable after a failed exchange")
        try:
            return self._exchange(pFunc, data, oData)
        except BaseException:
            self._failed = True
            raise

    def _exchange(self, pFunc, data, oData):
        while data != b"":
            header = self.SenserPacketHeader.pack(
                size=len(data), pFunc=pFunc, sequence=self._sequence,
                version=0, miconType=0, offsetType=0, response=0)
            self.driver.write(header + data[:self.SenserMaxSize])
            data = data[self.SenserMaxSize:]

        out = BytesIO() if oData is None else oData
        # 0x0336 is the service-mode endpoint: replies are not padded to 512
        # bytes there, so the header arrives alone.
        min_size = 0 if self.driver.getId()[1] == 0x0336 else self.SenserMinSize
        while True:
            padding = max(min_size - self.SenserPacketHeader.size, 0)
            want = self.SenserPacketHeader.size + padding
            head = self._read_nonempty(want)
            if len(head) < want:
                raise RuntimeError("Short Senser header: %d of %d bytes" % (len(head), want))
            reply = self.SenserPacketHeader.unpack(head)
            if reply.sequence != self._sequence or reply.pFunc != pFunc:
                raise RuntimeError(
                    "Wrong Senser reply: expected sequence %d/function %#x, "
                    "got %d/%#x" % (self._sequence, pFunc, reply.sequence, reply.pFunc))
            out.write(head[self.SenserPacketHeader.size:])
            done = padding
            data_len = min(reply.size, self.SenserMaxSize)
            chunk = self.SenserChunkSize - min_size
            while done < data_len:
                take = min(data_len - done, chunk)
                out.write(self._read_all(take))
                done += take
                chunk = self.SenserChunkSize
            if reply.size <= self.SenserMaxSize:
                break
        self._sequence += 1
        return reply.response, out.getvalue() if oData is None else None


def choice(value=None):
    """Resolve ``auto``/``stock``/``length`` without touching the driver."""
    selected = (value or os.environ.get("ZVE10_SENSER_FRAMING") or "auto").strip().lower()
    if selected not in CHOICES:
        raise ValueError("ZVE10_SENSER_FRAMING must be one of: " + ", ".join(CHOICES))
    if selected == "auto":
        return "length" if os.name == "nt" else "stock"
    return selected


def install(value=None):
    """Select the reader for the camera factory; return True if patched.

    ``pmca.commands.usb`` builds every service device from its module-level
    ``SonySenserDevice`` name and also uses it for ``isinstance`` checks, so
    replacing that name covers detection and construction at once.
    """
    from pmca.commands import usb as pmca_usb
    if choice(value) == "stock":
        if pmca_usb.SonySenserDevice is LengthDelimitedSenserDevice:
            pmca_usb.SonySenserDevice = StockSenserDevice
        return False
    if pmca_usb.SonySenserDevice is not LengthDelimitedSenserDevice:
        pmca_usb.SonySenserDevice = LengthDelimitedSenserDevice
    return True

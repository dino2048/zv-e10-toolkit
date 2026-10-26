"""Release payload integrity and capability checks require no hardware or ELF."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / 'tools'))
import check_abi


class ReleaseTests(unittest.TestCase):
    def test_pinned_stage1(self):
        self.assertEqual(len(check_abi.verify()), 8028)

    def test_release_stage2_capability(self):
        blob = (check_abi.PREBUILT / 'stage2-flash.bin').read_bytes()
        self.assertEqual(check_abi.verify_stage2(blob, allow_writer=True),
                         check_abi.RELEASE['stage2-flash.bin']['identity'])

    def test_writer_requires_opt_in(self):
        blob = (check_abi.PREBUILT / 'stage2-flash.bin').read_bytes()
        with self.assertRaisesRegex(ValueError, 'explicit write'):
            check_abi.verify_stage2(blob)

    def test_corrupted_payload_is_not_accepted_as_release(self):
        blob = bytearray((check_abi.PREBUILT / 'stage2-flash.bin').read_bytes())
        blob[0] ^= 1
        with self.assertRaisesRegex(ValueError, 'not a published payload'):
            check_abi.verify_stage2(bytes(blob), ROOT / 'missing.elf')


if __name__ == '__main__':
    unittest.main()

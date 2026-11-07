import sys
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "host"))

import zve10_bootrom_dump as bootrom_dump  # noqa: E402


class HelperTmpfsTest(unittest.TestCase):
    def test_accepts_selected_tmpfs_mount(self):
        result = {
            "exit_code": 0,
            "output": "none /tmp_network tmpfs rw,size=1024k 0 0\r\n",
        }
        with mock.patch.object(bootrom_dump, "shell", return_value=result):
            bootrom_dump.check_mounts(object(), "/tmp_network")

    def test_rejects_non_tmpfs_mount(self):
        result = {
            "exit_code": 0,
            "output": "/dev/nflasha10 /tmp_network vfat rw 0 0\n",
        }
        with mock.patch.object(bootrom_dump, "shell", return_value=result):
            with self.assertRaisesRegex(RuntimeError, "is not tmpfs"):
                bootrom_dump.check_mounts(object(), "/tmp_network")

    def test_creates_helper_below_selected_tmpfs(self):
        result = {"exit_code": 0, "output": "/tmp_network/br.ABC123\r\n"}
        with mock.patch.object(bootrom_dump, "shell", return_value=result) as shell:
            path = bootrom_dump.make_helper_dir(object(), "/tmp_network")

        self.assertEqual(path, "/tmp_network/br.ABC123")
        self.assertIn("/tmp_network/br.XXXXXX", shell.call_args.args[2])


if __name__ == "__main__":
    unittest.main()

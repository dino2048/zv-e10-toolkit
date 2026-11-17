"""Offline CLI tests; no camera or service connection is opened."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
import zve10_terminal_client as client


class RequestTests(unittest.TestCase):
    def test_file_and_inline_preserve_values(self):
        payload = {'action': 'wbi-drop', 'confirm_emmc_write': 'INVALIDATE WBI test hash',
                   'sony_tool': 'private/Sony 工具/loader.elf',
                   'example': 'quotes "value", backslash \\, newline\n', 'recovery_ready': True}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '请求 with spaces.json'
            for encoding in ('utf-8', 'utf-8-sig'):
                path.write_text(json.dumps(payload, ensure_ascii=False), encoding=encoding)
                self.assertEqual(client.load_request(request_file=path), payload)
                with patch.object(sys, 'argv', ['client', '--request-file', str(path)]), \
                     patch.object(client, 'resolve', return_value=Path(folder)), \
                     patch.object(client, 'read_state', return_value={'state': 'ready'}), \
                     patch.object(client, 'submit', return_value={}) as submit, \
                     contextlib.redirect_stdout(io.StringIO()):
                    client.main()
                self.assertEqual(submit.call_args.args[1], payload)
        self.assertEqual(client.load_request(json.dumps(payload)), payload)

    def test_bad_requests_fail_before_session_access(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bad.json'
            for text in ('{', '[]', 'null', '"text"', '1', ''):
                path.write_text(text, encoding='utf-8')
                with self.subTest(text=text), patch.object(sys, 'argv', ['client', '--request-file', str(path)]), \
                     patch.object(client, 'resolve') as resolve, patch.object(client, 'submit') as submit, \
                     contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        client.main()
                    resolve.assert_not_called()
                    submit.assert_not_called()
            for args in (['--request-file', str(path), '--request-json', '{}'],
                         ['--request-file', str(path), '--cancel-backup'],
                         ['--request-file', str(path) + '.missing']):
                with patch.object(sys, 'argv', ['client'] + args), patch.object(client, 'resolve') as resolve, \
                     contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        client.main()
                    resolve.assert_not_called()

    @unittest.skipUnless(os.name == 'nt', 'requires Windows PowerShell')
    def test_powershell_file_request_preserves_spaces_and_unicode(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / '请求 with spaces.json'
            payload = {'action': 'shell', 'command': 'busybox cat /proc/mounts',
                       'confirmation': 'INVALIDATE WBI test hash', 'path': 'Sony 工具/a "b" \\ c'}
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8-sig')
            runner = root / 'offline runner.py'
            runner.write_text(
                'import sys\nsys.path.insert(0, ' + repr(str(Path(client.__file__).parent)) + ')\n'
                'import zve10_terminal_client as c\nfrom pathlib import Path\n'
                'c.resolve = lambda _: Path(".")\n'
                'c.read_state = lambda _: {"state": "ready"}\n'
                'c.submit = lambda session, payload, **kw: payload\nc.main()\n', encoding='utf-8')
            def quote(value):
                return "'" + str(value).replace("'", "''") + "'"
            command = '& %s -B %s --request-file %s' % tuple(map(quote, (sys.executable, runner, path)))
            import base64
            result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand',
                                     base64.b64encode(command.encode('utf-16-le')).decode()],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), payload)


if __name__ == '__main__':
    unittest.main()

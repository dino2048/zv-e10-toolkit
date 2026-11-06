"""Regression checks for the camera-tested shell-builtin inventory path."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'host'))
import zve10_backup_files as backup


class Tests(unittest.TestCase):
    def test_shell_listing_without_find_stat_or_ls(self):
        with tempfile.TemporaryDirectory(prefix='inventory space-') as temp:
            root=Path(temp);(root/'ordinary').write_text('x');(root/'.hidden').write_text('x')
            (root/'..also-hidden').write_text('x');(root/'nested dir').mkdir()
            (root/'link').symlink_to(root/'ordinary');(root/'cycle').symlink_to(root,target_is_directory=True)
            selected=''
            def command(dev,label,text,timeout):
                nonlocal selected
                if label=='inventory_path':
                    selected=text
                    return {'exit_code':0,'output':''}
                result=subprocess.run(['/bin/sh','-c',selected+';'+text],capture_output=True,env={'PATH':'/nonexistent'})
                return {'exit_code':result.returncode,'output':result.stdout.decode()}
            with patch.object(backup.common,'command',side_effect=command):
                entries=backup.directory_entries(None,temp)
                self.assertEqual(set(entries),{('F',str(root/'ordinary')),('F',str(root/'.hidden')),('F',str(root/'..also-hidden')),('D',str(root/'nested dir'))})
                with self.assertRaises(RuntimeError):backup.directory_entries(None,str(root/'missing'))
                with self.assertRaises(RuntimeError):backup.directory_entries(None,str(root/'cycle'))
            self.assertNotIn('busybox',backup.DIRECTORY_LOOP)
            self.assertNotIn('find',backup.DIRECTORY_LOOP)

    def test_mount_boundary_and_longest_match(self):
        mounts={'/':'1:1','/usr':'1:2','/root/same':'1:1','/root/other':'1:3'}
        tree={'/root':[('F','/root/a'),('D','/root/same'),('D','/root/other')],'/root/same':[('F','/root/same/b')]}
        with patch.object(backup,'mount_devices',return_value=mounts),patch.object(backup,'directory_entries',side_effect=lambda dev,path:tree[path]) as listing:
            files,errors=backup.inventory(None,['/root'])
            self.assertEqual(set(files),{'/root/a','/root/same/b'});self.assertEqual(errors,[])
            self.assertNotIn('/root/other',[call.args[1] for call in listing.call_args_list])
        self.assertEqual(backup.device_for('/usr/lib/a',mounts),'1:2')
        self.assertEqual(backup.device_for('/usr-other/a',mounts),'1:1')

    def test_failed_inventory_cannot_be_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)
            with patch.object(backup,'metadata',return_value={}),patch.object(backup,'inventory',return_value=([],[{'root':'/setting','error':'not readable'}])):
                result=backup.backup(None,out,'critical',max_file_bytes=0,max_files=0,double_read_all=False)
            self.assertFalse(result['completed'])
            backup.write_report(out,result)
            self.assertIn('not readable',(out/'REPORT.md').read_text())

    def test_malformed_listing_and_mountinfo_rejected(self):
        with patch.object(backup.common,'command',side_effect=[{'exit_code':0,'output':''},{'exit_code':0,'output':'F/setting/partial'}]):
            with self.assertRaises(RuntimeError):backup.directory_entries(None,'/setting')
        with patch.object(backup.common,'command',return_value={'exit_code':0,'output':'not mountinfo'}):
            files,errors=backup.inventory(None,['/setting'])
            self.assertEqual(files,[]);self.assertTrue(errors)


if __name__=='__main__':unittest.main()

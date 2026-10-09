import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from scripts.sanitize_archives import sanitize


class ArchiveTest(unittest.TestCase):
    def test_local_identity_removed_without_changing_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source.tar.gz'
            with tarfile.open(path,'w:gz') as archive:
                member=tarfile.TarInfo('source/example.txt');member.size=4
                member.uid=501;member.gid=20;member.uname='private-builder';member.gname='private-group'
                member.mtime=123;member.mode=0o755;member.pax_headers={'atime':'123'}
                archive.addfile(member,io.BytesIO(b'test'))
            sanitize(path)
            with tarfile.open(path) as archive:
                member=archive.getmember('source/example.txt')
                self.assertEqual((member.uid,member.gid,member.uname,member.gname,member.mtime),(0,0,'','',0))
                self.assertEqual(member.pax_headers,{})
                self.assertEqual(member.mode,0o755)
                self.assertEqual(archive.extractfile(member).read(),b'test')

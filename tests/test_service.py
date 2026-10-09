import json
from multiprocessing.connection import Client
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from univpn_client.service import request,locations,InstanceLock

class ServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.process=subprocess.Popen([sys.executable,'-m','univpn_client.daemon','--config-dir',str(self.root)],
                                      stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        end=time.monotonic()+5
        while time.monotonic()<end:
            try:request('snapshot',directory=self.root);return
            except (OSError,EOFError,RuntimeError):time.sleep(.02)
        self.fail('service did not start')
    def tearDown(self):
        try:request('shutdown',directory=self.root)
        except (OSError,EOFError,RuntimeError):pass
        try:self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
        self.tmp.cleanup()
    def test_two_clients_share_profiles_and_block_unknown_methods(self):
        value=request('save_profile',{'value':{'name':'Example','host':'vpn.example.com'}},self.root)
        result=request('snapshot',directory=self.root)
        self.assertEqual(result['config']['profiles'][0]['id'],value['id'])
        with self.assertRaises(RuntimeError):request('get_password',directory=self.root)
        self.assertEqual(request('snapshot',directory=self.root)['connection']['state'],'disconnected')
    def test_invalid_json_does_not_crash_service(self):
        root,address,key=locations(self.root)
        with Client(address,authkey=key.read_bytes()) as client:
            client.send_bytes(b'{bad json')
            self.assertIn('error',json.loads(client.recv_bytes()))
        self.assertIn('version',request('snapshot',directory=self.root))
    def test_wrong_ipc_key_does_not_crash_service(self):
        from multiprocessing import AuthenticationError
        root,address,key=locations(self.root)
        with self.assertRaises(AuthenticationError):Client(address,authkey=b'wrong')
        self.assertIn('version',request('snapshot',directory=self.root))
    def test_second_owner_rejected(self):
        with self.assertRaises(OSError):
            with InstanceLock(self.root/'service.lock'):pass

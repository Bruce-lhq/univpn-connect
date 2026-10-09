import tempfile,time,unittest
from pathlib import Path
from univpn_client.profiles import ProfileStore
from univpn_client.credentials import CredentialStore
from univpn_client.engine import ConnectionController
from tests.test_credentials import MemoryKeychain

class FakeProcess:
    def __init__(self, lines=(),hold=False): self.lines=list(lines); self.hold=hold; self.stopped=False
    def output(self):
        if self.lines: return self.lines.pop(0)
        time.sleep(.01); return None
    def poll(self): return None if self.hold and not self.stopped else 1
    def stop(self): self.stopped=True

class ControllerTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=ProfileStore(Path(self.tmp.name)/'config')
        self.profile=self.store.save_profile({'name':'Lab','host':'vpn.example.com'})
        self.account=self.store.save_account({'name':'Me','username':'user'})
        self.creds=CredentialStore(MemoryKeychain());self.creds.set(self.account['id'],'secret-test')
        self.controller=None
    def tearDown(self):
        if self.controller:self.controller.close()
        self.tmp.cleanup()
    def start(self,runner,**kwargs):
        self.controller=ConnectionController(self.store,self.creds,runner,**kwargs)
        self.controller.connect(self.profile['id'],self.account['id']);return self.controller
    def wait(self,state):
        end=time.monotonic()+3
        while time.monotonic()<end:
            if self.controller.snapshot()['state']==state:return
            time.sleep(.01)
        self.fail(str(self.controller.snapshot()))
    def test_connect_disconnect_and_single_owner(self):
        p=FakeProcess(['Configured as test-vip'],hold=True)
        c=self.start(lambda *_:p);self.wait('connected')
        with self.assertRaises(RuntimeError):c.connect(self.profile['id'],self.account['id'])
        c.disconnect();self.wait('disconnected');self.assertTrue(p.stopped)
    def test_auth_failure_does_not_retry_and_redacts(self):
        calls=[]
        def runner(*_):calls.append(1);return FakeProcess(['secret-test','UniVPN authentication failed (-1)'])
        c=self.start(runner);self.wait('failed');self.assertEqual(calls,[1])
        self.assertNotIn('secret-test',str(c.logs()))
    def test_missing_password_fails_without_launch(self):
        self.creds.delete(self.account['id']);calls=[]
        self.start(lambda *_:calls.append(1));self.wait('failed');self.assertEqual(calls,[])
    def test_certificate_failure_does_not_retry(self):
        calls=[]
        def runner(*_):
            calls.append(1);return FakeProcess(['Server certificate verify failed: unknown issuer'])
        self.start(runner);self.wait('failed');self.assertEqual(calls,[1])
    def test_accepted_pin_warning_does_not_disable_reconnection(self):
        calls=[]
        def runner(*_):
            calls.append(1)
            return FakeProcess(['Server certificate verify failed: unknown issuer','Configured as test-vip'],hold=len(calls)>1)
        c=self.start(runner,reconnects=1)
        end=time.monotonic()+3
        while len(calls)<2 and time.monotonic()<end:time.sleep(.01)
        self.assertEqual(len(calls),2);self.wait('connected')
    def test_timeout_stops_owned_process(self):
        p=FakeProcess(hold=True);self.start(lambda *_:p,connect_timeout=.02,reconnects=0)
        self.wait('failed');self.assertTrue(p.stopped)
    def test_cancel_during_launch_cleans_up(self):
        p=FakeProcess(hold=True)
        def runner(*_):time.sleep(.05);return p
        c=self.start(runner);c.disconnect();self.wait('disconnected');self.assertTrue(p.stopped)

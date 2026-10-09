import json,os
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
from univpn_client.routes import route_plan,route_hook
from univpn_client.helper import validate_job

class RouteTest(unittest.TestCase):
    def test_plans_touch_only_explicit_routes(self):
        for platform,device,index in [('darwin','utun99',None),('linux','uv0123abcd',None),('win32','UniVPN-0123abcd',7)]:
            setup,add,remove=route_plan(platform,device,'10.90.0.2',1400,['10.20.0.0/16'],index)
            self.assertEqual(len(add),1);self.assertEqual(len(remove),1)
            self.assertNotIn('0.0.0.0/0',str(setup+add+remove))
            self.assertNotIn('dns',str(setup+add+remove).lower())
    def test_invalid_device_default_loopback_or_mtu_rejected(self):
        cases=[('utun0;bad',1400,['10.0.0.0/8']),('utun0',0,['10.0.0.0/8']),
               ('utun0',1400,['0.0.0.0/0']),('utun0',1400,['127.0.0.0/8']),('utun0',1400,[])]
        for device,mtu,routes in cases:
            with self.assertRaises(ValueError):route_plan('darwin',device,'10.90.0.2',mtu,routes)
    def test_connect_disconnect_and_failure_rollback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);root.chmod(0o700)
            (root/'job.json').write_text(json.dumps({'routes':['10.20.0.0/16','10.30.0.0/16']}))
            env={'UNIVPN_SESSION_DIR':str(root),'reason':'connect','TUNDEV':'utun99','INTERNAL_IP4_ADDRESS':'10.90.0.2'}
            commands=[]
            with patch('univpn_client.routes.sys.platform','darwin'),patch('univpn_client.windows_security.verify_directory'):
                route_hook(env,commands.append)
                self.assertTrue((root/'state.json').exists())
                route_hook({**env,'reason':'disconnect'},commands.append)
                self.assertFalse((root/'state.json').exists())
                self.assertEqual(sum('delete' in cmd for cmd in commands),2)
                commands=[]
                def failure(command):
                    commands.append(command)
                    if 'add' in command and '10.30.0.0/16' in command:raise RuntimeError('failed')
                with self.assertRaises(RuntimeError):route_hook(env,failure)
                self.assertFalse((root/'state.json').exists())
                self.assertTrue(any('delete' in cmd for cmd in commands))
                self.assertFalse(any('delete' in cmd and '10.30.0.0/16' in cmd for cmd in commands))
    def test_cleanup_rejects_routes_outside_authorized_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);root.chmod(0o700)
            state={'platform':'darwin','device':'utun99','address':'10.90.0.2','mtu':1400,
                   'index':None,'routes':['10.99.0.0/16']}
            (root/'state.json').write_text(json.dumps(state))
            env={'UNIVPN_SESSION_DIR':str(root),'reason':'disconnect',
                 'UNIVPN_EXPECTED_ROUTES':json.dumps(['10.20.0.0/16'])}
            commands=[]
            with patch('univpn_client.routes.sys.platform','darwin'),patch('univpn_client.windows_security.verify_directory'):
                with self.assertRaises(ValueError):route_hook(env,commands.append)
            self.assertEqual(commands,[])
    def test_privileged_job_rejects_extra_command_or_missing_routes(self):
        job={'profile':{'name':'Lab','host':'vpn.example.com','routes':['10.0.0.0/8']},
             'account':{'name':'Work','username':'user'},'password':'mock','session':'mock-session'}
        self.assertEqual(validate_job(job,'mock-session')[2],'mock')
        with self.assertRaises(ValueError):validate_job({**job,'command':'bad'},'mock-session')
        with self.assertRaises(ValueError):validate_job(job,'different-session')
        job['profile']['routes']=[]
        with self.assertRaises(ValueError):validate_job(job,'mock-session')

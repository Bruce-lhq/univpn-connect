import json
import os
from pathlib import Path
import tempfile
import unittest
from univpn_client.profiles import ProfileStore

class ProfilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)/'config.json'
        self.store = ProfileStore(self.path)
    def tearDown(self):
        self.tmp.cleanup()
    def test_two_gateways_and_accounts_persist(self):
        one = self.store.save_profile({'name':'Office','host':'vpn.example.com','port':443,'routes':['10.0.0.0/8']})
        two = self.store.save_profile({'name':'Lab','host':'vpn2.example.com','port':18443})
        account = self.store.save_account({'name':'Work','username':'alice'})
        self.store.select(two['id'], account['id'])
        loaded = ProfileStore(self.path).snapshot()
        self.assertEqual(len(loaded['profiles']), 2)
        self.assertEqual(loaded['selected_profile'], two['id'])
        self.assertEqual(loaded['selected_account'], account['id'])
        self.assertNotEqual(one['id'], two['id'])
        if os.name != 'nt':
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
    def test_invalid_inputs_do_not_replace_file(self):
        self.store.save_profile({'name':'Lab','host':'vpn.example.com'})
        before = self.path.read_bytes()
        for item in ({'name':'Lab','host':'--exec=bad'}, {'name':'Lab','host':'x','port':0},
                     {'name':'Lab','host':'x','routes':['10.0.0.1/8']},
                     {'name':'Lab','host':'x','password':'secret'},
                     {'name':'Lab','host':'x','pin':'abc'}):
            with self.assertRaises(ValueError):
                self.store.save_profile(item)
            self.assertEqual(self.path.read_bytes(), before)
    def test_export_never_contains_secret_and_import_is_transactional(self):
        self.store.save_account({'name':'Work','username':'alice'})
        exported = self.store.export()
        self.assertNotIn('password', exported)
        bad = json.loads(exported); bad['accounts'][0]['password']='secret'
        with self.assertRaises(ValueError): self.store.import_config(json.dumps(bad))
        self.assertEqual(self.store.export(), exported)
    def test_delete_clears_selected_and_stable_id(self):
        p = self.store.save_profile({'name':'Lab','host':'vpn.example.com'})
        p['name']='Renamed'; self.assertEqual(self.store.save_profile(p)['id'], p['id'])
        self.store.select(p['id'], None)
        self.store.delete('profiles', p['id'])
        self.assertIsNone(self.store.snapshot()['selected_profile'])
    def test_invalid_import_rejected(self):
        for text in ('{}','[]','{"schema":99}', '{bad json'):
            with self.assertRaises(ValueError): self.store.import_config(text)
    def test_unknown_selection_rejected(self):
        with self.assertRaises(ValueError): self.store.select('missing', None)
    def test_snapshot_is_not_mutable_store(self):
        snap = self.store.snapshot(); snap['profiles'].append({})
        self.assertEqual(self.store.snapshot()['profiles'], [])

import unittest
import uuid
from univpn_client.credentials import CredentialStore

class MemoryKeychain:
    def __init__(self): self.data = {}
    def set_password(self, service, key, value): self.data[service,key] = value
    def get_password(self, service, key): return self.data.get((service,key))
    def delete_password(self, service, key): self.data.pop((service,key))

class CredentialTest(unittest.TestCase):
    def test_multiple_accounts_are_isolated(self):
        backend = MemoryKeychain(); store = CredentialStore(backend)
        first, second = str(uuid.uuid4()),str(uuid.uuid4())
        store.set(first,'one'); store.set(second,'two')
        self.assertEqual(store.get(first),'one'); self.assertEqual(store.get(second),'two')
        store.delete(first)
        with self.assertRaises(RuntimeError): store.get(first)
        self.assertEqual(store.get(second),'two')
    def test_empty_or_multiline_password_rejected(self):
        store = CredentialStore(MemoryKeychain()); account = str(uuid.uuid4())
        for value in ('','a\nb','a\rb','a\0b',None):
            with self.assertRaises(ValueError): store.set(account,value)
    def test_invalid_identifier_rejected_before_keychain(self):
        store = CredentialStore(MemoryKeychain())
        for action in (store.get,store.delete):
            with self.assertRaises(ValueError): action('unexpected path')

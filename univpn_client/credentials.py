"""System keychain credentials; no plaintext fallback or web-facing reads."""
from .profiles import _id

SERVICE = 'org.univpn-connect.accounts'
SECURE_MODULES = ('keyring.backends.macOS', 'keyring.backends.Windows',
                  'keyring.backends.SecretService', 'keyring.backends.libsecret')


class CredentialStore:
    def __init__(self, backend=None):
        self.backend = backend
    def _backend(self):
        if self.backend is None:
            try:
                import keyring
                backend = keyring.get_keyring()
                candidates = getattr(backend, 'backends', [backend])
                self.backend = next((b for b in candidates if type(b).__module__ in SECURE_MODULES), None)
                if self.backend is None:
                    raise RuntimeError('No supported system keychain is available')
            except ImportError:
                raise RuntimeError('Install the client extra to use the system keychain') from None
        return self.backend
    def set(self, account_id, password):
        account_id = _id(account_id)
        if not isinstance(password, str) or not password or '\n' in password or '\r' in password or '\0' in password:
            raise ValueError('Password must be a nonempty single line')
        self._backend().set_password(SERVICE, account_id, password)
    def get(self, account_id):
        password = self._backend().get_password(SERVICE, _id(account_id))
        if password is None:
            raise RuntimeError('No saved password for this account')
        return password
    def delete(self, account_id):
        backend = self._backend(); account_id = _id(account_id)
        if backend.get_password(SERVICE, account_id) is not None:
            backend.delete_password(SERVICE, account_id)

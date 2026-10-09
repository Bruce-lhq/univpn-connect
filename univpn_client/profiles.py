"""Validated, atomic profile metadata. Passwords never belong in this file."""
import copy
import ipaddress
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import uuid


def config_directory():
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', Path.home()/'AppData/Local'))/'UniVPN Connect'
    import sys
    if sys.platform == 'darwin':
        return Path.home()/'Library/Application Support/UniVPN Connect'
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))/'univpn-connect'


def _text(value, name, required=True):
    if not isinstance(value, str) or any(ord(c) < 32 for c in value):
        raise ValueError(name+' must be plain text')
    value = value.strip()
    if (required and not value) or len(value) > 255:
        raise ValueError('Invalid '+name)
    return value


def _id(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Invalid ID') from None


def profile(value):
    if not isinstance(value, dict) or set(value) - {'id','name','host','port','domain','routes','cafile','pin'}:
        raise ValueError('Unknown profile field')
    item = dict(value)
    item['id'] = _id(item['id']) if 'id' in item else str(uuid.uuid4())
    item['name'] = _text(item.get('name'), 'name')
    item['host'] = _text(item.get('host'), 'host')
    if item['host'].startswith('-') or not re.fullmatch(r'[a-zA-Z0-9_.:-]+', item['host']):
        raise ValueError('Use a hostname or IP address without URL/path')
    port = item.get('port', 443)
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Port must be 1–65535')
    item['port'] = port
    item['domain'] = _text(item.get('domain', ''), 'domain', False)
    if len(item['domain'].encode('utf-8'))>255:raise ValueError('Authentication domain must fit in 255 UTF-8 bytes')
    routes = item.get('routes', [])
    if not isinstance(routes, list) or len(routes) > 256:
        raise ValueError('Invalid routes')
    item['routes'] = [str(ipaddress.IPv4Network(r, strict=True)) for r in routes]
    item['cafile'] = _text(item.get('cafile', ''), 'CA path', False)
    pin = item.get('pin', '')
    if pin and not re.fullmatch(r'pin-sha256:[A-Za-z0-9+/]{43}=', pin):
        raise ValueError('Use a full OpenConnect pin-sha256 public-key pin')
    item['pin'] = pin
    return item


def account(value):
    if not isinstance(value, dict) or set(value) - {'id','name','username'}:
        raise ValueError('Unknown account field; passwords use the system keychain')
    return {'id':_id(value['id']) if 'id' in value else str(uuid.uuid4()),
            'name':_text(value.get('name'),'name'), 'username':_text(value.get('username'),'username')}


class ProfileStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else config_directory()/'config.json'
        self.lock = threading.RLock()
        self.data = {'schema':1,'profiles':[],'accounts':[], 'selected_profile':None,
                     'selected_account':None, 'theme':'system'}
        if self.path.exists():
            self.data = self._validate(json.loads(self.path.read_text(encoding='utf-8')))
    @staticmethod
    def _validate(value):
        keys = {'schema','profiles','accounts','selected_profile','selected_account','theme'}
        if not isinstance(value, dict) or set(value) != keys or value['schema'] != 1:
            raise ValueError('Unsupported configuration schema')
        result = copy.deepcopy(value)
        for kind, validate in (('profiles',profile),('accounts',account)):
            if not isinstance(value[kind], list): raise ValueError('Invalid '+kind)
            result[kind] = [validate(item) for item in value[kind]]
            ids = [item['id'] for item in result[kind]]
            if len(ids) != len(set(ids)): raise ValueError('Duplicate IDs')
            key = 'selected_'+('profile' if kind == 'profiles' else 'account')
            if result[key] is not None and result[key] not in ids:
                raise ValueError('Selected item does not exist')
        if result['theme'] not in ('system','light','dark'): raise ValueError('Invalid theme')
        return result
    def _commit(self, data):
        data = self._validate(data)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, name = tempfile.mkstemp(prefix='.config-', dir=self.path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as stream:
                json.dump(data,stream,ensure_ascii=False,indent=2)
                stream.flush(); os.fsync(stream.fileno())
            os.replace(name,self.path)
        finally:
            if os.path.exists(name): os.unlink(name)
        self.data = data
    def snapshot(self):
        with self.lock: return copy.deepcopy(self.data)
    def _save(self, kind, value, validate):
        item = validate(value)
        with self.lock:
            data = self.snapshot()
            data[kind] = [item if old['id'] == item['id'] else old for old in data[kind]]
            if not any(old['id'] == item['id'] for old in data[kind]): data[kind].append(item)
            self._commit(data)
        return item
    def save_profile(self, value): return self._save('profiles',value,profile)
    def save_account(self, value): return self._save('accounts',value,account)
    def delete(self, kind, item_id):
        if kind not in ('profiles','accounts'): raise ValueError('Invalid collection')
        with self.lock:
            data = self.snapshot(); data[kind] = [x for x in data[kind] if x['id'] != item_id]
            key = 'selected_'+('profile' if kind == 'profiles' else 'account')
            if data[key] == item_id: data[key] = None
            self._commit(data)
    def select(self, profile_id, account_id):
        with self.lock:
            data = self.snapshot(); data.update(selected_profile=profile_id,selected_account=account_id)
            self._commit(data)
    def set_theme(self, theme):
        with self.lock:
            data = self.snapshot(); data['theme'] = theme; self._commit(data)
    def export(self): return json.dumps(self.snapshot(),ensure_ascii=False,indent=2)
    def import_config(self, text):
        with self.lock: self._commit(json.loads(text))

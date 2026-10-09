"""Local authenticated IPC. Receive JSON bytes, never pickle application input."""
import hashlib
import json
from multiprocessing.connection import Client,Listener
from multiprocessing import AuthenticationError
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from .profiles import config_directory


def locations(directory=None):
    root = Path(directory) if directory else config_directory()
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    if root.is_symlink(): raise RuntimeError('Configuration directory must not be a symlink')
    address = (r'\\.\pipe\univpn-connect-'+hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:32]) if os.name=='nt' else str(root/'control.sock')
    return root,address,root/'ipc.key'


def request(method,params=None,directory=None):
    root,address,keyfile=locations(directory)
    key=keyfile.read_bytes()
    if len(key)!=32:raise RuntimeError('Invalid IPC key')
    with Client(address,family='AF_PIPE' if os.name=='nt' else 'AF_UNIX',authkey=key) as connection:
        connection.send_bytes(json.dumps({'method':method,'params':params or {}}).encode())
        if not connection.poll(15):raise RuntimeError('Local service did not respond')
        result=json.loads(connection.recv_bytes(1024*1024))
    if 'error' in result:raise RuntimeError(result['error'])
    return result['result']


def ensure_service(directory=None):
    try:
        request('snapshot',directory=directory);return
    except (OSError,EOFError,RuntimeError):pass
    command=[sys.executable,'--service'] if getattr(sys,'frozen',False) else [sys.executable,'-m','univpn_client.daemon']
    if directory:command+=['--config-dir',str(directory)]
    subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL,close_fds=True,
                     creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,
                     start_new_session=os.name!='nt')
    end=time.monotonic()+5
    while time.monotonic()<end:
        try:request('snapshot',directory=directory);return
        except (OSError,EOFError,RuntimeError):time.sleep(.1)
    raise RuntimeError('Unable to start the local connection service')


class InstanceLock:
    def __init__(self,path):self.path=Path(path);self.stream=None
    def __enter__(self):
        fd=os.open(self.path,os.O_RDWR|os.O_CREAT,0o600)
        self.stream=os.fdopen(fd,'r+b')
        try:
            if os.name=='nt':
                import msvcrt
                if self.path.stat().st_size==0:self.stream.write(b'0');self.stream.flush()
                self.stream.seek(0);msvcrt.locking(self.stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except Exception:self.stream.close();raise
        return self
    def __exit__(self,*_):self.stream.close()


def serve(api,directory=None):
    root,address,keyfile=locations(directory)
    with InstanceLock(root/'service.lock'):
        if os.name!='nt' and Path(address).exists():Path(address).unlink()
        key=secrets.token_bytes(32)
        fd=os.open(keyfile,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(key)
        listener=Listener(address,family='AF_PIPE' if os.name=='nt' else 'AF_UNIX',authkey=key)
        if os.name!='nt':os.chmod(address,0o600)
        try:
            while not api.shutdown_requested:
                try:connection=listener.accept()
                except (OSError,EOFError,AuthenticationError):continue
                with connection:
                    try:
                        data=json.loads(connection.recv_bytes(1024*1024))
                        if not isinstance(data,dict) or set(data)!={'method','params'}:
                            raise ValueError('Invalid request')
                        result={'result':api.dispatch(data['method'],data['params'])}
                    except Exception as exc:result={'error':str(exc)}
                    try:connection.send_bytes(json.dumps(result).encode())
                    except (OSError,EOFError):pass
        finally:
            api.controller.close();listener.close()
            keyfile.unlink(missing_ok=True)
            if os.name!='nt':Path(address).unlink(missing_ok=True)

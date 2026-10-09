"""Temporary OS authorization and private, authenticated helper IPC."""
import ctypes
import hashlib
import json
from multiprocessing.connection import Client, Listener
import os
from pathlib import Path
import queue
import secrets
import shlex
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time


def helper_command(address,keyfile,session):
    if getattr(sys,'frozen',False):command=[sys.executable,'--helper']
    else:command=[sys.executable,str(Path(__file__).with_name('launcher.py')),'--helper']
    return command+['--address',address,'--keyfile',str(keyfile),'--session',session]


def authorize(command):
    if sys.platform=='darwin':
        script='do shell script '+json.dumps(shlex.join(command))+' with administrator privileges'
        return subprocess.Popen(['/usr/bin/osascript','-e',script],stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE,text=True)
    if sys.platform=='win32':
        return WindowsElevation(command)
    return subprocess.Popen(['pkexec',*command],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)


class WindowsElevation:
    """Keep the exact OS-returned process handle; never kill a PID from a file."""
    def __init__(self,command):
        from ctypes import wintypes as w
        class Info(ctypes.Structure):
            _fields_=[('cbSize',w.DWORD),('fMask',w.ULONG),('hwnd',w.HWND),('lpVerb',w.LPCWSTR),
                      ('lpFile',w.LPCWSTR),('lpParameters',w.LPCWSTR),('lpDirectory',w.LPCWSTR),
                      ('nShow',ctypes.c_int),('hInstApp',w.HINSTANCE),('lpIDList',ctypes.c_void_p),
                      ('lpClass',w.LPCWSTR),('hkeyClass',w.HKEY),('dwHotKey',w.DWORD),
                      ('hIcon',w.HANDLE),('hProcess',w.HANDLE)]
        info=Info();info.cbSize=ctypes.sizeof(info);info.fMask=0x40|0x100;info.lpVerb='runas'
        info.lpFile=command[0];info.lpParameters=subprocess.list2cmdline(command[1:]);info.nShow=0
        shell=ctypes.WinDLL('shell32',use_last_error=True)
        shell.ShellExecuteExW.argtypes=[ctypes.POINTER(Info)];shell.ShellExecuteExW.restype=w.BOOL
        if not shell.ShellExecuteExW(ctypes.byref(info)):raise ctypes.WinError(ctypes.get_last_error())
        self.handle=info.hProcess;self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.kernel.GetProcessId.argtypes=[w.HANDLE];self.kernel.GetProcessId.restype=w.DWORD
        self.pid=self.kernel.GetProcessId(self.handle)
        self.kernel.GetExitCodeProcess.argtypes=[w.HANDLE,ctypes.POINTER(w.DWORD)]
        self.kernel.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD]
        self.kernel.TerminateProcess.argtypes=[w.HANDLE,w.UINT]
        self.kernel.CloseHandle.argtypes=[w.HANDLE]
    def poll(self):
        from ctypes import wintypes as w
        code=w.DWORD();self.kernel.GetExitCodeProcess(self.handle,ctypes.byref(code))
        return None if code.value==259 else code.value
    def terminate(self):self.kernel.TerminateProcess(self.handle,1)
    def kill(self):self.terminate()
    def wait(self,timeout):
        if self.kernel.WaitForSingleObject(self.handle,int(timeout*1000))==258:raise subprocess.TimeoutExpired('helper',timeout)
        return self.poll()
    def close(self):self.kernel.CloseHandle(self.handle)


def check_helper_peer(connection,launcher):
    if sys.platform=='win32':
        from ctypes import wintypes as w
        pid=w.ULONG();kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.GetNamedPipeClientProcessId.argtypes=[w.HANDLE,ctypes.POINTER(w.ULONG)]
        if not kernel.GetNamedPipeClientProcessId(connection.fileno(),ctypes.byref(pid)) or pid.value!=launcher.pid:
            raise RuntimeError('Unexpected elevated helper process')
    elif sys.platform=='darwin':
        libc=ctypes.CDLL(None);uid=ctypes.c_uint();gid=ctypes.c_uint()
        if libc.getpeereid(connection.fileno(),ctypes.byref(uid),ctypes.byref(gid)) or uid.value!=0:
            raise RuntimeError('Helper must be root')
    else:
        with socket.socket(fileno=os.dup(connection.fileno())) as peer:
            pid,uid,gid=struct.unpack('3i',peer.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
        if uid!=0:raise RuntimeError('Helper must be root')


class AuthorizedProcess:
    def __init__(self,profile,account,password):
        if not profile['routes']:raise ValueError('Configure at least one IPv4 split route')
        if any(route.endswith('/0') for route in profile['routes']):raise ValueError('This initial client supports split routes; /0 is not supported')
        self.lines=queue.Queue(maxsize=500);self.cancel=threading.Event();self.finished=threading.Event()
        self.connection=None;self.listener=None;self.launcher=None;self.exitcode=None
        self.lock=threading.Lock()
        self.thread=threading.Thread(target=self._run,args=(profile,account,password),daemon=True)
        self.thread.start()
    def _put(self,line):
        try:self.lines.put_nowait(line)
        except queue.Full:pass
    def _run(self,profile,account,password):
        temporary=tempfile.TemporaryDirectory(prefix='univpn-authorize-');root=Path(temporary.name)
        session=secrets.token_hex(16);address=r'\\.\pipe\univpn-auth-'+session if os.name=='nt' else str(root/'helper.sock')
        key=secrets.token_bytes(32);keyfile=root/'ipc.key';fd=os.open(keyfile,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as output:output.write(key)
        try:
            self.listener=Listener(address,family='AF_PIPE' if os.name=='nt' else 'AF_UNIX',authkey=key)
            if os.name!='nt':os.chmod(address,0o600)
            if self.cancel.is_set():return
            self._put('Waiting for system network authorization')
            self.launcher=authorize(helper_command(address,keyfile,session))
            # Accept is isolated so cancellation never blocks the UI thread.
            accepted=queue.Queue(maxsize=1)
            def accept():
                try:accepted.put(self.listener.accept())
                except Exception as exc:accepted.put(exc)
            threading.Thread(target=accept,daemon=True).start()
            deadline=time.monotonic()+85
            while not self.cancel.is_set():
                try:connection=accepted.get(timeout=.2);break
                except queue.Empty:
                    if self.launcher.poll() is not None:raise RuntimeError('Network authorization was cancelled or unavailable')
                    if time.monotonic()>deadline:raise RuntimeError('Network authorization timed out')
            else:return
            if isinstance(connection,Exception):raise connection
            self.connection=connection;check_helper_peer(connection,self.launcher)
            connection.send_bytes(json.dumps({'profile':profile,'account':account,'password':password,'session':session}).encode())
            password=''
            while not self.cancel.is_set():
                if not connection.poll(.2):
                    if self.launcher.poll() is not None:raise RuntimeError('Network helper exited unexpectedly')
                    continue
                message=json.loads(connection.recv_bytes(1024*1024))
                if message.get('kind')=='log':self._put(message['line'])
                elif message.get('kind')=='exit':self.exitcode=int(message['code']);break
                else:raise RuntimeError('Invalid helper response')
        except Exception as exc:
            self._put(str(exc).replace(password,'[redacted]') if password else str(exc));self.exitcode=1
        finally:
            password=''
            with self.lock:
                if self.connection:
                    try:self.connection.send_bytes(b'{"action":"stop"}')
                    except (OSError,EOFError):pass
                    self.connection.close();self.connection=None
            if self.listener:self.listener.close()
            if self.launcher:
                try:self.launcher.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    self.launcher.terminate()
                    try:self.launcher.wait(timeout=3)
                    except subprocess.TimeoutExpired:self.launcher.kill()
                if hasattr(self.launcher,'close'):self.launcher.close()
            temporary.cleanup();self.exitcode=0 if self.exitcode is None else self.exitcode;self.finished.set()
    def output(self,timeout=.2):
        try:return self.lines.get(timeout=timeout)
        except queue.Empty:return None
    def poll(self):return self.exitcode if self.finished.is_set() else None
    def stop(self):
        self.cancel.set()
        with self.lock:
            if self.connection:
                try:self.connection.send_bytes(b'{"action":"stop"}')
                except (OSError,EOFError):pass
        self.thread.join(timeout=16)

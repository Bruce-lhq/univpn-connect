"""One owned connection, asynchronous progress and bounded reconnects."""
from collections import deque
import copy
from pathlib import Path
import queue
import shlex
import os
import subprocess
import threading
import time
import uuid


class NativeProcess:
    def __init__(self, command, password):
        self.lines = queue.Queue(maxsize=500)
        self.process = subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT,text=True,bufsize=1)
        try:
            self.process.stdin.write(password+'\n'); self.process.stdin.close()
        except Exception:
            self.stop(); raise
        threading.Thread(target=self._read,daemon=True).start()
    def _read(self):
        try:
            for line in self.process.stdout:
                try: self.lines.put_nowait(line.rstrip())
                except queue.Full: pass
        finally:
            self.process.stdout.close()
    def output(self, timeout=.2):
        try: return self.lines.get(timeout=timeout)
        except queue.Empty: return None
    def poll(self): return self.process.poll()
    def stop(self):
        if self.process.poll() is None:
            self.process.terminate()
            try: self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.process.kill(); self.process.wait(timeout=3)


def command_for(binary, profile, account, route_script):
    binary, route_script = Path(binary).resolve(),Path(route_script).resolve()
    if not binary.is_file() or not route_script.is_file():
        raise RuntimeError('Native core or route script is missing; build the native bundle first')
    host = profile['host']
    if ':' in host: host = '['+host+']'
    command = [str(binary),'--protocol=univpn','--no-proxy','--non-inter',
               '--passwd-on-stdin','--user='+account['username'], '--script='+(str(route_script) if os.name=='nt' else shlex.quote(str(route_script)))]
    if profile['domain']: command.append('--authgroup='+profile['domain'])
    if profile['cafile']: command.append('--cafile='+profile['cafile'])
    if profile['pin']: command.append('--servercert='+profile['pin'])
    command.append('https://'+host+':'+str(profile['port']))
    return command


class ConnectionController:
    def __init__(self, profiles, credentials, runner, connect_timeout=90, reconnects=3):
        self.profiles, self.credentials, self.runner = profiles,credentials,runner
        self.connect_timeout, self.reconnects = connect_timeout,reconnects
        self.lock = threading.RLock(); self.records = deque(maxlen=300)
        self.state = {'state':'disconnected','profile_id':None,'account_id':None,
                      'session_id':None,'connected_at':None,'error':None,'attempt':0}
        self.cancel = threading.Event(); self.process = None; self.worker = None
    def snapshot(self):
        with self.lock: return copy.deepcopy(self.state)
    def logs(self):
        with self.lock: return list(self.records)
    def _log(self, line, password=''):
        if password: line = line.replace(password,'[redacted]')
        if 'COOKIE=' in line or 'token=' in line.lower(): line = '[session credential redacted]'
        with self.lock: self.records.append({'time':time.time(),'message':line[:2000]})
    def connect(self, profile_id, account_id):
        with self.lock:
            if self.worker and self.worker.is_alive(): raise RuntimeError('Disconnect before switching VPN')
            data = self.profiles.snapshot()
            profile = next((x for x in data['profiles'] if x['id']==profile_id),None)
            account = next((x for x in data['accounts'] if x['id']==account_id),None)
            if profile is None or account is None: raise ValueError('Select a gateway and account')
            self.profiles.select(profile_id,account_id)
            self.cancel = threading.Event()
            self.state.update(state='connecting',profile_id=profile_id,account_id=account_id,
                              session_id=str(uuid.uuid4()),error=None,attempt=0,connected_at=None)
            self.worker = threading.Thread(target=self._run,args=(profile,account,self.cancel),daemon=True)
            self.worker.start()
        return self.snapshot()
    def _run(self, profile, account, cancel):
        password = ''
        try:
            password = self.credentials.get(account['id'])
            for attempt in range(self.reconnects+1):
                if cancel.is_set(): break
                with self.lock: self.state.update(attempt=attempt,state='reconnecting' if attempt else 'connecting')
                process = self.runner(profile,account,password)
                with self.lock: self.process = process
                deadline = time.monotonic()+self.connect_timeout; connected = False; permanent = False
                while not cancel.is_set():
                    line = process.output()
                    if line is not None:
                        self._log(line,password)
                        lower = line.lower()
                        permanent |= any(word in lower for word in ('authentication failed (-1)',
                            'certificate verification failed','certificate verify failed','server ssl certificate','cookie was rejected',
                            'permission denied','operation not permitted','authorization was cancelled',
                            'authorization timed out','network command failed'))
                        if 'Configured as ' in line:
                            # A private-CA warning can precede successful explicit
                            # pin validation. Successful setup clears that warning.
                            connected = True; permanent = False
                            with self.lock: self.state.update(state='connected',connected_at=time.time())
                    elif process.poll() is not None:
                        break
                    if not connected and time.monotonic()>deadline:
                        self._log('Connection timed out'); break
                process.stop()
                with self.lock: self.process = None
                if cancel.is_set(): break
                if permanent or attempt==self.reconnects:
                    raise RuntimeError('Connection ended; check credentials, trust and network permission' if permanent
                                       else 'Connection failed after bounded reconnect attempts')
                self._log('Connection lost; retrying with fresh authentication')
                if cancel.wait(min(2**attempt,4)): break
        except Exception as exc:
            with self.lock:
                self.state.update(state='disconnected' if cancel.is_set() else 'failed',
                                  error=None if cancel.is_set() else str(exc).replace(password,'[redacted]') if password else str(exc))
        finally:
            password = ''
            with self.lock:
                process = self.process; self.process = None
                if cancel.is_set(): self.state.update(state='disconnected',error=None,connected_at=None)
            if process: process.stop()
    def disconnect(self):
        with self.lock:
            self.cancel.set()
            if self.worker and self.worker.is_alive(): self.state['state']='disconnecting'
            else: self.state.update(state='disconnected',error=None,connected_at=None)
        return self.snapshot()
    def close(self):
        self.disconnect()
        worker = self.worker
        if worker: worker.join(timeout=12)

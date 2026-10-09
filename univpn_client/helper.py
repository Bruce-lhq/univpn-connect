"""Elevated guardian. Accept one validated job; own only its child and routes."""
import argparse
import json
from multiprocessing.connection import Client
import os
from pathlib import Path
import re
import shutil
import sys
from .engine import NativeProcess,command_for
from .profiles import profile,account


def resources():return Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))


def validate_job(job,session):
    if not isinstance(job,dict) or set(job)!={'profile','account','password','session'} or job['session']!=session:
        raise ValueError('Invalid helper job')
    gateway,identity=profile(job['profile']),account(job['account'])
    password=job['password']
    if not isinstance(password,str) or not password or any(c in password for c in '\n\r\0'):
        raise ValueError('Invalid password')
    if not gateway['routes'] or any(route.endswith('/0') for route in gateway['routes']):
        raise ValueError('At least one IPv4 split route is required; /0 is unsupported')
    return gateway,identity,password


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--address',required=True)
    parser.add_argument('--keyfile',type=Path,required=True);parser.add_argument('--session',required=True)
    args=parser.parse_args(argv)
    if not re.fullmatch('[0-9a-f]{32}',args.session):raise ValueError('Invalid session identifier')
    if os.name=='nt':
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():raise RuntimeError('Network helper requires administrator rights')
    elif os.geteuid()!=0:raise RuntimeError('Network helper requires root')
    key=args.keyfile.read_bytes()
    if len(key)!=32:raise ValueError('Invalid IPC key')
    from .windows_security import private_session
    process=None;root=private_session()
    try:
        with Client(args.address,family='AF_PIPE' if os.name=='nt' else 'AF_UNIX',authkey=key) as connection:
            if not connection.poll(10):raise RuntimeError('No connection job received')
            gateway,identity,password=validate_job(json.loads(connection.recv_bytes(1024*1024)),args.session)
            (root/'job.json').write_text(json.dumps({'routes':gateway['routes'],'session':args.session}),encoding='utf-8')
            os.chmod(root/'job.json',0o600)
            bundle=resources();core=bundle/'native'/('openconnect.exe' if os.name=='nt' else 'openconnect')
            route_script=bundle/'native'/('route-script.js' if os.name=='nt' else 'route-script')
            command=command_for(core,gateway,identity,route_script)
            if os.name=='nt' and not gateway['cafile']:
                command.insert(1,'--cafile='+str(bundle/'native/ca-bundle.pem'))
            elif not gateway['cafile']:
                # Bundled OpenSSL's build-time Homebrew CA directory may not
                # exist on the user's machine. Use the actual OS CA bundle.
                ca='/etc/ssl/cert.pem' if sys.platform=='darwin' else '/etc/ssl/certs/ca-certificates.crt'
                command.insert(1,'--cafile='+ca)
            if os.name=='nt':command.insert(1,'--interface=UniVPN-'+args.session[:8])
            elif sys.platform!='darwin':command.insert(1,'--interface=uv'+args.session[:8])
            # Fixed runtime paths only. Never copy arbitrary job-supplied environment.
            os.environ['UNIVPN_SESSION_DIR']=str(root)
            os.environ['UNIVPN_SESSION_ID']=args.session
            os.environ['UNIVPN_EXPECTED_ROUTES']=json.dumps(gateway['routes'])
            os.environ['UNIVPN_HELPER_EXE']=sys.executable
            os.environ['UNIVPN_HELPER_SCRIPT']='' if getattr(sys,'frozen',False) else str(Path(__file__).with_name('launcher.py'))
            process=NativeProcess(command,password);password=''
            while True:
                if connection.poll(0):
                    message=json.loads(connection.recv_bytes(1024))
                    if message!={'action':'stop'}:raise ValueError('Invalid control request')
                    break
                line=process.output(timeout=.1)
                if line is not None:connection.send_bytes(json.dumps({'kind':'log','line':line}).encode())
                elif process.poll() is not None:
                    connection.send_bytes(json.dumps({'kind':'exit','code':process.poll()}).encode());break
    finally:
        if process:process.stop()
        from .routes import route_hook
        try:route_hook({'reason':'disconnect','UNIVPN_SESSION_DIR':str(root),'UNIVPN_SESSION_ID':args.session,
                        'UNIVPN_EXPECTED_ROUTES':os.environ.get('UNIVPN_EXPECTED_ROUTES','[]')})
        finally:shutil.rmtree(root)
    return 0

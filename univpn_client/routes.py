"""IPv4 split-route hooks. Add only owned routes; never replace global DNS/defaults."""
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def route_plan(platform,device,address,mtu,routes,index=None):
    address=str(ipaddress.IPv4Address(address))
    if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,32}',device):raise ValueError('Invalid tunnel device')
    mtu=int(mtu)
    if not 576<=mtu<=65527:raise ValueError('Invalid MTU')
    parsed=[ipaddress.IPv4Network(route,strict=True) for route in routes]
    if not parsed or any(net.prefixlen==0 or net.overlaps(ipaddress.IPv4Network('127.0.0.0/8')) for net in parsed):
        raise ValueError('Only explicit non-loopback IPv4 split routes are supported')
    if ipaddress.IPv4Address(address).is_loopback or ipaddress.IPv4Address(address).is_multicast:
        raise ValueError('Invalid assigned IPv4 address')
    if platform=='darwin':
        if not re.fullmatch(r'utun\d+',device):raise ValueError('Expected an allocated utun device')
        setup=[['/sbin/ifconfig',device,'inet',address,address,'netmask','255.255.255.255','mtu',str(mtu),'up']]
        add=[['/sbin/route','-n','add','-net',str(net),'-interface',device] for net in parsed]
        remove=[['/sbin/route','-n','delete','-net',str(net),'-interface',device] for net in parsed]
    elif platform=='win32':
        if not re.fullmatch(r'UniVPN-[0-9a-f]{8}',device) or not str(index).isdigit():raise ValueError('Invalid owned Windows adapter')
        # netsh arguments contain only validated interface/IP/numeric values.
        setup=[['netsh','interface','ipv4','set','address','name='+device,'source=static','address='+address,'mask=255.255.255.255'],
               ['netsh','interface','ipv4','set','subinterface',device,'mtu='+str(mtu),'store=active']]
        add=[['netsh','interface','ipv4','add','route','prefix='+str(net),'interface='+str(index),'nexthop=0.0.0.0','store=active'] for net in parsed]
        remove=[['netsh','interface','ipv4','delete','route','prefix='+str(net),'interface='+str(index),'nexthop=0.0.0.0','store=active'] for net in parsed]
    else:
        if not re.fullmatch(r'uv[0-9a-f]{8}',device):raise ValueError('Invalid owned Linux tunnel')
        from shutil import which
        ip=which('ip',path='/usr/sbin:/sbin:/usr/bin:/bin') or '/usr/sbin/ip'
        setup=[[ip,'addr','add',address+'/32','dev',device],[ip,'link','set','dev',device,'mtu',str(mtu),'up']]
        add=[[ip,'route','add',str(net),'dev',device] for net in parsed]
        remove=[[ip,'route','del',str(net),'dev',device] for net in parsed]
    return setup,add,remove


def _run(command):
    result=subprocess.run(command,capture_output=True,text=True,timeout=8)
    if result.returncode:raise RuntimeError('Network command failed: '+result.stderr.strip()[:300])


def _save(path,value):
    temporary=path.with_suffix('.tmp');fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as stream:json.dump(value,stream)
    os.replace(temporary,path)


def route_hook(environment=None,run=_run):
    env=os.environ if environment is None else environment
    reason=env.get('reason','')
    if reason in ('pre-init','attempt-reconnect','reconnect'):return 0
    root=Path(env.get('UNIVPN_SESSION_DIR',''))
    if not env.get('UNIVPN_SESSION_DIR') or root.is_symlink() or not root.is_dir():raise ValueError('Missing private route session')
    stat=root.stat()
    if os.name!='nt' and (stat.st_uid!=os.geteuid() or stat.st_mode&0o077):raise ValueError('Insecure route session')
    if os.name=='nt':
        from .windows_security import verify_directory
        verify_directory(root.parent);verify_directory(root)
    state_file=root/'state.json'
    if reason=='disconnect':
        if not state_file.exists():return 0
        state=json.loads(state_file.read_text())
        if state['platform']!=sys.platform:raise ValueError('Route session platform mismatch')
        expected=env.get('UNIVPN_SESSION_ID')
        if expected and sys.platform=='win32' and state['device']!='UniVPN-'+expected[:8]:raise ValueError('Route session adapter mismatch')
        if expected and sys.platform not in ('darwin','win32') and state['device']!='uv'+expected[:8]:raise ValueError('Route session device mismatch')
        allowed=json.loads(env['UNIVPN_EXPECTED_ROUTES']) if env.get('UNIVPN_EXPECTED_ROUTES') else None
        if allowed is not None and not set(state['routes']).issubset(allowed):raise ValueError('Unowned route in cleanup')
        if not state['routes']:state_file.unlink(missing_ok=True);return 0
        _,_,remove=route_plan(state['platform'],state['device'],state['address'],state['mtu'],state['routes'],state['index'])
        for command in reversed(remove):
            try:run(command)
            except RuntimeError:pass # The kernel may already have removed routes with the device.
        state_file.unlink(missing_ok=True);return 0
    if reason!='connect':raise ValueError('Unsupported route-hook event')
    if state_file.exists():raise RuntimeError('Route session is already configured')
    job=json.loads((root/'job.json').read_text())
    setup,add,remove=route_plan(sys.platform,env.get('TUNDEV',''),env.get('INTERNAL_IP4_ADDRESS',''),
                              env.get('INTERNAL_IP4_MTU','1400'),job['routes'],env.get('TUNIDX'))
    state={'platform':sys.platform,'device':env.get('TUNDEV',''),'address':env.get('INTERNAL_IP4_ADDRESS',''),
           'mtu':env.get('INTERNAL_IP4_MTU','1400'),'index':env.get('TUNIDX'),'routes':[]};_save(state_file,state)
    try:
        for command in setup:run(command)
        for command,route in zip(add,job['routes']):
            # Never delete a pre-existing route when an add failed. Any route
            # added just before a crash disappears with our temporary adapter.
            run(command);state['routes'].append(route);_save(state_file,state)
    except Exception:
        route_hook({**env,'reason':'disconnect'},run);raise
    return 0

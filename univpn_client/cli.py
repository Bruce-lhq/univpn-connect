"""Cross-platform CLI sharing the desktop's local service and keychain."""
import argparse
import getpass
import json
from pathlib import Path
import sys
from . import __version__
from .service import request,ensure_service


def main(argv=None):
    parser=argparse.ArgumentParser(prog='univpn-client')
    parser.add_argument('--version',action='version',version=__version__)
    parser.add_argument('--config-dir',type=Path)
    commands=parser.add_subparsers(dest='command',required=True)
    for name in ('status','logs','disconnect','shutdown','desktop'):
        commands.add_parser(name)
    profiles=commands.add_parser('profiles');profiles.add_argument('action',choices=['list','add','remove'])
    profiles.add_argument('--id');profiles.add_argument('--name');profiles.add_argument('--host')
    profiles.add_argument('--port',type=int,default=443);profiles.add_argument('--domain',default='')
    profiles.add_argument('--route',action='append',default=[]);profiles.add_argument('--ca',default='');profiles.add_argument('--pin',default='')
    accounts=commands.add_parser('accounts');accounts.add_argument('action',choices=['list','add','remove','password'])
    accounts.add_argument('--id');accounts.add_argument('--name');accounts.add_argument('--username')
    connect=commands.add_parser('connect');connect.add_argument('--profile',required=True);connect.add_argument('--account',required=True)
    export=commands.add_parser('export');export.add_argument('path',type=Path)
    imp=commands.add_parser('import');imp.add_argument('path',type=Path)
    args=parser.parse_args(argv)
    try:
        if args.command=='desktop':
            from .desktop import main as desktop
            return desktop(args.config_dir)
        ensure_service(args.config_dir)
        call=lambda method,**params:request(method,params,directory=args.config_dir)
        if args.command=='status':result=call('snapshot')
        elif args.command in ('logs','disconnect','shutdown'):result=call(args.command)
        elif args.command=='connect':result=call('connect',profile_id=args.profile,account_id=args.account)
        elif args.command=='export':args.path.write_text(call('export_config'),encoding='utf-8');result={'exported':str(args.path)}
        elif args.command=='import':call('import_config',text=args.path.read_text(encoding='utf-8'));result={'imported':True}
        elif args.command in ('profiles','accounts'):
            kind=args.command
            if args.action=='list':result=call('snapshot')['config'][kind]
            elif args.action=='remove':result=call('delete',kind=kind,item_id=args.id)
            elif kind=='profiles':
                value={'name':args.name,'host':args.host,'port':args.port,'domain':args.domain,
                       'routes':args.route,'cafile':args.ca,'pin':args.pin}
                if args.id:value['id']=args.id
                result=call('save_profile',value=value)
            elif args.action=='password':
                value=next((x for x in call('snapshot')['config']['accounts'] if x['id']==args.id),None)
                if value is None:raise ValueError('Account not found')
                result=call('save_account',value=value,password=getpass.getpass('VPN password: '))
            else:
                value={'name':args.name,'username':args.username}
                if args.id:value['id']=args.id
                result=call('save_account',value=value,password=getpass.getpass('VPN password: '))
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (OSError,RuntimeError,ValueError,EOFError) as exc:
        print('Error: '+str(exc),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())

"""Owned local service; no privileged HTTP endpoint."""
import argparse
from pathlib import Path
import sys
from . import __version__
from .credentials import CredentialStore
from .engine import ConnectionController,NativeProcess,command_for
from .platforms import AuthorizedProcess
from .profiles import ProfileStore,config_directory,account
from .service import serve


class API:
    METHODS={'snapshot','logs','save_profile','save_account','delete','select','set_theme',
             'export_config','import_config','connect','disconnect','shutdown'}
    def __init__(self,store,credentials,controller):
        self.store,self.credentials,self.controller=store,credentials,controller
        self.shutdown_requested=False
    def dispatch(self,method,params):
        if method not in self.METHODS or not isinstance(params,dict):raise ValueError('Unknown action')
        return getattr(self,method)(**params)
    def snapshot(self):return {'version':__version__,'config':self.store.snapshot(),'connection':self.controller.snapshot()}
    def logs(self):return self.controller.logs()
    def save_profile(self,value):return self.store.save_profile(value)
    def save_account(self,value,password=None):
        value=account(value)
        if password is not None:self.credentials.set(value['id'],password)
        return self.store.save_account(value)
    def delete(self,kind,item_id):
        connection=self.controller.snapshot()
        if connection['state'] not in ('disconnected','failed') and item_id in (connection['profile_id'],connection['account_id']):
            raise RuntimeError('Disconnect before deleting an active item')
        if kind=='accounts':self.credentials.delete(item_id)
        self.store.delete(kind,item_id)
    def select(self,profile_id,account_id):self.store.select(profile_id,account_id)
    def set_theme(self,theme):self.store.set_theme(theme)
    def export_config(self):return self.store.export()
    def import_config(self,text):
        if self.controller.snapshot()['state'] not in ('disconnected','failed'):raise RuntimeError('Disconnect before importing')
        self.store.import_config(text)
    def connect(self,profile_id,account_id):return self.controller.connect(profile_id,account_id)
    def disconnect(self):return self.controller.disconnect()
    def shutdown(self):self.controller.close();self.shutdown_requested=True


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config-dir',type=Path)
    parser.add_argument('--core',type=Path);parser.add_argument('--route-script',type=Path)
    args=parser.parse_args();root=args.config_dir or config_directory()
    resources=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
    core=args.core or resources/'native'/('openconnect.exe' if sys.platform=='win32' else 'openconnect')
    script=args.route_script or resources/'native'/('route-script.js' if sys.platform=='win32' else 'route-script')
    store=ProfileStore(root/'config.json');credentials=CredentialStore()
    def runner(p,a,password):
        if args.core or args.route_script:
            return NativeProcess(command_for(core,p,a,script),password)
        command_for(core,p,a,script) # Fail before authorization when the bundle is missing.
        return AuthorizedProcess(p,a,password)
    controller=ConnectionController(store,credentials,runner)
    try:serve(API(store,credentials,controller),root)
    except OSError:return 1
    return 0

if __name__=='__main__':raise SystemExit(main())

#!/usr/bin/env python3
"""Freeze the same desktop/CLI executable on each supported build host."""
import argparse
import hashlib
import json
import importlib.metadata
from pathlib import Path
import platform
import plistlib
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def dependency_licenses():
    target=ROOT/'build/third-party-licenses'
    import shutil
    if target.exists():shutil.rmtree(target)
    target.mkdir(parents=True)
    for package in importlib.metadata.distributions():
        for file in package.files or []:
            if file.name.lower().startswith(('license','licence','copying','notice')) and file.suffix not in ('.so','.dll','.dylib','.py','.pyc','.yaml','.yml'):
                source=package.locate_file(file)
                if source.is_file():
                    name=package.metadata['Name']+'-'+file.name
                    (target/name).write_bytes(source.read_bytes())
    for source in (ROOT/'build/dependency-source-licenses').glob('*'):
        (target/source.name).write_bytes(source.read_bytes())
    for source in (Path(sys.base_prefix)/'LICENSE.txt',Path(sys.base_prefix)/'lib/python3.12/LICENSE.txt',Path('/usr/share/doc/python3.12/copyright')):
        if source.is_file():(target/'Python-LICENSE.txt').write_bytes(source.read_bytes());break
    return target


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native',type=Path,default=ROOT/'univpn_client/native')
    args=parser.parse_args();native=args.native.resolve()
    core=native/('openconnect.exe' if sys.platform=='win32' else 'openconnect')
    for required in (core,native/'manifest.json',native/'licenses/OpenConnect-LGPL-2.1.txt'):
        if not required.is_file():parser.error('Missing native build or license: '+str(required))
    metadata=json.loads((native/'manifest.json').read_text())
    for name,digest in metadata['files'].items():
        if hashlib.sha256((native/name).read_bytes()).hexdigest()!=digest:
            parser.error('Native file no longer matches manifest: '+name)
    # A console-enabled executable also handles --service, --helper and CLI.
    # macOS .app launches without a terminal; Windows uses a hidden-window
    # launcher for the same executable, preserving console output for CLI.
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir',
             '--specpath',str(ROOT/'build'),
             '--name','UniVPN Connect','--paths',str(ROOT),
             '--add-data',str(ROOT/'univpn_client/ui')+':ui',
             '--add-data',str(native)+':native','--add-data',str(ROOT/'LICENSE')+':licenses',
             '--add-data',str(dependency_licenses())+':licenses/third-party',
             '--collect-all','keyring','--collect-all','webview',
             '--hidden-import','univpn_client.daemon','--hidden-import','univpn_client.helper',
             '--hidden-import','univpn_client.windows_security']
    if sys.platform=='darwin':
        command+=['--windowed','--osx-bundle-identifier','org.univpn-connect.desktop']
    elif sys.platform=='win32':
        command+=['--collect-all','win32ctypes','--hidden-import','win32security',
                  '--hidden-import','win32file','--hidden-import','pywintypes']
    subprocess.run(command+[str(ROOT/'univpn_client/launcher.py')],cwd=ROOT,check=True)
    if sys.platform=='darwin':
        sys.path.insert(0,str(ROOT))
        from univpn_forward import __version__
        bundle=ROOT/'dist/UniVPN Connect.app';info=bundle/'Contents/Info.plist'
        metadata=plistlib.loads(info.read_bytes());number=re.match(r'\d+\.\d+\.\d+',__version__).group()
        metadata.update(CFBundleShortVersionString=number,CFBundleVersion=number,
                        CFBundleGetInfoString='UniVPN Connect '+__version__)
        info.write_bytes(plistlib.dumps(metadata))
        subprocess.run(['codesign','--force','--deep','--sign','-',str(bundle)],check=True)
    elif sys.platform=='linux':
        # GTK/WebKit and OS libraries are declared runtime dependencies, not
        # untracked copies of Ubuntu binaries with separate source obligations.
        import shutil
        internal=ROOT/'dist/UniVPN Connect/_internal'
        for library in internal.glob('lib*.so*'):
            if not library.name.startswith('libpython'):library.unlink()
        typelibs=internal/'gi_typelibs'
        if typelibs.exists():shutil.rmtree(typelibs)
    print('Built for '+sys.platform+' / '+platform.machine())


if __name__=='__main__':main()

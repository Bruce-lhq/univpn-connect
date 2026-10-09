#!/usr/bin/env python3
"""Stage Linux/Windows core libraries and required notices on the build host."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys


def run(*command):return subprocess.check_output(command,text=True).strip()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--openssl-license',type=Path,required=True)
    parser.add_argument('--destination',type=Path,default=Path('univpn_client/native'))
    parser.add_argument('--wintun',type=Path)
    parser.add_argument('--wintun-license',type=Path)
    args=parser.parse_args();source=args.source.resolve();target=args.destination.resolve()
    windows=sys.platform=='win32';core=source/'.libs'/('openconnect.exe' if windows else 'openconnect')
    for path in (core,source/'COPYING.LGPL',args.openssl_license):
        if not path.is_file():parser.error('Missing build or license input: '+str(path))
    target.mkdir(parents=True,exist_ok=True);todo=[core];copied={}
    native_bin=Path(os.environ.get('UNIVPN_MINGW_BIN','C:/msys64/mingw64/bin'))
    while todo:
        original=todo.pop(0).absolute()
        if original in copied:continue
        output=target/original.name;output.unlink(missing_ok=True);shutil.copy2(original,output)
        output.chmod(output.stat().st_mode|0o200);copied[original]=output.name
        if windows:
            deps=re.findall(r'DLL Name:\s*(\S+)',run(str(native_bin/'objdump.exe'),'-p',str(original)))
            for name in deps:
                candidate=source/'.libs'/name
                if not candidate.exists():candidate=native_bin/name
                # Windows API DLLs come from System32; never redistribute them.
                if candidate.is_file():todo.append(candidate)
                elif not (Path(os.environ['SystemRoot'])/'System32'/name).is_file() and not name.lower().startswith(('api-ms-','ext-ms-')):
                    raise RuntimeError('Unresolved DLL: '+name)
        else:
            for line in run('ldd',str(original)).splitlines():
                if '=>' not in line:continue
                name,resolved=line.strip().split('=>',1);name=name.strip();resolved=resolved.strip().split(' (',1)[0]
                if name.startswith(('libc.','libm.','libpthread.','libdl.','librt.','ld-linux')):continue
                # The Debian package declares system TLS/XML/zlib libraries.
                # Only our modified, replaceable libopenconnect is redistributed.
                if not name.startswith('libopenconnect.'):continue
                candidate=Path(resolved) if resolved!='not found' else source/'.libs'/name
                if not candidate.is_file():raise RuntimeError('Unresolved library: '+name)
                todo.append(candidate)
            subprocess.run(['patchelf','--set-rpath','$ORIGIN',str(output)],check=True)
    licenses=target/'licenses';licenses.mkdir(exist_ok=True)
    shutil.copy2(source/'COPYING.LGPL',licenses/'OpenConnect-LGPL-2.1.txt')
    shutil.copy2(args.openssl_license,licenses/'OpenSSL-Apache-2.0.txt')
    shutil.copy2(source/'json/LICENSE',licenses/'OpenConnect-json.txt')
    if windows:
        if not args.wintun or not args.wintun_license:parser.error('Windows builds require the official Wintun DLL and license')
        shutil.copy2(args.wintun,target/'wintun.dll');shutil.copy2(args.wintun_license,licenses/'Wintun-LICENSE.txt')
        copied[args.wintun.resolve()]='wintun.dll'
        bundles=(native_bin.parent/'ssl/cert.pem',
                 native_bin.parent/'etc/ssl/certs/ca-bundle.crt',
                 native_bin.parent/'etc/pki/tls/certs/ca-bundle.crt')
        bundle=next((path for path in bundles if path.is_file()),None)
        if bundle is None:raise RuntimeError('Missing Windows CA certificate bundle')
        shutil.copy2(bundle,target/'ca-bundle.pem');copied[bundle]='ca-bundle.pem'
        for directory in (native_bin.parent/'share/licenses').iterdir():
            if directory.is_dir():shutil.copytree(directory,licenses/directory.name,dirs_exist_ok=True)
    metadata={'platform':sys.platform,'architecture':platform.machine(),
              'version':run(str(target/core.name),'--version'),
              'files':{name:hashlib.sha256((target/name).read_bytes()).hexdigest() for name in sorted(copied.values())}}
    (target/'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n');print(metadata['version'])


if __name__=='__main__':main()

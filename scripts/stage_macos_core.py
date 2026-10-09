#!/usr/bin/env python3
"""Bundle a built OpenConnect core; keep its dynamic libraries replaceable."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def run(*command):
    return subprocess.check_output(command,text=True).strip()


def dependencies(path):
    return [line.strip().split(' (',1)[0] for line in run('otool','-L',str(path)).splitlines()[1:]]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--openssl-license',type=Path,required=True)
    parser.add_argument('--destination',type=Path,default=Path('univpn_client/native'))
    args=parser.parse_args();source=args.source.resolve();target=args.destination.resolve()
    if sys.platform!='darwin':parser.error('This stager requires macOS')
    for path in (source/'.libs/openconnect',source/'COPYING.LGPL',args.openssl_license):
        if not path.is_file():parser.error('Missing build or license input: '+str(path))
    target.mkdir(parents=True,exist_ok=True)
    todo=[source/'.libs/openconnect'];copied={};links={}
    while todo:
        original=todo.pop(0).resolve()
        if original in copied:continue
        name='openconnect' if not copied else original.name
        if name in copied.values():raise RuntimeError('Conflicting library names')
        output=target/name;output.unlink(missing_ok=True);shutil.copy2(original,output)
        output.chmod(output.stat().st_mode|0o200);copied[original]=name
        links[output]=[]
        for dependency in dependencies(original):
            if dependency.startswith(('/usr/lib/','/System/')):continue
            if dependency==str(original):continue
            candidate=Path(dependency)
            if not candidate.exists():candidate=source/'.libs'/candidate.name
            if not candidate.exists():raise RuntimeError('Unresolved library: '+dependency)
            links[output].append((dependency,candidate.resolve()))
            todo.append(candidate)
    for output,refs in links.items():
        for old,original in refs:
            run('install_name_tool','-change',old,'@loader_path/'+copied[original],str(output))
        if output.suffix=='.dylib':run('install_name_tool','-id','@loader_path/'+output.name,str(output))
        run('codesign','--force','--sign','-',str(output))
    licenses=target/'licenses';licenses.mkdir(exist_ok=True)
    shutil.copy2(source/'COPYING.LGPL',licenses/'OpenConnect-LGPL-2.1.txt')
    shutil.copy2(args.openssl_license,licenses/'OpenSSL-Apache-2.0.txt')
    if (source/'json/LICENSE').exists():shutil.copy2(source/'json/LICENSE',licenses/'OpenConnect-json.txt')
    version=run(str(target/'openconnect'),'--version')
    manifest={'upstream_commit':run('git','-C',str(source),'rev-parse','HEAD'),
              'platform':'macos','architecture':run('uname','-m'),'version':version,
              'files':{name:hashlib.sha256((target/name).read_bytes()).hexdigest() for name in sorted(copied.values())}}
    (target/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(version)


if __name__=='__main__':main()

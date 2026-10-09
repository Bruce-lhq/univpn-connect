#!/usr/bin/env python3
"""Retrieve the pinned official source archive and apply the public patch series."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination',type=Path,default=ROOT/'build/openconnect')
    parser.add_argument('--archive',type=Path)
    args=parser.parse_args();destination=args.destination.resolve()
    if destination.exists():parser.error('Destination already exists; use a fresh directory')
    pin=json.loads((ROOT/'native/openconnect/upstream.json').read_text())
    patches=sorted((ROOT/'native/openconnect/patches').glob('*.patch'))
    if not pin.get('patches') or [p.name for p in patches]!=pin['patches']:
        parser.error('The complete pinned patch series is required')
    archive=args.archive or ROOT/'build/openconnect-upstream.tar.gz'
    archive.parent.mkdir(parents=True,exist_ok=True)
    if not archive.exists():urllib.request.urlretrieve(pin['url'],archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=pin['sha256']:
        parser.error('Upstream source SHA-256 mismatch')
    with tarfile.open(archive) as source:
        for member in source.getmembers():
            path=Path(*Path(member.name).parts[1:])
            if not path.parts:continue
            target=destination/path
            if not target.resolve().is_relative_to(destination) or member.isdev():
                parser.error('Unsafe source archive member')
            if member.issym() or member.islnk():
                parser.error('Unexpected source archive link')
            member.name=str(path);source.extract(member,destination)
    for patch in patches:
        subprocess.run(['git','apply','--check',str(patch)],cwd=destination,check=True)
        subprocess.run(['git','apply',str(patch)],cwd=destination,check=True)
    print('Pinned source and patches ready: '+str(destination))


if __name__=='__main__':main()

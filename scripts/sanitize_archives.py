#!/usr/bin/env python3
"""Remove build-user and timestamp metadata from release tar archives."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile


def neutral_member(member):
    member.uid=member.gid=0
    member.uname=member.gname=''
    member.mtime=0
    member.pax_headers={}
    return member


def sanitize(path):
    path=Path(path)
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as temporary:
        output=Path(temporary.name)
    try:
        with tarfile.open(path) as source,tarfile.open(output,'w:gz') as target:
            for member in source:
                target.addfile(neutral_member(member),source.extractfile(member) if member.isfile() else None)
        output.replace(path)
    finally:output.unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths',nargs='+',type=Path)
    args=parser.parse_args()
    parents=set()
    for path in args.paths:
        archives=sorted(path.rglob('*.tar.gz')) if path.is_dir() else [path]
        for archive in archives:
            manifest=archive.parent/'binding-sources.json'
            upstream={item['source'] for item in json.loads(manifest.read_text()).values()} if manifest.exists() else set()
            if archive.name not in upstream:sanitize(archive)
            parents.add(archive.parent)
    for parent in parents:
        checksum=parent/'SHA256SUMS'
        if checksum.exists():
            checksum.write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(parent.iterdir()) if p.is_file() and p!=checksum))


if __name__=='__main__':main()

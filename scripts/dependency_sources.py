#!/usr/bin/env python3
"""Collect matching binding sources and notices needed beside native releases."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import tarfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


def main():
    packages=ROOT/'dist/packages';packages.mkdir(parents=True,exist_ok=True)
    licenses=ROOT/'build/dependency-source-licenses';licenses.mkdir(parents=True,exist_ok=True)
    manifest={}
    for name in ('pyobjc-core','PyGObject','pycairo'):
        try:version=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:continue
        with urllib.request.urlopen('https://pypi.org/pypi/'+name+'/'+version+'/json',timeout=30) as response:
            metadata=json.load(response)
        entry=next(x for x in metadata['urls'] if x['packagetype']=='sdist' and x['filename'].endswith('.tar.gz'))
        target=packages/entry['filename'];expected=entry['digests']['sha256']
        if not target.exists():
            with urllib.request.urlopen(entry['url'],timeout=30) as response:target.write_bytes(response.read())
        if hashlib.sha256(target.read_bytes()).hexdigest()!=expected:raise RuntimeError('Dependency source hash mismatch: '+name)
        found=False
        with tarfile.open(target) as source:
            for member in source:
                filename=Path(member.name).name
                if member.isfile() and member.size<262144 and filename.lower().startswith(('license','copying')) and Path(filename).suffix.lower() in ('','.txt','.md','.rst'):
                    (licenses/(name+'-'+filename)).write_bytes(source.extractfile(member).read());found=True
        if not found:raise RuntimeError('Dependency source has no license notice: '+name)
        manifest[name]={'version':version,'source':target.name,'url':entry['url'],'sha256':expected}
    (packages/'binding-sources.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Matching binding sources and notices collected')


if __name__=='__main__':main()

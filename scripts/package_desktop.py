#!/usr/bin/env python3
"""Produce unsigned installer layouts plus portable desktop/CLI archives."""
import hashlib
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from univpn_forward import __version__
from scripts.sanitize_archives import neutral_member


def main():
    output=ROOT/'dist';machine=platform.machine().lower()
    system={'darwin':'macos','win32':'windows'}.get(sys.platform,'linux')
    name='univpn-connect-'+__version__+'-'+system+'-'+machine
    executable=output/'UniVPN Connect';release=output/'packages';release.mkdir(exist_ok=True)
    if not executable.is_dir():raise SystemExit('Build desktop first')
    if sys.platform=='darwin':
        app=output/'UniVPN Connect.app';layout=ROOT/'build/dmg';layout.mkdir(parents=True,exist_ok=True)
        staged=layout/app.name
        if staged.exists():shutil.rmtree(staged)
        shutil.copytree(app,staged,symlinks=True)
        shortcut=layout/'Applications'
        if not shortcut.exists():shortcut.symlink_to('/Applications')
        target=release/(name+'.dmg');target.unlink(missing_ok=True)
        subprocess.run(['hdiutil','create','-volname','UniVPN Connect','-srcfolder',str(layout),
                        '-format','UDZO',str(target)],check=True)
        with tarfile.open(release/(name+'-cli.tar.gz'),'w:gz') as archive:
            archive.add(executable,arcname='univpn-connect',filter=neutral_member)
    elif sys.platform=='win32':
        vbs='Set shell = CreateObject("WScript.Shell")\nSet fs = CreateObject("Scripting.FileSystemObject")\nshell.Run Chr(34) & fs.BuildPath(fs.GetParentFolderName(WScript.ScriptFullName), "UniVPN Connect.exe") & Chr(34), 0, False\n'
        (executable/'UniVPN Connect.vbs').write_text(vbs)
        (executable/'univpn-client.cmd').write_text('@echo off\r\n"%~dp0UniVPN Connect.exe" %*\r\n')
        with zipfile.ZipFile(release/(name+'-portable.zip'),'w',zipfile.ZIP_DEFLATED) as archive:
            for path in executable.rglob('*'):
                if path.is_file():archive.write(path,Path('univpn-connect')/path.relative_to(executable))
        subprocess.run(['makensis','/DSOURCE='+str(executable),'/DOUTPUT='+str(release/(name+'-setup.exe')),
                        '/DVERSION='+__version__,'/DICON='+str(ROOT/'univpn_client/ui/app-icon.ico'),str(ROOT/'packaging/windows.nsi')],check=True)
    else:
        with tarfile.open(release/(name+'-portable.tar.gz'),'w:gz') as archive:
            archive.add(executable,arcname='univpn-connect',filter=neutral_member)
        deb=ROOT/'build/debian';deb.mkdir(parents=True,exist_ok=True)
        destination=deb/'opt/univpn-connect'
        if destination.exists():shutil.rmtree(destination)
        destination.parent.mkdir(exist_ok=True);shutil.copytree(executable,destination,symlinks=True)
        (deb/'usr/bin').mkdir(parents=True,exist_ok=True)
        for command,args in [('univpn-client',''),('univpn-connect','desktop')]:
            wrapper=deb/'usr/bin'/command
            wrapper.write_text('#!/bin/sh\nexec "/opt/univpn-connect/UniVPN Connect" '+args+' "$@"\n');wrapper.chmod(0o755)
        applications=deb/'usr/share/applications';applications.mkdir(parents=True,exist_ok=True)
        (applications/'univpn-connect.desktop').write_text('[Desktop Entry]\nType=Application\nName=UniVPN Connect\nExec=univpn-connect\nIcon=univpn-connect\nTerminal=false\nCategories=Network;\n')
        icons=deb/'usr/share/icons/hicolor/512x512/apps';icons.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/'univpn_client/ui/app-icon-512.png',icons/'univpn-connect.png')
        metadata=deb/'DEBIAN';metadata.mkdir(exist_ok=True)
        arch={'x86_64':'amd64','aarch64':'arm64'}.get(machine,machine)
        (metadata/'control').write_text('Package: univpn-connect\nVersion: '+__version__.replace('a','~alpha')+
            '\nArchitecture: '+arch+'\nMaintainer: UniVPN Connect contributors <contributors@example.invalid>\n'+
            'Depends: libc6 (>= 2.39), libssl3t64, libxml2, zlib1g, libgtk-3-0t64, libwebkit2gtk-4.1-0, gir1.2-gtk-3.0, gir1.2-webkit2-4.1, libreadline8t64, libbz2-1.0, liblzma5, policykit-1, iproute2, gnome-keyring\n'+
            'Description: Experimental UniVPN desktop and CLI client\n')
        subprocess.run(['dpkg-deb','--root-owner-group','--build',str(deb),str(release/(name+'.deb'))],check=True)
    files=sorted(p for p in release.iterdir() if p.is_file() and p.name!='SHA256SUMS')
    (release/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files))
    print('Installer and portable artifacts: '+str(release))


if __name__=='__main__':main()

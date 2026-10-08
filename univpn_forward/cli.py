"""Command-line configuration for the single-target TCP protocol prototype."""
import argparse
import getpass
import ipaddress
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import threading

from . import __version__, protocol


def port(value):
    result = int(value)
    if not 1 <= result <= 65535:
        raise argparse.ArgumentTypeError("Port must be between 1 and 65535")
    return result


def fingerprint(value):
    result = value.lower().removeprefix("sha256:").replace(":", "")
    if len(result) != 64 or any(c not in "0123456789abcdef" for c in result):
        raise argparse.ArgumentTypeError("Expected a full SHA-256 certificate fingerprint")
    return result


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version', action='version', version=__version__)
    p.add_argument('--gateway', required=True, help='VPN gateway hostname or IP')
    p.add_argument('--gateway-port', type=port, default=443)
    p.add_argument('--domain', help='Authentication domain; defaults to gateway')
    p.add_argument('--server-name', help='TLS certificate name/SNI; defaults to gateway')
    p.add_argument('--target', required=True, type=ipaddress.IPv4Address, help='Destination IPv4 address inside VPN')
    p.add_argument('--target-port', required=True, type=port)
    p.add_argument('--listen', default='127.0.0.1', choices=['127.0.0.1'])
    p.add_argument('--listen-port', type=port, default=2222)
    credentials = p.add_mutually_exclusive_group()
    credentials.add_argument('--credentials-file', type=Path, help='Private JSON with username/password (chmod 600)')
    credentials.add_argument('--keychain-service', help='macOS generic-password service containing username/password JSON')
    p.add_argument('--keychain-account', default='gateway')
    p.add_argument('--username', help='Interactive authentication username')
    tls = p.add_mutually_exclusive_group()
    tls.add_argument('--ca-file', help='Trusted CA certificate bundle')
    tls.add_argument('--cert-sha256', type=fingerprint, help='Full trusted leaf-certificate SHA-256 fingerprint')
    tls.add_argument('--insecure', action='store_true', help='Explicitly disable certificate verification (diagnostics only)')
    return p


def credentials(args):
    if args.credentials_file:
        with args.credentials_file.open('r', encoding='utf-8') as f:
            info = os.fstat(f.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
                raise ValueError('Credentials must be a regular private file; chmod 600')
            data = json.load(f)
    elif args.keychain_service:
        if sys.platform != 'darwin':
            raise ValueError('Keychain authentication requires macOS')
        result = subprocess.run(['/usr/bin/security', 'find-generic-password', '-s',
                                 args.keychain_service, '-a', args.keychain_account, '-w'],
                                capture_output=True, text=True)
        if result.returncode:
            raise ValueError('Could not read requested Keychain credential')
        data = json.loads(result.stdout)
    else:
        data = {'username': args.username or input('VPN username: '),
                'password': getpass.getpass('VPN password: ')}
    if not isinstance(data, dict) or any(not isinstance(data.get(k), str) or not data[k] for k in ('username', 'password')):
        raise ValueError('Credentials require nonempty username and password strings')
    return data['username'], data['password']


def configure(args):
    if len((args.domain or args.gateway).encode()) > 256:
        raise ValueError('Authentication domain is limited to 256 encoded bytes')
    protocol.VPN_HOST, protocol.VPN_PORT = args.gateway, args.gateway_port
    protocol.DOMAIN = args.domain or args.gateway
    protocol.SERVER_NAME = args.server_name or args.gateway
    protocol.REMOTE_HOST, protocol.REMOTE_PORT = str(args.target), args.target_port
    protocol.CA_FILE, protocol.CERT_SHA256, protocol.INSECURE = args.ca_file, args.cert_sha256, args.insecure


def main():
    args = parser().parse_args()
    try:
        configure(args)
        username, password = credentials(args)
        if args.insecure:
            print('WARNING: server certificate verification disabled', file=sys.stderr)
        def session(client):
            try:
                protocol.relay(client, username, password)
            except Exception as exc:
                print('Connection failed: ' + str(exc), file=sys.stderr, flush=True)
        with socket.socket() as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((args.listen, args.listen_port))
            server.listen(4)
            print(f'READY {args.listen}:{args.listen_port} (authentication occurs on connection)', flush=True)
            while True:
                client, _ = server.accept()
                threading.Thread(target=session, args=(client,), daemon=True).start()
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from None

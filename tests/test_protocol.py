import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch, Mock
import ssl
import hashlib

from univpn_forward import protocol as p
from univpn_forward.cli import parser, configure, credentials, fingerprint


class Stream:
    def __init__(self, chunks): self.chunks = iter(chunks)
    def recv(self, n):
        item = next(self.chunks)
        if isinstance(item, Exception): raise item
        return item


class Tests(unittest.TestCase):
    def test_fragmented_frame_survives_body_timeout(self):
        frame = p.nem(0x66, b'abcd')
        s = Stream([frame[:3], socket.timeout(), frame[3:8], socket.timeout(), b'a', b'bcd'])
        header, body = p.recv_nem(s)
        self.assertEqual(header, frame[:8]); self.assertEqual(body, b'abcd')

    def test_idle_timeout_propagates(self):
        with self.assertRaises(socket.timeout): p.recv_nem(Stream([socket.timeout()]))

    def test_eof_mid_frame(self):
        with self.assertRaises(EOFError): p.recv_nem(Stream([p.nem(1, b'a')[:8], b'']))

    def test_bad_magic(self):
        with self.assertRaises(RuntimeError): p.recv_nem(Stream([b'xxxxxxxx']))

    def test_multibyte_domain_padding(self):
        with patch.object(p, 'DOMAIN', '域.example'):
            packet = p.firstconnect_packet()
            self.assertEqual(len(packet), 340)
            self.assertEqual(packet[80:80+len(p.DOMAIN.encode())], p.DOMAIN.encode())

    def test_default_tls_verifies_certificate(self):
        with patch.object(p, 'INSECURE', False), patch.object(p, 'CERT_SHA256', None):
            ctx = ssl.create_default_context()
            tls = Mock()
            with patch.object(p.ssl, 'create_default_context', return_value=ctx), patch.object(p.socket, 'create_connection', return_value=Mock()), patch.object(ctx, 'wrap_socket', return_value=tls):
                p.tls_connect()
            self.assertTrue(ctx.check_hostname)
            self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)

    def test_packet_and_checksums(self):
        packet = p.build_tcp('10.0.0.1','10.0.0.2',40001,22,123,456,0x18,b'hello')
        self.assertEqual(p.checksum(packet[:20]), 0)
        pseudo = packet[12:20] + bytes([0,6]) + (len(packet)-20).to_bytes(2,'big')
        self.assertEqual(p.checksum(pseudo+packet[20:]),0)
        info = p.parse_ipv4_tcp(packet)
        self.assertEqual(info['payload'],b'hello');self.assertEqual(info['seq'],123)

    def test_reject_malformed_offsets(self):
        packet = bytearray(p.build_tcp('10.0.0.1','10.0.0.2',1,2,0,0,0x10))
        packet[0]=0x40;self.assertIsNone(p.parse_ipv4_tcp(packet))
        packet[0]=0x45;packet[32]=0;self.assertIsNone(p.parse_ipv4_tcp(packet))

    def test_secure_defaults(self):
        a=parser().parse_args(['--gateway','vpn.example.com','--target','10.0.0.2','--target-port','22'])
        configure(a);self.assertFalse(p.INSECURE);self.assertIsNone(p.CERT_SHA256)
        self.assertEqual(p.SERVER_NAME,'vpn.example.com')

    def test_pin_mismatch_closes_socket(self):
        p.CERT_SHA256='a'*64
        raw=Mock();tls=Mock();tls.getpeercert.return_value=b'certificate'
        ctx=Mock();ctx.wrap_socket.return_value=tls
        with patch.object(p.ssl,'create_default_context',return_value=ctx), patch.object(p.socket,'create_connection',return_value=raw):
            with self.assertRaises(ssl.SSLCertVerificationError):p.tls_connect()
        tls.close.assert_called_once();raw.close.assert_called_once()
        p.CERT_SHA256=None

    def test_matching_pin(self):
        p.CERT_SHA256=hashlib.sha256(b'certificate').hexdigest()
        tls=Mock();tls.getpeercert.return_value=b'certificate';ctx=Mock();ctx.wrap_socket.return_value=tls
        with patch.object(p.ssl,'create_default_context',return_value=ctx), patch.object(p.socket,'create_connection',return_value=Mock()):
            self.assertIs(p.tls_connect(),tls)
        p.CERT_SHA256=None

    def test_private_credentials(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'credentials.json';f.write_text(json.dumps({'username':'example','password':'test-only'}))
            args=parser().parse_args(['--gateway','vpn.example.com','--target','10.0.0.2','--target-port','22','--credentials-file',str(f)])
            f.chmod(0o644)
            with self.assertRaises(ValueError):credentials(args)
            f.chmod(0o600);self.assertEqual(credentials(args),('example','test-only'))

    def test_partial_pin_rejected(self):
        with self.assertRaises(Exception):fingerprint('abcd')


if __name__=='__main__':unittest.main()

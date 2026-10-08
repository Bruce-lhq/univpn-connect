#!/usr/bin/env python3
import socket, ssl, struct, hashlib, hmac, ipaddress, random, threading, time, errno

# Populated once by the CLI before accepting connections.
VPN_HOST = DOMAIN = REMOTE_HOST = ""
VPN_PORT = REMOTE_PORT = 0
SERVER_NAME = ""
CA_FILE = CERT_SHA256 = None
INSECURE = False

MAGIC = b"\xc1\x92\xa4\xd6"
MSS = 1200



def is_retryable_io_error(e):
    """iSH/Alpine may surface socket timeout as EAGAIN/SSLWantRead."""
    if isinstance(e, (socket.timeout, TimeoutError, ssl.SSLWantReadError, ssl.SSLWantWriteError)):
        return True
    if isinstance(e, BlockingIOError):
        return getattr(e, "errno", None) in (errno.EAGAIN, errno.EWOULDBLOCK)
    return getattr(e, "errno", None) in (errno.EAGAIN, errno.EWOULDBLOCK)


def checksum(data):
    if len(data) % 2:
        data += b"\x00"
    s = sum(struct.unpack("!%dH" % (len(data) // 2), data))
    s = (s >> 16) + (s & 0xffff)
    s += s >> 16
    return (~s) & 0xffff


def nem(cmd, payload=b""):
    return MAGIC + bytes([1, cmd]) + struct.pack(">H", len(payload)) + payload


def recv_exact(t, n, frame_started=False):
    """
    Read exactly n bytes without discarding a partially received NEM frame.
    iSH can raise EAGAIN / SSLWantRead between chunks.
    """
    out = bytearray()
    while len(out) < n:
        try:
            x = t.recv(n - len(out))
        except Exception as e:
            if is_retryable_io_error(e):
                if out or frame_started:
                    time.sleep(0.005)
                    continue
                raise
            raise

        if not x:
            raise EOFError("VPN TLS closed")

        out += x

    return bytes(out)


def recv_nem(t):
    h = recv_exact(t, 8)
    if h[:4] != MAGIC:
        raise RuntimeError("Bad NEM magic: " + h.hex(" "))
    ln = struct.unpack(">H", h[6:8])[0]
    return h, recv_exact(t, ln, frame_started=True)


def tlv(t, v):
    return struct.pack(">HH", t, len(v)) + v


def esc(s):
    return s.replace("%", "%25").replace("&", "%26").replace("+", "%2B")


def stable_mac(username):
    h = bytearray(hashlib.sha256((username + "|" + VPN_HOST).encode()).digest()[:6])
    h[0] = (h[0] | 0x02) & 0xFE
    hx = "".join(f"{b:02X}" for b in h)
    return f"{hx[:4]}-{hx[4:8]}-{hx[8:12]}"


def tls_connect(timeout=10):
    ctx = ssl.create_default_context(cafile=CA_FILE)
    if INSECURE or CERT_SHA256:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    s = socket.create_connection((VPN_HOST, VPN_PORT), timeout=timeout)
    try:
        t = ctx.wrap_socket(s, server_hostname=SERVER_NAME or VPN_HOST)
        if CERT_SHA256:
            actual = hashlib.sha256(t.getpeercert(binary_form=True)).hexdigest()
            if not hmac.compare_digest(actual, CERT_SHA256):
                t.close()
                raise ssl.SSLCertVerificationError("Server certificate SHA-256 mismatch")
        t.settimeout(timeout)
        return t
    except BaseException:
        s.close()
        raise


def firstconnect_packet():
    p = (
        b"\xfe\xfc\xef\xbe"
        b"\xc1\x92\xa4\xd6"
        b"\x00\x00\x00\x00"
        b"\x00\x1d"
        b"\x01\x44"
        + b"\x00" * 64
        + DOMAIN.encode() + b"\x00" * (256 - len(DOMAIN.encode()))
        + b"\x00\x01\x00\x00"
    )
    assert len(p) == 340
    return p


def build_tcp(src_ip, dst_ip, src_port, dst_port, seq, ack, flags, payload=b""):
    src = socket.inet_aton(src_ip)
    dst = socket.inet_aton(dst_ip)

    offset = 5
    window = 65535

    tcp0 = struct.pack(
        "!HHIIBBHHH",
        src_port, dst_port, seq, ack,
        offset << 4, flags, window, 0, 0
    ) + payload

    pseudo = src + dst + struct.pack("!BBH", 0, socket.IPPROTO_TCP, len(tcp0))
    tcp_ck = checksum(pseudo + tcp0)

    tcp = struct.pack(
        "!HHIIBBHHH",
        src_port, dst_port, seq, ack,
        offset << 4, flags, window, tcp_ck, 0
    ) + payload

    total_len = 20 + len(tcp)
    ident = random.randint(0, 65535)

    ip0 = struct.pack(
        "!BBHHHBBH4s4s",
        0x45, 0, total_len, ident, 0x4000,
        64, socket.IPPROTO_TCP, 0, src, dst
    )
    ip_ck = checksum(ip0)

    iphdr = struct.pack(
        "!BBHHHBBH4s4s",
        0x45, 0, total_len, ident, 0x4000,
        64, socket.IPPROTO_TCP, ip_ck, src, dst
    )

    return iphdr + tcp


def parse_ipv4_tcp(pkt):
    if len(pkt) < 20 or (pkt[0] >> 4) != 4 or pkt[9] != socket.IPPROTO_TCP:
        return None

    ihl = (pkt[0] & 0x0f) * 4
    if ihl < 20 or len(pkt) < ihl + 20:
        return None

    src = socket.inet_ntoa(pkt[12:16])
    dst = socket.inet_ntoa(pkt[16:20])

    tcp = pkt[ihl:]
    sport, dport, seq, ack = struct.unpack("!HHII", tcp[:12])
    off = (tcp[12] >> 4) * 4
    if off < 20 or len(tcp) < off:
        return None

    flags = tcp[13]
    return {
        "src": src,
        "dst": dst,
        "sport": sport,
        "dport": dport,
        "seq": seq,
        "ack": ack,
        "flags": flags,
        "syn": bool(flags & 0x02),
        "ack_flag": bool(flags & 0x10),
        "rst": bool(flags & 0x04),
        "fin": bool(flags & 0x01),
        "payload": tcp[off:],
    }


class UniVPNSession:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.mac = stable_mac(username)

        self.ctl = None
        self.data = None

        self.token = None
        self.vip = None

        self.src_port = None
        self.client_seq = None
        self.server_next = None

        self.send_lock = threading.Lock()
        self.ctl_send_lock = threading.Lock()
        self.state_lock = threading.Lock()
        self.closed = threading.Event()
        self.keepalive_thread = None
        self.control_keepalive_thread = None
        self.control_reader_thread = None
        self.control_tick0 = time.monotonic()

    def login(self):
        self.ctl = tls_connect()

        self.ctl.sendall(firstconnect_packet())
        h, p = recv_nem(self.ctl)
        if h[5] != 0 or p != b"\x00\x00\x00\x00":
            raise RuntimeError("FirstConnect failed")

        u = esc(self.username).encode() + b"\x00"
        pw = esc(self.password).encode() + b"\x00"
        m = self.mac.encode()

        base = (
            DOMAIN.encode()
            + b"\x00" * (256 - len(DOMAIN.encode()))
            + b"\x00\x00\x00\x00"
        )
        auth = nem(0x01, base + tlv(1, u) + tlv(2, pw) + tlv(3, m))

        self.ctl.sendall(auth)
        h, p = recv_nem(self.ctl)

        if h[5] != 1 or len(p) < 8:
            raise RuntimeError("Unexpected auth response")

        result = struct.unpack(">I", p[:4])[0]
        if result != 0:
            raise RuntimeError(f"VPN auth failed: {result}")

        pos = 8
        while pos + 4 <= len(p):
            typ, ln = struct.unpack(">HH", p[pos:pos+4])
            pos += 4
            if pos + ln > len(p):
                break
            v = p[pos:pos+ln]
            if typ == 3 and ln >= 32:
                self.token = v[:32]
            pos += ln

        if self.token is None:
            raise RuntimeError("VPN token not found")

        self.ctl.sendall(nem(0x03, self.token))
        h, p = recv_nem(self.ctl)
        if h[5] != 3 or not p or p[0] != 0:
            raise RuntimeError("REQVIP failed")

        pos = 4
        while pos + 4 <= len(p):
            typ, ln = struct.unpack(">HH", p[pos:pos+4])
            pos += 4
            if pos + ln > len(p):
                break
            v = p[pos:pos+ln]
            if typ == 1 and ln == 5:
                self.vip = str(ipaddress.IPv4Address(v[:4]))
            pos += ln

        if self.vip is None:
            raise RuntimeError("VIP not found")

        self.data = tls_connect()
        self.data.sendall(nem(0x64, self.token))
        h, p = recv_nem(self.data)
        if h[5] != 0x64 or p != b"\x00":
            raise RuntimeError("DATA_CONNECT failed")

        self.data.settimeout(1.0)
        self.ctl.settimeout(1.0)

        # Official UniVPN v1 control-channel detective:
        # every 10 seconds send cmd=0x06 with token[32] + elapsed_ms[4].
        self.control_tick0 = time.monotonic()
        self.control_keepalive_thread = threading.Thread(
            target=self._control_keepalive_loop,
            daemon=True,
            name="univpn-control-keepalive",
        )
        self.control_reader_thread = threading.Thread(
            target=self._control_reader_loop,
            daemon=True,
            name="univpn-control-reader",
        )
        self.control_keepalive_thread.start()
        self.control_reader_thread.start()

        # Official UniVPN v1 creates a 15-second data-channel detective timer
        # and sends CMD_DATA_KEEPALIVE_V1 (0x65) with an empty payload.
        self.keepalive_thread = threading.Thread(
            target=self._data_keepalive_loop,
            daemon=True,
            name="univpn-data-keepalive",
        )
        self.keepalive_thread.start()

    def _control_keepalive_loop(self):
        count = 0
        while not self.closed.wait(10.0):
            try:
                elapsed_ms = int(
                    (time.monotonic() - self.control_tick0) * 1000
                ) & 0xffffffff
                payload = self.token + struct.pack(">I", elapsed_ms)
                frame = nem(0x06, payload)

                with self.ctl_send_lock:
                    self.ctl.sendall(frame)

                count += 1
                print(
                    f"  control-keepalive TX #{count} elapsed_ms={elapsed_ms}",
                    flush=True,
                )
            except Exception as e:
                if not self.closed.is_set():
                    print(
                        f"  control-keepalive: {type(e).__name__}: {e}",
                        flush=True,
                    )
                break

    def _control_reader_loop(self):
        while not self.closed.is_set():
            try:
                h, p = recv_nem(self.ctl)
            except Exception as e:
                if is_retryable_io_error(e):
                    continue
                if not self.closed.is_set():
                    print(
                        f"  control-reader: {type(e).__name__}: {e}",
                        flush=True,
                    )
                break

            if len(h) == 8:
                cmd = h[5]
                if cmd == 0x06:
                    print(
                        f"  control-keepalive RX payload_len={len(p)}",
                        flush=True,
                    )
                else:
                    print(
                        f"  control RX cmd=0x{cmd:02x} payload_len={len(p)}",
                        flush=True,
                    )

    def _data_keepalive_loop(self):
        while not self.closed.wait(15.0):
            try:
                frame = nem(0x65, b"")
                with self.send_lock:
                    self.data.sendall(frame)
                print("  data-keepalive TX", flush=True)
            except Exception as e:
                if not self.closed.is_set():
                    print(
                        f"  data-keepalive: {type(e).__name__}: {e}",
                        flush=True,
                    )
                break

    def send_ip(self, pkt):
        frame = nem(0x66, b"\x00" * 8 + pkt)
        with self.send_lock:
            self.data.sendall(frame)

    def connect_remote_tcp(self):
        self.src_port = random.randint(40000, 60000)
        isn = random.randint(1, 0xffffffff)

        self.client_seq = (isn + 1) & 0xffffffff

        syn = build_tcp(
            self.vip, REMOTE_HOST,
            self.src_port, REMOTE_PORT,
            isn, 0, 0x02
        )
        self.send_ip(syn)

        deadline = time.time() + 8
        while time.time() < deadline:
            try:
                h, p = recv_nem(self.data)
            except Exception as e:
                if is_retryable_io_error(e):
                    continue
                raise

            if h[5] != 0x66 or len(p) < 9:
                continue

            info = parse_ipv4_tcp(p[8:])
            if not self.matches_remote(info):
                continue

            if info["rst"]:
                raise RuntimeError("Remote TCP reset during connect")

            if info["syn"] and info["ack_flag"]:
                self.server_next = (info["seq"] + 1) & 0xffffffff
                ack = build_tcp(
                    self.vip, REMOTE_HOST,
                    self.src_port, REMOTE_PORT,
                    self.client_seq, self.server_next, 0x10
                )
                self.send_ip(ack)
                return

        raise RuntimeError("Remote TCP connect timed out")

    def matches_remote(self, info):
        return bool(
            info
            and info["src"] == REMOTE_HOST
            and info["dst"] == self.vip
            and info["sport"] == REMOTE_PORT
            and info["dport"] == self.src_port
        )

    def send_stream(self, data):
        pos = 0
        while pos < len(data):
            chunk = data[pos:pos + MSS]
            with self.state_lock:
                seq = self.client_seq
                ack = self.server_next

            pkt = build_tcp(
                self.vip, REMOTE_HOST,
                self.src_port, REMOTE_PORT,
                seq, ack,
                0x18,  # PSH|ACK
                chunk
            )
            self.send_ip(pkt)

            with self.state_lock:
                self.client_seq = (self.client_seq + len(chunk)) & 0xffffffff

            pos += len(chunk)

    def ack_remote(self):
        with self.state_lock:
            seq = self.client_seq
            ack = self.server_next

        pkt = build_tcp(
            self.vip, REMOTE_HOST,
            self.src_port, REMOTE_PORT,
            seq, ack, 0x10
        )
        self.send_ip(pkt)

    def close(self):
        if self.closed.is_set():
            return

        self.closed.set()

        try:
            if self.data and self.client_seq is not None and self.server_next is not None:
                with self.state_lock:
                    seq = self.client_seq
                    ack = self.server_next

                fin = build_tcp(
                    self.vip, REMOTE_HOST,
                    self.src_port, REMOTE_PORT,
                    seq, ack, 0x11  # FIN|ACK
                )
                self.send_ip(fin)
        except Exception:
            pass

        for s in (self.data, self.ctl):
            try:
                if s:
                    s.close()
            except Exception:
                pass


def relay(local, username, password):
    vpn = UniVPNSession(username, password)

    try:
        print("  [1/4] VPN login...", flush=True)
        vpn.login()
        print(f"  [2/4] VIP {vpn.vip}", flush=True)

        print(f"  [3/4] TCP -> {REMOTE_HOST}:{REMOTE_PORT}...", flush=True)
        vpn.connect_remote_tcp()
        print("  [4/4] Connected. Relaying TCP.", flush=True)

        stop = threading.Event()

        def local_to_remote():
            try:
                while not stop.is_set():
                    b = local.recv(32768)
                    if not b:
                        break
                    vpn.send_stream(b)
            except Exception as e:
                if not stop.is_set():
                    print(f"  local->remote: {type(e).__name__}: {e}", flush=True)
            finally:
                stop.set()

        def remote_to_local():
            try:
                while not stop.is_set():
                    try:
                        h, p = recv_nem(vpn.data)
                    except Exception as e:
                        if is_retryable_io_error(e):
                            continue
                        raise

                    if h[5] != 0x66 or len(p) < 9:
                        if len(h) == 8 and h[5] == 0x65:
                            print(
                                f"  data-keepalive RX payload_len={len(p)}",
                                flush=True,
                            )
                        elif len(h) == 8:
                            print(
                                f"  data RX cmd=0x{h[5]:02x} payload_len={len(p)}",
                                flush=True,
                            )
                        continue

                    info = parse_ipv4_tcp(p[8:])
                    if not vpn.matches_remote(info):
                        continue

                    if info["rst"]:
                        print("  Remote sent RST", flush=True)
                        break

                    payload = info["payload"]
                    seq = info["seq"]

                    if payload:
                        deliver = b""

                        with vpn.state_lock:
                            expected = vpn.server_next

                            if seq == expected:
                                deliver = payload
                                vpn.server_next = (
                                    vpn.server_next + len(payload)
                                ) & 0xffffffff

                            elif seq < expected:
                                # Duplicate segment; ACK current state.
                                deliver = b""

                        if deliver:
                            local.sendall(deliver)

                        vpn.ack_remote()

                    if info["fin"]:
                        with vpn.state_lock:
                            if info["seq"] == vpn.server_next:
                                vpn.server_next = (vpn.server_next + 1) & 0xffffffff
                            elif payload and (
                                info["seq"] + len(payload)
                            ) == vpn.server_next:
                                vpn.server_next = (vpn.server_next + 1) & 0xffffffff

                        vpn.ack_remote()
                        break

            except Exception as e:
                if not stop.is_set():
                    print(f"  remote->local: {type(e).__name__}: {e}", flush=True)
            finally:
                stop.set()

        a = threading.Thread(target=local_to_remote, daemon=True)
        b = threading.Thread(target=remote_to_local, daemon=True)
        a.start()
        b.start()

        while not stop.wait(0.2):
            pass

    finally:
        vpn.close()
        try:
            local.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        local.close()
        print("  Session closed.", flush=True)


# Compatibility TCP forwarder



Requires Python 3.9 or newer. Download the source `.tar.gz` from this repository's GitHub Releases and unpack it:

```sh
tar -xzf univpn_tcp_forward-0.1.0a1.tar.gz
cd univpn_tcp_forward-0.1.0a1
```

From this directory, no installation, third-party Python dependency, administrator privilege or `uv` is required.

```sh
python3 -m univpn_forward \
  --gateway vpn.example.com \
  --target 10.0.0.2 --target-port 22 \
  --listen-port 2222
```

Replace the gateway, internal destination and destination port with your own values. Enter your VPN username and password at the prompts. `READY` means the localhost listener is ready; VPN authentication happens when a client connects.

In another terminal, connect to the destination's SSH server:

```sh
ssh -o HostKeyAlias=10.0.0.2 -p 2222 your-user@127.0.0.1
```

The SSH account is separate from the VPN account. `HostKeyAlias` identifies the actual destination rather than the local forwarding endpoint. Verify the destination's host key when connecting for the first time.

Optional gateway settings:

- `--gateway-port 443`: external TLS port.
- `--domain AUTH_DOMAIN`: authentication domain; defaults to the gateway.
- `--server-name vpn.example.com`: certificate hostname/SNI when connecting to a gateway IP.
- `--ca-file /path/to/trusted-ca.pem`: a trusted private CA bundle.
- `--cert-sha256 FULL_SHA256`: pin a trusted leaf certificate, instead of CA/hostname validation.

TLS certificate verification is enabled by default. Obtain a private CA or certificate fingerprint through a trusted channel. A fingerprint read from an unverified first connection only provides trust on first use, not proof of server identity. `--insecure` is available explicitly for diagnostics; it is not the default connection method.

## Credentials and unattended use

Interactive input keeps passwords out of command arguments. For unattended use, create a private JSON file using your editor:

```json
{"username": "YOUR_VPN_USERNAME", "password": "YOUR_VPN_PASSWORD"}
```

```sh
chmod 600 credentials.local.json
python3 -m univpn_forward \
  --gateway vpn.example.com --target 10.0.0.2 --target-port 22 \
  --credentials-file credentials.local.json
```

Credential JSON files are ignored by Git. Do not publish them or protocol captures containing authentication/session data. Ordinary diagnostic logs include endpoint addresses and assigned VPN addresses, but never intentionally print passwords or session tokens.

On macOS, `--keychain-service YOUR_SERVICE --keychain-account gateway` can read a generic-password Keychain item whose secret is the same JSON object. Creating that item is a separate local setup step; the tool does not change your Keychain, SSH configuration, routes or startup services.

Keep the forwarder process running. SSH `ControlMaster`/`ControlPersist` can reuse an established SSH connection and avoid repeated VPN handshakes; this prototype itself authenticates a new VPN session for each accepted local TCP connection.

## iSH on iPhone

Download the release source archive and make it available in iSH. Install the system tools, unpack it, and run the same command:

```sh
apk add python3 openssh-client
tar -xzf univpn_tcp_forward-0.1.0a1.tar.gz
cd univpn_tcp_forward-0.1.0a1
python3 -m univpn_forward \
  --gateway vpn.example.com --target 10.0.0.2 --target-port 22
```

In a second iSH shell, forward a remote web service to the phone:

```sh
ssh -N -o HostKeyAlias=10.0.0.2 \
  -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
  -L 127.0.0.1:8765:127.0.0.1:8765 \
  -p 2222 your-user@127.0.0.1
```

Open `http://127.0.0.1:8765` on the phone. The remote service must already listen on port 8765. iOS can suspend iSH; background lifetime depends on the device and iSH. The packaged version has not yet been tested on a physical iPhone, although the predecessor script was used there.

## Scope and limitations

- IPv4 TCP, one destination per forwarder process; no UDP, IPv6, DNS tunnel or system-wide routing.
- Password authentication as observed on one gateway; no MFA, browser SSO or certificate authentication.
- Two TLS channels per VPN session, with control/data heartbeats.
- The user-space TCP implementation is minimal: it is not a complete TCP stack and lacks general retransmission, out-of-order buffering and comprehensive sequence-wrap handling. Bulk-transfer and idle tests do not establish reliability on every network.
- Local clients share the configured VPN credentials. Only loopback binding is supported; other local processes can still connect.
- Linux/iSH use the portable Python code; only macOS live network testing is recorded so far. Windows compatibility is not claimed.

For a complete VPN implementation, see the [OpenConnect contribution plan](docs/openconnect.md). This prototype is useful as protocol documentation and interoperability evidence, rather than a Python patch directly mergeable into OpenConnect's C codebase.

## Development

```sh
python3 -m unittest discover -s tests -v
python3 -m univpn_forward --help
```

The included GitHub Actions workflow runs these tests on macOS and Linux with Python 3.9 and 3.12. A successful CI run tests code without contacting any private VPN gateway.

MIT license. No official vendor binaries, gateway configuration, credentials or captured sessions are included.

See [contribution guidelines](CONTRIBUTING.md), [changelog](CHANGELOG.md), and [release procedure](docs/releasing.md).

# Validation record

Recorded 2026-10-09 on macOS, Apple Silicon (arm64). This report intentionally omits private endpoints, usernames, certificate fingerprints and session identifiers.

## Automated tests

13 tests passed under Python 3.12.12 and 3.14.5:

- Fragmented NEM frames and a timeout between header/body retain framing.
- Idle timeouts, EOF and invalid frame magic are handled.
- UTF-8 authentication-domain padding remains the required byte length.
- IPv4/TCP payload round-trip and both checksums match.
- Malformed IPv4/TCP header offsets are rejected.
- Default TLS requires certificate/hostname validation.
- A matching certificate pin is accepted; a mismatch closes the socket.
- A partial fingerprint is rejected.
- Credential files must have private permissions and valid contents.

The CI workflow is prepared for Python 3.9/3.12 on Linux and macOS. It has not yet run on GitHub for this independent repository.

## Live gateway test

The new package ran on a separate loopback port. The existing private forwarder, SSH configuration and application services were left unchanged. Each test SSH connection explicitly disabled connection multiplexing, used the new port and retained SSH host-key checking.

| Test | Result |
| --- | --- |
| Incorrect TLS certificate pin rejected before VPN authentication | Passed |
| Fresh SSH login through the new forwarder | Passed |
| Remote application HTTP health check through SSH | Passed |
| 256 KiB random binary upload; remote SHA-256 equals local SHA-256 | Passed |
| 256 KiB binary download; full content comparison | Passed |
| Established SSH connection idle for 65 seconds, then echo request | Passed |
| Second fresh SSH connection while the first remained established | Passed |

The test gateway's certificate failed system CA verification (verification code 20). Live testing used a full fingerprint observed on the first connection. This is trust on first use, not independent authentication of the gateway. Default verification remains enabled in the distributed code.

This validates one gateway and a short idle interval. It does not establish multi-hour stability, universal UniVPN compatibility or a complete TCP implementation. Physical iPhone testing of the new package, additional gateways, Linux live tests and Windows support remain unverified.

## Packaging and privacy

The wheel and source archive are built locally and inspected for unexpected files. Private live-test scripts, logs and configuration reside in ignored `.local/`; they are excluded from distribution. The public repository starts with a fresh history rather than copying historical personal configuration from the application repository.

## Alpha release preparation

For `0.1.0a1`, the wheel installed and reported its version from outside the source directory. The source archive was extracted to a temporary directory and all 13 tests passed there. Release-note extraction, mismatched-tag rejection and YAML/shell/embedded-Python syntax checks passed locally. The GitHub-hosted workflow has not run yet; these checks are not a GitHub CI pass claim.

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

The CI workflow is prepared for Python 3.9/3.12 on Linux, Windows and macOS. It has not yet run on GitHub for this independent repository.

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


## Native client work in progress — 2026-10-09

- Native OpenConnect on macOS arm64: builds against upstream `70d1e79d1e55849dfc71dcc199b1edb535b547e4`.
- ASan/UBSan build: six loopback TLS gateway integration tests and four C tests passed. The integration uses `--script-tun`; it does not install routes or prove OS TUN behavior.
- Live native authentication, assigned IPv4 and route metadata parsing: passed.
- Live native IPv4: TCP SYN-ACK and an ICMP port-unreachable response to a UDP probe received. ICMP Echo reply not observed. No subnet scanning.
- Private gateway identity during live probes: full first-observed SPKI pin; not independent CA verification.
- macOS Keychain: separate disposable item save/read/delete passed.
- Management tests: configuration, credentials, cancellation, timeouts, local IPC and route rollback tested. CLI service exercised locally.
- System routing and desktop interaction on Mac: see the completed checks below. Non-Mac physical hardware remains pending.
- No GitHub repository, GitLab account or formal MR created for this expanded project.

Two-hour legacy forwarder soak: failed to resume SSH echo after idle. Both VPN channels continued acknowledging heartbeats. The cause is not yet established; a live outer tunnel alone is insufficient evidence of a healthy inner TCP session.

## Native macOS system networking — 2026-10-09

The user completed macOS administrator authorization for a temporary native
connection with one GPU host's /32 route. The bundled OpenConnect and dynamic
libraries ran without a Homebrew loader path. The existing private forwarder
was preserved.

| Real system-stack check | Result |
| --- | --- |
| Allocated macOS utun and target /32 route | Passed |
| Fresh direct SSH over the native route, without localhost forwarding | Passed |
| Remote HTTP application health through direct SSH | Passed |
| 1 MiB random upload SHA256 | Passed |
| 1 MiB download full comparison | Passed |
| 180-second idle SSH with ServerAliveInterval=15 | Passed |
| Desktop disconnect, target route removed, state disconnected | Passed |
| Original private localhost forwarder still listening afterward | Passed |

The separate compatibility forwarder also passed a three-minute idle test
with SSH keepalives and a concurrent fresh connection. This does not overturn
the failed two-hour test without application keepalives. Multi-hour native
stability and real other-platform networking are not yet established.

Desktop interaction on the built macOS app: launch/render, add/edit gateway,
connection switch, OS authorization, disconnect, settings navigation and
light/system appearance were exercised. Polling was changed to preserve list
controls when configuration is unchanged. A native-button color issue during
light/dark switching was found and fixed with explicit CSS appearance; the
final rebuilt app passed that visual recheck. No read-password API
is exposed.

Latest management suite: 44 tests on macOS, including accepted private-pin
warnings versus fatal trust errors and route cleanup rejecting unauthorized
prefixes. Six native TLS integration tests pass on the current OpenSSL build;
the earlier ASan/UBSan GnuTLS build passed six integrations and four C tests.
The two TLS backends and sanitizer runs are separate evidence.

A Cocoa SAVE-return regression was found: pywebview returns a single path string on macOS, while OPEN returns a tuple. Export now handles both without truncating to the first character; a regression test reproduces the backend contract. The rebuilt macOS app completed native export and import; exported JSON parsed successfully, contained no password and the UI confirmed import.

## Linux arm64 virtual-machine build — 2026-10-09

Ubuntu 24.04 arm64 in an isolated VM on the Mac compiled the pinned source
and all four patches. Six loopback TLS integrations and four C tests passed.
The first native test exposed a missing primary TLS descriptor registration
under epoll; the fourth patch fixes it, and the same integration then passed.
The desktop executable froze successfully; deb and portable archives were
created, and the frozen CLI reported 0.2.0a1. This verifies a Linux build and
script-tun transport, not physical Linux desktop or privileged network use.
Windows x64, Linux x64 and Intel Mac hosted builds remain pending.

Frozen CLI profile add/list/shutdown passed from extracted Ubuntu arm64 deb
and the Mac bundle. Account edit on Mac leaves the password field empty and
cancel preserves the account. The Windows compatibility-forwarder credential
file path is explicitly unsupported because chmod cannot establish its ACL;
interactive authentication and the native client credential store are separate.

The final management suite passed 44 tests on both Mac and the Ubuntu arm64
VM. Linux desktop rendering and system network use remain separate gates. Linux desktop rendering and system
keychain/UAC equivalents were not tested inside the headless build VM.

Release tar headers are neutralized (UID/GID, user/group names and PAX
time metadata). A regression test confirms content and executable mode are
preserved. Private-value scans include file contents and archive metadata.

The final Linux package excludes copied OS GTK/WebKit shared libraries and
typelibs and declares the corresponding runtime dependencies. Its frozen CLI
service/status/shutdown passed again after removal. Binding source archives
(PyGObject/pycairo on Linux, PyObjC core on Mac) and source SHA256 manifests
are included; verified upstream source archives remain unchanged.

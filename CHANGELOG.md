# Changelog

## 0.1.0a1 — 2026-10-09

First public alpha candidate. This version is experimental and tested against one authorized gateway.

- Single-target IPv4 TCP forwarding using two UniVPN TLS channels.
- Password authentication, virtual address allocation and independent control/data heartbeats.
- Runtime gateway/target configuration and loopback-only listener.
- Default TLS verification, private CA and full certificate fingerprint options.
- Interactive, private-file and macOS Keychain credential sources.
- Preserve partial protocol frames across timeouts; correct UTF-8 domain padding.
- Protocol documentation, Mac/iSH instructions, 13 automated tests and redacted live validation.
- Python wheel/source archives and GitHub CI/release workflows.

No full VPN/TUN, UDP, IPv6, MFA, browser SSO or universal gateway compatibility is claimed. New-package physical iPhone validation and live Linux/Windows testing remain outstanding.

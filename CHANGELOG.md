# Changelog

## 0.2.0 — 2026-10-09

Native client preview; not a universal VPN compatibility claim.

- OpenConnect UniVPN IPv4/TLS transport, public patches and reproducible pinned source.
- Multiple gateway profiles and secure saved accounts; shared desktop/CLI service.
- Temporary OS authorization, explicit split routes and scoped rollback.
- Local desktop UI with connection, profiles, accounts, logs and light/dark/system themes.
- macOS arm64 app and native network testing; Intel Mac/Windows/Linux packaging recipes and workflows prepared separately.
- Native loopback TLS, C parser and Python management tests; documented live and long-idle limits.


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

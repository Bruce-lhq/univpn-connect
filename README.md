# UniVPN Connect

[![CI](https://github.com/Bruce-lhq/univpn-connect/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/Bruce-lhq/univpn-connect/actions/workflows/tests.yml)
[![Desktop builds](https://github.com/Bruce-lhq/univpn-connect/actions/workflows/desktop.yml/badge.svg?branch=main)](https://github.com/Bruce-lhq/univpn-connect/actions/workflows/desktop.yml)

An experimental desktop and CLI client for the password-authentication / IPv4-over-TLS subset observed on a UniVPN gateway. It uses a patched OpenConnect core and your operating system’s TCP/IP stack.

Save multiple gateway profiles and accounts, switch between them, inspect connection logs, and choose light, dark or system appearance. Passwords stay in the system credential store; configuration exports contain no passwords. The desktop interface follows the compact connection-and-profile organization of Shadowrocket, with original assets and styling.

**Current version: 0.2.0 alpha 1.** One real gateway and macOS Apple Silicon have been tested. This is not a claim of compatibility with every Huawei / UniVPN product. See the [validation record](docs/validation.md) before deploying it.

## Install and connect

Installer builds are prepared locally; this project has not yet been published to a new GitHub repository. Choose the package matching your machine:

| Platform | Package | CLI |
| --- | --- | --- |
| macOS Apple Silicon / Intel | `.dmg`, drag UniVPN Connect to Applications | executable inside the app, or CLI archive |
| Windows x64 | `-setup.exe` or portable `.zip` | `univpn-client.cmd` in the installed/portable folder |
| Ubuntu 24.04 x64 / arm64 | `.deb` or portable `.tar.gz` | `univpn-client` after installing the deb |

The macOS arm64 package is built and exercised locally. Ubuntu 24.04 arm64 packages and native mock tests were built in an isolated Linux VM on that Mac; physical Linux desktop/network tests remain pending. Intel Mac, Windows and Linux x64 workflows are prepared but not yet run on their hosts; those packages are not presented as tested downloads. Packages are not notarized or signed by a commercial publisher. macOS uses local ad-hoc signatures required to execute Apple Silicon code; this is not Apple developer signing. Follow your system’s normal approval flow, rather than disabling global security protections.

In the app:

1. Add a **gateway**: hostname, TLS port and authentication domain. Leave the domain empty to use the hostname. Add explicit IPv4 routes, for example `10.20.0.0/16` or one host’s `10.20.1.5/32`.
2. Add an **account**: a label, VPN username and password. You may save several accounts independently of gateway profiles.
3. Select a gateway and account, then turn on the connection switch. Approve the temporary system network helper when prompted.
4. Connect your ordinary applications to the internal addresses. Turn off the switch to disconnect.

Certificate and hostname validation are on by default. For a private CA, specify its certificate file. Alternatively use a full `pin-sha256:…` public-key pin obtained through a trusted channel. Reading a fingerprint from an unverified first connection is only trust on first use. There is no desktop “ignore all certificate errors” option.

Closing the window keeps the connection service running. **Settings → Stop service** disconnects and exits the service. Only one gateway is active at a time; disconnect before switching or deleting an active profile/account. A channel failure triggers bounded fresh-authentication retries; invalid credentials and certificate failures are not retried indefinitely.

## CLI

The CLI shares profiles, accounts, connection state and logs with the desktop.

```sh
univpn-client profiles add --name Work --host vpn.example.com --route 10.20.0.0/16
univpn-client accounts add --name Work --username your-vpn-user
univpn-client profiles list
univpn-client accounts list
univpn-client connect --profile PROFILE_ID --account ACCOUNT_ID
univpn-client status
univpn-client logs
univpn-client disconnect
```

The account command prompts for a password; never put it in command arguments. Use `univpn-client --help` for import/export and editing commands. On macOS the same commands can use:

```sh
"/Applications/UniVPN Connect.app/Contents/MacOS/UniVPN Connect" status
```

Linux requires GTK/WebKitGTK, a running Secret Service credential store and PolicyKit. The deb declares its runtime dependencies. Windows uses Windows Credential Manager, UAC and the bundled official Wintun driver. OS administrator authorization is separate from the VPN password.

## Build from source

Requires Python 3.9+ for the Python source, Python 3.12 for the provided desktop build recipes, Node for JavaScript syntax checks, and the native development tools described in [building](docs/building.md). A Python wheel alone does not contain the OpenConnect binary or produce a working VPN connection.

```sh
python3 -m unittest discover -s tests -v
node --check univpn_client/ui/app.js
python3 scripts/prepare_native.py
```

Use the platform recipe to build and stage OpenConnect, then:

```sh
uv pip install '.[desktop,build]'
python3 scripts/dependency_sources.py
python3 scripts/build_desktop.py
python3 scripts/package_desktop.py
```

`uv` is only a build-time dependency manager here. Users of desktop/CLI bundles do not need Python or uv. The original zero-dependency [TCP compatibility forwarder](docs/compatibility-forwarder.md) remains available, including an iSH example; it does not provide native VPN routing and has a documented long-idle failure.

## Architecture and scope

```text
Desktop / CLI → authenticated local IPC → user connection service
                                        → temporary OS-authorized helper
                                        → patched OpenConnect → TLS gateway
                                        → OS utun / TUN / Wintun + explicit routes
```

The user service owns configuration and system-keychain access. The privileged helper receives one validated job through private IPC, owns its native process and route session, and cleans up on disconnect or IPC loss. Passwords travel through protected IPC and the native process’s stdin, not command arguments or exported JSON. The local WebView loads bundled assets; it has no password-reading API and no privileged HTTP API.

The current native implementation supports IPv4 over two TLS channels and explicit split routes. It intentionally does not modify global DNS or default routes. IPv6, DTLS, MFA, browser SSO, compression, universal firmware support and seamless session renewal are not implemented. Cookie-only startup after a separate `--authenticate` invocation is unsupported because the observed session token is bound to a live control channel. Multiple accounts do not mean multiple simultaneous VPN connections.

## Development and contribution

- [Five-stage design](docs/design.md) and [implementation plan](docs/implementation.md)
- [Protocol observations](docs/protocol.md), [validation](docs/validation.md) and [native build recipes](docs/building.md)
- [OpenConnect contribution preparation](docs/openconnect.md)
- [Release preparation](docs/releasing.md) and [changelog](CHANGELOG.md)

The management/desktop code is MIT licensed. The modified OpenConnect core retains LGPL-2.1 terms; bundled dependencies retain their own licenses. See [third-party notices](THIRD_PARTY_NOTICES.md). Matching source and public patches accompany native releases; the native executable and libopenconnect remain separate and replaceable.

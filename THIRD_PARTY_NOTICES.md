# Third-party notices and source correspondence

The `univpn_client` and compatibility Python management code are MIT licensed.
This does **not** relicense the bundled VPN core or any third-party runtime.

- OpenConnect: LGPL-2.1. The pinned upstream revision and public
  patches are in `native/openconnect/`; native artifacts include its license
  and a matching, patched source archive. The separate executable and dynamic
  `libopenconnect` are replaceable; they are not statically incorporated into
  the Python manager.
- OpenSSL: Apache-2.0. macOS and Windows bundles include dynamically linked
  libraries and a license notice. Record the exact build version in the
  native manifest; obtain the corresponding source from the official OpenSSL
  release with that version. Linux uses its distribution's system package.
- Windows Wintun: the official unmodified driver is bundled with its COPYING
  file. It retains the license of the official distribution; no locally built
  or unsigned replacement driver is installed.
- Windows MinGW dependencies: licenses from the build distribution are
  included in the native licenses directory. The toolchain manifest and
  dependency source correspondence must be recorded before publishing a
  Windows binary; a workflow definition alone is not a verified release.
- PyGObject and pycairo (Linux): binding sources matching the installed
  versions accompany the package; their license files are bundled. GTK/WebKit
  libraries and typelibs come from declared system packages.
- PyObjC core (macOS): matching source and its missing wheel license notice
  are retrieved from the verified official source distribution.
- Python, PyInstaller, keyring, pywebview, PyObjC (macOS) and platform bindings:
  package-provided license/notice files are collected into the desktop bundle.
  PyInstaller's bootloader exception applies under its own terms.
- macOS system frameworks and Linux distribution GTK/WebKit/TLS libraries
  are OS dependencies, not relicensed or included as project source.

Release manifests and SHA256 checksums identify the actual artifacts. Do not
replace a notice with an MIT-only claim. Source archives exclude local build
logs, configuration and credentials. See `docs/building.md` and
`docs/validation.md` for what was actually built and tested.

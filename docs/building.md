# Building native desktop and CLI packages

Use a fresh source directory. The recipes prepare an exact OpenConnect
upstream archive, verify its SHA256 and apply the four public patches. No
GitLab account, personal VPN configuration or developer signing account is
required. Release artifacts must include the matching clean patched source.

## macOS arm64 or Intel

Install Python 3.12, uv and Apple's Command Line Tools on the corresponding
architecture, then native tools from Homebrew:

```sh
brew install autoconf automake libtool pkg-config openssl@3
uv venv --python 3.12
uv pip install '.[desktop,build]'
python3 scripts/prepare_native.py
cd build/openconnect
sh ../../scripts/build_native.sh
cd ../..
```

Download the license for the exact OpenSSL version reported by the built
core, from the official OpenSSL release. Then stage the build:

```sh
.venv/bin/python scripts/stage_macos_core.py --source build/openconnect --openssl-license build/OpenSSL-LICENSE.txt
.venv/bin/python scripts/dependency_sources.py
.venv/bin/python scripts/build_desktop.py
.venv/bin/python scripts/package_desktop.py
```

The stager copies only non-system libraries, changes their references to
`@loader_path`, applies local ad-hoc signatures and runs the relocated core.
If your installed SDK cannot be consumed by your linker, set `SDKROOT` to a
compatible installed SDK for this build; do not change the global SDK
selection or claim an SDK failure is a protocol failure.

The DMG contains the app and an Applications shortcut. The CLI archive
contains the same command dispatcher and libraries. Neither depends on a
Homebrew installation at runtime. UI and bundle versions derive from the
single Python version value.

## Ubuntu 24.04 x64

The prepared workflow installs autoconf, automake, libtool, pkg-config,
libssl-dev, libxml2-dev, zlib1g-dev, patchelf, libgirepository1.0-dev,
libcairo2-dev, python3-dev and gir1.2-webkit2-4.1. Install the same development packages on
an Ubuntu build host. Use a Python 3.12 virtual environment and `uv pip`
for `.[desktop,build]`, `PyGObject==3.48.2` and pycairo.

Prepare source and run `scripts/build_native.sh` inside `build/openconnect`.
Run `scripts/stage_other_core.py --source build/openconnect
--openssl-license build/OpenSSL-LICENSE.txt`, then the same freeze/package
scripts. The deb declares GTK/WebKit, OpenSSL, XML, zlib, PolicyKit,
iproute2 and a Secret Service runtime. The portable directory still needs
these OS libraries; it is not an arbitrary-distribution static executable.

## Windows x64

Build on Windows with Python 3.12 and MSYS2 MINGW64. Install the packages
listed in `.github/workflows/desktop.yml`, including MinGW GCC, OpenSSL,
libxml2, zlib and CA certificates. Compile using `scripts/build_native.sh`
inside the MINGW64 shell. Use the regular Windows Python to stage/freeze.

The stager requires the official Wintun 0.14.1 `amd64/wintun.dll` and COPYING
file, copies dependent MinGW DLLs and verifies the native executable runs.
It records hashes in `native/manifest.json`. NSIS makes the x64 installer;
the portable zip includes a hidden-window desktop launcher and a console
CLI wrapper. UAC is requested only for the network helper at connection
time. System-created administrator-only session directories are checked
for unexpected owners, ACL principals and reparse points.

Windows/macOS Intel/Linux x64 workflows are **prepared, not locally executed**.
Ubuntu 24.04 arm64 native compilation, mock integration, deb/portable
packaging and frozen CLI smoke tests passed in a Linux VM on a Mac.
Their first hosted runs and network tests on those systems remain release
gates; source syntax checks cannot replace them.

## Tests, sources and release gates

```sh
python3 -m unittest discover -s tests -v
node --check univpn_client/ui/app.js
```

`build_native.sh` runs six local TLS integration tests and four C tests on
Unix. The integration uses `--script-tun`, not privileged system routing.
Windows runs the Python management tests but needs separate native mock/TUN
coverage before compatibility can be claimed.

Build a clean corresponding-source tree by calling `prepare_native.py` with
a new destination; archive that tree before any configure/build step. Do
not package `config.log` or a working checkout with local endpoint reports.
Inspect sources, binary dependencies, bundled notices, manifests and
checksums. See the actual evidence in `validation.md`.

After `uv build`, run `python3 scripts/sanitize_archives.py dist` before
checksumming/uploading. It removes local builder names, IDs and timestamps
from project tar headers without changing file contents. Verified third-party
source archives listed in binding-sources.json stay unmodified. Desktop tar generation
already uses neutral headers; matching-source archives need the same step.

Run `scripts/dependency_sources.py` in the build environment before freezing.
It retrieves the exact installed PyObjC/PyGObject/pycairo source distributions
from PyPI with SHA256 verification, includes notices and records source hashes.
Keep these source assets beside releases. Linux packaging excludes copied
system GTK/WebKit shared libraries and typelibs; install the deb dependencies.

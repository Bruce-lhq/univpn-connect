# Releasing

The version source is `univpn_forward/__init__.py`. Package metadata reads it dynamically; the tag must be `v` followed by exactly that version. Current release: `v0.2.0`.

## Local verification

```sh
python3 -m unittest discover -s tests -v
uv build
```

Inspect the wheel and source archive for private files. Source archives include user/developer documentation and tests, but no `.local/`, credentials or live-test logs. SHA-256 checksums belong beside release assets. CI does not perform private gateway tests.

## GitHub publication

Create the public repository and add its SSH URL as `origin`. Push the reviewed branch before tagging. Neither PyPI publication nor uploading private configurations is part of the release process.

```sh
git push -u origin main
git tag v0.2.0
git push origin v0.2.0
```

The release workflow reruns tests, checks tag/version equality, builds distributions, verifies the installed wheel from outside the source directory, and attaches the wheel, source archive and `SHA256SUMS` to a GitHub Release. The workflow classifies alpha/beta/rc versions as prereleases. It uses the matching version section of `CHANGELOG.md` for release notes and marks stable releases as latest.

The workflow needs the repository's Actions token to have `contents: write` for the release job. Normal test jobs require only `contents: read`. Publishing a tag is the explicit release action; simply uploading source does not create a release.

If tests or publishing fail, inspect the failed workflow before retrying. Do not claim Linux/iPhone/gateway testing that has not occurred. Do not create a stable release solely because packaging succeeds.

## Native desktop artifacts

The separate `desktop.yml` workflow builds macOS arm64/Intel, Windows x64
and Ubuntu 24.04 packages. Run it and inspect each result before publishing
binaries. A workflow definition is not a passing hosted build. Include the
clean patched OpenConnect source, dependency notices/version manifest and
SHA256 checksums. Windows dependency source/license correspondence and
real-host network tests are still release gates. Existing Python release
workflow publishes only the wheel/sdist; desktop artifacts remain explicit
reviewed uploads until those gates pass.

Do not create the repository, account, tag or MR as part of the currently
authorized pre-publication task. Never mark a prerelease stable merely to
hide untested platforms or unsupported authentication methods.

After `uv build`, run `python3 scripts/sanitize_archives.py dist` before
checksumming/uploading. It removes local builder names, IDs and timestamps
from tar headers without changing file contents. Desktop tar generation
already uses neutral headers; matching-source archives need the same step.

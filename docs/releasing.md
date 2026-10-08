# Releasing

The version source is `univpn_forward/__init__.py`. Package metadata reads it dynamically; the tag must be `v` followed by exactly that version. Current release candidate: `v0.1.0a1`.

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
git tag v0.1.0a1
git push origin v0.1.0a1
```

The release workflow reruns tests, checks tag/version equality, builds distributions, verifies the installed wheel from outside the source directory, and attaches the wheel, source archive and `SHA256SUMS` to a GitHub Release. The workflow classifies alpha/beta/rc versions as prereleases. It uses the matching version section of `CHANGELOG.md` for release notes and marks stable releases as latest.

The workflow needs the repository's Actions token to have `contents: write` for the release job. Normal test jobs require only `contents: read`. Publishing a tag is the explicit release action; simply uploading source does not create a release.

If tests or publishing fail, inspect the failed workflow before retrying. Do not claim Linux/iPhone/gateway testing that has not occurred. Do not create a stable release solely because packaging succeeds.

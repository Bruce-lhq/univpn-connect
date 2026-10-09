# Contributing

Run the standard-library tests before proposing a change:

```sh
python3 -m unittest discover -s tests -v
```

Keep changes focused and include a regression test for framing, packet handling or authentication behavior that changes. State the Python version and platform tested. For gateway interoperability reports, describe the client/firmware version only if it is known; do not infer a product version from a successful login.

Never attach usernames, passwords, certificate private keys, session tokens, private endpoint addresses or raw authentication captures. Diagnostic logs contain endpoint/virtual addresses and must be reviewed and redacted before sharing.

Management/desktop contributions use the MIT license. OpenConnect patches retain upstream LGPL-2.1 terms and DCO requirements; see [the upstream contribution notes](docs/openconnect.md).

Build distributions with `uv build` if packaging changes. Runtime use does not require uv. GitHub Releases are prereleases while the version includes an alpha, beta or release-candidate suffix. See [releasing](docs/releasing.md).

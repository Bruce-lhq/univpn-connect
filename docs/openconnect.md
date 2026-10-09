# OpenConnect contribution preparation

The local `feature/univpn-native` branch now contains an experimental native
IPv4/TLS implementation, rather than a Python forwarder proposed as a C
patch. The pinned upstream base is recorded in
`native/openconnect/upstream.json`; four unsigned public patches cover the
protocol report, implementation/tests, and channel-protocol/documentation
follow-up, and Linux epoll registration fix. `scripts/prepare_native.py` verifies the official source archive
and applies them in order.

The upstream [Huawei SSL VPN issue #603](https://gitlab.com/openconnect/openconnect/-/issues/603)
received maintainer replies relating Huawei and Leagsoft UniVPN and inviting
protocol investigation. Existing maintainer interest does not mean this
implementation has been reviewed or accepted.

The implementation uses OpenConnect TLS validation, authentication forms,
TUN queues and the event loop. It adds a second monitored TLS connection and
retains framing/write state across partial I/O. Six local TLS gateway tests
and four C tests were run on macOS; sanitizers and live probes are documented
in [validation](validation.md). Native system routing and other-host results
must be stated separately from mock results. IPv6, DTLS, MFA, SSO, HTTP proxy
and cross-process cookie-only startup remain unsupported.

Prepared submission title: **univpn: add experimental dual-TLS IPv4 transport**.
Use a draft MR until gateway coverage and upstream architecture questions are
resolved. The submission package must include the base revision, patches,
reproduction commands, honest evidence/limits and licensing details.

Follow the upstream [contribution instructions](https://www.infradead.org/openconnect/contribute.html)
and [protocol investigation guidance](https://www.infradead.org/openconnect/mitm.html).
OpenConnect retains LGPL-2.1 licensing. Developer Certificate of
Origin sign-off requires the contributor’s own confirmed public identity
and certification; the neutral preparation commits are intentionally
unsigned and must not be submitted as fabricated sign-offs.

No GitLab account, fork, issue comment, email or MR is created by this local
preparation. Those are explicit later publication actions.

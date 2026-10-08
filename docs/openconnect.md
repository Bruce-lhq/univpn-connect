# Contributing to OpenConnect

The upstream tracker already contains [Huawei SSL VPN issue #603](https://gitlab.com/openconnect/openconnect/-/issues/603). It received maintainer responses identifying the Huawei/Leagsoft UniVPN relationship and inviting protocol investigation and review. Huawei is absent from the published [supported protocol list](https://www.infradead.org/openconnect/protocols.html) at the time this project was prepared.

This repository is a standalone TCP prototype. A useful first upstream contribution is a concise protocol report, test results and a link to this public source, with no private endpoints or authentication/session captures. Publishing or posting that report is a separate action; preparing this repository does not submit anything upstream.

A mergeable implementation would require work in OpenConnect's C architecture:

1. Validate the framing/login notes with maintainers and additional gateway observations.
2. Implement control/data TLS sessions using upstream's TLS/authentication interfaces.
3. Transfer IPv4 packets through the existing TUN/event-loop machinery. Reuse the kernel TCP stack rather than this prototype's synthesized TCP connections.
4. Implement lifecycle, cancellation, reconnect and keepalive behavior, then add reproducible tests and authorized live interoperability checks.
5. Describe precisely which firmware and authentication modes were tested; leave unimplemented modes explicit.

Follow the upstream [contribution instructions](https://www.infradead.org/openconnect/contribute.html) and [protocol investigation guidance](https://www.infradead.org/openconnect/mitm.html). OpenConnect uses LGPL 2.1 and requires developer sign-off; new upstream code must satisfy its licensing and DCO requirements. This standalone repository uses MIT. A standalone release is not evidence that a complete upstream VPN adapter is ready.

Suggested upstream report title: **Huawei/UniVPN SSL transport: password login, IPv4 framing and heartbeat observations**.

# Draft upstream interoperability report

Suggested title: Huawei/UniVPN SSL transport: password login, IPv4 framing and heartbeat observations

I have prepared an experimental, standard-library Python implementation of a single-target TCP forwarder, along with redacted protocol notes. It is intended as a reference for Huawei/UniVPN protocol work, not as a complete VPN implementation or a Python module to merge directly into OpenConnect.

The implemented subset uses two TLS channels: password authentication and virtual IPv4 allocation on the control channel, token-based data-channel setup, and IPv4 packets transported in framed data messages. Control heartbeats run every 10 seconds and data heartbeats every 15 seconds. The frame format and observed command payloads are documented in `docs/protocol.md`.

On one authorized gateway, a fresh SSH connection, binary transfers in both directions, a 65-second idle connection and a concurrent second connection passed. The packaged source defaults to certificate verification and supports a trusted CA or full certificate pin. The test gateway did not chain to the system CA store, so this specific live test used a first-observed pin; no independent certificate identity verification is claimed.

The prototype has no UDP, IPv6, MFA or SSO support. Its minimal user-space TCP handling is deliberately limited. An OpenConnect implementation should transfer IPv4 packets through TUN and reuse the kernel TCP stack instead.

Before posting, attach the public repository URL and relevant protocol notes. No credentials, private endpoints, assigned addresses or session captures should be attached. I would welcome guidance on the appropriate upstream interfaces and additional redacted interoperability observations.

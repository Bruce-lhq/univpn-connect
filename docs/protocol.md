# Observed protocol

These notes describe the implemented subset, inferred from the supplied working prototype and validated against one gateway. Unknown fields are retained as observed constants, not asserted to be universal protocol definitions. All integers below are big-endian unless stated otherwise. No actual account, endpoint, session token or packet capture is included.

## Framing

After the initial connection request, both TLS channels use this frame:

| Offset | Bytes | Meaning |
| --- | --- | --- |
| 0 | 4 | Magic `c1 92 a4 d6` |
| 4 | 1 | Version `01` emitted by this client |
| 5 | 1 | Command |
| 6 | 2 | Payload length |
| 8 | variable | Payload |

TLS reads may split any field. The reader retains an incomplete frame across timeouts/EAGAIN, including a timeout immediately after the header. EOF closes the session. Partial-frame reads currently have no separate total deadline.

TLVs use a 16-bit type, 16-bit length, then that many bytes. The authentication/domain string is UTF-8, padded to 256 bytes. Percent, ampersand and plus characters in username/password are escaped as `%25`, `%26` and `%2B`; those values end in a NUL byte.

## Session setup

1. Establish a TLS control connection with certificate validation or explicit pinning.
2. Send the 340-byte FirstConnect request: `fe fc ef be`, frame magic, four zero bytes, `00 1d 01 44`, 64 zero bytes, domain padded to 256 bytes, then `00 01 00 00`. Require a command `00` response containing four zero status bytes.
3. Send AUTH command `01`: padded domain, four zero bytes, username TLV `1`, password TLV `2`, client MAC string TLV `3`. The locally administered MAC string is deterministically derived from username and gateway. Require result `0` in the first four response bytes; parse TLVs starting at byte 8. Token TLV `3` supplies the first 32 bytes as the session token.
4. Send REQVIP command `03` with the token. Require first response byte `0`; parse TLVs from byte 4. Type `1`, length `5` supplies the assigned IPv4 address in its first four bytes. The extra byte is not interpreted.
5. Establish a second TLS data connection and send DATA_CONNECT command `64` with the token. Require command `64`, payload `00`.

No server discovery, alternate authentication negotiation or MFA is implemented.

## Heartbeats and data

| Channel | Command | Payload | Client interval |
| --- | --- | --- | --- |
| Control | `06` | token (32 bytes) + elapsed milliseconds (32-bit) | 10 seconds |
| Data | `65` | empty | 15 seconds |
| Data | `66` | eight zero bytes + raw IPv4 packet | as needed |

Control replies are drained by a reader thread so they cannot accumulate while data is idle. Data heartbeats and packets share a send lock to prevent frame interleaving. Timers run independently of local application traffic.

The prototype crafts IPv4/TCP packets for one destination, including SYN, ACK, PSH and FIN. Segment payloads are limited to 1200 bytes. It computes IPv4 and TCP checksums, tracks the next expected sequence and acknowledges received bytes. Duplicate/out-of-order behavior is deliberately limited; this is not a substitute for a kernel TCP stack.

For a full OpenConnect implementation, move complete IPv4 packets between the VPN data channel and TUN, letting the operating system handle TCP. Do not port this minimal TCP stack into OpenConnect.

## Remaining questions

Other firmware/framing versions, heartbeat response semantics, flow control, session renewal, disconnect messages, compression, UDP/DTLS transports, MFA and IPv6 remain unverified. A contributor should collect redacted observations from additional authorized gateways before making broader compatibility claims.

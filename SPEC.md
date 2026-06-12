# Tendrilio Cloud Contract — Specification

This is the versioned contract between the open-source Tendrilio hub
(Connector) and the private Tendrilio Cloud. It is the complete interface:
a Connector built against this document needs no access to the cloud
codebase. The bundle is published to the public `tendrilio-contract`
repository on tagged releases; the hub repo pins a release tag for its
contract tests.

No uptime or SLA claims are made anywhere in this contract. Tendrilio Cloud
is an invite-only, limited-support companion service.

## Contract versioning

- The **contract major version** appears as the second topic segment
  (`v1`) and as the integer `contract_v` in event payloads. The single
  source is `topics.py` (`CONTRACT_VERSION = 1`).
- Bundle releases are tagged **`contract-v{major}.{minor}.{patch}`**
  (e.g. `contract-v1.0.0`) in both the cloud repo and this published repo.
  Minor/patch tags version the bundle (docs, clarifications, additive
  schema fields); the major only changes when topics or envelope semantics
  break.
- The cloud supports contract versions **N and N-1** simultaneously. A
  Connector reports its pinned contract version when it connects
  (`connector_version` at claim time; version field in connector status —
  negotiation details land with the full publishing surface). Outdated
  Connectors keep working and produce a quiet "update available" state,
  never an error.

## Bundle contents

| File | What it is |
|---|---|
| `SPEC.md` | This document — the language-neutral truth |
| `envelope/v1.json` | Command envelope JSON Schema (Draft 2020-12) |
| `topics.py` | Canonical MQTT topic grammar, the only rendering |
| `events.py` | Event-type vocabulary + uniform realtime payload shape |

`topics.py` / `events.py` are small, dependency-free Python modules the hub
(also Python) may import or treat as readable reference; the constants they
declare — not the language — are the contract.

## Identity & transport

- Every Hub holds a unique X.509 client certificate (obtained via Claim
  Bootstrap, below) and speaks **MQTT over TLS to AWS IoT Core only** —
  outbound from the hub, always. The cloud never opens a connection to a
  hub; no inbound reachability is assumed (CGNAT-safe).
- The Hub's cloud identifier `hub_id` is a lowercase UUIDv7 string and
  equals its IoT **Thing name**. The certificate policy confines each Hub
  to its own subtree across all contract versions:
  `tendrilio/*/{hub_id}/#`.
- QoS 1 (at-least-once) everywhere. The cloud's ingest is idempotent on
  `(hub_id, device_id, sensor_type, ts)` — publishing a reading twice is
  safe and expected under retransmission and backfill.

## Topic grammar

Canonical form, all lowercase:

```
tendrilio/{contract_v}/{hub_id}/{stream}
```

Streams (hub → cloud unless noted):

| Stream | Content |
|---|---|
| `readings` | Sensor readings (original `ts` preserved; backfill replays here) |
| `node-status` | Node online/offline + last-seen transitions |
| `actuator-state` | Actuator state changes (any origin: local, rule, remote) |
| `alerts` | Alert lifecycle transitions: raised / acknowledged / dismissed / auto-cleared |
| `rules` | Rule definition snapshots: enabled state + plain-English summary |
| `rule-executions` | Rule execution log entries, with trigger attribution |
| `commands` | **cloud → hub**: command envelopes (see below) |
| `command-status` | hub → cloud: per-command stage events (accepted → executed / declined) |
| `connector/status` | Connector lifecycle, incl. the clean-shutdown signal |
| `ota-status` | Per-node OTA progress (stage vocabulary frozen separately — see events) |

Timestamps in all payloads are ISO 8601 UTC with `Z` suffix and millisecond
precision (`2026-06-12T14:32:05.123Z`). Device-originated reading time is
`ts`; the cloud records its own `received_at`. Wire field names are
`snake_case`; hub vocabulary (`device_id`, `sensor_type`) is used verbatim,
never renamed.

## Event vocabulary

Defined in `events.py`: dot-namespaced, past tense, lowercase —
`reading.recorded`, `node.status_changed`, `alert.raised`,
`alert.acknowledged`, `alert.dismissed`, `alert.auto_cleared`,
`command.accepted`, `command.executed`, `command.declined`,
`command.timed_out`, `connector.disabled`, `ota.node_progress`,
`ota.node_succeeded`, `ota.node_rolled_back`.

Realtime payloads delivered to cloud clients all share one shape:

```json
{"type": "...", "contract_v": 1, "hub_id": "...",
 "occurred_at": "2026-06-12T14:32:05.123Z", "data": {}}
```

The `stage` enum inside `ota.node_progress` is **not yet frozen**: it will
mirror the hub's implemented `WsOtaStatusEvent` stage vocabulary verbatim
and ships in a later bundle release before any OTA feature does. Do not
invent stages against this version.

## Command envelope (v1)

Schema: `envelope/v1.json` (JSON Schema Draft 2020-12). Semantics:

- **Two classes.** `actuating` (moves hardware: actuator control, rule
  test-trigger, OTA trigger) requires platform attestation (mobile) or a
  command-passkey WebAuthn ceremony (web) at signing time. `write-back`
  (non-actuating state sync, e.g. alert acknowledge/dismiss) is
  session-gated with no Step-Up but is still a Command Request: enveloped,
  audited, and declined by the Kill Switch like everything else. Reads have
  no envelope and no command machinery.
- **The cloud cannot originate commands.** Envelopes are signed
  client-side by an owner-enrolled credential (iOS App Attest assertion;
  Android hardware-Keystore key whose Key Attestation chain was verified at
  enrollment, plus a Play Integrity verdict nonce-bound to the envelope
  hash; web WebAuthn command passkey). The cloud verifies, audits, and
  relays. The hub **re-verifies independently**: signature against the
  enrolled public key, TTL, idempotency, then its own Remote-Command Guards
  (max runtime, cooldown, conflicting state). A compromised cloud cannot
  move hardware.
- **Idempotency.** `command_id` is a client-generated UUIDv7. A hub seeing
  a repeated `command_id` must not act twice. Clients never auto-retry;
  user-initiated retry reuses the same `command_id`.
- **TTL.** `ttl_s` (nominally 30, bounded 5–60) from `issued_at`. Expired
  envelopes are rejected wherever they are evaluated. (Field named `ttl_s`
  per the contract's `_s` duration-suffix convention — the architecture
  sketch's shorthand `ttl` was normalized before freezing.)
- **Challenge.** `challenge` is an opaque, single-use, server-issued value
  bound into the signed payload — the cloud's anti-replay anchor.
- **Two-stage feedback.** The hub publishes `command.accepted` (or
  `command.declined`) on `command-status` when it verifies and starts the
  action, and `command.executed` when the node acknowledges. Every Command
  Request reaches a terminal state (`executed` / `declined` / `timed_out`)
  within 10 seconds — silence is not an outcome. Declines carry a
  structured reason (`guard_type`, time remaining where applicable) so
  every surface can render a plain-language explanation.
- **Kill Switch.** While the hub's local Kill Switch is on, the hub
  declines every Command Request — including write-backs — with an explicit
  owner-disabled outcome. Metric publishing continues.

## Claim Bootstrap (how a hub gets its credential)

Outbound-only HTTPS against the cloud API; no pre-claim MQTT access, no
shared secrets in the open-source Connector. The private key never leaves
the hub.

1. The owner opens the hub's local Cloud tab. The hub generates an X.509
   keypair + CSR and a **Claim Code** — Crockford Base32, 10 characters
   (≈50 bits), 15-minute TTL, single-use — and displays code + QR.
2. The hub submits `POST /api/v1/hub-claims` with
   `{"claim_code_hash": "...", "csr": "...", "connector_version": "..."}`
   and receives `202 {"request_id": "..."}`. It then polls
   `GET /api/v1/hub-claims/{request_id}`.
3. The owner, authenticated in the app or portal, enters the code. On a
   hash match the cloud issues the certificate from the CSR, creates the
   IoT Thing (name = `hub_id`), attaches the scoped policy, and binds
   hub ↔ account.
4. The hub's next poll returns the signed certificate, the IoT endpoint,
   and its `hub_id`. The bridge connects and publishing begins.

Abuse posture: codes are meaningful only while a pending request exists;
single-use; 15-minute expiry; per-IP and per-code rate limits on both
endpoints; a pending request is voided after 5 failed match attempts. An
already-claimed hub cannot be claimed again until its owner unlinks it.

## Clean shutdown vs. failure

When the owner disables the Connector, it publishes an explicit
`connector.disabled` event on `connector/status` before disconnecting —
the cloud then raises no "Hub Unreachable" noise. An ungraceful drop is
distinguished by the MQTT Last Will. Hubs silent for more than 10 minutes
without a clean-shutdown signal are flagged unreachable cloud-side and
auto-clear on reconnect.

## Buffering & backfill

During WAN outages the Connector buffers outbound events and replays them
in order on reconnect **with original timestamps**. Combined with
idempotent ingest, history backfills without artificial chart gaps. The
bounded replay window is documented with the Connector implementation.

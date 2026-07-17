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

### Version notes

- **`contract-v1.3.0`** (2026-07-17) — Epic 24 §7 / hub Epic 25 seam. Additive;
  integer `CONTRACT_VERSION` unchanged at `1` (N-1 rule holds — the cloud
  tolerates every addition being absent from older hubs):
  1. **`node.status_changed` `data` gains nullable `name`** (string — the node's
     human label). Present on every emission so upserts are idempotent; a rename
     propagates on the node's next status transition (the stream is
     transition-driven, not a heartbeat) or via a state snapshot.
  2. **Three read-only domain state-snapshot streams** (`compost-state`,
     `germination-state`, `irrigation-state`) each carrying one event
     (`compost.state_snapshot`, `germination.state_snapshot`,
     `irrigation.state_snapshot`). See *State snapshots* under Event vocabulary
     for shapes and semantics. Irrigation is strictly read-only — the command
     seam (envelope, guards, Kill Switch) is unchanged.
- **`contract-v1.2.0`** (2026-07-16; source-only — the tag was never published,
  and its changes first ship in the `contract-v1.3.0` bundle) — Cloud-signed
  **write-back** envelope variant (platform `"cloud"`, schema-restricted to
  class `write-back`; ECDSA P-256/KMS). See `envelope/v1.json` and the Command
  envelope section. Additive; `CONTRACT_VERSION` unchanged.
- **`contract-v1.1.0`** (2026-06-25) — Froze the `ota.node_progress` `stage`
  enum (`flashing`, `rebooting`, `confirmed`); see Event vocabulary. Additive
  and non-breaking: the OTA event types and `ota-status` stream were already
  reserved at `contract-v1.0.0` with no live consumer, so the integer
  `CONTRACT_VERSION` is unchanged at `1` (no N/N-1 break). The frozen set is a
  candidate drawn from the documented UX vocabulary; the cross-check against
  the hub's implemented `WsOtaStatusEvent` enum is a standing forward obligation
  — any change it forces will ship as a further version note here, never a
  silent edit. The enum is open (see Event vocabulary), so an unanticipated hub
  stage degrades gracefully rather than breaking surfaces.

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
| `ota-status` | Per-node OTA progress (`ota.node_progress` `stage` enum + terminals — see Event vocabulary) |
| `compost-state` | Compost domain state snapshots (`compost.state_snapshot` — see State snapshots) |
| `germination-state` | Germination domain state snapshots (`germination.state_snapshot`) |
| `irrigation-state` | Irrigation zone state snapshots (`irrigation.state_snapshot` — read-only; commands unchanged) |

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
`ota.node_succeeded`, `ota.node_rolled_back`, `compost.state_snapshot`,
`germination.state_snapshot`, `irrigation.state_snapshot`.

`node.status_changed` `data` (`contract-v1.3.0`) additionally carries a
nullable **`name`** — the node's human label — on **every** emission, so
cloud-side upserts are idempotent and a freshly provisioned device's first
online envelope already names it.

### State snapshots (`contract-v1.3.0`)

Read-only, hub → cloud, one stream + one event per domain. Each event's
`data` is a **full replacement** of that domain's state — the cloud upserts
the whole domain per event; there are no per-item deltas and no tombstones
(an item absent from a snapshot no longer exists). Hubs emit on domain
change **plus** a slow reconcile tick (~30 minutes). Absent streams are
normal (older hubs, or hardware the hub doesn't have) and MUST NOT produce
errors or warnings cloud-side. All `state` string values are **open
vocabularies** (the same rule as OTA stages): consumers humanize unknown
tokens, never drop them, never raise.

| Event | `data` |
|---|---|
| `compost.state_snapshot` | `{"bay_count": n, "piles": [{"id", "name", "bay_position", "bay_label", "state", "state_since"}]}` |
| `germination.state_snapshot` | `{"setups": [{"id", "name", "crop_label", "state", "planted_at"}]}` |
| `irrigation.state_snapshot` | `{"zones": [{"zone_id", "name", "enabled", "schedule", "duration_s", "last_activated_at", "next_run_at"}]}` |

Irrigation snapshots are **strictly read-only**: zone control remains a
hub-local concern and the command seam (envelopes, guards, Kill Switch) is
untouched by this addition.

Realtime payloads delivered to cloud clients all share one shape:

```json
{"type": "...", "contract_v": 1, "hub_id": "...",
 "occurred_at": "2026-06-12T14:32:05.123Z", "data": {}}
```

Per-node OTA progress streams as `ota.node_progress` carrying a `stage` value
in its `data` (`{"node_id": "...", "stage": "..."}`). The frozen `stage` enum
(`contract-v1.1.0`) is, in lifecycle order: **`flashing`**, **`rebooting`**,
**`confirmed`**. The per-node outcome is a separate terminal *event* —
`ota.node_succeeded` or `ota.node_rolled_back` — not a stage.

The `stage` enum is **open**: it is a candidate frozen from the documented UX
vocabulary, pending a cross-check against the hub's implemented
`WsOtaStatusEvent` enum. A consumer that receives a `stage` not in the frozen
set MUST render it as a humanized form of the raw token (e.g. title-cased) —
never drop it, never raise. Do not invent stage names; if the hub emits new
ones, freeze them here with a version note.

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
- **OTA trigger vocabulary (Story 7.2, candidate — hub cross-check pending).**
  A remote OTA is a single `actuating` Command Request, not a new class and
  not a binary transfer (no firmware ever passes through the cloud — the cloud
  relays a *trigger* and observes per-node progress). The candidate tokens are
  `action = "ota.update"`, `target = <hub_id>` (the hub orchestrates the
  selected nodes), and `params = { "node_ids": [<device_id>, …] }`. One
  envelope updates one-or-more nodes; the hub fans out and streams per-node
  `ota.node_progress` + terminals on `ota-status`. These tokens are a frozen
  *candidate* (the same forward-obligation discipline as the `ota.node_progress`
  `stage` enum): the implementing hub side (Epic 9.8 `ota-relay`) must match
  them, and a cross-check that forces a change ships as a version note, not a
  silent edit. Integer `CONTRACT_VERSION` is unchanged — the envelope shape is
  untouched (`params` was always an open object).

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

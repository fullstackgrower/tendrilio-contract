"""MQTT topic constants — the single rendering of the canonical grammar.

Canonical grammar: tendrilio/{contract_v}/{hub_id}/{stream}, lowercase.
Cert policy templates wildcard the version segment: tendrilio/*/{hub_id}/#.

This module is part of the PUBLISHED contract artifact (the public
tendrilio-contract repo is synced from this directory on tagged releases):
changes require a contract-version bump + N-1 compatibility + contract tests.
Rendering a topic anywhere else in the codebase is a defect.

{hub_id} is the Hub's cloud identifier (UUIDv7, lowercase) and EQUALS the
Hub's AWS IoT Thing name — that identity is what lets the policy variable
${iot:Connection.Thing.ThingName} confine each Hub to its own subtree.
"""

import re

# Contract version, both renderings derived from one integer:
# the topic segment uses "v1"; event payloads carry the bare integer.
CONTRACT_VERSION: int = 1
CONTRACT_V: str = f"v{CONTRACT_VERSION}"

# Render-time input guards for the single authoritative renderer (see topic()).
# hub_id must be a lowercase UUIDv7 (matches envelope/v1.json's uuidv7 def — also the
# Hub's IoT Thing name); contract_v must be a vN segment. This keeps a malformed value
# (uppercase, slashes, wildcards) from injecting extra MQTT levels or breaking grammar.
_HUB_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
_CONTRACT_V_RE = re.compile(r"^v\d+$")

TOPIC_ROOT: str = "tendrilio"

# Streams — the full publishing surface (named once, here; Epic 4/9 stories
# consume these constants rather than inventing names).
STREAM_READINGS: str = "readings"
STREAM_NODE_STATUS: str = "node-status"
STREAM_ACTUATOR_STATE: str = "actuator-state"
STREAM_ALERTS: str = "alerts"
STREAM_RULES: str = "rules"
STREAM_RULE_EXECUTIONS: str = "rule-executions"
STREAM_COMMANDS: str = "commands"  # cloud → hub: command envelopes
STREAM_COMMAND_STATUS: str = "command-status"  # hub → cloud: acceptance + node-ack stages
STREAM_KILL_SWITCH: str = "kill-switch"  # hub → cloud: owner's Kill-Switch state (Story 6.4)
STREAM_CONNECTOR_STATUS: str = "connector/status"  # connector lifecycle incl. clean shutdown
STREAM_OTA_STATUS: str = "ota-status"  # per-node OTA progress (stages: events.OTA_PROGRESS_STAGES)
# contract-v1.3.0 (Epic 24 §7 / hub Epic 25): read-only domain state snapshots,
# hub → cloud. One stream + one full-replacement event per domain; emitted on
# domain change plus a slow reconcile tick. Absence is normal (older hubs).
STREAM_COMPOST_STATE: str = "compost-state"  # compost.state_snapshot (hub 25.2)
STREAM_GERMINATION_STATE: str = "germination-state"  # germination.state_snapshot (hub 25.3)
STREAM_IRRIGATION_STATE: str = "irrigation-state"  # irrigation.state_snapshot (25.4; read-only)

STREAMS: frozenset[str] = frozenset(
    {
        STREAM_READINGS,
        STREAM_NODE_STATUS,
        STREAM_ACTUATOR_STATE,
        STREAM_ALERTS,
        STREAM_RULES,
        STREAM_RULE_EXECUTIONS,
        STREAM_COMMANDS,
        STREAM_COMMAND_STATUS,
        STREAM_KILL_SWITCH,
        STREAM_CONNECTOR_STATUS,
        STREAM_OTA_STATUS,
        STREAM_COMPOST_STATE,
        STREAM_GERMINATION_STATE,
        STREAM_IRRIGATION_STATE,
    }
)

# The per-Hub cert policy filter as deployed by terraform/modules/iot —
# version segment wildcarded so contract bumps never require policy re-issue.
IOT_POLICY_TOPIC_FILTER: str = "tendrilio/*/${iot:Connection.Thing.ThingName}/#"


def topic(hub_id: str, stream: str, contract_v: str = CONTRACT_V) -> str:
    """Render the canonical topic for a Hub and stream.

    Raises ValueError for streams outside the contract — there are no
    ad-hoc topics in this system.
    """
    if stream not in STREAMS:
        raise ValueError(f"unknown stream {stream!r}; contract streams: {sorted(STREAMS)}")
    if not _CONTRACT_V_RE.fullmatch(contract_v):
        raise ValueError(f"invalid contract_v {contract_v!r}; expected a version segment like 'v1'")
    if not _HUB_ID_RE.fullmatch(hub_id):
        raise ValueError(f"invalid hub_id {hub_id!r}; expected a lowercase UUIDv7")
    return f"{TOPIC_ROOT}/{contract_v}/{hub_id}/{stream}"

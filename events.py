"""Event-type vocabulary shared by realtime fan-out, Audit Events, and logs.

Dot-namespaced, past tense, lowercase snake_case. One vocabulary everywhere —
code never invents synonyms (alertDismissed / dismiss_alert are defects).

This module is part of the PUBLISHED contract artifact: changes require a
contract-version bump + N-1 compatibility + contract tests.

Uniform realtime (AppSync Events) payload shape — clients switch on `type`,
never on payload shape:

    {"type": "reading.recorded", "contract_v": 1, "hub_id": "...",
     "occurred_at": "2026-06-12T14:32:05.123Z", "data": {...}}

`contract_v` is the bare integer rendering of topics.CONTRACT_VERSION (the
single source — not redeclared here). Audit Events reuse this same verb
vocabulary plus actor fields.
"""

READING_RECORDED: str = "reading.recorded"
NODE_STATUS_CHANGED: str = "node.status_changed"
ALERT_RAISED: str = "alert.raised"
ALERT_ACKNOWLEDGED: str = "alert.acknowledged"
ALERT_DISMISSED: str = "alert.dismissed"
ALERT_AUTO_CLEARED: str = "alert.auto_cleared"
COMMAND_ACCEPTED: str = "command.accepted"
COMMAND_EXECUTED: str = "command.executed"
COMMAND_DECLINED: str = "command.declined"
COMMAND_TIMED_OUT: str = "command.timed_out"
CONNECTOR_DISABLED: str = "connector.disabled"  # clean-shutdown signal (owner intent)
# OTA events: the `stage` enum inside ota.node_progress payloads is NOT frozen
# here — Story 7.1 freezes it against the hub's real WsOtaStatusEvent
# vocabulary before any OTA feature ships. Do not invent stages.
OTA_NODE_PROGRESS: str = "ota.node_progress"
OTA_NODE_SUCCEEDED: str = "ota.node_succeeded"
OTA_NODE_ROLLED_BACK: str = "ota.node_rolled_back"

EVENT_TYPES: frozenset[str] = frozenset(
    {
        READING_RECORDED,
        NODE_STATUS_CHANGED,
        ALERT_RAISED,
        ALERT_ACKNOWLEDGED,
        ALERT_DISMISSED,
        ALERT_AUTO_CLEARED,
        COMMAND_ACCEPTED,
        COMMAND_EXECUTED,
        COMMAND_DECLINED,
        COMMAND_TIMED_OUT,
        CONNECTOR_DISABLED,
        OTA_NODE_PROGRESS,
        OTA_NODE_SUCCEEDED,
        OTA_NODE_ROLLED_BACK,
    }
)

# Top-level keys of every realtime event payload, in canonical order.
EVENT_PAYLOAD_KEYS: tuple[str, ...] = ("type", "contract_v", "hub_id", "occurred_at", "data")

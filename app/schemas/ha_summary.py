"""Parsed output of `HAWebSocketClient.fetch_dashboard_summary` (Slice 3).

Carries full, untruncated data - the 5-name cap, "+N more", and zero-count "all clear" styling
(Slice 4's concern) are decided at the route/template layer, not here. See the TDD's "HA
WebSocket client" section.
"""

from dataclasses import dataclass, field
from datetime import datetime

# Repair issues have no resolved, human-readable title in HA's WS payload - only a
# `translation_key` the real HA frontend resolves against its own translation catalog, which this
# app deliberately does not attempt to replicate (PRD "Out of scope": prettifying translation_key
# fallback strings). This is the last-resort default for the rare case even `translation_key`
# itself is missing/blank - a schema-level guarantee every RepairIssue has a non-empty display
# string, per the TDD.
UNKNOWN_ISSUE_NAME = "Unknown issue"


@dataclass(frozen=True)
class UpdateItem:
    entity_id: str
    name: str


@dataclass(frozen=True)
class RepairIssue:
    issue_id: str
    name: str = UNKNOWN_ISSUE_NAME


@dataclass(frozen=True)
class IntegrationError:
    entry_id: str
    name: str
    state: str


@dataclass(frozen=True)
class HASummary:
    # fetched_at has no default - the client always supplies it (datetime.now(UTC) at the moment
    # the whole 3-command fetch completes), so there's no risk of a hidden, untimezoned clock read
    # sneaking in via an unspecified default.
    fetched_at: datetime
    pending_updates: list[UpdateItem] = field(default_factory=list)
    repair_issues: list[RepairIssue] = field(default_factory=list)
    integration_errors: list[IntegrationError] = field(default_factory=list)

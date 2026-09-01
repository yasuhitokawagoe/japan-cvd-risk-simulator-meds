"""Privacy-preserving analytics for the public checkup flow.

Only navigation metadata and event names are stored. Health measurements and
simulation results must never be passed to ``record_event``.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


EVENTS = {
    "landing_view", "start_clicked", "consent_completed",
    "basic_input_completed", "full_input_completed", "result_viewed",
    "trajectory_viewed", "lifestyle_intervention_clicked",
    "medical_intervention_clicked", "specific_drug_clicked", "plan_created",
    "family_share_clicked", "doctor_handoff_clicked",
}


def _event_path() -> Path:
    return Path(os.environ.get("CHECKUP_ANALYTICS_PATH", "checkup_analytics.jsonl"))


def record_event(event: str, context: Mapping[str, str]) -> None:
    """Append one de-identified event. Analytics failures never break the UI."""
    if event not in EVENTS:
        raise ValueError(f"Unknown analytics event: {event}")
    allowed = {
        "session_id", "source", "campaign", "facility_id",
        "referral_id", "parent_referral_id",
    }
    payload = {key: str(context.get(key, ""))[:128] for key in allowed}
    payload.update({"event": event, "timestamp": datetime.now(timezone.utc).isoformat()})
    try:
        path = _event_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass


def aggregate_events() -> list[dict]:
    """Return facility/campaign aggregates; never returns patient-level rows."""
    path = _event_path()
    if not path.exists():
        return []
    counts: dict[tuple[str, str, str], int] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            key = (item.get("facility_id", ""), item.get("campaign", ""), item["event"])
            counts[key] = counts.get(key, 0) + 1
    except (OSError, json.JSONDecodeError, KeyError):
        return []
    return [
        {"facility_id": f or "（未設定）", "campaign": c or "（未設定）", "event": e, "count": n}
        for (f, c, e), n in sorted(counts.items())
    ]

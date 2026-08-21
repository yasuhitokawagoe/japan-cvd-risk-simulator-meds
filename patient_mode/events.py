from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


ALLOWED_EVENTS = {
    "session_start", "risk_result_viewed", "detailed_numbers_opened",
    "intervention_selected", "intervention_removed", "medication_details_opened",
    "lifestyle_details_opened", "burden_information_opened", "comparison_viewed",
    "ai_help_opened", "final_reaction_selected", "doctor_question_selected",
    "doctor_summary_viewed", "session_complete",
}


class EventSink(Protocol):
    def emit(self, event: dict) -> None: ...


class MemoryEventSink:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def emit(self, event: dict) -> None:
        self.events.append(event)


class JsonlEventSink:
    """Local-only sink. Enable explicitly with PATIENT_EVENT_LOG_PATH."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def emit(self, event: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def default_sink() -> EventSink:
    path = os.getenv("PATIENT_EVENT_LOG_PATH", "").strip()
    return JsonlEventSink(path) if path else MemoryEventSink()


def make_event(session_id: str, event_name: str, **properties) -> dict:
    if event_name not in ALLOWED_EVENTS:
        raise ValueError(f"Unknown event: {event_name}")
    # properties are deliberately limited to interaction metadata, never form values.
    return {
        "event": event_name,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "properties": properties,
    }

from patient_mode.events import MemoryEventSink, make_event


def test_anonymous_event_has_only_expected_envelope():
    sink = MemoryEventSink()
    event = make_event("anonymous-session", "intervention_selected", category="blood_pressure")
    sink.emit(event)
    assert set(event) == {"event", "session_id", "timestamp", "properties"}
    assert "name" not in str(event).lower()

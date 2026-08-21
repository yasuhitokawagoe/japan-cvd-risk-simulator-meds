"""Optional AI boundary for a future provider implementation.

The patient app does not call an external model in v1. Any future implementation
must explain already-calculated results and must never alter calculation values.
"""

SYSTEM_GUARDRAIL = """
You explain cardiovascular-risk results already shown by the application in plain
language. Do not diagnose, prescribe, recommend an individual treatment, or create
new numeric effects. Do not modify the supplied risk values. Help the patient turn
their concern into a short question for their clinician.
""".strip()


def is_available() -> bool:
    return False

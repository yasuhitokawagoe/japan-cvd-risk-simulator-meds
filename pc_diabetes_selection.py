"""PC-only diabetes model selection; an HbA1c suggestion is not a diagnosis."""
from collections.abc import MutableMapping


DIABETES_MODEL_KEY = "pc_type2_diabetes"
DIABETES_MANUAL_KEY = "pc_type2_diabetes_manual"
AUTO_CHECK_HBA1C = 6.5


def sync_diabetes_selection(state: MutableMapping, current_hba1c: float) -> None:
    """Auto-enable at >=6.5 unless the user has explicitly chosen either state.

    Falling HbA1c never clears an enabled setting: treatment does not erase a
    prior diagnosis. Only the current measurement, never a target, is passed in.
    Manual choices persist for the session, including subsequent HbA1c changes.
    """
    if DIABETES_MODEL_KEY not in state:
        state[DIABETES_MODEL_KEY] = False
    if not state.get(DIABETES_MANUAL_KEY, False) and current_hba1c >= AUTO_CHECK_HBA1C:
        state[DIABETES_MODEL_KEY] = True


def mark_diabetes_selection_manual(state: MutableMapping) -> None:
    state[DIABETES_MANUAL_KEY] = True

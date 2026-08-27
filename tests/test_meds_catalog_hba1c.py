from meds_catalog import _parse_hba1c_delta_pct


def test_hba1c_label_is_not_parsed_as_positive_one():
    mean, low, high = _parse_hba1c_delta_pct(
        "HbA1c -1.0% (95% CI -1.27〜-0.90%)"
    )
    assert mean == -1.0
    assert low == -1.27
    assert high == -0.90

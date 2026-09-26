from meds_catalog import _parse_hba1c_delta_pct, split_medication_key


def test_hba1c_label_is_not_parsed_as_positive_one():
    mean, low, high = _parse_hba1c_delta_pct(
        "HbA1c -1.0% (95% CI -1.27〜-0.90%)"
    )
    assert mean == -1.0
    assert low == -1.27
    assert high == -0.90


def test_medication_key_splits_name_and_daily_dose():
    assert split_medication_key("ネクセトール（ベムペド酸）180 mg 1日1回") == (
        "ネクセトール（ベムペド酸）", "180 mg 1日1回",
    )


def test_medication_key_splits_combination_dose():
    assert split_medication_key("サクビトリル/バルサルタン 24/26 mg BID") == (
        "サクビトリル/バルサルタン", "24/26 mg BID",
    )

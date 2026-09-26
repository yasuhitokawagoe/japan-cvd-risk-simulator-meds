from meds_catalog import (
    _parse_hba1c_delta_pct,
    apply_meds_to_targets,
    load_meds_catalog,
    split_medication_key,
)


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


def test_expanded_catalog_and_unregistered_cost_are_explicit():
    catalog = load_meds_catalog(
        "降圧薬詳細_Ca-ARNI_薬価付き_日本語表_英語タイトル引用付き.xlsx",
        "LDL_HbA1c_用量別_薬価付き_日本語表_英語タイトル引用付き.xlsx",
    )
    assert len(catalog["sbp"]) == 43
    assert len(catalog["ldl"]) == 17
    assert len(catalog["hba1c"]) == 28

    inclisiran = next(m for m in catalog["ldl"] if "インクリシラン" in m["key"])
    bempedoic_acid = next(m for m in catalog["ldl"] if "ベムペド酸" in m["key"])
    result = apply_meds_to_targets(140, 140, 8.0, [], [inclisiran, bempedoic_acid], [])
    assert result["cost_complete"] is False
    assert result["annual_cost_yen"] == 135_598
    assert result["missing_cost_labels"] == [inclisiran["key"]]

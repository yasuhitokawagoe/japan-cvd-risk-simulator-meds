from meds_catalog import (
    _parse_hba1c_delta_pct,
    _parse_yen_per_year,
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


def test_expanded_catalog_has_prices_for_every_dose():
    catalog = load_meds_catalog(
        "降圧薬詳細_Ca-ARNI_薬価付き_日本語表_英語タイトル引用付き.xlsx",
        "LDL_HbA1c_用量別_薬価付き_日本語表_英語タイトル引用付き.xlsx",
    )
    assert len(catalog["sbp"]) == 43
    assert len(catalog["ldl"]) == 17
    assert len(catalog["hba1c"]) == 28
    assert all(m["annual_cost_yen"] is not None and m["annual_cost_yen"] > 0
               for meds in catalog.values() for m in meds)

    inclisiran = next(m for m in catalog["ldl"] if "インクリシラン" in m["key"])
    bempedoic_acid = next(m for m in catalog["ldl"] if "ベムペド酸" in m["key"])
    result = apply_meds_to_targets(140, 140, 8.0, [], [inclisiran, bempedoic_acid], [])
    assert result["cost_complete"] is True
    assert result["annual_cost_yen"] == 789_516 + 135_598
    assert result["missing_cost_labels"] == []


def test_price_units_are_converted_to_annual_doses():
    catalog = load_meds_catalog(
        "降圧薬詳細_Ca-ARNI_薬価付き_日本語表_英語タイトル引用付き.xlsx",
        "LDL_HbA1c_用量別_薬価付き_日本語表_英語タイトル引用付き.xlsx",
    )
    costs = {m["key"]: m["annual_cost_yen"] for meds in catalog.values() for m in meds}
    assert costs["プラバスタチン 20 mg"] == 9271  # 10mg tablets, twice daily quantity
    assert costs["メトホルミン 1000 mg"] == 7884  # two 500mg tablets/day
    assert costs["ツイミーグ（イメグリミン）1000 mg 1日2回"] == 47450
    assert costs["ビクトーザ（リラグルチド）0.9 mg/日"] == 84571
    assert costs["ビクトーザ（リラグルチド）1.8 mg/日"] == 169141
    assert costs["シルニジピン 20 mg"] == 6899  # decimal half-up rounding


def test_price_parser_supports_cached_numeric_formulas_and_missing_values():
    assert _parse_yen_per_year(7884.0) == 7884
    assert _parse_yen_per_year("7,884 円/年") == 7884
    for missing in (None, float("nan"), float("inf"), "", -1):
        assert _parse_yen_per_year(missing) is None
    unknown = dict(key="Unknown", effect={"mean": 0.1}, annual_cost_yen=None)
    result = apply_meds_to_targets(140, 140, 8, [], [unknown], [])
    assert not result["cost_complete"]
    assert result["missing_cost_labels"] == ["Unknown"]

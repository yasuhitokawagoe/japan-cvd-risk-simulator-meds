# meds_catalog.py の効果量パースの回帰テスト
#
# 背景: HbA1c 効果テキストの先頭ラベル「HbA1c」の「1」を効果量として誤検出し、
# 全 HbA1c 薬の mean が +1.0 になるバグがあった（fix/hba1c-parse で修正）。
# 詳細: docs/hba1c_parse_bugfix_explained.md
#
# 実行: .venv/bin/python tests/test_meds_catalog_parse.py
#   または .venv/bin/python -m pytest tests/test_meds_catalog_parse.py

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meds_catalog import _parse_hba1c_delta_pct, load_meds_catalog

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XLSX_BP = os.path.join(REPO, "降圧薬詳細_Ca-ARNI_薬価付き_日本語表_英語タイトル引用付き.xlsx")
XLSX_LDL_A1C = os.path.join(REPO, "LDL_HbA1c_用量別_薬価付き_日本語表_英語タイトル引用付き.xlsx")


def test_hba1c_label_not_parsed_as_value():
    """先頭ラベル「HbA1c」の「1」を効果量として拾わないこと（バグの直接再現ケース）"""
    mean, low, high = _parse_hba1c_delta_pct("HbA1c −0.8% (95% CI −0.9〜−0.7)")
    assert mean == -0.8, f"mean: expected -0.8, got {mean}"
    assert low == -0.9 and high == -0.7, f"CI: got {low}..{high}"

    # ラベルなしテキストは従来どおり
    mean, _, _ = _parse_hba1c_delta_pct("−1.5%")
    assert mean == -1.5, f"mean: expected -1.5, got {mean}"


def test_catalog_hba1c_means_are_negative():
    """実カタログの全 HbA1c 薬の mean が負値（改善方向）でパースされること"""
    cat = load_meds_catalog(XLSX_BP, XLSX_LDL_A1C)
    assert len(cat["hba1c"]) > 0, "HbA1c 薬が1剤も読めていない"
    for m in cat["hba1c"]:
        mean = m["effect"]["mean"]
        assert mean < 0, f"{m['key']}: mean={mean} は負値のはず（バグ時は +1.0）"

    # 代表値の固定チェック（Excel 記載値と一致すること）
    by_key = {m["key"]: m["effect"]["mean"] for m in cat["hba1c"]}
    assert by_key["メトホルミン 500 mg"] == -0.8
    assert by_key["マンジャロ（チルゼパチド） 15 mg/週"] == -2.82


def test_sbp_ldl_unaffected():
    """修正が SBP / LDL のパースに影響しないこと（回帰ガード）"""
    cat = load_meds_catalog(XLSX_BP, XLSX_LDL_A1C)
    sbp = {m["key"]: m["effect"]["mean"] for m in cat["sbp"]}
    ldl = {m["key"]: m["effect"]["mean"] for m in cat["ldl"]}
    # 修正前に記録した代表値と一致すること
    assert sbp["アムロジピン 5 mg"] == -11.7
    assert sbp["アムロジピン 2.5 mg"] == -6.3
    assert ldl["ロスバスタチン 10 mg"] == 0.52
    assert ldl["エゼチミブ 10 mg"] == 0.22
    assert all(v < 0 for v in sbp.values()), "SBP はすべて負値（降圧）のはず"
    assert all(0 < v < 1 for v in ldl.values()), "LDL は 0〜1 の低下割合のはず"


def test_adalat_and_renivace_dose_ladders_are_available():
    """アダラートCRとレニベースが用量別に読み込まれ、高用量ほど降圧量が大きいこと。"""
    cat = load_meds_catalog(XLSX_BP, XLSX_LDL_A1C)
    sbp = {m["key"]: m["effect"]["mean"] for m in cat["sbp"]}

    adalat = [
        sbp["アダラートCR（ニフェジピン） 20 mg/日"],
        sbp["アダラートCR（ニフェジピン） 40 mg/日"],
        sbp["アダラートCR（ニフェジピン） 80 mg/日（40 mg 1日2回）"],
    ]
    renivace = [
        sbp["レニベース（エナラプリル） 2.5 mg/日"],
        sbp["レニベース（エナラプリル） 5 mg/日"],
        sbp["レニベース（エナラプリル） 10 mg/日"],
    ]
    assert adalat == sorted(adalat, reverse=True)
    assert renivace == sorted(renivace, reverse=True)


if __name__ == "__main__":
    test_hba1c_label_not_parsed_as_value()
    test_catalog_hba1c_means_are_negative()
    test_sbp_ldl_unaffected()
    test_adalat_and_renivace_dose_ladders_are_available()
    print("OK: 全テスト通過")

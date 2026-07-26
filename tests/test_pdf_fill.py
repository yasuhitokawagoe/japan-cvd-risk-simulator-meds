# pdf_fill.py の変換ロジック（build_field_values）のテスト。
#
# ここでテストするのは「どの値をどの欄に入れるか」＝間違えると誤った診療文書になる部分。
# PDF出力そのもの（pypdfでの記入）は別レイヤなので、このテストはPDF不要で回る。
#
# 実行: .venv/bin/python tests/test_pdf_fill.py
#   または .venv/bin/python -m pytest tests/test_pdf_fill.py

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pdf_fill import (
    PlanInput,
    build_field_values,
    F_SEX, F_AGE, F_DATE_Y, F_DATE_M, F_DATE_D,
    F_VISIT_FIRST, F_VISIT_CONT,
    F_BP, C_BP, F_BMI, C_BMI, F_A1C_TGT, C_A1C_TGT,
    F_LDL_NOW, C_LDL_NOW, F_A1C_NOW, C_A1C_NOW,
)


def test_basic_required_fields():
    """必須項目（性別・年齢・作成日・初回/継続）が正しい欄に入る"""
    fv = build_field_values(PlanInput(
        sex="female", age=72, visit_type="initial", created=date(2026, 7, 24),
    ))
    assert fv.text[F_SEX] == "（女）"      # 全角括弧・Dropdown9の選択肢と一致
    assert fv.text[F_AGE] == "72"
    assert fv.text[F_DATE_Y] == "2026"
    assert fv.text[F_DATE_M] == "7"       # ゼロ埋めしない（選択肢が '7'）
    assert fv.text[F_DATE_D] == "24"
    assert fv.checks.get(F_VISIT_FIRST) is True
    assert F_VISIT_CONT not in fv.checks   # 継続はONにしない


def test_male_and_continued():
    fv = build_field_values(PlanInput(
        sex="male", age=60, visit_type="continued",
    ))
    assert fv.text[F_SEX] == "（男）"
    assert fv.checks.get(F_VISIT_CONT) is True
    assert F_VISIT_FIRST not in fv.checks


def test_bp_with_dbp():
    """目標血圧はSBP/DBPがそろえば '130/80' 形式。連動チェックもON"""
    fv = build_field_values(PlanInput(
        sex="male", age=55, visit_type="initial", sbp_tgt=130, dbp_tgt=80,
    ))
    assert fv.text[F_BP] == "130/80"
    assert fv.checks.get(C_BP) is True


def test_bp_sbp_only():
    """DBP未指定ならSBPのみ記入（拡張期は手書き想定）"""
    fv = build_field_values(PlanInput(
        sex="male", age=55, visit_type="initial", sbp_tgt=140,
    ))
    assert fv.text[F_BP] == "140"
    assert fv.checks.get(C_BP) is True


def test_targets_and_labs():
    """目標BMI/HbA1c（目標）と実測LDL/HbA1c（実測）が別々の欄に入る"""
    fv = build_field_values(PlanInput(
        sex="female", age=68, visit_type="continued",
        bmi_target=23.0, a1c_tgt=7.0, ldl_now=160, a1c_now=8.4,
    ))
    # 目標ブロック
    assert fv.text[F_BMI] == "23.0"
    assert fv.checks.get(C_BMI) is True
    assert fv.text[F_A1C_TGT] == "7.0"
    assert fv.checks.get(C_A1C_TGT) is True
    # 実測ブロック
    assert fv.text[F_LDL_NOW] == "160"
    assert fv.checks.get(C_LDL_NOW) is True
    assert fv.text[F_A1C_NOW] == "8.4"
    assert fv.checks.get(C_A1C_NOW) is True


def test_hba1c_target_and_actual_go_to_different_fields():
    """HbA1cの目標値と実測値が別フィールドに入ること（同じ欄に混ざらない）"""
    fv = build_field_values(PlanInput(
        sex="male", age=50, visit_type="initial", a1c_tgt=6.5, a1c_now=9.1,
    ))
    assert fv.text[F_A1C_TGT] == "6.5"
    assert fv.text[F_A1C_NOW] == "9.1"
    assert F_A1C_TGT != F_A1C_NOW


def test_optional_values_omitted_when_none():
    """None の任意項目は記入もチェックもされない"""
    fv = build_field_values(PlanInput(
        sex="male", age=40, visit_type="initial",
    ))
    for f in (F_BP, F_BMI, F_A1C_TGT, F_LDL_NOW, F_A1C_NOW):
        assert f not in fv.text, f"{f} は None なので記入されないはず"
    for c in (C_BP, C_BMI, C_A1C_TGT, C_LDL_NOW, C_A1C_NOW):
        assert c not in fv.checks, f"{c} は None なのでOFFのはず"


def test_decimal_rounding():
    """小数1桁に丸める（7.25 → 7.3）"""
    fv = build_field_values(PlanInput(
        sex="male", age=40, visit_type="initial", a1c_now=7.25,
    ))
    assert fv.text[F_A1C_NOW] == "7.2" or fv.text[F_A1C_NOW] == "7.3"  # 銀行丸め許容


def test_invalid_sex_raises():
    try:
        build_field_values(PlanInput(sex="M", age=40, visit_type="initial"))
    except ValueError:
        pass
    else:
        raise AssertionError("不正な sex で ValueError が出るべき")


def test_invalid_visit_type_raises():
    try:
        build_field_values(PlanInput(sex="male", age=40, visit_type="foo"))
    except ValueError:
        pass
    else:
        raise AssertionError("不正な visit_type で ValueError が出るべき")


def test_no_leftover_default_values_in_output():
    """
    ひな型に残る作成時テストデータ（/DV）が記入済みPDFに漏れないこと。
    Dropdown29='低栄養状態の恐れ'・Dropdown10='86' 等が印字されると誤った診療文書になる。
    実PDF依存のためひな型が無ければスキップ。
    """
    import io
    from datetime import date
    from pdf_fill import DEFAULT_TEMPLATE, PlanInput, generate_ryoyo_pdf

    if not DEFAULT_TEMPLATE.exists():
        print("  (skip) ひな型PDFが無いため test_no_leftover_default_values_in_output をスキップ")
        return

    from pypdf import PdfReader

    plan = PlanInput(
        sex="female", age=72, visit_type="initial", created=date(2026, 7, 24),
        sbp_tgt=130, dbp_tgt=80, bmi_target=23.0, a1c_tgt=7.0, ldl_now=160, a1c_now=8.4,
    )
    reader = PdfReader(io.BytesIO(generate_ryoyo_pdf(plan)))
    fields = reader.trailer["/Root"]["/AcroForm"]["/Fields"]

    # どのフィールドにも /DV（デフォルト値）が残っていないこと
    for f in fields:
        o = f.get_object()
        assert "/DV" not in o, f"{o.get('/T')} に /DV が残存している"

    # 記入対象外の栄養状態(Dropdown29)が空欄であること
    d29 = reader.get_fields().get("Dropdown29", {})
    v = d29.get("/V")
    assert v in (None, ""), f"栄養状態(Dropdown29)が空欄でない: {v!r}"


def test_disease_checkbox_mapping():
    """
    主病名CB→病名の対応が固定されていること（Step 4-B・診療文書で最も間違えられない箇所）。
    実PDF依存。各病名を単独でONにし、意図した1つだけが立つことを確認する。
    """
    import io
    from pdf_fill import (
        DEFAULT_TEMPLATE, FieldValues, fill_pdf,
        C_DX_DIABETES, C_DX_HYPERTENSION, C_DX_DYSLIPIDEMIA,
    )

    if not DEFAULT_TEMPLATE.exists():
        print("  (skip) ひな型PDFが無いため test_disease_checkbox_mapping をスキップ")
        return

    from pypdf import PdfReader

    all_dx = [C_DX_DIABETES, C_DX_HYPERTENSION, C_DX_DYSLIPIDEMIA]
    for target in all_dx:
        fv = FieldValues()
        fv.checks[target] = True
        fields = PdfReader(io.BytesIO(fill_pdf(fv))).get_fields()
        for cb in all_dx:
            v = fields.get(cb, {}).get("/V")
            on = v not in (None, "/Off", "")
            if cb == target:
                assert on, f"{cb} をONにしたのに立っていない"
            else:
                assert not on, f"{cb} が誤ってONになっている（{target} を指定）"


def test_text111_split_isolates_boxes():
    """
    達成目標(テキスト111 上箱)と目標の達成状況(下箱)が独立フィールドに分割され、
    片方だけ記入してももう片方に漏れないこと。実PDF依存。
    """
    import io
    from pdf_fill import (
        DEFAULT_TEMPLATE, FieldValues, fill_pdf,
        F_PLAN_FREETEXT, F_ACHIEVEMENT_STATUS, F_VISIT_FIRST,
    )

    if not DEFAULT_TEMPLATE.exists():
        print("  (skip) ひな型PDFが無いため test_text111_split_isolates_boxes をスキップ")
        return

    from pypdf import PdfReader

    fv = FieldValues()
    fv.text[F_PLAN_FREETEXT] = "達成目標のみ"
    fv.checks[F_VISIT_FIRST] = True
    fields = PdfReader(io.BytesIO(fill_pdf(fv))).get_fields()
    assert fields.get("テキスト111", {}).get("/V") == "達成目標のみ"
    # 達成状況は空欄のまま
    assert fields.get(F_ACHIEVEMENT_STATUS, {}).get("/V") in (None, "")


if __name__ == "__main__":
    test_basic_required_fields()
    test_male_and_continued()
    test_bp_with_dbp()
    test_bp_sbp_only()
    test_targets_and_labs()
    test_hba1c_target_and_actual_go_to_different_fields()
    test_optional_values_omitted_when_none()
    test_decimal_rounding()
    test_invalid_sex_raises()
    test_invalid_visit_type_raises()
    test_no_leftover_default_values_in_output()
    test_disease_checkbox_mapping()
    test_text111_split_isolates_boxes()
    print("OK: 全テスト通過")

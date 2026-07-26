# pdf_fill.py
# -*- coding: utf-8 -*-
"""
療養計画書PDF（AcroForm方式）の記入モジュール。PC版・モバイル版で共有する。

本ファイルは2層に分かれる:
  ① build_field_values(): アプリの状態 → PDFフィールド値への「変換ロジック」（純粋関数）
     ── どの値をどの欄に入れるか。間違えると誤った診療文書になる。PDF不要でテスト可能。
  ② fill_pdf() / generate_ryoyo_pdf(): pypdf で実際にAcroFormへ記入し、PDFバイト列を返す。
     ── チェックボックスON値は帳型から動的取得、NeedAppearances でフォント未埋め込みに対処。
        手法は scripts/pdf_smoke_check.py（Step 1で実証済み）と同じ。

フィールド対応は docs/pdf_forms/ryoyo_keikakusho_fields.csv の meaning_TODO 列と
ロードマップ Step 2（2026-07-24 ユーザー確認により確定）に対応する。
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, Optional, Union

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, BooleanObject, NameObject, TextStringObject

# ひな型PDF（v1.2）。帳票様式は診療報酬改定で変わるためバージョンをパスに含める。
DEFAULT_TEMPLATE = Path(__file__).resolve().parent / "docs" / "pdf_forms" / "ryoyo_keikakusho_v1.2.pdf"

# ---------------------------------------------------------------------------
# フィールド名の定数（CSVの field_name と一致）。
# ハードコードを1箇所に集約し、帳票改版時にここだけ直せばよいようにする。
# ---------------------------------------------------------------------------
# 基本情報
F_SEX = "Dropdown9"          # 選択肢 （男）|（女）
F_AGE = "Dropdown10"         # 選択肢 20..99（編集可能コンボ）
F_DATE_Y = "Dropdown3"       # 作成日:年（西暦）
F_DATE_M = "Dropdown4"       # 作成日:月
F_DATE_D = "Dropdown8"       # 作成日:日
F_VISIT_FIRST = "Check Box1"  # 初回
F_VISIT_CONT = "Check Box2"   # 継続

# 【目標】ブロック（数値欄 + 連動チェック）
F_BP = "Dropdown1"            # 目標血圧 収縮期/拡張期（例 130/80）
C_BP = "チェックボックス117"
F_BMI = "テキスト113"          # 目標BMI
C_BMI = "チェックボックス11"
F_A1C_TGT = "テキスト114"      # 目標HbA1c
C_A1C_TGT = "チェックボックス15"

# 【血液検査項目】ブロック（実測値 + 連動チェック）
F_LDL_NOW = "テキスト26"       # 実測LDLコレステロール
C_LDL_NOW = "チェックボックス79"
F_A1C_NOW = "テキスト21"       # 実測HbA1c
C_A1C_NOW = "チェックボックス13"

# --- 手入力項目（Step 4-B）。アプリが値を持たないため画面で手入力する欄。 ---
# 主病名（自動推定しない。CB→病名の対応はラベルx座標で確認済み・2026-07-24）
C_DX_DIABETES = "チェックボックス119"       # 糖尿病
C_DX_HYPERTENSION = "チェックボックス121"   # 高血圧症
C_DX_DYSLIPIDEMIA = "チェックボックス120"   # 脂質異常症
# 目標: 体重(kg)（BMIは自動17項目側 F_BMI）
F_WEIGHT = "テキスト8"
C_WEIGHT = "チェックボックス116"
# 栄養状態
F_NUTRITION = "Dropdown29"
C_NUTRITION = "チェックボックス83"
NUTRITION_OPTIONS = ("低栄養状態の恐れ", "良好", "肥満")
# 行動目標・達成目標（自由記述）。上の箱(y≈601)。
# 帳票上 テキスト111 は「達成目標」と「目標の達成状況」の別セクション2箱に同名で
# 割り当てられ値を共有してしまうため、fill_pdf で独立フィールドに分割する。
F_PLAN_FREETEXT = "テキスト111"
# 目標の達成状況（継続の場合のみ）。下の箱(y≈547)。分割後に付ける独立名。
F_ACHIEVEMENT_STATUS = "テキスト111_達成状況"

# 数値欄 → 連動してONにするチェックボックス。
# 編集可能な確認画面で「値が入っていればチェックON」を再導出するのに使う。
FIELD_CONNECTED_CHECK = {
    F_BP: C_BP,
    F_BMI: C_BMI,
    F_A1C_TGT: C_A1C_TGT,
    F_LDL_NOW: C_LDL_NOW,
    F_A1C_NOW: C_A1C_NOW,
    F_WEIGHT: C_WEIGHT,
    F_NUTRITION: C_NUTRITION,
}

# 性別コード → 帳票の選択肢文字列（Dropdown9 の options と厳密一致させる）
_SEX_LABEL = {"male": "（男）", "female": "（女）"}


@dataclass
class PlanInput:
    """
    療養計画書に記入する値。アプリの状態から詰めて渡す。
    None の項目は「記入しない（連動チェックもOFF）」を意味する。
    任意項目（BMI等）を出すかどうかの判断はUI層（Step 4）が行い、
    ここは渡された値を機械的に写すだけにする。
    """
    # 必須
    sex: str                       # "male" / "female"
    age: int
    visit_type: str                # "initial"（初回）/ "continued"（継続）
    created: date = field(default_factory=date.today)  # 作成日

    # 任意（None なら記入しない）
    sbp_tgt: Optional[int] = None  # 目標収縮期血圧
    dbp_tgt: Optional[int] = None  # 目標拡張期血圧（UIで新設・SBPとセットで記入）
    bmi_target: Optional[float] = None
    a1c_tgt: Optional[float] = None
    ldl_now: Optional[int] = None
    a1c_now: Optional[float] = None


@dataclass
class FieldValues:
    """記入処理（②）に渡す最終形。text=テキスト/ドロップダウン、checks=チェックボックス。"""
    text: Dict[str, str] = field(default_factory=dict)
    checks: Dict[str, bool] = field(default_factory=dict)


def _fmt_decimal(v: float) -> str:
    """BMI・HbA1c を小数1桁で。24.0 → '24.0'、7.25 → '7.3'。"""
    return f"{v:.1f}"


def build_field_values(plan: PlanInput) -> FieldValues:
    """アプリの状態 → PDFフィールド値。純粋関数（副作用なし・PDF不要）。"""
    fv = FieldValues()

    # --- 基本情報（必須） ---
    if plan.sex not in _SEX_LABEL:
        raise ValueError(f"sex は 'male'/'female' のいずれか: {plan.sex!r}")
    fv.text[F_SEX] = _SEX_LABEL[plan.sex]
    fv.text[F_AGE] = str(int(plan.age))

    fv.text[F_DATE_Y] = str(plan.created.year)
    fv.text[F_DATE_M] = str(plan.created.month)
    fv.text[F_DATE_D] = str(plan.created.day)

    if plan.visit_type == "initial":
        fv.checks[F_VISIT_FIRST] = True
    elif plan.visit_type == "continued":
        fv.checks[F_VISIT_CONT] = True
    else:
        raise ValueError(f"visit_type は 'initial'/'continued': {plan.visit_type!r}")

    # --- 【目標】ブロック ---
    # 目標血圧: SBP と DBP がそろえば "130/80"、SBPのみなら "130"
    if plan.sbp_tgt is not None:
        if plan.dbp_tgt is not None:
            fv.text[F_BP] = f"{int(plan.sbp_tgt)}/{int(plan.dbp_tgt)}"
        else:
            fv.text[F_BP] = str(int(plan.sbp_tgt))
        fv.checks[C_BP] = True

    if plan.bmi_target is not None:
        fv.text[F_BMI] = _fmt_decimal(plan.bmi_target)
        fv.checks[C_BMI] = True

    if plan.a1c_tgt is not None:
        fv.text[F_A1C_TGT] = _fmt_decimal(plan.a1c_tgt)
        fv.checks[C_A1C_TGT] = True

    # --- 【血液検査項目】ブロック（実測値） ---
    if plan.ldl_now is not None:
        fv.text[F_LDL_NOW] = str(int(plan.ldl_now))
        fv.checks[C_LDL_NOW] = True

    if plan.a1c_now is not None:
        fv.text[F_A1C_NOW] = _fmt_decimal(plan.a1c_now)
        fv.checks[C_A1C_NOW] = True

    return fv


# ---------------------------------------------------------------------------
# ② 記入処理（pypdf）。実際にAcroFormへ書き込む。
# ---------------------------------------------------------------------------
def _collect_checkbox_on_values(reader: PdfReader) -> Dict[str, str]:
    """
    各チェックボックスのON値を帳票から動的に読み出す（field_name -> ON値文字列）。

    この帳票のON値は /Yes ではなく「はい」のUTF-16BE表現（/þÿ0o0D）。
    ハードコードすると帳票の改版で壊れるため、必ず実物から取る。
    """
    result: Dict[str, str] = {}
    for page in reader.pages:
        for annot in page.get("/Annots") or []:
            obj = annot.get_object()
            name = obj.get("/T")
            if name is None:
                continue
            states = (obj.get("/AP") or {}).get("/N") or {}
            for state in states.keys():
                if state != "/Off":
                    result[str(name)] = str(state).lstrip("/")
                    break
    return result


def _split_shared_text111(writer: PdfWriter) -> None:
    """
    テキスト111 は帳票上、意味の異なる2箱に同名で割り当てられ値を共有してしまう:
      上の箱(y≈601) = 【①達成目標／②行動目標】、下の箱(y≈547) = 【目標の達成状況】(継続のみ)。
    これを2つの独立フィールドに分割し、別々に記入できるようにする。
      上 → F_PLAN_FREETEXT("テキスト111") / 下 → F_ACHIEVEMENT_STATUS。
    """
    fields = writer._root_object["/AcroForm"]["/Fields"]
    parent_obj = None
    for ref in fields:
        o = ref.get_object()
        if str(o.get("/T")) == "テキスト111" and o.get("/Kids"):
            parent_obj = o
            break
    if parent_obj is None:
        return  # 構造が違う／既に分割済み

    kids = list(parent_obj["/Kids"])
    if len(kids) != 2:
        return

    kids.sort(key=lambda k: float(k.get_object()["/Rect"][1]), reverse=True)  # [0]=上, [1]=下
    da = parent_obj.get("/DA")
    ff = parent_obj.get("/Ff")

    for kid, name in zip(kids, ("テキスト111", F_ACHIEVEMENT_STATUS)):
        ko = kid.get_object()
        ko[NameObject("/T")] = TextStringObject(name)
        ko[NameObject("/FT")] = NameObject("/Tx")
        if da is not None and "/DA" not in ko:
            ko[NameObject("/DA")] = da
        if ff is not None and "/Ff" not in ko:
            ko[NameObject("/Ff")] = ff
        if "/Parent" in ko:
            del ko[NameObject("/Parent")]

    # 親を除き、2つの子を独立フィールドとして /Fields に据える
    new_fields = ArrayObject(
        [r for r in fields if r.get_object() is not parent_obj]
    )
    new_fields.extend(kids)
    writer._root_object["/AcroForm"][NameObject("/Fields")] = new_fields


def fill_pdf(
    field_values: FieldValues,
    template_path: Union[str, Path] = DEFAULT_TEMPLATE,
) -> bytes:
    """
    FieldValues をひな型PDFに記入し、PDFのバイト列を返す。

    - テキスト/ドロップダウン: update_page_form_field_values で /V を設定
    - チェックボックス: /V と /AS の両方に NameObject を入れる
      （文字列で渡すと pypdf が別型で書き、ビューアが /Off として扱うため）
    - AcroForm に NeedAppearances=true を立て、ビューア側に外観を再生成させる
      （日本語フォントが未埋め込みのため）
    """
    reader = PdfReader(str(template_path))
    on_values = _collect_checkbox_on_values(reader)

    # 記入対象のチェックボックスがひな型に存在するか先に検証（対応表ズレを早期検出）
    for cb_name, on in field_values.checks.items():
        if on and cb_name not in on_values:
            raise KeyError(f"チェックボックスがひな型に無い: {cb_name}")

    writer = PdfWriter(clone_from=str(template_path))
    # 同名2箱の テキスト111 を独立フィールドに分割（達成目標／達成状況を別々に記入可能に）
    _split_shared_text111(writer)

    for page in writer.pages:
        if field_values.text:
            writer.update_page_form_field_values(
                page, field_values.text, auto_regenerate=False
            )
        for annot in page.get("/Annots") or []:
            obj = annot.get_object()
            name = obj.get("/T")
            if name is None:
                continue
            name = str(name)
            if field_values.checks.get(name):
                on = on_values[name]
                obj[NameObject("/V")] = NameObject(f"/{on}")
                obj[NameObject("/AS")] = NameObject(f"/{on}")

    # ひな型に残る作成時のテストデータ（/DV デフォルト値・/V・/I）を掃除する。
    # 例: Dropdown29 /DV='低栄養状態の恐れ'、Dropdown10 /DV='86'。
    # 記入しない欄にこれらが残ると NeedAppearances 再生成時に印字され、誤情報になる。
    fill_names = set(field_values.text) | {
        name for name, on in field_values.checks.items() if on
    }
    for f in writer._root_object["/AcroForm"]["/Fields"]:
        obj = f.get_object()
        name = obj.get("/T")
        # デフォルト値は印字対象ではないので、記入する欄も含め全て除去する。
        for key in ("/DV",):
            if key in obj:
                del obj[NameObject(key)]
        # 記入しない欄は現在値・選択インデックスも消して空欄にする。
        if name is None or str(name) not in fill_names:
            for key in ("/V", "/I"):
                if key in obj:
                    del obj[NameObject(key)]

    # フォント未埋め込み対策。ビューア側に外観を再生成させる。
    # 注意: update_page_form_field_values(auto_regenerate=False) が NeedAppearances を
    # False に戻すため、必ず記入ループの後に立てる。
    writer._root_object["/AcroForm"][NameObject("/NeedAppearances")] = BooleanObject(True)

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def generate_ryoyo_pdf(
    plan: PlanInput,
    template_path: Union[str, Path] = DEFAULT_TEMPLATE,
) -> bytes:
    """アプリの状態（PlanInput）から記入済み療養計画書PDFのバイト列を返す（①→②の一括）。"""
    return fill_pdf(build_field_values(plan), template_path)

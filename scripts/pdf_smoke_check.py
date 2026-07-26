#!/usr/bin/env python3
"""
療養計画書PDF 疎通検証スクリプト（ロードマップ Step 1 / Step 5 兼用）

目的:
  ひな型の日本語フォント KozMinPr6N-Regular は参照のみで埋め込まれていない。
  記入した日本語が読み手の環境で表示されるかを、作り込む前に実物で確かめる。

確認手順（生成後、人が目で見る）:
  1. Acrobat で開く
  2. ブラウザ（pdf.js）で開く
  3. 実際に印刷する
  3環境すべてで文字が出て、チェックが入って見えれば合格。

使い方:
  .venv/bin/python scripts/pdf_smoke_check.py
  -> out/pdf_smoke/ryoyo_smoke.pdf を生成（out/ はgit管理外）
"""
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, BooleanObject

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "docs" / "pdf_forms" / "ryoyo_keikakusho_v1.2.pdf"
OUT = ROOT / "out" / "pdf_smoke" / "ryoyo_smoke.pdf"

# 検証用の最小セット。テキスト1欄に日本語、チェックボックス1個をON。
TEXT_FIELD = "テキスト111"   # 本文の広い欄。文字が読めるか確認しやすい
TEXT_VALUE = "日本語表示テスト：高血圧症・脂質異常症・糖尿病 ①②③ 130/80mmHg"
CHECK_FIELD = "Check Box1"


def checkbox_on_value(reader: PdfReader, field_name: str) -> str:
    """
    チェックボックスのON値をひな型から動的に読み出す。

    この帳票のON値は /Yes ではなく「はい」のUTF-16BE表現（/þÿ0o0D）。
    ハードコードすると帳票の改版で壊れるため、必ず実物から取る。
    """
    for page in reader.pages:
        for annot in page.get("/Annots") or []:
            obj = annot.get_object()
            if obj.get("/T") != field_name:
                continue
            states = (obj.get("/AP") or {}).get("/N") or {}
            for state in states.keys():
                if state != "/Off":
                    return str(state).lstrip("/")
    raise KeyError(f"チェックボックスが見つからない: {field_name}")


def main() -> None:
    reader = PdfReader(TEMPLATE)
    on_value = checkbox_on_value(reader, CHECK_FIELD)
    print(f"CB ON値（実測）: {on_value!r}")

    writer = PdfWriter(clone_from=TEMPLATE)

    # フォント未埋め込み対策。ビューア側に外観を再生成させる。
    writer._root_object["/AcroForm"][NameObject("/NeedAppearances")] = BooleanObject(True)

    for page in writer.pages:
        writer.update_page_form_field_values(page, {TEXT_FIELD: TEXT_VALUE})
        # チェックボックスは /V と /AS の両方に NameObject を入れる必要がある。
        # 文字列で渡すと pypdf が別型で書き込み、ビューアが /Off として扱う。
        for annot in page.get("/Annots") or []:
            obj = annot.get_object()
            if obj.get("/T") == CHECK_FIELD:
                obj[NameObject("/V")] = NameObject(f"/{on_value}")
                obj[NameObject("/AS")] = NameObject(f"/{on_value}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("wb") as f:
        writer.write(f)
    print(f"生成: {OUT}")
    print("Acrobat / ブラウザ / 印刷 の3経路で確認してください。")


if __name__ == "__main__":
    main()

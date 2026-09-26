"""Extract the exact MHLW rows used to fill the 36 previously unpriced doses.

Usage: python scripts/resolve_medication_prices.py oral.xlsx injection.xlsx
Outputs the auditable JSON price manifest; does not author workbooks.
"""
import hashlib
import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd

BP = "降圧薬詳細_Ca-ARNI_薬価付き_日本語表_英語タイトル引用付き.xlsx"
OTHER = "LDL_HbA1c_用量別_薬価付き_日本語表_英語タイトル引用付き.xlsx"
SOURCE = "https://www.mhlw.go.jp/topics/2026/04/tp20260401-01.html"
# Row, official drug code, annual price-unit consumption, description.
GROUPS = [
    (BP, "Sheet1", [
        (32, "2149042F1017", 365, "1錠/日 × 365日"),
        (33, "2149042F2013", 365, "1錠/日 × 365日"),
        (34, "2149042F3010", 365, "1錠/日 × 365日"),
        (35, "2149040F2014", 365, "1錠/日 × 365日"),
        (36, "2149040F3010", 365, "1錠/日 × 365日"),
        (37, "2149040F4017", 365, "1錠/日 × 365日"),
        (38, "2171014G4061", 365, "CR20mg錠 1錠/日 × 365日"),
        (39, "2171014G5068", 365, "CR40mg錠 1錠/日 × 365日"),
        (40, "2149037F2012", 365, "1錠/日 × 365日"),
        (41, "2149037F3019", 365, "1錠/日 × 365日"),
        (42, "2132004F2037", 365, "12.5mg錠 1錠/日 × 365日"),
        (43, "2132004F1103", 365, "25mg錠 1錠/日 × 365日"),
        (44, "2133001F1018", 365, "1錠/日 × 365日"),
    ]),
    (OTHER, "LDL用量別（薬価付き）", [
        (12, "2189017F1014", 365, "2.5mg錠 1錠/日 × 365日"),
        (13, "2189015F1015", 365, "5mg錠 1錠/日 × 365日"),
        (14, "2189016F1010", 365, "1mg錠 1錠/日 × 365日"),
        (15, "2189016F3012", 365, "4mg錠 1錠/日 × 365日"),
        (16, "2189010F2353", 365, "10mg錠 1錠/日 × 365日"),
        (17, "2189010F2353", 730, "10mg錠 2錠/日 × 365日"),
        (18, "2189403G1029", 2, "維持期2筒/年。初年度は0・3・9か月の3筒。300mgナトリウム塩＝インクリシラン284mg"),
    ]),
    (OTHER, "HbA1c用量別（薬価付き）", [
        (14, "3962002F2019", 365, "250mg MT錠 1錠/日 × 365日（選択用量を1日量として算出）"),
        (15, "3962002F3015", 730, "500mg MT錠 2錠/日 × 365日"),
        (16, "3969019F1027", 365, "5mg錠 1錠/日 × 365日"),
        (17, "3969019F2023", 365, "10mg錠 1錠/日 × 365日"),
        (18, "3969022F1029", 365, "1錠/日 × 365日"),
        (19, "3969018F2029", 365, "1錠/日 × 365日"),
        (20, "3969010F2030", 365, "1錠/日 × 365日"),
        (21, "3969015F1029", 365, "1錠/日 × 365日"),
        (22, "2499416G1029", 52, "0.75mgキット 1回/週 × 52週（既存週1回薬と同じ年換算）"),
        (23, "2499410G1021", 18.25, "18mgキット × 0.9mg/日 ÷ 18mg × 365日。消費量按分、端数キット・針代・導入漸増を除く"),
        (24, "2499410G1021", 36.5, "18mgキット × 1.8mg/日 ÷ 18mg × 365日。消費量按分、端数キット・針代・導入漸増を除く"),
        (25, "3961008F3015", 365, "0.5mg錠 1錠/日 × 365日"),
        (26, "3961008F1012", 365, "1mg錠 1錠/日 × 365日"),
        (27, "3969007F1016", 365, "15mg錠 1錠/日 × 365日"),
        (28, "3969007F2012", 365, "30mg錠 1錠/日 × 365日"),
        (29, "3969026F1027", 1460, "500mg錠 2錠/回 × 2回/日 × 365日"),
    ]),
]


def main():
    paths = [Path(p) for p in sys.argv[1:]]
    assert len(paths) == 2
    source = pd.concat([pd.read_excel(p) for p in paths], ignore_index=True)
    records = []
    for filename, sheet, selections in GROUPS:
        current = pd.read_excel(filename, sheet_name=sheet)
        for row_number, code, units, basis in selections:
            matches = source[source["薬価基準収載医薬品コード"] == code]
            assert len(matches) == 1, code
            item = matches.iloc[0]
            price = Decimal(str(item["薬価"]))
            annual = int((price * Decimal(str(units))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            records.append(dict(
                workbook=filename, sheet=sheet, row=row_number,
                key=current.iloc[row_number-2]["薬剤名・用量"],
                code=code, product=item["品名"], specification=item["規格"],
                price_yen=float(price), annual_units=units, annual_cost_yen=annual,
                calculation=basis,
                first_year_cost_yen=int(price * 3) if code == "2189403G1029" else None,
                source_file="tp20260813-01_02.xlsx" if item["区分"] == "注射薬" else "tp20260813-01_01.xlsx",
            ))
    manifest = dict(source=SOURCE, effective_date="2026-08-13", checked_date="2026-09-26",
                    source_sha256=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths],
                    policy="商品名指定は該当商品、一般名は記録した普通錠の統一名収載価格または代表後発品。薬剤料のみ。",
                    records=records)
    destination = Path("docs/medication_prices_20260926.json")
    destination.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
    print(f"Resolved {len(records)} doses from official drug codes: {destination}")


if __name__ == "__main__":
    main()

import unittest
from pathlib import Path
from meds_catalog import MEDICATION_CLASS_ORDER, load_meds_catalog


class MedicationClassOrderTests(unittest.TestCase):
    def test_catalog_uses_agreed_class_order(self):
        root = Path(__file__).resolve().parents[1]
        catalog = load_meds_catalog(
            str(root / "降圧薬詳細_Ca-ARNI_薬価付き_日本語表_英語タイトル引用付き.xlsx"),
            str(root / "LDL_HbA1c_用量別_薬価付き_日本語表_英語タイトル引用付き.xlsx"),
        )
        self.assertEqual(sum(map(len, catalog.values())), 88)
        for domain, meds in catalog.items():
            self.assertEqual(list(dict.fromkeys(m["category"] for m in meds)),
                             list(MEDICATION_CLASS_ORDER[domain]))
            self.assertEqual(len({m["key"] for m in meds}), len(meds))


if __name__ == "__main__":
    unittest.main()

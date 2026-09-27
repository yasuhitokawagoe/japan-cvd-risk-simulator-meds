from dataclasses import FrozenInstanceError
from pathlib import Path
import unittest
from urllib.parse import urlparse

from bone_health import OSTEOPOROSIS_DRUGS
from meds_catalog import load_meds_catalog
from pharmacist_guidance import (
    GUIDES, BY_ID, BY_NAME, CLASSES, LOW_GLUCOSE,
    candidate_ids, selection_alerts, export_ready, handout_html,
)

ROOT = Path(__file__).resolve().parents[1]


class PharmacistGuidanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_meds_catalog(
            str(ROOT / "降圧薬詳細_Ca-ARNI_薬価付き_日本語表_英語タイトル引用付き.xlsx"),
            str(ROOT / "LDL_HbA1c_用量別_薬価付き_日本語表_英語タイトル引用付き.xlsx"),
        )

    def test_every_catalog_dose_and_bone_drug_has_exact_reviewed_mapping(self):
        meds = [m for domain in self.catalog.values() for m in domain]
        self.assertEqual(len(meds), 88)
        self.assertEqual(len({m["drug_name"] for m in meds}), 40)
        ids, missing = candidate_ids(meds)
        self.assertEqual(missing, [])
        self.assertEqual(len(ids), 40)
        self.assertEqual(len(GUIDES), 47)
        for key, drug in OSTEOPOROSIS_DRUGS.items():
            if key == "none":
                continue
            with self.subTest(key=key):
                self.assertEqual(candidate_ids([], key), ([key], []))
                self.assertEqual(BY_ID[key].name, drug["label"])

    def test_unique_ids_names_and_primary_sources_nonempty_sections(self):
        self.assertEqual(len(GUIDES), len(BY_ID))
        self.assertEqual(len(GUIDES), len(BY_NAME))
        for guide in GUIDES:
            with self.subTest(drug=guide.id):
                self.assertIn(urlparse(guide.source_url).hostname, {"www.pmda.go.jp", "www.info.pmda.go.jp"})
                self.assertEqual(urlparse(guide.source_url).scheme, "https")
                for field in ("focus", "routine", "sick", "urgent", "missed"):
                    self.assertTrue(getattr(guide.content, field))

    def test_unknown_drug_is_not_silently_given_a_class_template(self):
        ids, missing = candidate_ids([{"drug_name": "未知のSGLT2薬", "key": "未知のSGLT2薬 5mg", "category": "SGLT2阻害薬"}], "unknown_bone")
        self.assertEqual(ids, [])
        self.assertEqual(missing, ["未知のSGLT2薬 5mg", "unknown_bone"])
        self.assertFalse(export_ready(["unknown"], {}, actual_confirmed=True, reviewed=True))

    def test_dose_variants_deduplicated_without_mutation(self):
        meds = [{"drug_name": "メトホルミン", "key": "メトホルミン 500mg"},
                {"drug_name": "メトホルミン", "key": "メトホルミン 1000mg"}]
        original = [dict(m) for m in meds]
        self.assertEqual(candidate_ids(meds), (["metformin"], []))
        self.assertEqual(meds, original)
        with self.assertRaises(FrozenInstanceError):
            BY_ID["metformin"].name = "changed"

    def test_sick_day_is_drug_specific_and_no_blanket_bp_cutoff(self):
        for group in ("sglt2", "metformin"):
            self.assertIn("休薬", "".join(CLASSES[group].sick))
            self.assertIn("再開", "".join(CLASSES[group].sick))
        self.assertIn("急に中断", "".join(CLASSES["beta"].routine))
        self.assertIn("一律の休薬", "".join(CLASSES["dpp4"].sick))
        self.assertIn("機械的には", "".join(CLASSES["imeglimin"].sick))
        self.assertIn("口に物を入れず119", LOW_GLUCOSE)
        self.assertNotIn("90mmHg", str(CLASSES))

    def test_formulation_specific_reminders(self):
        self.assertIn("120mL", str(BY_ID["semaglutide_oral"].content.routine))
        self.assertIn("翌日", BY_ID["semaglutide_oral"].content.missed)
        self.assertIn("48時間", BY_ID["semaglutide_injection"].content.missed)
        self.assertIn("72時間", BY_ID["tirzepatide"].content.missed)
        self.assertIn("72時間", BY_ID["dulaglutide"].content.missed)
        self.assertIn("1日1回", str(BY_ID["liraglutide"].content.routine))
        self.assertIn("CR錠", str(BY_ID["nifedipine"].content.routine))

    def test_export_requires_all_confirmations_actual_regimens_and_valid_selection(self):
        ids = ["metformin", "amlodipine"]
        regimens = {key: "架空の確認済み用法" for key in ids}
        for actual, reviewed in ((False, False), (True, False), (False, True)):
            self.assertFalse(export_ready(ids, regimens, actual_confirmed=actual, reviewed=reviewed))
            with self.assertRaises(ValueError):
                handout_html(ids, regimens, {}, "", actual_confirmed=actual, reviewed=reviewed)
        self.assertFalse(export_ready(ids, {"metformin": "あり", "amlodipine": " "}, actual_confirmed=True, reviewed=True))
        self.assertFalse(export_ready([], {}, actual_confirmed=True, reviewed=True))
        self.assertTrue(export_ready(ids, regimens, actual_confirmed=True, reviewed=True))

    def test_document_escapes_input_and_contains_every_safety_section(self):
        html = handout_html(["metformin"], {"metformin": '<script>alert(1)</script>'},
                            {"metformin": '<img src=x onerror="bad()">'}, "<b>test</b>",
                            actual_confirmed=True, reviewed=True)
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img ", html)
        self.assertIn("&lt;script&gt;", html)
        for text in ("119番", "体調が悪いとき", "休薬", "再開", "低血糖", "根拠：PMDA"):
            self.assertIn(text, html)
        self.assertIn("未記入", handout_html(["metformin"], {"metformin": "確認済み"}, {}, "", actual_confirmed=True, reviewed=True))

    def test_every_drug_can_generate_a_handout_individually(self):
        for guide in GUIDES:
            with self.subTest(drug=guide.id):
                html = handout_html([guide.id], {guide.id: "架空の確認済み用法"}, {}, "", actual_confirmed=True, reviewed=True)
                self.assertIn(guide.name, html)
                self.assertIn("用法", html)
                self.assertIn("体調が悪いとき", html)

    def test_known_contraindicated_combinations_block_export_but_others_do_not(self):
        for ids in (["enalapril", "sacubitril_valsartan"], ["spironolactone", "esaxerenone"]):
            self.assertTrue(any(level == "block" for level, _ in selection_alerts(ids)))
            self.assertFalse(export_ready(ids, {key: "確認済み" for key in ids}, actual_confirmed=True, reviewed=True))
        self.assertEqual(selection_alerts(["amlodipine", "telmisartan"]), [])
        for ids in (["dulaglutide", "sitagliptin"], ["semaglutide_oral", "semaglutide_injection"],
                    ["empagliflozin", "hctz"], ["glimepiride", "metformin"],
                    ["atorvastatin", "bempedoic_acid"], ["telmisartan", "losartan"]):
            self.assertTrue(selection_alerts(ids))
            self.assertFalse(any(level == "block" for level, _ in selection_alerts(ids)))


if __name__ == "__main__":
    unittest.main()

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from patient_report_pdf import generate_patient_report_pdf


def _risks():
    result = {}
    for key, now, after in (
        ("mortality", 20.0, 15.0), ("mi", 8.0, 5.0), ("stroke", 12.0, 7.0),
    ):
        result[key] = {
            "time": [0, 10, 20],
            "baseline_cumulative": [0, now / 2, now],
            "target_cumulative": [0, after / 2, after],
        }
    return result


def test_patient_report_is_two_page_pdf():
    pdf = generate_patient_report_pdf(
        age=60, sex_label="男性", height_cm=165, weight_kg=65,
        current_values={"sbp": 150, "ldl": 160, "a1c": 8.0},
        target_values={"sbp": 130, "ldl": 100, "a1c": 7.0},
        diagnoses=["糖尿病", "高血圧症"], medications=["薬A"],
        lifestyle_interventions=["減塩", "中強度有酸素運動"],
        instructions=["食塩・調味料を控える"], goals=["毎日歩く"],
        risks=_risks(), horizon_years=20,
    )
    assert pdf.startswith(b"%PDF-")
    from pypdf import PdfReader
    assert len(PdfReader(io.BytesIO(pdf)).pages) == 2


if __name__ == "__main__":
    test_patient_report_is_two_page_pdf()
    print("OK: patient report PDF tests passed")

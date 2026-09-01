"""A4 QR handout for attaching to health-check results."""
from __future__ import annotations

from io import BytesIO

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _font() -> str:
    candidates = [
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        try:
            pdfmetrics.registerFont(TTFont("CheckupJP", path, subfontIndex=0))
            return "CheckupJP"
        except Exception:
            continue
    # Built into PDF viewers and available in ReportLab without shipping a font file.
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
        return "HeiseiKakuGo-W5"
    except Exception:
        return "Helvetica"


def create_checkup_handout(url: str, facility_name: str = "") -> bytes:
    """Create a tasteful one-page A4 handout with a QR code when available."""
    font = _font()
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=24 * mm, rightMargin=24 * mm,
                            topMargin=24 * mm, bottomMargin=20 * mm)
    navy, teal, mist = HexColor("#17324D"), HexColor("#147D75"), HexColor("#EFF7F5")
    title = ParagraphStyle("title", fontName=font, fontSize=23, leading=32, textColor=navy,
                           alignment=TA_CENTER, spaceAfter=5 * mm)
    body = ParagraphStyle("body", fontName=font, fontSize=11, leading=19, textColor=HexColor("#425466"),
                          alignment=TA_CENTER)
    small = ParagraphStyle("small", fontName=font, fontSize=8.5, leading=14,
                           textColor=HexColor("#66788A"), alignment=TA_CENTER)
    story = [Spacer(1, 9 * mm), Paragraph("健診、おつかれさまでした。", title),
             Paragraph("その数字を「未来」にしてみませんか？", title), Spacer(1, 3 * mm),
             Paragraph("お手元の健診結果から、今の状態と、生活や治療を変えた未来を比較できます。", body),
             Spacer(1, 10 * mm)]
    qr_flowable = None
    try:
        import qrcode
        from reportlab.platypus import Image
        qr = qrcode.QRCode(box_size=8, border=2)
        qr.add_data(url); qr.make(fit=True)
        image = qr.make_image(fill_color="#17324D", back_color="white")
        qr_buf = BytesIO(); image.save(qr_buf, format="PNG"); qr_buf.seek(0)
        qr_flowable = Image(qr_buf, 48 * mm, 48 * mm)
    except Exception:
        qr_flowable = Paragraph("QRコードはURL発行環境で生成されます", small)
    box = Table([[qr_flowable], [Paragraph("スマートフォンで読み取る　｜　約3分", body)]],
                colWidths=[78 * mm], rowHeights=[58 * mm, 14 * mm])
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), mist), ("BOX", (0, 0), (-1, -1), .6, teal),
                             ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("ROUNDEDCORNERS", [8])]))
    story += [box, Spacer(1, 8 * mm), Paragraph(url, small), Spacer(1, 11 * mm),
              Paragraph("本サービスは医療診断ではありません。表示値は研究データに基づく推定値です。<br/>医薬品を自己判断で変更せず、治療については医療専門職へご相談ください。", small)]
    if facility_name:
        story += [Spacer(1, 8 * mm), Paragraph(facility_name, body)]
    doc.build(story)
    return buf.getvalue()

"""Renders every vendor's .txt contract documents to PDF via reportlab, so
the seed data ships as both realistic PDFs and plain text (for the demo-mode
extraction path to have something to point at)."""
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

DATA = Path(__file__).resolve().parents[1] / "data"
VENDORS_TXT = DATA / "vendors"
PROPOSAL_TXT = DATA / "proposal"


def txt_to_pdf(txt_path: Path):
    pdf_path = txt_path.with_suffix(".pdf")
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(pdf_path), pagesize=LETTER,
                             leftMargin=1 * inch, rightMargin=1 * inch, topMargin=1 * inch, bottomMargin=1 * inch)
    story = []
    for para in txt_path.read_text(encoding="utf-8").split("\n\n"):
        para = para.strip()
        if not para:
            continue
        text = para.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
        first_line = para.split("\n")[0]
        style = styles["Heading3"] if first_line.isupper() and len(first_line) < 60 else styles["BodyText"]
        story.append(Paragraph(text, style))
        story.append(Spacer(1, 10))
    doc.build(story)
    return pdf_path


def main():
    count = 0
    paths = sorted(VENDORS_TXT.glob("*/*.txt")) + sorted(PROPOSAL_TXT.glob("*.txt"))
    for txt_path in paths:
        pdf_path = txt_to_pdf(txt_path)
        print(f"  {txt_path.relative_to(DATA)} -> {pdf_path.name}")
        count += 1
    print(f"Rendered {count} PDFs.")


if __name__ == "__main__":
    main()

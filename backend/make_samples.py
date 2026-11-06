"""Generates the demo sample files in ../docs/sample_content (TXT, DOCX, PDF, PNG)."""
from pathlib import Path

import docx
import pymupdf
from PIL import Image, ImageDraw, ImageFont

from app.services.seed import SAMPLE_TEXT

out = Path(__file__).resolve().parents[1] / "docs" / "sample_content"
out.mkdir(parents=True, exist_ok=True)
(out / "sample_violations.txt").write_text(SAMPLE_TEXT, encoding="utf-8")

d = docx.Document()
d.add_heading("TechNova Cloud announcement (DEMO)", 1)
d.add_paragraph(SAMPLE_TEXT)
d.save(out / "sample_violations.docx")

pdf = pymupdf.open()
page = pdf.new_page()
page.insert_textbox(pymupdf.Rect(50, 50, 545, 400), "TechNova Cloud announcement (DEMO)\n\n" + SAMPLE_TEXT, fontsize=12)
pdf.save(out / "sample_violations.pdf")

img = Image.new("RGB", (1500, 360), "white")
dr = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34)
except OSError:
    font = ImageFont.load_default()
dr.text((40, 40), "Tech Nova Cloud is India's No. 1 cloud platform.", fill="black", font=font)
dr.text((40, 130), "Only Rs 1299 per month with 100% guaranteed results.", fill="black", font=font)
img.save(out / "sample_violations.png")
print("samples written to", out)

"""Export the editable architecture SVG as vector PDF and 300-dpi PNG."""
from pathlib import Path
import pymupdf

ROOT = Path(__file__).resolve().parent
source = pymupdf.open(ROOT / "edgelvef-architecture.svg")
pdf = pymupdf.open("pdf", source.convert_to_pdf())
pdf.save(ROOT / "edgelvef-architecture.pdf")
pdf[0].get_pixmap(dpi=300).save(ROOT / "edgelvef-architecture.png")
print("Exported editable SVG, vector PDF and 300-dpi PNG")

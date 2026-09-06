"""Shared reportlab paragraph styles and table-styling colors for every export PDF
(eo_pdf.py, factcheck_pdf.py) -- one visual identity across exports, not redefined
per-file."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

HEADER_BG = colors.HexColor("#EDE7DD")
GRID_LINE = colors.HexColor("#CCCCCC")

_styles = getSampleStyleSheet()
TITLE = ParagraphStyle("ExportTitle", parent=_styles["Title"], fontSize=22, spaceAfter=6)
H1 = ParagraphStyle(
    "ExportH1", parent=_styles["Heading1"], fontSize=14, spaceBefore=10, spaceAfter=6
)
H2 = ParagraphStyle(
    "ExportH2", parent=_styles["Heading2"], fontSize=11, spaceBefore=8, spaceAfter=4
)
BODY = ParagraphStyle("ExportBody", parent=_styles["BodyText"], fontSize=9, leading=12)
SMALL = ParagraphStyle(
    "ExportSmall",
    parent=_styles["BodyText"],
    fontSize=8,
    leading=10,
    textColor=colors.HexColor("#555555"),
)

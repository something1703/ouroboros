"""Fact-check report PDF (PHASE_08.md §8.5): timecode-ordered verdicts with corrected
wording, for factual (TRUE CUT) claims -- the narration/on-screen-text accuracy
counterpart to eo_pdf.py's legal evidence pack.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from packages.claims.enums import ClaimKind
from packages.claims.models import Claim, Evidence
from packages.exports._pdf_styles import BODY, GRID_LINE, H1, HEADER_BG, SMALL, TITLE
from packages.ledger.repositories import ClaimRepo, EvidenceRepo, ProjectRepo

_VERDICT_COLOR_HEX = {
    "contradicted": "#B3261E",
    "partially_supported": "#946200",
    "supported": "#3A6B35",
    "unverifiable": "#666666",
}


def _timecode(claim: Claim) -> str:
    if claim.source.t_start_ms is not None:
        total_s = claim.source.t_start_ms // 1000
        return f"{total_s // 60:02d}:{total_s % 60:02d}"
    if claim.source.page is not None:
        return f"p.{claim.source.page}"
    return "-"


def _sort_key(claim: Claim) -> tuple[bool, int, bool, int]:
    # Matches services/dashboard_api/main.py::get_asset_timeline's own mixed sort key:
    # video claims by time, script-sourced factual claims (page-based) after them.
    return (
        claim.source.t_start_ms is None,
        claim.source.t_start_ms or 0,
        claim.source.page is None,
        claim.source.page or 0,
    )


def _verdict_flowable(claim: Claim, evidence: Evidence | None) -> list[object]:
    verdict = str(evidence.output.get("verdict", "unverifiable")) if evidence else "unverifiable"
    color_hex = _VERDICT_COLOR_HEX.get(verdict, "#666666")
    flow: list[object] = [
        Paragraph(
            f'<font color="{color_hex}">[{_timecode(claim)} — {verdict.upper()}]</font> '
            f"{claim.entity_text}",
            H1,
        ),
        Paragraph(f"As stated: {claim.claim_text}", BODY),
    ]
    if evidence is not None:
        corrected = evidence.output.get("corrected_statement") or evidence.output.get(
            "recommended_wording"
        )
        if corrected:
            flow.append(Paragraph(f"Corrected wording: {corrected}", BODY))
        summary = evidence.output.get("key_evidence_summary")
        if summary:
            flow.append(Spacer(1, 4))
            flow.append(Paragraph(str(summary), SMALL))
        seen: set[str] = set()
        citation_lines = []
        for basis in evidence.basis:
            for citation in basis.citations:
                if citation.url in seen:
                    continue
                seen.add(citation.url)
                citation_lines.append(
                    f"&bull; {citation.url} (retrieved {citation.retrieved_at.strftime('%Y-%m-%d')})"
                )
        if citation_lines:
            flow.append(Spacer(1, 4))
            flow.extend(Paragraph(line, SMALL) for line in citation_lines)
    else:
        flow.append(Paragraph("No evidence recorded yet.", SMALL))
    return flow


def generate_factcheck_report(session: Session, project_id: str) -> bytes:
    """Timecode-ordered verdicts for every factual (TRUE CUT) claim, with corrected
    wording where evidence contradicts or partially supports the original statement."""
    project = ProjectRepo.require(session, project_id)
    claims = [
        claim
        for claim in ClaimRepo.list_by_project(session, project_id, limit=100_000)
        if claim.kind == ClaimKind.FACTUAL
    ]
    claims.sort(key=_sort_key)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=LETTER, topMargin=0.75 * inch, bottomMargin=0.75 * inch
    )
    story: list[object] = [
        Paragraph("Fact-Check Report", TITLE),
        Paragraph(project.title, H1),
        Paragraph(
            f"Project ID: {project.project_id} &nbsp;&nbsp; Generated: "
            f"{datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
            BODY,
        ),
        Spacer(1, 12),
    ]

    verdict_counts: dict[str, int] = {}
    for claim in claims:
        evidence = EvidenceRepo.latest_for_claim(session, claim.claim_id)
        verdict = (
            str(evidence.output.get("verdict", "unverifiable")) if evidence else "unverifiable"
        )
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1

    summary_rows = [["Verdict", "Claims"]]
    for verdict in ("contradicted", "partially_supported", "unverifiable", "supported"):
        if verdict in verdict_counts:
            summary_rows.append([verdict.replace("_", " "), str(verdict_counts[verdict])])
    summary_table = Table(summary_rows, colWidths=[2.2 * inch, 1 * inch])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("GRID", (0, 0), (-1, -1), 0.5, GRID_LINE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.append(summary_table)
    story.append(PageBreak())

    if not claims:
        story.append(Paragraph("No factual claims recorded for this project.", BODY))
    for i, claim in enumerate(claims):
        evidence = EvidenceRepo.latest_for_claim(session, claim.claim_id)
        story.extend(_verdict_flowable(claim, evidence))
        if i < len(claims) - 1:
            story.append(Spacer(1, 10))

    doc.build(story)
    return buffer.getvalue()

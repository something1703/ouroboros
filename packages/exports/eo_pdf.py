"""E&O (Errors & Omissions) evidence pack PDF (PHASE_08.md §8.5): cover, a summary
table by risk level, then one page per `high`/`blocking` claim with its full evidence
trail — the document an E&O insurer or a studio's legal department actually reviews
before underwriting a production.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from config.parallel import days_to_release, frequency_for
from packages.claims.enums import RiskLevel
from packages.claims.models import Claim, Evidence, Risk, VerificationEvent
from packages.exports._pdf_styles import BODY, GRID_LINE, H1, H2, HEADER_BG, SMALL, TITLE
from packages.ledger.projections import Projector
from packages.ledger.repositories import ClaimRepo, EvidenceRepo, HistoryRepo, ProjectRepo, RiskRepo

_HIGH_RISK = frozenset({RiskLevel.HIGH, RiskLevel.BLOCKING})
# Plain hex strings for inline `<font color="...">` markup (Paragraph's mini-XML wants
# a literal "#RRGGBB", not a reportlab Color object) -- kept separate from any
# colors.HexColor(...) used for Table styling, which does take Color objects.
_RISK_COLOR_HEX = {
    RiskLevel.BLOCKING: "#B3261E",
    RiskLevel.HIGH: "#B3261E",
    RiskLevel.MEDIUM: "#946200",
    RiskLevel.LOW: "#3A6B35",
    RiskLevel.NONE: "#666666",
}


def _source_description(claim: Claim) -> str:
    if claim.source.page is not None:
        scene = f", {claim.source.scene_heading}" if claim.source.scene_heading else ""
        return f"Script page {claim.source.page}{scene}"
    if claim.source.t_start_ms is not None:
        start_s = claim.source.t_start_ms / 1000
        return f"Video {start_s:.1f}s (channel: {claim.source.channel or 'unknown'})"
    return "Unknown source"


def _evidence_fields_table(evidence: Evidence) -> Table:
    confidence_by_field = {basis.field: basis.confidence.value for basis in evidence.basis}
    rows = [["Field", "Value", "Confidence"]]
    for field, value in evidence.output.items():
        rows.append(
            [field.replace("_", " "), str(value)[:200], confidence_by_field.get(field, "-")]
        )
    table = Table(rows, colWidths=[1.3 * inch, 3.6 * inch, 0.9 * inch], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, GRID_LINE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    return table


def _citations_paragraphs(evidence: Evidence) -> list[Paragraph]:
    seen: set[str] = set()
    paragraphs = []
    for basis in evidence.basis:
        for citation in basis.citations:
            if citation.url in seen:
                continue
            seen.add(citation.url)
            retrieved = citation.retrieved_at.strftime("%Y-%m-%d")
            paragraphs.append(Paragraph(f"&bull; {citation.url} (retrieved {retrieved})", SMALL))
    return paragraphs or [Paragraph("No citations recorded.", SMALL)]


def _history_table(history: list[VerificationEvent]) -> Table:
    rows = [["When", "Actor", "Transition", "Note"]]
    for event in history:
        transition = (
            f"{event.from_status.value if event.from_status else '-'} -> {event.to_status.value}"
        )
        rows.append(
            [
                event.at.strftime("%Y-%m-%d %H:%M UTC"),
                event.actor,
                transition,
                (event.note or "")[:120],
            ]
        )
    table = Table(rows, colWidths=[1.2 * inch, 0.8 * inch, 1.4 * inch, 2.4 * inch], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, GRID_LINE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    return table


def _human_overrides_paragraphs(history: list[VerificationEvent]) -> list[Paragraph]:
    overrides = [event for event in history if event.actor == "human"]
    if not overrides:
        return [Paragraph("No human overrides recorded.", SMALL)]
    paragraphs = []
    for event in overrides:
        signer = event.ref.get("user", "unknown")
        when = event.at.strftime("%Y-%m-%d %H:%M UTC")
        paragraphs.append(Paragraph(f"&bull; {when} by {signer}: {event.note}", SMALL))
    return paragraphs


def _claim_flowable(
    claim: Claim, risk: Risk | None, evidence: Evidence | None, history: list[VerificationEvent]
) -> list[object]:
    risk_level = risk.level if risk else RiskLevel.NONE
    color_hex = _RISK_COLOR_HEX.get(risk_level, "#666666")
    flow: list[object] = [
        Paragraph(
            f'<font color="{color_hex}">[{risk_level.value.upper()}]</font> {claim.entity_text}',
            H1,
        ),
        Paragraph(claim.claim_text, BODY),
        Paragraph(
            f"Category: {claim.category.value} &nbsp;&nbsp; Source: {_source_description(claim)} "
            f"&nbsp;&nbsp; Claim ID: {claim.claim_id}",
            SMALL,
        ),
        Spacer(1, 6),
    ]
    if risk is not None:
        flow.append(
            Paragraph(
                f"Risk score: {risk.score:.2f} &nbsp;&nbsp; Cost band: {risk.cost_band or 'unknown'} "
                f"&nbsp;&nbsp; Rationale: {risk.rationale}",
                BODY,
            )
        )
        flow.append(Spacer(1, 6))

    flow.append(Paragraph("Evidence", H2))
    if evidence is not None:
        flow.append(_evidence_fields_table(evidence))
        flow.append(Spacer(1, 4))
        flow.append(Paragraph("Citations", H2))
        flow.extend(_citations_paragraphs(evidence))
    else:
        flow.append(Paragraph("No evidence recorded yet.", SMALL))

    flow.append(Paragraph("Verification history", H2))
    if history:
        flow.append(_history_table(history))
    else:
        flow.append(Paragraph("No verification events recorded.", SMALL))

    flow.append(Paragraph("Human overrides", H2))
    flow.extend(_human_overrides_paragraphs(history))
    return flow


def generate_eo_pack(session: Session, project_id: str) -> bytes:
    """Builds the full PDF in memory and returns its bytes -- callers upload it to
    GCS themselves (dashboard_api's own signed-URL convention, `main.py`'s
    `_generate_signed_url`), matching how the rest of this codebase separates
    content generation from storage."""
    project = ProjectRepo.require(session, project_id)
    # ClaimRepo.list_by_project's default limit=50 is right for the dashboard's own
    # worklist (PHASE_08.md §8.2) but wrong here -- an export must cover every claim.
    claims = ClaimRepo.list_by_project(session, project_id, limit=100_000)
    risk_by_claim: dict[str, Risk] = {}
    for claim in claims:
        risk = RiskRepo.get(session, claim.claim_id)
        if risk is not None:
            risk_by_claim[claim.claim_id] = risk

    counts_by_risk: dict[str, int] = {}
    for claim in claims:
        level = (
            risk_by_claim[claim.claim_id].level.value
            if claim.claim_id in risk_by_claim
            else "unassessed"
        )
        counts_by_risk[level] = counts_by_risk.get(level, 0) + 1

    summary = Projector().get_project_summary(project_id) or {}
    days_left = days_to_release(project.release_date)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=LETTER, topMargin=0.75 * inch, bottomMargin=0.75 * inch
    )
    story: list[object] = [
        Paragraph("E&amp;O Evidence Pack", TITLE),
        Paragraph(project.title, H1),
        Paragraph(
            f"Project ID: {project.project_id} &nbsp;&nbsp; Generated: "
            f"{datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
            BODY,
        ),
        Paragraph(
            f"Reality Drift: {summary.get('reality_drift', 'n/a')} &nbsp;&nbsp; "
            f"7-day drift: {summary.get('drift_7d', 'n/a')} &nbsp;&nbsp; "
            f"Monitor cadence: {frequency_for(days_left)} &nbsp;&nbsp; "
            f"Days to release: {days_left}",
            BODY,
        ),
        Spacer(1, 12),
        Paragraph("Summary by risk level", H2),
    ]

    summary_rows = [["Risk level", "Claims"]]
    for level in ("blocking", "high", "medium", "low", "none", "unassessed"):
        if level in counts_by_risk:
            summary_rows.append([level, str(counts_by_risk[level])])
    summary_table = Table(summary_rows, colWidths=[2 * inch, 1 * inch])
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

    high_risk_claims = [
        claim
        for claim in claims
        if claim.claim_id in risk_by_claim and risk_by_claim[claim.claim_id].level in _HIGH_RISK
    ]
    high_risk_claims.sort(
        key=lambda c: (
            0 if risk_by_claim[c.claim_id].level == RiskLevel.BLOCKING else 1,
            -risk_by_claim[c.claim_id].score,
        )
    )

    if not high_risk_claims:
        story.append(Paragraph("No high or blocking claims for this project.", BODY))
    for i, claim in enumerate(high_risk_claims):
        evidence = EvidenceRepo.latest_for_claim(session, claim.claim_id)
        history = HistoryRepo.for_claim(session, claim.claim_id)
        story.append(
            KeepTogether(
                _claim_flowable(claim, risk_by_claim.get(claim.claim_id), evidence, history)
            )
        )
        if i < len(high_risk_claims) - 1:
            story.append(PageBreak())

    doc.build(story)
    return buffer.getvalue()

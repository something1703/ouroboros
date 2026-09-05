"""asset segments

Revision ID: 0002_asset_segments
Revises: 0001_initial
Create Date: 2026-09-05 05:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_asset_segments"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PHASE_06.md §6.1/§6.4: FactAgent's ±20s transcript-window context and
    # dashboard_api's GET /assets/{id}/segments both need the transcript segments a
    # cut's video-understanding pass already produces (packages/gemini_client/schemas.py
    # ::CutExtraction.segments) -- previously discarded after claim extraction, kept
    # nowhere. One JSONB array on `assets`, not a separate table: a segment list belongs
    # entirely to its one asset, is always read as a whole document (never queried by
    # individual segment fields), and only cut-kind assets ever populate it.
    op.add_column(
        "assets",
        sa.Column(
            "segments",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("assets", "segments")

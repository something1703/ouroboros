"""asset proxy/poster

Revision ID: 0003_asset_proxy_poster
Revises: 0002_asset_segments
Create Date: 2026-09-05 06:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_asset_proxy_poster"
down_revision: str | None = "0002_asset_segments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PHASE_06.md §6.4: a low-res proxy MP4 + poster frame, generated at ingest
    # alongside claim extraction and stored in the artifacts bucket, so the UI can
    # scrub a cut without ever touching the original (often much larger) source file.
    # Nullable: a script asset never has either; a cut asset only has them once
    # ARTIFACTS_BUCKET is configured and ffmpeg succeeds (see packages/gemini_client
    # /video.py::_generate_proxy_and_poster) -- absence is a real, expected state, not
    # an error.
    op.add_column("assets", sa.Column("proxy_uri", sa.Text(), nullable=True))
    op.add_column("assets", sa.Column("poster_uri", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "poster_uri")
    op.drop_column("assets", "proxy_uri")

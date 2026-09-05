"""claim prior-production memory note

Revision ID: 0004_claim_prior_production_note
Revises: 0003_asset_proxy_poster
Create Date: 2026-09-05 08:45:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_claim_prior_production_note"
down_revision: str | None = "0003_asset_proxy_poster"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PHASE_07.md §7.5: ClaimTriage checks Parallel Memory (studio-scoped) for prior
    # productions' hits on this same entity; when found, the claim view surfaces it as
    # "Seen in previous production." Nullable -- most claims have no Memory hit, which
    # is the normal case, not an error.
    op.add_column("claims", sa.Column("prior_production_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("claims", "prior_production_note")

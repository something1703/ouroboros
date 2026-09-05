"""Phase 8.1/8.6 — email -> role mapping for the dashboard's role-gated access. See
`config/roles.yaml` for the actual mapping and `services/dashboard_api/auth.py` for
where this is enforced.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final, Literal

import yaml

Role = Literal["legal", "editorial", "producer"]

_ROLES_PATH = Path(__file__).parent / "roles.yaml"


def _load_roles() -> dict[str, Role]:
    with _ROLES_PATH.open() as f:
        return yaml.safe_load(f) or {}


ROLES: Final[dict[str, Role]] = _load_roles()

"""Role-gated auth for the dashboard (PHASE_08.md §8.1/§8.6).

Originally speced against Cloud IAP (`x-goog-iap-jwt-assertion`), but this project has
no GCP Organization -- `gcloud iap oauth-brands create` fails outright with "Project
must belong to an organization", and Google's own deprecation notice says the IAP
OAuth Admin APIs are being phased out entirely. Uses Google Identity Services (GIS)
sign-in instead: the frontend gets a Google-signed ID token the same way IAP's
assertion would have been, just carried as a bearer header the frontend sets itself
rather than one a load balancer injects -- this service becomes the sole enforcement
point (no infra-level "unauthenticated blocked before reaching the app" guarantee the
way IAP would have given). The email -> role lookup and per-endpoint role gate are
otherwise identical to what IAP would have needed.

`GOOGLE_OAUTH_CLIENT_ID` must be a real Google OAuth 2.0 Web application Client ID --
creating one requires the Cloud Console UI (no gcloud/Terraform path exists for a
personal, non-org project); until it's set, every request needing auth fails with 401.
"""

from __future__ import annotations

import os
from collections.abc import Callable

import google.auth.transport.requests as gauth_requests
import google.oauth2.id_token as id_token
from fastapi import Depends, Header, HTTPException
from google.auth.exceptions import GoogleAuthError
from pydantic import BaseModel

from config.roles import ROLES, Role


class UserContext(BaseModel):
    email: str
    role: Role


def get_current_user(authorization: str = Header(...)) -> UserContext:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "expected 'Authorization: Bearer <id_token>'")
    token = authorization.removeprefix("Bearer ")

    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    if not client_id:
        raise HTTPException(401, "GOOGLE_OAUTH_CLIENT_ID not configured")

    try:
        claims = id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
            token, gauth_requests.Request(), audience=client_id
        )
    except (ValueError, GoogleAuthError) as exc:
        raise HTTPException(401, f"invalid ID token: {exc}") from exc

    email = claims.get("email")
    if not email or not claims.get("email_verified"):
        raise HTTPException(401, "token has no verified email")

    role = ROLES.get(email)
    if role is None:
        raise HTTPException(403, f"{email} is not a recognized dashboard user")

    return UserContext(email=email, role=role)


def require_role(*allowed: Role) -> Callable[[UserContext], UserContext]:
    """Dependency factory: 403s unless the caller's role is one of `allowed`."""

    def _check(user: UserContext = Depends(get_current_user)) -> UserContext:
        if user.role not in allowed:
            raise HTTPException(403, f"role {user.role!r} cannot access this endpoint")
        return user

    return _check


# The only real callers of `/internal/*` today (Terraform-verified): the
# `claims-extracted-autorun` Pub/Sub push subscription and the `tighten-monitors`
# Cloud Scheduler job both authenticate as `sa_scheduler_email`. `sa-ingest` is kept
# too since it already held `roles/run.invoker` on this service before this change.
_INTERNAL_CALLERS = frozenset(
    {
        "sa-scheduler@ouroboros-507503.iam.gserviceaccount.com",
        "sa-ingest@ouroboros-507503.iam.gserviceaccount.com",
    }
)


def require_internal_caller(authorization: str = Header(...)) -> None:
    """Replaces Cloud Run's own IAM check for `/internal/*` routes. Making the whole
    service `--allow-unauthenticated` (needed so real users' GIS tokens ever reach
    `get_current_user` at all -- Cloud Run's IAM check would otherwise reject them
    before the app sees the request, since a GIS token and a Cloud Run invoker
    identity token are different things entirely) means these routes need their own
    protection instead of relying on the ingress layer. Verifies a real Google-signed
    identity token -- the same kind `sa-scheduler`/`sa-ingest` already mint via
    `google.oauth2.id_token.fetch_id_token(audience=<this service's own URL>)` for
    every one of these calls today -- with `audience=SELF_BASE_URL` (this service's
    own URL, distinct from `GOOGLE_OAUTH_CLIENT_ID`, so a GIS sign-in token can never
    satisfy this check even by accident)."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "expected 'Authorization: Bearer <id_token>'")
    token = authorization.removeprefix("Bearer ")

    self_url = os.environ.get("SELF_BASE_URL")
    if not self_url:
        raise HTTPException(500, "SELF_BASE_URL not configured")

    try:
        claims = id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
            token, gauth_requests.Request(), audience=self_url
        )
    except (ValueError, GoogleAuthError) as exc:
        raise HTTPException(401, f"invalid identity token: {exc}") from exc

    email = claims.get("email")
    if email not in _INTERNAL_CALLERS:
        raise HTTPException(403, f"{email} is not an authorized internal caller")

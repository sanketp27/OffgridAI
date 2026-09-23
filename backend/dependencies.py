"""
dependencies.py — shared FastAPI dependencies.

Implements the Request Auth Flow described in Implementation Plan §5.3:

    Client
      -> Firebase Auth sign-in (client-side)
      -> Firebase issues JWT (RS256, 1h TTL)
      -> Client sends `Authorization: Bearer <token>`
      -> `verify_token()` validates signature/expiry/audience via firebase-admin
      -> `require_role([...])` checks the decoded `role` custom claim
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import Settings, get_settings
from services.bigquery import BigQueryService
from services.embeddings import EmbeddingsService
from services.firestore import FirestoreService
from services.storage import StorageService

_bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------- #
# Firebase Auth verification
# ---------------------------------------------------------------------- #
async def verify_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> dict[str, Any]:
    """Verify the Firebase ID token on the request and return its decoded claims.

    Decoded claims look like::

        {"uid": "abc123", "email": "...", "role": "merchant", "store_id": "store_001"}

    Raises 401 if the token is missing, malformed, or invalid/expired.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization: Bearer <token> header",
        )

    import firebase_admin
    from firebase_admin import auth as firebase_auth

    if not firebase_admin._apps:  # lazy singleton init
        firebase_admin.initialize_app()

    try:
        decoded = firebase_auth.verify_id_token(credentials.credentials)
    except Exception as exc:  # firebase_admin raises several exception subtypes
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
        ) from exc

    return decoded


CurrentUser = Annotated[dict[str, Any], Depends(verify_token)]


def require_role(allowed_roles: list[str]) -> Any:
    """Dependency factory: raises 403 unless `claims["role"]` is in `allowed_roles`.

    Usage:
        @router.post("/insights/generate")
        async def generate(claims: CurrentUser = Depends(require_role(["merchant", "admin"]))):
            ...
    """

    async def _guard(claims: CurrentUser) -> dict[str, Any]:
        role = claims.get("role")
        if role not in allowed_roles and "admin" not in {role}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' is not permitted to perform this operation "
                f"(requires one of {allowed_roles})",
            )
        return claims

    return _guard


def require_store_match(claims: dict[str, Any], store_id: str) -> None:
    """Guard against a merchant/associate reading or writing another store's data.

    `admin` bypasses the scoping check (per §5.2 role table).
    """
    if claims.get("role") == "admin":
        return
    claimed_store = claims.get("store_id")
    if claimed_store is not None and claimed_store != store_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="store_id does not match the authenticated user's store scope",
        )


# ---------------------------------------------------------------------- #
# Service singletons — constructed once per process, reused across requests
# ---------------------------------------------------------------------- #
def get_config() -> Settings:
    return get_settings()


def get_db(request: Request) -> FirestoreService:
    """Return the shared FirestoreService instance stored on `app.state` at startup."""
    return request.app.state.firestore  # type: ignore[no-any-return]


def get_embeddings(request: Request) -> EmbeddingsService:
    return request.app.state.embeddings  # type: ignore[no-any-return]


def get_storage(request: Request) -> StorageService:
    return request.app.state.storage  # type: ignore[no-any-return]


def get_bigquery(request: Request) -> BigQueryService:
    return request.app.state.bigquery  # type: ignore[no-any-return]


def get_orchestrator(request: Request) -> Any:
    return request.app.state.orchestrator

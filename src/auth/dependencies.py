"""FastAPI security dependencies for API-key-based RBAC.

Keys are configured in the environment as a JSON map:

    API_KEYS={"sk-admin-xxx": "admin", "sk-review-yyy": "compliance_officer", "sk-read-zzz": "viewer"}

If API_KEYS is empty (development default), all requests are treated as `admin`
so the server works out-of-the-box without configuration.
"""
import json
import logging
from functools import lru_cache

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from src.auth.roles import Role, has_role
from src.config import settings

logger = logging.getLogger(__name__)

_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


@lru_cache(maxsize=1)
def _key_map() -> dict[str, Role]:
    """Parse the API_KEYS env var once and cache the result."""
    raw = getattr(settings, "api_keys", "{}")
    if not raw or raw == "{}":
        return {}
    try:
        parsed = json.loads(raw)
        return {k: Role(v) for k, v in parsed.items()}
    except Exception as exc:
        logger.warning("Failed to parse API_KEYS: %s — auth disabled", exc)
        return {}


def get_current_role(api_key: str | None = Security(_KEY_HEADER)) -> Role:
    """Resolve the caller's role from the X-API-Key header.

    - No key + no keys configured → admin (dev mode)
    - No key + keys configured    → 401
    - Key not in map              → 403
    """
    key_map = _key_map()

    if not key_map:
        # Development: no keys configured, allow everything
        return Role.admin

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key header required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    role = key_map.get(api_key)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    logger.debug("Authenticated request with role=%s", role.value)
    return role


def require_role(minimum: Role):
    """Return a FastAPI dependency that enforces a minimum role level."""
    def _check(role: Role = Depends(get_current_role)) -> Role:
        if not has_role(role, minimum):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{minimum.value}' or higher required (yours: '{role.value}')",
            )
        return role
    return _check


# Pre-built dependencies for the four permission tiers
RequireViewer = Depends(require_role(Role.viewer))
RequireAnalyst = Depends(require_role(Role.analyst))
RequireComplianceOfficer = Depends(require_role(Role.compliance_officer))
RequireAdmin = Depends(require_role(Role.admin))

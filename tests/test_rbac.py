"""Tests for RBAC: API-key parsing, role hierarchy, and FastAPI dependencies."""
import json
from unittest.mock import patch

import pytest

from src.auth.roles import Role, has_role


# ── Role hierarchy ────────────────────────────────────────────────────────────

def test_has_role_same_level():
    assert has_role(Role.viewer, Role.viewer) is True
    assert has_role(Role.analyst, Role.analyst) is True
    assert has_role(Role.compliance_officer, Role.compliance_officer) is True
    assert has_role(Role.admin, Role.admin) is True


def test_has_role_higher_satisfies_lower():
    assert has_role(Role.admin, Role.viewer) is True
    assert has_role(Role.admin, Role.analyst) is True
    assert has_role(Role.admin, Role.compliance_officer) is True
    assert has_role(Role.compliance_officer, Role.viewer) is True
    assert has_role(Role.compliance_officer, Role.analyst) is True
    assert has_role(Role.analyst, Role.viewer) is True


def test_has_role_lower_does_not_satisfy_higher():
    assert has_role(Role.viewer, Role.analyst) is False
    assert has_role(Role.viewer, Role.compliance_officer) is False
    assert has_role(Role.viewer, Role.admin) is False
    assert has_role(Role.analyst, Role.compliance_officer) is False
    assert has_role(Role.analyst, Role.admin) is False
    assert has_role(Role.compliance_officer, Role.admin) is False


# ── Key map parsing ───────────────────────────────────────────────────────────

def test_key_map_dev_mode_empty_string():
    """Empty api_keys → dev mode → empty map."""
    from src.auth import dependencies

    # Clear lru_cache before patching
    dependencies._key_map.cache_clear()
    with patch.object(dependencies.settings, "api_keys", "{}"):
        km = dependencies._key_map()
    assert km == {}
    dependencies._key_map.cache_clear()


def test_key_map_parses_valid_json():
    from src.auth import dependencies

    keys_json = json.dumps({"sk-admin": "admin", "sk-view": "viewer"})
    dependencies._key_map.cache_clear()
    with patch.object(dependencies.settings, "api_keys", keys_json):
        km = dependencies._key_map()
    assert km == {"sk-admin": Role.admin, "sk-view": Role.viewer}
    dependencies._key_map.cache_clear()


def test_key_map_invalid_json_returns_empty():
    from src.auth import dependencies

    dependencies._key_map.cache_clear()
    with patch.object(dependencies.settings, "api_keys", "not-json"):
        km = dependencies._key_map()
    assert km == {}
    dependencies._key_map.cache_clear()


def test_key_map_unknown_role_raises():
    from src.auth import dependencies

    keys_json = json.dumps({"sk-bad": "superuser"})
    dependencies._key_map.cache_clear()
    with patch.object(dependencies.settings, "api_keys", keys_json):
        km = dependencies._key_map()
    # Invalid role value → caught by except → returns {}
    assert km == {}
    dependencies._key_map.cache_clear()


# ── get_current_role ──────────────────────────────────────────────────────────

def test_get_current_role_dev_mode_no_key():
    """No keys configured + no header → admin (dev mode)."""
    from src.auth import dependencies

    dependencies._key_map.cache_clear()
    with patch.object(dependencies.settings, "api_keys", "{}"):
        role = dependencies.get_current_role(api_key=None)
    assert role == Role.admin
    dependencies._key_map.cache_clear()


def test_get_current_role_valid_key():
    from fastapi import HTTPException
    from src.auth import dependencies

    keys_json = json.dumps({"sk-analyst": "analyst"})
    dependencies._key_map.cache_clear()
    with patch.object(dependencies.settings, "api_keys", keys_json):
        role = dependencies.get_current_role(api_key="sk-analyst")
    assert role == Role.analyst
    dependencies._key_map.cache_clear()


def test_get_current_role_missing_key_raises_401():
    from fastapi import HTTPException
    from src.auth import dependencies

    keys_json = json.dumps({"sk-analyst": "analyst"})
    dependencies._key_map.cache_clear()
    with patch.object(dependencies.settings, "api_keys", keys_json):
        with pytest.raises(HTTPException) as exc_info:
            dependencies.get_current_role(api_key=None)
    assert exc_info.value.status_code == 401
    dependencies._key_map.cache_clear()


def test_get_current_role_invalid_key_raises_403():
    from fastapi import HTTPException
    from src.auth import dependencies

    keys_json = json.dumps({"sk-analyst": "analyst"})
    dependencies._key_map.cache_clear()
    with patch.object(dependencies.settings, "api_keys", keys_json):
        with pytest.raises(HTTPException) as exc_info:
            dependencies.get_current_role(api_key="sk-wrong")
    assert exc_info.value.status_code == 403
    dependencies._key_map.cache_clear()


# ── require_role ──────────────────────────────────────────────────────────────

def test_require_role_passes_when_sufficient():
    from src.auth.dependencies import require_role

    checker = require_role(Role.analyst)
    result = checker(role=Role.admin)
    assert result == Role.admin


def test_require_role_raises_403_when_insufficient():
    from fastapi import HTTPException
    from src.auth.dependencies import require_role

    checker = require_role(Role.compliance_officer)
    with pytest.raises(HTTPException) as exc_info:
        checker(role=Role.analyst)
    assert exc_info.value.status_code == 403

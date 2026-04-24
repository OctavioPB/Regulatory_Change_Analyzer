"""Role definitions and permission matrix."""
import enum


class Role(str, enum.Enum):
    viewer = "viewer"               # read-only access
    analyst = "analyst"             # read + trigger analysis/ingestion
    compliance_officer = "compliance_officer"  # analyst + review + export
    admin = "admin"                 # full access

# Hierarchy: each role includes all permissions of lower roles
_RANK: dict[Role, int] = {
    Role.viewer: 0,
    Role.analyst: 1,
    Role.compliance_officer: 2,
    Role.admin: 3,
}


def has_role(user_role: Role, required: Role) -> bool:
    """Return True if user_role meets or exceeds the required role level."""
    return _RANK[user_role] >= _RANK[required]

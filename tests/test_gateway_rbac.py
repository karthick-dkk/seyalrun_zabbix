"""Gateway RBAC matrix invariants (built-in role fallback, used until the live
role-perms cache populates). Pure function — no app/DB needed."""

from __future__ import annotations

import pytest


@pytest.fixture
def rbac(load_module):
    return load_module("services/api-gateway/app/rbac.py", "gw_rbac")


def test_superadmin_can_do_anything(rbac):
    assert rbac.is_authorized(["superadmin"], "DELETE", "users") is True


def test_audit_is_read_only(rbac):
    assert rbac.is_authorized(["audit"], "GET", "hosts") is True
    assert rbac.is_authorized(["audit"], "DELETE", "hosts") is False


def test_plain_user_has_no_management_access(rbac):
    assert rbac.is_authorized(["user"], "GET", "users") is False
    assert rbac.is_authorized(["user"], "POST", "hosts") is False


def test_auth_segment_always_allowed(rbac):
    # login / MFA / self-service must work for any authenticated caller.
    assert rbac.is_authorized(["user"], "POST", "auth/login") is True


def test_reveal_requires_reveal_capability(rbac):
    # audit can read everything but must NOT be able to reveal a stored secret.
    assert rbac.is_authorized(["audit"], "GET", "credentials/123/reveal") is False
    assert rbac.is_authorized(["admin"], "GET", "credentials/123/reveal") is True


def test_can_reveal_matrix(rbac):
    assert rbac.can_reveal(["admin"]) is True
    assert rbac.can_reveal(["superadmin"]) is True
    assert rbac.can_reveal(["audit"]) is False
    assert rbac.can_reveal(["user"]) is False

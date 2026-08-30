import pytest
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models import SysPermission, SysRole, SysUser
from app.repositories import (
    PermissionRepository,
    RoleRepository,
    UserRepository,
)


@pytest.fixture()
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, autoflush=False)
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture()
def user_repo(db):
    return UserRepository(db)


@pytest.fixture()
def role_repo(db):
    return RoleRepository(db)


@pytest.fixture()
def permission_repo(db):
    return PermissionRepository(db)


def _make_user(username="alice", **overrides):
    data = {"username": username, "password_hash": "hashed-password"}
    data.update(overrides)
    return SysUser(**data)


def _make_role(role_code="OPS_ENGINEER", **overrides):
    data = {"role_code": role_code, "role_name": "运维人员"}
    data.update(overrides)
    return SysRole(**data)


def _make_permission(code, name="权限", **overrides):
    data = {"permission_code": code, "permission_name": name, "permission_type": "API"}
    data.update(overrides)
    return SysPermission(**data)


def test_user_create_and_get_by_username(user_repo):
    user = user_repo.create(_make_user())
    assert user.id is not None
    found = user_repo.get_by_username("alice")
    assert found is not None and found.id == user.id


def test_user_update_and_soft_delete(user_repo):
    user = user_repo.create(_make_user())
    user_repo.update(user, nickname="Alice", status=0)
    assert user.nickname == "Alice" and user.status == 0

    user_repo.soft_delete(user)
    assert user.deleted_at is not None
    assert user_repo.get(user.id) is None
    assert user_repo.get_by_username("alice") is None


def test_user_unique_email_conflict(user_repo):
    user_repo.create(_make_user("alice", email="a@example.com"))
    with pytest.raises(Exception):
        user_repo.create(_make_user("bob", email="a@example.com"))


def test_user_list_pagination_and_filter(user_repo):
    for i in range(5):
        user_repo.create(_make_user(f"user{i}", status=1 if i % 2 == 0 else 0))
    total, items = user_repo.list(page=1, page_size=2, order_by="id")
    assert total == 5 and len(items) == 2
    _, enabled = user_repo.list(status=1)
    assert len(enabled) == 3


def test_user_update_last_login(user_repo):
    user = user_repo.create(_make_user())
    user_repo.update_last_login(user, ip="10.0.0.1")
    assert user.last_login_at is not None
    assert user.last_login_ip == "10.0.0.1"


def test_role_crud_and_soft_unsupported(role_repo):
    role = role_repo.create(_make_role())
    assert role_repo.get_by_code("OPS_ENGINEER").id == role.id
    total, items = role_repo.list(page=1, page_size=10)
    assert total == 1 and items[0].id == role.id


def test_permission_tree_and_get_by_code(permission_repo):
    parent = permission_repo.create(
        _make_permission("server", "服务器管理", permission_type="MENU")
    )
    child = permission_repo.create(
        _make_permission("server:list", "服务器列表", permission_type="API", parent_id=parent.id)
    )
    assert permission_repo.get_by_code("server:list").parent_id == parent.id
    tree = permission_repo.list_tree()
    assert {p.permission_code for p in tree} == {"server", "server:list"}


def test_assign_roles_to_user(user_repo, role_repo):
    user = user_repo.create(_make_user())
    r1 = role_repo.create(_make_role("ADMIN", role_name="系统管理员"))
    r2 = role_repo.create(_make_role("VIEWER", role_name="普通用户"))
    user_repo.set_roles(user.id, [r1.id, r2.id])
    assert set(user_repo.get_role_ids(user.id)) == {r1.id, r2.id}
    assert {r.role_code for r in user_repo.get_roles_by_user(user.id)} == {"ADMIN", "VIEWER"}

    user_repo.set_roles(user.id, [r1.id])
    assert user_repo.get_role_ids(user.id) == [r1.id]


def test_assign_permissions_to_role(role_repo, permission_repo):
    role = role_repo.create(_make_role())
    p1 = permission_repo.create(_make_permission("p1"))
    p2 = permission_repo.create(_make_permission("p2"))
    role_repo.set_permissions(role.id, [p1.id, p2.id])
    assert set(role_repo.get_permission_ids(role.id)) == {p1.id, p2.id}
    assert set(permission_repo.get_codes_by_role(role.id)) == {"p1", "p2"}

    role_repo.set_permissions(role.id, [p1.id])
    assert role_repo.get_permission_ids(role.id) == [p1.id]


def test_count(user_repo):
    user_repo.create(_make_user("a", status=1))
    user_repo.create(_make_user("b", status=1))
    assert user_repo.count() == 2
    assert user_repo.count(status=1) == 2
    assert user_repo.count(status=0) == 0

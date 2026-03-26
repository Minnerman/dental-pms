from __future__ import annotations

from sqlalchemy import MetaData

from app import main as app_main


class DummySession:
    def __init__(self, actor: object):
        self.actor = actor
        self.closed = False
        self.scalar_calls = 0

    def scalar(self, _statement):
        self.scalar_calls += 1
        return self.actor

    def close(self):
        self.closed = True


def test_startup_does_not_call_metadata_create_all(monkeypatch):
    actor = object()
    session = DummySession(actor=actor)
    calls: list[str] = []
    create_all_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_validate_settings(_settings):
        calls.append("validate_settings")

    def fake_session_local():
        calls.append("session_open")
        return session

    def fake_seed_initial_admin(db, *, email: str, password: str):
        assert db is session
        assert email == str(app_main.settings.admin_email)
        assert password == app_main.settings.admin_password.strip()
        calls.append("seed_initial_admin")
        return False

    def fake_ensure_capabilities(db):
        assert db is session
        calls.append("ensure_capabilities")
        return []

    def fake_backfill_user_capabilities(db):
        assert db is session
        calls.append("backfill_user_capabilities")
        return 0

    def fake_ensure_default_templates(db, *, actor):
        assert db is session
        assert actor is session.actor
        calls.append("ensure_default_templates")
        return 0

    def fake_create_all(self, *args, **kwargs):
        create_all_calls.append((args, kwargs))

    monkeypatch.setattr(app_main, "validate_settings", fake_validate_settings)
    monkeypatch.setattr(app_main, "SessionLocal", fake_session_local)
    monkeypatch.setattr(app_main, "seed_initial_admin", fake_seed_initial_admin)
    monkeypatch.setattr(app_main, "ensure_capabilities", fake_ensure_capabilities)
    monkeypatch.setattr(app_main, "backfill_user_capabilities", fake_backfill_user_capabilities)
    monkeypatch.setattr(app_main, "ensure_default_templates", fake_ensure_default_templates)
    monkeypatch.setattr(MetaData, "create_all", fake_create_all)

    app_main.startup()

    assert create_all_calls == []
    assert calls == [
        "validate_settings",
        "session_open",
        "seed_initial_admin",
        "ensure_capabilities",
        "backfill_user_capabilities",
        "ensure_default_templates",
    ]
    assert session.scalar_calls == 1
    assert session.closed is True

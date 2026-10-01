"""Regression tests for trade bookkeeping (no network, no Telegram)."""
import json
import time
from datetime import datetime, timedelta, timezone

import pytest

import bot_engine
import db_manager as db_manager_module

ADMIN = "test-admin-token"
TR_TZ = timezone(timedelta(hours=3))


def _open_trade(trade_id="t-1", coin="BTC", direction="LONG", entry=100.0):
    return {
        "id": trade_id, "coin": coin, "yon": direction, "durum": "AÇIK",
        "giris_fiyati": entry, "miktar_usdt": 50.0, "kaldirac": 3,
        "stop_loss": entry * 0.98, "tarih": "2026-01-01 10:00:00",
    }


@pytest.fixture
def utc_server(monkeypatch):
    """Simulate a host whose local clock is UTC (like Render)."""
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()
    yield
    monkeypatch.delenv("TZ", raising=False)
    time.tzset()


def test_danger_reset_skips_telegram_when_chat_is_unset(client, app_mod, monkeypatch):
    """No hard-coded chat IDs: with no Telegram configuration nothing is sent."""
    import sys
    import types

    calls = []
    scratch_pkg = types.ModuleType("scratch")
    reset_mod = types.ModuleType("scratch.archive_and_reset_data")
    reset_mod.archive_and_reset = lambda: calls.append("archived")
    monkeypatch.setitem(sys.modules, "scratch", scratch_pkg)
    monkeypatch.setitem(sys.modules, "scratch.archive_and_reset_data", reset_mod)

    import requests
    monkeypatch.setattr(requests, "post", lambda *a, **k: calls.append(("post", a, k)))
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN)
    for name in ("TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_DATA_CHAT_ID"):
        monkeypatch.setenv(name, "")

    res = client.post("/api/danger-reset-db", headers={"X-Admin-Token": ADMIN})
    assert res.status_code == 200
    assert calls == ["archived"]


def test_danger_reset_unpins_configured_data_chat(client, app_mod, monkeypatch):
    """The unpin call uses the chat from the environment, not a hard-coded ID."""
    import sys
    import types

    calls = []
    scratch_pkg = types.ModuleType("scratch")
    reset_mod = types.ModuleType("scratch.archive_and_reset_data")
    reset_mod.archive_and_reset = lambda: None
    monkeypatch.setitem(sys.modules, "scratch", scratch_pkg)
    monkeypatch.setitem(sys.modules, "scratch.archive_and_reset_data", reset_mod)

    import requests
    monkeypatch.setattr(requests, "post", lambda url, data=None, timeout=None: calls.append((url, data)))
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN)
    monkeypatch.setenv("TELEGRAM_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_DATA_CHAT_ID", "-100555")

    res = client.post("/api/danger-reset-db", headers={"X-Admin-Token": ADMIN})
    assert res.status_code == 200
    assert calls == [("https://api.telegram.org/bot123:abc/unpinChatMessage", {"chat_id": "-100555"})]

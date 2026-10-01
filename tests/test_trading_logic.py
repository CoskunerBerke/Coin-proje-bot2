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


def test_manual_close_uses_turkey_time_and_correct_pnl(client, app_mod, monkeypatch, workdir, utc_server):
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN)
    (workdir / "bot_trades.json").write_text(json.dumps([_open_trade()]), encoding="utf-8")
    monkeypatch.setattr(app_mod.fetcher, "fetch_ticker", lambda coin: {"last": 110.0})

    res = client.post("/api/close-trade/t-1", headers={"X-Admin-Token": ADMIN})
    assert res.status_code == 200

    trade = json.loads((workdir / "bot_trades.json").read_text(encoding="utf-8"))[0]
    assert trade["durum"] == "KAPALI"
    assert trade["cikis_fiyati"] == 110.0
    closed_at = datetime.strptime(trade["kapanis_tarihi"], "%Y-%m-%d %H:%M:%S")
    now_tr = datetime.now(TR_TZ).replace(tzinfo=None)
    # Every other timestamp in the trade store is Turkey time (UTC+3), even on a UTC host.
    assert abs((now_tr - closed_at).total_seconds()) < 120
    # +10 % move x3 leverage = +30 %, minus 2 x 0.04 % commission
    assert trade["pnl_yuzde"] == pytest.approx(29.92)
    assert trade["pnl_usdt"] == pytest.approx(14.96)


class _FakeExecutor:
    def __init__(self, trades, balance=1000.0):
        self._trades = trades
        self._balance = balance

    def get_trade_history(self):
        return self._trades

    def get_balance(self):
        return self._balance


# The daily loss guard compares closing dates with "today" in Turkey time. The tests freeze that
# clock and build the trades relative to it, so they never straddle midnight.
FROZEN_NOW_TR = datetime(2026, 3, 15, 12, 0, 0, tzinfo=TR_TZ)


class _FrozenDatetime(datetime):
    now_tr = FROZEN_NOW_TR

    @classmethod
    def now(cls, tz=None):
        return cls.now_tr.astimezone(tz) if tz else cls.now_tr.astimezone().replace(tzinfo=None)


@pytest.fixture
def frozen_clock(monkeypatch):
    monkeypatch.setattr(bot_engine, "datetime", _FrozenDatetime)
    monkeypatch.setattr(_FrozenDatetime, "now_tr", FROZEN_NOW_TR)
    return _FrozenDatetime


def _closed(pnl, seconds_ago, now=FROZEN_NOW_TR):
    closed_at = now - timedelta(seconds=seconds_ago)
    return {"coin": "BTC", "durum": "KAPALI", "pnl_usdt": pnl,
            "kapanis_tarihi": closed_at.strftime("%Y-%m-%d %H:%M:%S")}


def test_daily_loss_guard_counts_closed_trades(frozen_clock):
    # Three losing trades closed today (as written by trade_executor: durum=KAPALI, kapanis_tarihi).
    trades = [_closed(-1.0, 3), _closed(-1.0, 2), _closed(-1.0, 1)]
    stats = bot_engine.get_daily_loss_stats(_FakeExecutor(trades))
    assert stats["closed_today"] == 3
    assert stats["consecutive_losses"] == 3
    assert stats["is_banned"] is True


def test_daily_loss_guard_bans_on_daily_loss_percentage(frozen_clock):
    trades = [_closed(-40.0, 1)]  # -4 % of a 1,000 USDT balance, limit is -3 %
    stats = bot_engine.get_daily_loss_stats(_FakeExecutor(trades))
    assert stats["daily_pnl_pct"] == pytest.approx(-4.0)
    assert stats["is_banned"] is True


def test_daily_loss_guard_resets_at_turkey_midnight(frozen_clock, monkeypatch):
    just_after_midnight = datetime(2026, 3, 16, 0, 0, 0, 500000, tzinfo=TR_TZ)
    monkeypatch.setattr(frozen_clock, "now_tr", just_after_midnight)
    trades = [_closed(-40.0, 1, now=just_after_midnight)]  # closed at 23:59:59 the day before
    stats = bot_engine.get_daily_loss_stats(_FakeExecutor(trades))
    assert stats["is_banned"] is False
    assert stats["daily_pnl_pct"] == 0.0


def test_daily_loss_guard_ignores_open_and_old_trades(frozen_clock):
    old = _closed(-50.0, 0)
    old["kapanis_tarihi"] = "2000-01-01 12:00:00"
    trades = [old, _open_trade(), _closed(5.0, 1)]
    stats = bot_engine.get_daily_loss_stats(_FakeExecutor(trades))
    assert stats["closed_today"] == 1  # only the +5 USDT trade closed "today"
    assert stats["is_banned"] is False
    assert stats["consecutive_losses"] == 0


def test_sync_credentials_fall_back_when_env_vars_are_blank(workdir, monkeypatch):
    # .env.example ships "TELEGRAM_DATA_CHAT_ID=" (blank) and documents a fallback to TELEGRAM_CHAT_ID.
    monkeypatch.setenv("TELEGRAM_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_DATA_CHAT_ID", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100123")
    (workdir / "persistent_settings.json").write_text(json.dumps({"tg_token": "saved-token"}), encoding="utf-8")
    token, chat_id = db_manager_module.db_manager._get_sync_credentials()
    assert token == "saved-token"
    assert chat_id == "-100123"


def test_sync_credentials_prefer_env_over_saved_settings(workdir, monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "env-token")
    monkeypatch.setenv("TELEGRAM_DATA_CHAT_ID", "-100999")
    (workdir / "persistent_settings.json").write_text(
        json.dumps({"tg_token": "saved-token", "tg_data_chat_id": "-1"}), encoding="utf-8")
    assert db_manager_module.db_manager._get_sync_credentials() == ("env-token", "-100999")


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

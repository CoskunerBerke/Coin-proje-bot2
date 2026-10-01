"""The Telegram bot token must never reach the public log (GET /api/logs), no network.

Telegram calls carry the token in the URL (https://api.telegram.org/bot<TOKEN>/...), and a
requests connection error repeats that URL in its message. These tests simulate such errors
on every Telegram path that logs or returns the exception text.
"""
import json
import sys
import types

import pytest
import requests

import db_manager as db_manager_module
from log_manager import REDACTED, redact_secrets
from telegram_notifier import TelegramNotifier

ADMIN = "test-admin-token"
ENV_TOKEN = "123456:FAKESECRETTOKEN"
# Same shape as a real token (numeric bot id, colon, 35 url-safe characters).
SAVED_TOKEN = "7012345678:AAFakeTokenForTestsOnly_0123456789a"


def _connection_error(url, *args, **kwargs):
    """Raise what requests raises when api.telegram.org is unreachable (message includes the URL)."""
    path = url.split("api.telegram.org", 1)[1]
    raise requests.exceptions.ConnectionError(
        "HTTPSConnectionPool(host='api.telegram.org', port=443): Max retries exceeded with url: "
        f"{path} (Caused by NewConnectionError('Failed to establish a new connection: "
        "[Errno 111] Connection refused'))"
    )


@pytest.fixture
def env_token(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", ENV_TOKEN)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100123")
    return ENV_TOKEN


@pytest.fixture
def saved_token(workdir, monkeypatch):
    """Token saved from the panel (persistent_settings.json) instead of the environment."""
    for name in ("TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_DATA_CHAT_ID"):
        monkeypatch.setenv(name, "")
    (workdir / "persistent_settings.json").write_text(
        json.dumps({"tg_token": SAVED_TOKEN, "tg_chat_id": "-100123"}), encoding="utf-8")
    return SAVED_TOKEN


def _public_logs(client):
    res = client.get("/api/logs")
    assert res.status_code == 200
    return res.get_data(as_text=True)


@pytest.mark.parametrize("text", [
    f"url: /bot{SAVED_TOKEN}/getMe",
    f"url: /file/bot{SAVED_TOKEN}/documents/file_1.json",
    f"url: /bot{SAVED_TOKEN.replace(':', '%3A')}/sendDocument",
    f"token={SAVED_TOKEN} rejected",
])
def test_redact_secrets_hides_telegram_tokens(text):
    out = redact_secrets(text)
    assert SAVED_TOKEN.split(":")[1] not in out
    assert REDACTED in out


def test_redact_secrets_hides_the_configured_env_token(env_token):
    assert ENV_TOKEN not in redact_secrets(f"Unauthorized for token {ENV_TOKEN}")


def test_redact_secrets_keeps_ordinary_log_lines():
    line = "[2026-10-01 04:51:58] 🚀 BTC LONG açıldı @ 64000.5 (bot motoru 3x)"
    assert redact_secrets(line) == line


@pytest.mark.parametrize("token_fixture", ["env_token", "saved_token"])
def test_cloud_sync_error_does_not_leak_token_via_public_logs(client, monkeypatch, request, token_fixture):
    token = request.getfixturevalue(token_fixture)
    monkeypatch.setattr(db_manager_module.requests, "get", _connection_error)

    db_manager_module.db_manager.sync_from_cloud()

    logs = _public_logs(client)
    assert token not in logs
    assert token.split(":")[1] not in logs
    # The failure is still logged, only without the secret.
    assert f"/bot{REDACTED}/getMe" in json.loads(logs)[-1]


def test_cloud_upload_errors_do_not_leak_token(client, monkeypatch, saved_token, workdir):
    monkeypatch.setattr(db_manager_module.requests, "post", _connection_error)

    db_manager_module.db_manager._upload_worker()
    db_manager_module.db_manager._force_push_empty_to_cloud()

    logs = _public_logs(client)
    assert saved_token not in logs
    assert logs.count(f"/bot{REDACTED}/sendDocument") == 2
    assert saved_token not in (workdir / "bot_logs.txt").read_text(encoding="utf-8")


def test_reset_unpin_error_does_not_leak_token(client, monkeypatch, env_token):
    reset_mod = types.ModuleType("scratch.archive_and_reset_data")
    reset_mod.archive_and_reset = lambda: None
    monkeypatch.setitem(sys.modules, "scratch", types.ModuleType("scratch"))
    monkeypatch.setitem(sys.modules, "scratch.archive_and_reset_data", reset_mod)
    monkeypatch.setattr(requests, "post", _connection_error)
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN)

    res = client.post("/api/danger-reset-db", headers={"X-Admin-Token": ADMIN})
    assert res.status_code == 200
    logs = _public_logs(client)
    assert env_token not in logs
    assert f"/bot{REDACTED}/unpinChatMessage" in logs


def test_logs_endpoint_redacts_lines_written_before_the_fix(client, workdir, monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "")
    (workdir / "bot_logs.txt").write_text(
        f"[2026-09-30 12:00:00] ⚠️ Telegram Cloud Sync Hatası: url: /bot{SAVED_TOKEN}/getMe\n",
        encoding="utf-8")
    logs = _public_logs(client)
    assert SAVED_TOKEN not in logs
    assert f"/bot{REDACTED}/getMe" in logs


def test_notifier_connection_error_message_is_redacted(monkeypatch):
    monkeypatch.setattr(requests, "post", _connection_error)
    ok, message = TelegramNotifier(token=SAVED_TOKEN, chat_id="-100123").send_message("hello")
    assert ok is False
    assert SAVED_TOKEN not in message
    assert f"/bot{REDACTED}/sendMessage" in message

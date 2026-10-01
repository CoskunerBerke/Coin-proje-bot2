"""Auth, CORS and secret-handling checks for the REST API (Flask test client, no network)."""
import json

import pytest

ADMIN = "test-admin-token"

STATE_CHANGING = [
    ("/api/settings", {"bot_active": False}),
    ("/api/close-trade/123", None),
    ("/api/danger-reset-db", None),
    ("/api/telegram-test", {"tg_token": "x", "tg_chat_id": "1"}),
    ("/api/memory-report", None),
]


@pytest.mark.parametrize("path,body", STATE_CHANGING)
def test_state_changing_endpoints_return_503_when_admin_token_unset(client, monkeypatch, path, body):
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    res = client.post(path, json=body, headers={"X-Admin-Token": "anything"})
    assert res.status_code == 503
    assert res.get_json()["success"] is False


@pytest.mark.parametrize("path,body", STATE_CHANGING)
@pytest.mark.parametrize("headers", [{}, {"X-Admin-Token": "wrong"}, {"X-Admin-Token": ""}])
def test_state_changing_endpoints_reject_missing_or_wrong_token(client, monkeypatch, path, body, headers):
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN)
    res = client.post(path, json=body, headers=headers)
    assert res.status_code == 401


def test_settings_post_with_valid_token_is_saved(client, monkeypatch, workdir):
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN)
    res = client.post("/api/settings", json={"tg_chat_id": "42", "tg_token": "secret-bot-token"},
                      headers={"X-Admin-Token": ADMIN})
    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "success"
    # The response never echoes the bot token back.
    assert body["settings"]["tg_token"] == ""
    assert body["settings"]["tg_token_set"] is True
    saved = json.loads((workdir / "persistent_settings.json").read_text(encoding="utf-8"))
    assert saved["tg_chat_id"] == "42"
    assert saved["tg_token"] == "secret-bot-token"


def test_settings_post_without_token_field_keeps_stored_token(client, monkeypatch, workdir):
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN)
    (workdir / "persistent_settings.json").write_text(json.dumps({"tg_token": "stored-token"}), encoding="utf-8")
    res = client.post("/api/settings", json={"tg_token": "", "tg_chat_id": "7", "tg_token_set": True},
                      headers={"X-Admin-Token": ADMIN})
    assert res.status_code == 200
    saved = json.loads((workdir / "persistent_settings.json").read_text(encoding="utf-8"))
    assert saved["tg_token"] == "stored-token"
    assert "tg_token_set" not in saved


def test_settings_post_rejects_non_object_body(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN)
    res = client.post("/api/settings", json=["not", "a", "dict"], headers={"X-Admin-Token": ADMIN})
    assert res.status_code == 400


def test_get_settings_never_exposes_telegram_token(client, monkeypatch, workdir):
    monkeypatch.setenv("TELEGRAM_TOKEN", "123456:env-secret")
    res = client.get("/api/settings")
    assert res.status_code == 200
    body = res.get_json()
    assert body["tg_token"] == ""
    assert body["tg_token_set"] is True
    assert "123456:env-secret" not in res.get_data(as_text=True)


@pytest.mark.parametrize("path", ["/", "/api/settings", "/api/trades", "/api/avoided", "/api/logs",
                                  "/api/balance", "/api/memory", "/api/opportunities", "/api/spot-portfolio"])
def test_read_only_endpoints_work_without_token(client, monkeypatch, path):
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN)
    res = client.get(path)
    assert res.status_code == 200


def test_close_trade_with_valid_token_reaches_handler(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN)
    res = client.post("/api/close-trade/does-not-exist", headers={"X-Admin-Token": ADMIN})
    assert res.status_code == 404  # authorised, but there is no such open trade


def test_cors_allows_only_configured_origin(client):
    allowed = client.get("/", headers={"Origin": "https://panel.example.com"})
    assert allowed.headers.get("Access-Control-Allow-Origin") == "https://panel.example.com"
    other = client.get("/", headers={"Origin": "https://evil.example"})
    assert other.headers.get("Access-Control-Allow-Origin") is None


def test_cors_preflight_allows_admin_header_for_configured_origin(client):
    res = client.options("/api/settings", headers={
        "Origin": "https://panel.example.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "X-Admin-Token, Content-Type",
    })
    assert res.headers.get("Access-Control-Allow-Origin") == "https://panel.example.com"
    assert "x-admin-token" in res.headers.get("Access-Control-Allow-Headers", "").lower()


def test_cors_default_is_same_origin_only(app_mod):
    from flask import Flask

    assert app_mod.parse_cors_origins("") == []
    assert app_mod.parse_cors_origins(" https://a.example/ , https://b.example ") == ["https://a.example", "https://b.example"]
    bare = Flask("bare")
    bare.add_url_rule("/", "index", lambda: "ok")
    assert app_mod.configure_cors(bare, "") == []
    res = bare.test_client().get("/", headers={"Origin": "https://evil.example"})
    assert res.headers.get("Access-Control-Allow-Origin") is None


@pytest.mark.parametrize("coin", ["<img src=x onerror=alert(1)>", "BTC USDT", "A", "X" * 16, "BTC%2F..%2F"])
def test_analysis_rejects_malformed_coin_and_does_not_register_it(client, app_mod, coin):
    before = set(app_mod.SUPPORTED_COINS)
    res = client.get(f"/api/analysis/{coin}/15m")
    assert res.status_code in (400, 404)
    assert set(app_mod.SUPPORTED_COINS) == before


def test_analysis_rejects_unknown_timeframe(client):
    assert client.get("/api/analysis/BTC/7x").status_code == 400


def test_analysis_does_not_register_coin_when_exchange_lookup_fails(client, app_mod, monkeypatch):
    def offline(*args, **kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr(app_mod.fetcher, "fetch_ticker", offline)
    monkeypatch.setattr(app_mod.fetcher, "fetch_coin_info", offline)
    monkeypatch.setattr(app_mod.fetcher, "fetch_ohlcv", offline)
    res = client.get("/api/analysis/NOTACOIN1/15m")
    assert res.status_code == 200
    assert "NOTACOIN1" not in app_mod.SUPPORTED_COINS
    assert "NOTACOIN1" not in client.get("/").get_json()["supported_coins"]

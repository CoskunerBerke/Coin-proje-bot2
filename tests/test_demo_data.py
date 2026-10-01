"""The offline demo (scripts/demo_server.py) seeds clearly fictional data that the real API can serve."""
import importlib.util
import os

import pytest

from conftest import REPO_ROOT

_spec = importlib.util.spec_from_file_location("demo_server", os.path.join(REPO_ROOT, "scripts", "demo_server.py"))
demo_server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(demo_server)


def test_synthetic_candles_are_deterministic_and_limit_only_slices():
    a = demo_server.synthetic_ohlcv("BTC", "15m", 50)
    b = demo_server.synthetic_ohlcv("BTC", "15m", 210)
    assert len(a) == 50 and len(b) == 210
    assert a["close"].iloc[-1] == pytest.approx(b["close"].iloc[-1])


def test_demo_trades_are_marked_as_demo_and_simulated():
    trades = demo_server.build_demo_trades(demo_server.SyntheticFetcher())
    assert trades and all(t["id"].startswith("demo-") for t in trades)
    assert all(t["mod"] == "SİMÜLASYON" for t in trades)
    assert {t["durum"] for t in trades} == {"AÇIK", "KAPALI"}


def test_api_serves_seeded_demo_data(client, workdir, monkeypatch):
    fetcher = demo_server.SyntheticFetcher()
    monkeypatch.setattr("spot_investor.SpotInvestor.scan_spot_opportunities", lambda self: None)
    demo_server.seed_demo_data(str(workdir), fetcher)
    trades = client.get("/api/trades").get_json()
    assert len(trades) == 10
    memory = client.get("/api/memory").get_json()
    assert memory["overall"]["total_trades"] == 8
    assert client.get("/api/balance").get_json()["balance"] == pytest.approx(
        1000 + sum(t["pnl_usdt"] for t in trades if t["durum"] == "KAPALI"))

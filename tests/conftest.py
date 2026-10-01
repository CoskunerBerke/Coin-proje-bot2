"""Pytest setup: imports the Flask app offline, inside a throwaway working directory.

app.py has import-time side effects (data files in the CWD, Telegram sync, the
background engine thread). Here we:
  * switch to a temporary directory before importing, so no repo file is touched,
  * blank the Telegram variables (so a local .env can never trigger network calls),
  * set DISABLE_BOT_ENGINE=1 so the 24/7 engine thread is not started.
"""
import atexit
import os
import shutil
import sys
import tempfile

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

_IMPORT_DIR = tempfile.mkdtemp(prefix="coinbot-tests-")
atexit.register(shutil.rmtree, _IMPORT_DIR, ignore_errors=True)

for _name in ("TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_DATA_CHAT_ID", "ADMIN_TOKEN"):
    os.environ[_name] = ""
os.environ["DISABLE_BOT_ENGINE"] = "1"
# CORS is configured once at import time; the tests check this allow-list.
os.environ["CORS_ORIGINS"] = "https://panel.example.com"

_previous_cwd = os.getcwd()
os.chdir(_IMPORT_DIR)
try:
    import app as app_module  # noqa: E402  (must come after the environment setup)
    import db_manager as db_manager_module  # noqa: E402
finally:
    os.chdir(_previous_cwd)


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """Each test runs in its own empty directory (all data files are CWD-relative)."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def app_mod(workdir, monkeypatch):
    # No Telegram uploads (push_to_cloud starts a 15 s timer thread otherwise).
    monkeypatch.setattr(db_manager_module.db_manager, "push_to_cloud", lambda *a, **k: None)
    monkeypatch.setattr(app_module.executor, "notifier", None)
    return app_module


@pytest.fixture
def client(app_mod):
    app_mod.app.config["TESTING"] = True
    return app_mod.app.test_client()

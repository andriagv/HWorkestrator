"""Tests must never depend on (or leak) the real .env: use dummy profile data."""
import os

os.environ["STUDENT_NAME"] = "Test Student"
os.environ["STUDENT_GROUP"] = "000000-0"
os.environ["TELEGRAM_BOT_TOKEN"] = "1:test"
os.environ["OWNER_TELEGRAM_ID"] = "1"
os.environ["DRIVE_ROOT_FOLDER_ID"] = "root"
os.environ["MOODLE_TOKEN"] = "T"


# ---- shared fixtures (the fakes themselves are in fakes.py)
import pytest  # noqa: E402

from fakes import FakeDrive  # noqa: E402
from hworkestrator import pipeline  # noqa: E402
from hworkestrator.sources import gdrive  # noqa: E402


@pytest.fixture
def drive(monkeypatch, tmp_path):
    drv = FakeDrive()
    monkeypatch.setattr(gdrive, "client", lambda: drv)
    monkeypatch.setattr(pipeline, "new_workdir", lambda: tmp_path)
    return drv


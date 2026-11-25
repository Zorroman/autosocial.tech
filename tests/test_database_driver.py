"""Check database engine construction with the installed driver dependencies."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(("url", "driver"), [
    ("postgresql://demo:p%40ss@localhost/demo", "psycopg2"),
    ("postgresql+psycopg2://demo:p%40ss@localhost/demo", "psycopg2"),
    ("sqlite:///:memory:", "pysqlite"),
])
def test_engine_loads_installed_driver_without_connecting(url, driver):
    # A fresh interpreter avoids reusing another test's already imported engine.
    result = subprocess.run(
        [sys.executable, "-c", "from database import engine; print(engine.dialect.driver)"],
        cwd=ROOT, env={**os.environ, "DATABASE_URL": url},
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == driver

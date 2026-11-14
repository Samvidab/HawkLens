import json
import os
import subprocess
import sys
from pathlib import Path

from tests.fake_nessie import CUSTOMER, OPERATING, RESERVE

BACKEND = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND / "scripts" / "nessie_live_check.py"


def run(tmp_path, *args, key="k-123", balance=50_000.0):
    (tmp_path / "sitecustomize.py").write_text(f"""
import atexit, json, sys
sys.path.insert(0, {str(BACKEND)!r})
from tests.fake_nessie import FakeNessie
f = FakeNessie(balance={balance}).install_plain()
atexit.register(lambda: open({str(tmp_path / 'writes.json')!r}, 'w').write(json.dumps(f.writes)))
""")
    env = {"PATH": os.environ["PATH"], "PYTHONPATH": f"{tmp_path}:{BACKEND}", "NESSIE_CUSTOMER_ID": CUSTOMER,
           "NESSIE_SOURCE_ACCOUNT_ID": OPERATING, "RETROALPHA_ENV_FILE": str(tmp_path / "no.env")}  # not this machine's .env
    if key:
        env["NESSIE_API_KEY"] = key
    r = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env, cwd=BACKEND, timeout=120)
    writes = json.loads((tmp_path / "writes.json").read_text()) if (tmp_path / "writes.json").exists() else None
    return r, writes


def test_dry_run_writes_nothing(tmp_path):
    r, writes = run(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "dry run" in r.stdout and "balance $50,000.00" in r.stdout and "capped at $25,000" in r.stdout
    assert writes == []


def test_missing_key_is_reported(tmp_path):
    r, _ = run(tmp_path, "--yes", key=None)
    assert r.returncode == 2 and "NESSIE_API_KEY" in r.stdout


def test_real_run_creates_and_reads_back(tmp_path):
    r, writes = run(tmp_path, "--yes", "--max-usd", "250000", balance=5_000_000.0)
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout[r.stdout.index("{"):r.stdout.rindex("}") + 1])
    assert out["state"] == "executed" and out["nessie_ids"]["account"] == RESERVE and out["nessie_ids"]["transfer"].startswith("xfer-")
    assert out["total_upfront_usd"] <= 250_000 and "read-back matches the plan: True" in r.stdout
    assert sum(b["amount"] for b in out["read_back"]["reserve_bills"]) == pytest_approx(out["total_upfront_usd"])
    assert out["read_back"]["reserve_balance_usd"] == pytest_approx(out["total_upfront_usd"])
    assert [w[1] for w in writes][0] == f"/accounts/{OPERATING}/transfers" and all("/transfers" in w[1] or "/bills" in w[1] for w in writes)


def pytest_approx(v):
    import pytest
    return pytest.approx(v, abs=0.06)

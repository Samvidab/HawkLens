import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "smoke_test.py"


@pytest.mark.parametrize("engine", ["stub", "live"])
def test_smoke_script_passes_end_to_end(engine):
    """stub: a sample-priced plan is refused at approve. live: the quant engine's plan is financed."""
    r = subprocess.run([sys.executable, str(SCRIPT), "--engine", engine], capture_output=True, text=True, timeout=180,
                       cwd=SCRIPT.parents[1])
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-1000:]
    assert "FAIL" not in r.stdout and "PASS: " in r.stdout

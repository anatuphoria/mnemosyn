import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_lint_finds_nothing():
    ruff = shutil.which("ruff", path=str(ROOT / ".venv" / "bin")) or shutil.which("ruff")
    if ruff is None:
        pytest.skip("ruff is not installed")
    result = subprocess.run([ruff, "check", str(ROOT)], capture_output=True, text=True,
                            check=False)
    assert result.returncode == 0, result.stdout[-3000:]

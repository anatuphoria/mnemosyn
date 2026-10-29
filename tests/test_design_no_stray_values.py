import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "cns_desktop"
STRAY = re.compile(r'#[0-9a-fA-F]{6}\b|setStyleSheet\(|QColor\("|setPointSize\(|setPixelSize\(|mkPen\("#')


def stray_values() -> list[str]:
    found = []
    for path in sorted(ROOT.rglob("*.py")):
        if "design" in path.relative_to(ROOT).parts:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if STRAY.search(line):
                found.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    return found


@pytest.mark.xfail(strict=True, reason="views still write their own values until the last task")
def test_no_view_writes_its_own_colours_or_sizes():
    assert stray_values() == []

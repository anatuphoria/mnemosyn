import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "cns_desktop"
STRAY = re.compile(r'#[0-9a-fA-F]{6}\b|setStyleSheet\(|QColor\("|setPointSize\(|setPixelSize\(|mkPen\("#')
LAYOUT = re.compile(r"\b(setContentsMargins|setSpacing|addSpacing|setFixed\w*|setMinimum\w*"
                    r"|setMaximum\w*|setIndentation|resize)\(([^()]*(?:\([^()]*\)[^()]*)*)\)")
NUMBER = re.compile(r"(?<![\w.\"'])[1-9]\d*(?![\w.])")


def lines():
    for path in sorted(ROOT.rglob("*.py")):
        if "design" in path.relative_to(ROOT).parts:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            yield f"{path.relative_to(ROOT)}:{number}: {line.strip()}", line


def stray_values() -> list[str]:
    return [where for where, line in lines() if STRAY.search(line)]


def stray_sizes() -> list[str]:
    found = []
    for where, line in lines():
        for _name, arguments in LAYOUT.findall(line):
            if NUMBER.search(re.sub(r"\[[^\]]*\]", "", arguments)):
                found.append(where)
    return found


def test_no_view_writes_its_own_colours_or_sizes():
    assert stray_values() == []


def test_no_view_writes_its_own_spacing_or_sizes():
    assert stray_sizes() == []


def test_the_size_scan_sees_literals_and_ignores_tokens():
    samples = ["layout.setSpacing(8)", "layout.setContentsMargins(0, 8, 0, 0)",
               "self.resize(1500, 900)", "box.setFixedWidth(SIZE[\"panel_left\"] - 16)"]
    caught = [s for s in samples for _n, a in LAYOUT.findall(s)
              if NUMBER.search(re.sub(r"\[[^\]]*\]", "", a))]
    assert caught == samples
    clean = ["layout.setSpacing(0)", "layout.setContentsMargins(0, 0, 0, 0)",
             "layout.setSpacing(GAP[\"small\"])", "self.resize(*SIZE[\"window\"])"]
    assert not [s for s in clean for _n, a in LAYOUT.findall(s)
                if NUMBER.search(re.sub(r"\[[^\]]*\]", "", a))]

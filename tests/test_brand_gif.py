import shutil

import pytest

pytest.importorskip("fontTools")

from tools.brand import gif


def test_the_easing_runs_from_start_to_end():
    ease = gif.bezier(.65, 0, .35, 1)
    assert ease(0) == pytest.approx(0) and ease(1) == pytest.approx(1)
    assert 0 < ease(.25) < .5 < ease(.75) < 1


def test_the_seal_starts_empty_and_ends_complete():
    start, end = gif.seal_state(0.0), gif.seal_state(3.0)
    assert start.key_opacity == 0 and all(a == 0 for a in start.letter_opacity)
    assert end.key_drawn == pytest.approx(1) and all(a == pytest.approx(1) for a in end.letter_opacity)
    middle = gif.seal_state(1.4)
    opacity = middle.letter_opacity
    assert opacity[0] > opacity[-1] and 0 < middle.key_drawn <= 1


def test_the_favicon_light_runs_once_along_the_key():
    assert gif.icon_state(0.0).trace_opacity == 0
    early, late = gif.icon_state(0.9), gif.icon_state(1.7)
    assert 0 < early.trace_start < late.trace_start < 1
    assert gif.icon_state(3.0).trace_opacity == pytest.approx(0)


def test_a_frame_is_a_still_svg_with_the_state_drawn_in():
    frame = gif.frame_svg("seal", "dark", 1.4)
    assert "@keyframes" not in frame and "stroke-dasharray" in frame
    assert frame.count('opacity="') >= 9


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")
def test_a_gif_is_written(tmp_path):
    path = gif.write_gif("icon", "dark", tmp_path, fps=10, size=64)
    data = path.read_bytes()
    assert data[:6] == b"GIF89a" and len(data) > 1000


def test_the_favicon_light_is_one_moving_dash():
    import re

    frame = gif.icon_frame(1.2)
    dashes = re.findall(r'stroke-dasharray="([^"]+)" stroke-dashoffset="([^"]+)"', frame)
    light = dashes[-1]
    assert len(light[0].split()) == 2 and float(light[1]) < 0


SCRIPT = "site/javascripts/favicon.js"


def test_the_website_plays_the_favicon_with_a_generated_script(tmp_path):
    from tools import brand

    brand.write_all(tmp_path, "0.4.2")
    text = (tmp_path / SCRIPT).read_text()
    assert str([list(p) for p in brand.KEY_POINTS]).replace(" ", "") in text.replace(" ", "")
    assert "prefers-reduced-motion: reduce" in text and "sessionStorage" in text
    assert (brand.ROOT / SCRIPT).read_text() == brand.favicon_script()
    config = (brand.ROOT / "mkdocs.yml").read_text()
    assert "javascripts/favicon.js" in config


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_script_moves_the_light_exactly_like_the_gif(tmp_path):
    import json
    import subprocess

    from tools import brand

    script = tmp_path / "favicon.js"
    script.write_text(brand.favicon_script())
    times = [0.0, 0.3, 0.5, 0.9, 1.3, 1.7, 2.1, 2.3, 3.0]
    code = (f"const f = require({json.dumps(str(script))});"
            f"console.log(JSON.stringify({json.dumps(times)}.map(t => f.state(t))));")
    found = json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True,
                                      check=True).stdout)
    for t, (opacity, start) in zip(times, found, strict=True):
        want = gif.icon_state(t)
        assert opacity == pytest.approx(want.trace_opacity, abs=1e-6), t
        assert start == pytest.approx(want.trace_start, abs=1e-6), t

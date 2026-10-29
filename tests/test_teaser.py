import re

from tools import teaser
from tools.brand import ROOT

README = ROOT / "README.md"


def test_the_encoders_keep_the_teaser_sharp():
    commands = {name: " ".join(cmd) for name, cmd in teaser.encode_commands(ROOT / "f", ROOT / "o")}
    assert "libsvtav1" in commands["avif"] and "-f avif" in commands["avif"]
    assert "-crf 18" in commands["mp4"] and "yuv420p" in commands["mp4"]
    quality = int(re.search(r"-quality (\d+)", commands["webp"]).group(1))
    assert quality >= 90 and "scale" not in commands["webp"]


def test_the_scenes_add_up_to_a_short_teaser():
    seconds = sum(s for _name, s in teaser.SCENES)
    assert 10 <= seconds <= 20
    assert [name for name, _s in teaser.SCENES] == ["intro", "explore", "slices", "pathway",
                                                     "lab", "end"]


def test_the_readme_opens_with_the_teaser_and_a_fallback():
    text = README.read_text()
    picture = re.search(r'<picture><source srcset="brand/teaser.avif" type="image/avif">'
                        r'<img src="brand/teaser.webp"[^>]*></picture>', text)
    assert picture and text.index("brand/teaser.avif") < text.index("## ")
    assert (ROOT / "brand/teaser.avif").exists() and (ROOT / "brand/teaser.webp").exists()

import struct
import xml.etree.ElementTree as ET

import pytest

pytest.importorskip("fontTools")

from tools import brand

OUTPUTS = ["brand/wordmark-dark.svg", "brand/wordmark-light.svg", "brand/mark.svg",
           "brand/mark-blue.svg", "brand/divider.svg", "brand/divider-gold.svg",
           "brand/badge-release.svg", "brand/badge-licence.svg", "brand/badge-platforms.svg",
           "brand/badge-website.svg", "brand/badge-review.svg",
           "cns_desktop/resources/mark.png", "cns_desktop/resources/wordmark.svg",
           "tools/package/mnemosyn.png", "tools/package/mnemosyn.ico",
           "site/assets/mark.svg", "site/assets/favicon.png", "site/assets/divider.svg"]


@pytest.fixture(scope="module")
def made(tmp_path_factory):
    root = tmp_path_factory.mktemp("brand")
    brand.write_all(root, "0.4.2")
    return root


def test_every_brand_file_is_made(made):
    missing = [name for name in OUTPUTS if not (made / name).exists()]
    assert missing == []


def test_svgs_are_outlines_only(made):
    for name in OUTPUTS:
        if name.endswith(".svg"):
            text = (made / name).read_text()
            ET.fromstring(text)
            assert "<text" not in text and "<path" in text, name


def test_badges_follow_the_version():
    assert brand.badges("0.4.2")["release"] == ("RELEASE", "0.4.2 test")
    assert brand.badges("1.0.0")["release"] == ("RELEASE", "1.0.0")
    assert set(brand.badges("0.4.2")) == {"release", "licence", "platforms", "website", "review"}


def test_a_missing_glyph_is_named():
    with pytest.raises(brand.BrandError, match="not in GFSDidot"):
        brand.text_path(brand.font("GFSDidot-Regular.ttf"), "𖡎", 20)


def test_the_icon_holds_every_windows_size(made):
    data = (made / "tools/package/mnemosyn.ico").read_bytes()
    count = struct.unpack("<HHH", data[:6])[2]
    sizes = {data[6 + 16 * i] or 256 for i in range(count)}
    assert sizes == {16, 32, 48, 256}


README = brand.ROOT / "README.md"


def test_the_readme_opens_with_the_wordmark_for_both_themes():
    text = README.read_text()
    assert text.index("<picture>") < text.index("## ")
    assert 'media="(prefers-color-scheme: dark)" srcset="brand/wordmark-dark.svg"' in text
    assert 'src="brand/wordmark-light.svg"' in text


def test_the_readme_badges_and_links_lead_where_they_should():
    text = README.read_text()
    for name in ("release", "licence", "platforms", "website", "review"):
        assert f'src="brand/badge-{name}.svg"' in text, name
    site = "https://mnemo.saeed.cool/"
    for page in ("download/", "guide/", "atlas/structures/", "review/", "decisions/"):
        assert f"{site}{page}" in text, page
    assert "releases/tag/v" in text or "/releases" in text


def test_the_readme_keeps_what_a_visitor_needs():
    text = README.read_text()
    assert "pip install -e" in text and "python -m tools.build_atlas" in text
    assert "not for diagnosis or treatment" in text
    assert "GNU General Public License v3.0 or later" in text
    assert "| Data | Source | Licence |" in text and "atlas/sources/" in text
    assert "OFL" in text or "Open Font Licence" in text


def test_every_brand_file_the_readme_uses_exists():
    import re

    for path in re.findall(r'(?:src|srcset)="(brand/[^"]+)"', README.read_text()):
        assert (brand.ROOT / path).exists(), path

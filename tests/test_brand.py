import struct
import xml.etree.ElementTree as ET

import pytest

pytest.importorskip("fontTools")

from tools import brand

LOCKUPS = ("line", "latin", "seal", "signature")
OUTPUTS = [*(f"brand/logo-{kind}-{theme}.svg" for kind in LOCKUPS for theme in ("dark", "light")),
           "brand/key.svg", "brand/mark.svg", "brand/mark-blue.svg",
           "brand/badge-release.svg", "brand/badge-licence.svg", "brand/badge-platforms.svg",
           "brand/badge-website.svg", "brand/badge-review.svg",
           "cns_desktop/resources/mark.png", "cns_desktop/resources/logo.svg",
           "tools/package/mnemosyn.png", "tools/package/mnemosyn.ico",
           "site/assets/mark.svg", "site/assets/favicon.png", "site/assets/logo-seal-dark.svg",
           "site/assets/logo-seal-light.svg"]
GONE = ["brand/wordmark-dark.svg", "brand/wordmark-light.svg", "brand/divider.svg",
        "brand/divider-gold.svg", "cns_desktop/resources/wordmark.svg",
        "site/assets/divider.svg"]


@pytest.fixture(scope="module")
def made(tmp_path_factory):
    root = tmp_path_factory.mktemp("brand")
    brand.write_all(root, "0.4.2")
    return root


def test_every_brand_file_is_made(made):
    missing = [name for name in OUTPUTS if not (made / name).exists()]
    assert missing == []


def test_the_old_wordmark_and_dividers_are_gone(made):
    assert [name for name in GONE if (made / name).exists()] == []
    assert [name for name in GONE if (brand.ROOT / name).exists()] == []


def test_every_lockup_draws_the_key_in_blue_and_the_name_in_ink(made):
    from cns_desktop.design.tokens import KEY

    for kind in LOCKUPS:
        for theme, ink in (("dark", brand.LIGHT), ("light", brand.INK)):
            text = (made / f"brand/logo-{kind}-{theme}.svg").read_text()
            assert f'stroke="{brand.BLUE}"' in text and f'fill="{ink}"' in text, (kind, theme)
            assert text.count("L") >= len(KEY) - 1


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


def test_the_readme_opens_with_the_seal_for_both_themes():
    text = README.read_text()
    assert text.index("<picture>") < text.index("## ")
    assert 'media="(prefers-color-scheme: dark)" srcset="brand/logo-seal-dark.svg"' in text
    assert 'src="brand/logo-seal-light.svg"' in text
    assert "divider" not in text


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


def test_the_committed_brand_files_match_the_project_version(tmp_path):
    for path in brand.write_all(tmp_path, brand.project_version()):
        if path.suffix == ".svg":
            name = path.relative_to(tmp_path)
            assert (brand.ROOT / name).read_text() == path.read_text(), (
                f"{name} is out of date; run python -m tools.brand")


def test_the_icon_is_the_blue_key_on_the_dark_square(made):
    icon = (made / "brand/mark.svg").read_text()
    assert f'fill="{brand.INK}"' in icon and f'stroke="{brand.BLUE}"' in icon
    assert 'rx="52"' in icon and "<text" not in icon
    header = (made / "site/assets/mark.svg").read_text()
    assert f'stroke="{brand.BLUE}"' in header and "<rect" not in header


def test_the_icon_images_show_the_key(made):
    from PySide6.QtGui import QImage

    image = QImage(str(made / "cns_desktop/resources/mark.png"))
    centre_row = [image.pixelColor(x, 128) for x in range(256)]
    blue = [c for c in centre_row if c.blue() > 150 and c.red() < 120]
    assert len(blue) > 20


def test_the_bamum_font_is_no_longer_needed():
    assert not (brand.FONTS / "NotoSansBamum.ttf").exists()
    assert not (brand.FONTS / "OFL-NotoSansBamum.txt").exists()
    assert "Bamum" not in README.read_text()


def test_the_readme_keeps_the_layout_and_the_site_preview_setup():
    text = README.read_text()
    assert "cns_desktop/" in text and "tools/brand/" in text and "brand/" in text
    assert 'pip install "mkdocs>=1.6,<2" "mkdocs-material>=9.5,<10"' in text


def test_the_light_website_header_stays_dark_for_the_mark():
    css = (brand.ROOT / "site/stylesheets/extra.css").read_text()
    assert '[data-md-color-scheme="default"] .md-header' in css

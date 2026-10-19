import sys

from cns_desktop import app
import cns_desktop.views.about_dialog as about


def test_the_atlas_is_found_next_to_a_frozen_app(tmp_path, monkeypatch):
    bundle = tmp_path / "Mnemosyn ünï folder"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    assert app.default_atlas() == bundle / "atlases" / "cns"


def test_from_source_the_atlas_is_the_repository_build(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert app.default_atlas() == app.DEFAULT_ATLAS


def test_a_packaged_app_reads_its_version_file(tmp_path, monkeypatch):
    (tmp_path / "VERSION").write_text("0.1.0\n")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    def missing(name):
        raise about.PackageNotFoundError(name)

    monkeypatch.setattr(about, "version", missing)
    assert about.app_version() == "0.1.0"


def test_versions_below_one_are_test_versions():
    assert about.is_test_version("0.1.0") and about.is_test_version("0.9.3")
    assert not about.is_test_version("1.0.0") and not about.is_test_version("development")


def test_the_about_box_names_a_test_version(monkeypatch, tmp_path):
    from atlas_package import tetra, tiny_structures, write_package
    from cns_atlas import Atlas

    root = write_package(tmp_path / "pkg", tiny_structures(), meshes={101: tetra()})
    monkeypatch.setattr(about, "app_version", lambda: "0.1.0")
    assert "Version 0.1.0, test version" in about.about_text(Atlas.open(root))


def test_the_app_wears_the_mark():
    from PySide6.QtWidgets import QApplication

    qapp = QApplication.instance() or QApplication([])
    app.apply_identity(qapp)
    assert not qapp.windowIcon().isNull()
    assert (app.RESOURCES / "mark.png").exists() and (app.RESOURCES / "wordmark.svg").exists()


def test_the_about_box_opens_with_the_wordmark(tmp_path):
    from PySide6.QtSvgWidgets import QSvgWidget
    from PySide6.QtWidgets import QApplication

    from atlas_package import tetra, tiny_structures, write_package
    from cns_atlas import Atlas

    QApplication.instance() or QApplication([])
    root = write_package(tmp_path / "pkg", tiny_structures(), meshes={101: tetra()})
    dialog = about.AboutDialog(Atlas.open(root))
    marks = dialog.findChildren(QSvgWidget)
    assert len(marks) == 1 and marks[0].renderer().isValid()

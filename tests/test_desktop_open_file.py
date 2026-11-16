from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QFileOpenEvent

from cns_desktop.app import open_file, watch_file_opens
from cns_lab.experiment import Block, Experiment
from cns_lab.files import write
from pathway_helpers import open_window

pytestmark = pytest.mark.usefixtures("themed")
PACKAGE = Path(__file__).resolve().parent.parent / "tools" / "package"


@pytest.fixture
def window(qapp, toy_lab_atlas, tmp_path):
    w = open_window(qapp, toy_lab_atlas, tmp_path)
    yield w
    w.lab.document.undo.setClean()
    qapp.processEvents()
    w.close()


def saved(window, tmp_path) -> Path:
    model = window.lab.document.model
    path = tmp_path / "an experiment.mnemolab"
    write(path, Experiment(model.key, model.version, 2880.0, model.start_clock,
                           (Block("remove_b", 60.0),)))
    return path


def test_a_lab_file_opens_in_the_lab(window, tmp_path):
    assert open_file(window, saved(window, tmp_path))
    document = window.lab.document
    assert window.workspaces.current == "Lab" and document.experiment.length == 2880.0
    assert [b.experiment for b in document.experiment.blocks] == ["remove_b"]


def test_other_files_are_left_alone(window, tmp_path):
    other = tmp_path / "notes.txt"
    other.write_text("hello")
    assert not open_file(window, other)
    assert window.workspaces.current == "Explore"


def test_a_file_opened_by_the_system_reaches_the_lab(window, tmp_path, qapp):
    opener = watch_file_opens(qapp, window)
    QCoreApplication.sendEvent(qapp, QFileOpenEvent(str(saved(window, tmp_path))))
    assert window.workspaces.current == "Lab"
    qapp.removeEventFilter(opener)


def test_a_file_opened_during_a_quiz_ends_the_quiz_first(window, tmp_path):
    from cns_study.session import QuizChoice

    window.start_quiz(QuizChoice("name-typed", "structures", None, True))
    assert window.quiz_active
    assert open_file(window, saved(window, tmp_path))
    assert not window.quiz_active and window.workspaces.current == "Lab"


def test_every_package_registers_the_lab_file_type():
    desktop = (PACKAGE / "mnemosyn.desktop").read_text()
    assert "Exec=Mnemosyn %f" in desktop
    assert "MimeType=application/x-mnemolab;application/x-mnemolesson;" in desktop
    installer = (PACKAGE / "mnemosyn.iss").read_text()
    assert "ChangesAssociations=yes" in installer and r"Software\Classes\.mnemolab" in installer
    assert '""{app}\\Mnemosyn.exe"" ""%1""' in installer and "HKLM" not in installer
    spec = (PACKAGE / "mnemosyn.spec").read_text()
    assert "CFBundleDocumentTypes" in spec and '"public.filename-extension": ["mnemolab"]' in spec
    assert r"Software\Classes\.mnemolesson" in installer
    assert '"public.filename-extension": ["mnemolesson"]' in spec

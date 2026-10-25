import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from atlas_package import (TOY_CELLS_TEXT, TOY_REFERENCE, tetra, tiny_structures, toy_cell_view,
                           write_package)
from cns_atlas import Atlas
from cns_desktop.state import AppState
from cns_desktop.views.cell_panel import CellPanel


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def cells_package(root, **extra):
    return write_package(root, tiny_structures(), meshes={101: tetra(), 102: tetra(30.0)},
                         cells=[toy_cell_view()], entries={"en": {"cells-toy": TOY_CELLS_TEXT}},
                         references=TOY_REFERENCE, **extra)


@pytest.fixture
def cells_panel(qapp, tmp_path):
    panel = CellPanel(AppState(Atlas.open(cells_package(tmp_path / "a"))))
    panel.resize(900, 700)
    panel.show_view("toy")
    panel.show()
    qapp.processEvents()
    yield panel
    panel.close()


def view_point(panel, item) -> QPoint:
    return panel.view.mapFromScene(item.mapToScene(item.data(1)))


def click_item(panel, key: str) -> None:
    QTest.mouseClick(panel.view.viewport(), Qt.MouseButton.LeftButton, pos=view_point(
        panel, panel.items(key)[0]))
    QApplication.processEvents()


def click_empty(panel) -> None:
    QTest.mouseClick(panel.view.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(3, 3))
    QApplication.processEvents()


def visible_fraction(panel) -> float:
    shown = panel.view.mapToScene(panel.view.viewport().rect()).boundingRect()
    content = panel.content_rect()
    both = shown.intersected(content)
    return both.width() * both.height() / (content.width() * content.height())


def test_every_item_kind_is_drawn(cells_panel):
    assert len(cells_panel.items("cell:big")) == 3 and len(cells_panel.items("cell:small")) == 4
    assert cells_panel.items("cell:stop") == []
    assert cells_panel.items("layer:upper") and cells_panel.items("box:input")
    assert cells_panel.items("label")


def test_full_level_draws_its_extra_cells(cells_panel):
    cells_panel.set_level("full")
    assert len(cells_panel.items("cell:stop")) == 2


def test_clicking_a_cell_shows_its_text_and_fades_others(cells_panel):
    click_item(cells_panel, "cell:big")
    text = cells_panel.text.toPlainText()
    assert cells_panel.selected == "cell:big"
    assert "Big cell" in text and "NeuroMorpho" in text and "[1]" in text
    assert "Upper layer" in text and "rat" in text
    assert all(item.opacity() < 0.5 for item in cells_panel.items("cell:small"))
    assert all(item.opacity() == 1 for item in cells_panel.items("cell:big"))


def test_clicking_empty_space_clears(cells_panel):
    click_item(cells_panel, "cell:big")
    click_empty(cells_panel)
    assert cells_panel.selected is None
    assert all(item.opacity() == 1 for item in cells_panel.items("cell:small"))
    assert "Click a cell" in cells_panel.text.toPlainText()


def test_box_and_layer_clicks_show_their_text(cells_panel):
    click_item(cells_panel, "box:input")
    assert "The input arrives here." in cells_panel.text.toPlainText()
    click_item(cells_panel, "layer:upper")
    assert "The upper layer holds big cells." in cells_panel.text.toPlainText()


def test_text_says_it_is_a_draft(cells_panel):
    click_item(cells_panel, "cell:small")
    assert "draft" in cells_panel.text.toPlainText().lower()


def test_fit_after_zoom_shows_the_whole_drawing(cells_panel):
    cells_panel.zoom_by(4.0)
    assert visible_fraction(cells_panel) < 0.5
    cells_panel.fit()
    assert visible_fraction(cells_panel) > 0.95


def test_wheel_zooms_in(cells_panel):
    before = cells_panel.view.transform().m11()
    cells_panel.view.zoom_at(QPointF(450, 300), 120)
    assert cells_panel.view.transform().m11() > before


def test_only_the_level_s_flows_are_drawn(cells_panel):
    assert cells_panel.items("flow:f2") and not cells_panel.items("flow:f3")
    cells_panel.set_level("full")
    assert cells_panel.items("flow:f3")


def run_through(panel) -> list[str]:
    seen = []
    panel.play()
    for _ in range(1000):
        panel.advance(0.1)
        if not panel.playing:
            break
        if not seen or seen[-1] != panel.caption.text():
            seen.append(panel.caption.text())
    return seen


def test_play_walks_the_basic_captions_in_order(cells_panel):
    assert run_through(cells_panel) == ["Basic one", "Basic two"]
    assert not cells_panel.playing and cells_panel.caption.text().startswith("Done")
    assert cells_panel.index == 0


def test_full_level_has_its_own_steps(cells_panel):
    cells_panel.set_level("full")
    assert run_through(cells_panel) == ["Full one", "Full two", "Full three"]


def test_speed_halves_the_step_time(cells_panel):
    cells_panel.set_speed(2.0)
    cells_panel.play()
    cells_panel.advance(1.25)
    assert cells_panel.index == 1


def test_lit_cells_light_at_the_end_of_a_step(cells_panel):
    cells_panel.play()
    cells_panel.advance(0.5)
    assert all(item.opacity() < 0.5 for item in cells_panel.items("cell:small"))
    cells_panel.advance(1.2)
    assert all(item.opacity() == 1 for item in cells_panel.items("cell:small"))
    assert all(item.opacity() < 0.5 for item in cells_panel.items("cell:big"))


def test_a_pulse_travels_the_step_s_arrow(cells_panel):
    cells_panel.play()
    cells_panel.advance(0.4)
    first = cells_panel.pulses()[0].pos()
    cells_panel.advance(0.4)
    assert cells_panel.pulses()[0].pos() != first and cells_panel.pulses()[0].isVisible()


def test_pause_keeps_the_place(cells_panel):
    cells_panel.play()
    cells_panel.advance(1.0)
    cells_panel.pause()
    before = cells_panel.progress
    cells_panel.advance(1.0)
    assert cells_panel.progress == before and not cells_panel.playing


def test_next_and_back_move_one_step_and_stop(cells_panel):
    cells_panel.set_level("full")
    cells_panel.play()
    cells_panel.next()
    assert cells_panel.index == 1 and not cells_panel.playing
    assert cells_panel.caption.text() == "Full two"
    cells_panel.back()
    cells_panel.back()
    assert cells_panel.index == 0 and cells_panel.caption.text() == "Full one"


def test_restart_clears_the_run(cells_panel):
    cells_panel.play()
    cells_panel.advance(3.0)
    cells_panel.restart()
    assert cells_panel.index == 0 and not cells_panel.playing
    assert all(item.opacity() == 1 for item in cells_panel.items("cell:big"))


def test_a_click_stops_playback(cells_panel):
    cells_panel.play()
    click_item(cells_panel, "cell:big")
    assert not cells_panel.playing and cells_panel.selected == "cell:big"


def test_switching_to_basic_drops_a_full_only_selection(cells_panel):
    cells_panel.set_level("full")
    click_item(cells_panel, "cell:stop")
    cells_panel.play()
    cells_panel.set_level("basic")
    assert cells_panel.selected is None and not cells_panel.playing


def test_switching_level_keeps_a_shared_selection(cells_panel):
    click_item(cells_panel, "cell:big")
    cells_panel.set_level("full")
    assert cells_panel.selected == "cell:big"


def test_level_buttons_switch_the_level(cells_panel):
    cells_panel.level_buttons["full"].click()
    assert cells_panel.level == "full" and cells_panel.items("cell:stop")


def test_a_layer_is_clicked_only_on_its_band(cells_panel):
    upper = cells_panel.items("layer:upper")[0]
    assert upper.shape().contains(QPointF(450, 169))
    assert not upper.shape().contains(QPointF(500, 199))


def test_every_cell_can_be_clicked_near_its_soma(cells_panel):
    cells_panel.set_level("full")
    for key in ("cell:big", "cell:small", "cell:stop"):
        for item in cells_panel.items(key):
            soma = item.mapToScene(QPointF(0, 0))
            for dx, dy in ((4, 0), (0, 4), (-4, 0), (0, -4)):
                assert item.shape().contains(item.mapFromScene(soma + QPointF(dx, dy))), key

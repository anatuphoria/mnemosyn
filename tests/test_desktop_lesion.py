import numpy as np
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from atlas_fixtures import place_territories, sha256_file, write_extended_source_tree
from cns_atlas import Atlas
from cns_atlas.lesions import Lesion, structure_lesion, territory_lesion
from cns_atlas import DISCLAIMER
from cns_desktop.lesion.cases_panel import NO_CASES
from cns_desktop.lesion.place_panel import CORD_MISSING, TERRITORIES_MISSING
from cns_desktop.lesion.results_panel import EMPTY_LESION
from cns_desktop.main_window import MainWindow
from tools.build_atlas.build import build


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def open_window(qapp, atlas, tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    w = MainWindow(Atlas.open(atlas), progress_path=tmp_path / "progress.sqlite",
                   settings=settings)
    w.resize(1400, 900)
    w.show()
    qapp.processEvents()
    return w


@pytest.fixture
def window(qapp, toy_pathway_atlas, tmp_path):
    w = open_window(qapp, toy_pathway_atlas, tmp_path)
    yield w
    qapp.processEvents()
    w.close()


def label_lesion(atlas, structure_id):
    volume = atlas.volumes[0]
    return Lesion.empty(atlas).with_mask(volume.name, volume.data == structure_id)


def test_the_lesion_workspace_is_listed_and_has_its_panels(window, qapp):
    lesion = window.lesion
    assert lesion is not None and window.workspaces.button("Lesion").isVisibleTo(window)
    window.workspaces.switch("Lesion")
    qapp.processEvents()
    assert lesion.tools_group.keys() == ["place", "cases"]
    assert lesion.results_group.keys() == ["deficits", "hit"]
    assert lesion.tools_group.isVisible() and lesion.results_group.isVisible()
    assert window.slices_group.isVisible() and not window.structures_group.isVisible()
    window.workspaces.switch("Explore")
    qapp.processEvents()
    assert not lesion.tools_group.isVisible() and not lesion.results_group.isVisible()
    assert window.structures_group.isVisible()


def test_entering_and_leaving_restores_the_window(window, qapp):
    state = window.state
    state.select(101)
    state.set_hidden([102], True)
    window.workspaces.switch("Lesion")
    state.select(111)
    state.set_hidden([102], False)
    window.workspaces.switch("Explore")
    qapp.processEvents()
    assert state.selected == 101 and state.is_hidden(102)


def test_the_document_keeps_an_undo_step_per_lesion_and_a_fresh_report(window):
    doc = window.lesion.document
    atlas = window.state.atlas
    assert doc.lesion.is_empty and doc.report.deficits == ()
    doc.set_lesion(label_lesion(atlas, 101), "Brush")
    assert [d.step for d in doc.report.deficits if d.route == "loop"] == [0]
    assert doc.undo.count() == 1
    doc.clear()
    assert doc.lesion.is_empty and doc.undo.count() == 2
    doc.undo.undo()
    assert not doc.lesion.is_empty and np.any(doc.lesion.masks["brain"])
    doc.undo.undo()
    assert doc.lesion.is_empty


def test_an_atlas_without_pathways_has_no_lesion_workspace(qapp, toy_atlas, tmp_path):
    w = open_window(qapp, toy_atlas, tmp_path)
    try:
        assert w.lesion is None and not w.workspaces.button("Lesion").isVisibleTo(w)
        w.workspaces.switch("Lesion")
        assert w.workspaces.current == "Explore"
    finally:
        w.close()


def built(root, **options):
    cache = root / "cache"
    if options.pop("territories", False):
        options["territories"] = sha256_file(place_territories(root, cache))
    src = write_extended_source_tree(root, tracts=True, pathways=True, **options)
    return build(src, root / "out" / "toy", cache=cache, log=lambda *_: None, local=True)


@pytest.fixture(scope="module")
def territory_atlas(tmp_path_factory):
    return built(tmp_path_factory.mktemp("lesionterritories"), territories=True)


@pytest.fixture(scope="module")
def spine_atlas(tmp_path_factory):
    return built(tmp_path_factory.mktemp("lesionspine"), spine=True)


def entered(window, qapp):
    window.workspaces.switch("Lesion")
    qapp.processEvents()
    return window.lesion


def test_a_territory_click_sets_the_lesion_on_the_chosen_side(qapp, territory_atlas, tmp_path):
    w = open_window(qapp, territory_atlas, tmp_path)
    try:
        lesion = entered(w, qapp)
        place = lesion.place
        assert place.territory_tree.topLevelItemCount() == 1
        group = place.territory_tree.topLevelItem(0)
        names = [group.child(i).text(0) for i in range(group.childCount())]
        assert names == ["Toy artery A territory", "Toy artery B territory"]
        place.set_side("right")
        place.choose_territory(260)
        atlas = w.state.atlas
        right = next(s.id for s in atlas.structures if s.name == "Toy artery A territory (right)")
        expected = territory_lesion(atlas, right).masks[atlas.volumes[0].name]
        assert (lesion.document.lesion.masks[atlas.volumes[0].name] == expected).all()
        assert lesion.document.undo.count() == 1
    finally:
        w.close()


def test_brushing_adds_spheres_and_ctrl_erases(window, qapp):
    lesion = entered(window, qapp)
    place, doc = lesion.place, lesion.document
    place.set_tool("brush")
    place.set_radius(8)
    name = window.state.atlas.volumes[0].name
    window.slices.brush("press", (20, 24, 18), name, False)
    window.slices.brush("move", (22, 24, 18), name, False)
    assert doc.lesion.is_empty and place.stroke is not None
    window.slices.brush("release", (22, 24, 18), name, False)
    painted = int(doc.lesion.masks[name].sum())
    assert painted > 0 and doc.undo.count() == 1 and place.stroke is None
    window.slices.brush("press", (20, 24, 18), name, True)
    window.slices.brush("release", (20, 24, 18), name, True)
    assert 0 <= int(doc.lesion.masks[name].sum()) < painted and doc.undo.count() == 2


def test_a_slice_pixel_brushes_the_voxel_under_it(window, qapp):
    entered(window, qapp).place.set_tool("brush")
    seen = []
    brush = window.slices.brush
    window.slices.brush = lambda *args: seen.append(args)
    window.slices.brush_at_pixel("press", 10, 12, False)
    window.slices.brush = brush
    from cns_desktop import slices
    labels = window.slices.labels
    expected = slices.voxel_for_pixel(labels.shape, window.state.slice_axis, window.slices.index,
                                      10, 12)
    assert seen == [("press", expected, labels.name, False)]


def test_leaving_mid_stroke_drops_the_stroke(window, qapp):
    lesion = entered(window, qapp)
    lesion.place.set_tool("brush")
    name = window.state.atlas.volumes[0].name
    window.slices.brush("press", (20, 24, 18), name, False)
    window.workspaces.switch("Explore")
    assert lesion.place.stroke is None and window.slices.brush is None
    assert lesion.document.lesion.is_empty
    entered(window, qapp)
    assert lesion.place.stroke is None and window.slices.brush is not None


def test_undo_redo_and_clear_buttons(window, qapp):
    lesion = entered(window, qapp)
    doc = lesion.document
    doc.set_lesion(structure_lesion(window.state.atlas, 101), "Alpha")
    lesion.place.clear_button.click()
    assert doc.lesion.is_empty
    lesion.place.undo_button.click()
    assert not doc.lesion.is_empty
    lesion.place.redo_button.click()
    assert doc.lesion.is_empty


def test_a_public_build_says_what_it_lacks(window, qapp):
    place = entered(window, qapp).place
    assert place.territory_tree.isHidden() and place.tool_control.keys() == ["brush", "structure"]
    assert place.territory_note.text() == TERRITORIES_MISSING and not place.territory_note.isHidden()
    assert place.cord_note.text() == CORD_MISSING and not place.cord_note.isHidden()


def test_the_structure_tool_takes_the_selected_structure(window, qapp):
    lesion = entered(window, qapp)
    lesion.place.set_tool("structure")
    window.state.select(112)
    hit = lesion.document.report.hits
    assert hit[112] == pytest.approx(1.0) and lesion.document.undo.count() == 1


def test_the_lesion_shows_on_the_slice_and_in_3d(window, qapp):
    lesion = entered(window, qapp)
    atlas = window.state.atlas
    window.state.set_slice("axial", 20.0)
    qapp.processEvents()
    before = window.slices.image.copy()
    lesion.document.set_lesion(structure_lesion(atlas, 101), "Alpha")
    qapp.processEvents()
    after = window.slices.image
    assert after.shape == before.shape and (after != before).any()
    assert window.view.lesion_actor is not None and window.view.lesion_actor.GetVisibility()
    lesion.document.clear()
    qapp.processEvents()
    assert not window.view.lesion_actor.GetVisibility()
    assert (window.slices.image == before).all()


def test_brushing_on_the_spine_slice_writes_the_spine_mask(qapp, spine_atlas, tmp_path):
    w = open_window(qapp, spine_atlas, tmp_path)
    try:
        lesion = entered(w, qapp)
        assert lesion.place.cord_note.isHidden()
        lesion.place.set_tool("brush")
        spine = next(v for v in w.state.atlas.volumes if v.name == "spine")
        centre = tuple(int(n) // 2 for n in spine.shape)
        w.slices.brush("press", centre, "spine", False)
        w.slices.brush("release", centre, "spine", False)
        assert lesion.document.lesion.masks["spine"].any()
        assert not lesion.document.lesion.masks[w.state.atlas.volumes[0].name].any()
    finally:
        w.close()


def fraction_lesion(atlas, structure_id, share):
    volume = atlas.volumes[0]
    where = np.flatnonzero(volume.data == structure_id)
    mask = np.zeros(volume.shape, dtype=bool)
    mask.flat[where[:max(1, round(len(where) * share))]] = True
    return Lesion.empty(atlas).with_mask(volume.name, mask)


def test_deficits_start_with_a_prompt(window, qapp):
    text = entered(window, qapp).deficits.toPlainText()
    assert text.startswith(EMPTY_LESION)


def test_deficits_follow_the_report(window, qapp):
    lesion = entered(window, qapp)
    lesion.document.set_lesion(structure_lesion(window.state.atlas, 101), "Alpha")
    text = lesion.deficits.toPlainText()
    assert "Toy loop" in text and "Loss on the right side." in text
    assert "Alpha gyrus (left)" in text and "100%" in text
    assert "Spared" in text and "Short path" in text
    assert "References" in text and DISCLAIMER in text
    assert "partly" not in text


def test_a_partly_broken_step_says_so(window, qapp):
    lesion = entered(window, qapp)
    lesion.document.set_lesion(fraction_lesion(window.state.atlas, 101, 0.10), "Part")
    assert "partly" in lesion.deficits.toPlainText()


def test_the_hit_list_ranks_structures_and_selects_one(window, qapp):
    lesion = entered(window, qapp)
    atlas = window.state.atlas
    mask = structure_lesion(atlas, 101).masks[atlas.volumes[0].name] | fraction_lesion(
        atlas, 112, 0.5).masks[atlas.volumes[0].name]
    lesion.document.set_lesion(Lesion.empty(atlas).with_mask(atlas.volumes[0].name, mask), "Two")
    rows = [lesion.hit.item(i).text() for i in range(lesion.hit.count())]
    assert rows[0] == "Alpha gyrus (left)  100%" and any(r.startswith("Beta nucleus (right)") for r in rows)
    lesion.place.set_tool("brush")
    lesion.hit.itemClicked.emit(lesion.hit.item(0))
    assert window.state.selected == 101


def test_shares_read_as_whole_percents_and_slivers_as_under_one():
    from cns_desktop.lesion.results_panel import percent
    assert percent(1.0) == "100%" and percent(0.124) == "12%" and percent(0.004) == "under 1%"


def test_each_route_group_says_where_it_starts(window, qapp):
    lesion = entered(window, qapp)
    lesion.document.set_lesion(structure_lesion(window.state.atlas, 101), "Alpha")
    assert "From the left alpha gyrus" in lesion.deficits.toPlainText()


@pytest.fixture(scope="module")
def sign_atlas(tmp_path_factory):
    from atlas_fixtures import TOY_PATHWAY_TEXTS

    root = tmp_path_factory.mktemp("lesionsigns")
    src = write_extended_source_tree(root, tracts=True, pathways=True)
    loop = TOY_PATHWAY_TEXTS["pathway-loop"].replace(
        "Lesion: Loss on the {opposite} side.",
        "Lesion: Loss on the {opposite} side.\nSign: Numb {opposite} hand [ref2020].", 1)
    (src / "knowledge" / "en" / "pathway-loop.md").write_text(loop)
    return build(src, root / "out" / "toy", cache=root / "cache", log=lambda *_: None)


def test_a_whole_case_runs_and_is_recorded(qapp, sign_atlas, tmp_path):
    import random
    w = open_window(qapp, sign_atlas, tmp_path)
    try:
        lesion = entered(w, qapp)
        cases = lesion.cases
        cases.rng = random.Random(3)
        cases.new_case_button.click()
        case = cases.case
        assert case is not None and all(s in cases.signs_label.text() for s in case.signs)
        assert not cases.check_button.isEnabled()
        lesion.document.set_lesion(case.target, "Answer")
        assert cases.check_button.isEnabled()
        cases.check_button.click()
        result = cases.result_label.text()
        assert "Matched" in result and case.label in result
        assert w.progress_store().cases() == [(case.target_id, len(case.signs), 0, 0)]
        assert w.slices.answer_masks and w.view.answer_actor.GetVisibility()
    finally:
        w.close()


def test_a_case_survives_leaving_and_returning(qapp, sign_atlas, tmp_path):
    import random
    w = open_window(qapp, sign_atlas, tmp_path)
    try:
        lesion = entered(w, qapp)
        lesion.cases.rng = random.Random(3)
        lesion.cases.new_case_button.click()
        case = lesion.cases.case
        w.workspaces.switch("Explore")
        assert not w.slices.answer_masks
        entered(w, qapp)
        assert lesion.cases.case is case and case.signs[0] in lesion.cases.signs_label.text()
    finally:
        w.close()


def test_cases_say_so_when_no_route_has_signs(window, qapp):
    cases = entered(window, qapp).cases
    cases.new_case_button.click()
    assert cases.case is None and cases.signs_label.text() == NO_CASES


def test_territories_live_only_in_the_lesion_workspace(qapp, territory_atlas, tmp_path):
    w = open_window(qapp, territory_atlas, tmp_path)
    try:
        atlas = w.state.atlas
        hidden = [s.id for s in atlas.structures if s.kind == "territory"] + [7]
        assert not any(i in w.tree.items for i in hidden)
        place = entered(w, qapp).place
        group = place.territory_tree.topLevelItem(0)
        assert group.child(0).toolTip(0) == group.child(0).text(0)
        layout = place.layout()
        assert layout.stretch(layout.indexOf(place.territory_tree)) > 0
    finally:
        w.close()

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog

from cns_atlas.lesions import Lesion, pack_mask, signs_of, unpack_mask
from cns_lab.files import FileError
from cns_lab.files import dumps as experiment_text
from cns_lab.files import loads as experiment_from
from cns_study.lessons import EXTENSION, WORKSPACES, Lesson, LessonError, Step, read
from cns_study.questions import pool_for
from cns_study.session import QuizChoice

from .views.lesson_window import LessonWindow

FILTER = f"Lessons (*{EXTENSION})"
NOT_HERE = "Go to Explore, Slices, an open route, the Lab or a placed lesion to add a step."
NO_LESION = "This atlas has no Lesion workspace, so this lesion cannot be shown."
OTHER_IMAGES = "This lesion was made on images this atlas does not have."
NO_ROUTE = "This route is not in this atlas."
NO_LAB = "This atlas has no Lab, so this experiment cannot be shown."
KEPT = "Your unsaved experiment was kept, so this step was not shown."
NOTHING_TO_ASK = "Nothing to ask here in this atlas."


def _missing(count: int) -> str:
    one = count == 1
    return (f"{count} structure{'' if one else 's'} of this step {'is' if one else 'are'} not in "
            "this atlas.")


class LessonMode:
    def _add_lesson_menu(self) -> None:
        menu = self.topbar.menu("File")
        menu.addSeparator()
        self.new_lesson_action = QAction("New lesson", self, triggered=self.new_lesson)
        self.open_lesson_action = QAction("Open lesson…", self,
                                          triggered=lambda _checked=False: self.open_lesson())
        menu.addAction(self.new_lesson_action)
        menu.addAction(self.open_lesson_action)
        self.lesson_window: LessonWindow | None = None
        self.pick_lesson_open = lambda: QFileDialog.getOpenFileName(
            self, "Open lesson", "", FILTER)[0]
        self.pick_lesson_save = lambda: QFileDialog.getSaveFileName(
            self, "Save lesson", f"lesson{EXTENSION}", FILTER)[0]

    def _calm(self) -> None:
        if self.quiz_active:
            self.quiz.stop()
        if self.pathway_active:
            self.pathways.leave()

    def capture_step(self) -> Step | None:
        if self.quiz_active:
            return None
        current = self.workspaces.current
        if current == "Lab" and self.lab is not None:
            document = self.lab.document
            return Step("lab", document.model.name,
                        data={"experiment": experiment_text(document.experiment),
                              "playhead": float(document.playhead)})
        if self.pathway_active and self.pathways.pathway is not None:
            panel = self.pathways
            return Step("route", f"{panel.pathway.name}, step {panel.index + 1}",
                        data={"key": panel.pathway.key, "side": panel.side,
                              "index": int(panel.index)})
        if current == "Lesion" and self.lesion is not None:
            return self._capture_lesion()
        if current not in WORKSPACES:
            return None
        hidden, selected, axis, mm, volume = self._snapshot()
        camera = self._camera_rows()
        title = self.state.atlas.get(selected).name if selected is not None else current
        return Step("view", title, data={
            "workspace": current, "selected": selected, "hidden": [int(i) for i in hidden],
            "camera": camera, "axis": axis, "mm": float(mm), "volume": volume or ""})

    def _camera_rows(self) -> list[list[float]]:
        return [[float(v) for v in row] for row in self.view.camera_position.to_list()]

    def _capture_lesion(self) -> Step | None:
        document = self.lesion.document
        if document.lesion.is_empty:
            return None
        signs = signs_of(document.report)
        title = f"Lesion: {signs[0]}" if signs else "Lesion"
        masks = {name: pack_mask(mask) for name, mask in document.lesion.masks.items()
                 if mask.any()}
        return Step("lesion", title[:200], data={"masks": masks, "camera": self._camera_rows()})

    def show_step(self, step: Step) -> list[str]:
        self._calm()
        return {"view": self._show_view, "route": self._show_route, "lab": self._show_lab,
                "quiz": self._show_quiz, "lesion": self._show_lesion}[step.kind](step.data)

    def _show_lesion(self, data: dict) -> list[str]:
        if self.lesion is None:
            return [NO_LESION]
        lesion = Lesion.empty(self.state.atlas)
        shapes = {name: mask.shape for name, mask in lesion.masks.items()}
        for name, row in data["masks"].items():
            if shapes.get(name) != tuple(row["shape"]):
                return [OTHER_IMAGES]
            try:
                lesion = lesion.with_mask(name, unpack_mask(row))
            except ValueError:
                return [OTHER_IMAGES]
        self.workspaces.switch("Lesion")
        self.lesion.document.set_lesion(lesion, "Lesson step")
        if data["camera"] is not None:
            self._put_camera([tuple(row) for row in data["camera"]])
            self.view.render()
        return []

    def _show_view(self, data: dict) -> list[str]:
        self.workspaces.switch(data["workspace"])
        known = set(self.state.geometry_ids)
        hidden = [i for i in data["hidden"] if i in known]
        selected = data["selected"]
        lost = len(data["hidden"]) - len(hidden)
        if selected is not None and selected not in self.state.atlas:
            selected, lost = None, lost + 1
        volumes = {v.name for v in self.state.atlas.volumes}
        volume = data["volume"] if data["volume"] in volumes else ""
        self._restore(hidden, selected, data["axis"], data["mm"], volume)
        if data["camera"] is not None:
            self._put_camera([tuple(row) for row in data["camera"]])
            self.view.render()
        return [_missing(lost)] if lost else []

    def _show_route(self, data: dict) -> list[str]:
        if not self.open_route_step(data["key"], data["side"], data["index"]):
            return [NO_ROUTE]
        return []

    def _show_lab(self, data: dict) -> list[str]:
        if self.lab is None:
            return [NO_LAB]
        try:
            experiment, report = experiment_from(data["experiment"], self.state.atlas.models)
        except FileError as exc:
            return [str(exc)]
        if not self.lab.show_experiment(experiment, min(data["playhead"], experiment.length)):
            return [KEPT]
        return list(report)

    def _show_quiz(self, data: dict) -> list[str]:
        level, scope = data["level"], data["scope"]
        if isinstance(scope, int) and scope not in self.state.atlas:
            scope = None
        try:
            pool = pool_for(self.state.atlas, level, scope)
        except (KeyError, ValueError):
            pool = []
        if not pool:
            return [NOTHING_TO_ASK]
        self.start_quiz(QuizChoice(data["mode"], level, scope, True))
        return []

    def _lesson(self, lesson: Lesson, path: Path | None, editing: bool) -> LessonWindow | None:
        if self.lesson_window is not None and not self.lesson_window.close():
            return None
        self.lesson_window = LessonWindow(self, lesson, path, editing)
        self.lesson_window.show()
        return self.lesson_window

    def new_lesson(self) -> LessonWindow | None:
        name = str(self.state.atlas.metadata.get("name", ""))
        return self._lesson(Lesson(atlas=name), None, True)

    def open_lesson(self, path: Path | None = None) -> LessonWindow | None:
        path = path or self.pick_lesson_open()
        if not path:
            return None
        try:
            lesson = read(Path(path))
        except LessonError as exc:
            self.inform("Cannot open the lesson", str(exc))
            return None
        opened = self._lesson(lesson, Path(path), False)
        if opened is not None and lesson.steps:
            opened.go(0)
        return opened

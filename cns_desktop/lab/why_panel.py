from __future__ import annotations

from html import escape

from PySide6.QtWidgets import QTextBrowser

from cns_atlas.timelines import note_parts
from cns_lab.why import chain, normal_note, phrase

from ..views.info_panel import references_html

DRAFT = "Draft: not yet reviewed."
SEPARATOR = "\x1f"


def duration_text(minutes: float) -> str:
    minutes = round(minutes)
    days, rest = divmod(minutes, 1440)
    hours, mins = divmod(rest, 60)
    if days:
        return f"{days} d" + (f" {hours} h" if hours else "")
    if hours:
        return f"{hours} h" + (f" {mins} min" if mins else "")
    return f"{mins} min"


def moment_text(document, t: float) -> str:
    if t < 1440:
        return duration_text(t)
    clock = round(document.experiment.start_clock + t)
    day = clock // 1440 + 1
    clock %= 1440
    return f"day {day}, {clock // 60:02d}:{clock % 60:02d}"


def block_label(document, block) -> str:
    name = document.name_of(block.experiment)
    experiment = next((e for e in document.model.experiments if e.key == block.experiment), None)
    if experiment and experiment.options:
        option = experiment.options[0]
        value = block.option_map.get(option.key, option.default)
        return f"{name} {value:g} {option.unit}"
    return name


def time_heading(document, t: float) -> str:
    heading = f"At {moment_text(document, t)}"
    started = [b for b in document.experiment.blocks if not b.present and b.start <= t]
    if started:
        last = max(started, key=lambda b: b.start)
        if t > last.start:
            heading += f", {duration_text(t - last.start)} after {block_label(document, last)}"
    return heading


class WhyPanel(QTextBrowser):
    def __init__(self, document, parent=None) -> None:
        super().__init__(parent)
        self.document = document
        self.setOpenExternalLinks(True)
        document.changed.connect(self.refresh)
        document.playhead_moved.connect(lambda _t: self.refresh())
        self.refresh()

    def _source(self, key: str) -> str:
        doc = self.document
        return doc.atlas.lab_source(doc.model.key, key) or ""

    def refresh(self) -> None:
        self.setHtml(self.html())

    def html(self) -> str:
        doc = self.document
        if doc.error:
            return f"<p>{escape(doc.error)}</p><p><i>{DRAFT}</i></p>"
        t = doc.playhead
        parts = [f"<p><b>{escape(time_heading(doc, t))}</b></p>"]
        items: list[str] = []
        if doc.run is not None:
            for step in chain(doc.simulator, doc.run, t):
                if step.kind == "change":
                    name = doc.name_of(step.source)
                    items.append(f"{name}: {self._source(step.text_key + '.description')}")
                    continue
                text = self._source(step.text_key)
                if step.value is not None:
                    value = doc.simulator.values[step.value]
                    text += f" {value.name} {phrase(value, step.ratio)}."
                else:
                    text += f" Its strength {phrase(None, step.ratio)}."
                items.append(text)
        edited = []
        for key, value in doc.experiment.values:
            parameter = doc.model.parameter(key)
            edited.append(f"{parameter.name} is {value:g} {parameter.unit} "
                          f"(normal {parameter.value:g}).")
        if not items and not doc.experiment.blocks:
            note = normal_note(doc.model, doc.experiment.start_clock + t)
            if note:
                items.append(self._source(f"normal.{note}"))
        joined, references = note_parts(SEPARATOR.join(items), doc.atlas.references)
        numbered = [p for p in joined.split(SEPARATOR) if p]
        if numbered:
            parts.append("<ol>" + "".join(f"<li>{escape(p)}</li>" for p in numbered) + "</ol>")
        if edited:
            parts.append("<p>Edited values: " + " ".join(escape(e) for e in edited) + "</p>")
        parts += references_html(references)
        parts.append(f"<p><i>{DRAFT}</i></p>")
        return "".join(parts)

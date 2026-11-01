from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QTextBrowser

from cns_atlas import DISCLAIMER
from cns_desktop.design import rich
from cns_desktop.views.info_panel import references_html

EMPTY_LESION = "Place a lesion to see what it hits and which routes it breaks."
NOTHING_BROKEN = "This lesion breaks no route the atlas can follow."
CASE_HEADING = "The case's lesion"


def percent(share: float) -> str:
    whole = round(share * 100)
    return f"{whole}%" if whole else "under 1%"


class DeficitsPanel(QTextBrowser):
    def __init__(self, document, parent=None) -> None:
        super().__init__(parent)
        self.document = document
        self.setOpenExternalLinks(True)
        QTextBrowser.document(self).setDefaultStyleSheet(rich.document_css())
        QTextBrowser.document(self).setDocumentMargin(12)
        self.case = None
        document.changed.connect(self._on_changed)
        self.refresh()

    def _on_changed(self) -> None:
        self.case = None
        self.refresh()

    def show_case(self, report, label: str) -> None:
        self.case = (report, label)
        self.refresh()

    def refresh(self) -> None:
        kept = self.verticalScrollBar().value()
        self.setHtml(self.html())
        self.verticalScrollBar().setValue(kept)

    def html(self) -> str:
        doc = self.document
        atlas = doc.atlas
        if self.case is not None:
            report, label = self.case
            return (f"<h2>{escape(CASE_HEADING)}: {escape(label)}</h2>"
                    + self._deficits(atlas, report) + self._notice())
        if doc.lesion.is_empty:
            return f"<p>{escape(EMPTY_LESION)}</p>" + self._notice()
        return self._deficits(atlas, doc.report) + self._notice()

    def _deficits(self, atlas, report) -> str:
        parts = []
        groups: dict[tuple[str, str], list] = {}
        for deficit in report.deficits:
            groups.setdefault((deficit.route, deficit.side), []).append(deficit)
        if not groups:
            parts.append(f"<p>{escape(NOTHING_BROKEN)}</p>")
        starts = {p.key: p.start for p in atlas.pathways}
        for (route, side), deficits in groups.items():
            first = deficits[0]
            parts.append(f"<h3>{escape(first.route_name)}</h3>")
            parts.append(rich.secondary(f"From the {escape(side)} {escape(starts[route])}"))
            items = []
            for deficit in deficits:
                partly = f"{rich.chip('partly', 'edited')}&nbsp;&nbsp;" if deficit.partly else ""
                hit = ", ".join(f"{escape(atlas.get(i).name)} {percent(s)}"
                                for i, s in deficit.structures)
                items.append(f"<li>{partly}{escape(deficit.lesion)}"
                             f"<br>{rich.secondary(f'Step {deficit.step + 1}: {hit}')}</li>")
            parts.append("<ol>" + "".join(items) + "</ol>")
            parts += references_html(first.references)
        if report.spared:
            names = {p.key: p.name for p in atlas.pathways}
            spared = ", ".join(escape(names[key]) for key in report.spared)
            parts.append(f"{rich.heading('Spared')}<p>{spared}</p>")
        return "".join(parts)

    @staticmethod
    def _notice() -> str:
        return f"<p><i>{escape(DISCLAIMER)}</i></p>"


class HitPanel(QListWidget):
    def __init__(self, document, state, on_select=None, parent=None) -> None:
        super().__init__(parent)
        self.document, self.state = document, state
        self.on_select = on_select or state.select
        self.itemClicked.connect(self._on_item)
        document.changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        self.clear()
        atlas = self.document.atlas
        ranked = sorted(self.document.report.hits.items(), key=lambda pair: (-pair[1], pair[0]))
        for structure_id, share in ranked:
            if atlas.get(structure_id).kind == "territory":
                continue
            item = QListWidgetItem(f"{atlas.get(structure_id).name}  {percent(share)}")
            item.setData(Qt.ItemDataRole.UserRole, structure_id)
            self.addItem(item)

    def _on_item(self, item: QListWidgetItem) -> None:
        self.on_select(int(item.data(Qt.ItemDataRole.UserRole)))

from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QKeySequence, QShortcut, QTextDocument

from cns_atlas import DISCLAIMER, Entry, Structure
from cns_atlas.knowledge import SECTIONS
from cns_atlas.names import linked_html

from ..design import rich
from ..design.linked import STRUCTURE, LinkedText
from ..report import mistake_link, status_html
from ..state import AppState


def references_html(references) -> list[str]:
    if not references:
        return []
    items = []
    for ref in references:
        link = f" <a href='{escape(ref.link)}'>link</a>" if ref.link else ""
        items.append(f"<li>{escape(ref.citation())}{link}</li>")
    return [f"{rich.heading('References')}<ol>{''.join(items)}</ol>"]


def entry_html(entry: Entry | None, names=None, shown: int | None = None) -> list[str]:
    if entry is None:
        return [rich.secondary("No description yet.")]
    parts = []
    parts.append(rich.secondary(status_html(entry.status, entry.review_line())))
    for name in SECTIONS:
        if name in entry.sections:
            text = entry.numbered(entry.sections[name])
            body = linked_html(text, names.find(text, shown)) if names else escape(text)
            parts.append(f"{rich.heading(name)}<p>{body}</p>")
    parts += references_html(entry.references)
    return parts


class InfoPanel(LinkedText):
    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        self.trail: list[int] = []
        self._arriving: tuple[int | None, int] | None = None
        self.document().setDefaultStyleSheet(rich.document_css())
        self.document().setDocumentMargin(12)
        self.back_requested.connect(self.go_back)
        QShortcut(QKeySequence("Alt+Left"), self, self.go_back,
                  context=Qt.ShortcutContext.WindowShortcut)
        state.selection_changed.connect(self.show_structure)
        self.show_structure(state.selected)

    def _on_anchor(self, url: QUrl) -> None:
        current = self.state.selected
        if url.scheme() == STRUCTURE and current is not None:
            self._arriving = (current, int(url.path())) if url.path().isdigit() else None
        super()._on_anchor(url)

    def go_back(self) -> None:
        if not self.trail:
            return
        previous = self.trail.pop()
        self._arriving = (None, previous)
        self.structure_linked.emit(previous)

    def show_structure(self, structure_id: int | None) -> None:
        arriving, self._arriving = self._arriving, None
        if arriving is not None and arriving[1] == structure_id:
            if arriving[0] is not None and arriving[0] != structure_id:
                self.trail.append(arriving[0])
        else:
            self.trail.clear()
        self.setHtml(self.html_for(structure_id))

    def warm(self, structure_id: int) -> None:
        document = QTextDocument()
        document.setDefaultFont(self.font())
        document.setDefaultStyleSheet(rich.document_css())
        document.setHtml(self.html_for(structure_id))
        document.setTextWidth(self.viewport().width())
        document.size()

    def html_for(self, structure_id: int | None) -> str:
        if structure_id is None:
            return rich.secondary("Click a structure in the 3D view or the tree.")
        s = self.state.atlas.get(structure_id)
        r, g, b = s.rgb_triplet
        parts = []
        if self.trail:
            back = escape(self.state.atlas.get(self.trail[-1]).name)
            parts.append(f"<p><a href='back:'>← Back to {back}</a></p>")
        parts.append(f"<h2><span style='color:#{r:02x}{g:02x}{b:02x}'>&#9632;&nbsp;</span>"
                     f"{escape(s.name)}</h2>")
        if s.side in ("left", "right") and f"({s.side})" not in s.name:
            parts.append(rich.secondary(s.side))
        entry = self.state.atlas.knowledge(structure_id)
        parts += entry_html(entry, self.state.atlas.names, structure_id)
        parts += self._sources_html(s)
        if entry is not None:
            parts.append(mistake_link(f"{s.name} (structure {s.id})", self.state.atlas,
                                      entry.status))
        parts.append("<p></p>" + rich.card(escape(DISCLAIMER)))
        return "".join(parts)

    def _sources_html(self, structure: Structure) -> list[str]:
        sources = [self.state.atlas.sources[i] for i in structure.sources
                   if i in self.state.atlas.sources]
        if not sources:
            return []
        rows = "".join(f"<li>{escape(src.citation())} Licence: {escape(src.licence)}.</li>"
                       for src in sources)
        return [f"{rich.heading('Geometry source')}<ul>{rows}</ul>"]

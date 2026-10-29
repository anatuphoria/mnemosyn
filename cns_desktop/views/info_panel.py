from __future__ import annotations

from html import escape

from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QTextBrowser

from cns_atlas import DISCLAIMER, Entry, Structure
from cns_atlas.knowledge import SECTIONS

from ..design import rich
from ..state import AppState


def references_html(references) -> list[str]:
    if not references:
        return []
    items = []
    for ref in references:
        link = f" <a href='{escape(ref.link)}'>link</a>" if ref.link else ""
        items.append(f"<li>{escape(ref.citation())}{link}</li>")
    return [f"{rich.heading('References')}<ol>{''.join(items)}</ol>"]


def entry_html(entry: Entry | None) -> list[str]:
    if entry is None:
        return [rich.secondary("No description yet.")]
    parts = []
    if entry.status == "draft":
        parts.append(rich.secondary(f"{rich.chip('Draft', 'edited')} · not yet reviewed"))
    for name in SECTIONS:
        if name in entry.sections:
            body = escape(entry.numbered(entry.sections[name]))
            parts.append(f"{rich.heading(name)}<p>{body}</p>")
    parts += references_html(entry.references)
    return parts


class InfoPanel(QTextBrowser):
    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        self.setOpenExternalLinks(True)
        self.document().setDefaultStyleSheet(rich.document_css())
        self.document().setDocumentMargin(12)
        state.selection_changed.connect(self.show_structure)
        self.show_structure(state.selected)

    def show_structure(self, structure_id: int | None) -> None:
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
        parts = [f"<h2><span style='color:#{r:02x}{g:02x}{b:02x}'>&#9632;&nbsp;</span>"
                 f"{escape(s.name)}</h2>"]
        if s.side in ("left", "right"):
            parts.append(rich.secondary(s.side))
        parts += entry_html(self.state.atlas.knowledge(structure_id))
        parts += self._sources_html(s)
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

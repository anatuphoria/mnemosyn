from __future__ import annotations

from html import escape

from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QTextBrowser

from cns_atlas import DISCLAIMER, Entry, Structure
from cns_atlas.knowledge import SECTIONS

from ..state import AppState


def references_html(references) -> list[str]:
    if not references:
        return []
    items = []
    for ref in references:
        link = f" <a href='{escape(ref.link)}'>link</a>" if ref.link else ""
        items.append(f"<li>{escape(ref.citation())}{link}</li>")
    return [f"<h4>References</h4><ol>{''.join(items)}</ol>"]


def entry_html(entry: Entry | None) -> list[str]:
    if entry is None:
        return ["<p><i>No description yet.</i></p>"]
    parts = ["<p><b>Draft</b>: not yet reviewed.</p>"] if entry.status == "draft" else []
    for name in SECTIONS:
        if name in entry.sections:
            body = escape(entry.numbered(entry.sections[name]))
            parts.append(f"<h4>{name}</h4><p>{body}</p>")
    parts += references_html(entry.references)
    return parts


class InfoPanel(QTextBrowser):
    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        self.setOpenExternalLinks(True)
        state.selection_changed.connect(self.show_structure)
        self.show_structure(state.selected)

    def show_structure(self, structure_id: int | None) -> None:
        self.setHtml(self.html_for(structure_id))

    def warm(self, structure_id: int) -> None:
        document = QTextDocument()
        document.setDefaultFont(self.font())
        document.setHtml(self.html_for(structure_id))
        document.setTextWidth(self.viewport().width())
        document.size()

    def html_for(self, structure_id: int | None) -> str:
        if structure_id is None:
            return "<p><i>Click a structure in the 3D view or the tree.</i></p>"
        s = self.state.atlas.get(structure_id)
        r, g, b = s.rgb_triplet
        parts = [f"<h2><span style='color:#{r:02x}{g:02x}{b:02x}'>&#9632;</span> "
                 f"{escape(s.name)}</h2>"]
        if s.side in ("left", "right"):
            parts.append(f"<p>{s.side}</p>")
        parts += entry_html(self.state.atlas.knowledge(structure_id))
        parts += self._sources_html(s)
        parts.append(f"<p style='color:#c55'><small>{escape(DISCLAIMER)}</small></p>")
        return "".join(parts)

    def _sources_html(self, structure: Structure) -> list[str]:
        sources = [self.state.atlas.sources[i] for i in structure.sources
                   if i in self.state.atlas.sources]
        if not sources:
            return []
        rows = "".join(f"<li>{escape(src.citation())} Licence: {escape(src.licence)}.</li>"
                       for src in sources)
        return [f"<h4>Geometry source</h4><ul>{rows}</ul>"]

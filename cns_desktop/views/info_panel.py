from __future__ import annotations

from html import escape

from PySide6.QtWidgets import QTextBrowser

from brain_tui.knowledge import KnowledgeBase

from ..state import AppState


class InfoPanel(QTextBrowser):
    def __init__(self, state: AppState, kb: KnowledgeBase, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        self.kb = kb
        state.selection_changed.connect(self.show_structure)
        self.show_structure(state.selected)

    def show_structure(self, sid: str | None) -> None:
        if sid is None:
            self.setHtml("<p><i>Click a structure in the 3D view or the tree.</i></p>")
            return
        s = self.state.atlas.structures[sid]
        k = self.kb.get(s.name)
        swatch = "#%02x%02x%02x" % s.color
        self.setHtml(
            f"<h2>{escape(s.name)}</h2>"
            f"<p><span style='color:{swatch}'>■</span> {escape(s.system)}</p>"
            f"<h4>Function</h4><p>{escape(k['function'])}</p>"
            f"<h4>Connections</h4><p>{escape(k['connections'])}</p>"
            f"<h4>Clinical</h4><p>{escape(k['disorders'])}</p>"
            "<p style='color:#c55'><small>Educational model - not for diagnosis.</small></p>"
        )

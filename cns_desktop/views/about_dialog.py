from __future__ import annotations

import sys
from html import escape
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QListWidget, QTabWidget,
                               QVBoxLayout, QWidget)

from cns_atlas import DISCLAIMER, Atlas
from cns_atlas.model import Source

APP_NAME = "Mnemosyn"
WORDMARK = Path(__file__).resolve().parents[1] / "resources" / "wordmark.svg"
WORDMARK_WIDTH = 320
SIZE = (720, 520)
BUILT_WITH = ("The interface uses the Inter typeface by Rasmus Andersson (SIL Open Font License 1.1) "
              "and the Lucide icons (ISC License).")


def app_version() -> str:
    try:
        return version("mnemosyn")
    except PackageNotFoundError:
        bundled = Path(getattr(sys, "_MEIPASS", "")) / "VERSION"
        if getattr(sys, "frozen", False) and bundled.is_file():
            return bundled.read_text(encoding="utf-8").strip()
        return "development"


def is_test_version(text: str) -> bool:
    return text.split(".")[0] == "0"


def about_text(atlas: Atlas) -> str:
    name = escape(str(atlas.metadata.get("name", "")))
    version = escape(str(atlas.metadata.get("version", "")))
    notice = ""
    if atlas.local_only:
        names = ", ".join(escape(source_label(atlas.sources[i]) if i in atlas.sources else i)
                          for i in atlas.local_only)
        notice = ("<p><b>Local build, not for sharing.</b> It contains data that may not be "
                  f"shared yet: {names}.</p>")
    current = app_version()
    label = f"{current}, test version" if is_test_version(current) else current
    return (f"<h3>{APP_NAME}</h3><p>Version {escape(label)}</p>"
            f"<p>{escape(DISCLAIMER)}</p>"
            f"<p>Atlas package: {name} {version}</p>{notice}"
            f"<p>{escape(BUILT_WITH)}</p>")


def source_label(source: Source) -> str:
    return source.provides or source.title


def short_authors(source: Source) -> str:
    names = [part.strip() for part in source.authors.split(",") if part.strip()]
    first = names[0].rsplit(" ", 1)[0] if names else source.id
    return f"{first} et al." if len(names) > 1 else first


def source_row(source: Source, local: bool) -> str:
    tag = " - local only" if local else ""
    return f"{source_label(source)} - {short_authors(source)} {source.year}{tag} - {source.licence}"


class AboutDialog(QDialog):
    def __init__(self, atlas: Atlas, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setFixedSize(*SIZE)
        self._sources = list(atlas.sources.values())

        about = QLabel(about_text(atlas))
        about.setWordWrap(True)
        about.setAlignment(Qt.AlignmentFlag.AlignTop)
        about.setTextFormat(Qt.TextFormat.RichText)

        self.sources = QListWidget()
        for source in self._sources:
            self.sources.addItem(source_row(source, source.id in atlas.local_only))
        self.detail = QLabel()
        self.detail.setWordWrap(True)
        self.detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.detail.setOpenExternalLinks(True)
        self.sources.currentRowChanged.connect(self._show_source)
        listing = QWidget()
        column = QVBoxLayout(listing)
        column.addWidget(self.sources, 1)
        column.addWidget(self.detail)

        wordmark = QSvgWidget(str(WORDMARK))
        natural = wordmark.renderer().defaultSize()
        wordmark.setFixedSize(WORDMARK_WIDTH,
                              round(WORDMARK_WIDTH * natural.height() / max(natural.width(), 1)))
        front = QWidget()
        front_layout = QVBoxLayout(front)
        front_layout.addWidget(wordmark, 0, Qt.AlignmentFlag.AlignHCenter)
        front_layout.addWidget(about, 1)
        self.tabs = QTabWidget()
        self.tabs.addTab(front, "About")
        self.tabs.addTab(listing, "Data sources")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(buttons)

    def _show_source(self, row: int) -> None:
        if not 0 <= row < len(self._sources):
            self.detail.setText("")
            return
        source = self._sources[row]
        link = f"https://doi.org/{source.doi}" if source.doi else source.url
        anchor = f'<br><a href="{escape(link)}">{escape(link)}</a>' if link else ""
        self.detail.setText(f"{escape(source.citation())} Licence: {escape(source.licence)}."
                            f"{anchor}")

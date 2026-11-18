from __future__ import annotations

import sys
import tomllib
from html import escape
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QPushButton, QScrollArea, QStackedWidget, QStyle,
                               QVBoxLayout, QWidget)

from cns_atlas import DISCLAIMER, Atlas
from cns_atlas.model import Source

from ..design import icons
from ..design.brand import KeyMark
from ..design.theme import set_flag, set_role, set_tone
from ..design.tokens import GAP, SIZE
from ..design.widgets import Card, ElidedLabel, SegmentedControl, button_icon, chip

APP_NAME = "Mnemosyn"
TAGLINE = "A 3D atlas of the central nervous system, with a lab for the body's control loops"
APP_LICENCE = "GPL 3.0 or later"
SITE_URL = "https://mnemo.saeed.cool/"
HANDBOOK_URL = "https://mnemo.saeed.cool/handbook/"
DOWNLOAD_URL = "https://mnemo.saeed.cool/download/"
SOURCE_URL = "https://github.com/anatuphoria/mnemosyn"
PROBLEM_URL = "https://github.com/anatuphoria/mnemosyn/issues/new"
LINKS = (("Website", "globe", SITE_URL), ("Handbook", "book-open", HANDBOOK_URL),
         ("Source code", "code-xml", SOURCE_URL))
PAGES = (("about", "About"), ("sources", "Data sources"))
BUILT_WITH = ("Typeface Inter by Rasmus Andersson (SIL Open Font License 1.1). "
              "Icons from Lucide (ISC License).")
LICENCE_TAGS = (
    ("CC0", "CC0"),
    ("ShareAlike 4.0", "CC BY SA 4.0"),
    ("Attribution 4.0", "CC BY 4.0"),
    ("Creative Commons Attribution", "CC BY"),
    ("GNU General Public License", "GPL"),
    ("BSD 3-Clause", "BSD 3 Clause"),
    ("Permissive", "Permissive"),
)


PROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def _checkout_version() -> str | None:
    try:
        project = tomllib.loads(PROJECT.read_text(encoding="utf-8"))["project"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return None
    return project.get("version") if project.get("name") == "mnemosyn" else None


def app_version() -> str:
    if getattr(sys, "frozen", False):
        bundled = Path(getattr(sys, "_MEIPASS", "")) / "VERSION"
        if bundled.is_file():
            return bundled.read_text(encoding="utf-8").strip()
    checkout = _checkout_version()
    if checkout:
        return checkout
    try:
        return version("mnemosyn")
    except PackageNotFoundError:
        return "development"


def is_test_version(text: str) -> bool:
    return text.split(".")[0] == "0"


def source_label(source: Source) -> str:
    return source.provides or source.title


def short_authors(source: Source) -> str:
    names = [part.strip() for part in source.authors.split(",") if part.strip()]
    first = names[0].rsplit(" ", 1)[0] if names else source.id
    return f"{first} et al." if len(names) > 1 else first


def licence_tag(source: Source, local: bool) -> tuple[str, str]:
    if local:
        return "Local only", "edited"
    for needle, tag in LICENCE_TAGS:
        if needle in source.licence:
            return tag, "text2"
    return "Other", "text2"


def source_link(source: Source) -> str:
    return f"https://doi.org/{source.doi}" if source.doi else source.url


def local_note(atlas: Atlas) -> str:
    if not atlas.local_only:
        return ""
    listed = [i for i in atlas.local_only if i in atlas.sources]
    unlisted = [i for i in atlas.local_only if i not in atlas.sources]
    count = len(listed)
    noun = "source" if count == 1 else "sources"
    text = (f"<b>Local build, not for sharing.</b> It holds {count} {noun} that may not be "
            "shared yet, marked Local only under Data sources.")
    if unlisted:
        text += f" Also not for sharing: {escape(', '.join(unlisted))}."
    return text


def _label(text: str, tone: str = "", role: str = "") -> QLabel:
    label = QLabel(text)
    if tone:
        set_tone(label, tone)
    if role:
        set_role(label, role)
    return label


class SourceRow(QFrame):
    def __init__(self, source: Source, local: bool, parent=None) -> None:
        super().__init__(parent)
        self.source = source
        self.setProperty("sourcerow", "true")
        self.setProperty("open", "false")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.provides = ElidedLabel(source_label(source))
        self.authors = ElidedLabel(f"{short_authors(source)} {source.year}")
        set_tone(self.authors, "text2")
        text, tone = licence_tag(source, local)
        self.tag = chip(text, tone)
        self.chevron = QLabel()
        self.chevron.setFixedSize(SIZE["icon"], SIZE["icon"])
        tag_cell = QWidget()
        tag_cell.setFixedWidth(SIZE["tag_column"])
        tag_row = QHBoxLayout(tag_cell)
        tag_row.setContentsMargins(0, 0, 0, 0)
        tag_row.addWidget(self.tag)
        tag_row.addStretch(1)
        summary = QHBoxLayout()
        summary.setContentsMargins(0, 0, 0, 0)
        summary.setSpacing(GAP["medium"])
        summary.addWidget(self.provides, 5)
        summary.addWidget(self.authors, 4)
        summary.addWidget(tag_cell)
        summary.addWidget(self.chevron)
        self.detail = QLabel(self._detail_html())
        self.detail.setWordWrap(True)
        self.detail.setTextFormat(Qt.TextFormat.RichText)
        self.detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.detail.setOpenExternalLinks(True)
        set_tone(self.detail, "text2")
        set_role(self.detail, "secondary")
        self.detail.hide()
        column = QVBoxLayout(self)
        column.setContentsMargins(GAP["medium"], GAP["small"], GAP["medium"], GAP["small"])
        column.setSpacing(GAP["small"])
        column.addLayout(summary)
        column.addWidget(self.detail)
        self._show_chevron()

    def _detail_html(self) -> str:
        source = self.source
        link = source_link(source)
        anchor = f'<br><a href="{escape(link)}">{escape(link)}</a>' if link else ""
        return f"{escape(source.citation())}<br>Licence: {escape(source.licence)}{anchor}"

    def _show_chevron(self) -> None:
        name = "chevron-down" if self.is_open() else "chevron-right"
        self.chevron.setPixmap(icons.pixmap(name, "text3", SIZE["icon"]))

    def is_open(self) -> bool:
        return self.property("open") == "true"

    def toggle(self) -> None:
        opened = not self.is_open()
        set_flag(self, "open", opened)
        self.detail.setVisible(opened)
        self._show_chevron()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
                event.position().toPoint()):
            self.toggle()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.toggle()
            return
        super().keyPressEvent(event)


class AboutDialog(QDialog):
    def __init__(self, atlas: Atlas, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setFixedSize(*SIZE["dialog_about"])
        self.pages = QStackedWidget()
        self.pages.addWidget(self._front(atlas))
        self.pages.addWidget(self._sources(atlas))
        self.switch = SegmentedControl(list(PAGES))
        self.switch.changed.connect(self.show_page)
        local = sum(i in atlas.sources for i in atlas.local_only)
        count = len(atlas.sources)
        summary = f"{count} {'source' if count == 1 else 'sources'}"
        self.summary = _label(f"{summary}, {local} local only" if local else summary,
                              "text3", "secondary")
        self.summary.hide()
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addWidget(self.switch)
        top.addStretch(1)
        top.addWidget(self.summary)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        foot = QHBoxLayout()
        foot.addStretch(1)
        foot.addWidget(buttons)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(GAP["large"], GAP["large"], GAP["large"], GAP["large"])
        layout.setSpacing(GAP["medium"])
        layout.addLayout(top)
        layout.addWidget(self.pages, 1)
        layout.addLayout(foot)

    def page_names(self) -> list[str]:
        return [label for _key, label in PAGES]

    def show_page(self, key: str) -> None:
        index = [k for k, _label in PAGES].index(key)
        if self.switch.current() != key:
            self.switch.set_current(key)
        self.pages.setCurrentIndex(index)
        self.summary.setVisible(key == "sources")

    def open_link(self, url: str) -> None:
        opener = getattr(self.parent(), "open_url", None)
        if callable(opener):
            opener(QUrl(url))
        else:
            QDesktopServices.openUrl(QUrl(url))

    def _link(self, text: str, icon_name: str, url: str) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("variant", "ghost")
        button.setIcon(button_icon(icon_name))
        button.setIconSize(QSize(SIZE["icon"], SIZE["icon"]))
        button.setToolTip(url)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setProperty("url", url)
        button.clicked.connect(self._link_clicked)
        return button

    def _link_clicked(self) -> None:
        self.open_link(self.sender().property("url"))

    def _facts(self, title: str, facts: dict[str, str]) -> QWidget:
        box = QWidget()
        grid = QGridLayout(box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(GAP["medium"])
        grid.setVerticalSpacing(GAP["tight"])
        grid.setColumnMinimumWidth(0, SIZE["label_column"])
        grid.setColumnStretch(1, 1)
        heading = _label(title.upper(), "text3", "data")
        grid.addWidget(heading, 0, 0, 1, 2)
        grid.setRowMinimumHeight(0, SIZE["status"])
        for row, (key, value) in enumerate(facts.items(), start=1):
            grid.addWidget(_label(key, "text3"), row, 0)
            grid.addWidget(_label(value, "text2"), row, 1)
        grid.setRowStretch(len(facts) + 1, 1)
        return box

    def _front(self, atlas: Atlas) -> QWidget:
        current = app_version()
        self.name = _label(APP_NAME, role="title")
        self.tagline = _label(TAGLINE, "text2")
        self.tagline.setWordWrap(True)
        self.version = _label(f"Version {current}", "text3")
        self.test_tag = chip("Test version", "accent_text") if is_test_version(current) else None
        meta = QHBoxLayout()
        meta.setSpacing(GAP["small"])
        meta.addWidget(self.version)
        if self.test_tag is not None:
            meta.addWidget(self.test_tag)
        meta.addStretch(1)
        title = QVBoxLayout()
        title.setSpacing(GAP["tight"])
        title.addWidget(self.name)
        title.addWidget(self.tagline)
        title.addLayout(meta)
        brand = QHBoxLayout()
        brand.setSpacing(GAP["large"])
        brand.addWidget(KeyMark(SIZE["mark_about"]), 0, Qt.AlignmentFlag.AlignTop)
        brand.addLayout(title, 1)

        self.links = [self._link(*link) for link in LINKS]
        links = QHBoxLayout()
        links.setContentsMargins(SIZE["mark_about"] + GAP["large"] - GAP["small"], 0, 0, 0)
        links.setSpacing(GAP["tight"])
        for button in self.links:
            links.addWidget(button)
        links.addStretch(1)

        self.notes: list[QLabel] = []
        cards = []
        for text in (escape(DISCLAIMER), local_note(atlas)):
            if not text:
                continue
            card = Card()
            label = _label(text, "text2")
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.RichText)
            card.layout_.setContentsMargins(GAP["large"], GAP["medium"], GAP["large"],
                                            GAP["medium"])
            card.layout_.addWidget(label)
            self.notes.append(label)
            cards.append(card)

        name = str(atlas.metadata.get("name", ""))
        package = f"{name} {atlas.metadata.get('version', '')}".strip()
        self.app_facts = {"Version": current, "Licence": APP_LICENCE}
        self.facts = {"Atlas package": package, "Sources": str(len(atlas.sources))}
        reviewed, texts = atlas.review_counts()
        if texts:
            self.facts["Texts reviewed"] = f"{reviewed} of {texts}"
        if atlas.metadata.get("licence"):
            self.facts["Licence"] = str(atlas.metadata["licence"])
        facts = QHBoxLayout()
        facts.setSpacing(GAP["widest"])
        facts.addWidget(self._facts("App", self.app_facts), 1)
        facts.addWidget(self._facts("Atlas", {("Package" if k == "Atlas package" else k): v
                                              for k, v in self.facts.items()}), 1)

        self.credits = _label(BUILT_WITH, "text3", "secondary")
        self.credits.setWordWrap(True)
        front = QWidget()
        column = QVBoxLayout(front)
        column.setContentsMargins(GAP["large"], GAP["large"], GAP["large"], GAP["medium"])
        column.setSpacing(GAP["large"])
        column.addLayout(brand)
        column.addLayout(links)
        for card in cards:
            column.addWidget(card)
        column.addLayout(facts)
        column.addStretch(1)
        column.addWidget(self.credits)
        return front

    def _sources(self, atlas: Atlas) -> QWidget:
        head = QFrame()
        head.setProperty("tablehead", "true")
        head.setFixedHeight(SIZE["control"] + GAP["tight"])
        columns = QHBoxLayout(head)
        columns.setContentsMargins(GAP["medium"] + SIZE["border"], 0, GAP["medium"] + SIZE["border"], 0)
        columns.setSpacing(GAP["medium"])
        for text, stretch in (("Provides", 5), ("Authors", 4)):
            heading = ElidedLabel(text)
            set_tone(heading, "text3")
            set_role(heading, "secondary")
            columns.addWidget(heading, stretch)
        licence = _label("Licence", "text3", "secondary")
        licence.setFixedWidth(SIZE["tag_column"])
        columns.addWidget(licence)
        blank = QWidget()
        blank.setFixedWidth(SIZE["icon"])
        columns.addWidget(blank)
        self.head = head
        self.head_labels = [columns.itemAt(i).widget() for i in range(3)]

        self.rows = [SourceRow(source, source.id in atlas.local_only)
                     for source in atlas.sources.values()]
        body = QWidget()
        body.setProperty("sourcelist", "true")
        stack = QVBoxLayout(body)
        stack.setContentsMargins(0, GAP["tight"], 0, GAP["tight"])
        stack.setSpacing(0)
        for row in self.rows:
            stack.addWidget(row)
        stack.addStretch(1)
        self.scroll = QScrollArea()
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(body)
        self.scroll.verticalScrollBar().rangeChanged.connect(self._align_head)
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(GAP["small"], GAP["small"], GAP["small"], 0)
        column.setSpacing(0)
        column.addWidget(head)
        column.addWidget(self.scroll, 1)
        return page

    def _align_head(self, _low: int, high: int) -> None:
        bar = self.scroll.verticalScrollBar()
        extent = bar.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent, None, bar)
        side = GAP["medium"] + SIZE["border"]
        self.head.layout().setContentsMargins(side, 0, side + (extent if high > 0 else 0), 0)

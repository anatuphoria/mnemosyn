from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ..design.theme import set_role
from ..design.tokens import GAP

SEEN_KEY = "welcome/seen"
WIDTH = 440
PAGES = (
    (None, "Welcome to Mnemosyn",
     "A 3D atlas of the brain that you can turn, take apart and test yourself on. This short "
     "tour visits its five workspaces. The switch at the top right of the window moves between "
     "them, and this tour moves it for you."),
    ("Explore", "Explore: the brain in 3D",
     "Click any part to read what it does, what it connects to and what damage there causes. "
     "Drag to turn, scroll to zoom. F frames what you selected, I shows it alone, and Ctrl+F "
     "finds a structure by name."),
    ("Slices", "Slices: the brain as an atlas plate",
     "The same labels drawn on an MRI in three planes, the way scans and exams show the brain. "
     "Move the slider and the plane travels through the 3D brain with it."),
    ("Pathways", "Pathways: follow a route",
     "Pick a route, such as voluntary movement or pain, and walk it station by station with the "
     "arrow keys. Each step says what happens there and what a lesion there would do."),
    ("Lab", "Lab: change the body and watch it answer",
     "Remove a gland, give a drug or run a clinical test, and every hormone moves on a timeline "
     "beside its normal day. The Why panel explains each change as a chain of causes."),
    ("Lesion", "Lesion: from a lesion to the signs",
     "Place a stroke by its artery, paint one with a brush or pick a structure, and read the "
     "deficits that follow from every route it breaks."),
    ("Explore", "Test yourself, and know what to trust",
     "Press Q to start a quiz on names, places, route order or Lab outcomes; it brings each "
     "question back just before you would forget it. Every text says whether a specialist has "
     "reviewed it. Help, then Welcome tour shows this again."),
)


class WelcomeTour(QDialog):
    def __init__(self, window) -> None:
        super().__init__(window)
        self.window_ = window
        self.setWindowTitle("Welcome tour")
        self.setModal(False)
        self.setFixedWidth(WIDTH)
        actions = window.workspaces.actions
        self.pages = [page for page in PAGES
                      if page[0] is None or (page[0] in actions and actions[page[0]].isEnabled())]
        self.index = 0
        self.counter = QLabel()
        self.title = QLabel()
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setTextFormat(Qt.TextFormat.PlainText)
        self.title.setWordWrap(True)
        set_role(self.counter, "data")
        set_role(self.title, "heading")
        self.skip_button = QPushButton("Skip")
        self.skip_button.setProperty("variant", "ghost")
        self.back_button = QPushButton("Back")
        self.next_button = QPushButton("Next")
        self.next_button.setProperty("variant", "primary")
        self.next_button.setDefault(True)
        row = QHBoxLayout()
        row.setSpacing(GAP["small"])
        row.addWidget(self.skip_button)
        row.addStretch(1)
        row.addWidget(self.back_button)
        row.addWidget(self.next_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(GAP["wide"], GAP["large"], GAP["wide"], GAP["large"])
        layout.setSpacing(GAP["small"])
        layout.addWidget(self.counter)
        layout.addWidget(self.title)
        layout.addWidget(self.text)
        layout.addSpacing(GAP["medium"])
        layout.addLayout(row)
        self.skip_button.clicked.connect(self.reject)
        self.back_button.clicked.connect(lambda: self.go(self.index - 1))
        self.next_button.clicked.connect(self.forward)
        self.go(0)

    def go(self, index: int) -> None:
        self.index = max(0, min(index, len(self.pages) - 1))
        workspace, title, text = self.pages[self.index]
        last = self.index == len(self.pages) - 1
        self.counter.setText(f"{self.index + 1} of {len(self.pages)}")
        self.title.setText(title)
        self.text.setText(text)
        self.back_button.setEnabled(self.index > 0)
        self.next_button.setText("Done" if last else "Next")
        self.skip_button.setVisible(not last)
        if workspace is not None:
            self.window_.workspaces.switch(workspace)
        self.adjustSize()
        self.place()

    def forward(self) -> None:
        if self.index == len(self.pages) - 1:
            self.accept()
        else:
            self.go(self.index + 1)

    def place(self) -> None:
        frame = self.window_.frameGeometry()
        x = frame.center().x() - self.width() // 2
        y = frame.bottom() - self.height() - 72
        self.move(x, max(y, frame.top()))

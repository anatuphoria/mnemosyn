from __future__ import annotations

import faulthandler
import sys
import traceback
from datetime import datetime
from pathlib import Path

LOG_NAME = "errors.log"
CRASH_NAME = "crashes.log"
KEEP_BYTES = 200_000
MESSAGE = ("Something went wrong, but Mnemosyn is still running. If it keeps happening, restart "
           "it.\n\nThe details were saved to:\n{path}\n\nTo report it, choose Help, then "
           "Report a problem, and attach that file.")


def trim(path: Path, keep: int = KEEP_BYTES) -> None:
    try:
        if path.stat().st_size <= keep:
            return
        data = path.read_bytes()[-keep:]
        cut = data.find(b"\n")
        path.write_bytes(data[cut + 1:] if cut >= 0 else data)
    except OSError:
        return


def entry(version: str, kind, value, trace, now: datetime | None = None) -> str:
    stamp = (now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    text = "".join(traceback.format_exception(kind, value, trace))
    return f"--- {stamp} Mnemosyn {version}\n{text}\n"


class Reporter:
    def __init__(self, folder: Path, version: str, show=None) -> None:
        self.folder = Path(folder)
        self.path = self.folder / LOG_NAME
        self.version = version
        self.show = show
        self.shown = False
        self.previous = sys.excepthook
        self.crashes = None

    def write(self, kind, value, trace) -> bool:
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            trim(self.path)
            with self.path.open("a", encoding="utf-8") as log:
                log.write(entry(self.version, kind, value, trace))
        except OSError:
            return False
        return True

    def hook(self, kind, value, trace) -> None:
        if issubclass(kind, KeyboardInterrupt):
            self.previous(kind, value, trace)
            return
        saved = self.write(kind, value, trace)
        if sys.stderr is not None:
            self.previous(kind, value, trace)
        if saved and self.show is not None and not self.shown:
            self.shown = True
            self.show(MESSAGE.format(path=self.path))

    def install(self) -> None:
        sys.excepthook = self.hook
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            trim(self.folder / CRASH_NAME)
            self.crashes = (self.folder / CRASH_NAME).open("a", encoding="utf-8")
            faulthandler.enable(self.crashes)
        except OSError:
            self.crashes = None

    def remove(self) -> None:
        sys.excepthook = self.previous
        if self.crashes is not None:
            faulthandler.disable()
            self.crashes.close()
            self.crashes = None

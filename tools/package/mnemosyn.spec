import os
import sys
from pathlib import Path

root = Path(SPECPATH).parents[1]
analysis = Analysis(
    [str(Path(SPECPATH) / "launch.py")],
    pathex=[str(root)],
    datas=[(os.environ["MNEMOSYN_ATLAS"], "atlases/cns"),
           (os.environ["MNEMOSYN_VERSION_FILE"], ".")],
    excludes=["tkinter", "tools", "IPython", "jupyter", "notebook", "pytest"],
)
archive = PYZ(analysis.pure)
executable = EXE(archive, analysis.scripts, [], exclude_binaries=True, name="Mnemosyn",
                 console=False, icon=str(Path(SPECPATH) / "mnemosyn.ico"))
COLLECT(executable, analysis.binaries, analysis.datas, name="Mnemosyn")

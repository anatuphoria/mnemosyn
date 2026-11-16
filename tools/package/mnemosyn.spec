import os
import sys
from pathlib import Path

root = Path(SPECPATH).parents[1]
analysis = Analysis(
    [str(Path(SPECPATH) / "launch.py")],
    pathex=[str(root)],
    datas=[(os.environ["MNEMOSYN_ATLAS"], "atlases/cns"),
           (os.environ["MNEMOSYN_VERSION_FILE"], "."),
           (str(root / "cns_desktop" / "resources"), "cns_desktop/resources")],
    excludes=["tkinter", "tools", "IPython", "jupyter", "notebook", "pytest"],
)
archive = PYZ(analysis.pure)
mac = sys.platform == "darwin"
icon = str(Path(SPECPATH) / ("mnemosyn.icns" if mac else "mnemosyn.ico"))
executable = EXE(archive, analysis.scripts, [], exclude_binaries=True, name="Mnemosyn",
                 console=False, icon=icon)
collected = COLLECT(executable, analysis.binaries, analysis.datas, name="Mnemosyn")
if mac:
    version = Path(os.environ["MNEMOSYN_VERSION_FILE"]).read_text(encoding="utf-8").strip()
    BUNDLE(collected, name="Mnemosyn.app", icon=icon, bundle_identifier="cool.saeed.mnemosyn",
           version=version,
           info_plist={"NSHighResolutionCapable": True, "LSMinimumSystemVersion": "12.0",
                       "LSApplicationCategoryType": "public.app-category.education",
                       "NSHumanReadableCopyright": "GNU General Public License 3.0"})

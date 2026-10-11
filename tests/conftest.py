import importlib.util
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

collect_ignore = [] if importlib.util.find_spec("pyvistaqt") else ["test_desktop.py"]

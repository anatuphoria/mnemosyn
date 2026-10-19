import os
import sys

from . import ROOT, project_version, write_all


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    for path in write_all(ROOT, project_version()):
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())

import sys

from . import ROOT, project_version, write_all


def main() -> int:
    for path in write_all(ROOT, project_version()):
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())

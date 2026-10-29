import argparse
import os
import sys
from pathlib import Path

from . import ROOT, project_version, write_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.brand",
                                     description="Draw the logos, icon and badges")
    parser.add_argument("--gifs", nargs="?", const=ROOT / "dist" / "animated", type=Path,
                        help="also write looping GIFs of the animations (default dist/animated)")
    args = parser.parse_args(argv)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    for path in write_all(ROOT, project_version()):
        print(path.relative_to(ROOT))
    if args.gifs is not None:
        from .gif import write_gifs

        for path in write_gifs(args.gifs):
            print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

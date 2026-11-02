from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.handbook",
                                     description="Make the handbook's experiment files and shots")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("files", help="write the downloadable .mnemolab files")
    shots = commands.add_parser("shots", help="take the handbook screenshots from the app")
    shots.add_argument("--atlas", type=Path, required=True,
                       help="a shareable atlas package, for example build/atlas-shareable")
    shots.add_argument("--only", nargs="*", default=None, help="take only these shots")
    args = parser.parse_args(argv)
    if args.command == "files":
        from tools.handbook.experiments import source_models, write_files

        for path in write_files(source_models()):
            print(path)
        return 0
    from tools.handbook.shots import take

    for path in take(args.atlas, names=args.only):
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

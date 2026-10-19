from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.build_atlas.recipe import BuildError

from . import ROOT, PackageError, package


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.package",
                                     description="Package Mnemosyn for this system")
    parser.add_argument("--atlas", type=Path, default=ROOT / "atlases" / "cns")
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    parser.add_argument("--local", action="store_true",
                        help="package the local build for your own machines; never share it")
    parser.add_argument("--no-wrap", action="store_true",
                        help="stop after the bundled folder, without the installer or AppImage")
    args = parser.parse_args(argv)
    try:
        made = package(args.atlas, args.out, args.local, wrap=not args.no_wrap)
    except (PackageError, BuildError) as exc:
        print(f"packaging failed: {exc}", file=sys.stderr)
        return 1
    print(f"packaged {made}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

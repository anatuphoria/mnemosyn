from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .build import build
from .fetch import DEFAULT_CACHE
from .recipe import BuildError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.build_atlas",
                                     description="Build the CNS atlas package")
    parser.add_argument("--src", type=Path, default=Path("atlas_src"))
    parser.add_argument("--out", type=Path, default=Path("atlases/cns"))
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    args = parser.parse_args(argv)
    try:
        out = build(args.src, args.out, args.cache)
    except BuildError as exc:
        print("build failed:", file=sys.stderr)
        for problem in exc.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(f"built {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

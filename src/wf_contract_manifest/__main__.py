from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .generate import generate_manifest
from .io import (
    DEFAULT_MANIFEST_PATH,
    ManifestDriftError,
    check_manifest,
    write_manifest,
)
from .model import ManifestError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the checked workflow API contract manifest.")
    parser.add_argument("command", choices=("write", "check"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        manifest = generate_manifest()
        if args.command == "write":
            path = write_manifest(manifest, DEFAULT_MANIFEST_PATH)
            print(f"wrote {path}")
        else:
            check_manifest(manifest, DEFAULT_MANIFEST_PATH)
            print(f"checked {DEFAULT_MANIFEST_PATH}")
    except (ManifestError, ManifestDriftError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

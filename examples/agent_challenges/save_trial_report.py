"""Central CLI for saving agent challenge trial reports."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from .reports import main as reports_main
except ImportError:
    _project_root = Path(__file__).resolve().parents[2]
    if str(_project_root) not in sys.path:
        sys.path.insert(0, str(_project_root))
    from examples.agent_challenges.reports import main as reports_main


def main(argv: list[str] | None = None) -> int:
    return reports_main(argv)


if __name__ == "__main__":
    sys.exit(main())

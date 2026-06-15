from __future__ import annotations

import sys
from pathlib import Path

# Support direct execution as `python examples/.../save_trial_report.py`.
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.agent_challenges.browser_click_challenge.reports import (  # noqa: E402
    main,
    report_from_result,
    save_report,
)

__all__ = ["main", "report_from_result", "save_report"]


if __name__ == "__main__":
    raise SystemExit(main())

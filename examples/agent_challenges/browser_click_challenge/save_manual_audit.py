from __future__ import annotations

import sys
from pathlib import Path

# Support direct execution as `python examples/.../save_manual_audit.py`.
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.agent_challenges.audit import (  # noqa: E402
    audit_from_result,
    main,
    save_manual_audit,
)

__all__ = ["audit_from_result", "main", "save_manual_audit"]


if __name__ == "__main__":
    raise SystemExit(main())

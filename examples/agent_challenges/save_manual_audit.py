"""Central CLI for saving agent challenge manual audits.

Routes to V1 or V2 audit logic based on the harness version in the result file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from .audit import main as audit_main
    from .audit import save_v2_manual_audit
except ImportError:
    _project_root = Path(__file__).resolve().parents[2]
    if str(_project_root) not in sys.path:
        sys.path.insert(0, str(_project_root))
    from examples.agent_challenges.audit import main as audit_main
    from examples.agent_challenges.audit import save_v2_manual_audit


def _is_v2_result(result_path: Path) -> bool:
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
        return isinstance(result, dict) and result.get("harness_version") == "v2"
    except json.JSONDecodeError, OSError:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-result", type=Path, required=True)
    parser.add_argument("--from-report", type=Path, default=None)
    parser.add_argument("--manual-classification", required=True)
    parser.add_argument("--auditor", default="human")
    parser.add_argument("--audited-at", default=None)
    parser.add_argument("--set-read", action="append", default=[])
    parser.add_argument("--set-evidence", action="append", default=[])
    parser.add_argument("--correction", action="append", default=[])
    parser.add_argument("--notes", default="")
    parser.add_argument("--output-name", default="manual-audit.yaml")
    args = parser.parse_args(argv)

    result_path = args.from_result

    if _is_v2_result(result_path):
        if args.from_report is not None:
            parser.error("--from-report is not supported for V2 results")
        try:
            read_overrides = dict(
                _parse_bool_assignment(item) for item in args.set_read
            )
            evidence_overrides = dict(
                _parse_value_assignment(item) for item in args.set_evidence
            )
            paths = save_v2_manual_audit(
                result_path,
                official_outcome=args.manual_classification,
                auditor=args.auditor,
                audited_at=args.audited_at,
                read_overrides=read_overrides,
                evidence_overrides=evidence_overrides,
                corrections=list(args.correction),
                notes=args.notes,
            )
            print(
                json.dumps(
                    {
                        "audit": paths.audit.as_posix(),
                        "markdown": paths.markdown.as_posix(),
                        "machine": paths.machine.as_posix(),
                        "results_markdown": (
                            paths.results_markdown.as_posix()
                            if paths.results_markdown is not None
                            else None
                        ),
                    }
                )
            )
            return 0
        except ValueError as exc:
            parser.error(str(exc))

    return audit_main(argv)


def _parse_bool_assignment(value: str) -> tuple[str, bool]:
    key, separator, raw = value.partition("=")
    if separator != "=" or not key:
        raise ValueError("expected KEY=true or KEY=false")
    lowered = raw.lower()
    if lowered == "true":
        return key, True
    if lowered == "false":
        return key, False
    raise ValueError("boolean override value must be true or false")


def _parse_value_assignment(value: str) -> tuple[str, object]:
    key, separator, raw = value.partition("=")
    if separator != "=" or not key:
        raise ValueError("expected KEY=VALUE")
    lowered = raw.lower()
    if lowered == "true":
        return key, True
    if lowered == "false":
        return key, False
    try:
        return key, int(raw)
    except ValueError:
        return key, raw


if __name__ == "__main__":
    sys.exit(main())

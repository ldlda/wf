from __future__ import annotations

import argparse
import sys
from pathlib import Path

THESIS_DIR = Path(__file__).resolve().parent
ROOT = THESIS_DIR.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.agent_challenges.evaluation import (  # noqa: E402
    load_evaluation_cohort,
    render_evaluation_figures,
    render_evaluation_markdown,
)


def _write_text_atomic(path: Path, content: str) -> None:
    """Replace generated Markdown without exposing a partially written file."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    temporary.replace(path)


def generate(*, manifest_path: Path, output_dir: Path) -> tuple[Path, ...]:
    """Generate the audited Markdown rollup plus SVG/PDF figure pairs."""
    cohort = load_evaluation_cohort(manifest_path, repository_root=ROOT)
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "agent-challenge-results.md"
    _write_text_atomic(markdown_path, render_evaluation_markdown(cohort))
    figure_paths = render_evaluation_figures(cohort, output_dir / "figures")
    return (markdown_path, *figure_paths)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Regenerate thesis agent-challenge results and figures."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=THESIS_DIR / "agent-challenge-cohort.json",
        help="Explicit audited cohort manifest.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=THESIS_DIR,
        help="Directory receiving Markdown and figures/ outputs.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    output_dir = args.output_dir.resolve()
    for path in generate(manifest_path=args.manifest.resolve(), output_dir=output_dir):
        resolved = path.resolve()
        try:
            display_path = resolved.relative_to(ROOT)
        except ValueError:
            try:
                display_path = resolved.relative_to(output_dir)
            except ValueError:
                display_path = resolved
        print(display_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

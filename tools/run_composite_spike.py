"""Generate deterministic development composites and material-decision evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from interaction_studio_api.preflight.composite import run_composite_spike


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--landmarks", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = run_composite_spike(
        args.manifest,
        args.manifest.parent.parent,
        args.landmarks,
        args.output_dir,
    )
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 1 if any(not item["residual"]["within_gate"] for item in report["outputs"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())

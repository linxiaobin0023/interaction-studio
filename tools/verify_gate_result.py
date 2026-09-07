"""Verify every local evidence hash referenced by a gate result."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(result_path: Path, project_root: Path) -> list[str]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    errors = []
    for item in result.get("evidence", []):
        relative = PurePosixPath(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(f"unsafe evidence path: {relative}")
            continue
        path = (project_root / Path(*relative.parts)).resolve()
        try:
            path.relative_to(project_root.resolve())
        except ValueError:
            errors.append(f"evidence escapes project root: {relative}")
            continue
        if not path.is_file():
            errors.append(f"missing evidence: {relative}")
        elif sha256_file(path) != item["sha256"]:
            errors.append(f"evidence hash mismatch: {relative}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    args = parser.parse_args()
    errors = verify(args.result, args.project_root.resolve())
    print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

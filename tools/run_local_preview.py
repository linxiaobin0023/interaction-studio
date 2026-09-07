"""Export a model-free Development preview bundle without modifying sealed inputs."""

import argparse
import json
from pathlib import Path

from interaction_studio_api.domain.local_preview import (
    PreviewRequest,
    bundle_bytes,
    render_preview,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--case-id", default="DEV_MOUTH_001")
    parser.add_argument("--request", type=Path, help="Optional complete PreviewRequest JSON")
    parser.add_argument("--output-dir", type=Path, default=Path(".cache/local-previews"))
    args = parser.parse_args()
    request = (PreviewRequest.model_validate_json(args.request.read_bytes()) if args.request
               else PreviewRequest(case_id=args.case_id))
    project = args.project_root.resolve()
    destination = args.output_dir.resolve()
    # CLI exports must not introduce files into versioned/sealed source directories.
    for name in ("datasets", "assets", "workers"):
        if destination == project / name or (project / name) in destination.parents:
            parser.error("output directory must be outside input/source asset directories")
    manifest, files = render_preview(project, request)
    destination = destination / manifest["preview_id"]
    destination.mkdir(parents=True, exist_ok=True)
    exports = files | {"bundle.zip": bundle_bytes(files)}
    for relative, data in exports.items():
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != data:
                raise ValueError("existing preview has changed; refusing to overwrite")
        else:
            with path.open("xb") as stream:
                stream.write(data)
    print(json.dumps({"status": manifest["status"], "preview_id": manifest["preview_id"],
                      "directory": str(destination), "provider_execution_performed": False},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

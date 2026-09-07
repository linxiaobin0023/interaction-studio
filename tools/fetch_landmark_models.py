"""Fetch pinned MediaPipe model bundles and verify their SHA256 digests."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import urllib.request
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_models(manifest_path: Path, output_dir: Path) -> list[dict]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for model in manifest["models"]:
        destination = output_dir / model["filename"]
        if destination.is_file() and sha256_file(destination) == model["sha256"]:
            results.append({"model_id": model["model_id"], "status": "CACHED"})
            continue

        with tempfile.NamedTemporaryFile(dir=output_dir, delete=False) as temp:
            temp_path = Path(temp.name)
        try:
            with (
                urllib.request.urlopen(model["source"], timeout=60) as response,
                temp_path.open("wb") as output,
            ):
                shutil.copyfileobj(response, output)
            actual = sha256_file(temp_path)
            if actual != model["sha256"]:
                raise ValueError(
                    f"{model['model_id']}: SHA256 mismatch; expected {model['sha256']}, got {actual}"
                )
            temp_path.replace(destination)
            results.append({"model_id": model["model_id"], "status": "FETCHED"})
        finally:
            temp_path.unlink(missing_ok=True)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("workers/landmarks/models.json"),
    )
    parser.add_argument("--output", type=Path, default=Path(".cache/landmark-models"))
    args = parser.parse_args()
    print(json.dumps(fetch_models(args.manifest, args.output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

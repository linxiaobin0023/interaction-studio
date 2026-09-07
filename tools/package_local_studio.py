"""Create a source/material delivery archive without local credentials or runtime data."""

import argparse
import hashlib
import io
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCLUDE = ["apps", "assets", "datasets", "docs", "tools", "workers", "config", ".github",
           "mock_assets", "interaction_studio_prototype",
           "README.md", "Makefile", "compose.yaml", "alembic.ini", ".env.example", ".gitignore",
           ".dockerignore", "人物-奶嘴交互一致性优化_开发计划.md",
           "人物-奶嘴交互一致性优化_正式实施冻结方案.md"]
EXCLUDE = {".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", "dist",
           ".cache", ".git", "data", "tmp"}


def package(destination: Path):
    paths = []
    for source in INCLUDE:
        path = ROOT / source
        paths.extend(path.rglob("*") if path.is_dir() else [path])
    paths = sorted({p for p in paths if p.is_file() and not p.is_symlink()
                    and not EXCLUDE.intersection(p.relative_to(ROOT).parts)
                    and p.name != ".env" and not p.name.endswith((".pyc", ".tsbuildinfo", ".log"))})
    records = []
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as output, tarfile.open(fileobj=output, mode="w:gz") as archive:
        for path in paths:
            relative = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            records.append({"path": relative, "bytes": len(data),
                            "sha256": hashlib.sha256(data).hexdigest()})
            info = tarfile.TarInfo(relative)
            info.size, info.mode = len(data), 0o644
            archive.addfile(info, io.BytesIO(data))
        manifest = {"release": "local-development-v1", "formal_eligible": False,
                    "model_integration": "DEFERRED_BY_USER", "files": records}
        data = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
        info = tarfile.TarInfo("delivery-manifest.json")
        info.size, info.mode = len(data), 0o644
        archive.addfile(info, io.BytesIO(data))
    with destination.open("rb") as file:
        digest = hashlib.file_digest(file, "sha256").hexdigest()
    destination.with_suffix(destination.suffix + ".sha256").write_text(
        f"{digest}  {destination.name}\n")
    return {"package": str(destination), "files": len(records), "sha256": digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(package(args.output.resolve()), indent=2))


if __name__ == "__main__":
    main()

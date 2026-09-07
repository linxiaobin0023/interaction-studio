"""Verify an extracted delivery in isolated Compose resources and allocated local ports."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    project = "studio-cleanroom-" + uuid4().hex[:12]
    with tempfile.TemporaryDirectory(prefix=project) as directory:
        root = Path(directory)
        with tarfile.open(args.package, "r:gz") as archive:
            for member in archive.getmembers():
                path = PurePosixPath(member.name)
                if not member.isfile() or path.is_absolute() or ".." in path.parts:
                    raise ValueError("unsafe delivery package")
            archive.extractall(root, filter="data")
        manifest = json.loads((root / "delivery-manifest.json").read_text())
        for ref in manifest["files"]:
            data = (root / ref["path"]).read_bytes()
            assert len(data) == ref["bytes"]
            assert hashlib.sha256(data).hexdigest() == ref["sha256"]
        assert not (root / ".env").exists() and not (root / "data").exists()
        environment = dict(os.environ) | {
            "COMPOSE_PROJECT_NAME": project, "APP_PORT": "0", "MINIO_API_PORT": "0",
            "MINIO_CONSOLE_PORT": "0", "APP_BIND_HOST": "127.0.0.1",
            "AUTH_MODE": "authenticated", "EXTERNAL_INFERENCE_ENABLED": "false",
        }
        compose = ["docker", "compose", "-p", project]

        def run(command, **kwargs):
            return subprocess.run(command, cwd=root, env=environment, check=True, **kwargs)

        try:
            run([sys.executable, "tools/install_local_studio.py", "--skip-build"])
            mapped = run(compose + ["port", "api", "8000"], text=True,
                         stdout=subprocess.PIPE).stdout.strip()
            base = "http://" + mapped
            cookie = ""

            def call(path, data=None):
                request = urllib.request.Request(base + path,
                    data=json.dumps(data).encode() if data is not None else None,
                    headers={"Content-Type": "application/json", "X-Studio-Request": "1",
                             "Cookie": cookie})
                return urllib.request.urlopen(request, timeout=30)

            for _ in range(100):
                try:
                    with call("/health/live"):
                        break
                except (urllib.error.URLError, ConnectionResetError):
                    time.sleep(.2)
            else:
                raise RuntimeError("clean-room API did not start")
            credentials = (root / "data/local-delivery/initial-login.txt").read_text().splitlines()
            password = next(line.removeprefix("Password: ") for line in credentials
                            if line.startswith("Password: "))
            with call("/api/v1/auth/login", {"username": "studio_owner", "password": password}) as r:
                cookie = r.headers["Set-Cookie"].split(";", 1)[0]
            with call("/api/v1/development/catalog") as r:
                assert len(json.load(r)["cases"]) == 30
            jobs = "/api/v1/development/studio/jobs"
            with call(jobs, {"idempotency_key": str(uuid4()),
                             "parameters": {"case_id": "DEV_HAND_001"}}) as r:
                job_id = json.load(r)["id"]
            for _ in range(100):
                with call(jobs + "/" + job_id) as r:
                    detail = json.load(r)
                if detail["state"] in {"SUCCEEDED", "FAILED"}:
                    break
                time.sleep(.2)
            assert detail["state"] == "SUCCEEDED", detail["error_code"]
            with call(jobs + "/" + job_id + "/output") as r:
                assert hashlib.sha256(r.read()).hexdigest() == detail["output_sha256"]
            with call(jobs + "/" + job_id + "/evidence") as r:
                assert r.status == 200
            report = {"scope": "LOCAL_DEVELOPMENT_ONLY", "isolated_project": project,
                      "source_hashes_verified": len(manifest["files"]), "fresh_volumes": True,
                      "fresh_accounts": True, "catalog_cases": 30,
                      "separate_worker_succeeded": True, "result_hash_verified": True,
                      "provider_execution_performed": False, "formal_eligible": False,
                      "browser_acceptance_performed": False}
        finally:
            run(compose + ["down", "-v", "--remove-orphans"])
        report["temporary_resources_removed"] = True
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        print("Isolated local installation and processing passed; temporary resources removed.")


if __name__ == "__main__":
    main()

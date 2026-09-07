"""Portable local evidence export and offline verification, explicitly not WORM."""

import hashlib
import io
import json
import zipfile

from .local_preview import PreviewProblem, bundle_bytes
from .studio import hash_json
from .studio_jobs import DIMENSIONS, get_job, job_dict, reviews, verified_output


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def export_evidence(session, job_id: str) -> bytes:
    job = get_job(session, job_id, lock=True)
    output = verified_output(session, job)
    records = reviews(session, job)
    files = {"output.zip": output.bundle, "job.json": encoded(job_dict(job)),
             "reviews.json": encoded(records)}
    manifest = {"format": "studio-development-evidence-v1", "scope": "LOCAL_DEVELOPMENT_ONLY",
                "job_id": job.id, "output_sha256": output.sha256, "review_count": len(records),
                "review_head": records[-1]["content_sha256"] if records else None,
                "formal_eligible": False, "object_lock_verified": False,
                "source_assets_included": False,
                "files": [{"path": name, "bytes": len(data),
                           "sha256": hashlib.sha256(data).hexdigest()}
                          for name, data in sorted(files.items())]}
    files["evidence-manifest.json"] = encoded(manifest)
    result = bundle_bytes(files)
    verify_evidence(result)
    return result


def verify_evidence(data: bytes) -> dict:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if set(archive.namelist()) != {
                "output.zip", "job.json", "reviews.json", "evidence-manifest.json",
            } or len(archive.namelist()) != 4:
                raise ValueError("unexpected entries")
            if sum(i.file_size for i in archive.infolist()) > 40 * 1024 * 1024:
                raise ValueError("evidence too large")
            manifest = json.loads(archive.read("evidence-manifest.json"))
            if (manifest["format"] != "studio-development-evidence-v1"
                    or manifest["scope"] != "LOCAL_DEVELOPMENT_ONLY"
                    or manifest["formal_eligible"] is not False
                    or manifest["object_lock_verified"] is not False):
                raise ValueError("invalid scope")
            expected = {"output.zip", "job.json", "reviews.json"}
            if ({ref["path"] for ref in manifest["files"]} != expected
                    or len(manifest["files"]) != 3):
                raise ValueError("missing references")
            for ref in manifest["files"]:
                content = archive.read(ref["path"])
                if (len(content) != ref["bytes"]
                        or hashlib.sha256(content).hexdigest() != ref["sha256"]):
                    raise ValueError("file mismatch")
            job = json.loads(archive.read("job.json"))
            records = json.loads(archive.read("reviews.json"))
            output_bytes = archive.read("output.zip")
        if (job["state"] != "SUCCEEDED" or job["id"] != manifest["job_id"]
                or job["output_sha256"] != manifest["output_sha256"]
                or hashlib.sha256(output_bytes).hexdigest() != job["output_sha256"]
                or job["request_hash"] != hash_json({"parameters": job["parameters"],
                                                     "sources": job["sources"]})):
            raise ValueError("job binding mismatch")
        with zipfile.ZipFile(io.BytesIO(output_bytes)) as output:
            if sum(i.file_size for i in output.infolist()) > 128 * 1024 * 1024:
                raise ValueError("output too large")
            result = json.loads(output.read("manifest.json"))
            if result["sources"] != job["sources"] or result["request"] != job["parameters"]:
                raise ValueError("source binding mismatch")
            for ref in result["artifacts"]:
                content = output.read(ref["path"])
                if (len(content) != ref["bytes"]
                        or hashlib.sha256(content).hexdigest() != ref["sha256"]):
                    raise ValueError("output artifact mismatch")
        previous = None
        for version, record in enumerate(records, 1):
            payload = {k: v for k, v in record.items() if k not in {"id", "content_sha256"}}
            if (record["version"] != version or record["job_id"] != job["id"]
                    or record["output_sha256"] != job["output_sha256"]
                    or record["previous_hash"] != previous
                    or hash_json(payload) != record["content_sha256"]
                    or set(record["dimensions"]) != set(DIMENSIONS)):
                raise ValueError("review chain mismatch")
            labels = record["dimensions"].values()
            if any(d["decision"] not in {"PASS", "FAIL"}
                   or d["decision"] == "FAIL" and not d["reason"].strip() for d in labels):
                raise ValueError("invalid review")
            decision = "PASS" if all(d["decision"] == "PASS" for d in labels) else "FAIL"
            if record["decision"] != decision:
                raise ValueError("incorrect verdict")
            previous = record["content_sha256"]
        if len(records) != manifest["review_count"] or previous != manifest["review_head"]:
            raise ValueError("review head mismatch")
        return {"valid": True, "scope": "LOCAL_DEVELOPMENT_ONLY", "job_id": job["id"],
                "review_count": len(records), "formal_eligible": False,
                "object_lock_verified": False}
    except (KeyError, ValueError, TypeError, zipfile.BadZipFile, OSError) as exc:
        raise PreviewProblem("EVIDENCE_INTEGRITY_FAILED", 503) from exc

"""Encrypted local backup and isolated restore drill; never overwrite the live database."""

import argparse
import hashlib
import hmac
import io
import json
import os
import secrets
import shutil
import subprocess
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from uuid import uuid4

from interaction_studio_api.config import get_settings
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ["datasets/development", "datasets/validation", "datasets/registry",
          "assets/production/character", "assets/production/product_master",
          "workers/landmarks/models.json"]
CHECK = r'''
import json, pathlib, secrets, subprocess, sys, time, urllib.request, urllib.error
from datetime import UTC, datetime, timedelta
from sqlalchemy import delete, inspect, select
from interaction_studio_api.auth import create_account, token_hash
from interaction_studio_api.db import make_session_factory
from interaction_studio_api.domain.studio import load_draft, list_templates
from interaction_studio_api.domain.dataset_releases import read_release
from interaction_studio_api.domain.studio_evidence import export_evidence, verify_evidence
from interaction_studio_api.domain.studio_jobs import reviews, verified_output
from interaction_studio_api.models import (StudioDraft, StudioJob, StudioUser, StudioSession,
                                            StudioSecurityEvent)
factory=make_session_factory()
with factory() as session:
    counts={name:session.connection().exec_driver_sql('SELECT COUNT(*) FROM "'+name+'"').scalar()
            for name in inspect(session.bind).get_table_names()}
    for case_id in session.scalars(select(StudioDraft.case_id)):
        assert load_draft(session,pathlib.Path('/app/artifacts'),case_id)['history_verified']
    list_templates(session)
    for job in session.scalars(select(StudioJob)):
        if job.state=='SUCCEEDED':
            verified_output(session,job)
            assert verify_evidence(export_evidence(session,job.id))['valid']
        reviews(session,job)
    for user in session.scalars(select(StudioUser)):
        assert not {'ADMIN','GATE_SIGNER'} <= set(user.roles)
    for dataset in ['development','validation']:
        assert read_release(pathlib.Path('/app/artifacts'),dataset).seal_verified
with factory.begin() as session:
    probe=create_account(session,'restore_probe_'+secrets.token_hex(4),secrets.token_hex(16),
                         ['AUDITOR'],'RESTORE_DRILL')
    token=secrets.token_hex(32)
    session.add(StudioSession(token_hash=token_hash(token),user_id=probe.id,
                              expires_at=datetime.now(UTC)+timedelta(minutes=5)))
server=subprocess.Popen([sys.executable,'-m','uvicorn','interaction_studio_api.main:app',
                         '--host','127.0.0.1','--port','8000','--log-level','error'],
                         stdout=subprocess.DEVNULL)
def call(path,body=None,cookie=False):
    headers={'Content-Type':'application/json','X-Studio-Request':'1'}
    if cookie: headers['Cookie']='studio_session='+token
    request=urllib.request.Request('http://127.0.0.1:8000'+path,headers=headers,
                                   data=json.dumps(body).encode() if body else None)
    return urllib.request.urlopen(request,timeout=10)
try:
    for _ in range(100):
        try:
            with call('/health/live'): break
        except urllib.error.URLError: time.sleep(.1)
    else: raise RuntimeError('restore API did not start')
    try:
        call('/api/v1/development/catalog')
        raise AssertionError('restored API accepted anonymous access')
    except urllib.error.HTTPError as exc: assert exc.code==401
    with call('/api/v1/auth/me',cookie=True) as response:
        assert json.load(response)['roles']==['AUDITOR']
    try:
        call('/api/v1/development/previews',{'case_id':'DEV_HAND_001'},cookie=True)
        raise AssertionError('restored API accepted unauthorized write')
    except urllib.error.HTTPError as exc: assert exc.code==403
finally:
    server.terminate()
    server.wait(timeout=10)
with factory.begin() as session:
    session.execute(delete(StudioSession).where(StudioSession.user_id==probe.id))
    session.execute(delete(StudioSecurityEvent).where(StudioSecurityEvent.subject==probe.username))
    session.execute(delete(StudioUser).where(StudioUser.id==probe.id))
print(json.dumps({'counts':counts,'drafts_templates_verified':True,
                  'outputs_reviews_replayed':True,'account_roles_verified':True,
                  'restored_seals_verified':True,'restored_http_permission_checks':True}))
'''


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def run(command, **kwargs):
    return subprocess.run(command, check=True, cwd=ROOT, **kwargs)


def key_bytes(path):
    if path.stat().st_mode & 0o077:
        raise ValueError("backup key must be accessible only to its owner (chmod 600)")
    value = path.read_bytes().strip()
    if len(value) != 64:
        raise ValueError("expected a generated 256-bit hexadecimal backup key")
    bytes.fromhex(value.decode())
    return value


def crypt(data: bytes, key: bytes, decrypt=False) -> bytes:
    # A private FD keeps the key out of process arguments, environment and logs.
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, key + b"\n")
        os.close(write_fd)
        write_fd = -1
        command = ["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "200000",
                   "-pass", f"fd:{read_fd}"]
        if decrypt:
            command.append("-d")
        return run(command, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                   pass_fds=(read_fd,)).stdout
    finally:
        os.close(read_fd)
        if write_fd != -1:
            os.close(write_fd)


def mac(key, manifest):
    auth_key = hmac.digest(key, b"interaction-studio-backup-authentication-v1", "sha256")
    return hmac.new(auth_key, canonical(manifest), hashlib.sha256).hexdigest()


def create_backup(output: Path, key_path: Path, database_url: str | None = None) -> dict:
    key = key_bytes(key_path)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    configured = make_url(database_url or get_settings().database_url)
    database = configured.database or "interaction_studio"
    user = configured.username or "interaction_studio"
    dump = run(["docker", "compose", "exec", "-T", "postgres", "pg_dump", "-U", user,
                "-Fc", "--no-owner", "--no-acl", database], stdout=subprocess.PIPE).stdout
    stream = io.BytesIO()
    inputs = []
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for source in INPUTS:
            path = ROOT / source
            paths = sorted(path.rglob("*")) if path.is_dir() else [path]
            for item in paths:
                if item.is_symlink():
                    raise ValueError("input archives do not support symlinks")
                if not item.is_file():
                    continue
                relative = item.relative_to(ROOT).as_posix()
                data = item.read_bytes()
                info = tarfile.TarInfo(relative)
                info.size, info.mode = len(data), 0o600
                archive.addfile(info, io.BytesIO(data))
                inputs.append({"path": relative, "sha256": hashlib.sha256(data).hexdigest()})
    files = []
    for name, content in [("database.dump.enc", dump), ("inputs.tar.gz.enc", stream.getvalue())]:
        encrypted = crypt(content, key)
        target = output / name
        with target.open("xb") as file:
            os.chmod(target, 0o600)
            file.write(encrypted)
        files.append({"path": name, "bytes": len(encrypted),
                      "sha256": hashlib.sha256(encrypted).hexdigest()})
    manifest = {"format": "studio-encrypted-backup-v1", "scope": "LOCAL_DEVELOPMENT_ONLY",
                "created_at": datetime.now(UTC).isoformat(), "database": database,
                "encryption": "AES-256-CBC / PBKDF2-SHA256-200000 / encrypt-then-HMAC-SHA256",
                "files": files, "inputs": inputs, "formal_dr_passed": False}
    envelope = {"manifest": manifest, "hmac_sha256": mac(key, manifest)}
    (output / "backup.json").write_text(json.dumps(envelope, indent=2) + "\n")
    os.chmod(output / "backup.json", 0o600)
    return {"backup": str(output), "encrypted": True, "input_files": len(inputs)}


def decrypt_backup(backup, key_path):
    key = key_bytes(key_path)
    envelope = json.loads((backup / "backup.json").read_text())
    manifest = envelope["manifest"]
    if (manifest["format"] != "studio-encrypted-backup-v1"
            or not hmac.compare_digest(mac(key, manifest), envelope["hmac_sha256"])):
        raise ValueError("backup authentication failed")
    if {ref["path"] for ref in manifest["files"]} != {"database.dump.enc", "inputs.tar.gz.enc"}:
        raise ValueError("unexpected backup files")
    decrypted = {}
    for ref in manifest["files"]:
        data = (backup / ref["path"]).read_bytes()
        if len(data) != ref["bytes"] or hashlib.sha256(data).hexdigest() != ref["sha256"]:
            raise ValueError("encrypted backup integrity failed")
        decrypted[ref["path"]] = crypt(data, key, decrypt=True)
    return manifest, decrypted


def restore_drill(backup: Path, key_path: Path, *, keep=False):
    manifest, decrypted = decrypt_backup(backup, key_path)
    configured = make_url(get_settings().database_url)
    user = configured.username or "interaction_studio"
    database = "studio_restore_" + uuid4().hex[:12]
    pg = ["docker", "compose", "exec", "-T", "postgres"]
    completed = False
    # Assets are recovered and hash-checked before database creation.
    with tempfile.TemporaryDirectory(prefix="studio-restore-") as directory:
        root = Path(directory)
        with tarfile.open(fileobj=io.BytesIO(decrypted["inputs.tar.gz.enc"]), mode="r:gz") as archive:
            members = archive.getmembers()
            allowed = {ref["path"] for ref in manifest["inputs"]}
            if {m.name for m in members} != allowed or len(members) != len(allowed):
                raise ValueError("input inventory mismatch")
            for member in members:
                path = PurePosixPath(member.name)
                if (not member.isfile() or path.is_absolute() or ".." in path.parts
                        or member.size > 128 * 1024 * 1024):
                    raise ValueError("unsafe backup entry")
            archive.extractall(root, filter="data")
        for ref in manifest["inputs"]:
            if hashlib.sha256((root / ref["path"]).read_bytes()).hexdigest() != ref["sha256"]:
                raise ValueError("restored asset hash mismatch")
        # Nonroot API containers require traversal/read access to this short-lived fixture.
        os.chmod(root, 0o755)
        for item in root.rglob("*"):
            os.chmod(item, 0o755 if item.is_dir() else 0o644)
        run(pg + ["createdb", "-U", user, database])
        try:
            run(pg + ["pg_restore", "-U", user, "-d", database, "--no-owner", "--no-acl",
                      "--exit-on-error"], input=decrypted["database.dump.enc"])
            environment = dict(os.environ)
            environment["STUDIO_RESTORE_DATABASE_URL"] = configured.set(
                host="postgres", port=5432, database=database).render_as_string(hide_password=False)
            command = ["docker", "compose", "run", "--rm", "--no-deps", "-T", "--entrypoint", "sh",
                       "-e", "STUDIO_RESTORE_DATABASE_URL", "-v", f"{root}:/restore:ro", "api", "-c",
                       'export DATABASE_URL="$STUDIO_RESTORE_DATABASE_URL"; exec python -']
            checked = run(command, input=CHECK.replace("/app/artifacts", "/restore"), text=True,
                          stdout=subprocess.PIPE, env=environment)
            report = json.loads(checked.stdout)
            report.update({"restored_input_files": len(manifest["inputs"]),
                           "backup_authenticated": True, "live_database_modified": False,
                           "formal_dr_passed": False})
            if keep:
                recovered = ROOT / "data/recoveries" / database
                recovered.mkdir(parents=True, exist_ok=False, mode=0o700)
                shutil.copytree(root, recovered / "assets")
                env_path = recovered / ".env.recovery"
                with env_path.open("x") as file:
                    os.chmod(env_path, 0o600)
                    file.write("DATABASE_URL=" + environment["STUDIO_RESTORE_DATABASE_URL"] + "\n")
                report.update({"recovered_database": database,
                               "recovery_directory": str(recovered),
                               "live_database_switched": False})
            completed = True
            return report
        finally:
            if not keep or not completed:
                run(pg + ["dropdb", "-U", user, database])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["keygen", "backup", "verify", "drill", "recover"])
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--directory", type=Path)
    args = parser.parse_args()
    if args.action == "keygen":
        args.key_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with args.key_file.open("xb") as file:
            os.chmod(args.key_file, 0o600)
            file.write(secrets.token_hex(32).encode() + b"\n")
        print("Backup key created; store it separately from the encrypted backup.")
        return
    if not args.directory:
        parser.error("--directory is required")
    if args.action == "backup":
        result = create_backup(args.directory.resolve(), args.key_file)
    elif args.action in {"drill", "recover"}:
        result = restore_drill(args.directory.resolve(), args.key_file, keep=args.action == "recover")
    else:
        manifest, _ = decrypt_backup(args.directory.resolve(), args.key_file)
        result = {"valid": True, "created_at": manifest["created_at"], "formal_dr_passed": False}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

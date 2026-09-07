import importlib.util
import json
from pathlib import Path

import pytest

path = Path(__file__).parents[3] / "tools/studio_backup.py"
spec = importlib.util.spec_from_file_location("studio_backup", path)
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def test_encryption_authentication_and_tampering(tmp_path):
    key = b"a" * 64
    content = b"database contains private accounts and audit records"
    encrypted = backup.crypt(content, key)
    assert content not in encrypted
    assert backup.crypt(encrypted, key, decrypt=True) == content
    key_file = tmp_path / "key"
    key_file.write_bytes(key)
    key_file.chmod(0o600)
    files = []
    for name in ["database.dump.enc", "inputs.tar.gz.enc"]:
        (tmp_path / name).write_bytes(encrypted)
        files.append({"path": name, "bytes": len(encrypted),
                      "sha256": backup.hashlib.sha256(encrypted).hexdigest()})
    manifest = {"format": "studio-encrypted-backup-v1", "files": files}
    envelope = {"manifest": manifest, "hmac_sha256": backup.mac(key, manifest)}
    (tmp_path / "backup.json").write_text(json.dumps(envelope))
    assert backup.decrypt_backup(tmp_path, key_file)[1]["database.dump.enc"] == content
    (tmp_path / "database.dump.enc").write_bytes(encrypted[:-1] + b"x")
    with pytest.raises(ValueError, match="integrity"):
        backup.decrypt_backup(tmp_path, key_file)
    envelope["manifest"]["files"] = []
    (tmp_path / "backup.json").write_text(json.dumps(envelope))
    with pytest.raises(ValueError, match="authentication"):
        backup.decrypt_backup(tmp_path, key_file)
    key_file.chmod(0o644)
    with pytest.raises(ValueError, match="owner"):
        backup.key_bytes(key_file)

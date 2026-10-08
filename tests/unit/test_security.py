from pathlib import Path

import pytest

from app.security.crypto import CryptoVault, hash_password, verify_password
from app.security.paths import is_safe_task_id, safe_under
from app.utils.exceptions import ValidationError
from app.utils.file_manager import ROOT


def test_roundtrip_text():
    vault = CryptoVault("unit-test-master-key-framegenius")
    token = vault.encrypt_text("secret-api-key")
    assert token != "secret-api-key"
    assert vault.decrypt_text(token) == "secret-api-key"


def test_db_blob_roundtrip():
    vault = CryptoVault("unit-test-master-key-framegenius")
    blob = vault.encrypt_db(b"sqlite-bytes")
    assert blob.startswith(b"FGDB1")
    assert vault.decrypt_db(blob) == b"sqlite-bytes"


def test_password_hash():
    stored = hash_password("correct horse battery")
    assert verify_password("correct horse battery", stored)
    assert not verify_password("wrong", stored)


def test_task_id_guard():
    assert is_safe_task_id("c14ec0cae512")
    assert not is_safe_task_id("../etc/passwd")
    assert not is_safe_task_id("a" * 80)


def test_wrong_key_quarantines_and_recovers(tmp_path: Path):
    import os

    from app.security.crypto import reset_vault
    from app.security.db import EncryptedDB

    os.environ["FRAMEGENIUS_MASTER_KEY"] = "unit-key-one-framegenius-aaaa"
    reset_vault()
    first = EncryptedDB(tmp_path)
    first.flush()
    first.close()
    assert (tmp_path / "framegenius.db.enc").exists()

    os.environ["FRAMEGENIUS_MASTER_KEY"] = "unit-key-two-framegenius-bbbb"
    reset_vault()
    second = EncryptedDB(tmp_path)
    assert second.recovered is True
    second.close()
    leftovers = list(tmp_path.glob("framegenius.db.enc.broken-*"))
    assert leftovers


def test_path_escape(tmp_path: Path):
    allowed = tmp_path / "outputs"
    allowed.mkdir()
    good = allowed / "a.mp4"
    good.write_bytes(b"x")
    assert safe_under(good, allowed) == good.resolve()
    outside = tmp_path / "secret.txt"
    outside.write_text("nope")
    with pytest.raises(ValidationError):
        safe_under(outside, allowed)
    # ROOT fixture exists in the real project
    assert ROOT.exists()

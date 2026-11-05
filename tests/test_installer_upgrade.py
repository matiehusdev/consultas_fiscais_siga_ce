import os
import shutil
from pathlib import Path
import pytest
from installer import get_installed_version, deploy_payload_files, TARGET_DIR

def test_get_installed_version_from_flag(tmp_path, monkeypatch):
    test_target = tmp_path / "installed_app"
    test_target.mkdir()
    data_dir = test_target / "data"
    data_dir.mkdir()
    flag = data_dir / ".bootstrap_completed"
    flag.write_text("installed_at=123456\nversion=1.2.0\n", encoding="utf-8")

    monkeypatch.setattr("installer.TARGET_DIR", test_target)
    assert get_installed_version() == "1.2.0"

def test_get_installed_version_from_src(tmp_path, monkeypatch):
    test_target = tmp_path / "installed_app"
    test_target.mkdir()
    src_dir = test_target / "src"
    src_dir.mkdir()
    init_f = src_dir / "__init__.py"
    init_f.write_text('__version__ = "1.1.0"\n', encoding="utf-8")

    monkeypatch.setattr("installer.TARGET_DIR", test_target)
    assert get_installed_version() == "1.1.0"

def test_get_installed_version_none_on_fresh(tmp_path, monkeypatch):
    test_target = tmp_path / "empty_dir"
    test_target.mkdir()
    monkeypatch.setattr("installer.TARGET_DIR", test_target)
    assert get_installed_version() is None

def test_deploy_payload_preserves_existing_data(tmp_path, monkeypatch):
    payload_dir = tmp_path / "payload"
    payload_dir.mkdir()
    (payload_dir / "src").mkdir()
    (payload_dir / "src" / "sample.py").write_text("# new code", encoding="utf-8")
    (payload_dir / ".env.example").write_text("SECRET_KEY=sample_example\n", encoding="utf-8")
    (payload_dir / "main.py").write_text("# main", encoding="utf-8")

    target_dir = tmp_path / "target"
    target_dir.mkdir()
    data_db_dir = target_dir / "data" / "db"
    data_db_dir.mkdir(parents=True)
    db_file = data_db_dir / "siga_fiscal.db"
    db_file.write_text("DADOS_IMPORTANTES_DE_EMPRESAS", encoding="utf-8")
    
    existing_env = target_dir / ".env"
    existing_env.write_text("SECRET_KEY=MY_PERSISTED_KEY\n", encoding="utf-8")

    monkeypatch.setattr("installer.PAYLOAD_DIR", payload_dir)
    monkeypatch.setattr("installer.TARGET_DIR", target_dir)

    success = deploy_payload_files()
    assert success is True

    # Verifica que o código foi atualizado
    assert (target_dir / "src" / "sample.py").exists()
    assert (target_dir / "src" / "sample.py").read_text(encoding="utf-8") == "# new code"

    # Verifica que o banco de dados e o .env EXISTENTES NUNCA FORAM APAGADOS OU MODIFICADOS
    assert db_file.exists()
    assert db_file.read_text(encoding="utf-8") == "DADOS_IMPORTANTES_DE_EMPRESAS"
    assert existing_env.read_text(encoding="utf-8") == "SECRET_KEY=MY_PERSISTED_KEY\n"

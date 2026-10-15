import pytest
from datetime import datetime, timezone, timedelta
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12, BestAvailableEncryption

from src.utils.crypto import encrypt_passphrase, decrypt_passphrase
from src.utils.cert_parser import inspect_pfx, modernize_pfx
from src.database import crud

def _create_mock_pfx(cn: str = "EMPRESA TESTE:12720599000117", password: str = "senha123", valid_days: int = 365) -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, cn)])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1000)
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=valid_days))
        .sign(key, hashes.SHA256())
    )
    return pkcs12.serialize_key_and_certificates(
        b"alias", key, cert, None, BestAvailableEncryption(password.encode("utf-8"))
    )

def test_encrypt_and_decrypt_passphrase():
    senha_original = "minha_senha_super_secreta_123"
    cifrada = encrypt_passphrase(senha_original)
    assert cifrada != senha_original
    assert len(cifrada) > 10

    decifrada = decrypt_passphrase(cifrada)
    assert decifrada == senha_original

def test_inspect_pfx_valid():
    pfx_bytes = _create_mock_pfx(cn="EMPRESA A LTDA:12720599000117", password="mypassword")
    is_valid, meta, err = inspect_pfx(pfx_bytes, "mypassword")

    assert is_valid is True
    assert err == ""
    assert meta["common_name"] == "EMPRESA A LTDA:12720599000117"
    assert meta["cnpj_extraido"] == "12720599000117"
    assert meta["dias_restantes"] > 300

def test_inspect_pfx_wrong_password():
    pfx_bytes = _create_mock_pfx(password="senha_certa")
    is_valid, meta, err = inspect_pfx(pfx_bytes, "senha_errada")

    assert is_valid is False
    assert "senha incorreta" in err.lower()

def test_save_and_retrieve_empresa_certificate(db_session):
    empresa, _ = crud.create_empresa(
        db=db_session,
        razao_social="Empresa com Certificado",
        cnpj="12.720.599/0001-17"
    )

    pfx_bytes = _create_mock_pfx(password="segredo_a1")
    success, err = crud.save_empresa_certificado(
        db=db_session,
        empresa_id=empresa.id,
        pfx_data=pfx_bytes,
        filename="teste_a1.pfx",
        passphrase="segredo_a1"
    )

    assert success is True
    assert err == ""
    assert empresa.certificado_caminho is not None
    assert empresa.certificado_validade is not None

    # Obter estrutura para o Playwright
    client_cert = crud.get_empresa_client_certificate(db_session, empresa.id)
    assert client_cert is not None
    assert isinstance(client_cert, list)
    assert len(client_cert) >= 3
    assert client_cert[0]["passphrase"] == "segredo_a1"
    assert client_cert[0]["pfxPath"].endswith("certificado.pfx")

    # Remover certificado
    rem_ok, rem_err = crud.remove_empresa_certificado(db_session, empresa.id)
    assert rem_ok is True
    assert empresa.certificado_caminho is None

def test_api_upload_and_delete_certificate(client, db_session):
    empresa, _ = crud.create_empresa(
        db=db_session,
        razao_social="Empresa API Cert",
        cnpj="00.000.000/0001-91"
    )

    pfx_bytes = _create_mock_pfx(password="senha_api")

    # Upload via endpoint
    response = client.post(
        f"/api/empresas/{empresa.id}/certificado",
        data={"senha": "senha_api"},
        files={"certificado": ("cert.pfx", pfx_bytes, "application/x-pkcs12")}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tem_certificado"] is True
    assert data["certificado_nome"] == "cert.pfx"

    # Remoção via endpoint
    del_resp = client.delete(f"/api/empresas/{empresa.id}/certificado")
    assert del_resp.status_code == 200
    assert del_resp.json()["message"] == "Certificado digital removido com sucesso."

def test_modernize_pfx():
    # Testa modernização de certificado PFX com senha correta
    pfx_bytes = _create_mock_pfx(password="minhasenha")
    modern_bytes, ok = modernize_pfx(pfx_bytes, "minhasenha")
    assert ok is True
    assert len(modern_bytes) > 0

    # Verifica se os bytes modernizados podem ser inspecionados normalmente
    is_valid, meta, err = inspect_pfx(modern_bytes, "minhasenha")
    assert is_valid is True
    assert meta["cnpj_extraido"] == "12720599000117"

    # Testa com senha errada
    _, fail_ok = modernize_pfx(pfx_bytes, "senha_errada")
    assert fail_ok is False


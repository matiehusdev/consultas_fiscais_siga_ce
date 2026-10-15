from datetime import datetime, timezone
from typing import Tuple, Optional, Dict, Any
from cryptography.hazmat.primitives.serialization import pkcs12, BestAvailableEncryption
from cryptography import x509
from cryptography.x509.oid import NameOID
import re

from src.utils.cnpj_validator import clean_cnpj
from src.utils.logger import logger

def inspect_pfx(pfx_data: bytes, passphrase: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Inspeciona e valida o arquivo PKCS#12 (.pfx / .p12) e sua senha.
    Extrai metadados do certificado (CN, Validade, Emissor, CNPJ associado).
    Retorna (True, metadata_dict, "") ou (False, None, "Mensagem de erro").
    """
    if not pfx_data:
        return False, None, "Arquivo de certificado vazio."

    pass_bytes = passphrase.encode("utf-8") if passphrase else b""

    try:
        private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
            pfx_data,
            pass_bytes
        )
    except Exception as e:
        err_msg = str(e).lower()
        if "bad decrypt" in err_msg or "password" in err_msg or "mac verify failure" in err_msg:
            return False, None, "Senha incorreta para o certificado digital."
        return False, None, f"Falha ao carregar arquivo de certificado (.pfx/.p12): {e}"

    if not certificate:
        return False, None, "O arquivo PKCS#12 não contém um certificado público válido."

    # Extração de CN (Common Name)
    common_name = ""
    try:
        cn_attributes = certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if cn_attributes:
            common_name = cn_attributes[0].value
    except Exception:
        pass

    # Extração de Emissor
    issuer_name = ""
    try:
        issuer_attrs = certificate.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
        if issuer_attrs:
            issuer_name = issuer_attrs[0].value
    except Exception:
        pass

    # Data de validade (UTC)
    try:
        # cryptography >= 42 possui not_valid_after_utc
        not_valid_after = getattr(certificate, "not_valid_after_utc", None)
        if not not_valid_after:
            not_valid_after = certificate.not_valid_after.replace(tzinfo=timezone.utc)
    except Exception:
        not_valid_after = datetime.now(timezone.utc)

    # Verifica expiração
    now = datetime.now(timezone.utc)
    if not_valid_after < now:
        return False, None, f"Certificado expirado em {not_valid_after.strftime('%d/%m/%Y')}."

    # Tenta identificar CNPJ dentro do Common Name (ex: "RAZAO SOCIAL:12345678000190")
    cnpj_encontrado = ""
    numeros = re.findall(r"\d{14}", common_name)
    if numeros:
        cnpj_encontrado = clean_cnpj(numeros[0])

    metadata = {
        "common_name": common_name,
        "emissor": issuer_name,
        "validade": not_valid_after,
        "cnpj_extraido": cnpj_encontrado,
        "dias_restantes": (not_valid_after - now).days
    }

    return True, metadata, ""

def modernize_pfx(pfx_data: bytes, passphrase: str) -> Tuple[bytes, bool]:
    """
    Carrega o arquivo PKCS#12 (.pfx / .p12) e o re-serializa utilizando criptografia
    moderna (AES-256-CBC com PBKDF2).

    Esta modernização é essencial porque a maioria das Autoridades Certificadoras
    brasileiras (ICP-Brasil) exporta certificados A1 com cifras legadas (RC2-40, 3DES, SHA-1 MAC).
    O OpenSSL 3.0+ adotado pelo Chromium/Playwright rejeita tais cifras legadas com o erro:
    'Unsupported TLS certificate. Most likely, the security algorithm of the given certificate was deprecated by OpenSSL.'

    Retorna (pfx_modernizado_bytes, foi_modernizado_bool).
    """
    if not pfx_data:
        return pfx_data, False

    pass_bytes = passphrase.encode("utf-8") if passphrase else b""
    try:
        private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
            pfx_data,
            pass_bytes
        )
        if not private_key or not certificate:
            return pfx_data, False

        modern_bytes = pkcs12.serialize_key_and_certificates(
            name=None,
            key=private_key,
            cert=certificate,
            cas=additional_certs,
            encryption_algorithm=BestAvailableEncryption(pass_bytes)
        )
        return modern_bytes, True
    except Exception as e:
        logger.warning(f"Aviso ao modernizar PKCS#12: {e}")
        return pfx_data, False


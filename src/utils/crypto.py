import os
from pathlib import Path
from src.config import settings
from src.utils.logger import logger
from src.utils.deps import ensure_cryptography

ensure_cryptography()
from cryptography.fernet import Fernet

def _get_key_file() -> Path:
    return settings.data_dir / ".secret_key"

def _get_or_create_key() -> bytes:
    """Obtém ou gera chave local mestra para cifragem de senhas em repouso."""
    settings.ensure_directories()
    env_key = os.getenv("CERTIFICATE_SECRET_KEY")
    if env_key:
        return env_key.encode("utf-8")

    key_file = _get_key_file()
    if key_file.exists():
        try:
            with open(key_file, "rb") as f:
                content = f.read().strip()
                if content:
                    return content
        except Exception as e:
            logger.warning(f"Erro ao ler chave mestra de {key_file}: {e}")

    # Gera nova chave de 32 bytes compatível com Fernet
    new_key = Fernet.generate_key()
    try:
        key_file.parent.mkdir(parents=True, exist_ok=True)
        with open(key_file, "wb") as f:
            f.write(new_key)
        logger.info("Nova chave criptográfica local gerada para proteção de certificados.")
    except Exception as e:
        logger.error(f"Erro ao salvar arquivo de chave mestra {key_file}: {e}")
    return new_key

def encrypt_passphrase(plain_text: str) -> str:
    """Cifra a senha do certificado com chave simétrica AES-128."""
    if not plain_text:
        return ""
    key = _get_or_create_key()
    fernet = Fernet(key)
    encrypted_bytes = fernet.encrypt(plain_text.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")

def decrypt_passphrase(cipher_text: str) -> str:
    """Decifra a senha do certificado para uso em memória durante a sessão."""
    if not cipher_text:
        return ""
    key = _get_or_create_key()
    fernet = Fernet(key)
    try:
        decrypted_bytes = fernet.decrypt(cipher_text.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except Exception as e:
        logger.error(f"Erro ao decifrar senha do certificado: {e}")
        return ""

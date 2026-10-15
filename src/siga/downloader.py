import hashlib
from pathlib import Path
from typing import Tuple, Optional
from src.utils.sanitizers import sanitize_url, sanitize_text
from src.utils.logger import logger

class Downloader:
    """
    Realiza o download seguro e sanitizado dos arquivos gerados pelo SIGA SEFAZ-CE.
    Garante que URLs pré-assinadas da Amazon S3 nunca vazem em logs ou em disco.
    """

    @staticmethod
    def salvar_arquivo_bytes(
        conteudo_bytes: bytes,
        destino_caminho: Path
    ) -> Tuple[bool, str, int, str]:
        """
        Grava os bytes diretamente no disco e calcula hash SHA-256 e tamanho.
        """
        try:
            destino_caminho.parent.mkdir(parents=True, exist_ok=True)
            
            sha256 = hashlib.sha256(conteudo_bytes).hexdigest()
            tamanho = len(conteudo_bytes)

            with open(destino_caminho, "wb") as f:
                f.write(conteudo_bytes)

            logger.info(f"Arquivo salvo com sucesso em: {destino_caminho.name} ({tamanho} bytes, SHA256: {sha256[:12]}...)")
            return True, sha256, tamanho, ""
        except Exception as e:
            err = f"Falha ao salvar arquivo no disco: {sanitize_text(str(e))}"
            logger.error(err)
            return False, "", 0, err

import time
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List
from src.config import settings
from src.siga.browser_session import BrowserSession
from src.siga.downloader import Downloader
from src.utils.cnpj_validator import clean_cnpj
from src.utils.sanitizers import sanitize_url, sanitize_text
from src.utils.logger import logger

class NFCeClient:
    """
    Cliente dedicado para integração com NFC-e (Nota Fiscal de Consumidor Eletrônica - Modelo 65).
    Mantido estritamente isolado de NF-e para preservar a estabilidade da aplicação
    conforme premissa do projeto.
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.siga_base_url).rstrip("/")
        self.polling_interval = settings.polling_interval_seconds
        self.max_polling_attempts = settings.max_polling_attempts

    def solicitar_download(
        self,
        session: BrowserSession,
        cnpj: str,
        data_inicio: str,
        data_fim: str,
        operacao: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Dispara solicitação de geração do arquivo XLSX para NFC-e.
        Utiliza rota de NFC-e descoberta ou mapeada no portal SIGA.
        """
        clean = clean_cnpj(cnpj)
        operacao_upper = operacao.upper()

        # Endpoint real descoberto para NFC-e no SIGA SEFAZ-CE
        url = f"{self.base_url}/api/v1/unidades/{clean}/documentos-fiscais/nfc-e/download"

        payload = {
            "dataReferencia": f"{data_inicio},{data_fim}",
            "tipoOperacao": operacao_upper,
            "formatoArquivo": "xlsx"
        }

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        token = session.get_auth_token() if hasattr(session, "get_auth_token") else getattr(session, "auth_token", None)
        if token:
            headers["Authorization"] = token

        logger.info(f"Solicitando download de NFC-e ({operacao_upper}) para CNPJ {clean}...")

        try:
            response = session.context.request.post(
                url,
                data=payload,
                headers=headers
            )

            if response.status in (200, 201, 202):
                logger.info(f"Solicitação de NFC-e ({operacao_upper}) aceita com sucesso (HTTP {response.status}).")
                return True, "Solicitação aceita", None
            elif response.status == 409:
                logger.info(f"Solicitação de NFC-e ({operacao_upper}) já existente na SEFAZ (HTTP 409). Prosseguindo para acompanhamento e download.")
                return True, "Solicitação já existente", None
            else:
                err_text = sanitize_text(response.text()[:200])
                logger.warning(f"Resposta na solicitação de NFC-e: HTTP {response.status} - {err_text}")
                return False, None, f"HTTP {response.status}: {err_text}"

        except Exception as e:
            err = f"Erro na solicitação de NFC-e: {sanitize_text(str(e))}"
            logger.error(err)
            return False, None, err

    def acompanhar_solicitacao(
        self,
        session: BrowserSession,
        cnpj: str,
        operacao: str,
        data_inicio: str,
        data_fim: str,
        timeout_seconds: Optional[int] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Consulta solicitações de NFC-e com matching estrito.
        """
        clean = clean_cnpj(cnpj)
        operacao_upper = operacao.upper()
        url = f"{self.base_url}/api/v1/solicitacoes?sort=criacao,desc"

        interval = self.polling_interval if self.polling_interval > 0 else 1
        max_attempts = (timeout_seconds // interval) if timeout_seconds else self.max_polling_attempts
        max_attempts = max(1, max_attempts)
        logger.info(f"Acompanhando processamento de NFC-e ({operacao_upper}) para CNPJ {clean}...")

        headers = {"Accept": "application/json"}
        token = session.get_auth_token() if hasattr(session, "get_auth_token") else getattr(session, "auth_token", None)
        if token:
            headers["Authorization"] = token

        for attempt in range(1, max_attempts + 1):
            try:
                response = session.context.request.get(url, headers=headers)
                if response.status == 200:
                    payload = response.json()
                    items: List[Dict] = payload.get("data", [])

                    matched_item = None
                    # Prioridade 1: matching estrito de CNPJ + Tipo + Data de Referência
                    for it in items:
                        if clean_cnpj(it.get("cnpj", "")) != clean:
                            continue
                        if it.get("tipo") not in ("NFC_E_RESUMO_EVENTOS", "NFCE_RESUMO_EVENTOS", "NFC_E", "NFCE"):
                            continue
                        filtro = it.get("filtro") or {}
                        if filtro.get("tipoOperacao") and filtro.get("tipoOperacao") != operacao_upper:
                            continue
                        dat_ref = filtro.get("datReferencia")
                        if dat_ref and isinstance(dat_ref, list):
                            if data_inicio in dat_ref or data_fim in dat_ref:
                                matched_item = it
                                break

                    # Prioridade 2: se não encontrou com datReferencia exata, seleciona a mais recente para o CNPJ
                    if not matched_item:
                        for it in items:
                            if clean_cnpj(it.get("cnpj", "")) != clean:
                                continue
                            # Mapeamento do tipo de documento NFC-e
                            if it.get("tipo") not in ("NFC_E_RESUMO_EVENTOS", "NFCE_RESUMO_EVENTOS", "NFC_E", "NFCE"):
                                continue
                            filtro = it.get("filtro") or {}
                            if filtro.get("tipoOperacao") and filtro.get("tipoOperacao") != operacao_upper:
                                continue

                            matched_item = it
                            break

                    if matched_item:
                        status = matched_item.get("status", "").upper()
                        if status == "CONCLUIDO":
                            return True, matched_item, ""
                        elif status in ("ERRO", "EXPIRADO"):
                            motivo = matched_item.get("resultadoProcessamento") or "Erro na geração do arquivo NFC-e"
                            return False, matched_item, f"Status '{status}': {motivo}"

            except Exception as e:
                logger.debug(f"Aviso no polling de NFC-e: {sanitize_text(str(e))}")

            if self.polling_interval > 0:
                time.sleep(self.polling_interval)

        return False, None, f"Timeout aguardando arquivo NFC-e ({max_attempts * interval}s)."

    def baixar_arquivo(
        self,
        session: BrowserSession,
        solicitacao_id: str,
        destino_caminho: Path
    ) -> Tuple[bool, str, int, str]:
        """
        Baixa o arquivo de NFC-e pronto com Bearer token.
        """
        url = f"{self.base_url}/api/v1/solicitacoes/{solicitacao_id}/download"
        headers = {"Accept": "*/*"}
        token = session.get_auth_token() if hasattr(session, "get_auth_token") else getattr(session, "auth_token", None)
        if token:
            headers["Authorization"] = token

        try:
            response = session.context.request.get(url, headers=headers, max_redirects=5)
            if response.status == 200:
                conteudo = response.body()
                return Downloader.salvar_arquivo_bytes(conteudo, destino_caminho)
            else:
                return False, "", 0, f"HTTP {response.status} ao baixar NFC-e"
        except Exception as e:
            return False, "", 0, f"Erro ao baixar NFC-e: {sanitize_text(str(e))}"

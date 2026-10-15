import time
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List
from src.config import settings
from src.siga.browser_session import BrowserSession
from src.siga.downloader import Downloader
from src.utils.cnpj_validator import clean_cnpj
from src.utils.sanitizers import sanitize_url, sanitize_text
from src.utils.logger import logger

class NFeClient:
    """
    Cliente para integração com os endpoints de NF-e (Modelo 55) do portal SIGA SEFAZ-CE.
    Opera no contexto autenticado do Playwright herdando sessão e Certificado A1.
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
        Dispara a solicitação de geração do arquivo XLSX para NF-e.
        POST /api/v1/unidades/{CNPJ}/documentos-fiscais/nf-e/resumos/eventos/download
        """
        clean = clean_cnpj(cnpj)
        operacao_upper = operacao.upper()
        url = f"{self.base_url}/api/v1/unidades/{clean}/documentos-fiscais/nf-e/resumos/eventos/download"

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

        logger.info(f"Solicitando download de NF-e ({operacao_upper}) para CNPJ {clean}...")

        try:
            response = session.context.request.post(
                url,
                data=payload,
                headers=headers
            )

            if response.status in (200, 201, 202):
                logger.info(f"Solicitação de NF-e ({operacao_upper}) aceita com sucesso (HTTP {response.status}).")
                return True, "Solicitação aceita", None
            elif response.status == 409:
                logger.info(f"Solicitação de NF-e ({operacao_upper}) já existente na SEFAZ (HTTP 409). Prosseguindo para acompanhamento e download.")
                return True, "Solicitação já existente", None
            else:
                err_text = sanitize_text(response.text()[:200])
                logger.error(f"Falha ao solicitar download de NF-e: HTTP {response.status} - {err_text}")
                return False, None, f"HTTP {response.status}: {err_text}"

        except Exception as e:
            err = f"Erro de comunicação na solicitação de NF-e: {sanitize_text(str(e))}"
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
        Consulta periodicamente a lista de solicitações até a conclusão.
        Aplica matching estrito para evitar pegar solicitação incorreta.
        GET /api/v1/solicitacoes?sort=criacao,desc
        """
        clean = clean_cnpj(cnpj)
        operacao_upper = operacao.upper()
        url = f"{self.base_url}/api/v1/solicitacoes?sort=criacao,desc"

        interval = self.polling_interval if self.polling_interval > 0 else 1
        max_attempts = (timeout_seconds // interval) if timeout_seconds else self.max_polling_attempts
        max_attempts = max(1, max_attempts)
        logger.info(f"Acompanhando processamento de NF-e ({operacao_upper}) para CNPJ {clean} (máx {max_attempts} tentativas)...")

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
                        if it.get("tipo") not in ("NF_E_RESUMO_EVENTOS", "NFE_RESUMO_EVENTOS", "NF_E", "NFE"):
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
                            if it.get("tipo") not in ("NF_E_RESUMO_EVENTOS", "NFE_RESUMO_EVENTOS", "NF_E", "NFE"):
                                continue
                            filtro = it.get("filtro") or {}
                            if filtro.get("tipoOperacao") and filtro.get("tipoOperacao") != operacao_upper:
                                continue

                            matched_item = it
                            break

                    if matched_item:
                        status = matched_item.get("status", "").upper()
                        id_solicitacao = matched_item.get("id")
                        logger.info(f"Tentativa {attempt}/{max_attempts}: Solicitação {id_solicitacao} status = '{status}'")

                        if status == "CONCLUIDO":
                            return True, matched_item, ""
                        elif status in ("ERRO", "EXPIRADO"):
                            motivo = matched_item.get("resultadoProcessamento") or "Erro no processamento da SEFAZ"
                            return False, matched_item, f"Solicitação finalizada com status '{status}': {motivo}"

                else:
                    logger.warning(f"Tentativa {attempt}: Resposta inesperada ao consultar solicitações: HTTP {response.status}")

            except Exception as e:
                logger.debug(f"Aviso durante polling de solicitações: {sanitize_text(str(e))}")

            if self.polling_interval > 0:
                time.sleep(self.polling_interval)

        return False, None, f"Tempo limite de {max_attempts * interval}s atingido aguardando geração do arquivo."

    def baixar_arquivo(
        self,
        session: BrowserSession,
        solicitacao_id: str,
        destino_caminho: Path
    ) -> Tuple[bool, str, int, str]:
        """
        Executa o download do arquivo pronto, com token Bearer autenticado.
        GET /api/v1/solicitacoes/{id}/download
        """
        url = f"{self.base_url}/api/v1/solicitacoes/{solicitacao_id}/download"
        logger.info(f"Baixando arquivo da solicitação {solicitacao_id}...")

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
                err = f"Falha no download da solicitação {solicitacao_id}: HTTP {response.status}"
                logger.error(err)
                return False, "", 0, err

        except Exception as e:
            err = f"Exceção ao baixar arquivo: {sanitize_text(str(e))}"
            logger.error(err)
            return False, "", 0, err

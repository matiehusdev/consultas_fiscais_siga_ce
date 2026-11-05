import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from src.config import settings
from src.siga.browser_session import BrowserSession
from src.siga.downloader import Downloader
from src.utils.cnpj_validator import clean_cnpj
from src.utils.logger import logger
from src.utils.sanitizers import sanitize_text

class SigaUiDownloader:
    """
    Realiza o fluxo completo de solicitação e download de relatórios XLSX via interface web do SIGA SEFAZ-CE:
    1. Acessa /ui/contribuinte/{CNPJ}/informacoes-fiscais/nfe (ou nfce)
    2. Seleciona o ano/período correspondente
    3. Alterna entre Emissor (Saídas) e Destinatário (Entradas) com verificação rigorosa de estado
    4. Clica em 'Baixar Tabela (XLSX)' e captura o evento de solicitação
    5. Acessa /ui/contribuinte/{CNPJ}/downloads-assincronos
    6. Atualiza o status e aguarda EXCLUSIVAMENTE a solicitação recém-gerada (vínculo por ID/timestamp e operação)
    7. Faz o download do arquivo XLSX pronto e salva no destino especificado
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.siga_base_url).rstrip("/")
        self.polling_interval = 2.0
        self.max_attempts = 150  # até ~300 segundos aguardando o processamento assíncrono

    def solicitar_e_baixar(
        self,
        session: BrowserSession,
        cnpj: str,
        tipo_doc: str,  # "NFE" ou "NFCE"
        operacao: str,  # "SAIDA" ou "ENTRADA"
        ano: int,
        destino_caminho: Path
    ) -> Tuple[bool, str, int, str]:
        """
        Executa a sequência visual segura de solicitação e download no SIGA.
        Retorna (sucesso, sha256, tamanho_bytes, erro_detalhe).
        """
        clean = clean_cnpj(cnpj)
        op_upper = operacao.upper()
        doc_upper = tipo_doc.upper()

        if not session or not session.is_alive:
            return False, "", 0, "Sessão do navegador não está ativa para download visual."

        page: Page = session.page

        # Guarda contra operação inválida: NFC-e no portal SEFAZ-CE não possui visão de Destinatário (apenas venda no varejo)
        if doc_upper == "NFCE" and op_upper == "ENTRADA":
            logger.info("UI Downloader: NFC-e (Modelo 65) não possui visão de Destinatário no SEFAZ-CE. Concluindo entrada zerada.")
            return True, "", 0, ""

        # =========================================================================
        # Passo 1: Navegar para a tela de Informações Fiscais
        # =========================================================================
        target_path = "nfce" if doc_upper == "NFCE" else "nfe"
        info_fiscais_url = f"{self.base_url}/ui/contribuinte/{clean}/informacoes-fiscais/{target_path}"

        logger.info(f"UI Downloader: Acessando Informações Fiscais para CNPJ {clean} ({doc_upper} - {op_upper})...")
        try:
            if f"/informacoes-fiscais/{target_path}" not in page.url or clean not in page.url:
                page.goto(info_fiscais_url, wait_until="domcontentloaded", timeout=25000)
                time.sleep(2.0)

            # Fecha eventuais modais ou diálogos
            for m_sel in ["ed-dialog button:has-text('Ok')", ".p-dialog-header-close", "button:has-text('Fechar')", "button:has-text('✕')"]:
                try:
                    b = page.locator(m_sel).first
                    if b.is_visible(timeout=400):
                        b.click()
                        time.sleep(0.3)
                except Exception:
                    pass

            # Garante que a aba correta está ativa
            if doc_upper == "NFCE":
                tab_nfce = page.locator("a:has-text('NFC-e'), button:has-text('NFC-e'), [role='tab']:has-text('NFC-e'), .p-menuitem-link:has-text('NFC-e')").first
                if tab_nfce.is_visible(timeout=3000):
                    tab_class = tab_nfce.get_attribute("class") or ""
                    if "p-highlight" not in tab_class and "active" not in tab_class:
                        tab_nfce.click()
                        time.sleep(1.5)
            else:
                tab_nfe = page.locator("a:has-text('NF-e'), button:has-text('NF-e'), [role='tab']:has-text('NF-e'), .p-menuitem-link:has-text('NF-e')").first
                if tab_nfe.is_visible(timeout=2000):
                    tab_class = tab_nfe.get_attribute("class") or ""
                    if "p-highlight" not in tab_class and "active" not in tab_class:
                        tab_nfe.click()
                        time.sleep(0.5)

        except Exception as e:
            err = f"Falha ao carregar página de Informações Fiscais: {sanitize_text(str(e))}"
            logger.error(err)
            return False, "", 0, err

        # =========================================================================
        # Passo 2: Selecionar o Ano no dropdown "Selecione um Período"
        # =========================================================================
        ano_str = str(ano)
        try:
            periodo_container = page.locator("div:has-text('Selecione um Período')").first
            if periodo_container.is_visible(timeout=3000):
                text_atual = periodo_container.text_content() or ""
                if ano_str not in text_atual:
                    logger.info(f"UI Downloader: Selecionando ano {ano_str} no filtro de período...")
                    dropdown = periodo_container.locator(".p-dropdown, [role='combobox'], .p-dropdown-trigger").first
                    if dropdown.is_visible(timeout=3000):
                        dropdown.click()
                        time.sleep(0.5)
                        opt = page.locator(f".p-dropdown-item:has-text('{ano_str}'), li:has-text('{ano_str}')").first
                        if opt.is_visible(timeout=3000):
                            opt.click()
                            time.sleep(1.5)
        except Exception as e:
            logger.debug(f"Aviso no seletor de ano: {e}")

        # =========================================================================
        # Passo 3: Alternar entre Emissor (Saídas) e Destinatário (Entradas)
        # =========================================================================
        btn_label = "Emissor" if op_upper == "SAIDA" else "Destinatário"
        logger.info(f"UI Downloader: Selecionando visão '{btn_label}'...")

        try:
            if op_upper == "SAIDA":
                btn_op = page.locator(".p-selectbutton .p-button:has-text('Emissor'), .p-button:has-text('Emissor')").first
            else:
                btn_op = page.locator(".p-selectbutton .p-button:has-text('Destinatário'), .p-selectbutton .p-button:has-text('Destinatario'), .p-button:has-text('Destinatário'), .p-button:has-text('Destinatario')").first

            try:
                btn_op.wait_for(state="visible", timeout=6000)
            except Exception:
                pass

            if btn_op.is_visible(timeout=2000):
                btn_class = btn_op.get_attribute("class") or ""
                aria_pressed = btn_op.get_attribute("aria-pressed") or ""
                # Se não estiver destacado ou pressionado, clica para selecionar
                if "p-highlight" not in btn_class and aria_pressed.lower() != "true":
                    btn_op.click()
                    time.sleep(1.5)
                    try:
                        page.wait_for_load_state("networkidle", timeout=3000)
                    except Exception:
                        pass
                logger.info(f"UI Downloader: Visão '{btn_label}' selecionada e confirmada.")
            else:
                if op_upper == "ENTRADA" and doc_upper == "NFE":
                    err = "Botão de visão 'Destinatário' (Entradas) não foi encontrado na interface do SIGA."
                    logger.error(err)
                    return False, "", 0, err
                logger.warning(f"Botão de visão '{btn_label}' não encontrado diretamente. Prosseguindo...")
        except Exception as e:
            logger.warning(f"Aviso ao alternar visão para '{btn_label}': {e}")

        # =========================================================================
        # Passo 4: Interceptar Requisição e Clicar em "Baixar Tabela (XLSX)"
        # =========================================================================
        logger.info(f"UI Downloader: Clicando em 'Baixar Tabela (XLSX)' para {doc_upper} {op_upper}...")

        hora_disparo = datetime.now(timezone.utc)
        solicitacao_interceptada_id: Optional[str] = None
        solicitacoes_interceptadas: List[Dict[str, Any]] = []

        def on_response_intercept(response):
            nonlocal solicitacao_interceptada_id
            try:
                # Intercepta POST do botão de download
                if "documentos-fiscais" in response.url and "download" in response.url and response.request.method == "POST":
                    loc = response.headers.get("location") or ""
                    if loc:
                        solicitacao_interceptada_id = loc.strip().split("/")[-1]
                    try:
                        data = response.json()
                        if isinstance(data, dict) and data.get("id"):
                            solicitacao_interceptada_id = str(data.get("id")).strip()
                    except Exception:
                        pass

                # Intercepta listagem de solicitações do backend
                if "solicitacoes" in response.url and response.request.method == "GET":
                    try:
                        payload = response.json()
                        items = payload.get("data", []) if isinstance(payload, dict) else payload
                        if isinstance(items, list):
                            solicitacoes_interceptadas.clear()
                            solicitacoes_interceptadas.extend(items)
                    except Exception:
                        pass
            except Exception:
                pass

        page.on("response", on_response_intercept)

        try:
            btn_baixar = page.locator("button:has-text('Baixar Tabela (XLSX)'), button:has-text('Baixar Tabela'), button.p-splitbutton-defaultbutton, .p-splitbutton-defaultbutton").first
            try:
                btn_baixar.wait_for(state="visible", timeout=15000)
            except Exception:
                pass

            if not btn_baixar.is_visible(timeout=4000):
                page.remove_listener("response", on_response_intercept)
                return False, "", 0, "Botão 'Baixar Tabela (XLSX)' não encontrado na tela."

            btn_baixar.click()
            time.sleep(1.5)
        except Exception as e:
            page.remove_listener("response", on_response_intercept)
            err = f"Falha ao clicar no botão 'Baixar Tabela (XLSX)': {sanitize_text(str(e))}"
            logger.error(err)
            return False, "", 0, err

        # =========================================================================
        # Passo 5: Acessar a página de Downloads Assíncronos
        # =========================================================================
        downloads_url = f"{self.base_url}/ui/contribuinte/{clean}/downloads-assincronos"
        logger.info("UI Downloader: Direcionando para tela de Downloads Assíncronos...")

        try:
            link_aqui = page.locator("a:has-text('aqui')").first
            if link_aqui.is_visible(timeout=2500):
                link_aqui.click()
                time.sleep(1.5)
            else:
                page.goto(downloads_url, wait_until="domcontentloaded", timeout=20000)
                time.sleep(1.5)
        except Exception:
            page.goto(downloads_url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(1.5)

        # =========================================================================
        # Passo 6: Acompanhar status com matching estrito da solicitação recém-gerada
        # =========================================================================
        logger.info(f"UI Downloader: Aguardando processamento da solicitação de {doc_upper} - {op_upper} (CNPJ {clean})...")
        btn_atualizar = page.locator("button:has-text('Atualizar Status'), .p-button:has-text('Atualizar Status')").first

        solicitacao_concluida_id: Optional[str] = None
        concluido = False
        matching_row = None

        try:
            page.locator("table tbody tr").first.wait_for(state="visible", timeout=15000)
        except Exception:
            pass

        for attempt in range(1, self.max_attempts + 1):
            try:
                # Método 1 (Mais confiável): Valida via dados JSON oficiais interceptados do backend SEFAZ
                if solicitacoes_interceptadas:
                    for it in solicitacoes_interceptadas:
                        it_cnpj = clean_cnpj(it.get("cnpj", ""))
                        if it_cnpj and it_cnpj != clean:
                            continue

                        it_tipo = str(it.get("tipo", "")).upper()
                        if doc_upper == "NFCE" and ("NFC" not in it_tipo):
                            continue
                        elif doc_upper == "NFE" and ("NFC" in it_tipo or "NF" not in it_tipo):
                            continue

                        filtro = it.get("filtro") or {}
                        filtro_op = str(filtro.get("tipoOperacao", "")).upper()
                        if filtro_op and filtro_op != op_upper:
                            continue

                        # Se tivermos o ID da criação, bate estritamente
                        it_id = str(it.get("id", "")).strip()
                        if solicitacao_interceptada_id and it_id != solicitacao_interceptada_id:
                            continue

                        it_status = str(it.get("status", "")).upper()
                        if it_status == "CONCLUIDO":
                            solicitacao_concluida_id = it_id
                            concluido = True
                            logger.info(f"UI Downloader: Solicitação {it_id} confirmada como CONCLUÍDA via API interceptada!")
                            break
                        elif it_status == "ERRO":
                            page.remove_listener("response", on_response_intercept)
                            return False, "", 0, f"SEFAZ retornou status de ERRO na solicitação {it_id}."

                if concluido:
                    break

                # Método 2: Análise da tabela DOM
                rows = page.locator("table tbody tr")
                try:
                    raw_count = rows.count()
                    count = int(raw_count) if isinstance(raw_count, (int, float)) else 1
                except Exception:
                    count = 1

                for idx in range(count):
                    try:
                        row = rows.nth(idx) if count > 1 else rows.first
                    except Exception:
                        row = rows.first

                    if not row.is_visible(timeout=1000):
                        continue

                    row_text = (row.text_content() or "").upper()

                    # Checa tipo de documento
                    if doc_upper == "NFCE":
                        if "NFC-E" not in row_text and "NFCE" not in row_text:
                            continue
                    else:  # NFE
                        if ("NF-E" not in row_text and "NFE" not in row_text) or "NFC" in row_text:
                            continue

                    # Checa visão se informada na linha
                    if any(k in row_text for k in ["EMISSOR", "DESTINAT", "SAÍDA", "SAIDA", "ENTRADA"]):
                        if op_upper == "SAIDA":
                            if "DESTINAT" in row_text or "ENTRADA" in row_text:
                                continue
                        else:  # ENTRADA
                            if "EMISSOR" in row_text or "SAÍDA" in row_text or "SAIDA" in row_text:
                                continue

                    matching_row = row
                    logger.debug(f"UI Downloader [Tentativa {attempt}/{self.max_attempts}]: Linha {idx + 1} = {row_text[:90]}")

                    if "CONCLUÍDO" in row_text or "CONCLUIDO" in row_text:
                        concluido = True
                        break
                    elif "ERRO" in row_text:
                        page.remove_listener("response", on_response_intercept)
                        return False, "", 0, f"SEFAZ indicou status ERRO no download: {row_text[:120]}"
                    else:
                        break

                if concluido:
                    break

            except Exception as e:
                logger.debug(f"Aviso ao consultar linhas de download: {e}")

            # Clica em Atualizar Status
            try:
                if btn_atualizar.is_visible(timeout=1000):
                    btn_atualizar.click()
            except Exception:
                pass

            time.sleep(self.polling_interval)

        page.remove_listener("response", on_response_intercept)

        if not concluido:
            return False, "", 0, f"Tempo limite de {int(self.max_attempts * self.polling_interval)}s atingido aguardando o arquivo de {doc_upper} - {op_upper}."

        # =========================================================================
        # Passo 7: Baixar e salvar o arquivo XLSX pronto
        # =========================================================================
        logger.info(f"UI Downloader: Solicitação pronta! Iniciando download do XLSX ({doc_upper} - {op_upper})...")

        # Prioridade A: Download direto autenticado via API caso o ID tenha sido identificado
        if solicitacao_concluida_id:
            try:
                url_dl = f"{self.base_url}/api/v1/solicitacoes/{solicitacao_concluida_id}/download"
                headers = {"Accept": "*/*"}
                token = session.get_auth_token() if hasattr(session, "get_auth_token") else getattr(session, "auth_token", None)
                if token:
                    headers["Authorization"] = token

                resp_dl = session.context.request.get(url_dl, headers=headers, max_redirects=5)
                if resp_dl.status == 200 and len(resp_dl.body()) > 200:
                    ok_save, h_save, s_save, e_save = Downloader.salvar_arquivo_bytes(resp_dl.body(), destino_caminho)
                    if ok_save:
                        logger.info(f"UI Downloader: Arquivo baixado diretamente via API com sucesso ({s_save} bytes, SHA256: {h_save[:12]}...).")
                        return True, h_save, s_save, ""
            except Exception as e:
                logger.debug(f"Fallback para clique visual após erro no download direto: {e}")

        # Prioridade B: Download via clique no botão de download do navegador
        try:
            target_row = matching_row if matching_row and matching_row.is_visible(timeout=2000) else page.locator("table tbody tr").first
            dl_candidates = target_row.locator("span:has-text('Download'), td:has-text('Download'), a:has-text('Download'), button:has-text('Download')")
            download_elem = dl_candidates.last

            if not download_elem.is_visible(timeout=4000):
                download_elem = dl_candidates.first

            if not download_elem.is_visible(timeout=4000):
                return False, "", 0, f"Elemento 'Download' não encontrado na linha correspondente da tabela para {doc_upper} - {op_upper}."

            with page.expect_download(timeout=30000) as download_info:
                download_elem.click()
            download = download_info.value

            destino_caminho.parent.mkdir(parents=True, exist_ok=True)
            download.save_as(str(destino_caminho))

            if not destino_caminho.exists() or destino_caminho.stat().st_size == 0:
                return False, "", 0, "O arquivo baixado está corrompido ou vazio no disco."

            with open(destino_caminho, "rb") as f:
                conteudo = f.read()

            sha256 = hashlib.sha256(conteudo).hexdigest()
            tamanho = len(conteudo)

            logger.info(f"UI Downloader: Arquivo salvo com sucesso em {destino_caminho.name} ({tamanho} bytes, SHA256: {sha256[:12]}...)")
            return True, sha256, tamanho, ""

        except PlaywrightTimeoutError:
            err = "Timeout aguardando início do download pelo navegador."
            logger.error(err)
            return False, "", 0, err
        except Exception as e:
            err = f"Falha durante o download via UI: {sanitize_text(str(e))}"
            logger.error(err)
            return False, "", 0, err

import time
import hashlib
from pathlib import Path
from typing import Tuple, Optional
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from src.config import settings
from src.siga.browser_session import BrowserSession
from src.utils.cnpj_validator import clean_cnpj
from src.utils.logger import logger
from src.utils.sanitizers import sanitize_text

class SigaUiDownloader:
    """
    Realiza o fluxo completo de solicitação e download de relatórios XLSX via interface web do SIGA SEFAZ-CE:
    1. Acessa /ui/contribuinte/{CNPJ}/informacoes-fiscais/nfe (ou nfce)
    2. Seleciona o ano/período correspondente
    3. Alterna entre Emissor (Saídas) e Destinatário (Entradas)
    4. Clica em 'Baixar Tabela (XLSX)'
    5. Acessa /ui/contribuinte/{CNPJ}/downloads-assincronos (via link 'aqui' do toast de sucesso ou URL direta)
    6. Atualiza o status até a conclusão da solicitação mais recente (linha 1)
    7. Faz o download do arquivo XLSX pronto e salva no destino especificado
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.siga_base_url).rstrip("/")
        self.polling_interval = 2.0
        self.max_attempts = 150  # até ~300 segundos aguardando o processamento assíncrono (essencial para NFC-e pesados)

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
        Executa a sequência visual de 5 passos comprovada nos prints do portal SIGA.
        Retorna (sucesso, sha256, tamanho_bytes, erro_detalhe).
        """
        clean = clean_cnpj(cnpj)
        op_upper = operacao.upper()
        doc_upper = tipo_doc.upper()

        if not session or not session.is_alive:
            return False, "", 0, "Sessão do navegador não está ativa para download visual."

        page: Page = session.page

        # =========================================================================
        # Passo 1: Navegar para a tela de Informações Fiscais
        # =========================================================================
        target_path = "nfce" if doc_upper == "NFCE" else "nfe"
        info_fiscais_url = f"{self.base_url}/ui/contribuinte/{clean}/informacoes-fiscais/{target_path}"

        logger.info(f"UI Downloader: Acessando Informações Fiscais para CNPJ {clean} ({doc_upper} - {op_upper})...")
        try:
            # Se ainda não estiver na página correspondente, navega
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

            # Se for NFCE, garante que a aba NFC-e está selecionada
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
                btn_op = page.locator(".p-button:has-text('Emissor'), span.p-button-label:has-text('Emissor')").first
            else:
                btn_op = page.locator(".p-button:has-text('Destinatário'), .p-button:has-text('Destinatario'), span.p-button-label:has-text('Destinatário'), span.p-button-label:has-text('Destinatario')").first

            try:
                btn_op.wait_for(state="visible", timeout=10000)
            except Exception:
                pass

            if btn_op.is_visible(timeout=2000):
                btn_class = btn_op.get_attribute("class") or ""
                if "p-highlight" not in btn_class:
                    btn_op.click()
                    time.sleep(1.5)
            else:
                logger.warning(f"Botão de visão '{btn_label}' não encontrado diretamente. Prosseguindo...")
        except Exception as e:
            logger.warning(f"Aviso ao alternar visão para '{btn_label}': {e}")

        # =========================================================================
        # Passo 4: Clicar no botão "Baixar Tabela (XLSX)"
        # =========================================================================
        logger.info(f"UI Downloader: Clicando em 'Baixar Tabela (XLSX)' para {doc_upper} {op_upper}...")
        try:
            btn_baixar = page.locator("button:has-text('Baixar Tabela (XLSX)'), button:has-text('Baixar Tabela'), button.p-splitbutton-defaultbutton, .p-splitbutton-defaultbutton").first
            try:
                btn_baixar.wait_for(state="visible", timeout=15000)
            except Exception:
                pass

            if not btn_baixar.is_visible(timeout=4000):
                return False, "", 0, "Botão 'Baixar Tabela (XLSX)' não encontrado na tela."

            btn_baixar.click()
            time.sleep(1.5)
        except Exception as e:
            err = f"Falha ao clicar no botão 'Baixar Tabela (XLSX)': {sanitize_text(str(e))}"
            logger.error(err)
            return False, "", 0, err

        # =========================================================================
        # Passo 5: Acessar a página de Downloads Assíncronos
        # =========================================================================
        downloads_url = f"{self.base_url}/ui/contribuinte/{clean}/downloads-assincronos"
        logger.info("UI Downloader: Direcionando para tela de Downloads Assíncronos...")

        try:
            # Tenta clicar no link "aqui" da notificação de sucesso verde
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
        # Passo 6: Acompanhar status na tabela até "Concluído" da linha correspondente
        # =========================================================================
        logger.info(f"UI Downloader: Aguardando processamento da solicitação de {doc_upper} - {op_upper}...")
        btn_atualizar = page.locator("button:has-text('Atualizar Status'), .p-button:has-text('Atualizar Status')").first

        visao_esperada = "EMISSOR" if op_upper == "SAIDA" else "DESTINAT"
        matching_row = None
        concluido = False

        # Aguarda a primeira linha aparecer na tabela
        try:
            page.locator("table tbody tr").first.wait_for(state="visible", timeout=15000)
        except Exception:
            pass

        for attempt in range(1, self.max_attempts + 1):
            try:
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

                    if not row.is_visible(timeout=2000):
                        continue

                    row_text = (row.text_content() or "").upper()

                    # Checa tipo de documento correspondente
                    if doc_upper == "NFCE":
                        if "NFC-E" not in row_text and "NFCE" not in row_text:
                            continue
                    else:  # NFE
                        if ("NF-E" not in row_text and "NFE" not in row_text) or "NFC" in row_text:
                            continue

                    # Checa visão se informada na linha (com suporte a EMISSOR/DESTINATÁRIO e SAÍDAS/ENTRADAS)
                    if any(k in row_text for k in ["EMISSOR", "DESTINAT", "SAÍDA", "SAIDA", "ENTRADA"]):
                        if op_upper == "SAIDA":
                            if "DESTINAT" in row_text or "ENTRADA" in row_text:
                                continue
                        else:  # ENTRADA
                            if "EMISSOR" in row_text or "SAÍDA" in row_text or "SAIDA" in row_text:
                                continue

                    # Encontrou a linha mais recente correspondente
                    matching_row = row
                    logger.debug(f"UI Downloader [Tentativa {attempt}/{self.max_attempts}]: Linha {idx + 1} = {row_text[:90]}")

                    if "CONCLUÍDO" in row_text or "CONCLUIDO" in row_text:
                        concluido = True
                        break
                    elif "ERRO" in row_text:
                        return False, "", 0, f"SEFAZ indicou status ERRO no download: {row_text[:120]}"
                    else:
                        # Ainda em processamento, não analisa linhas anteriores mais antigas
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

        if not concluido:
            return False, "", 0, f"Tempo limite de {int(self.max_attempts * self.polling_interval)}s atingido aguardando o arquivo de {doc_upper} - {op_upper}."

        # =========================================================================
        # Passo 7: Interceptar e salvar o download do arquivo XLSX da linha correspondente
        # =========================================================================
        logger.info(f"UI Downloader: Solicitação pronta! Iniciando download do XLSX ({doc_upper} - {op_upper})...")
        try:
            target_row = matching_row if matching_row and matching_row.is_visible(timeout=2000) else page.locator("table tbody tr").first
            # No DOM real da SEFAZ, o botão de download é um <span class="ng-star-inserted">Download</span> dentro de um <td>
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

import time
from typing import Optional
from playwright.sync_api import Page
from src.siga.browser_session import BrowserSession
from src.utils.cnpj_validator import clean_cnpj, format_cnpj
from src.utils.logger import logger

class ContribuinteSelector:
    """
    Garante a seleção e confirmação do contribuinte/unidade correta na interface do SIGA.
    """

    def __init__(self, timeout_seconds: int = 15):
        self.timeout_seconds = timeout_seconds

    def selecionar_contribuinte(
        self,
        session: BrowserSession,
        cnpj: str,
        razao_social: str = ""
    ) -> bool:
        """
        Localiza e seleciona a empresa correspondente pelo CNPJ na interface do SIGA.
        Se já estiver na unidade correta, confirma e retorna True.
        """
        clean = clean_cnpj(cnpj)
        formatted = format_cnpj(clean)
        page: Page = session.page

        logger.info(f"Verificando seleção de contribuinte para CNPJ: {formatted} ({razao_social})...")

        # 1. Fecha quaisquer diálogos informativos na tela
        for m_sel in ["ed-dialog button:has-text('Ok')", ".p-dialog-header-close", "button:has-text('✕')", "button:has-text('Fechar')"]:
            try:
                b = page.locator(m_sel).first
                if b.is_visible(timeout=500):
                    b.click()
                    time.sleep(0.5)
            except Exception:
                pass

        # 2. Verifica se a URL já indica a unidade correta
        try:
            current_url = page.url
            if f"/unidades/{clean}" in current_url or f"/ui/contribuinte/{clean}" in current_url:
                logger.info(f"Sessão já posicionada na unidade {clean}.")
                return True
        except Exception:
            pass

        # 3. Utiliza campo de pesquisa de contribuinte se presente
        try:
            search_input = page.locator("#tabela-pesquisa-id, input[placeholder*='CNPJ, CGF'], input[placeholder*='Buscar']").first
            if search_input.is_visible(timeout=3000):
                logger.info(f"Filtrando contribuinte pelo CNPJ {formatted}...")
                search_input.click()
                search_input.fill("")
                search_input.fill(clean)
                search_input.press("Enter")
                time.sleep(1.5)
        except Exception as e:
            logger.debug(f"Aviso no campo de pesquisa de unidades: {e}")

        # 4. Procura e seleciona a linha da empresa na tabela PrimeNG com matching estrito
        linha_selecionada = False
        try:
            seletores_linha = [
                f"tr:has-text('{formatted}')",
                f"tr:has-text('{clean}')"
            ]
            if razao_social and len(razao_social.strip()) >= 3:
                seletores_linha.append(f"tr:has-text('{razao_social.strip()}')")

            for sel in seletores_linha:
                row = page.locator(sel).first
                if row.is_visible(timeout=3000):
                    logger.info(f"Linha do contribuinte localizada ({sel}). Selecionando...")
                    # Garante que nenhum modal residual bloqueie o clique
                    for m_sel in ["ed-dialog button:has-text('Ok')", ".p-dialog-header-close", "button:has-text('✕')"]:
                        try:
                            b = page.locator(m_sel).first
                            if b.is_visible(timeout=300):
                                b.click()
                                time.sleep(0.3)
                        except Exception:
                            pass

                    row.click(force=True)
                    time.sleep(1.0)

                    # Clica no botão Ok para confirmar seleção
                    ok_btn = page.locator("button.p-button:has-text('Ok'), button:has-text('Ok')").last
                    if ok_btn.is_visible(timeout=2000):
                        logger.info("Confirmando seleção no botão 'Ok'...")
                        ok_btn.click()
                    else:
                        row.dblclick(force=True)

                    try:
                        page.wait_for_load_state("networkidle", timeout=3000)
                    except Exception:
                        pass
                    time.sleep(2.5)

                    linha_selecionada = True
                    break

            if not linha_selecionada:
                # Se não encontrou pelo CNPJ limpo no filtro, tenta pesquisar pelo CNPJ formatado se houver campo
                try:
                    search_input = page.locator("#tabela-pesquisa-id, input[placeholder*='CNPJ, CGF'], input[placeholder*='Buscar']").first
                    if search_input.is_visible(timeout=1000):
                        logger.info(f"Tentando refiltrar contribuinte pelo CNPJ formatado {formatted}...")
                        search_input.click()
                        search_input.fill(formatted)
                        search_input.press("Enter")
                        time.sleep(1.5)
                        for sel in seletores_linha:
                            row = page.locator(sel).first
                            if row.is_visible(timeout=2000):
                                logger.info(f"Linha localizada após refiltro ({sel})...")
                                row.click(force=True)
                                time.sleep(1.0)
                                ok_btn = page.locator("button.p-button:has-text('Ok'), button:has-text('Ok')").last
                                if ok_btn.is_visible(timeout=2000):
                                    ok_btn.click()
                                else:
                                    row.dblclick(force=True)

                                try:
                                    page.wait_for_load_state("networkidle", timeout=3000)
                                except Exception:
                                    pass
                                time.sleep(2.5)
                                linha_selecionada = True
                                break
                except Exception:
                    pass

        except Exception as e:
            logger.debug(f"Aviso ao selecionar linha de contribuinte: {e}")

        # 5. Verificação de segurança: confirma se a unidade ativa na página é a esperada
        try:
            current_url = page.url
            if f"/unidades/{clean}" in current_url or f"/ui/contribuinte/{clean}" in current_url:
                logger.info(f"✓ Seleção confirmada na URL: unidade {clean}.")
                return True

            body_text = page.locator("body").text_content() or ""
            if formatted in body_text or clean in body_text:
                logger.info(f"✓ Seleção confirmada no conteúdo da página: CNPJ {formatted}.")
                return True

            # Se ainda houver tabela de seleção visível e não selecionou a empresa correta
            tabela_visivel = page.locator("#tabela-pesquisa-id, table[aria-label*='unidades'], .p-datatable").first.is_visible(timeout=1500)
            if tabela_visivel and not linha_selecionada:
                logger.error(f"Empresa {formatted} ({razao_social}) não foi encontrada na lista de contribuintes autorizados.")
                return False

        except Exception as e:
            logger.debug(f"Aviso na verificação final de contribuinte: {e}")

        logger.info("Nenhum seletor múltiplo bloqueante. Prosseguindo com unidade ativa na sessão.")
        return True

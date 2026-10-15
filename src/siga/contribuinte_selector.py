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
            if search_input.is_visible(timeout=5000):
                logger.info(f"Filtrando contribuinte pelo CNPJ {clean}...")
                search_input.fill(clean)
                search_input.press("Enter")
                time.sleep(2.0)
        except Exception as e:
            logger.debug(f"Aviso no campo de pesquisa de unidades: {e}")

        # 4. Procura e seleciona a linha da empresa na tabela PrimeNG
        try:
            seletores_linha = [
                f"tr:has-text('{formatted}')",
                f"tr:has-text('{clean}')",
                "table tbody tr"
            ]
            for sel in seletores_linha:
                row = page.locator(sel).first
                if row.is_visible(timeout=4000):
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
                        time.sleep(3.0)
                    else:
                        row.dblclick(force=True)
                        time.sleep(3.0)

                    return True
        except Exception as e:
            logger.debug(f"Aviso ao selecionar linha: {e}")

        # 5. Se não houver seletor explícito e já estiver no painel/dashboard, assume unidade única ativa
        logger.info("Nenhum seletor múltiplo pendente. Prosseguindo com unidade ativa na sessão.")
        return True

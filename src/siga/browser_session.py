import time
from typing import Optional, List
from playwright.sync_api import sync_playwright, Playwright, Browser, BrowserContext, Page
from src.config import settings
from src.utils.logger import logger

class BrowserSession:
    """
    Gerencia o ciclo de vida do navegador Playwright em sessão isolada.
    Garante inicialização em modo visível (headless=False) para permitir
    a exibição do diálogo nativo de seleção do Certificado Digital A1.
    """

    def __init__(
        self,
        headless: Optional[bool] = None,
        slow_mo: Optional[int] = None,
        timeout_ms: Optional[int] = None,
        extra_args: Optional[List[str]] = None,
        client_certificates: Optional[List[dict]] = None
    ):
        self.headless = headless if headless is not None else settings.browser_headless
        self.slow_mo = slow_mo if slow_mo is not None else settings.browser_slow_mo_ms
        self.timeout_ms = timeout_ms if timeout_ms is not None else settings.page_timeout_ms
        self.extra_args = extra_args or []
        self.client_certificates = client_certificates

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._is_open = False

    @property
    def is_alive(self) -> bool:
        """Verifica se o navegador e a página continuam abertos e responsivos."""
        if not self._is_open or not self._browser or not self._page:
            return False
        try:
            return not self._page.is_closed() and self._browser.is_connected()
        except Exception:
            return False

    @property
    def page(self) -> Page:
        if not self._page or not self.is_alive:
            raise RuntimeError("Navegador não está aberto ou a página foi fechada.")
        return self._page

    @property
    def context(self) -> BrowserContext:
        if not self._context:
            raise RuntimeError("Contexto do navegador não foi inicializado.")
        return self._context

    def start(self) -> Page:
        """Inicializa uma nova instância do Chromium em sessão isolada."""
        logger.info(f"Iniciando nova sessão do navegador (headless={self.headless})...")

        args = [
            "--start-maximized",
            "--disable-blink-features=AutomationControlled",
            "--no-default-browser-check",
            "--disable-features=Translate"
        ]
        if self.extra_args:
            args.extend(self.extra_args)

        self._playwright = sync_playwright().start()

        # Inicia Chromium nativo do Playwright
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,
            args=args
        )

        # Contexto completamente isolado (sem cookies de sessões anteriores)
        context_kwargs = {
            "no_viewport": True,
            "accept_downloads": True
        }
        if self.client_certificates:
            context_kwargs["client_certificates"] = self.client_certificates
            logger.info("Certificado de cliente A1 configurado no contexto TLS do Playwright.")

        self._context = self._browser.new_context(**context_kwargs)
        self._page = self._context.new_page()
        self._is_open = True
        self.auth_token: Optional[str] = None

        def _capture_auth(request):
            try:
                auth = request.headers.get("authorization", "")
                if auth and auth.startswith("Bearer "):
                    self.auth_token = auth
            except Exception:
                pass

        self._page.on("request", _capture_auth)

        logger.info("Navegador iniciado com sucesso em sessão limpa.")
        return self._page

    def get_auth_token(self) -> Optional[str]:
        """Retorna o Bearer token JWT da sessão, capturado do tráfego ou do armazenamento da página."""
        if self.auth_token:
            return self.auth_token
        if self._page and self.is_alive:
            try:
                token = self._page.evaluate("""
                    () => {
                        for (let k of Object.keys(sessionStorage)) {
                            let v = sessionStorage.getItem(k);
                            if (v && v.startsWith('ey') && v.includes('.')) return 'Bearer ' + v;
                        }
                        for (let k of Object.keys(localStorage)) {
                            let v = localStorage.getItem(k);
                            if (v && v.startsWith('ey') && v.includes('.')) return 'Bearer ' + v;
                        }
                        return null;
                    }
                """)
                if token:
                    self.auth_token = token
                    return token
            except Exception:
                pass
        return self.auth_token

    def close(self) -> None:
        """Encerra com segurança a página, contexto e processo do navegador."""
        logger.info("Encerrando sessão do navegador...")
        self._is_open = False

        if self._page:
            try:
                if not self._page.is_closed():
                    self._page.close()
            except Exception as e:
                logger.debug(f"Aviso ao fechar página: {e}")
            self._page = None

        if self._context:
            try:
                self._context.close()
            except Exception as e:
                logger.debug(f"Aviso ao fechar contexto: {e}")
            self._context = None

        if self._browser:
            try:
                if self._browser.is_connected():
                    self._browser.close()
            except Exception as e:
                logger.debug(f"Aviso ao fechar navegador: {e}")
            self._browser = None

        if self._playwright:
            try:
                self._playwright.stop()
            except Exception as e:
                logger.debug(f"Aviso ao finalizar Playwright: {e}")
            self._playwright = None

        logger.info("Sessão do navegador finalizada e recursos liberados.")

    def __enter__(self) -> "BrowserSession":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

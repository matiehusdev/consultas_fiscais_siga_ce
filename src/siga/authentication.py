import time
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from playwright.sync_api import Page, Response
from src.config import settings
from src.siga.browser_session import BrowserSession
from src.utils.logger import logger

@dataclass
class AuthStatusUpdate:
    status: str            # INICIANDO, AGUARDANDO_CERTIFICADO, AUTENTICADO, TIMEOUT, ERRO
    mensagem: str
    acao_necessaria: bool = False
    detalhes: Optional[Dict[str, Any]] = None

class Authenticator:
    """
    Controla o fluxo de autenticação via Certificado Digital A1 no portal SIGA SEFAZ-CE.
    Acompanha a interação manual do usuário sem interferir na janela nativa do Windows,
    detectando de forma assíncrona e não-bloqueante a conclusão do login.
    """

    def __init__(self, timeout_seconds: Optional[int] = None):
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None 
            else settings.certificate_selection_timeout_seconds
        )
        self.check_interval_seconds = 0.5
        self._auth_api_detected = False

    def _setup_network_listener(self, page: Page):
        """Monitora respostas da API do SIGA para detectar autenticação concluída."""
        self._auth_api_detected = False

        def handle_response(response: Response):
            try:
                url = response.url.lower()
                # Se a API interna do SIGA responder com 200, a autenticação foi estabelecida
                if "siga.sefaz.ce.gov.br/api/v1/" in url:
                    if response.status in (200, 202, 204):
                        # Evita considerar apenas rotas públicas caso existam
                        if any(auth_path in url for auth_path in ["/unidades", "/contribuinte", "/perfil", "/solicitacoes", "/selecao-contribuinte"]):
                            self._auth_api_detected = True
            except Exception:
                pass

        page.on("response", handle_response)

    def _is_authenticated_dom(self, page: Page) -> bool:
        """Verifica marcadores visuais no DOM que indicam sessão autenticada."""
        try:
            # Seletores comuns de navegação autenticada no SIGA
            selectors = [
                "button:has-text('Sair')",
                "a:has-text('Sair')",
                "a[href*='logout']",
                "[data-testid='user-info']",
                ".user-profile",
                ".contribuinte",
                "#tabela-pesquisa-id",
                "input[placeholder*='CNPJ, CGF ou Razão Social']",
                ".p-datatable-table",
                "select[name='unidade']",
                "table[aria-label*='unidades']"
            ]
            for sel in selectors:
                if page.locator(sel).first.is_visible(timeout=200):
                    return True
        except Exception:
            pass
        return False

    def authenticate(
        self,
        session: BrowserSession,
        empresa_razao_social: str = "Empresa",
        empresa_cnpj: str = "",
        on_status_change: Optional[Callable[[AuthStatusUpdate], None]] = None
    ) -> bool:
        """
        Executa o fluxo de autenticação para a empresa informada.
        """
        def notify(status: str, msg: str, acao: bool = False, detalhes: Optional[Dict] = None):
            update = AuthStatusUpdate(status=status, mensagem=msg, acao_necessaria=acao, detalhes=detalhes)
            logger.info(f"[{status}] {msg}")
            if on_status_change:
                try:
                    on_status_change(update)
                except Exception as e:
                    logger.debug(f"Erro no callback de status: {e}")

        notify(
            status="INICIANDO",
            msg=f"Acessando o portal do SIGA para {empresa_razao_social}...",
            acao=False
        )

        page = session.page
        self._setup_network_listener(page)

        try:
            logger.info(f"Navegando para: {settings.siga_base_url}")
            page.goto(settings.siga_base_url, wait_until="domcontentloaded")
        except Exception as e:
            # Pode ocorrer exceção durante o handshake de certificado se o diálogo estiver aberto
            logger.debug(f"Aviso na navegação inicial (diálogo de certificado pode estar aberto): {e}")

        # Se houver botão de login com Certificado Digital no SSO, clica automaticamente
        try:
            cert_btn = page.locator("#social-certificado-digital, a:has-text('Entrar com Certificado Digital')").first
            if cert_btn.is_visible(timeout=3000):
                logger.info("Botão 'Entrar com Certificado Digital' localizado no SSO. Clicando...")
                cert_btn.click()
        except Exception as e:
            logger.debug(f"Aviso ao verificar botão de certificado no SSO: {e}")

        is_autonomo = bool(getattr(session, "client_certificates", None))

        if is_autonomo:
            notify(
                status="AUTENTICANDO_AUTOMATICO",
                msg=f"Autenticando '{empresa_razao_social}' ({empresa_cnpj}) de forma 100% autônoma via Certificado A1 cadastrado...",
                acao=False,
                detalhes={"empresa": empresa_razao_social, "cnpj": empresa_cnpj, "modo": "autonomo"}
            )
        else:
            # Mensagem orientando o usuário a selecionar o certificado no Windows caso não haja A1 anexado
            notify(
                status="AGUARDANDO_CERTIFICADO",
                msg=f"Aguardando seleção do Certificado Digital A1 de '{empresa_razao_social}' ({empresa_cnpj}). Selecione o certificado na janela do navegador.",
                acao=True,
                detalhes={"empresa": empresa_razao_social, "cnpj": empresa_cnpj, "modo": "manual"}
            )

        start_time = time.time()
        while time.time() - start_time < self.timeout_seconds:
            # 1. Verifica se a janela do navegador foi fechada pelo usuário
            if not session.is_alive:
                notify(
                    status="ERRO",
                    msg="O navegador foi fechado antes da conclusão da autenticação.",
                    acao=False
                )
                return False

            # Tenta clicar no botão de certificado caso a página tenha terminado de carregar agora
            try:
                cert_btn = page.locator("#social-certificado-digital, a:has-text('Entrar com Certificado Digital')").first
                if cert_btn.is_visible(timeout=200):
                    cert_btn.click()
            except Exception:
                pass

            # Fecha eventuais modais informativos que surgem automaticamente após login
            try:
                for sel_modal in ["ed-dialog button:has-text('Ok')", ".p-dialog-header-close", "button:has-text('✕')"]:
                    m_btn = page.locator(sel_modal).first
                    if m_btn.is_visible(timeout=200):
                        m_btn.click()
            except Exception:
                pass

            # 2. Verifica se a API interna confirmou o login
            if self._auth_api_detected:
                notify(
                    status="AUTENTICADO",
                    msg="Autenticação confirmada via resposta segura da API da SEFAZ-CE!",
                    acao=False
                )
                return True

            # 3. Verifica elementos do DOM na página atual
            if self._is_authenticated_dom(page):
                notify(
                    status="AUTENTICADO",
                    msg="Autenticação detectada com sucesso na interface do SIGA!",
                    acao=False
                )
                return True

            # 4. Verifica mudança de URL para rotas autenticadas conhecidas
            try:
                current_url = page.url.lower()
                if any(path in current_url for path in ["/unidades", "/painel", "/declaracoes", "/documentos-fiscais", "/selecao-contribuinte", "/contribuinte"]):
                    notify(
                        status="AUTENTICADO",
                        msg="Autenticação confirmada por redirecionamento de rota do SIGA!",
                        acao=False
                    )
                    return True
            except Exception:
                pass

            time.sleep(self.check_interval_seconds)

        # Se atingiu o limite de tempo
        notify(
            status="TIMEOUT",
            msg=f"Tempo limite de {self.timeout_seconds}s excedido aguardando a seleção do certificado digital.",
            acao=False
        )
        return False

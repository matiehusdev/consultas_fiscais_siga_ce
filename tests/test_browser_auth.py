import pytest
from unittest.mock import MagicMock, patch
from src.siga.browser_session import BrowserSession
from src.siga.authentication import Authenticator, AuthStatusUpdate
from src.orchestrator.status_broadcaster import StatusBroadcaster

def test_browser_session_initialization():
    session = BrowserSession(headless=True, slow_mo=50, timeout_ms=30000)
    assert session.headless is True
    assert session.slow_mo == 50
    assert session.timeout_ms == 30000
    assert session.is_alive is False

def test_status_broadcaster_publish_and_history():
    broadcaster = StatusBroadcaster(max_history=10)
    broadcaster.reset()

    event = broadcaster.publish(
        etapa="AGUARDANDO_CERTIFICADO",
        mensagem="Selecione o certificado da Empresa X no navegador.",
        empresa="Empresa X",
        cnpj="12.720.599/0001-17",
        acao_necessaria=True,
        acao_mensagem="Clique no certificado no Windows"
    )

    state = broadcaster.get_current_state()
    assert state["ativo"] is True
    assert state["etapa"] == "AGUARDANDO_CERTIFICADO"
    assert state["acao_necessaria"] is True
    assert state["empresa_atual"] == "Empresa X"

    history = broadcaster.get_history()
    assert len(history) == 1
    assert history[0]["etapa"] == "AGUARDANDO_CERTIFICADO"

def test_status_broadcaster_sanitizes_tokens():
    broadcaster = StatusBroadcaster()
    event = broadcaster.publish(
        etapa="TESTE",
        mensagem="URL com token=12345 e X-Amz-Signature=abcd987"
    )
    assert "abcd987" not in event["mensagem"]
    assert "12345" not in event["mensagem"]

def test_authenticator_detects_dom_elements():
    authenticator = Authenticator(timeout_seconds=2)

    # Mock da sessão e da página Playwright
    mock_session = MagicMock(spec=BrowserSession)
    mock_session.is_alive = True
    mock_session.client_certificates = None
    mock_page = MagicMock()
    mock_session.page = mock_page

    # Simula que o seletor 'button:has-text("Sair")' fica visível
    def mock_is_visible(selector, timeout=200):
        return True if "Sair" in selector else False

    mock_locator = MagicMock()
    mock_locator.first.is_visible.side_effect = lambda timeout=200: True
    mock_page.locator.return_value = mock_locator
    mock_page.url = "https://siga.sefaz.ce.gov.br/painel"

    status_updates = []
    def callback(update: AuthStatusUpdate):
        status_updates.append(update.status)

    sucesso = authenticator.authenticate(
        session=mock_session,
        empresa_razao_social="Empresa Teste",
        empresa_cnpj="12.720.599/0001-17",
        on_status_change=callback
    )

    assert sucesso is True
    assert "AUTENTICADO" in status_updates

def test_authenticator_autonomous_with_client_certificates():
    authenticator = Authenticator(timeout_seconds=2)

    mock_session = MagicMock(spec=BrowserSession)
    mock_session.is_alive = True
    mock_session.client_certificates = [{"origin": "https://siga.sefaz.ce.gov.br", "pfxPath": "dummy.pfx"}]
    mock_page = MagicMock()
    mock_session.page = mock_page

    mock_locator = MagicMock()
    mock_locator.first.is_visible.return_value = True
    mock_page.locator.return_value = mock_locator
    mock_page.url = "https://siga.sefaz.ce.gov.br/painel"

    status_updates = []
    def callback(update: AuthStatusUpdate):
        status_updates.append(update.status)

    sucesso = authenticator.authenticate(
        session=mock_session,
        empresa_razao_social="Empresa Autonoma",
        empresa_cnpj="12.720.599/0001-17",
        on_status_change=callback
    )

    assert sucesso is True
    assert "AUTENTICANDO_AUTOMATICO" in status_updates
    assert "AUTENTICADO" in status_updates

def test_authenticator_handles_timeout():
    # Timeout ultrarrápido de 0.2s para teste
    authenticator = Authenticator(timeout_seconds=0.2)
    authenticator.check_interval_seconds = 0.05

    mock_session = MagicMock(spec=BrowserSession)
    mock_session.is_alive = True
    mock_session.client_certificates = None
    mock_page = MagicMock()
    mock_session.page = mock_page

    # Nenhum elemento autenticado visível
    mock_locator = MagicMock()
    mock_locator.first.is_visible.return_value = False
    mock_page.locator.return_value = mock_locator
    mock_page.url = "https://siga.sefaz.ce.gov.br/login"

    status_updates = []
    def callback(update: AuthStatusUpdate):
        status_updates.append(update.status)

    sucesso = authenticator.authenticate(
        session=mock_session,
        empresa_razao_social="Empresa Teste",
        on_status_change=callback
    )

    assert sucesso is False
    assert "TIMEOUT" in status_updates

def test_authenticator_handles_browser_closed_by_user():
    authenticator = Authenticator(timeout_seconds=5)

    mock_session = MagicMock(spec=BrowserSession)
    # Simula que a janela foi fechada pelo operador
    mock_session.is_alive = False
    mock_session.client_certificates = None
    mock_page = MagicMock()
    mock_session.page = mock_page

    status_updates = []
    def callback(update: AuthStatusUpdate):
        status_updates.append(update.status)

    sucesso = authenticator.authenticate(
        session=mock_session,
        on_status_change=callback
    )

    assert sucesso is False
    assert "ERRO" in status_updates

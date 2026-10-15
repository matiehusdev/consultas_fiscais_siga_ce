import pytest
from pathlib import Path
from unittest.mock import MagicMock
from src.siga.nfe_client import NFeClient
from src.siga.nfce_client import NFCeClient
from src.siga.downloader import Downloader
from src.siga.contribuinte_selector import ContribuinteSelector
from src.siga.browser_session import BrowserSession

def test_downloader_salvar_arquivo_bytes(tmp_path):
    arquivo_destino = tmp_path / "test_download.xlsx"
    conteudo = b"PK\x03\x04MockXLSXContentBytesForTesting"

    sucesso, sha256, tamanho, err = Downloader.salvar_arquivo_bytes(conteudo, arquivo_destino)
    assert sucesso is True
    assert arquivo_destino.exists()
    assert tamanho == len(conteudo)
    assert len(sha256) == 64
    assert err == ""

def test_contribuinte_selector_url_already_matches():
    selector = ContribuinteSelector()
    mock_session = MagicMock(spec=BrowserSession)
    mock_page = MagicMock()
    mock_page.url = "https://siga.sefaz.ce.gov.br/unidades/12720599000117/painel"
    mock_session.page = mock_page

    resultado = selector.selecionar_contribuinte(
        session=mock_session,
        cnpj="12.720.599/0001-17",
        razao_social="Empresa Teste"
    )
    assert resultado is True

def test_contribuinte_selector_clicks_element():
    selector = ContribuinteSelector()
    mock_session = MagicMock(spec=BrowserSession)
    mock_page = MagicMock()
    mock_page.url = "https://siga.sefaz.ce.gov.br/inicio"

    mock_locator = MagicMock()
    mock_locator.is_visible.return_value = True
    mock_btn = MagicMock()
    mock_btn.is_visible.return_value = True
    mock_locator.locator.return_value.first = mock_btn

    mock_page.locator.return_value.first = mock_locator
    mock_session.page = mock_page

    resultado = selector.selecionar_contribuinte(
        session=mock_session,
        cnpj="12.720.599/0001-17",
        razao_social="Empresa Teste"
    )
    assert resultado is True
    assert mock_locator.click.called

def test_nfe_client_solicitar_download_success():
    client = NFeClient()
    mock_session = MagicMock(spec=BrowserSession)
    mock_response = MagicMock()
    mock_response.status = 202
    mock_session.context.request.post.return_value = mock_response

    sucesso, msg, err = client.solicitar_download(
        session=mock_session,
        cnpj="12720599000117",
        data_inicio="2026-01-01",
        data_fim="2026-09-30",
        operacao="SAIDA"
    )
    assert sucesso is True
    assert err is None
    mock_session.context.request.post.assert_called_once()

def test_nfe_client_solicitar_download_error():
    client = NFeClient()
    mock_session = MagicMock(spec=BrowserSession)
    mock_response = MagicMock()
    mock_response.status = 400
    mock_response.text.return_value = "Período inválido"
    mock_session.context.request.post.return_value = mock_response

    sucesso, msg, err = client.solicitar_download(
        session=mock_session,
        cnpj="12720599000117",
        data_inicio="2026-01-01",
        data_fim="2026-09-30",
        operacao="SAIDA"
    )
    assert sucesso is False
    assert "HTTP 400" in err

def test_nfe_client_acompanhar_solicitacao_strict_matching():
    client = NFeClient()
    client.polling_interval = 0  # sem sleep no teste
    mock_session = MagicMock(spec=BrowserSession)
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "data": [
            {
                "id": "item-errado",
                "tipo": "NF_E_RESUMO_EVENTOS",
                "cnpj": "99999999000199",
                "status": "CONCLUIDO"
            },
            {
                "id": "uuid-correto-123",
                "tipo": "NF_E_RESUMO_EVENTOS",
                "cnpj": "12720599000117",
                "filtro": {
                    "tipoOperacao": "SAIDA",
                    "formatoArquivo": "xlsx"
                },
                "status": "CONCLUIDO"
            }
        ]
    }
    mock_session.context.request.get.return_value = mock_response

    sucesso, item, err = client.acompanhar_solicitacao(
        session=mock_session,
        cnpj="12720599000117",
        operacao="SAIDA",
        data_inicio="2026-01-01",
        data_fim="2026-09-30",
        timeout_seconds=5
    )
    assert sucesso is True
    assert item["id"] == "uuid-correto-123"
    assert err == ""

def test_nfe_client_baixar_arquivo(tmp_path):
    client = NFeClient()
    mock_session = MagicMock(spec=BrowserSession)
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.body.return_value = b"FakeXLSXBytes"
    mock_session.context.request.get.return_value = mock_response

    destino = tmp_path / "nfe_saida.xlsx"
    sucesso, sha256, tamanho, err = client.baixar_arquivo(
        session=mock_session,
        solicitacao_id="uuid-correto-123",
        destino_caminho=destino
    )

    assert sucesso is True
    assert destino.exists()
    assert tamanho == len(b"FakeXLSXBytes")
    assert err == ""

def test_nfce_client_solicitar_download():
    client = NFCeClient()
    mock_session = MagicMock(spec=BrowserSession)
    mock_response = MagicMock()
    mock_response.status = 202
    mock_session.context.request.post.return_value = mock_response

    sucesso, msg, err = client.solicitar_download(
        session=mock_session,
        cnpj="63.330.299/0001-62",
        data_inicio="2026-01-01",
        data_fim="2026-09-30",
        operacao="SAIDA"
    )
    assert sucesso is True
    assert err is None
    # Verifica se chamou a rota de NFC-e correta com JSON
    call_args = mock_session.context.request.post.call_args
    assert "/documentos-fiscais/nfc-e/download" in call_args[0][0]
    assert call_args[1]["data"]["tipoOperacao"] == "SAIDA"

def test_nfe_client_solicitar_download_409_already_exists():
    client = NFeClient()
    mock_session = MagicMock(spec=BrowserSession)
    mock_response = MagicMock()
    mock_response.status = 409
    mock_session.context.request.post.return_value = mock_response

    sucesso, msg, err = client.solicitar_download(
        session=mock_session,
        cnpj="63330299000162",
        data_inicio="2025-10-13",
        data_fim="2026-10-13",
        operacao="SAIDA"
    )
    assert sucesso is True
    assert msg == "Solicitação já existente"
    assert err is None

def test_nfce_client_solicitar_download_409_already_exists():
    client = NFCeClient()
    mock_session = MagicMock(spec=BrowserSession)
    mock_response = MagicMock()
    mock_response.status = 409
    mock_session.context.request.post.return_value = mock_response

    sucesso, msg, err = client.solicitar_download(
        session=mock_session,
        cnpj="63330299000162",
        data_inicio="2025-10-13",
        data_fim="2026-10-13",
        operacao="SAIDA"
    )
    assert sucesso is True
    assert msg == "Solicitação já existente"
    assert err is None


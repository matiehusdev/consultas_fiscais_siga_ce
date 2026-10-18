import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.siga.ui_downloader import SigaUiDownloader
from src.siga.browser_session import BrowserSession

def test_ui_downloader_session_not_alive(tmp_path):
    downloader = SigaUiDownloader()
    mock_session = MagicMock(spec=BrowserSession)
    mock_session.is_alive = False

    destino = tmp_path / "nfe_saida.xlsx"
    sucesso, sha256, tamanho, err = downloader.solicitar_e_baixar(
        session=mock_session,
        cnpj="63330299000162",
        tipo_doc="NFE",
        operacao="SAIDA",
        ano=2026,
        destino_caminho=destino
    )

    assert sucesso is False
    assert "não está ativa" in err
    assert not destino.exists()

def test_ui_downloader_successful_flow(tmp_path):
    downloader = SigaUiDownloader()
    downloader.polling_interval = 0
    downloader.max_attempts = 2

    mock_session = MagicMock(spec=BrowserSession)
    mock_session.is_alive = True

    mock_page = MagicMock()
    mock_page.url = "https://siga.sefaz.ce.gov.br/ui/contribuinte/63330299000162/painel"
    mock_session.page = mock_page

    # Mock de elementos
    mock_modal = MagicMock()
    mock_modal.is_visible.return_value = False

    mock_tab = MagicMock()
    mock_tab.is_visible.return_value = True

    mock_btn_op = MagicMock()
    mock_btn_op.is_visible.return_value = True

    mock_btn_baixar = MagicMock()
    mock_btn_baixar.is_visible.return_value = True

    mock_link_aqui = MagicMock()
    mock_link_aqui.is_visible.return_value = True

    # Linha da tabela na tela de downloads
    mock_row = MagicMock()
    mock_row.is_visible.return_value = True
    mock_row.text_content.return_value = "Informações Fiscais - NF-e - Indicadores - 2026 | Visão: EMISSOR | Concluído | Download"

    mock_download_btn = MagicMock()
    mock_download_btn.is_visible.return_value = True
    mock_row.locator.return_value.first = mock_download_btn
    mock_row.locator.return_value.last = mock_download_btn

    # Mock do retorno do locator da página
    def locator_side_effect(selector, *args, **kwargs):
        loc = MagicMock()
        if "Baixar Tabela" in selector:
            loc.first = mock_btn_baixar
        elif "aqui" in selector:
            loc.first = mock_link_aqui
        elif "table tbody tr" in selector:
            loc.first = mock_row
            loc.count.return_value = 1
            loc.nth.return_value = mock_row
        elif "Emissor" in selector or "Destinatário" in selector:
            loc.first = mock_btn_op
        elif "NF-e" in selector or "NFC-e" in selector:
            loc.first = mock_tab
        elif "Atualizar Status" in selector:
            loc.first = MagicMock(is_visible=MagicMock(return_value=True))
        else:
            loc.first = MagicMock(is_visible=MagicMock(return_value=False))
        return loc

    mock_page.locator.side_effect = locator_side_effect

    # Mock do expect_download
    destino = tmp_path / "nfe_saida.xlsx"
    mock_download_obj = MagicMock()
    def mock_save_as(path_str):
        with open(path_str, "wb") as f:
            f.write(b"PK0304MockXLSXDownloadedContent")

    mock_download_obj.save_as.side_effect = mock_save_as

    mock_context_manager = MagicMock()
    mock_context_manager.__enter__.return_value = MagicMock(value=mock_download_obj)
    mock_page.expect_download.return_value = mock_context_manager

    sucesso, sha256, tamanho, err = downloader.solicitar_e_baixar(
        session=mock_session,
        cnpj="63330299000162",
        tipo_doc="NFE",
        operacao="SAIDA",
        ano=2026,
        destino_caminho=destino
    )

    assert sucesso is True
    assert err == ""
    assert destino.exists()
    assert tamanho == len(b"PK0304MockXLSXDownloadedContent")
    assert len(sha256) == 64
    assert mock_btn_baixar.click.called

def test_ui_downloader_error_status_from_sefaz(tmp_path):
    downloader = SigaUiDownloader()
    downloader.polling_interval = 0
    downloader.max_attempts = 2

    mock_session = MagicMock(spec=BrowserSession)
    mock_session.is_alive = True
    mock_page = MagicMock()
    mock_session.page = mock_page

    mock_btn_baixar = MagicMock(is_visible=MagicMock(return_value=True))
    mock_row = MagicMock()
    mock_row.is_visible.return_value = True
    mock_row.text_content.return_value = "Informações Fiscais - NF-e | Erro no processamento interno da SEFAZ"

    def locator_side_effect(selector, *args, **kwargs):
        loc = MagicMock()
        if "Baixar Tabela" in selector:
            loc.first = mock_btn_baixar
        elif "table tbody tr" in selector:
            loc.first = mock_row
            loc.count.return_value = 1
            loc.nth.return_value = mock_row
        else:
            loc.first = MagicMock(is_visible=MagicMock(return_value=False))
        return loc

    mock_page.locator.side_effect = locator_side_effect
    destino = tmp_path / "nfe_saida.xlsx"

    sucesso, sha256, tamanho, err = downloader.solicitar_e_baixar(
        session=mock_session,
        cnpj="63330299000162",
        tipo_doc="NFE",
        operacao="SAIDA",
        ano=2026,
        destino_caminho=destino
    )

    assert sucesso is False
    assert "status ERRO" in err
    assert not destino.exists()

def test_ui_downloader_distinguishes_saida_and_entrada(tmp_path):
    downloader = SigaUiDownloader()
    downloader.polling_interval = 0
    downloader.max_attempts = 1

    mock_session = MagicMock(spec=BrowserSession)
    mock_session.is_alive = True
    mock_page = MagicMock()
    mock_session.page = mock_page

    mock_btn_baixar = MagicMock(is_visible=MagicMock(return_value=True))

    # Linha 1 é ENTRADA, Linha 2 é SAÍDA (Emissor)
    row_entrada = MagicMock()
    row_entrada.is_visible.return_value = True
    row_entrada.text_content.return_value = "NF-e - Indicadores - 2026 | Visão: DESTINATÁRIO | Concluído"

    row_saida = MagicMock()
    row_saida.is_visible.return_value = True
    row_saida.text_content.return_value = "NF-e - Indicadores - 2026 | Visão: EMISSOR | Concluído"

    mock_dl_btn = MagicMock(is_visible=MagicMock(return_value=True))
    row_saida.locator.return_value.first = mock_dl_btn
    row_saida.locator.return_value.last = mock_dl_btn

    def locator_side_effect(selector, *args, **kwargs):
        loc = MagicMock()
        if "Baixar Tabela" in selector:
            loc.first = mock_btn_baixar
        elif "table tbody tr" in selector:
            loc.count.return_value = 2
            loc.nth.side_effect = lambda i: row_entrada if i == 0 else row_saida
            loc.first = row_entrada
        else:
            loc.first = MagicMock(is_visible=MagicMock(return_value=False))
        return loc

    mock_page.locator.side_effect = locator_side_effect
    mock_download_obj = MagicMock()
    mock_download_obj.save_as.side_effect = lambda p: Path(p).write_bytes(b"PK0304MockSaidaContent")
    mock_context_manager = MagicMock()
    mock_context_manager.__enter__.return_value = MagicMock(value=mock_download_obj)
    mock_page.expect_download.return_value = mock_context_manager

    destino = tmp_path / "nfe_saida.xlsx"
    sucesso, sha256, tamanho, err = downloader.solicitar_e_baixar(
        session=mock_session,
        cnpj="63330299000162",
        tipo_doc="NFE",
        operacao="SAIDA",
        ano=2026,
        destino_caminho=destino
    )

    assert sucesso is True
    assert destino.exists()
    assert destino.read_bytes() == b"PK0304MockSaidaContent"


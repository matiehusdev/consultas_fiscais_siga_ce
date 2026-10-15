import pytest
from unittest.mock import MagicMock, patch
from datetime import date
from src.database import crud
from src.orchestrator.queue_manager import (
    run_consulta_batch,
    trigger_consulta_async,
    is_execution_running,
    stop_execution,
    get_active_consulta_id
)
from src.database.models import Consulta, ConsultaEmpresa

def test_queue_manager_batch_execution(db_session):
    # 1. Cria empresa de teste
    empresa, _ = crud.create_empresa(
        db_session,
        razao_social="Empresa Orquestrador Teste Ltda",
        cnpj="12.720.599/0001-17",
        ativa=True
    )

    # 2. Cria lote de consulta
    consulta, _ = crud.create_consulta(
        db_session,
        empresas_ids=[empresa.id],
        data_inicio=date(2026, 1, 1),
        data_fim=date(2026, 9, 30),
        consultar_nfe=True,
        consultar_nfce=False,
        consultar_entradas=True,
        consultar_saidas=True
    )

    assert consulta.status == "PENDENTE"

    # 3. Executa batch com mocks do Playwright
    with patch("src.orchestrator.queue_manager.BrowserSession") as mock_session_cls, \
         patch("src.orchestrator.queue_manager.Authenticator") as mock_auth_cls, \
         patch("src.orchestrator.queue_manager.ContribuinteSelector") as mock_sel_cls, \
         patch("src.orchestrator.queue_manager._processar_documentos_empresa", return_value=(True, "")) as mock_proc:

        mock_session = MagicMock()
        mock_session.is_alive = True
        mock_session_cls.return_value = mock_session

        mock_auth = MagicMock()
        mock_auth.authenticate.return_value = True
        mock_auth_cls.return_value = mock_auth

        # Executa síncrono para teste
        run_consulta_batch(consulta.id)

    # 4. Valida atualização de status no banco
    db_session.refresh(consulta)
    assert consulta.status == "CONCLUIDO"
    assert consulta.sucesso_empresas == 1
    assert consulta.erro_empresas == 0

    item = consulta.empresas_consulta[0]
    assert item.status == "CONCLUIDO"
    assert item.iniciado_em is not None
    assert item.finalizado_em is not None

def test_queue_manager_batch_with_error(db_session):
    empresa, _ = crud.create_empresa(
        db_session,
        razao_social="Empresa Falha Teste Ltda",
        cnpj="12.720.599/0001-17",
        ativa=True
    )

    consulta, _ = crud.create_consulta(
        db_session,
        empresas_ids=[empresa.id],
        data_inicio=date(2026, 1, 1),
        data_fim=date(2026, 9, 30),
        consultar_nfe=True,
        consultar_nfce=False,
        consultar_entradas=True,
        consultar_saidas=True
    )

    with patch("src.orchestrator.queue_manager.BrowserSession") as mock_session_cls, \
         patch("src.orchestrator.queue_manager.Authenticator") as mock_auth_cls:

        mock_session = MagicMock()
        mock_session.is_alive = True
        mock_session_cls.return_value = mock_session

        mock_auth = MagicMock()
        # Simula falha na autenticação
        mock_auth.authenticate.return_value = False
        mock_auth_cls.return_value = mock_auth

        run_consulta_batch(consulta.id)

    db_session.refresh(consulta)
    assert consulta.status == "ERRO_TOTAL"
    assert consulta.sucesso_empresas == 0
    assert consulta.erro_empresas == 1

    item = consulta.empresas_consulta[0]
    assert item.status == "ERRO"
    assert "Falha na autenticação" in item.erro_mensagem

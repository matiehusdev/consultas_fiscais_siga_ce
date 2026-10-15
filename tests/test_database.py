import pytest
from datetime import date
from src.database import crud
from src.database.models import Empresa, Consulta

def test_crud_empresa_success(db_session):
    empresa, err = crud.create_empresa(
        db=db_session,
        razao_social="Empresa Teste Fortaleza Ltda",
        cnpj="12.720.599/0001-17",
        cgf="06.123.456-7",
        observacao="Cliente VIP",
        ativa=True
    )
    assert err == ""
    assert empresa is not None
    assert empresa.id is not None
    assert empresa.razao_social == "Empresa Teste Fortaleza Ltda"
    assert empresa.cnpj == "12720599000117"
    assert empresa.cnpj_base == "12720599"
    assert empresa.ativa is True

def test_crud_empresa_duplicate_cnpj(db_session):
    crud.create_empresa(
        db=db_session,
        razao_social="Primeira Empresa",
        cnpj="12.720.599/0001-17"
    )
    # Tenta cadastrar novamente com o mesmo CNPJ
    empresa2, err = crud.create_empresa(
        db=db_session,
        razao_social="Segunda Empresa",
        cnpj="12.720.599/0001-17"
    )
    assert empresa2 is None
    assert "Já existe uma empresa cadastrada com o CNPJ" in err

def test_crud_empresa_invalid_cnpj(db_session):
    empresa, err = crud.create_empresa(
        db=db_session,
        razao_social="Empresa Invalida",
        cnpj="12.720.599/0001-99"
    )
    assert empresa is None
    assert "inválido" in err.lower()

def test_toggle_empresa_status(db_session):
    empresa, _ = crud.create_empresa(
        db=db_session,
        razao_social="Empresa Toggle",
        cnpj="00.000.000/0001-91",
        ativa=True
    )
    assert empresa.ativa is True

    empresa_toggled, _ = crud.toggle_empresa_status(db_session, empresa.id)
    assert empresa_toggled.ativa is False

    empresa_toggled2, _ = crud.toggle_empresa_status(db_session, empresa.id)
    assert empresa_toggled2.ativa is True

def test_list_and_search_empresas(db_session):
    crud.create_empresa(db=db_session, razao_social="Alfa Comercio", cnpj="00.000.000/0001-91", ativa=True)
    crud.create_empresa(db=db_session, razao_social="Beta Servicos", cnpj="33.000.167/0001-01", ativa=False)

    # Busca geral
    todas = crud.list_empresas(db_session)
    assert len(todas) == 2

    # Apenas ativas
    ativas = crud.list_empresas(db_session, apenas_ativas=True)
    assert len(ativas) == 1
    assert ativas[0].razao_social == "Alfa Comercio"

    # Busca por texto
    busca = crud.list_empresas(db_session, termo_busca="Beta")
    assert len(busca) == 1
    assert busca[0].razao_social == "Beta Servicos"

def test_create_consulta_batch(db_session):
    emp1, _ = crud.create_empresa(db=db_session, razao_social="Empresa 1", cnpj="00.000.000/0001-91")
    emp2, _ = crud.create_empresa(db=db_session, razao_social="Empresa 2", cnpj="33.000.167/0001-01")

    consulta, err = crud.create_consulta(
        db=db_session,
        empresas_ids=[emp1.id, emp2.id],
        data_inicio=date(2026, 1, 1),
        data_fim=date(2026, 9, 30),
        consultar_nfe=True,
        consultar_nfce=True,
        consultar_entradas=True,
        consultar_saidas=True
    )

    assert err == ""
    assert consulta is not None
    assert consulta.total_empresas == 2
    assert len(consulta.empresas_consulta) == 2
    assert consulta.status == "PENDENTE"

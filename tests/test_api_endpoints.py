import pytest

def test_api_stats_initial(client):
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_empresas" in data
    assert "total_consultas" in data

def test_api_create_and_list_empresa(client):
    # Criar nova empresa via API
    payload = {
        "razao_social": "Restaurante Beira Mar Ltda",
        "cnpj": "12.720.599/0001-17",
        "cgf": "06.999.888-1",
        "observacao": "Teste API",
        "ativa": True
    }
    create_resp = client.post("/api/empresas", json=payload)
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    assert created_data["razao_social"] == "Restaurante Beira Mar Ltda"
    assert created_data["cnpj"] == "12720599000117"

    # Listar empresas via API
    list_resp = client.get("/api/empresas")
    assert list_resp.status_code == 200
    empresas = list_resp.json()
    assert len(empresas) == 1
    assert empresas[0]["cnpj_base"] == "12720599"

def test_api_create_empresa_invalid_cnpj(client):
    payload = {
        "razao_social": "Empresa Errada",
        "cnpj": "12.720.599/0001-00",
        "ativa": True
    }
    resp = client.post("/api/empresas", json=payload)
    assert resp.status_code == 400
    data = resp.json()
    assert "inválido" in data["detail"].lower()

def test_api_pages_render(client):
    # As páginas HTML devem renderizar código 200
    assert client.get("/").status_code == 200
    assert client.get("/empresas").status_code == 200
    assert client.get("/consultas/nova").status_code == 200
    assert client.get("/historico").status_code == 200
    assert client.get("/configuracoes").status_code == 200

def test_api_create_consulta_triggers_execution(client):
    from unittest.mock import patch

    # 1. Cria empresa para a consulta
    emp_resp = client.post("/api/empresas", json={
        "razao_social": "Posto Cearense Ltda",
        "cnpj": "12.720.599/0001-17",
        "ativa": True
    })
    emp_id = emp_resp.json()["id"]

    # 2. Mocka trigger_consulta_async para validar chamada
    with patch("src.web.app.trigger_consulta_async", return_value=True) as mock_trigger:
        consulta_resp = client.post("/api/consultas", json={
            "empresas_ids": [emp_id],
            "data_inicio": "2026-01-01",
            "data_fim": "2026-09-30",
            "consultar_nfe": True,
            "consultar_nfce": False,
            "consultar_entradas": True,
            "consultar_saidas": True
        })
        assert consulta_resp.status_code == 201
        data = consulta_resp.json()
        assert data["status"] == "PENDENTE"
        assert data["execucao_iniciada"] is True
        mock_trigger.assert_called_once_with(data["id"])

def test_api_consulta_executar_e_detalhes(client):
    from unittest.mock import patch

    # Cria empresa e consulta
    emp_resp = client.post("/api/empresas", json={
        "razao_social": "Mercadinho São José Ltda",
        "cnpj": "12.720.599/0001-17",
        "ativa": True
    })
    emp_id = emp_resp.json()["id"]

    with patch("src.web.app.trigger_consulta_async", return_value=True):
        c_resp = client.post("/api/consultas", json={
            "empresas_ids": [emp_id],
            "data_inicio": "2026-01-01",
            "data_fim": "2026-06-30",
            "consultar_nfe": True,
            "consultar_nfce": True,
            "consultar_entradas": True,
            "consultar_saidas": True
        })
    consulta_id = c_resp.json()["id"]

    # Detalhes
    detalhes_resp = client.get(f"/api/consultas/{consulta_id}/detalhes")
    assert detalhes_resp.status_code == 200
    detalhes = detalhes_resp.json()
    assert detalhes["consulta"]["id"] == consulta_id
    assert len(detalhes["empresas"]) == 1
    assert detalhes["empresas"][0]["razao_social"] == "Mercadinho São José Ltda"

    # Executar
    with patch("src.web.app.trigger_consulta_async", return_value=True) as mock_exec:
        exec_resp = client.post(f"/api/consultas/{consulta_id}/executar")
        assert exec_resp.status_code == 200
        mock_exec.assert_called_once_with(consulta_id)

    # Repetir erros
    with patch("src.web.app.trigger_consulta_async", return_value=True) as mock_retry:
        retry_resp = client.post(f"/api/consultas/{consulta_id}/repetir-erros")
        assert retry_resp.status_code == 200
        mock_retry.assert_called_once_with(consulta_id)

    # Cancelar
    cancel_resp = client.post("/api/consultas/cancelar")
    assert cancel_resp.status_code == 200

def test_api_download_relatorios(client, tmp_path):
    from unittest.mock import patch
    from src.database import crud
    from src.database.connection import SessionLocal
    from src.config import settings

    # Cria empresa e consulta
    emp_resp = client.post("/api/empresas", json={
        "razao_social": "Drogaria Viva Bem Ltda",
        "cnpj": "12.720.599/0001-17",
        "ativa": True
    })
    emp_id = emp_resp.json()["id"]

    with patch("src.web.app.trigger_consulta_async", return_value=True):
        c_resp = client.post("/api/consultas", json={
            "empresas_ids": [emp_id],
            "data_inicio": "2026-09-01",
            "data_fim": "2026-09-30",
            "consultar_nfe": True,
            "consultar_nfce": True,
            "consultar_entradas": True,
            "consultar_saidas": True
        })
    consulta_id = c_resp.json()["id"]

    # Cria arquivos simulados no banco
    db = SessionLocal()
    detalhes = client.get(f"/api/consultas/{consulta_id}/detalhes").json()
    item_id = detalhes["empresas"][0]["id"]

    # Cria arquivos temporários reais no disco
    test_xl = settings.base_dir / "data" / "consultas" / "test_relatorio.xlsx"
    test_pdf = settings.base_dir / "data" / "consultas" / "test_relatorio.pdf"
    test_xl.parent.mkdir(parents=True, exist_ok=True)
    test_xl.write_bytes(b"PK fake excel")
    test_pdf.write_bytes(b"%PDF fake pdf")

    crud.create_arquivo_registro(
        db=db,
        consulta_empresa_id=item_id,
        tipo_arquivo="RELATORIO_LOTE_EXCEL",
        caminho_relativo=str(test_xl.relative_to(settings.base_dir)),
        hash_sha256="",
        tamanho_bytes=len(b"PK fake excel")
    )
    crud.create_arquivo_registro(
        db=db,
        consulta_empresa_id=item_id,
        tipo_arquivo="RELATORIO_LOTE_PDF",
        caminho_relativo=str(test_pdf.relative_to(settings.base_dir)),
        hash_sha256="",
        tamanho_bytes=len(b"%PDF fake pdf")
    )
    db.close()

    # Testa download direto de Excel
    resp_xl = client.get(f"/api/consultas/{consulta_id}/relatorio-excel")
    assert resp_xl.status_code == 200
    assert resp_xl.content == b"PK fake excel"

    # Testa download direto de PDF
    resp_pdf = client.get(f"/api/consultas/{consulta_id}/relatorio-pdf")
    assert resp_pdf.status_code == 200
    assert resp_pdf.content == b"%PDF fake pdf"

    # Limpeza
    if test_xl.exists(): test_xl.unlink()
    if test_pdf.exists(): test_pdf.unlink()

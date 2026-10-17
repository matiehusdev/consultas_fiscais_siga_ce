from contextlib import asynccontextmanager
from datetime import datetime, timezone, date
from typing import List, Optional
import threading
import queue
import json
import asyncio
from fastapi import FastAPI, Depends, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.config import settings
from src.database.connection import get_db, init_db, get_db_context
from src.database import crud
from src.siga.browser_session import BrowserSession
from src.siga.authentication import Authenticator, AuthStatusUpdate
from src.orchestrator.status_broadcaster import status_broadcaster
from src.orchestrator.queue_manager import (
    trigger_consulta_async,
    is_execution_running,
    stop_execution,
    get_active_consulta_id
)
from src.utils.cnpj_validator import format_cnpj
from src.utils.logger import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Giro Empresarial",
    description="Sistema de Gestão e Automação de Consultas Fiscais SEFAZ-CE com Certificado A1",
    version="1.0.0",
    lifespan=lifespan
)

# Templates Jinja2
templates = Jinja2Templates(directory=str(settings.base_dir / "src" / "web" / "templates"))

# Monta pasta static
app.mount("/static", StaticFiles(directory=str(settings.base_dir / "src" / "web" / "static")), name="static")

# ============================================================
# SCHEMAS PYDANTIC
# ============================================================

class EmpresaCreate(BaseModel):
    razao_social: str
    cnpj: str
    cgf: Optional[str] = None
    observacao: Optional[str] = None
    ativa: bool = True

class EmpresaUpdate(BaseModel):
    razao_social: Optional[str] = None
    cnpj: Optional[str] = None
    cgf: Optional[str] = None
    observacao: Optional[str] = None
    ativa: Optional[bool] = None

class ConsultaCreate(BaseModel):
    empresas_ids: List[int]
    data_inicio: date
    data_fim: date
    consultar_nfe: bool = True
    consultar_nfce: bool = True
    consultar_entradas: bool = True
    consultar_saidas: bool = True

class TestAuthRequest(BaseModel):
    empresa_id: Optional[int] = None
    razao_social: Optional[str] = None
    cnpj: Optional[str] = None

# ============================================================
# ROTAS HTML (INTERFACE WEB)
# ============================================================

@app.get("/", response_class=HTMLResponse)
def page_dashboard(request: Request, db: Session = Depends(get_db)):
    stats = crud.get_stats(db)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"active_page": "dashboard", "stats": stats}
    )

@app.get("/empresas", response_class=HTMLResponse)
def page_empresas(
    request: Request,
    busca: Optional[str] = None,
    filtro: str = "todas",
    db: Session = Depends(get_db)
):
    apenas_ativas = True if filtro == "ativas" else False if filtro == "inativas" else None
    empresas = crud.list_empresas(db, termo_busca=busca, apenas_ativas=apenas_ativas)
    return templates.TemplateResponse(
        request=request,
        name="empresas.html",
        context={
            "active_page": "empresas",
            "empresas": empresas,
            "termo_busca": busca,
            "filtro_status": filtro
        }
    )

@app.get("/consultas/nova", response_class=HTMLResponse)
def page_nova_consulta(request: Request, db: Session = Depends(get_db)):
    empresas = crud.list_empresas(db)
    return templates.TemplateResponse(
        request=request,
        name="nova_consulta.html",
        context={"active_page": "nova_consulta", "empresas": empresas}
    )

@app.get("/historico", response_class=HTMLResponse)
def page_historico(request: Request, db: Session = Depends(get_db)):
    consultas = crud.list_consultas(db)
    active_id = get_active_consulta_id()
    return templates.TemplateResponse(
        request=request,
        name="historico.html",
        context={
            "active_page": "historico",
            "consultas": consultas,
            "active_consulta_id": active_id,
            "is_running": is_execution_running()
        }
    )

@app.get("/configuracoes", response_class=HTMLResponse)
def page_configuracoes(request: Request, db: Session = Depends(get_db)):
    empresas = crud.list_empresas(db, apenas_ativas=True)
    return templates.TemplateResponse(
        request=request,
        name="configuracoes.html",
        context={"active_page": "configuracoes", "config": settings, "empresas": empresas}
    )

# ============================================================
# ROTAS DE API REST
# ============================================================

@app.get("/api/stats")
def api_get_stats(db: Session = Depends(get_db)):
    return crud.get_stats(db)

@app.get("/api/empresas")
def api_list_empresas(
    busca: Optional[str] = None,
    apenas_ativas: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    empresas = crud.list_empresas(db, termo_busca=busca, apenas_ativas=apenas_ativas)
    return [e.to_dict() for e in empresas]

@app.post("/api/empresas", status_code=status.HTTP_201_CREATED)
def api_create_empresa(payload: EmpresaCreate, db: Session = Depends(get_db)):
    empresa, err = crud.create_empresa(
        db,
        razao_social=payload.razao_social,
        cnpj=payload.cnpj,
        cgf=payload.cgf,
        observacao=payload.observacao,
        ativa=payload.ativa
    )
    if err:
        raise HTTPException(status_code=400, detail=err)
    return empresa.to_dict()

@app.get("/api/empresas/{empresa_id}")
def api_get_empresa(empresa_id: int, db: Session = Depends(get_db)):
    empresa = crud.get_empresa_by_id(db, empresa_id)
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")
    return empresa.to_dict()

@app.put("/api/empresas/{empresa_id}")
def api_update_empresa(empresa_id: int, payload: EmpresaUpdate, db: Session = Depends(get_db)):
    empresa, err = crud.update_empresa(
        db,
        empresa_id=empresa_id,
        razao_social=payload.razao_social,
        cnpj=payload.cnpj,
        cgf=payload.cgf,
        observacao=payload.observacao,
        ativa=payload.ativa
    )
    if err:
        raise HTTPException(status_code=400, detail=err)
    return empresa.to_dict()

@app.post("/api/empresas/{empresa_id}/toggle")
def api_toggle_empresa(empresa_id: int, db: Session = Depends(get_db)):
    empresa, err = crud.toggle_empresa_status(db, empresa_id)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return empresa.to_dict()

@app.delete("/api/empresas/{empresa_id}")
def api_delete_empresa(empresa_id: int, db: Session = Depends(get_db)):
    success, err = crud.delete_empresa(db, empresa_id)
    if not success:
        raise HTTPException(status_code=404, detail=err)
    return {"message": "Empresa excluída com sucesso."}

@app.post("/api/consultas", status_code=status.HTTP_201_CREATED)
def api_create_consulta(payload: ConsultaCreate, db: Session = Depends(get_db)):
    consulta, err = crud.create_consulta(
        db,
        empresas_ids=payload.empresas_ids,
        data_inicio=payload.data_inicio,
        data_fim=payload.data_fim,
        consultar_nfe=payload.consultar_nfe,
        consultar_nfce=payload.consultar_nfce,
        consultar_entradas=payload.consultar_entradas,
        consultar_saidas=payload.consultar_saidas
    )
    if err:
        raise HTTPException(status_code=400, detail=err)

    # Dispara a execução sequencial com o navegador Playwright imediatamente
    execucao_iniciada = trigger_consulta_async(consulta.id)
    result = consulta.to_dict()
    result["execucao_iniciada"] = execucao_iniciada
    return result

@app.get("/api/consultas")
def api_list_consultas(db: Session = Depends(get_db)):
    consultas = crud.list_consultas(db)
    return [c.to_dict() for c in consultas]

@app.post("/api/consultas/{consulta_id}/executar")
def api_executar_consulta(consulta_id: int, db: Session = Depends(get_db)):
    """Inicia ou retoma a execução de uma consulta pendente ou existente."""
    consulta = crud.get_consulta_by_id(db, consulta_id)
    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta não encontrada.")

    if is_execution_running():
        raise HTTPException(
            status_code=400,
            detail="Já existe uma consulta em execução no momento. Aguarde a finalização ou interrompa."
        )

    crud.reset_consulta_for_retry(db, consulta_id, only_errors=False)
    iniciada = trigger_consulta_async(consulta_id)
    if not iniciada:
        raise HTTPException(status_code=400, detail="Não foi possível disparar a execução da consulta.")

    return {"message": "Execução da consulta iniciada com sucesso.", "consulta_id": consulta_id}

@app.post("/api/consultas/{consulta_id}/repetir-erros")
def api_repetir_erros_consulta(consulta_id: int, db: Session = Depends(get_db)):
    """Reexecuta apenas as empresas que apresentaram erro na consulta."""
    consulta = crud.get_consulta_by_id(db, consulta_id)
    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta não encontrada.")

    if is_execution_running():
        raise HTTPException(
            status_code=400,
            detail="Já existe uma consulta em execução no momento."
        )

    crud.reset_consulta_for_retry(db, consulta_id, only_errors=True)
    iniciada = trigger_consulta_async(consulta_id)
    if not iniciada:
        raise HTTPException(status_code=400, detail="Não foi possível reiniciar a consulta para os erros.")

    return {"message": "Repetição iniciada apenas para as empresas com erro.", "consulta_id": consulta_id}

@app.post("/api/consultas/cancelar")
def api_cancelar_consulta():
    """Interrompe a execução da consulta em andamento e fecha o navegador."""
    if not is_execution_running():
        return {"message": "Nenhuma consulta em execução para cancelar."}
    stop_execution()
    return {"message": "Comando de interrupção enviado com sucesso."}

@app.get("/api/consultas/{consulta_id}/detalhes")
def api_get_consulta_detalhes(consulta_id: int, db: Session = Depends(get_db)):
    """Retorna detalhes completos da consulta e o status de cada empresa."""
    consulta = crud.get_consulta_by_id(db, consulta_id)
    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta não encontrada.")

    from decimal import Decimal
    from src.utils.date_helpers import format_periodo_mes

    empresas_info = []
    for it in consulta.empresas_consulta:
        nfe_s_val = Decimal("0.00")
        nfe_s_qtd = 0
        nfce_s_val = Decimal("0.00")
        nfce_s_qtd = 0
        nfe_e_val = Decimal("0.00")
        nfe_e_qtd = 0
        canc_val = Decimal("0.00")

        for r in it.resultados:
            val_aut = Decimal(str(r.valor_autorizado or 0))
            val_canc = Decimal(str(r.valor_cancelado or 0))
            qtd_aut = int(r.qtd_autorizada or 0)
            if r.tipo_documento == "NFE":
                if r.operacao == "SAIDA":
                    nfe_s_val += val_aut
                    nfe_s_qtd += qtd_aut
                else:
                    nfe_e_val += val_aut
                    nfe_e_qtd += qtd_aut
            elif r.tipo_documento == "NFCE":
                if r.operacao == "SAIDA":
                    nfce_s_val += val_aut
                    nfce_s_qtd += qtd_aut
            canc_val += val_canc

        tot_s_val = nfe_s_val + nfce_s_val
        tot_s_qtd = nfe_s_qtd + nfce_s_qtd

        empresas_info.append({
            "id": it.id,
            "empresa_id": it.empresa_id,
            "razao_social": it.empresa.razao_social,
            "cnpj": format_cnpj(it.empresa.cnpj),
            "status": it.status,
            "erro_mensagem": it.erro_mensagem,
            "iniciado_em": it.iniciado_em.strftime("%H:%M:%S") if it.iniciado_em else None,
            "finalizado_em": it.finalizado_em.strftime("%H:%M:%S") if it.finalizado_em else None,
            "tem_certificado": bool(it.empresa.certificado_caminho),
            "totais": {
                "nfe_saidas_val": float(nfe_s_val),
                "nfce_saidas_val": float(nfce_s_val),
                "total_saidas_val": float(tot_s_val),
                "total_saidas_qtd": tot_s_qtd,
                "total_entradas_val": float(nfe_e_val),
                "total_entradas_qtd": nfe_e_qtd,
                "total_canceladas_val": float(canc_val)
            }
        })

    active_id = get_active_consulta_id()
    arquivos_db = crud.list_arquivos_por_consulta(db, consulta_id)
    arquivos_info = []
    for a in arquivos_db:
        from pathlib import Path
        arquivos_info.append({
            "id": a.id,
            "tipo_arquivo": a.tipo_arquivo,
            "nome_arquivo": Path(a.caminho_relativo).name,
            "tamanho_bytes": a.tamanho_bytes,
            "criado_em": a.criado_em.strftime("%d/%m/%Y %H:%M:%S") if a.criado_em else ""
        })

    consulta_dict = consulta.to_dict()
    consulta_dict["periodo_formatado"] = format_periodo_mes(consulta.data_inicio, consulta.data_fim)

    return {
        "consulta": consulta_dict,
        "empresas": empresas_info,
        "arquivos": arquivos_info,
        "em_execucao": (is_execution_running() and active_id == consulta_id)
    }

@app.get("/api/arquivos/{arquivo_id}/download")
def api_download_arquivo(arquivo_id: int, db: Session = Depends(get_db)):
    """Permite download seguro de arquivos XLSX, PDF e Excel de relatórios."""
    from fastapi.responses import FileResponse
    from src.database.models import Arquivo
    arq = db.query(Arquivo).filter(Arquivo.id == arquivo_id).first()
    if not arq:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado no registro.")
    full_path = settings.base_dir / arq.caminho_relativo
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo físico não encontrado no servidor.")
    return FileResponse(path=str(full_path), filename=full_path.name)

@app.get("/api/consultas/{consulta_id}/relatorio-excel")
def api_download_relatorio_excel(consulta_id: int, db: Session = Depends(get_db)):
    """Permite download direto do Relatório Final em Excel da consulta."""
    from fastapi.responses import FileResponse
    from src.database.models import Arquivo, ConsultaEmpresa
    arq = (
        db.query(Arquivo)
        .join(ConsultaEmpresa, Arquivo.consulta_empresa_id == ConsultaEmpresa.id)
        .filter(ConsultaEmpresa.consulta_id == consulta_id)
        .filter(Arquivo.tipo_arquivo.in_(["RELATORIO_LOTE_EXCEL", "RELATORIO_EXCEL"]))
        .order_by(Arquivo.id.desc())
        .first()
    )
    if not arq:
        raise HTTPException(status_code=404, detail="Relatório Excel não encontrado para esta consulta.")
    full_path = settings.base_dir / arq.caminho_relativo
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo físico não encontrado no servidor.")
    return FileResponse(path=str(full_path), filename="relatorio_fiscal_consolidado.xlsx")

@app.get("/api/consultas/{consulta_id}/relatorio-pdf")
def api_download_relatorio_pdf(consulta_id: int, db: Session = Depends(get_db)):
    """Permite download direto do Relatório Final em PDF da consulta."""
    from fastapi.responses import FileResponse
    from src.database.models import Arquivo, ConsultaEmpresa
    arq = (
        db.query(Arquivo)
        .join(ConsultaEmpresa, Arquivo.consulta_empresa_id == ConsultaEmpresa.id)
        .filter(ConsultaEmpresa.consulta_id == consulta_id)
        .filter(Arquivo.tipo_arquivo.in_(["RELATORIO_LOTE_PDF", "RELATORIO_PDF"]))
        .order_by(Arquivo.id.desc())
        .first()
    )
    if not arq:
        raise HTTPException(status_code=404, detail="Relatório PDF não encontrado para esta consulta.")
    full_path = settings.base_dir / arq.caminho_relativo
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo físico não encontrado no servidor.")
    return FileResponse(path=str(full_path), filename="relatorio_fiscal_consolidado.pdf")

@app.post("/api/empresas/{empresa_id}/certificado")
async def api_upload_empresa_certificado(
    empresa_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    from fastapi import UploadFile, File
    form = await request.form()
    file: Optional[UploadFile] = form.get("certificado")
    senha: str = str(form.get("senha") or "")

    if not file:
        raise HTTPException(status_code=400, detail="Nenhum arquivo de certificado (.pfx/.p12) enviado.")
    if not senha:
        raise HTTPException(status_code=400, detail="A senha do certificado é obrigatória.")

    pfx_data = await file.read()
    success, err = crud.save_empresa_certificado(
        db,
        empresa_id=empresa_id,
        pfx_data=pfx_data,
        filename=file.filename or "certificado.pfx",
        passphrase=senha
    )
    if not success:
        raise HTTPException(status_code=400, detail=err)

    empresa = crud.get_empresa_by_id(db, empresa_id)
    return empresa.to_dict()

@app.delete("/api/empresas/{empresa_id}/certificado")
def api_delete_empresa_certificado(empresa_id: int, db: Session = Depends(get_db)):
    success, err = crud.remove_empresa_certificado(db, empresa_id)
    if not success:
        raise HTTPException(status_code=404, detail=err)
    return {"message": "Certificado digital removido com sucesso."}

# ============================================================
# ROTAS E PROCESSOS DA FASE 2: NAVEGADOR E AUTENTICAÇÃO
# ============================================================

_current_test_session: Optional[BrowserSession] = None

def _run_test_auth_worker(
    razao_social: str,
    cnpj: str,
    client_certs: Optional[List[dict]] = None
):
    global _current_test_session
    status_broadcaster.reset()
    modo_str = "Autônomo (com A1 anexado)" if client_certs else "Manual (janela do Windows)"
    status_broadcaster.publish(
        etapa="INICIANDO_NAVEGADOR",
        mensagem=f"Iniciando navegador para {razao_social} no modo {modo_str}...",
        empresa=razao_social,
        cnpj=cnpj,
        tipo_operacao="TESTE_AUTENTICACAO"
    )

    session = BrowserSession(headless=False, client_certificates=client_certs)
    _current_test_session = session
    authenticator = Authenticator(timeout_seconds=settings.certificate_selection_timeout_seconds)

    try:
        session.start()
        status_broadcaster.publish(
            etapa="NAVEGADOR_ABERTO",
            mensagem=f"Navegador aberto com sucesso. Carregando portal do SIGA ({modo_str})...",
            empresa=razao_social,
            cnpj=cnpj
        )

        def on_status_change(update: AuthStatusUpdate):
            status_broadcaster.publish(
                etapa=update.status,
                mensagem=update.mensagem,
                empresa=razao_social,
                cnpj=cnpj,
                acao_necessaria=update.acao_necessaria,
                acao_mensagem=update.mensagem if update.acao_necessaria else None
            )

        sucesso = authenticator.authenticate(
            session=session,
            empresa_razao_social=razao_social,
            empresa_cnpj=cnpj,
            on_status_change=on_status_change
        )

        if sucesso:
            status_broadcaster.publish(
                etapa="CONCLUIDO",
                mensagem="✓ Autenticação detectada com sucesso! A conexão com o SIGA está validada.",
                empresa=razao_social,
                cnpj=cnpj
            )
        else:
            status_broadcaster.publish(
                etapa="ERRO",
                mensagem="Falha na autenticação: tempo limite excedido ou navegador fechado.",
                empresa=razao_social,
                cnpj=cnpj
            )

    except Exception as e:
        logger.error(f"Exceção no teste de autenticação: {e}")
        status_broadcaster.publish(
            etapa="ERRO",
            mensagem=f"Erro inesperado: {str(e)}",
            empresa=razao_social,
            cnpj=cnpj
        )
    finally:
        session.close()
        _current_test_session = None

@app.post("/api/auth/test")
def api_test_auth(payload: TestAuthRequest, db: Session = Depends(get_db)):
    """Dispara teste de abertura de navegador e autenticação em segundo plano."""
    current_state = status_broadcaster.get_current_state()
    if current_state.get("ativo"):
        raise HTTPException(
            status_code=400,
            detail="Já existe uma operação com navegador em execução no momento."
        )

    razao = payload.razao_social or "Empresa de Teste"
    cnpj = payload.cnpj or "00.000.000/0001-00"
    client_certs = None

    if payload.empresa_id:
        empresa = crud.get_empresa_by_id(db, payload.empresa_id)
        if empresa:
            razao = empresa.razao_social
            cnpj = format_cnpj(empresa.cnpj)
            cert_dict = crud.get_empresa_client_certificate(db, payload.empresa_id)
            if isinstance(cert_dict, list):
                client_certs = cert_dict
            elif cert_dict:
                client_certs = [cert_dict]

    thread = threading.Thread(
        target=_run_test_auth_worker,
        args=(razao, cnpj, client_certs),
        daemon=True
    )
    thread.start()

    return {
        "message": "Teste de autenticação iniciado com sucesso.",
        "empresa": razao,
        "cnpj": cnpj,
        "modo_autonomo": bool(client_certs)
    }

@app.post("/api/auth/test/cancel")
def api_test_auth_cancel():
    """Cancela o teste de autenticação fechando o navegador."""
    global _current_test_session
    if _current_test_session and _current_test_session.is_alive:
        _current_test_session.close()
        _current_test_session = None
        status_broadcaster.publish(
            etapa="CANCELADO",
            mensagem="Operação cancelada pelo usuário."
        )
        return {"message": "Operação cancelada."}
    return {"message": "Nenhuma sessão ativa para cancelar."}

@app.get("/api/status/live")
def api_get_status_live():
    """Retorna estado e histórico recente da execução para polling do frontend."""
    return {
        "state": status_broadcaster.get_current_state(),
        "history": status_broadcaster.get_history(limit=30)
    }

@app.get("/api/status/stream")
async def api_status_stream():
    """Transmite eventos em tempo real via Server-Sent Events (SSE)."""
    q = status_broadcaster.subscribe()

    async def event_generator():
        try:
            # Envia estado inicial
            initial_state = status_broadcaster.get_current_state()
            yield f"data: {json.dumps(initial_state)}\n\n"

            while True:
                # Verifica a fila de eventos de forma não-bloqueante
                try:
                    event = q.get_nowait()
                    yield f"data: {json.dumps(event)}\n\n"
                except queue.Empty:
                    await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass
        finally:
            status_broadcaster.unsubscribe(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

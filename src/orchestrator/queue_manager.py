import threading
import time
from datetime import datetime, timezone
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.orm import Session

from src.database.connection import get_db_context
from src.database.models import Consulta, ConsultaEmpresa, Empresa
from src.database import crud
from src.siga.browser_session import BrowserSession
from src.siga.authentication import Authenticator, AuthStatusUpdate
from src.siga.contribuinte_selector import ContribuinteSelector
from src.siga.nfe_client import NFeClient
from src.siga.nfce_client import NFCeClient
from src.siga.ui_downloader import SigaUiDownloader
from src.processor import DocumentType, OperationType
from src.processor.nfe_processor import NFeProcessor
from src.processor.nfce_processor import NFCeProcessor
from src.processor.aggregator import FiscalAggregator
from decimal import Decimal
from src.reports.excel_reporter import ExcelReporter
from src.reports.pdf_reporter import PdfReporter
from src.reports.batch_reporter import BatchReporter, EmpresaResumoLote
from src.orchestrator.status_broadcaster import status_broadcaster
from src.utils.cnpj_validator import clean_cnpj, format_cnpj
from src.utils.date_helpers import matches_month, format_periodo_mes, NOMES_MESES
from src.utils.logger import logger
from src.config import settings

_active_execution_thread: Optional[threading.Thread] = None
_stop_execution_event = threading.Event()
_current_consulta_id: Optional[int] = None
_current_session: Optional[BrowserSession] = None

def is_execution_running() -> bool:
    """Verifica se há um lote sendo processado no momento."""
    global _active_execution_thread
    return _active_execution_thread is not None and _active_execution_thread.is_alive()

def get_active_consulta_id() -> Optional[int]:
    """Retorna o ID da consulta atualmente em execução, ou None se nenhuma estiver ativa."""
    global _current_consulta_id
    if is_execution_running():
        return _current_consulta_id
    return None

def stop_execution():
    """Sinaliza para interromper o processamento do lote atual e encerra o navegador ativo."""
    global _stop_execution_event, _current_session
    _stop_execution_event.set()
    if _current_session and _current_session.is_alive:
        try:
            _current_session.close()
        except Exception as e:
            logger.debug(f"Aviso ao encerrar sessão ativa na interrupção: {e}")

def _processar_documentos_empresa(
    session: BrowserSession,
    consulta_id: int,
    item_id: int,
    cnpj_limpo: str,
    razao: str,
    cnpj_fmt: str
) -> Tuple[bool, str]:
    """
    Executa as solicitações de download, acompanhamento de processamento e
    armazenamento dos arquivos XLSX de NF-e e NFC-e no SIGA.
    """
    with get_db_context() as db:
        consulta = db.query(Consulta).filter(Consulta.id == consulta_id).first()
        if not consulta:
            return False, "Consulta não encontrada no banco."
        data_inicio = consulta.data_inicio
        data_fim = consulta.data_fim
        id_lote = consulta.id_lote
        consultar_nfe = consulta.consultar_nfe
        consultar_nfce = consulta.consultar_nfce
        consultar_entradas = consulta.consultar_entradas
        consultar_saidas = consulta.consultar_saidas

    data_inicio_str = data_inicio.strftime("%Y-%m-%d")
    data_fim_str = data_fim.strftime("%Y-%m-%d")

    emp_dir = settings.consultas_dir / id_lote / cnpj_limpo
    emp_dir.mkdir(parents=True, exist_ok=True)

    tarefas = []
    if consultar_nfe:
        if consultar_saidas:
            tarefas.append(("NFE", "SAIDA"))
        if consultar_entradas:
            tarefas.append(("NFE", "ENTRADA"))

    if consultar_nfce:
        if consultar_saidas:
            tarefas.append(("NFCE", "SAIDA"))
        if consultar_entradas:
            tarefas.append(("NFCE", "ENTRADA"))

    nfe_client = NFeClient()
    nfce_client = NFCeClient()

    total_tarefas = len(tarefas)
    concluidas = 0
    erros = []

    for t_idx, (tipo_doc, operacao) in enumerate(tarefas, start=1):
        if _stop_execution_event.is_set():
            return False, "Execução cancelada pelo usuário."

        label_doc = "NF-e (Mod 55)" if tipo_doc == "NFE" else "NFC-e (Mod 65)"
        label_op = "Saídas" if operacao == "SAIDA" else "Entradas"

        status_broadcaster.publish(
            etapa=f"SOLICITANDO_{tipo_doc}_{operacao}",
            mensagem=f"[{t_idx}/{total_tarefas}] Solicitando {label_doc} - {label_op} para {razao}...",
            empresa=razao,
            cnpj=cnpj_fmt
        )

        with get_db_context() as db:
            sol_reg = crud.create_solicitacao(
                db=db,
                consulta_empresa_id=item_id,
                cnpj=cnpj_limpo,
                tipo_documento=tipo_doc,
                operacao=operacao,
                data_inicio=data_inicio,
                data_fim=data_fim,
                status_siga="SOLICITANDO"
            )
            sol_id = sol_reg.id

        nome_arquivo = f"{tipo_doc.lower()}_{operacao.lower()}.xlsx"
        arquivo_path = emp_dir / nome_arquivo

        download_sucesso = False
        hash_sha256 = ""
        tamanho = 0
        siga_id = None

        # Prioridade 1: Execução pela interface web visual comprovada nos prints 1, 2 e 3
        if session and session.is_alive:
            try:
                ui_downloader = SigaUiDownloader()
                status_broadcaster.publish(
                    etapa=f"SOLICITANDO_{tipo_doc}_{operacao}",
                    mensagem=f"[{t_idx}/{total_tarefas}] Solicitando {label_doc} - {label_op} via portal SIGA...",
                    empresa=razao,
                    cnpj=cnpj_fmt
                )
                ok_ui, hash_sha256, tamanho, err_ui = ui_downloader.solicitar_e_baixar(
                    session=session,
                    cnpj=cnpj_limpo,
                    tipo_doc=tipo_doc,
                    operacao=operacao,
                    ano=data_inicio.year,
                    destino_caminho=arquivo_path
                )
                if ok_ui:
                    download_sucesso = True
                    logger.info(f"Download concluído com sucesso via UI para {label_doc} {label_op}.")
                else:
                    logger.warning(f"UI Downloader não concluiu: {err_ui}. Tentando fallback via API...")
            except Exception as e:
                logger.warning(f"Exceção no UI Downloader: {e}. Tentando fallback via API...")

        # Prioridade 2: Fallback via API REST caso a sessão visual não esteja disponível ou tenha falhado
        if not download_sucesso:
            client = nfe_client if tipo_doc == "NFE" else nfce_client
            ok_sol, msg_sol, err_sol = client.solicitar_download(
                session=session,
                cnpj=cnpj_limpo,
                data_inicio=data_inicio_str,
                data_fim=data_fim_str,
                operacao=operacao
            )

            if not ok_sol:
                with get_db_context() as db:
                    crud.update_solicitacao_status(db, sol_id, status_siga="ERRO", erro_detalhe=err_sol)
                erros.append(f"{label_doc} {label_op}: {err_sol}")
                continue

            status_broadcaster.publish(
                etapa=f"AGUARDANDO_{tipo_doc}_{operacao}",
                mensagem=f"Aguardando processamento da SEFAZ para {label_doc} - {label_op}...",
                empresa=razao,
                cnpj=cnpj_fmt
            )

            ok_track, solicitacao_data, err_track = client.acompanhar_solicitacao(
                session=session,
                cnpj=cnpj_limpo,
                operacao=operacao,
                data_inicio=data_inicio_str,
                data_fim=data_fim_str,
                timeout_seconds=None
            )

            if not ok_track or not solicitacao_data:
                with get_db_context() as db:
                    crud.update_solicitacao_status(db, sol_id, status_siga="ERRO", erro_detalhe=err_track)
                erros.append(f"{label_doc} {label_op}: {err_track}")
                continue

            siga_id = solicitacao_data.get("id")
            with get_db_context() as db:
                crud.update_solicitacao_status(db, sol_id, status_siga="PROCESSANDO", id_solicitacao_siga=siga_id)

            status_broadcaster.publish(
                etapa=f"BAIXANDO_{tipo_doc}_{operacao}",
                mensagem=f"Baixando arquivo XLSX de {label_doc} - {label_op}...",
                empresa=razao,
                cnpj=cnpj_fmt
            )

            ok_down, hash_sha256, tamanho, err_down = client.baixar_arquivo(
                session=session,
                solicitacao_id=siga_id,
                destino_caminho=arquivo_path
            )

            if ok_down:
                download_sucesso = True
            else:
                with get_db_context() as db:
                    crud.update_solicitacao_status(db, sol_id, status_siga="ERRO", erro_detalhe=err_down)
                erros.append(f"{label_doc} {label_op}: {err_down}")
                continue

        if download_sucesso:
            caminho_rel = str(arquivo_path.relative_to(settings.base_dir))
            with get_db_context() as db:
                crud.update_solicitacao_status(db, sol_id, status_siga="CONCLUIDO", id_solicitacao_siga=siga_id)
                crud.create_arquivo_registro(
                    db=db,
                    consulta_empresa_id=item_id,
                    solicitacao_id=sol_id,
                    tipo_arquivo="ORIGINAL_XLSX",
                    caminho_relativo=caminho_rel,
                    hash_sha256=hash_sha256,
                    tamanho_bytes=tamanho
                )
            concluidas += 1
            status_broadcaster.publish(
                etapa=f"CONCLUIDO_{tipo_doc}_{operacao}",
                mensagem=f"✓ {label_doc} - {label_op} salvo com sucesso ({tamanho} bytes).",
                empresa=razao,
                cnpj=cnpj_fmt
            )

    # Fase 6 & 7: Processamento de dados e Geração de Relatórios
    if concluidas > 0:
        try:
            records_empresa = []
            nfe_proc = NFeProcessor()
            nfce_proc = NFCeProcessor()

            for (tipo_doc, operacao) in tarefas:
                nome_arq = f"{tipo_doc.lower()}_{operacao.lower()}.xlsx"
                caminho_arq = emp_dir / nome_arq
                if caminho_arq.exists():
                    op_enum = OperationType.SAIDA if operacao == "SAIDA" else OperationType.ENTRADA
                    if tipo_doc == "NFE":
                        recs = nfe_proc.processar_arquivo(caminho_arq, operacao=op_enum)
                    else:
                        recs = nfce_proc.processar_arquivo(caminho_arq, operacao=op_enum)

                    # Previne duplicação caso um arquivo tenha sido baixado com nome cruzado
                    if tipo_doc == "NFCE" and operacao == "ENTRADA":
                        if any(r.operacao == OperationType.SAIDA for r in recs) and (emp_dir / "nfce_saida.xlsx").exists():
                            logger.warning(f"Ignorando {nome_arq} pois seu conteúdo é de SAÍDA e nfce_saida.xlsx já existe.")
                            continue

                    # Filtro estrito: seleciona SOMENTE os registros correspondentes ao mês/ano da consulta
                    recs_filtrados = [
                        r for r in recs
                        if matches_month(r.mes, target_year=data_inicio.year, target_month=data_inicio.month)
                    ]
                    records_empresa.extend(recs_filtrados)

            status_broadcaster.publish(
                etapa="GERANDO_RELATORIOS",
                mensagem=f"Consolidando cálculos fiscais e gerando relatórios para {razao}...",
                empresa=razao,
                cnpj=cnpj_fmt
            )
            resumo_fiscal = FiscalAggregator.agregar(records_empresa)

            # Salva resultados tabulares agregados no banco
            with get_db_context() as db:
                quadros = [
                    resumo_fiscal.quadro_nfe_saidas,
                    resumo_fiscal.quadro_nfe_entradas,
                    resumo_fiscal.quadro_nfce_saidas,
                    resumo_fiscal.quadro_nfce_entradas
                ]
                salvou_algum = False
                for q in quadros:
                    for it in q.itens:
                        crud.save_resultado(
                            db=db,
                            consulta_empresa_id=item_id,
                            tipo_documento=q.tipo_documento.value,
                            operacao=q.operacao.value,
                            categoria=it.categoria,
                            mes=it.mes,
                            qtd_autorizada=it.quantidade_autorizada,
                            valor_autorizado=it.valor_autorizado,
                            qtd_cancelada=it.quantidade_cancelada,
                            valor_cancelado=it.valor_cancelado,
                            qtd_denegada=it.quantidade_denegada,
                            valor_denegado=it.valor_denegado
                        )
                        salvou_algum = True

                if not salvou_algum:
                    # Registra competência zerada no banco
                    nome_m = NOMES_MESES.get(data_inicio.month, f"Mês {data_inicio.month}")
                    crud.save_resultado(
                        db=db,
                        consulta_empresa_id=item_id,
                        tipo_documento="NFE",
                        operacao="SAIDA",
                        categoria="Geral",
                        mes=nome_m,
                        qtd_autorizada=0,
                        valor_autorizado=Decimal("0.00"),
                        qtd_cancelada=0,
                        valor_cancelado=Decimal("0.00"),
                        qtd_denegada=0,
                        valor_denegado=Decimal("0.00")
                    )

            periodo_txt = format_periodo_mes(data_inicio, data_fim)
            with get_db_context() as db:
                emp = db.query(Empresa).filter(Empresa.cnpj == cnpj_limpo).first()
                cgf_str = emp.cgf if emp else ""

            # Relatório Excel
            excel_path = emp_dir / "relatorio_consolidado.xlsx"
            ExcelReporter.gerar_relatorio(
                resumo=resumo_fiscal,
                razao_social=razao,
                cnpj=cnpj_limpo,
                periodo_str=periodo_txt,
                destino_caminho=excel_path
            )
            with get_db_context() as db:
                crud.create_arquivo_registro(
                    db=db,
                    consulta_empresa_id=item_id,
                    tipo_arquivo="RELATORIO_EXCEL",
                    caminho_relativo=str(excel_path.relative_to(settings.base_dir)),
                    hash_sha256="",
                    tamanho_bytes=excel_path.stat().st_size if excel_path.exists() else 0
                )

            # Relatório PDF
            pdf_path = emp_dir / "relatorio_fiscal.pdf"
            PdfReporter.gerar_relatorio(
                resumo=resumo_fiscal,
                razao_social=razao,
                cnpj=cnpj_limpo,
                cgf=cgf_str,
                periodo_str=periodo_txt,
                destino_caminho=pdf_path
            )
            with get_db_context() as db:
                crud.create_arquivo_registro(
                    db=db,
                    consulta_empresa_id=item_id,
                    tipo_arquivo="RELATORIO_PDF",
                    caminho_relativo=str(pdf_path.relative_to(settings.base_dir)),
                    hash_sha256="",
                    tamanho_bytes=pdf_path.stat().st_size if pdf_path.exists() else 0
                )

            status_broadcaster.publish(
                etapa="RELATORIOS_PRONTOS",
                mensagem=f"✓ Relatórios em Excel e PDF gerados com sucesso para {razao}!",
                empresa=razao,
                cnpj=cnpj_fmt
            )

        except Exception as e:
            logger.error(f"Erro ao processar relatórios para {razao}: {e}")

    if concluidas > 0:
        return True, ""
    elif erros:
        return False, " | ".join(erros[:2])
    else:
        return True, ""

def _gerar_relatorios_consolidados_lote(consulta_id: int):
    """
    Gera o Relatório Consolidado do Lote (Multi-Empresas) em Excel e PDF,
    apresentando os totais fiscais de cada empresa SOMENTE para o mês consultado.
    """
    try:
        with get_db_context() as db:
            consulta = db.query(Consulta).filter(Consulta.id == consulta_id).first()
            if not consulta or not consulta.empresas_consulta:
                return

            empresas_resumo: List[EmpresaResumoLote] = []
            primeiro_item_id = consulta.empresas_consulta[0].id
            periodo_txt = format_periodo_mes(consulta.data_inicio, consulta.data_fim)

            for item in consulta.empresas_consulta:
                razao = item.empresa.razao_social if item.empresa else ""
                cnpj = item.empresa.cnpj if item.empresa else ""

                nfe_s_val = Decimal("0.00")
                nfe_s_qtd = 0
                nfce_s_val = Decimal("0.00")
                nfce_s_qtd = 0
                nfe_e_val = Decimal("0.00")
                nfe_e_qtd = 0
                nfce_e_val = Decimal("0.00")
                nfce_e_qtd = 0
                canc_val = Decimal("0.00")

                for r in item.resultados:
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
                        else:
                            nfce_e_val += val_aut
                            nfce_e_qtd += qtd_aut

                    canc_val += val_canc

                tot_s_val = nfe_s_val + nfce_s_val
                tot_s_qtd = nfe_s_qtd + nfce_s_qtd
                tot_e_val = nfe_e_val + nfce_e_val
                tot_e_qtd = nfe_e_qtd + nfce_e_qtd

                status_label = "Concluído" if item.status == "CONCLUIDO" else ("Erro" if item.status == "ERRO" else item.status)

                empresas_resumo.append(EmpresaResumoLote(
                    razao_social=razao,
                    cnpj=cnpj,
                    nfe_saidas_val=nfe_s_val,
                    nfe_saidas_qtd=nfe_s_qtd,
                    nfce_saidas_val=nfce_s_val,
                    nfce_saidas_qtd=nfce_s_qtd,
                    total_saidas_val=tot_s_val,
                    total_saidas_qtd=tot_s_qtd,
                    nfe_entradas_val=nfe_e_val,
                    nfe_entradas_qtd=nfe_e_qtd,
                    total_canceladas_val=canc_val,
                    status=status_label,
                    nfce_entradas_val=nfce_e_val,
                    nfce_entradas_qtd=nfce_e_qtd,
                    total_entradas_val=tot_e_val,
                    total_entradas_qtd=tot_e_qtd
                ))

            lote_dir = settings.consultas_dir / consulta.id_lote
            lote_dir.mkdir(parents=True, exist_ok=True)

            excel_lote_path = lote_dir / "relatorio_lote_consolidado.xlsx"
            pdf_lote_path = lote_dir / "relatorio_lote_consolidado.pdf"

            ok_xl = BatchReporter.gerar_excel(
                empresas=empresas_resumo,
                lote_id=consulta.id,
                id_lote_str=consulta.id_lote,
                periodo_str=periodo_txt,
                destino_caminho=excel_lote_path
            )
            if ok_xl:
                crud.create_arquivo_registro(
                    db=db,
                    consulta_empresa_id=primeiro_item_id,
                    tipo_arquivo="RELATORIO_LOTE_EXCEL",
                    caminho_relativo=str(excel_lote_path.relative_to(settings.base_dir)),
                    hash_sha256="",
                    tamanho_bytes=excel_lote_path.stat().st_size if excel_lote_path.exists() else 0
                )

            ok_pdf = BatchReporter.gerar_pdf(
                empresas=empresas_resumo,
                lote_id=consulta.id,
                id_lote_str=consulta.id_lote,
                periodo_str=periodo_txt,
                destino_caminho=pdf_lote_path
            )
            if ok_pdf:
                crud.create_arquivo_registro(
                    db=db,
                    consulta_empresa_id=primeiro_item_id,
                    tipo_arquivo="RELATORIO_LOTE_PDF",
                    caminho_relativo=str(pdf_lote_path.relative_to(settings.base_dir)),
                    hash_sha256="",
                    tamanho_bytes=pdf_lote_path.stat().st_size if pdf_lote_path.exists() else 0
                )

    except Exception as e:
        logger.error(f"Erro ao gerar consolidação geral do lote #{consulta_id}: {e}")

def run_consulta_batch(consulta_id: int):
    """
    Executa o lote de consultas de forma sequencial empresa por empresa,
    garantindo sessões de navegador 100% isoladas e suporte a Certificado A1.
    """
    global _current_consulta_id, _current_session
    _current_consulta_id = consulta_id
    _stop_execution_event.clear()

    logger.info(f"Iniciando orquestrador para o Lote de Consulta #{consulta_id}...")

    try:
        with get_db_context() as db:
            consulta = db.query(Consulta).filter(Consulta.id == consulta_id).first()
            if not consulta:
                logger.error(f"Consulta #{consulta_id} não encontrada no banco.")
                return

            consulta.status = "EM_ANDAMENTO"
            db.commit()

            empresas_consulta = (
                db.query(ConsultaEmpresa)
                .filter(ConsultaEmpresa.consulta_id == consulta_id)
                .all()
            )

            total_empresas = len(empresas_consulta)
            sucesso_count = sum(1 for ec in empresas_consulta if ec.status == "CONCLUIDO")
            erro_count = 0

            status_broadcaster.reset()
            status_broadcaster.publish(
                etapa="INICIANDO_LOTE",
                mensagem=f"Iniciando processamento sequencial de {total_empresas} empresa(s)...",
                tipo_operacao="CONSULTA_LOTE"
            )

        # Itera empresa por empresa sequencialmente
        for idx, item_id in enumerate([ec.id for ec in empresas_consulta], start=1):
            if _stop_execution_event.is_set():
                logger.warning("Execução do lote interrompida pelo usuário.")
                break

            with get_db_context() as db:
                item = db.query(ConsultaEmpresa).filter(ConsultaEmpresa.id == item_id).first()
                if not item:
                    continue

                empresa = item.empresa
                razao = empresa.razao_social
                cnpj_limpo = clean_cnpj(empresa.cnpj)
                cnpj_fmt = format_cnpj(empresa.cnpj)

                # Se já foi concluído anteriormente (em caso de repetição de erros), pula
                if item.status == "CONCLUIDO":
                    logger.info(f"[{idx}/{total_empresas}] {razao} já concluído anteriormente. Pulando.")
                    continue

                item.status = "EM_ANDAMENTO"
                item.iniciado_em = datetime.now(timezone.utc)
                db.commit()

                # Obtém certificado A1 da empresa (se houver)
                client_cert = crud.get_empresa_client_certificate(db, empresa.id)
                if isinstance(client_cert, list):
                    client_certs = client_cert
                elif client_cert:
                    client_certs = [client_cert]
                else:
                    client_certs = None

            is_autonomo = bool(client_certs)
            modo_txt = "100% Autônomo (A1)" if is_autonomo else "Manual (Janela do Windows)"

            status_broadcaster.publish(
                etapa="EMPRESA_INICIADA",
                mensagem=f"[{idx}/{total_empresas}] Iniciando sessão para {razao} ({modo_txt})...",
                empresa=razao,
                cnpj=cnpj_fmt
            )

            # Inicia sessão isolada do navegador Playwright (visível na tela)
            session = BrowserSession(headless=False, client_certificates=client_certs)
            _current_session = session
            authenticator = Authenticator(timeout_seconds=settings.certificate_selection_timeout_seconds)

            empresa_sucesso = False
            erro_msg = ""

            try:
                session.start()
                status_broadcaster.publish(
                    etapa="NAVEGADOR_ABERTO",
                    mensagem=f"Navegador aberto para {razao}. Conectando ao SIGA SEFAZ-CE...",
                    empresa=razao,
                    cnpj=cnpj_fmt
                )

                def on_status_change(update: AuthStatusUpdate):
                    status_broadcaster.publish(
                        etapa=update.status,
                        mensagem=update.mensagem,
                        empresa=razao,
                        cnpj=cnpj_fmt,
                        acao_necessaria=update.acao_necessaria,
                        acao_mensagem=update.mensagem if update.acao_necessaria else None
                    )

                # Executa autenticação (autônoma se tiver A1, ou manual com orientação)
                autenticado = authenticator.authenticate(
                    session=session,
                    empresa_razao_social=razao,
                    empresa_cnpj=cnpj_fmt,
                    on_status_change=on_status_change
                )

                if autenticado:
                    status_broadcaster.publish(
                        etapa="AUTENTICADO",
                        mensagem=f"✓ Autenticação confirmada com sucesso para {razao}!",
                        empresa=razao,
                        cnpj=cnpj_fmt
                    )
                    time.sleep(1.0)

                    # Fase 3: Seleção do contribuinte no SIGA
                    status_broadcaster.publish(
                        etapa="SELECIONANDO_CONTRIBUINTE",
                        mensagem=f"Verificando seleção de unidade/contribuinte para {razao}...",
                        empresa=razao,
                        cnpj=cnpj_fmt
                    )
                    selector = ContribuinteSelector()
                    selector.selecionar_contribuinte(session, cnpj=cnpj_limpo, razao_social=razao)

                    # Fase 4: Processamento e download dos documentos fiscais
                    empresa_sucesso, erro_msg = _processar_documentos_empresa(
                        session=session,
                        consulta_id=consulta_id,
                        item_id=item_id,
                        cnpj_limpo=cnpj_limpo,
                        razao=razao,
                        cnpj_fmt=cnpj_fmt
                    )
                else:
                    erro_msg = "Falha na autenticação ou timeout de certificado."
                    status_broadcaster.publish(
                        etapa="ERRO",
                        mensagem=f"Falha na autenticação de {razao}.",
                        empresa=razao,
                        cnpj=cnpj_fmt
                    )

            except Exception as e:
                erro_msg = str(e)
                logger.error(f"Erro ao processar empresa {razao}: {e}")
                status_broadcaster.publish(
                    etapa="ERRO",
                    mensagem=f"Erro na empresa {razao}: {erro_msg}",
                    empresa=razao,
                    cnpj=cnpj_fmt
                )
            finally:
                # Encerra sessão do navegador da empresa atual
                session.close()
                _current_session = None
                status_broadcaster.publish(
                    etapa="SESSAO_ENCERRADA",
                    mensagem=f"Sessão de {razao} encerrada com segurança.",
                    empresa=razao,
                    cnpj=cnpj_fmt
                )

            # Atualiza status no banco de dados
            with get_db_context() as db:
                item = db.query(ConsultaEmpresa).filter(ConsultaEmpresa.id == item_id).first()
                if item:
                    item.finalizado_em = datetime.now(timezone.utc)
                    if empresa_sucesso:
                        item.status = "CONCLUIDO"
                        sucesso_count += 1
                    else:
                        item.status = "ERRO"
                        item.erro_mensagem = erro_msg
                        erro_count += 1
                    db.commit()

                consulta = db.query(Consulta).filter(Consulta.id == consulta_id).first()
                if consulta:
                    consulta.sucesso_empresas = sucesso_count
                    consulta.erro_empresas = erro_count
                    db.commit()

            # Pequeno intervalo antes de abrir a próxima empresa
            time.sleep(1)

        # Finalização do Lote
        with get_db_context() as db:
            consulta = db.query(Consulta).filter(Consulta.id == consulta_id).first()
            if consulta:
                consulta.finalizado_em = datetime.now(timezone.utc)
                if _stop_execution_event.is_set():
                    consulta.status = "CANCELADO"
                elif erro_count == 0 and sucesso_count == total_empresas:
                    consulta.status = "CONCLUIDO"
                elif sucesso_count > 0:
                    consulta.status = "ERRO_PARCIAL"
                else:
                    consulta.status = "ERRO_TOTAL"
                db.commit()

        # Gera o Relatório Consolidado do Lote (Multi-Empresas) se houver sucesso
        if sucesso_count > 0:
            _gerar_relatorios_consolidados_lote(consulta_id)

        status_broadcaster.publish(
            etapa="LOTE_FINALIZADO",
            mensagem=f"Lote finalizado: {sucesso_count} empresa(s) concluída(s) com sucesso, {erro_count} com erro.",
            tipo_operacao="CONSULTA_LOTE"
        )
        logger.info(f"Lote #{consulta_id} finalizado. Sucessos: {sucesso_count}, Erros: {erro_count}")

    finally:
        _current_consulta_id = None

def trigger_consulta_async(consulta_id: int) -> bool:
    """Dispara a execução do lote de consulta em uma thread de background."""
    global _active_execution_thread

    if is_execution_running():
        logger.warning("Já existe um lote de consulta em execução.")
        return False

    _active_execution_thread = threading.Thread(
        target=run_consulta_batch,
        args=(consulta_id,),
        daemon=True,
        name=f"Worker-Consulta-{consulta_id}"
    )
    _active_execution_thread.start()
    return True

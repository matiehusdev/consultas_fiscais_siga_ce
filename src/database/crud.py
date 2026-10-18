from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timezone, date
from decimal import Decimal
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc

from src.database.models import Empresa, Consulta, ConsultaEmpresa, Solicitacao, Arquivo, Resultado, LogSistema
from src.utils.cnpj_validator import validate_cnpj, clean_cnpj, extract_cnpj_base, format_cnpj
from src.utils.sanitizers import sanitize_text
from src.utils.logger import logger

def get_now():
    return datetime.now(timezone.utc)

# ============================================================
# EMPRESAS CRUD
# ============================================================

def create_empresa(
    db: Session,
    razao_social: str,
    cnpj: str,
    cgf: Optional[str] = None,
    observacao: Optional[str] = None,
    ativa: bool = True
) -> Tuple[Optional[Empresa], str]:
    """Cria uma nova empresa validando o CNPJ e garantindo unicidade."""
    is_valid, error_msg = validate_cnpj(cnpj)
    if not is_valid:
        return None, error_msg

    cleaned_cnpj = clean_cnpj(cnpj)
    existing = db.query(Empresa).filter(Empresa.cnpj == cleaned_cnpj).first()
    if existing:
        return None, f"Já existe uma empresa cadastrada com o CNPJ {format_cnpj(cleaned_cnpj)}."

    empresa = Empresa(
        razao_social=razao_social.strip(),
        cnpj=cleaned_cnpj,
        cnpj_base=extract_cnpj_base(cleaned_cnpj),
        cgf=cgf.strip() if cgf else None,
        observacao=observacao.strip() if observacao else None,
        ativa=ativa
    )
    db.add(empresa)
    db.commit()
    db.refresh(empresa)
    return empresa, ""

def get_empresa_by_id(db: Session, empresa_id: int) -> Optional[Empresa]:
    return db.query(Empresa).filter(Empresa.id == empresa_id).first()

def get_empresa_by_cnpj(db: Session, cnpj: str) -> Optional[Empresa]:
    cleaned = clean_cnpj(cnpj)
    return db.query(Empresa).filter(Empresa.cnpj == cleaned).first()

def list_empresas(
    db: Session,
    termo_busca: Optional[str] = None,
    apenas_ativas: Optional[bool] = None
) -> List[Empresa]:
    query = db.query(Empresa)

    if apenas_ativas is not None:
        query = query.filter(Empresa.ativa == apenas_ativas)

    if termo_busca:
        busca = f"%{termo_busca.strip()}%"
        busca_limpa = f"%{clean_cnpj(termo_busca)}%" if clean_cnpj(termo_busca) else busca
        query = query.filter(
            or_(
                Empresa.razao_social.ilike(busca),
                Empresa.cnpj.like(busca_limpa),
                Empresa.cgf.ilike(busca),
                Empresa.observacao.ilike(busca)
            )
        )

    return query.order_by(Empresa.razao_social.asc()).all()

def update_empresa(
    db: Session,
    empresa_id: int,
    razao_social: Optional[str] = None,
    cnpj: Optional[str] = None,
    cgf: Optional[str] = None,
    observacao: Optional[str] = None,
    ativa: Optional[bool] = None
) -> Tuple[Optional[Empresa], str]:
    empresa = get_empresa_by_id(db, empresa_id)
    if not empresa:
        return None, "Empresa não encontrada."

    if cnpj is not None:
        cleaned_cnpj = clean_cnpj(cnpj)
        if cleaned_cnpj != empresa.cnpj:
            is_valid, error_msg = validate_cnpj(cleaned_cnpj)
            if not is_valid:
                return None, error_msg

            existing = db.query(Empresa).filter(Empresa.cnpj == cleaned_cnpj, Empresa.id != empresa_id).first()
            if existing:
                return None, f"Já existe outra empresa com o CNPJ {format_cnpj(cleaned_cnpj)}."

            empresa.cnpj = cleaned_cnpj
            empresa.cnpj_base = extract_cnpj_base(cleaned_cnpj)

    if razao_social is not None:
        empresa.razao_social = razao_social.strip()
    if cgf is not None:
        empresa.cgf = cgf.strip() if cgf else None
    if observacao is not None:
        empresa.observacao = observacao.strip() if observacao else None
    if ativa is not None:
        empresa.ativa = ativa

    empresa.atualizado_em = get_now()
    db.commit()
    db.refresh(empresa)
    return empresa, ""

def toggle_empresa_status(db: Session, empresa_id: int) -> Tuple[Optional[Empresa], str]:
    empresa = get_empresa_by_id(db, empresa_id)
    if not empresa:
        return None, "Empresa não encontrada."
    empresa.ativa = not empresa.ativa
    empresa.atualizado_em = get_now()
    db.commit()
    db.refresh(empresa)
    return empresa, ""

def delete_empresa(db: Session, empresa_id: int) -> Tuple[bool, str]:
    empresa = get_empresa_by_id(db, empresa_id)
    if not empresa:
        return False, "Empresa não encontrada."
    
    # Remove arquivo de certificado se existir
    if empresa.certificado_caminho:
        remove_empresa_certificado(db, empresa_id)

    db.delete(empresa)
    db.commit()
    return True, ""

# ============================================================
# GESTÃO DE CERTIFICADOS DIGITAIS A1
# ============================================================

def save_empresa_certificado(
    db: Session,
    empresa_id: int,
    pfx_data: bytes,
    filename: str,
    passphrase: str
) -> Tuple[bool, str]:
    """Valida, moderniza (OpenSSL 3.0), armazena com segurança e vincula um Certificado A1 à empresa."""
    empresa = get_empresa_by_id(db, empresa_id)
    if not empresa:
        return False, "Empresa não encontrada."

    from src.utils.cert_parser import inspect_pfx, modernize_pfx
    from src.utils.crypto import encrypt_passphrase
    from src.config import settings

    is_valid, metadata, err = inspect_pfx(pfx_data, passphrase)
    if not is_valid:
        return False, err

    # Opcional: validação de CNPJ do certificado em relação à empresa
    if metadata.get("cnpj_extraido") and metadata["cnpj_extraido"] != empresa.cnpj:
        logger.warning(
            f"Aviso: CNPJ do certificado ({metadata['cnpj_extraido']}) "
            f"difere do CNPJ cadastrado da empresa ({empresa.cnpj})."
        )

    # Moderniza para padrão AES-256 (OpenSSL 3.0+ compatível com Chromium / Playwright)
    modern_bytes, modernized = modernize_pfx(pfx_data, passphrase)
    pfx_to_save = modern_bytes if modernized else pfx_data

    # Diretório seguro por empresa
    emp_cert_dir = settings.certificados_dir / empresa.cnpj
    emp_cert_dir.mkdir(parents=True, exist_ok=True)
    cert_path = emp_cert_dir / "certificado.pfx"

    with open(cert_path, "wb") as f:
        f.write(pfx_to_save)

    empresa.certificado_caminho = str(cert_path.relative_to(settings.base_dir))
    empresa.certificado_senha_hash = encrypt_passphrase(passphrase)
    empresa.certificado_nome = filename
    empresa.certificado_validade = metadata.get("validade")
    empresa.certificado_cn = metadata.get("common_name")
    empresa.atualizado_em = get_now()

    db.commit()
    db.refresh(empresa)
    return True, ""

def remove_empresa_certificado(db: Session, empresa_id: int) -> Tuple[bool, str]:
    """Desvincula e apaga com segurança o certificado digital da empresa."""
    empresa = get_empresa_by_id(db, empresa_id)
    if not empresa:
        return False, "Empresa não encontrada."

    from src.config import settings
    if empresa.certificado_caminho:
        full_path = settings.base_dir / empresa.certificado_caminho
        if full_path.exists():
            try:
                full_path.unlink()
            except Exception as e:
                logger.warning(f"Erro ao remover arquivo físico do certificado: {e}")

    empresa.certificado_caminho = None
    empresa.certificado_senha_hash = None
    empresa.certificado_nome = None
    empresa.certificado_validade = None
    empresa.certificado_cn = None
    empresa.atualizado_em = get_now()

    db.commit()
    db.refresh(empresa)
    return True, ""

def get_empresa_client_certificate(db: Session, empresa_id: int) -> Optional[dict]:
    """
    Retorna a estrutura ClientCertificate exigida pelo Playwright para autenticação automática,
    garantindo retroativamente a modernização de certificados antigos gravados no disco.
    """
    empresa = get_empresa_by_id(db, empresa_id)
    if not empresa or not empresa.certificado_caminho or not empresa.certificado_senha_hash:
        return None

    from src.utils.crypto import decrypt_passphrase
    from src.utils.cert_parser import modernize_pfx
    from src.config import settings

    full_path = settings.base_dir / empresa.certificado_caminho
    if not full_path.exists():
        logger.warning(f"Arquivo do certificado não encontrado no caminho: {full_path}")
        return None

    decrypted_pass = decrypt_passphrase(empresa.certificado_senha_hash)

    # Auto-modernização retroativa para arquivos já salvos em disco
    try:
        current_data = full_path.read_bytes()
        modern_data, modernized = modernize_pfx(current_data, decrypted_pass)
        if modernized:
            full_path.write_bytes(modern_data)
    except Exception as e:
        logger.warning(f"Aviso ao verificar modernização retroativa para {empresa.cnpj}: {e}")

    origins = [
        settings.siga_base_url,
        "https://sso.sefaz.ce.gov.br",
        "https://cert-sso.sefaz.ce.gov.br"
    ]

    return [
        {
            "origin": org,
            "pfxPath": str(full_path),
            "passphrase": decrypted_pass
        }
        for org in origins
    ]

def get_stats(db: Session) -> Dict[str, Any]:
    total_empresas = db.query(Empresa).count()
    empresas_ativas = db.query(Empresa).filter(Empresa.ativa == True).count()
    total_consultas = db.query(Consulta).count()
    ultima_consulta = db.query(Consulta).order_by(desc(Consulta.criado_em)).first()

    return {
        "total_empresas": total_empresas,
        "empresas_ativas": empresas_ativas,
        "empresas_inativas": total_empresas - empresas_ativas,
        "total_consultas": total_consultas,
        "ultima_consulta_data": ultima_consulta.criado_em.strftime("%d/%m/%Y %H:%M") if ultima_consulta else "Nenhuma"
    }

# ============================================================
# CONSULTAS E LOGS
# ============================================================

def create_consulta(
    db: Session,
    empresas_ids: List[int],
    data_inicio: date,
    data_fim: date,
    consultar_nfe: bool = True,
    consultar_nfce: bool = True,
    consultar_entradas: bool = True,
    consultar_saidas: bool = True
) -> Tuple[Optional[Consulta], str]:
    """Cria um registro de consulta em lote com suas empresas associadas."""
    if not empresas_ids:
        return None, "Selecione pelo menos uma empresa para a consulta."
    if not (consultar_nfe or consultar_nfce):
        return None, "Selecione pelo menos um tipo de documento (NF-e ou NFC-e)."
    if not (consultar_entradas or consultar_saidas):
        return None, "Selecione pelo menos uma operação (Entradas ou Saídas)."

    id_lote = str(uuid.uuid4())
    consulta = Consulta(
        id_lote=id_lote,
        data_inicio=data_inicio,
        data_fim=data_fim,
        consultar_nfe=consultar_nfe,
        consultar_nfce=consultar_nfce,
        consultar_entradas=consultar_entradas,
        consultar_saidas=consultar_saidas,
        status="PENDENTE",
        total_empresas=len(empresas_ids),
        sucesso_empresas=0,
        erro_empresas=0
    )
    db.add(consulta)
    db.flush()

    for emp_id in empresas_ids:
        item = ConsultaEmpresa(
            consulta_id=consulta.id,
            empresa_id=emp_id,
            status="PENDENTE"
        )
        db.add(item)

    db.commit()
    db.refresh(consulta)
    return consulta, ""

def list_consultas(db: Session, limit: int = 50) -> List[Consulta]:
    return db.query(Consulta).order_by(desc(Consulta.criado_em)).limit(limit).all()

def get_consulta_by_id(db: Session, consulta_id: int) -> Optional[Consulta]:
    """Retorna uma consulta pelo ID numérico."""
    return db.query(Consulta).filter(Consulta.id == consulta_id).first()

def get_consulta_by_lote(db: Session, id_lote: str) -> Optional[Consulta]:
    """Retorna uma consulta pelo identificador UUID do lote."""
    return db.query(Consulta).filter(Consulta.id_lote == id_lote).first()

def reset_consulta_for_retry(db: Session, consulta_id: int, only_errors: bool = True) -> bool:
    """Prepara uma consulta para reexecução, resetando itens com erro ou todos."""
    consulta = get_consulta_by_id(db, consulta_id)
    if not consulta:
        return False

    consulta.status = "PENDENTE"
    consulta.finalizado_em = None

    for item in consulta.empresas_consulta:
        if only_errors:
            if item.status in ("ERRO", "ERRO_PARCIAL", "PENDENTE"):
                item.status = "PENDENTE"
                item.erro_mensagem = None
                item.iniciado_em = None
                item.finalizado_em = None
        else:
            item.status = "PENDENTE"
            item.erro_mensagem = None
            item.iniciado_em = None
            item.finalizado_em = None

    sucesso_count = sum(1 for it in consulta.empresas_consulta if it.status == "CONCLUIDO")
    erro_count = sum(1 for it in consulta.empresas_consulta if it.status in ("ERRO", "ERRO_PARCIAL"))
    consulta.sucesso_empresas = sucesso_count
    consulta.erro_empresas = erro_count

    db.commit()
    return True

def save_log(db: Session, mensagem: str, nivel: str = "INFO", consulta_empresa_id: Optional[int] = None):
    """Grava log estruturado no banco com sanitização garantida."""
    msg_limpa = sanitize_text(mensagem)
    log_entry = LogSistema(
        consulta_empresa_id=consulta_empresa_id,
        nivel=nivel.upper(),
        mensagem=msg_limpa,
        timestamp=get_now()
    )
    db.add(log_entry)
    db.commit()

def create_solicitacao(
    db: Session,
    consulta_empresa_id: int,
    cnpj: str,
    tipo_documento: str,
    operacao: str,
    data_inicio: date,
    data_fim: date,
    id_solicitacao_siga: Optional[str] = None,
    status_siga: str = "CRIADA"
) -> Solicitacao:
    sol = Solicitacao(
        consulta_empresa_id=consulta_empresa_id,
        cnpj=cnpj,
        tipo_documento=tipo_documento.upper(),
        operacao=operacao.upper(),
        data_inicio=data_inicio,
        data_fim=data_fim,
        id_solicitacao_siga=id_solicitacao_siga,
        status_siga=status_siga,
        criado_em=get_now()
    )
    db.add(sol)
    db.commit()
    db.refresh(sol)
    return sol

def update_solicitacao_status(
    db: Session,
    solicitacao_id: int,
    status_siga: str,
    id_solicitacao_siga: Optional[str] = None,
    erro_detalhe: Optional[str] = None
) -> Optional[Solicitacao]:
    sol = db.query(Solicitacao).filter(Solicitacao.id == solicitacao_id).first()
    if not sol:
        return None
    sol.status_siga = status_siga
    if id_solicitacao_siga:
        sol.id_solicitacao_siga = id_solicitacao_siga
    if erro_detalhe:
        sol.erro_detalhe = sanitize_text(erro_detalhe)
    if status_siga == "CONCLUIDO":
        sol.concluido_em = get_now()
    db.commit()
    db.refresh(sol)
    return sol

def create_arquivo_registro(
    db: Session,
    consulta_empresa_id: int,
    tipo_arquivo: str,
    caminho_relativo: str,
    hash_sha256: str,
    tamanho_bytes: int,
    solicitacao_id: Optional[int] = None
) -> Arquivo:
    arq = Arquivo(
        solicitacao_id=solicitacao_id,
        consulta_empresa_id=consulta_empresa_id,
        tipo_arquivo=tipo_arquivo,
        caminho_relativo=caminho_relativo,
        hash_sha256=hash_sha256,
        tamanho_bytes=tamanho_bytes,
        criado_em=get_now()
    )
    db.add(arq)
    db.commit()
    db.refresh(arq)
    return arq

def save_resultado(
    db: Session,
    consulta_empresa_id: int,
    tipo_documento: str,
    operacao: str,
    categoria: str,
    mes: str,
    qtd_autorizada: int,
    valor_autorizado: Decimal,
    qtd_cancelada: int = 0,
    valor_cancelado: Decimal = Decimal("0.00"),
    qtd_denegada: int = 0,
    valor_denegado: Decimal = Decimal("0.00")
) -> Resultado:
    res = Resultado(
        consulta_empresa_id=consulta_empresa_id,
        tipo_documento=tipo_documento,
        operacao=operacao,
        categoria=categoria,
        mes=mes,
        qtd_autorizada=qtd_autorizada,
        valor_autorizado=float(valor_autorizado),
        qtd_cancelada=qtd_cancelada,
        valor_cancelado=float(valor_cancelado),
        qtd_denegada=qtd_denegada,
        valor_denegado=float(valor_denegado),
        criado_em=get_now()
    )
    db.add(res)
    db.commit()
    db.refresh(res)
    return res

def list_arquivos_por_consulta(db: Session, consulta_id: int) -> List[Arquivo]:
    """Retorna todos os arquivos (XLSX originais, relatórios PDF e Excel) gerados no lote."""
    return (
        db.query(Arquivo)
        .join(ConsultaEmpresa, Arquivo.consulta_empresa_id == ConsultaEmpresa.id)
        .filter(ConsultaEmpresa.consulta_id == consulta_id)
        .all()
    )

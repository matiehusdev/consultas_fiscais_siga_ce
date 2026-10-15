from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Date, 
    ForeignKey, Numeric
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def get_utc_now():
    return datetime.now(timezone.utc)

class Empresa(Base):
    __tablename__ = "empresas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    razao_social = Column(String(255), nullable=False)
    cnpj = Column(String(14), unique=True, nullable=False, index=True)
    cnpj_base = Column(String(8), nullable=False, index=True)
    cgf = Column(String(20), nullable=True)  # Cadastro Geral da Fazenda (SEFAZ-CE)
    observacao = Column(Text, nullable=True)
    ativa = Column(Boolean, default=True, index=True)
    
    # Certificado Digital A1
    certificado_caminho = Column(String(500), nullable=True)
    certificado_senha_hash = Column(String(500), nullable=True)
    certificado_nome = Column(String(255), nullable=True)
    certificado_validade = Column(DateTime, nullable=True)
    certificado_cn = Column(String(255), nullable=True)

    criado_em = Column(DateTime, default=get_utc_now)
    atualizado_em = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

    # Relacionamentos
    consultas_participadas = relationship("ConsultaEmpresa", back_populates="empresa", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "razao_social": self.razao_social,
            "cnpj": self.cnpj,
            "cnpj_base": self.cnpj_base,
            "cgf": self.cgf or "",
            "observacao": self.observacao or "",
            "ativa": self.ativa,
            "tem_certificado": bool(self.certificado_caminho),
            "certificado_nome": self.certificado_nome or "",
            "certificado_validade": self.certificado_validade.strftime("%d/%m/%Y") if self.certificado_validade else "",
            "certificado_cn": self.certificado_cn or "",
            "criado_em": self.criado_em.strftime("%d/%m/%Y %H:%M:%S") if self.criado_em else "",
            "atualizado_em": self.atualizado_em.strftime("%d/%m/%Y %H:%M:%S") if self.atualizado_em else "",
        }

class Consulta(Base):
    __tablename__ = "consultas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_lote = Column(String(36), unique=True, index=True, nullable=False)
    data_inicio = Column(Date, nullable=False)
    data_fim = Column(Date, nullable=False)
    consultar_nfe = Column(Boolean, default=True)
    consultar_nfce = Column(Boolean, default=True)
    consultar_entradas = Column(Boolean, default=True)
    consultar_saidas = Column(Boolean, default=True)
    status = Column(String(20), default="PENDENTE", index=True)  # PENDENTE, EM_ANDAMENTO, CONCLUIDO, ERRO_PARCIAL, ERRO_TOTAL
    total_empresas = Column(Integer, default=0)
    sucesso_empresas = Column(Integer, default=0)
    erro_empresas = Column(Integer, default=0)
    criado_em = Column(DateTime, default=get_utc_now)
    finalizado_em = Column(DateTime, nullable=True)

    # Relacionamentos
    empresas_consulta = relationship("ConsultaEmpresa", back_populates="consulta", cascade="all, delete-orphan")

    @property
    def empresas(self):
        return self.empresas_consulta

    def to_dict(self):
        return {
            "id": self.id,
            "id_lote": self.id_lote,
            "data_inicio": self.data_inicio.strftime("%d/%m/%Y") if self.data_inicio else "",
            "data_fim": self.data_fim.strftime("%d/%m/%Y") if self.data_fim else "",
            "consultar_nfe": self.consultar_nfe,
            "consultar_nfce": self.consultar_nfce,
            "consultar_entradas": self.consultar_entradas,
            "consultar_saidas": self.consultar_saidas,
            "status": self.status,
            "total_empresas": self.total_empresas,
            "sucesso_empresas": self.sucesso_empresas,
            "erro_empresas": self.erro_empresas,
            "criado_em": self.criado_em.strftime("%d/%m/%Y %H:%M:%S") if self.criado_em else "",
            "finalizado_em": self.finalizado_em.strftime("%d/%m/%Y %H:%M:%S") if self.finalizado_em else "",
        }

class ConsultaEmpresa(Base):
    __tablename__ = "consultas_empresas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    consulta_id = Column(Integer, ForeignKey("consultas.id"), nullable=False, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"), nullable=False, index=True)
    status = Column(String(30), default="PENDENTE", index=True)  # PENDENTE, AGUARDANDO_CERTIFICADO, EM_ANDAMENTO, CONCLUIDO, ERRO
    erro_mensagem = Column(Text, nullable=True)
    iniciado_em = Column(DateTime, nullable=True)
    finalizado_em = Column(DateTime, nullable=True)

    # Relacionamentos
    consulta = relationship("Consulta", back_populates="empresas_consulta")
    empresa = relationship("Empresa", back_populates="consultas_participadas")
    solicitacoes = relationship("Solicitacao", back_populates="consulta_empresa", cascade="all, delete-orphan")
    resultados = relationship("Resultado", back_populates="consulta_empresa", cascade="all, delete-orphan")
    arquivos = relationship("Arquivo", back_populates="consulta_empresa", cascade="all, delete-orphan")
    logs = relationship("LogSistema", back_populates="consulta_empresa", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "consulta_id": self.consulta_id,
            "empresa_id": self.empresa_id,
            "empresa_razao_social": self.empresa.razao_social if self.empresa else "",
            "empresa_cnpj": self.empresa.cnpj if self.empresa else "",
            "status": self.status,
            "erro_mensagem": self.erro_mensagem or "",
            "iniciado_em": self.iniciado_em.strftime("%d/%m/%Y %H:%M:%S") if self.iniciado_em else "",
            "finalizado_em": self.finalizado_em.strftime("%d/%m/%Y %H:%M:%S") if self.finalizado_em else "",
        }

class Solicitacao(Base):
    __tablename__ = "solicitacoes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    consulta_empresa_id = Column(Integer, ForeignKey("consultas_empresas.id"), nullable=True, index=True)
    cnpj = Column(String(14), nullable=False, index=True)
    tipo_documento = Column(String(10), nullable=False, index=True)  # NFE, NFCE
    operacao = Column(String(10), nullable=False, index=True)        # ENTRADA, SAIDA
    data_inicio = Column(Date, nullable=False)
    data_fim = Column(Date, nullable=False)
    id_solicitacao_siga = Column(String(100), nullable=True, index=True)  # UUID da SEFAZ
    status_siga = Column(String(20), default="CRIADA", index=True)  # CRIADA, PENDENTE, PROCESSANDO, CONCLUIDO, ERRO, EXPIRADO
    criado_em = Column(DateTime, default=get_utc_now)
    concluido_em = Column(DateTime, nullable=True)
    erro_detalhe = Column(Text, nullable=True)

    consulta_empresa = relationship("ConsultaEmpresa", back_populates="solicitacoes")
    arquivos = relationship("Arquivo", back_populates="solicitacao", cascade="all, delete-orphan")

class Arquivo(Base):
    __tablename__ = "arquivos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    solicitacao_id = Column(Integer, ForeignKey("solicitacoes.id"), nullable=True, index=True)
    consulta_empresa_id = Column(Integer, ForeignKey("consultas_empresas.id"), nullable=True, index=True)
    tipo_arquivo = Column(String(30), nullable=False)  # ORIGINAL_XLSX, RELATORIO_EXCEL, RELATORIO_PDF
    caminho_relativo = Column(String(500), nullable=False)
    hash_sha256 = Column(String(64), nullable=True)
    tamanho_bytes = Column(Integer, default=0)
    criado_em = Column(DateTime, default=get_utc_now)

    solicitacao = relationship("Solicitacao", back_populates="arquivos")
    consulta_empresa = relationship("ConsultaEmpresa", back_populates="arquivos")

class Resultado(Base):
    __tablename__ = "resultados"

    id = Column(Integer, primary_key=True, autoincrement=True)
    consulta_empresa_id = Column(Integer, ForeignKey("consultas_empresas.id"), nullable=False, index=True)
    tipo_documento = Column(String(10), nullable=False, index=True)  # NFE, NFCE
    operacao = Column(String(10), nullable=False, index=True)        # ENTRADA, SAIDA
    categoria = Column(String(50), nullable=False)                    # Interna, Interestadual, Externa
    mes = Column(String(20), nullable=False)                          # Janeiro, 2026-01
    qtd_autorizada = Column(Integer, default=0)
    valor_autorizado = Column(Numeric(15, 2), default=0.0)
    qtd_cancelada = Column(Integer, default=0)
    valor_cancelado = Column(Numeric(15, 2), default=0.0)
    qtd_denegada = Column(Integer, default=0)
    valor_denegado = Column(Numeric(15, 2), default=0.0)
    criado_em = Column(DateTime, default=get_utc_now)

    consulta_empresa = relationship("ConsultaEmpresa", back_populates="resultados")

class LogSistema(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    consulta_empresa_id = Column(Integer, ForeignKey("consultas_empresas.id"), nullable=True, index=True)
    nivel = Column(String(10), default="INFO", index=True)  # INFO, WARN, ERROR
    mensagem = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=get_utc_now, index=True)

    consulta_empresa = relationship("ConsultaEmpresa", back_populates="logs")

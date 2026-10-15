# Módulo processor
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

class DocumentType(str, Enum):
    NFE = "NFE"
    NFCE = "NFCE"

class OperationType(str, Enum):
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"

@dataclass
class NormalizedRecord:
    tipo_documento: DocumentType
    operacao: OperationType
    categoria: str          # ex: "Interna", "Interestadual", "Externa"
    mes: str                # ex: "Janeiro", "01/2026"
    quantidade_autorizada: int
    valor_autorizado: Decimal
    quantidade_cancelada: int
    valor_cancelado: Decimal
    quantidade_denegada: int
    valor_denegado: Decimal

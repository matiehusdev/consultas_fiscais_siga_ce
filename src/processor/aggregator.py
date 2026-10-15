from decimal import Decimal
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict

from src.processor import DocumentType, OperationType, NormalizedRecord

@dataclass
class ItemAgregado:
    mes: str
    categoria: str
    valor_autorizado: Decimal = Decimal("0.00")
    quantidade_autorizada: int = 0
    valor_cancelado: Decimal = Decimal("0.00")
    quantidade_cancelada: int = 0
    valor_denegado: Decimal = Decimal("0.00")
    quantidade_denegada: int = 0

@dataclass
class QuadroDemonstrativo:
    tipo_documento: DocumentType
    operacao: OperationType
    itens: List[ItemAgregado] = field(default_factory=list)
    total_valor_autorizado: Decimal = Decimal("0.00")
    total_quantidade_autorizada: int = 0
    total_valor_cancelado: Decimal = Decimal("0.00")
    total_quantidade_cancelada: int = 0
    total_valor_denegado: Decimal = Decimal("0.00")
    total_quantidade_denegada: int = 0

@dataclass
class LinhaConsolidada:
    operacao: str
    valor_nfe: Decimal = Decimal("0.00")
    qtd_nfe: int = 0
    valor_nfce: Decimal = Decimal("0.00")
    qtd_nfce: int = 0
    valor_total: Decimal = Decimal("0.00")
    qtd_total: int = 0

@dataclass
class ResumoFiscalConsolidado:
    quadro_nfe_saidas: QuadroDemonstrativo
    quadro_nfe_entradas: QuadroDemonstrativo
    quadro_nfce_saidas: QuadroDemonstrativo
    quadro_nfce_entradas: QuadroDemonstrativo
    linhas_consolidadas: List[LinhaConsolidada]

class FiscalAggregator:
    """
    Agregador contábil e auditor fiscal.
    Aplica rigorosamente o princípio:
    - Faturamento/Movimento baseia-se EXCLUSIVAMENTE em notas autorizadas.
    - Notas canceladas e denegadas são segregadas para auditoria.
    - NF-e e NFC-e são demonstradas em quadros independentes e consolidadas no final.
    """

    @classmethod
    def agregar(cls, records: List[NormalizedRecord]) -> ResumoFiscalConsolidado:
        # Agrupa por (tipo_doc, operacao, mes, categoria)
        grupos = defaultdict(lambda: {
            "valor_aut": Decimal("0.00"),
            "qtd_aut": 0,
            "valor_canc": Decimal("0.00"),
            "qtd_canc": 0,
            "valor_deneg": Decimal("0.00"),
            "qtd_deneg": 0
        })

        for r in records:
            key = (r.tipo_documento, r.operacao, r.mes, r.categoria)
            grupos[key]["valor_aut"] += r.valor_autorizado
            grupos[key]["qtd_aut"] += r.quantidade_autorizada
            grupos[key]["valor_canc"] += r.valor_cancelado
            grupos[key]["qtd_canc"] += r.quantidade_cancelada
            grupos[key]["valor_deneg"] += r.valor_denegado
            grupos[key]["qtd_deneg"] += r.quantidade_denegada

        def construir_quadro(tipo: DocumentType, op: OperationType) -> QuadroDemonstrativo:
            quadro = QuadroDemonstrativo(tipo_documento=tipo, operacao=op)
            itens_map = {}

            for (t, o, mes, cat), vals in grupos.items():
                if t == tipo and o == op:
                    item = ItemAgregado(
                        mes=mes,
                        categoria=cat,
                        valor_autorizado=vals["valor_aut"],
                        quantidade_autorizada=vals["qtd_aut"],
                        valor_cancelado=vals["valor_canc"],
                        quantidade_cancelada=vals["qtd_canc"],
                        valor_denegado=vals["valor_deneg"],
                        quantidade_denegada=vals["qtd_deneg"]
                    )
                    quadro.itens.append(item)
                    quadro.total_valor_autorizado += vals["valor_aut"]
                    quadro.total_quantidade_autorizada += vals["qtd_aut"]
                    quadro.total_valor_cancelado += vals["valor_canc"]
                    quadro.total_quantidade_cancelada += vals["qtd_canc"]
                    quadro.total_valor_denegado += vals["valor_deneg"]
                    quadro.total_quantidade_denegada += vals["qtd_deneg"]

            return quadro

        q_nfe_saidas = construir_quadro(DocumentType.NFE, OperationType.SAIDA)
        q_nfe_entradas = construir_quadro(DocumentType.NFE, OperationType.ENTRADA)
        q_nfce_saidas = construir_quadro(DocumentType.NFCE, OperationType.SAIDA)
        q_nfce_entradas = construir_quadro(DocumentType.NFCE, OperationType.ENTRADA)

        # Consolidação Geral (Quadro 3 de REPORTS.md)
        # Total = NF-e Autorizada + NFC-e Autorizada
        linha_saidas = LinhaConsolidada(
            operacao="Saídas",
            valor_nfe=q_nfe_saidas.total_valor_autorizado,
            qtd_nfe=q_nfe_saidas.total_quantidade_autorizada,
            valor_nfce=q_nfce_saidas.total_valor_autorizado,
            qtd_nfce=q_nfce_saidas.total_quantidade_autorizada,
            valor_total=q_nfe_saidas.total_valor_autorizado + q_nfce_saidas.total_valor_autorizado,
            qtd_total=q_nfe_saidas.total_quantidade_autorizada + q_nfce_saidas.total_quantidade_autorizada
        )

        linha_entradas = LinhaConsolidada(
            operacao="Entradas",
            valor_nfe=q_nfe_entradas.total_valor_autorizado,
            qtd_nfe=q_nfe_entradas.total_quantidade_autorizada,
            valor_nfce=q_nfce_entradas.total_valor_autorizado,
            qtd_nfce=q_nfce_entradas.total_quantidade_autorizada,
            valor_total=q_nfe_entradas.total_valor_autorizado + q_nfce_entradas.total_valor_autorizado,
            qtd_total=q_nfe_entradas.total_quantidade_autorizada + q_nfce_entradas.total_quantidade_autorizada
        )

        return ResumoFiscalConsolidado(
            quadro_nfe_saidas=q_nfe_saidas,
            quadro_nfe_entradas=q_nfe_entradas,
            quadro_nfce_saidas=q_nfce_saidas,
            quadro_nfce_entradas=q_nfce_entradas,
            linhas_consolidadas=[linha_saidas, linha_entradas]
        )

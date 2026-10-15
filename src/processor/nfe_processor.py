import re
from pathlib import Path
from decimal import Decimal
from typing import List, Optional
import pandas as pd
from openpyxl import load_workbook

from src.processor import DocumentType, OperationType, NormalizedRecord
from src.utils.logger import logger

def _parse_decimal(val) -> Decimal:
    """Converte valores variados (float, int, string R$, vírgulas) para Decimal seguro."""
    if val is None or pd.isna(val):
        return Decimal("0.00")
    if isinstance(val, (int, float)):
        return Decimal(str(round(val, 2)))
    if isinstance(val, Decimal):
        return val

    s = str(val).strip().replace("R$", "").replace(" ", "")
    # Tratamento de formato brasileiro: 1.234,56 -> 1234.56
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")

    try:
        return Decimal(s)
    except Exception:
        return Decimal("0.00")

def _parse_int(val) -> int:
    if val is None or pd.isna(val):
        return 0
    try:
        return int(float(val))
    except Exception:
        return 0

class NFeProcessor:
    """
    Processador de planilhas XLSX oficiais de NF-e (Modelo 55) do SIGA SEFAZ-CE.
    Extrai valores autorizados (regra primária), cancelados e denegados (auditoria).
    """

    def processar_arquivo(
        self,
        caminho_xlsx: Path,
        operacao: OperationType = OperationType.SAIDA
    ) -> List[NormalizedRecord]:
        """
        Lê e normaliza o arquivo XLSX de NF-e gerado pelo SIGA.
        """
        if not caminho_xlsx.exists():
            logger.error(f"Arquivo XLSX não encontrado: {caminho_xlsx}")
            return []

        logger.info(f"Processando planilha NF-e ({operacao.value}): {caminho_xlsx.name}...")
        records: List[NormalizedRecord] = []

        try:
            try:
                df = pd.read_excel(caminho_xlsx, sheet_name=0)
            except Exception:
                try:
                    df = pd.read_csv(caminho_xlsx, sep=";", encoding="utf-8-sig")
                except Exception:
                    df = pd.read_csv(caminho_xlsx, sep=",", encoding="utf-8-sig")

            if df.empty:
                logger.warning(f"Planilha {caminho_xlsx.name} está vazia.")
                return []

            # Normaliza nomes de colunas para busca flexível
            col_map = {col: str(col).strip().lower() for col in df.columns}

            for idx, row in df.iterrows():
                # Tenta identificar o mês/competência
                mes_val = None
                for orig_col, norm_col in col_map.items():
                    if any(k in norm_col for k in ["mês", "mes", "competência", "periodo", "referência", "referencia"]):
                        mes_val = str(row[orig_col]).strip()
                        break
                if not mes_val or mes_val.lower() in ("total", "nan", "none", ""):
                    mes_val = f"Linha {idx + 1}"

                # Categoria (Interna, Interestadual, Exterior ou Geral)
                categoria = "Geral"
                for orig_col, norm_col in col_map.items():
                    if any(k in norm_col for k in ["abrangência", "abrangencia", "destino", "categoria", "tipo"]):
                        cat_str = str(row[orig_col]).strip()
                        if cat_str and cat_str.lower() != "nan":
                            categoria = cat_str
                            break

                # Extração de valores e quantidades autorizadas (Regra Mandatória)
                val_aut = Decimal("0.00")
                qtd_aut = 0
                val_canc = Decimal("0.00")
                qtd_canc = 0
                val_deneg = Decimal("0.00")
                qtd_deneg = 0

                for orig_col, norm_col in col_map.items():
                    val = row[orig_col]
                    # Ignora colunas de percentual (ex: "qtd%", "val%")
                    if "%" in norm_col or "percent" in norm_col:
                        continue

                    # Autorizadas
                    if "autorizad" in norm_col:
                        if any(k in norm_col for k in ["qtd", "quant", "quantidade"]):
                            qtd_aut = _parse_int(val)
                        elif any(k in norm_col for k in ["val", "valor", "r$"]):
                            val_aut = _parse_decimal(val)
                    # Canceladas
                    elif "cancelad" in norm_col:
                        if any(k in norm_col for k in ["qtd", "quant", "quantidade"]):
                            qtd_canc = _parse_int(val)
                        elif any(k in norm_col for k in ["val", "valor", "r$"]):
                            val_canc = _parse_decimal(val)
                    # Denegadas
                    elif "denegad" in norm_col:
                        if any(k in norm_col for k in ["qtd", "quant", "quantidade"]):
                            qtd_deneg = _parse_int(val)
                        elif any(k in norm_col for k in ["val", "valor", "r$"]):
                            val_deneg = _parse_decimal(val)
                    # Fallback para colunas simples "Valor" / "Quantidade"
                    elif "valor" in norm_col and val_aut == Decimal("0.00") and "emitid" not in norm_col:
                        val_aut = _parse_decimal(val)
                    elif ("qtd" in norm_col or "quantidade" in norm_col) and qtd_aut == 0 and "emitid" not in norm_col:
                        qtd_aut = _parse_int(val)

                # Se a planilha tiver colunas divididas por região (Interna / Interestadual)
                # Verifica se há colunas como "Interna (R$)" ou "Interestadual (R$)"
                interna_col = next((c for c, n in col_map.items() if "interna" in n and ("val" in n or "r$" in n)), None)
                interestadual_col = next((c for c, n in col_map.items() if "interestadual" in n and ("val" in n or "r$" in n)), None)
                exterior_col = next((c for c, n in col_map.items() if ("exterior" in n or "externa" in n) and ("val" in n or "r$" in n)), None)

                if interna_col or interestadual_col:
                    if interna_col and not pd.isna(row[interna_col]):
                        v = _parse_decimal(row[interna_col])
                        records.append(NormalizedRecord(
                            tipo_documento=DocumentType.NFE,
                            operacao=operacao,
                            categoria="Interna",
                            mes=mes_val,
                            quantidade_autorizada=qtd_aut,
                            valor_autorizado=v,
                            quantidade_cancelada=qtd_canc,
                            valor_cancelado=val_canc,
                            quantidade_denegada=qtd_deneg,
                            valor_denegado=val_deneg
                        ))
                    if interestadual_col and not pd.isna(row[interestadual_col]):
                        v = _parse_decimal(row[interestadual_col])
                        records.append(NormalizedRecord(
                            tipo_documento=DocumentType.NFE,
                            operacao=operacao,
                            categoria="Interestadual",
                            mes=mes_val,
                            quantidade_autorizada=0,
                            valor_autorizado=v,
                            quantidade_cancelada=0,
                            valor_cancelado=Decimal("0.00"),
                            quantidade_denegada=0,
                            valor_denegado=Decimal("0.00")
                        ))
                    if exterior_col and not pd.isna(row[exterior_col]):
                        v = _parse_decimal(row[exterior_col])
                        records.append(NormalizedRecord(
                            tipo_documento=DocumentType.NFE,
                            operacao=operacao,
                            categoria="Exterior",
                            mes=mes_val,
                            quantidade_autorizada=0,
                            valor_autorizado=v,
                            quantidade_cancelada=0,
                            valor_cancelado=Decimal("0.00"),
                            quantidade_denegada=0,
                            valor_denegado=Decimal("0.00")
                        ))
                else:
                    records.append(NormalizedRecord(
                        tipo_documento=DocumentType.NFE,
                        operacao=operacao,
                        categoria=categoria,
                        mes=mes_val,
                        quantidade_autorizada=qtd_aut,
                        valor_autorizado=val_aut,
                        quantidade_cancelada=qtd_canc,
                        valor_cancelado=val_canc,
                        quantidade_denegada=qtd_deneg,
                        valor_denegado=val_deneg
                    ))

            logger.info(f"NF-e {caminho_xlsx.name}: {len(records)} registro(s) normalizado(s) extraído(s).")
            return records

        except Exception as e:
            logger.error(f"Erro ao processar XLSX NF-e {caminho_xlsx}: {e}")
            return []

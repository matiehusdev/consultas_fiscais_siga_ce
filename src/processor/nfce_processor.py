from pathlib import Path
from decimal import Decimal
from typing import List, Optional
import pandas as pd

from src.processor import DocumentType, OperationType, NormalizedRecord
from src.processor.nfe_processor import _parse_decimal, _parse_int, _load_dataframe_safely
from src.utils.cnpj_validator import clean_cnpj
from src.utils.logger import logger

class NFCeProcessor:
    """
    Processador de planilhas oficiais de NFC-e (Modelo 65) do SIGA SEFAZ-CE.
    Preserva a segregação estrita entre NF-e e NFC-e.
    """

    def processar_arquivo(
        self,
        caminho_xlsx: Path,
        operacao: OperationType = OperationType.SAIDA
    ) -> List[NormalizedRecord]:
        """
        Lê e normaliza a planilha XLSX de NFC-e com auto-detecção da operação real (Saídas vs Entradas).
        """
        if not caminho_xlsx.exists():
            logger.error(f"Arquivo XLSX de NFC-e não encontrado: {caminho_xlsx}")
            return []

        logger.info(f"Processando planilha NFC-e ({operacao.value}): {caminho_xlsx.name}...")
        records: List[NormalizedRecord] = []

        try:
            df = _load_dataframe_safely(caminho_xlsx)

            if df.empty:
                logger.warning(f"Planilha de NFC-e {caminho_xlsx.name} está vazia.")
                return []

            col_map = {col: str(col).strip().lower() for col in df.columns}
            is_analitico = any("chave" in c for c in col_map.values())

            # Auto-detecção de Operação (Saída vs Entrada) baseada no conteúdo real do arquivo:
            # 1. Se a coluna for "CNPJ/CPF destinatário", a empresa reportada é a emitente -> SAÍDA (venda a consumidor)
            # 2. Se a 44-digit Chave de Acesso contiver o CNPJ da empresa na posição [6:20], é emitente -> SAÍDA
            # 3. Se a coluna for "CNPJ/CPF emitente", a empresa é compradora -> ENTRADA
            operacao_efetiva = operacao
            if is_analitico:
                tem_col_destinatario = any("destinat" in c for c in col_map.values())
                tem_col_emitente = any("emit" in c for c in col_map.values())
                if tem_col_destinatario and not tem_col_emitente:
                    operacao_efetiva = OperationType.SAIDA
                elif tem_col_emitente and not tem_col_destinatario:
                    operacao_efetiva = OperationType.ENTRADA
                else:
                    # Verifica chave de acesso contra CNPJ da pasta da empresa
                    try:
                        cnpj_pasta = clean_cnpj(caminho_xlsx.parent.name)
                        if cnpj_pasta and len(cnpj_pasta) == 14:
                            for orig_col, norm_col in col_map.items():
                                if "chave" in norm_col:
                                    s_ch = df[orig_col].dropna().astype(str).tolist()
                                    if s_ch and len(s_ch[0]) >= 20:
                                        emitente_chave = s_ch[0][6:20]
                                        if emitente_chave == cnpj_pasta:
                                            operacao_efetiva = OperationType.SAIDA
                                        else:
                                            operacao_efetiva = OperationType.ENTRADA
                                    break
                    except Exception:
                        pass
            else:
                if "saida" in caminho_xlsx.name.lower():
                    operacao_efetiva = OperationType.SAIDA
                elif "entrada" in caminho_xlsx.name.lower():
                    operacao_efetiva = OperationType.ENTRADA

            for idx, row in df.iterrows():
                # Competência / Mês
                mes_val = None
                for orig_col, norm_col in col_map.items():
                    if any(k in norm_col for k in ["data de emissão", "data de emissao", "data emissão", "data emissao", "emissão", "emissao", "mês", "mes", "competência", "competencia", "periodo", "período"]):
                        val_str = str(row[orig_col]).strip()
                        if val_str and val_str.lower() not in ("nan", "none", ""):
                            # Se for data completa YYYY-MM-DD ou DD/MM/YYYY, extrai ano-mês
                            if "-" in val_str and len(val_str) >= 7:
                                mes_val = val_str[:7]
                            elif "/" in val_str and len(val_str) >= 7:
                                partes = val_str.split("/")
                                if len(partes) == 3:
                                    mes_val = f"{partes[2]}-{partes[1]}"
                                else:
                                    mes_val = val_str
                            else:
                                mes_val = val_str
                            break
                if not mes_val or mes_val.lower() in ("total", "nan", "none", ""):
                    mes_val = f"Linha {idx + 1}"

                # Categoria / Detalhe
                categoria = "Venda a Consumidor (NFC-e)" if operacao_efetiva == OperationType.SAIDA else "Devolução / Entrada (NFC-e)"
                for orig_col, norm_col in col_map.items():
                    if any(k in norm_col for k in ["detalhe", "categoria", "tipo", "descricao", "descrição"]):
                        cat_str = str(row[orig_col]).strip()
                        if cat_str and cat_str.lower() != "nan":
                            categoria = cat_str
                            break

                val_aut = Decimal("0.00")
                qtd_aut = 0
                val_canc = Decimal("0.00")
                qtd_canc = 0
                val_deneg = Decimal("0.00")
                qtd_deneg = 0

                if is_analitico:
                    # Em listagem analítica nota a nota, a linha é 1 nota autorizada
                    qtd_aut = 1
                    for orig_col, norm_col in col_map.items():
                        if norm_col == "valor r$" or (norm_col.startswith("valor") and "icms" not in norm_col and "base" not in norm_col):
                            val_aut = _parse_decimal(row[orig_col])
                            break
                else:
                    for orig_col, norm_col in col_map.items():
                        val = row[orig_col]
                        if "autorizad" in norm_col:
                            if any(k in norm_col for k in ["qtd", "quant", "quantidade"]):
                                qtd_aut = _parse_int(val)
                            elif any(k in norm_col for k in ["val", "valor", "r$"]):
                                val_aut = _parse_decimal(val)
                        elif "cancelad" in norm_col:
                            if any(k in norm_col for k in ["qtd", "quant", "quantidade"]):
                                qtd_canc = _parse_int(val)
                            elif any(k in norm_col for k in ["val", "valor", "r$"]):
                                val_canc = _parse_decimal(val)
                        elif "denegad" in norm_col:
                            if any(k in norm_col for k in ["qtd", "quant", "quantidade"]):
                                qtd_deneg = _parse_int(val)
                            elif any(k in norm_col for k in ["val", "valor", "r$"]):
                                val_deneg = _parse_decimal(val)
                        elif "valor" in norm_col and val_aut == Decimal("0.00") and "emitid" not in norm_col:
                            val_aut = _parse_decimal(val)
                        elif ("qtd" in norm_col or "quantidade" in norm_col) and qtd_aut == 0 and "emitid" not in norm_col:
                            qtd_aut = _parse_int(val)

                records.append(NormalizedRecord(
                    tipo_documento=DocumentType.NFCE,
                    operacao=operacao_efetiva,
                    categoria=categoria,
                    mes=mes_val,
                    quantidade_autorizada=qtd_aut,
                    valor_autorizado=val_aut,
                    quantidade_cancelada=qtd_canc,
                    valor_cancelado=val_canc,
                    quantidade_denegada=qtd_deneg,
                    valor_denegado=val_deneg
                ))

            logger.info(f"NFC-e {caminho_xlsx.name}: {len(records)} registro(s) normalizado(s) extraído(s).")
            return records

        except Exception as e:
            logger.error(f"Erro ao processar XLSX NFC-e {caminho_xlsx}: {e}")
            return []

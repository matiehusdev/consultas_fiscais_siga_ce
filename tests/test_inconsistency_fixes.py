import io
import hashlib
from datetime import date
from decimal import Decimal
from pathlib import Path
import pandas as pd
import pytest

from src.processor import DocumentType, OperationType, NormalizedRecord
from src.processor.nfe_processor import NFeProcessor
from src.processor.nfce_processor import NFCeProcessor
from src.utils.date_helpers import clean_date_str, matches_month, matches_period

def test_clean_date_str_various_formats():
    assert clean_date_str("20/08/2026 14:32:10") == "20/08/2026"
    assert clean_date_str("2026-08-20T14:32:10.000Z") == "2026-08-20"
    assert clean_date_str("2026-08-20 14:32") == "2026-08-20"
    assert clean_date_str("Setembro/2026") == "Setembro/2026"
    assert clean_date_str("09/2026") == "09/2026"
    assert clean_date_str(date(2026, 9, 1)) == "2026-09-01"

def test_matches_month_resilience():
    # Com timestamp
    assert matches_month("20/08/2026 14:32:10", 2026, 8) is True
    assert matches_month("2026-09-15 10:00:00", 2026, 9) is True
    # Numérico
    assert matches_month("9", 2026, 9) is True
    assert matches_month("09", 2026, 9) is True
    assert matches_month("Mês 9", 2026, 9) is True
    assert matches_month("mes 09", 2026, 9) is True
    # Rejeição
    assert matches_month("20/08/2026 14:32:10", 2026, 9) is False
    assert matches_month("Setembro/2025", 2026, 9) is False

def test_matches_period():
    d_ini = date(2026, 8, 1)
    d_fim = date(2026, 10, 31)
    assert matches_period("Agosto", d_ini, d_fim) is True
    assert matches_period("Setembro", d_ini, d_fim) is True
    assert matches_period("Outubro", d_ini, d_fim) is True
    assert matches_period("Julho", d_ini, d_fim) is False
    assert matches_period("Novembro", d_ini, d_fim) is False

def test_nfce_processor_with_timestamp_dates(tmp_path):
    # Simula planilha de NFC-e analítica da SEFAZ com datas contendo horários
    df = pd.DataFrame({
        "CNPJ/CPF destinatário": ["***.123.456-**", "***.987.654-**"],
        "Chave de acesso": [
            "23260814869652000171650010000100931000100230",
            "23260814869652000171650010000100941000100240"
        ],
        "Data de emissão": ["20/08/2026 14:32:10", "25/08/2026 18:45:00"],
        "Base de cálculo do ICMS R$": ["0,00", "0,00"],
        "Valor do ICMS R$": ["0,00", "0,00"],
        "Valor R$": ["150,50", "49,50"]
    })
    caminho = tmp_path / "nfce_saida.xlsx"
    df.to_excel(caminho, index=False)

    proc = NFCeProcessor()
    recs = proc.processar_arquivo(caminho, operacao=OperationType.SAIDA)

    assert len(recs) == 2
    assert recs[0].mes == "2026-08"
    assert recs[1].mes == "2026-08"
    assert recs[0].valor_autorizado == Decimal("150.50")
    assert recs[1].valor_autorizado == Decimal("49.50")

    # Garante que o filtro por mês identifica perfeitamente
    recs_filtrados = [r for r in recs if matches_month(r.mes, 2026, 8)]
    assert len(recs_filtrados) == 2
    assert sum(r.valor_autorizado for r in recs_filtrados) == Decimal("200.00")

def test_nfe_processor_does_not_capture_icms_as_val_aut(tmp_path):
    # Simula planilha com coluna de valor de ICMS onde autorizada é 0
    df = pd.DataFrame({
        "mês": ["Setembro"],
        "tipo": ["Interna"],
        "qtd NF-e emitidas autorizadas": [0],
        "valor R$ NF-e emitidas autorizadas": ["0,00"],
        "valor do ICMS R$": ["1500,00"]
    })
    caminho = tmp_path / "nfe_saida.xlsx"
    df.to_excel(caminho, index=False)

    proc = NFeProcessor()
    recs = proc.processar_arquivo(caminho, operacao=OperationType.SAIDA)
    assert len(recs) == 1
    # Não deve ter puxado os 1500 de ICMS como valor autorizado
    assert recs[0].valor_autorizado == Decimal("0.00")

import pytest
from pathlib import Path
from decimal import Decimal
import pandas as pd
from openpyxl import Workbook

from src.processor import DocumentType, OperationType, NormalizedRecord
from src.processor.nfe_processor import NFeProcessor
from src.processor.nfce_processor import NFCeProcessor
from src.processor.aggregator import FiscalAggregator
from src.reports.excel_reporter import ExcelReporter
from src.reports.pdf_reporter import PdfReporter

def test_nfe_processor_reads_spreadsheet(tmp_path):
    # Cria arquivo XLSX simulando saída da SEFAZ-CE
    xlsx_path = tmp_path / "nfe_saida.xlsx"
    df = pd.DataFrame([
        {
            "Mês": "Janeiro/2026",
            "Abrangência": "Interna",
            "Qtd Autorizadas": 100,
            "Valor Autorizadas": "15.000,50",
            "Qtd Canceladas": 5,
            "Valor Canceladas": "500,00",
            "Qtd Denegadas": 1,
            "Valor Denegadas": "100,00"
        },
        {
            "Mês": "Fevereiro/2026",
            "Abrangência": "Interestadual",
            "Qtd Autorizadas": 50,
            "Valor Autorizadas": "25.000,00",
            "Qtd Canceladas": 2,
            "Valor Canceladas": "200,00",
            "Qtd Denegadas": 0,
            "Valor Denegadas": "0,00"
        }
    ])
    df.to_excel(xlsx_path, index=False)

    processor = NFeProcessor()
    records = processor.processar_arquivo(xlsx_path, operacao=OperationType.SAIDA)

    assert len(records) == 2
    assert records[0].tipo_documento == DocumentType.NFE
    assert records[0].operacao == OperationType.SAIDA
    assert records[0].categoria == "Interna"
    assert records[0].quantidade_autorizada == 100
    assert records[0].valor_autorizado == Decimal("15000.50")
    assert records[0].quantidade_cancelada == 5
    assert records[0].valor_cancelado == Decimal("500.00")

def test_nfce_processor_reads_spreadsheet(tmp_path):
    xlsx_path = tmp_path / "nfce_saida.xlsx"
    df = pd.DataFrame([
        {
            "Competência": "Janeiro/2026",
            "Detalhe": "Venda Consumidor",
            "Qtd Autorizadas": 200,
            "Valor Autorizadas": "8.500,00",
            "Qtd Canceladas": 10,
            "Valor Canceladas": "400,00"
        }
    ])
    df.to_excel(xlsx_path, index=False)

    processor = NFCeProcessor()
    records = processor.processar_arquivo(xlsx_path, operacao=OperationType.SAIDA)

    assert len(records) == 1
    assert records[0].tipo_documento == DocumentType.NFCE
    assert records[0].quantidade_autorizada == 200
    assert records[0].valor_autorizado == Decimal("8500.00")

def test_fiscal_aggregator_authorized_totals():
    records = [
        NormalizedRecord(
            tipo_documento=DocumentType.NFE,
            operacao=OperationType.SAIDA,
            categoria="Interna",
            mes="Janeiro",
            quantidade_autorizada=10,
            valor_autorizado=Decimal("1000.00"),
            quantidade_cancelada=2,
            valor_cancelado=Decimal("200.00"),
            quantidade_denegada=0,
            valor_denegado=Decimal("0.00")
        ),
        NormalizedRecord(
            tipo_documento=DocumentType.NFCE,
            operacao=OperationType.SAIDA,
            categoria="Venda",
            mes="Janeiro",
            quantidade_autorizada=20,
            valor_autorizado=Decimal("500.00"),
            quantidade_cancelada=1,
            valor_cancelado=Decimal("50.00"),
            quantidade_denegada=0,
            valor_denegado=Decimal("0.00")
        )
    ]

    resumo = FiscalAggregator.agregar(records)

    # Saídas consolidadas
    saida = next(l for l in resumo.linhas_consolidadas if l.operacao == "Saídas")
    assert saida.valor_nfe == Decimal("1000.00")
    assert saida.qtd_nfe == 10
    assert saida.valor_nfce == Decimal("500.00")
    assert saida.qtd_nfce == 20
    assert saida.valor_total == Decimal("1500.00")
    assert saida.qtd_total == 30

    # Auditoria segregada em NF-e Saídas
    assert resumo.quadro_nfe_saidas.total_valor_cancelado == Decimal("200.00")
    assert resumo.quadro_nfe_saidas.total_quantidade_cancelada == 2

def test_excel_and_pdf_generation(tmp_path):
    records = [
        NormalizedRecord(
            tipo_documento=DocumentType.NFE,
            operacao=OperationType.SAIDA,
            categoria="Interna",
            mes="Janeiro/2026",
            quantidade_autorizada=15,
            valor_autorizado=Decimal("3000.00"),
            quantidade_cancelada=1,
            valor_cancelado=Decimal("100.00"),
            quantidade_denegada=0,
            valor_denegado=Decimal("0.00")
        ),
        NormalizedRecord(
            tipo_documento=DocumentType.NFE,
            operacao=OperationType.ENTRADA,
            categoria="Interna",
            mes="Janeiro/2026",
            quantidade_autorizada=5,
            valor_autorizado=Decimal("1200.00"),
            quantidade_cancelada=0,
            valor_cancelado=Decimal("0.00"),
            quantidade_denegada=0,
            valor_denegado=Decimal("0.00")
        )
    ]
    resumo = FiscalAggregator.agregar(records)

    # Teste geração Excel
    excel_file = tmp_path / "relatorio_teste.xlsx"
    ok_excel = ExcelReporter.gerar_relatorio(
        resumo=resumo,
        razao_social="Empresa Teste Relatório",
        cnpj="12720599000117",
        periodo_str="01/01/2026 a 31/01/2026",
        destino_caminho=excel_file
    )
    assert ok_excel is True
    assert excel_file.exists()
    assert excel_file.stat().st_size > 1000

    # Teste geração PDF
    pdf_file = tmp_path / "relatorio_teste.pdf"
    ok_pdf = PdfReporter.gerar_relatorio(
        resumo=resumo,
        razao_social="Empresa Teste Relatório",
        cnpj="12720599000117",
        cgf="06.123.456-7",
        periodo_str="01/01/2026 a 31/01/2026",
        destino_caminho=pdf_file
    )
    assert ok_pdf is True
    assert pdf_file.exists()
    assert pdf_file.stat().st_size > 1000

from pathlib import Path
from decimal import Decimal
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from src.processor.aggregator import ResumoFiscalConsolidado
from src.utils.cnpj_validator import format_cnpj
from src.utils.logger import logger

class ExcelReporter:
    """
    Gerador de relatórios executivos e analíticos em Excel (.xlsx) com múltiplas abas,
    estilização profissional e fórmulas financeiras via openpyxl.
    """

    HEADER_FILL = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    SUBHEADER_FILL = PatternFill(start_color="059669", end_color="059669", fill_type="solid")
    SUBHEADER_FONT = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    TOTAL_FILL = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    TOTAL_FONT = Font(name="Calibri", size=10, bold=True, color="0F172A")
    THIN_BORDER = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1")
    )

    @classmethod
    def gerar_relatorio(
        cls,
        resumo: ResumoFiscalConsolidado,
        razao_social: str,
        cnpj: str,
        periodo_str: str,
        destino_caminho: Path
    ) -> bool:
        """
        Cria a pasta de trabalho Excel com as abas Consolidado, NF-e e NFC-e.
        """
        destino_caminho.parent.mkdir(parents=True, exist_ok=True)
        wb = openpyxl.Workbook()

        # ============================================================
        # ABA 1: RESUMO CONSOLIDADO
        # ============================================================
        ws_resumo = wb.active
        ws_resumo.title = "Resumo Consolidado"
        ws_resumo.views.sheetView[0].showGridLines = True

        # Título da Empresa
        ws_resumo["A1"] = "SIGA FISCAL — RELATÓRIO CONSOLIDADO DE MOVIMENTAÇÃO"
        ws_resumo["A1"].font = Font(name="Calibri", size=14, bold=True, color="0F172A")
        ws_resumo["A2"] = f"Empresa: {razao_social}  |  CNPJ: {format_cnpj(cnpj)}  |  Período: {periodo_str}"
        ws_resumo["A2"].font = Font(name="Calibri", size=10, italic=True, color="475569")

        # Totais consolidados
        tot_entradas = Decimal("0.00")
        tot_saidas = Decimal("0.00")
        for linha in resumo.linhas_consolidadas:
            if "entrada" in linha.operacao.lower():
                tot_entradas += linha.valor_total
            elif "saída" in linha.operacao.lower() or "saida" in linha.operacao.lower():
                tot_saidas += linha.valor_total

        # ============================================================
        # TABELA EXECUTIVA PRINCIPAL (CONFORME MODELO SOLICITADO)
        # ============================================================
        headers_exec = ["EMPRESAS", "VALOR ENTRADAS", "VALOR SAIDAS"]
        for col_idx, h in enumerate(headers_exec, start=1):
            cell = ws_resumo.cell(row=4, column=col_idx, value=h)
            cell.fill = cls.HEADER_FILL
            cell.font = cls.HEADER_FONT
            cell.alignment = Alignment(horizontal="left" if col_idx == 1 else "right", vertical="center")
            cell.border = cls.THIN_BORDER

        c_emp = ws_resumo.cell(row=5, column=1, value=razao_social)
        c_emp.font = Font(name="Calibri", size=11, bold=True, color="0F172A")
        c_emp.border = cls.THIN_BORDER

        c_ent = ws_resumo.cell(row=5, column=2, value=float(tot_entradas))
        c_ent.number_format = '[$R$ -416]#,##0.00'
        c_ent.font = Font(name="Calibri", size=11, color="B45309")
        c_ent.alignment = Alignment(horizontal="right", vertical="center")
        c_ent.border = cls.THIN_BORDER

        c_sai = ws_resumo.cell(row=5, column=3, value=float(tot_saidas))
        c_sai.number_format = '[$R$ -416]#,##0.00'
        c_sai.font = Font(name="Calibri", size=11, bold=True, color="047857")
        c_sai.alignment = Alignment(horizontal="right", vertical="center")
        c_sai.border = cls.THIN_BORDER

        # ============================================================
        # TABELA DETALHADA POR OPERAÇÃO (NF-e + NFC-e)
        # ============================================================
        ws_resumo.cell(row=7, column=1, value="DETALHAMENTO CONSOLIDADO POR OPERAÇÃO").font = Font(name="Calibri", size=11, bold=True, color="059669")

        headers = ["Operação Fiscal", "NF-e (Valor R$)", "Qtd NF-e", "NFC-e (Valor R$)", "Qtd NFC-e", "Total Consolidado (R$)", "Total Documentos"]
        row_idx = 8
        for col_idx, h in enumerate(headers, start=1):
            cell = ws_resumo.cell(row=row_idx, column=col_idx, value=h)
            cell.fill = cls.SUBHEADER_FILL
            cell.font = cls.SUBHEADER_FONT
            cell.alignment = Alignment(horizontal="center" if col_idx > 1 else "left", vertical="center")
            cell.border = cls.THIN_BORDER

        # Linhas de dados
        for linha in resumo.linhas_consolidadas:
            row_idx += 1
            ws_resumo.cell(row=row_idx, column=1, value=linha.operacao).font = Font(bold=True)
            
            c2 = ws_resumo.cell(row=row_idx, column=2, value=float(linha.valor_nfe))
            c2.number_format = '[$R$ -416]#,##0.00'
            ws_resumo.cell(row=row_idx, column=3, value=linha.qtd_nfe).alignment = Alignment(horizontal="center")

            c4 = ws_resumo.cell(row=row_idx, column=4, value=float(linha.valor_nfce))
            c4.number_format = '[$R$ -416]#,##0.00'
            ws_resumo.cell(row=row_idx, column=5, value=linha.qtd_nfce).alignment = Alignment(horizontal="center")

            c6 = ws_resumo.cell(row=row_idx, column=6, value=float(linha.valor_total))
            c6.number_format = '[$R$ -416]#,##0.00'
            c6.font = Font(bold=True, color="047857")

            c7 = ws_resumo.cell(row=row_idx, column=7, value=linha.qtd_total)
            c7.alignment = Alignment(horizontal="center")
            c7.font = Font(bold=True)

            for col_idx in range(1, 8):
                ws_resumo.cell(row=row_idx, column=col_idx).border = cls.THIN_BORDER

        # ============================================================
        # ABA 2: NF-e (MODELO 55)
        # ============================================================
        ws_nfe = wb.create_sheet(title="NF-e (Modelo 55)")
        ws_nfe.views.sheetView[0].showGridLines = True

        ws_nfe["A1"] = f"DEMONSTRATIVO ANALÍTICO DE NF-e — {razao_social}"
        ws_nfe["A1"].font = Font(name="Calibri", size=13, bold=True)

        nfe_headers = ["Mês / Referência", "Categoria", "Valor Autorizado (R$)", "Qtd Autorizada", "Valor Cancelado (R$)", "Qtd Cancelada", "Valor Denegado (R$)", "Qtd Denegada"]
        
        # Seção Saídas
        ws_nfe["A3"] = "1. SAÍDAS (EMISSOR)"
        ws_nfe["A3"].font = Font(size=11, bold=True, color="047857")
        row_nfe = 4
        for col_idx, h in enumerate(nfe_headers, start=1):
            cell = ws_nfe.cell(row=row_nfe, column=col_idx, value=h)
            cell.fill = cls.SUBHEADER_FILL
            cell.font = cls.SUBHEADER_FONT
            cell.border = cls.THIN_BORDER

        for item in resumo.quadro_nfe_saidas.itens:
            row_nfe += 1
            ws_nfe.cell(row=row_nfe, column=1, value=item.mes)
            ws_nfe.cell(row=row_nfe, column=2, value=item.categoria)
            c_val = ws_nfe.cell(row=row_nfe, column=3, value=float(item.valor_autorizado))
            c_val.number_format = 'R$ #,##0.00'
            ws_nfe.cell(row=row_nfe, column=4, value=item.quantidade_autorizada).alignment = Alignment(horizontal="center")
            c_canc = ws_nfe.cell(row=row_nfe, column=5, value=float(item.valor_cancelado))
            c_canc.number_format = 'R$ #,##0.00'
            ws_nfe.cell(row=row_nfe, column=6, value=item.quantidade_cancelada).alignment = Alignment(horizontal="center")
            c_den = ws_nfe.cell(row=row_nfe, column=7, value=float(item.valor_denegado))
            c_den.number_format = 'R$ #,##0.00'
            ws_nfe.cell(row=row_nfe, column=8, value=item.quantidade_denegada).alignment = Alignment(horizontal="center")
            for c in range(1, 9):
                ws_nfe.cell(row=row_nfe, column=c).border = cls.THIN_BORDER

        # Linha Total Saídas
        row_nfe += 1
        ws_nfe.cell(row=row_nfe, column=1, value="TOTAL SAÍDAS").font = cls.TOTAL_FONT
        t_val = ws_nfe.cell(row=row_nfe, column=3, value=float(resumo.quadro_nfe_saidas.total_valor_autorizado))
        t_val.number_format = 'R$ #,##0.00'
        t_val.font = cls.TOTAL_FONT
        t_qtd = ws_nfe.cell(row=row_nfe, column=4, value=resumo.quadro_nfe_saidas.total_quantidade_autorizada)
        t_qtd.font = cls.TOTAL_FONT
        t_qtd.alignment = Alignment(horizontal="center")
        for c in range(1, 9):
            ws_nfe.cell(row=row_nfe, column=c).fill = cls.TOTAL_FILL
            ws_nfe.cell(row=row_nfe, column=c).border = cls.THIN_BORDER

        # Seção Entradas
        row_nfe += 3
        ws_nfe.cell(row=row_nfe, column=1, value="2. ENTRADAS (DESTINATÁRIO)").font = Font(size=11, bold=True, color="B45309")
        row_nfe += 1
        for col_idx, h in enumerate(nfe_headers, start=1):
            cell = ws_nfe.cell(row=row_nfe, column=col_idx, value=h)
            cell.fill = cls.HEADER_FILL
            cell.font = cls.HEADER_FONT
            cell.border = cls.THIN_BORDER

        for item in resumo.quadro_nfe_entradas.itens:
            row_nfe += 1
            ws_nfe.cell(row=row_nfe, column=1, value=item.mes)
            ws_nfe.cell(row=row_nfe, column=2, value=item.categoria)
            c_val = ws_nfe.cell(row=row_nfe, column=3, value=float(item.valor_autorizado))
            c_val.number_format = 'R$ #,##0.00'
            ws_nfe.cell(row=row_nfe, column=4, value=item.quantidade_autorizada).alignment = Alignment(horizontal="center")
            c_canc = ws_nfe.cell(row=row_nfe, column=5, value=float(item.valor_cancelado))
            c_canc.number_format = 'R$ #,##0.00'
            ws_nfe.cell(row=row_nfe, column=6, value=item.quantidade_cancelada).alignment = Alignment(horizontal="center")
            c_den = ws_nfe.cell(row=row_nfe, column=7, value=float(item.valor_denegado))
            c_den.number_format = 'R$ #,##0.00'
            ws_nfe.cell(row=row_nfe, column=8, value=item.quantidade_denegada).alignment = Alignment(horizontal="center")
            for c in range(1, 9):
                ws_nfe.cell(row=row_nfe, column=c).border = cls.THIN_BORDER

        # Linha Total Entradas
        row_nfe += 1
        ws_nfe.cell(row=row_nfe, column=1, value="TOTAL ENTRADAS").font = cls.TOTAL_FONT
        t_val = ws_nfe.cell(row=row_nfe, column=3, value=float(resumo.quadro_nfe_entradas.total_valor_autorizado))
        t_val.number_format = 'R$ #,##0.00'
        t_val.font = cls.TOTAL_FONT
        t_qtd = ws_nfe.cell(row=row_nfe, column=4, value=resumo.quadro_nfe_entradas.total_quantidade_autorizada)
        t_qtd.font = cls.TOTAL_FONT
        t_qtd.alignment = Alignment(horizontal="center")
        for c in range(1, 9):
            ws_nfe.cell(row=row_nfe, column=c).fill = cls.TOTAL_FILL
            ws_nfe.cell(row=row_nfe, column=c).border = cls.THIN_BORDER

        # ============================================================
        # ABA 3: NFC-e (MODELO 65)
        # ============================================================
        ws_nfce = wb.create_sheet(title="NFC-e (Modelo 65)")
        ws_nfce.views.sheetView[0].showGridLines = True
        ws_nfce["A1"] = f"DEMONSTRATIVO ANALÍTICO DE NFC-e — {razao_social}"
        ws_nfce["A1"].font = Font(name="Calibri", size=13, bold=True)

        ws_nfce["A3"] = "1. SAÍDAS (CONSUMIDOR FINAL)"
        ws_nfce["A3"].font = Font(size=11, bold=True, color="6B21A8")
        row_nfce = 4
        for col_idx, h in enumerate(nfe_headers, start=1):
            cell = ws_nfce.cell(row=row_nfce, column=col_idx, value=h)
            cell.fill = PatternFill(start_color="7C3AED", end_color="7C3AED", fill_type="solid")
            cell.font = cls.HEADER_FONT
            cell.border = cls.THIN_BORDER

        for item in resumo.quadro_nfce_saidas.itens:
            row_nfce += 1
            ws_nfce.cell(row=row_nfce, column=1, value=item.mes)
            ws_nfce.cell(row=row_nfce, column=2, value=item.categoria)
            c_val = ws_nfce.cell(row=row_nfce, column=3, value=float(item.valor_autorizado))
            c_val.number_format = 'R$ #,##0.00'
            ws_nfce.cell(row=row_nfce, column=4, value=item.quantidade_autorizada).alignment = Alignment(horizontal="center")
            c_canc = ws_nfce.cell(row=row_nfce, column=5, value=float(item.valor_cancelado))
            c_canc.number_format = 'R$ #,##0.00'
            ws_nfce.cell(row=row_nfce, column=6, value=item.quantidade_cancelada).alignment = Alignment(horizontal="center")
            c_den = ws_nfce.cell(row=row_nfce, column=7, value=float(item.valor_denegado))
            c_den.number_format = 'R$ #,##0.00'
            ws_nfce.cell(row=row_nfce, column=8, value=item.quantidade_denegada).alignment = Alignment(horizontal="center")
            for c in range(1, 9):
                ws_nfce.cell(row=row_nfce, column=c).border = cls.THIN_BORDER

        # Ajuste automático de largura de colunas para todas as abas
        for ws in [ws_resumo, ws_nfe, ws_nfce]:
            for col in ws.columns:
                max_len = max(len(str(cell.value or "")) for cell in col)
                col_letter = get_column_letter(col[0].column)
                ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

        wb.save(destino_caminho)
        logger.info(f"Relatório Excel gerado com sucesso: {destino_caminho.name}")
        return True

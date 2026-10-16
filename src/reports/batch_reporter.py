from pathlib import Path
from decimal import Decimal
from typing import List, Dict, Any
from dataclasses import dataclass
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)

from src.utils.cnpj_validator import format_cnpj
from src.utils.logger import logger

@dataclass
class EmpresaResumoLote:
    razao_social: str
    cnpj: str
    nfe_saidas_val: Decimal
    nfe_saidas_qtd: int
    nfce_saidas_val: Decimal
    nfce_saidas_qtd: int
    total_saidas_val: Decimal
    total_saidas_qtd: int
    nfe_entradas_val: Decimal
    nfe_entradas_qtd: int
    total_canceladas_val: Decimal
    status: str
    nfce_entradas_val: Decimal = Decimal("0.00")
    nfce_entradas_qtd: int = 0
    total_entradas_val: Decimal = Decimal("0.00")
    total_entradas_qtd: int = 0

    def __post_init__(self):
        if self.total_entradas_val == Decimal("0.00") and (self.nfe_entradas_val > Decimal("0.00") or self.nfce_entradas_val > Decimal("0.00")):
            self.total_entradas_val = self.nfe_entradas_val + self.nfce_entradas_val
        if self.total_entradas_qtd == 0 and (self.nfe_entradas_qtd > 0 or self.nfce_entradas_qtd > 0):
            self.total_entradas_qtd = self.nfe_entradas_qtd + self.nfce_entradas_qtd

def _format_moeda(val: Decimal) -> str:
    s = f"{val:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"

class BatchReporter:
    """
    Gerador de relatórios consolidados em nível de lote (multi-empresas).
    Apresenta em uma única visão tabular os totais de cada contribuinte
    SOMENTE para o mês/período fiscal selecionado.
    """

    HEADER_FILL = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    HEADER_FONT = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
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
    def gerar_excel(
        cls,
        empresas: List[EmpresaResumoLote],
        lote_id: int,
        id_lote_str: str,
        periodo_str: str,
        destino_caminho: Path
    ) -> bool:
        """
        Gera planilha Excel (.xlsx) consolidando todas as empresas do lote.
        A aba principal segue estritamente o layout executivo solicitado:
        EMPRESAS | VALOR ENTRADAS | VALOR SAIDAS
        A aba secundária traz o detalhamento analítico e auditoria de canceladas.
        """
        try:
            destino_caminho.parent.mkdir(parents=True, exist_ok=True)
            wb = openpyxl.Workbook()

            # ============================================================
            # ABA 1: RELATÓRIO FINAL (LAYOUT SOLICITADO: EMPRESAS | ENTRADAS | SAIDAS)
            # ============================================================
            ws_final = wb.active
            ws_final.title = "Relatório Final"
            ws_final.views.sheetView[0].showGridLines = True

            headers_final = ["EMPRESAS", "VALOR ENTRADAS", "VALOR SAIDAS"]
            for col_idx, h in enumerate(headers_final, start=1):
                cell = ws_final.cell(row=1, column=col_idx, value=h)
                cell.fill = cls.HEADER_FILL
                cell.font = cls.HEADER_FONT
                cell.alignment = Alignment(horizontal="left" if col_idx == 1 else "right", vertical="center")
                cell.border = cls.THIN_BORDER

            tot_sai = Decimal("0.00")
            tot_ent = Decimal("0.00")
            tot_canc = Decimal("0.00")
            tot_nfe_s = Decimal("0.00")
            tot_nfce_s = Decimal("0.00")

            row_f = 1
            for emp in empresas:
                row_f += 1
                tot_sai += emp.total_saidas_val
                tot_ent += emp.total_entradas_val
                tot_canc += emp.total_canceladas_val
                tot_nfe_s += emp.nfe_saidas_val
                tot_nfce_s += emp.nfce_saidas_val

                c1 = ws_final.cell(row=row_f, column=1, value=emp.razao_social)
                c1.font = Font(name="Calibri", size=11, bold=True, color="0F172A")
                c1.alignment = Alignment(horizontal="left", vertical="center")
                c1.border = cls.THIN_BORDER

                c2 = ws_final.cell(row=row_f, column=2, value=float(emp.total_entradas_val))
                c2.number_format = '[$R$ -416]#,##0.00'
                c2.font = Font(name="Calibri", size=11, color="B45309")
                c2.alignment = Alignment(horizontal="right", vertical="center")
                c2.border = cls.THIN_BORDER

                c3 = ws_final.cell(row=row_f, column=3, value=float(emp.total_saidas_val))
                c3.number_format = '[$R$ -416]#,##0.00'
                c3.font = Font(name="Calibri", size=11, bold=True, color="047857")
                c3.alignment = Alignment(horizontal="right", vertical="center")
                c3.border = cls.THIN_BORDER

            # Linha de Total Geral
            row_f += 1
            t1 = ws_final.cell(row=row_f, column=1, value="TOTAL GERAL")
            t1.font = cls.TOTAL_FONT
            t1.fill = cls.TOTAL_FILL
            t1.border = cls.THIN_BORDER

            t2 = ws_final.cell(row=row_f, column=2, value=float(tot_ent))
            t2.number_format = '[$R$ -416]#,##0.00'
            t2.font = Font(name="Calibri", size=11, bold=True, color="B45309")
            t2.fill = cls.TOTAL_FILL
            t2.alignment = Alignment(horizontal="right", vertical="center")
            t2.border = cls.THIN_BORDER

            t3 = ws_final.cell(row=row_f, column=3, value=float(tot_sai))
            t3.number_format = '[$R$ -416]#,##0.00'
            t3.font = Font(name="Calibri", size=11, bold=True, color="047857")
            t3.fill = cls.TOTAL_FILL
            t3.alignment = Alignment(horizontal="right", vertical="center")
            t3.border = cls.THIN_BORDER

            # Auto-largura de colunas na aba principal
            for col in ws_final.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = openpyxl.utils.get_column_letter(col[0].column)
                ws_final.column_dimensions[col_letter].width = max(max_len + 4, 18)

            # ============================================================
            # ABA 2: CONSOLIDADO DO LOTE (AUDITORIA E DETALHAMENTO)
            # ============================================================
            ws_detalhe = wb.create_sheet(title="Consolidado do Lote")
            ws_detalhe.views.sheetView[0].showGridLines = True

            ws_detalhe["A1"] = f"SIGA FISCAL — DETALHAMENTO DO LOTE #{lote_id}"
            ws_detalhe["A1"].font = Font(name="Calibri", size=13, bold=True, color="0F172A")
            ws_detalhe["A2"] = f"Identificador: {id_lote_str}  |  Mês/Período: {periodo_str}  |  Total Empresas: {len(empresas)}"
            ws_detalhe["A2"].font = Font(name="Calibri", size=10, italic=True, color="475569")

            headers_det = [
                "#", "Razão Social", "CNPJ",
                "NF-e Saídas (R$)", "NFC-e Saídas (R$)", "Total Saídas (R$)",
                "NF-e Entradas (R$)", "Total Entradas (R$)", "Canceladas (R$)", "Status"
            ]

            row_det = 4
            for col_idx, h in enumerate(headers_det, start=1):
                cell = ws_detalhe.cell(row=row_det, column=col_idx, value=h)
                cell.fill = cls.HEADER_FILL
                cell.font = cls.HEADER_FONT
                cell.alignment = Alignment(horizontal="center" if col_idx not in (2, 3) else "left", vertical="center")
                cell.border = cls.THIN_BORDER

            for idx, emp in enumerate(empresas, start=1):
                row_det += 1
                ws_detalhe.cell(row=row_det, column=1, value=idx).alignment = Alignment(horizontal="center")
                ws_detalhe.cell(row=row_det, column=2, value=emp.razao_social).font = Font(bold=True)
                ws_detalhe.cell(row=row_det, column=3, value=format_cnpj(emp.cnpj))

                c4 = ws_detalhe.cell(row=row_det, column=4, value=float(emp.nfe_saidas_val))
                c4.number_format = '[$R$ -416]#,##0.00'

                c5 = ws_detalhe.cell(row=row_det, column=5, value=float(emp.nfce_saidas_val))
                c5.number_format = '[$R$ -416]#,##0.00'

                c6 = ws_detalhe.cell(row=row_det, column=6, value=float(emp.total_saidas_val))
                c6.number_format = '[$R$ -416]#,##0.00'
                c6.font = Font(bold=True, color="047857")

                c7 = ws_detalhe.cell(row=row_det, column=7, value=float(emp.nfe_entradas_val))
                c7.number_format = '[$R$ -416]#,##0.00'

                c8 = ws_detalhe.cell(row=row_det, column=8, value=float(emp.nfe_entradas_val))
                c8.number_format = '[$R$ -416]#,##0.00'
                c8.font = Font(bold=True, color="B45309")

                c9 = ws_detalhe.cell(row=row_det, column=9, value=float(emp.total_canceladas_val))
                c9.number_format = '[$R$ -416]#,##0.00'

                ws_detalhe.cell(row=row_det, column=10, value=emp.status).alignment = Alignment(horizontal="center")

                for c in range(1, 11):
                    ws_detalhe.cell(row=row_det, column=c).border = cls.THIN_BORDER

            # Linha de Totais da aba de detalhes
            row_det += 1
            ws_detalhe.cell(row=row_det, column=1, value="").fill = cls.TOTAL_FILL
            ws_detalhe.cell(row=row_det, column=2, value="TOTAL GERAL DO LOTE").font = cls.TOTAL_FONT
            ws_detalhe.cell(row=row_det, column=3, value="").fill = cls.TOTAL_FILL

            t4 = ws_detalhe.cell(row=row_det, column=4, value=float(tot_nfe_s))
            t4.number_format = '[$R$ -416]#,##0.00'
            t4.font = cls.TOTAL_FONT

            t5 = ws_detalhe.cell(row=row_det, column=5, value=float(tot_nfce_s))
            t5.number_format = '[$R$ -416]#,##0.00'
            t5.font = cls.TOTAL_FONT

            t6 = ws_detalhe.cell(row=row_det, column=6, value=float(tot_sai))
            t6.number_format = '[$R$ -416]#,##0.00'
            t6.font = Font(name="Calibri", size=10, bold=True, color="047857")

            t7 = ws_detalhe.cell(row=row_det, column=7, value=float(tot_ent))
            t7.number_format = '[$R$ -416]#,##0.00'
            t7.font = cls.TOTAL_FONT

            t8 = ws_detalhe.cell(row=row_det, column=8, value=float(tot_ent))
            t8.number_format = '[$R$ -416]#,##0.00'
            t8.font = Font(name="Calibri", size=10, bold=True, color="B45309")

            t9 = ws_detalhe.cell(row=row_det, column=9, value=float(tot_canc))
            t9.number_format = '[$R$ -416]#,##0.00'
            t9.font = cls.TOTAL_FONT

            ws_detalhe.cell(row=row_det, column=10, value="").fill = cls.TOTAL_FILL

            for c in range(1, 11):
                ws_detalhe.cell(row=row_det, column=c).fill = cls.TOTAL_FILL
                ws_detalhe.cell(row=row_det, column=c).border = cls.THIN_BORDER

            for col in ws_detalhe.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = openpyxl.utils.get_column_letter(col[0].column)
                ws_detalhe.column_dimensions[col_letter].width = max(max_len + 3, 12)

            wb.save(destino_caminho)
            logger.info(f"Relatório Excel Consolidado do Lote gerado: {destino_caminho.name}")
            return True
        except Exception as e:
            logger.error(f"Erro ao gerar Excel consolidado do lote: {e}")
            return False

    @classmethod
    def gerar_pdf(
        cls,
        empresas: List[EmpresaResumoLote],
        lote_id: int,
        id_lote_str: str,
        periodo_str: str,
        destino_caminho: Path
    ) -> bool:
        """Gera relatório PDF em orientação paisagem com tabela executiva das empresas."""
        try:
            destino_caminho.parent.mkdir(parents=True, exist_ok=True)
            doc = SimpleDocTemplate(
                str(destino_caminho),
                pagesize=landscape(A4),
                leftMargin=28,
                rightMargin=28,
                topMargin=28,
                bottomMargin=28
            )

            styles = getSampleStyleSheet()
            titulo_style = ParagraphStyle(
                "BatchTitle",
                parent=styles["Heading1"],
                fontSize=15,
                leading=18,
                textColor=colors.HexColor("#0F172A"),
                fontName="Helvetica-Bold"
            )
            subtitulo_style = ParagraphStyle(
                "BatchSubtitle",
                parent=styles["Normal"],
                fontSize=9,
                leading=12,
                textColor=colors.HexColor("#475569")
            )
            secao_style = ParagraphStyle(
                "BatchSecao",
                parent=styles["Heading2"],
                fontSize=11,
                leading=14,
                textColor=colors.HexColor("#059669"),
                fontName="Helvetica-Bold",
                spaceAfter=4
            )
            cell_norm = ParagraphStyle("CellN", parent=styles["Normal"], fontSize=8, leading=10)
            cell_bold = ParagraphStyle("CellB", parent=styles["Normal"], fontSize=8, leading=10, fontName="Helvetica-Bold")
            cell_center = ParagraphStyle("CellC", parent=styles["Normal"], fontSize=8, leading=10, alignment=1)
            cell_right = ParagraphStyle("CellR", parent=styles["Normal"], fontSize=8, leading=10, alignment=2)
            cell_right_bold = ParagraphStyle("CellRB", parent=styles["Normal"], fontSize=8, leading=10, fontName="Helvetica-Bold", alignment=2)

            elements = []
            elements.append(Paragraph(f"SIGA FISCAL — RELATÓRIO EXECUTIVO CONSOLIDADO (LOTE #{lote_id})", titulo_style))
            elements.append(Paragraph(f"<b>Período Fiscal:</b> {periodo_str} | <b>Identificador:</b> {id_lote_str} | <b>Empresas no Lote:</b> {len(empresas)}", subtitulo_style))
            elements.append(Spacer(1, 14))

            # ============================================================
            # QUADRO 1: RELATÓRIO EXECUTIVO PRINCIPAL (EMPRESAS | VALOR ENTRADAS | VALOR SAIDAS)
            # ============================================================
            elements.append(Paragraph("1. DEMONSTRATIVO EXECUTIVO CONSOLIDADO", secao_style))

            table_data = [
                [
                    Paragraph("<b>#</b>", cell_center),
                    Paragraph("<b>EMPRESAS</b>", cell_bold),
                    Paragraph("<b>VALOR ENTRADAS</b>", cell_right_bold),
                    Paragraph("<b>VALOR SAIDAS</b>", cell_right_bold)
                ]
            ]

            tot_sai = Decimal("0.00")
            tot_ent = Decimal("0.00")
            tot_canc = Decimal("0.00")

            for idx, emp in enumerate(empresas, start=1):
                tot_sai += emp.total_saidas_val
                tot_ent += emp.total_entradas_val
                tot_canc += emp.total_canceladas_val

                table_data.append([
                    Paragraph(str(idx), cell_center),
                    Paragraph(f"<b>{emp.razao_social}</b><br/><font color='#64748B' size='7'>CNPJ: {format_cnpj(emp.cnpj)}</font>", cell_norm),
                    Paragraph(f"<font color='#B45309'><b>{_format_moeda(emp.total_entradas_val)}</b></font>", cell_right),
                    Paragraph(f"<font color='#047857'><b>{_format_moeda(emp.total_saidas_val)}</b></font>", cell_right)
                ])

            # Linha de Totais Gerais
            table_data.append([
                Paragraph("", cell_center),
                Paragraph("<b>TOTAL GERAL</b>", cell_bold),
                Paragraph(f"<font color='#B45309'><b>{_format_moeda(tot_ent)}</b></font>", cell_right_bold),
                Paragraph(f"<font color='#047857'><b>{_format_moeda(tot_sai)}</b></font>", cell_right_bold)
            ])

            t = Table(table_data, colWidths=[30, 370, 180, 180])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor("#F8FAFC")]),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E2E8F0")),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 14))

            # ============================================================
            # QUADRO 2: AUDITORIA E DESMEMBRAMENTO DE MODELOS
            # ============================================================
            elements.append(Paragraph("2. AUDITORIA E DESMEMBRAMENTO POR MODELO DE DOCUMENTO", secao_style))

            table_auditoria = [
                [
                    Paragraph("<b>#</b>", cell_center),
                    Paragraph("<b>Empresa</b>", cell_bold),
                    Paragraph("<b>NF-e Saídas</b>", cell_right_bold),
                    Paragraph("<b>NFC-e Saídas</b>", cell_right_bold),
                    Paragraph("<b>Canceladas (Auditoria)</b>", cell_right_bold),
                    Paragraph("<b>Status</b>", cell_center)
                ]
            ]

            tot_nfe_s = Decimal("0.00")
            tot_nfce_s = Decimal("0.00")

            for idx, emp in enumerate(empresas, start=1):
                tot_nfe_s += emp.nfe_saidas_val
                tot_nfce_s += emp.nfce_saidas_val

                table_auditoria.append([
                    Paragraph(str(idx), cell_center),
                    Paragraph(emp.razao_social, cell_norm),
                    Paragraph(_format_moeda(emp.nfe_saidas_val), cell_right),
                    Paragraph(_format_moeda(emp.nfce_saidas_val), cell_right),
                    Paragraph(_format_moeda(emp.total_canceladas_val), cell_right),
                    Paragraph(emp.status, cell_center)
                ])

            table_auditoria.append([
                Paragraph("", cell_center),
                Paragraph("<b>TOTAL</b>", cell_bold),
                Paragraph(f"<b>{_format_moeda(tot_nfe_s)}</b>", cell_right_bold),
                Paragraph(f"<b>{_format_moeda(tot_nfce_s)}</b>", cell_right_bold),
                Paragraph(f"<b>{_format_moeda(tot_canc)}</b>", cell_right_bold),
                Paragraph("", cell_center)
            ])

            t_aud = Table(table_auditoria, colWidths=[30, 250, 120, 120, 140, 100])
            t_aud.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#475569")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor("#F8FAFC")]),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E2E8F0")),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
            ]))
            elements.append(t_aud)

            doc.build(elements)
            logger.info(f"Relatório PDF Consolidado do Lote gerado: {destino_caminho.name}")
            return True
        except Exception as e:
            logger.error(f"Erro ao gerar PDF consolidado do lote: {e}")
            return False

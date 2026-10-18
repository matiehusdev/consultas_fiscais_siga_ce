from pathlib import Path
from decimal import Decimal
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether
)

from src.processor.aggregator import ResumoFiscalConsolidado
from src.utils.cnpj_validator import format_cnpj
from src.utils.logger import logger

def _format_moeda(val: Decimal) -> str:
    s = f"{val:,.2f}"
    # Formato brasileiro: 1,234.56 -> 1.234,56
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"

class PdfReporter:
    """
    Emissor de relatórios fiscais executivos em PDF com ReportLab.
    Gera tabelas vetoriais diagramadas, dados do contribuinte e auditoria segregada.
    """

    @classmethod
    def gerar_relatorio(
        cls,
        resumo: ResumoFiscalConsolidado,
        razao_social: str,
        cnpj: str,
        cgf: str,
        periodo_str: str,
        destino_caminho: Path
    ) -> bool:
        destino_caminho.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(destino_caminho),
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        normal_style = styles["Normal"]

        titulo_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#0F172A"),
            fontName="Helvetica-Bold"
        )
        subtitulo_style = ParagraphStyle(
            "DocSubtitle",
            parent=normal_style,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#475569")
        )
        secao_style = ParagraphStyle(
            "SecaoHeader",
            parent=styles["Heading2"],
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#059669"),
            fontName="Helvetica-Bold",
            spaceAfter=6
        )
        cell_style = ParagraphStyle(
            "CellNormal",
            parent=normal_style,
            fontSize=8,
            leading=10
        )
        cell_bold = ParagraphStyle(
            "CellBold",
            parent=normal_style,
            fontSize=8,
            leading=10,
            fontName="Helvetica-Bold"
        )
        cell_center = ParagraphStyle(
            "CellCenter",
            parent=normal_style,
            fontSize=8,
            leading=10,
            alignment=1
        )

        elements = []

        # ============================================================
        # CABEÇALHO DO DOCUMENTO
        # ============================================================
        elements.append(Paragraph("SIGA FISCAL — DEMONSTRATIVO FISCAL CONSOLIDADO", titulo_style))
        agora_str = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
        info_empresa = (
            f"<b>Contribuinte:</b> {razao_social} | <b>CNPJ:</b> {format_cnpj(cnpj)} | <b>CGF:</b> {cgf or '—'}<br/>"
            f"<b>Período de Referência:</b> {periodo_str} | <b>Emissão:</b> {agora_str}"
        )
        elements.append(Paragraph(info_empresa, subtitulo_style))
        elements.append(Spacer(1, 14))

        # Totais consolidados
        tot_entradas = Decimal("0.00")
        tot_saidas = Decimal("0.00")
        for l in resumo.linhas_consolidadas:
            if "entrada" in l.operacao.lower():
                tot_entradas += l.valor_total
            elif "saída" in l.operacao.lower() or "saida" in l.operacao.lower():
                tot_saidas += l.valor_total

        # ============================================================
        # QUADRO 1: DEMONSTRATIVO EXECUTIVO (CONFORME MODELO SOLICITADO)
        # ============================================================
        elements.append(Paragraph("1. DEMONSTRATIVO EXECUTIVO CONSOLIDADO", secao_style))

        th_exec = ParagraphStyle(
            "THExecWhite",
            parent=normal_style,
            fontSize=8,
            leading=10,
            fontName="Helvetica-Bold",
            textColor=colors.white
        )

        dados_executivo = [
            [
                Paragraph("<b>EMPRESAS</b>", th_exec),
                Paragraph("<b>VALOR ENTRADAS</b>", th_exec),
                Paragraph("<b>VALOR SAÍDAS</b>", th_exec)
            ],
            [
                Paragraph(f"<b>{razao_social}</b>", cell_style),
                Paragraph(f"<font color='#B45309'><b>{_format_moeda(tot_entradas)}</b></font>", cell_style),
                Paragraph(f"<font color='#047857'><b>{_format_moeda(tot_saidas)}</b></font>", cell_style)
            ]
        ]
        t_exec = Table(dados_executivo, colWidths=[260, 130, 130])
        t_exec.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('BACKGROUND', (0, 1), (-1, 1), colors.white),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(t_exec)
        elements.append(Spacer(1, 14))

        # ============================================================
        # QUADRO 2: RESUMO POR OPERAÇÃO (NF-e + NFC-e)
        # ============================================================
        elements.append(Paragraph("2. RESUMO DETALHADO POR OPERAÇÃO (NF-e + NFC-e)", secao_style))

        dados_consolidado = [
            [
                Paragraph("<b>Operação</b>", cell_style),
                Paragraph("<b>NF-e (Valor)</b>", cell_style),
                Paragraph("<b>Qtd NF-e</b>", cell_center),
                Paragraph("<b>NFC-e (Valor)</b>", cell_style),
                Paragraph("<b>Qtd NFC-e</b>", cell_center),
                Paragraph("<b>Total Consolidado</b>", cell_bold),
                Paragraph("<b>Total Docs</b>", cell_center)
            ]
        ]

        for l in resumo.linhas_consolidadas:
            dados_consolidado.append([
                Paragraph(f"<b>{l.operacao}</b>", cell_style),
                Paragraph(_format_moeda(l.valor_nfe), cell_style),
                Paragraph(str(l.qtd_nfe), cell_center),
                Paragraph(_format_moeda(l.valor_nfce), cell_style),
                Paragraph(str(l.qtd_nfce), cell_center),
                Paragraph(f"<b>{_format_moeda(l.valor_total)}</b>", cell_bold),
                Paragraph(f"<b>{l.qtd_total}</b>", cell_center)
            ])

        t_consolidado = Table(dados_consolidado, colWidths=[65, 80, 50, 80, 50, 95, 60])
        t_consolidado.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#059669")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('ALIGN', (4, 0), (4, -1), 'CENTER'),
            ('ALIGN', (6, 0), (6, -1), 'CENTER'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(t_consolidado)
        elements.append(Spacer(1, 16))

        # ============================================================
        # QUADRO 3: DEMONSTRATIVO NF-e (MODELO 55)
        # ============================================================
        elements.append(Paragraph("3. DEMONSTRATIVO ANALÍTICO DE NF-e (MODELO 55)", secao_style))

        def criar_tabela_detalhe(titulo_quadro: str, quadro):
            linhas = [
                [Paragraph(f"<b>{titulo_quadro}</b>", cell_bold), "", "", "", "", ""],
                [
                    Paragraph("<b>Mês / Categoria</b>", cell_style),
                    Paragraph("<b>Valor Autorizado</b>", cell_style),
                    Paragraph("<b>Qtd Aut.</b>", cell_center),
                    Paragraph("<b>Valor Cancelado</b>", cell_style),
                    Paragraph("<b>Qtd Canc.</b>", cell_center),
                    Paragraph("<b>Qtd Deneg.</b>", cell_center)
                ]
            ]
            if quadro.itens:
                for it in quadro.itens:
                    linhas.append([
                        Paragraph(f"{it.mes} • {it.categoria}", cell_style),
                        Paragraph(_format_moeda(it.valor_autorizado), cell_style),
                        Paragraph(str(it.quantidade_autorizada), cell_center),
                        Paragraph(_format_moeda(it.valor_cancelado), cell_style),
                        Paragraph(str(it.quantidade_cancelada), cell_center),
                        Paragraph(str(it.quantidade_denegada), cell_center)
                    ])
            else:
                linhas.append([Paragraph("Nenhuma movimentação registrada no período.", cell_style), "", "", "", "", ""])

            # Linha Total
            linhas.append([
                Paragraph("<b>TOTAL</b>", cell_bold),
                Paragraph(f"<b>{_format_moeda(quadro.total_valor_autorizado)}</b>", cell_bold),
                Paragraph(f"<b>{quadro.total_quantidade_autorizada}</b>", cell_center),
                Paragraph(_format_moeda(quadro.total_valor_cancelado), cell_style),
                Paragraph(str(quadro.total_quantidade_cancelada), cell_center),
                Paragraph(str(quadro.total_quantidade_denegada), cell_center)
            ])

            t = Table(linhas, colWidths=[140, 90, 50, 90, 50, 50])
            t.setStyle(TableStyle([
                ('SPAN', (0, 0), (-1, 0)),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#059669")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#E2E8F0")),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#F1F5F9")),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
            ]))
            return t

        elements.append(criar_tabela_detalhe("NF-e — SAÍDAS (EMISSOR)", resumo.quadro_nfe_saidas))
        elements.append(Spacer(1, 10))
        elements.append(criar_tabela_detalhe("NF-e — ENTRADAS (DESTINATÁRIO)", resumo.quadro_nfe_entradas))
        elements.append(Spacer(1, 16))

        # ============================================================
        # QUADRO 4: DEMONSTRATIVO NFC-e (MODELO 65)
        # ============================================================
        elements.append(Paragraph("4. DEMONSTRATIVO ANALÍTICO DE NFC-e (MODELO 65)", secao_style))
        elements.append(criar_tabela_detalhe("NFC-e — SAÍDAS (CONSUMIDOR FINAL)", resumo.quadro_nfce_saidas))
        elements.append(Spacer(1, 14))

        # Nota de Auditoria
        nota_auditoria = Paragraph(
            "<b>Nota Fiscal e Auditoria:</b> Conforme regras da SEFAZ-CE, os valores e quantidades de movimentação contábil "
            "são calculados estritamente com base nos documentos <b>AUTORIZADOS</b>. Documentos cancelados e denegados "
            "são apresentados separadamente exclusivamente para fins de auditoria e conformidade fiscal.",
            subtitulo_style
        )
        elements.append(nota_auditoria)

        doc.build(elements)
        logger.info(f"Relatório PDF gerado com sucesso: {destino_caminho.name}")
        return True

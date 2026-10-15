# Especificação e Regras de Negócio de Relatórios (REPORTS.md)

Este documento descreve as fórmulas matemáticas, regras contábeis, tratamento de eventos fiscais e estrutura de apresentação dos relatórios gerados pelo **SIGA Fiscal**.

---

## 1. Princípio Fundamental de Cálculo Fiscal

### 1.1 Regra Primária de Movimentação
No SIGA da SEFAZ-CE, a planilha oficial de NF-e apresenta tanto o total bruto de notas emitidas quanto o detalhamento das notas autorizadas, canceladas e denegadas.

> **REGRA MANDATÓRIA:**  
> O valor contábil e a quantidade oficial de documentos da movimentação fiscal **devem ser computados estritamente com base nos documentos autorizados**:
> - `valor R$ NF-e emitidas autorizadas`
> - `qtd NF-e emitidas autorizadas`

### 1.2 Por que NÃO utilizar "valor R$ NF-e emitidas"?
O campo genérico "emitidas" inclui notas fiscais que foram posteriormente **canceladas** pelo contribuinte ou que tiveram autorização de uso **denegada** pelo Fisco. Utilizar o valor total de emitidas distorce a receita auferida e a apuração tributária da empresa.

### 1.3 Preservação para Auditoria
As notas canceladas e denegadas **não** são descartadas. Elas são quantificadas e exibidas em seções e colunas exclusivas de **Auditoria Fiscal**, permitindo ao auditor ou contador inspecionar eventuais anomalias operacionais sem inflar a movimentação real.

---

## 2. Tratamento por Modelo de Documento

### 2.1 NF-e (Nota Fiscal Eletrônica - Modelo 55)
- **Saídas (Emissor):** Representam as vendas, remessas e transferências emitidas pela empresa.
- **Entradas (Destinatário):** Representam as compras e aquisições em que a empresa figura como destinatária.
- **Classificação Geográfica:**
  - **Interna:** Operações ocorridas dentro do Estado do Ceará.
  - **Interestadual:** Operações envolvendo outros estados da federação.
  - **Externa:** Operações de comércio exterior (importação/exportação).

### 2.2 NFC-e (Nota Fiscal de Consumidor Eletrônica - Modelo 65)
- Documento emitido para consumidor final presencial ou entrega em domicílio.
- Segue a mesma diretriz de cálculo: movimento baseado em notas autorizadas e segregação de canceladas.
- O processador preserva a classificação original das colunas encontradas no layout real do SIGA, sem tentar forçar categorias artificiais.

---

## 3. Modelo de Apresentação das Tabelas

O relatório analítico **não mistura NF-e com NFC-e**. Cada modelo é demonstrado em seu próprio quadro, seguido pela consolidação final.

### 3.1 Quadro 1: NF-e (Modelo 55)

**SAÍDAS**
| Mês de Competência | Interna (R$) | Interestadual (R$) | Externa (R$) | Total NF-e Saídas (R$) | Qtd Autorizada | Qtd Cancelada |
|---|---|---|---|---|---|---|
| Janeiro/2026 | R$ 10.000,00 | R$ 20.000,00 | R$ 0,00 | R$ 30.000,00 | 120 | 3 |
| Fevereiro/2026 | R$ 15.000,00 | R$ 25.000,00 | R$ 0,00 | R$ 40.000,00 | 150 | 2 |

**ENTRADAS**
| Mês de Competência | Interna (R$) | Interestadual (R$) | Externa (R$) | Total NF-e Entradas (R$) | Qtd Autorizada | Qtd Cancelada |
|---|---|---|---|---|---|---|
| Janeiro/2026 | R$ 5.000,00 | R$ 8.000,00 | R$ 0,00 | R$ 13.000,00 | 80 | 1 |
| Fevereiro/2026 | R$ 7.000,00 | R$ 10.000,00 | R$ 0,00 | R$ 17.000,00 | 95 | 0 |

---

### 3.2 Quadro 2: NFC-e (Modelo 65)

**SAÍDAS**
| Mês de Competência | Categoria / Detalhe | Total NFC-e Saídas (R$) | Qtd Autorizada | Qtd Cancelada |
|---|---|---|---|---|
| Janeiro/2026 | Venda a Consumidor | R$ 15.000,00 | 350 | 12 |
| Fevereiro/2026 | Venda a Consumidor | R$ 18.000,00 | 410 | 8 |

**ENTRADAS**
| Mês de Competência | Categoria / Detalhe | Total NFC-e Entradas (R$) | Qtd Autorizada | Qtd Cancelada |
|---|---|---|---|---|
| Janeiro/2026 | Devolução / Recebimento | R$ 2.000,00 | 20 | 1 |
| Fevereiro/2026 | Devolução / Recebimento | R$ 2.500,00 | 25 | 0 |

---

### 3.3 Quadro 3: Resumo Consolidado Geral

Após as demonstrações individuais, o sistema apresenta a síntese:

$$\text{Total Geral} = \text{Total NF-e} + \text{Total NFC-e}$$

| Operação | NF-e (Valor R$) | NFC-e (Valor R$) | Total Consolidado (R$) | Qtd NF-e | Qtd NFC-e | Total Documentos |
|---|---|---|---|---|---|---|
| **Saídas** | R$ 70.000,00 | R$ 33.000,00 | **R$ 103.000,00** | 270 | 760 | **1.030** |
| **Entradas** | R$ 30.000,00 | R$ 4.500,00 | **R$ 34.500,00** | 175 | 45 | **220** |

---

## 4. Formatos de Saída dos Relatórios

1. **Planilha Excel (`.xlsx`):**
   - Gera pasta de trabalho estruturada com abas separadas:
     - `Resumo Consolidado`
     - `NF-e Saídas e Entradas`
     - `NFC-e Saídas e Entradas`
     - `Evolução Mensal`
   - Aplica formatação monetária padrão brasileira (`R$ #,##0.00`), cabeçalhos destacados e bordas profissionais.
2. **Documento PDF (`.pdf`):**
   - Cabeçalho executivo padronizado contendo dados do contribuinte (Razão Social, CNPJ, CGF) e carimbo de data/hora de geração.
   - Tabelas vetoriais diagramadas milimetricamente com ReportLab, garantindo legibilidade e quebra de página automática.

# Diretrizes de Integridade de Automação Fiscal e Downloads Assíncronos

1. **Rastreamento Estrito de Solicitações Assíncronas (No Blind Polling):**
   - Em interfaces SPA com filas assíncronas (como o portal SIGA SEFAZ-CE em `/downloads-assincronos`), nunca assumir que a primeira linha da tabela DOM representa o download recém-solicitado.
   - Sempre interceptar ou correlacionar o ID único da solicitação (`solicitacao_id`) retornado pela API ou capturado no evento de rede.
   - Aguardar a conclusão **exclusivamente do registro correspondente à solicitação atual**, verificando CNPJ, tipo de documento (`NFE` / `NFCE`), tipo de operação (`SAIDA` / `ENTRADA`) e timestamp de criação.

2. **Guarda Contra Download Cruzado (Operation Segregation & Hash Collision):**
   - Ao baixar arquivos de operações opostas para uma mesma empresa (ex: `nfe_saida.xlsx` e `nfe_entrada.xlsx`), comparar os hashes SHA-256. Se os arquivos forem idênticos em conteúdo binário quando ambas as operações foram solicitadas, rejeitar a atribuição cruzada e registrar alerta.
   - Para NFC-e (Modelo 65), reconhecer que a SEFAZ-CE opera exclusivamente emissão no varejo (Saída). Não forçar downloads espúrios de Entrada que possam duplicar arquivos de Saída.

3. **Normalização e Truncamento de Datas em Parsers Fiscais:**
   - Em relatórios fiscais analíticos, colunas de emissão frequentemente contêm data e hora (`DD/MM/YYYY HH:MM:SS` ou ISO). Os parsers devem extrair exclusivamente a parte da data antes de realizar qualquer segmentação ou matching de competência mensal (`matches_month`).
   - O filtro de competência deve suportar tanto formatos textuais por extenso quanto códigos numéricos e objetos temporais nativos do pandas (`Timestamp`) e Python (`date`, `datetime`).

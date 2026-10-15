# Especificação de Integração com o SIGA (SIGA_INTEGRATION.md)

Este documento descreve detalhadamente o comportamento, endpoints, fluxos de autenticação, polling e download no portal **SIGA — Sistema de Interface Guiada à Autorregularização** da SEFAZ-CE.

---

## 1. Autenticação e Certificado Digital A1

### 1.1 Modos Operacionais de Autenticação
O sistema suporta dois modos operacionais complementares:

#### Modo 1: Autônomo com Certificado A1 Vinculado (Recomendado)
- O usuário anexa o arquivo `.pfx` ou `.p12` do Certificado Digital A1 e sua senha diretamente no cadastro da empresa.
- A senha é cifrada localmente com chave simétrica AES-128 em repouso (`src/utils/crypto.py`).
- Ao iniciar a sessão da empresa, o Playwright configura o contexto Chromium com `client_certificates=[{"origin": "https://siga.sefaz.ce.gov.br", "pfxPath": "...", "passphrase": "..."}]`.
- **Efeito:** O Chromium entrega o certificado automaticamente no handshake TLS da SEFAZ **sem abrir qualquer janela de diálogo do Windows**, viabilizando consultas 100% autônomas em lote para dezenas de empresas consecutivas.

#### Modo 2: Interação Manual Autorizada (Fallback)
- Utilizado caso o usuário prefira não anexar o arquivo `.pfx` ou para certificados A3 (cartão/token físico).
- O navegador abre em modo visível (`headless=False`) e aguarda o operador clicar no certificado na janela do Windows.
- O sistema detecta assincronamente a conclusão do login e assume o fluxo.

---

## 2. Isolamento de Sessão por Empresa

### 2.1 Particularidade Identificada
No SIGA, a troca de contribuinte logado dentro da mesma sessão web não é garantida de forma confiável e pode provocar contaminação de cookies e cache da empresa anterior.

### 2.2 Política de Sessões
- Toda consulta de uma nova empresa **inicia em uma nova sessão do navegador**.
- Ao concluir a Empresa A, o navegador é encerrado completamente.
- Uma nova sessão é iniciada do zero para a Empresa B.

---

## 3. Integração de NF-e (Nota Fiscal Eletrônica - Modelo 55)

### 3.1 Endpoint de Solicitação de Download
- **Método:** `POST`
- **URL:** `https://siga.sefaz.ce.gov.br/api/v1/unidades/{CNPJ}/documentos-fiscais/nf-e/resumos/eventos/download`
- **Cabeçalhos:**
  - `Accept: application/json`
  - `Content-Type: application/x-www-form-urlencoded` ou `application/json` (conforme interceptação)
- **Parâmetros:**
  - `dat-referencia`: `"YYYY-MM-DD,YYYY-MM-DD"` (ex: `2026-01-01,2026-09-30`)
  - `tipo-operacao`: `"SAIDA"` ou `"ENTRADA"`
  - `formato-arquivo`: `"xlsx"`
- **Resposta:**
  - Código: `HTTP 202 Accepted`
  - Indica que a solicitação foi colocada na fila de processamento assíncrono do SIGA.

### 3.2 Acompanhamento da Solicitação
- **Método:** `GET`
- **URL:** `https://siga.sefaz.ce.gov.br/api/v1/solicitacoes?sort=criacao,desc`
- **Resposta Exemplo:**
  ```json
  {
      "data": [
          {
              "id": "e6a21852-6a7c-4ea0-98b1-b4f028cf5bb0",
              "tipo": "NF_E_RESUMO_EVENTOS",
              "cnpjBase": "12720599",
              "cnpj": "12720599000117",
              "descricao": "Informações Fiscais - NF-e - Indicadores - 2026",
              "filtro": {
                  "datReferencia": [
                      "2026-01-01",
                      "2026-09-30"
                  ],
                  "formatoArquivo": "xlsx",
                  "resultadoProcessamento": null,
                  "tipoOperacao": "SAIDA"
              },
              "status": "CONCLUIDO",
              "expiracao": "2026-10-10",
              "criacao": "2026-10-08T17:55:28.811072"
          }
      ],
      "version": "v1"
  }
  ```

### 3.3 Regra de Matching da Solicitação
O sistema **não** seleciona cegamente `data[0]`. A correspondência correta é validada conferindo:
- `cnpj == request.cnpj`
- `tipo == "NF_E_RESUMO_EVENTOS"`
- `filtro.tipoOperacao == request.operacao` (SAIDA ou ENTRADA)
- `filtro.datReferencia == request.periodo`
- `filtro.formatoArquivo == "xlsx"`
- `criacao >= timestamp_solicitacao`

### 3.4 Estados da Solicitação
- `PENDENTE`: Aguardando processador da SEFAZ.
- `PROCESSANDO`: Arquivo em geração.
- `CONCLUIDO`: Disponível para download.
- `ERRO`: Falha de processamento na SEFAZ.
- `EXPIRADO`: Prazo de download ultrapassado.

---

## 4. Fluxo de Download e Redirecionamento S3

1. O sistema faz a chamada de download da solicitação com status `CONCLUIDO`.
2. A API do SIGA responde com `HTTP 302 Found` apontando para o bucket Amazon S3 da SEFAZ:
   `https://sefaz-ce-aplicacoes-prod.s3.sa-east-1.amazonaws.com/...`
3. A URL contém parâmetros pré-assinados com expiração rápida (`X-Amz-Algorithm`, `X-Amz-Credential`, `X-Amz-Date`, `X-Amz-Expires`, `X-Amz-SignedHeaders`, `X-Amz-Signature`).
4. O cliente HTTP segue o redirecionamento e faz o streaming direto para o arquivo local `original.xlsx`.
5. **A URL temporária é imediatamente descartada da memória.**
6. Em nenhuma hipótese as credenciais `X-Amz-*` ou a URL completa são registradas em logs ou no banco de dados.

---

## 5. Integração de NFC-e (Nota Fiscal de Consumidor Eletrônica - Modelo 65)

### 5.1 Princípio de Autonomia
A NFC-e **não** é tratada como mera variação da NF-e. No SIGA, a NFC-e possui tabelas e fluxos próprios.

### 5.2 Roteiro de Descoberta (Network Sniffing)
Antes de acionar chamadas reais de NFC-e, o módulo de inspeção (`scripts/discover_nfce.py`) executa o monitoramento de rede e mapeia os seguintes campos:
1. Endpoint exato de solicitação de download.
2. Método HTTP utilizado.
3. Parâmetros de URL e cabeçalhos obrigatórios.
4. Payload JSON ou formato de dados do corpo da requisição.
5. Tipo de operação aceito (`EMISSAO`, `SAIDA`, `ENTRADA`, etc.).
6. Formato do arquivo solicitado.
7. Valor do campo `tipo` correspondente retornado no endpoint `/solicitacoes`.
8. Estrutura do arquivo XLSX gerado e nomenclatura das colunas.
9. Classificações aplicadas (se existem categorias Interna/Interestadual ou divisões específicas de consumidor final).

Todos os parâmetros descobertos devem ser documentados neste arquivo antes da habilitação em produção.

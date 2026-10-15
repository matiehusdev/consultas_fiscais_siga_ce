# Documentação de Integração: SIGA SEFAZ-CE (NF-e e NFC-e)

Este documento descreve detalhadamente o fluxo técnico, endpoints, métodos HTTP, parâmetros, payloads e estruturas de arquivos descobertos e verificados em tempo real na integração com o **SIGA (Sistema de Interface Guiada à Autorregularização)** da **SEFAZ-CE**.

---

## 1. Arquitetura de Autenticação e TLS (mTLS)

O portal SIGA utiliza SSO corporativo via Keycloak e exige múltiplos domínios para autenticação com Certificado Digital A1:

* **Portal Principal:** `https://siga.sefaz.ce.gov.br`
* **Serviço de SSO/Login:** `https://sso.sefaz.ce.gov.br`
* **Serviço TLS de Validação X.509:** `https://cert-sso.sefaz.ce.gov.br`

### Requisitos Técnicos
1. **Modernização PKCS#12 (OpenSSL 3.0+):** O Chromium rejeita certificados A1 ICP-Brasil legados (RC2-40/3DES/SHA-1). Os certificados devem ser convertidos dinamicamente para AES-256-CBC com PBKDF2/SHA-256.
2. **Contexto Multi-Origem:** O contexto TLS do navegador deve associar o certificado de cliente às três origens (`siga`, `sso` e `cert-sso`).
3. **Bearer Token JWT:** Após a autenticação mTLS e seleção do contribuinte, a SPA gera um token Bearer que deve ser incluído no cabeçalho `Authorization: Bearer <token>` em todas as chamadas às APIs internas (`/api/v1/*`).

---

## 2. Fluxo da NF-e (Modelo 55)

### 2.1. Solicitação de Download
* **Endpoint:** `POST /api/v1/unidades/{CNPJ}/documentos-fiscais/nf-e/resumos/eventos/download`
* **Método HTTP:** `POST`
* **Headers:**
  * `Authorization: Bearer <token>`
  * `Content-Type: application/json`
  * `Accept: application/json`
* **Payload JSON:**
  ```json
  {
    "dataReferencia": "YYYY-MM-DD,YYYY-MM-DD",
    "tipoOperacao": "SAIDA", // ou "ENTRADA"
    "formatoArquivo": "xlsx"
  }
  ```
* **Resposta de Sucesso:** `HTTP 202 Accepted` (com corpo vazio).

### 2.2. Acompanhamento de Processamento
* **Endpoint:** `GET /api/v1/solicitacoes?sort=criacao,desc`
* **Método HTTP:** `GET`
* **Headers:**
  * `Authorization: Bearer <token>`
  * `Accept: application/json`
* **Estrutura do Objeto na Resposta:**
  ```json
  {
    "id": "2581b119-0163-4591-9a3a-41e3d1bd9a12",
    "tipo": "NF_E_RESUMO_EVENTOS",
    "cnpjBase": "63330299",
    "cnpj": "63330299000162",
    "status": "CONCLUIDO", // "SOLICITADO", "PROCESSANDO", "CONCLUIDO", "ERRO"
    "expiracao": "2026-10-15",
    "criacao": "2026-10-13T18:05:09.883777"
  }
  ```

### 2.3. Download do Arquivo
* **Endpoint:** `GET /api/v1/solicitacoes/{id}/download`
* **Método HTTP:** `GET`
* **Headers:** `Authorization: Bearer <token>`
* **Status de Retorno:** `HTTP 200 OK`
* **Estrutura das Colunas do Arquivo:**
  * `mês`: Competência (ex: `2026-01`, `01/2026`)
  * `tipo`: Categoria de abrangência ou operação
  * `qtd NF-e emitidas`: Quantidade total emitida
  * `valor R$ NF-e emitidas`: Valor total emitido
  * `qtd NF-e emitidas autorizadas`: Quantidade autorizada
  * `valor R$ NF-e emitidas autorizadas`: **Valor efetivo considerado para faturamento**
  * `qtd NF-e emitidas canceladas`: Quantidade cancelada (auditoria)
  * `valor R$ NF-e emitidas canceladas`: Valor cancelado (auditoria)
  * `qtd NF-e emitidas denegadas`: Quantidade denegada (auditoria)
  * `valor R$ NF-e emitidas denegadas`: Valor denegado (auditoria)

---

## 3. Fluxo da NFC-e (Modelo 65)

### 3.1. Solicitação de Download
* **Endpoint:** `POST /api/v1/unidades/{CNPJ}/documentos-fiscais/nfc-e/download`
* **Método HTTP:** `POST`
* **Headers:**
  * `Authorization: Bearer <token>`
  * `Content-Type: application/json`
  * `Accept: application/json`
* **Payload JSON:**
  ```json
  {
    "dataReferencia": "YYYY-MM-DD,YYYY-MM-DD",
    "tipoOperacao": "SAIDA", // ou "ENTRADA"
    "formatoArquivo": "xlsx"
  }
  ```
* **Resposta de Sucesso:** `HTTP 202 Accepted`.

### 3.2. Acompanhamento de Processamento
* **Endpoint:** `GET /api/v1/solicitacoes?sort=criacao,desc`
* **Tipo no JSON:** `"tipo": "NFC_E"`
* **Status:** `"SOLICITADO"`, `"PROCESSANDO"`, `"CONCLUIDO"`.

### 3.3. Download do Arquivo e Estrutura das Colunas
* **Endpoint:** `GET /api/v1/solicitacoes/{id}/download`
* **Headers:** `Authorization: Bearer <token>`
* **Colunas Retornadas:**
  * `CNPJ/CPF destinatário`: Documento do comprador ou consumidor final
  * `Chave de acesso`: Chave de 44 dígitos da NFC-e
  * `Data de emissão`: Data e hora da autorização
  * `Base de cálculo do ICMS R$`: Base de tributação
  * `Valor do ICMS R$`: Imposto destacado
  * `Valor R$`: Valor total da nota autorizada

---

## 4. Regras Fiscais e Consolidação

1. **Autorizadas vs Canceladas/Denegadas:**
   * O faturamento e volume oficial são calculados **estritamente sobre as notas com status AUTORIZADO**.
   * Notas canceladas e denegadas são segregadas em abas específicas e colunas informativas de auditoria.
2. **Separação de Modelos:**
   * NF-e (Modelo 55) e NFC-e (Modelo 65) são processadas por analisadores independentes (`NFeProcessor` e `NFCeProcessor`).

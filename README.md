# SIGA Fiscal — Automação de Consultas Fiscais SEFAZ-CE

Sistema modular em Python para automação de consultas fiscais de **NF-e (Nota Fiscal Eletrônica)** e **NFC-e (Nota Fiscal de Consumidor Eletrônica)** no portal **SIGA (Sistema de Interface Guiada à Autorregularização)** da SEFAZ-CE.

O sistema utiliza o certificado digital A1 instalado no sistema operacional através de autenticação normal autorizada pelo usuário, realiza downloads assíncronos das planilhas XLSX oficiais, processa e valida as informações e consolida relatórios gerenciais em formatos Excel e PDF.

---

## Principais Funcionalidades

- **Gestão de Empresas:** Cadastro com validação estrita de dígitos verificadores de CNPJ, identificação automática de CNPJ Base, registro de CGF (SEFAZ-CE), ativação/desativação e busca avançada.
- **Sessões Isoladas por Empresa:** O processamento em lote é sequencial. Cada empresa inicia e encerra sua própria instância de navegador, impedindo vazamento de cookies ou contaminações de contexto.
- **Autenticação Segura com Certificado A1:** O sistema aguarda a seleção manual do certificado digital no navegador. Nenhuma senha, token ou chave privada é capturada ou gravada.
- **Tratamento Independente de Documentos:**
  - **NF-e (Modelo 55):** Entradas (Destinatário) e Saídas (Emissor).
  - **NFC-e (Modelo 65):** Entradas e Saídas com cliente desacoplado.
- **Regra Fundamental de Movimentação:** Totaliza exclusivamente documentos **autorizados**. Notas canceladas e denegadas são segregadas para fins de auditoria, garantindo precisão fiscal.
- **Relatórios Gerenciais:** Subtotais analíticos mensais separados para NF-e e NFC-e, seguidos do resumo consolidado total.
- **Interface Web Local Não-Bloqueante:** Painel desenvolvido em FastAPI + TailwindCSS para monitoramento em tempo real.
- **Rastreabilidade e Logs Sanitizados:** Mascaramento estrito de parâmetros de URLs pré-assinadas Amazon S3 (`X-Amz-*`) e tokens.

---

## Estrutura da Documentação

A documentação completa do projeto está organizada na pasta [`docs/`](docs/):

- [`SETUP.md`](docs/SETUP.md): Guia passo a passo para instalação em qualquer máquina nova.
- [`ARCHITECTURE.md`](docs/ARCHITECTURE.md): Arquitetura modular, camadas e fluxo de dados.
- [`SIGA_INTEGRATION.md`](docs/SIGA_INTEGRATION.md): Especificação dos endpoints da SEFAZ-CE, polling e fluxo S3.
- [`DATABASE.md`](docs/DATABASE.md): Esquema relacional do SQLite e dicionário de dados.
- [`REPORTS.md`](docs/REPORTS.md): Fórmulas de cálculo, tratamento de canceladas/denegadas e layout dos relatórios.
- [`TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md): Diagnóstico e resolução de incidentes.
- [`CHANGELOG.md`](docs/CHANGELOG.md): Histórico de versões e roadmap das fases.

---

## Início Rápido

### Requisitos:
- Windows 10/11
- Python 3.11 ou superior
- Certificado digital A1 instalado no repositório de certificados do Windows

### Execução em 2 Passos:
1. Execute `install.bat` (ou `pip install -r requirements.txt && python -m playwright install chromium`).
2. Execute `run.bat` (ou `python main.py`).
3. Acesse a interface web em [http://127.0.0.1:8000](http://127.0.0.1:8000).

---

## Status do Projeto (Fases de Desenvolvimento)

- [x] **FASE 1 — Estrutura:** Base do projeto, banco de dados SQLite, validação de CNPJ, interface web responsiva, CRUD de empresas e documentação técnica.
- [x] **FASE 2 — Navegador e Autenticação:** Instanciação Playwright com detecção de login e certificado A1 manual.
- [ ] **FASE 3 — Seleção do Contribuinte:** Seleção precisa da unidade cadastrada via CNPJ.
- [ ] **FASE 4 — NF-e:** Emissão de solicitação POST, polling e download de NF-e.
- [ ] **FASE 5 — NFC-e:** Descoberta com Network Sniffer e cliente autônomo.
- [ ] **FASE 6 — Processamento:** Processadores independentes e normalização de dados.
- [ ] **FASE 7 — Relatórios:** Geração dos arquivos Excel e PDF consolidados.
- [ ] **FASE 8 — Múltiplas Empresas:** Orquestrador sequencial com tolerância a falhas.
- [ ] **FASE 9 — Histórico:** Visualização de detalhes e reprocessamento de erros.
- [ ] **FASE 10 — Robustez:** Testes de ponta a ponta e auditoria de segurança.

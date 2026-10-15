# Histórico de Mudanças (CHANGELOG.md)

Todas as alterações notáveis deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/), e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [1.2.0] - 2026-10-13

### Adicionado (Fases 3, 4, 5, 6 e 7 — Execução Ponta a Ponta, Coleta, Processamento e Relatórios)
- **Ativação da Execução Automática de Consultas no Navegador:**
  - `POST /api/consultas` agora dispara imediatamente o `QueueManager` em segundo plano com Playwright Chromium.
  - Adicionado endpoint `POST /api/consultas/{id}/executar` para disparar consultas pendentes ou reexecutá-las a qualquer momento pelo Histórico.
  - Adicionado endpoint `POST /api/consultas/{id}/repetir-erros` permitindo reprocessar exclusivamente as empresas que apresentaram falha (Requisito 21).
  - Adicionado endpoint `POST /api/consultas/cancelar` com interrupção limpa do lote e fechamento seguro do navegador ativo.
  - Adicionado endpoint `GET /api/consultas/{id}/detalhes` fornecendo auditoria detalhada de cada contribuinte e lista de arquivos gerados.
  - Adicionado endpoint `GET /api/arquivos/{id}/download` para download com 1 clique de arquivos XLSX originais, relatórios em Excel e relatórios em PDF.
- **Painel em Tempo Real no Histórico:**
  - Banner ativo de monitoramento em tempo real com indicador pulsante, empresa atual, CNPJ e etapa do SIGA.
  - Atualização dinâmica via polling a cada 2 segundos sem necessidade de recarregar a página manualmente (F5).
  - Modal de detalhes com status de cada empresa, alertas de erro e links diretos para download dos relatórios.
- **Integração com SIGA SEFAZ-CE:**
  - `src/siga/contribuinte_selector.py`: Verificação e seleção de estabelecimentos/unidades por CNPJ no portal SIGA.
  - `src/siga/nfe_client.py`: Solicitação de download de NF-e (Modelo 55), acompanhamento de solicitações com matching estrito e download de arquivos com expurgo de credenciais Amazon S3.
  - `src/siga/nfce_client.py`: Cliente dedicado à NFC-e (Modelo 65) operando de forma autônoma e isolada de NF-e.
  - `scripts/discover_nfce.py`: Ferramenta interativa com sniffer de rede para descoberta de endpoints de NFC-e.
- **Processamento Fiscal e Agregação:**
  - `src/processor/nfe_processor.py` e `src/processor/nfce_processor.py`: Leitura e normalização de planilhas XLSX oficiais da SEFAZ-CE.
  - `src/processor/aggregator.py`: Aplicação mandatória da regra fiscal: totais de faturamento/movimentação baseiam-se **estritamente em notas autorizadas**; notas canceladas e denegadas são segregadas para auditoria.
- **Emissão de Relatórios Executivos:**
  - `src/reports/excel_reporter.py`: Geração de pasta de trabalho Excel estilizada com múltiplas abas (Resumo Consolidado, NF-e Saídas/Entradas, NFC-e Saídas/Entradas).
  - `src/reports/pdf_reporter.py`: Geração de relatórios executivos em PDF de alta qualidade com ReportLab.
- **Suíte de Testes Automatizados:** 46 testes unitários e de integração passando com 100% de sucesso.

---

## [1.1.0] - 2026-10-08

### Adicionado (Fase 2 — Navegador e Autenticação com Certificado A1)
- **Autenticação 100% Autônoma via Playwright TLS (`client_certificates`):**
  - Vinculação direta do arquivo de Certificado Digital A1 (`.pfx` / `.p12`) e senha à empresa.
  - Cifragem simétrica AES-128 em repouso da senha do certificado com chave mestra local (`src/utils/crypto.py`).
  - Validação rigorosa e extração de metadados do certificado (CN, Emissor, Validade) via PKCS#12 (`src/utils/cert_parser.py`).
  - O Playwright injeta o certificado diretamente no handshake TLS do Chromium, eliminando qualquer necessidade de interação manual ou clique na janela nativa do Windows durante consultas em lote.
  - Modo híbrido inteligente: se uma empresa possui o A1 cadastrado, a consulta roda 100% autônoma; se não possuir, o sistema aguarda seleção manual.
- **Interface Web de Gestão de Certificados:**
  - Coluna de status do Certificado A1 na tabela de empresas com badges informativos (`Autônomo (A1)` vs `Manual`).
  - Modal dedicado para upload, substituição, validação imediata e remoção segura de certificados.
  - Indicadores de execução autônoma na tela de Nova Consulta.
- **Módulo `BrowserSession` (`src/siga/browser_session.py`):**
  - Inicialização do Playwright Chromium em modo visível (`headless=False`) com tela maximizada e suporte a `client_certificates`.
  - Isolamento de contexto sem contaminação de cookies de sessões anteriores.
  - Finalização segura de recursos e tratamento de fechamento manual pelo usuário.
- **Módulo `Authenticator` (`src/siga/authentication.py`):**
  - Loop assíncrono não-bloqueante para detecção de login no SIGA SEFAZ-CE.
  - Orientação visual clara ao usuário para seleção manual do Certificado Digital A1 no Windows.
  - Detecção via interceptação de respostas HTTP da API (`/api/v1/`), rotas autenticadas e elementos do DOM.
  - Timeout configurável com tratamento de cancelamento e encerramento prematuro.
- **Transmissão em Tempo Real (`src/orchestrator/status_broadcaster.py`):**
  - Publicador thread-safe de eventos em tempo real integrado a Server-Sent Events (SSE) e polling.
  - Console interativo na página de Configurações para teste prático em um clique.
- **Ferramenta CLI de Diagnóstico (`scripts/test_auth.py`):**
  - Script interativo para testar o navegador e a seleção do certificado diretamente via terminal.
- **Testes Automatizados:** 6 novos testes específicos em `tests/test_browser_auth.py` com 100% de sucesso.

---

## [1.0.0] - 2026-10-08

### Adicionado (Fase 1 — Estrutura e Fundação)
- **Estrutura Modular:** Organização completa do projeto em camadas desacopladas (`src/web`, `src/database`, `src/siga`, `src/processor`, `src/reports`, `src/orchestrator`, `src/utils`).
- **Validador de CNPJ:** Algoritmo estrito de cálculo de dígitos verificadores de CNPJ e extração do CNPJ Base (`src/utils/cnpj_validator.py`).
- **Segurança de Logs:** Módulo de higienização de credenciais e mascaramento de parâmetros pré-assinados da Amazon S3 (`src/utils/sanitizers.py` e `src/utils/logger.py`).
- **Banco de Dados SQLite:**
  - Esquema relacional com tabelas `empresas`, `consultas`, `consultas_empresas`, `solicitacoes`, `arquivos`, `resultados` e `logs`.
  - Ativação obrigatória de chaves estrangeiras e modo WAL para concorrência segura.
  - Funções CRUD completas em `src/database/crud.py`.
- **Interface Web Local:**
  - Aplicação FastAPI servindo painel de controle moderno em TailwindCSS.
  - Tela de Dashboard com estatísticas em tempo real.
  - Tela de Empresas com modais de inclusão, edição, ativação/desativação e exclusão.
  - Tela de Nova Consulta com seleção múltipla, período de datas, opções de NF-e/NFC-e e Entradas/Saídas.
  - Tela de Histórico de Consultas.
  - Tela de Configurações de sistema e caminhos de armazenamento.
- **Portabilidade:**
  - Scripts Windows automatizados `install.bat` e `run.bat`.
  - Arquivo de configuração `.env.example` e carregador desacoplado em `src/config.py`.
- **Documentação Obrigatória Completa:**
  - `README.md`, `SETUP.md`, `ARCHITECTURE.md`, `SIGA_INTEGRATION.md`, `DATABASE.md`, `REPORTS.md`, `TROUBLESHOOTING.md` e `CHANGELOG.md`.
- **Suite de Testes Automatizados:** Testes unitários para validação de CNPJ, banco de dados e rotas da API.

---

## [Roadmap de Versões Futuras]
- **v1.1.0 (Fase 2):** Automação Playwright com suporte a janela visível e handshake de certificado digital A1.
- **v1.2.0 (Fase 3):** Seleção do contribuinte no SIGA via CNPJ.
- **v1.3.0 (Fase 4):** Cliente de NF-e assíncrono e download com redirecionamento S3.
- **v1.4.0 (Fase 5):** Sniffer de rede para NFC-e e cliente autônomo de NFC-e.
- **v1.5.0 (Fase 6):** Processadores de planilhas XLSX e modelos normalizados.
- **v1.6.0 (Fase 7):** Geração de relatórios consolidados em Excel e PDF.
- **v1.7.0 (Fase 8 & 9):** Fila sequencial multi-empresas e repetição de falhas.
- **v1.8.0 (Fase 10):** Validação de ponta a ponta e pacote executável.

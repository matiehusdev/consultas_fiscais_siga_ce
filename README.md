# Giro Empresarial — Gestão Fiscal & Automação SEFAZ-CE

<p align="center">
  <img src="src/web/static/img/logo_giro_empresarial.png" alt="Giro Empresarial" width="380">
</p>

<p align="center">
  <strong>Sistema Desktop Inteligente para Consultas Fiscais em Lote, Auditoria Contábil e Consolidação Executiva na SEFAZ-CE</strong>
</p>

<p align="center">
  <a href="https://github.com/matiehusdev/consultas_fiscais_siga_ce/releases/latest"><img src="https://img.shields.io/badge/Release-v1.3.1-0064e0.svg" alt="Versão v1.3.1"></a>
  <a href="#-testes-automatizados"><img src="https://img.shields.io/badge/Testes-74%20passed-22c55e.svg" alt="74 Testes Passando"></a>
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Plataforma-Windows%2010%20%2F%2011-0a1317.svg" alt="Windows 64-bit">
</p>

---

## 📖 Visão Geral do Projeto

O **Giro Empresarial** é uma solução corporativa desenvolvida para escritórios de contabilidade, consultorias tributárias e departamentos fiscais. O sistema automatiza integralmente a extração, auditoria, conciliação e geração de relatórios de **NF-e (Modelo 55)** e **NFC-e (Modelo 65)** diretamente do portal **SIGA (Sistema de Interface Guiada à Autorregularização)** da **SEFAZ-CE**.

Com uma interface moderna inspirada no *Meta Design System*, o sistema combina execução autônoma via **Certificado Digital A1**, tolerância avançada a falhas da SEFAZ, isolamento estrito de sessões por CNPJ e um **Motor de Integridade Fiscal** com proteção ativa contra download cruzado e race conditions assíncronas.

---

## 🔒 Diretriz de Segurança e Certificados Digitais

> [!IMPORTANT]
> **POLÍTICA DE PRIVACIDADE E CERTIFICADOS LOCAIS:**
> - **NENHUM certificado digital, arquivo `.pfx`/`.p12`, chave privada ou senha é versionado neste repositório.**
> - O arquivo `.gitignore` bloqueia estritamente quaisquer chaves criptográficas, credenciais locais (`.env`), bancos SQLite e relatórios gerados.
> - **Modos de Operação com Certificado:**
>   - **Vinculação Direta no Cadastro (.pfx / .p12):** Você pode anexar o arquivo A1 diretamente à empresa na tela **Empresas**. O sistema converte dinamicamente certificados legados (RC2-40/3DES) para criptografia moderna (**AES-256-CBC com PBKDF2/SHA-256** compatível com o Chromium), protege a senha em repouso com chave simétrica local (*Fernet*) e opera de forma 100% autônoma.
>   - **Certificado de Procurador / Contador:** Um único certificado pode gerenciar múltiplas empresas outorgadas; o robô realiza a seleção e confirmação automática de unidade no SIGA.
>   - **Repositório do Windows:** Caso prefira não importar o arquivo, o sistema detecta os certificados instalados no repositório nativo (`certmgr.msc`).

---

## ⚡ Diferenciais & Motor de Integridade Fiscal (v1.3.1)

### 1. Rastreamento Estrito de Solicitações Assíncronas (Anti-Race Condition)
O portal SIGA opera downloads em fila assíncrona (`/downloads-assincronos`). O robô intercepta as respostas das requisições REST da SEFAZ, correlaciona o identificador único da solicitação (`solicitacao_id`) e aguarda a conclusão **exclusivamente do registro correspondente à operação atual**, impedindo que solicitações anteriores concluídas contaminem a operação seguinte.

### 2. Guarda Contra Colisão de Hash (Operation Segregation)
Ao processar operações opostas (Saídas vs Entradas) de uma mesma empresa, o sistema compara as assinaturas criptográficas **SHA-256** dos arquivos baixados. Se houver identidade binária entre os arquivos, o sistema rejeita a atribuição espúria, registra alertas de auditoria e garante que o faturamento de Saída nunca seja atribuído à Entrada.

### 3. Normalização e Truncamento Temporal
Parsers fiscais robustos que extraem a porção de data pura antes de realizar o matching mensal ou de período (`matches_period`), suportando timestamps detalhados (`DD/MM/YYYY HH:MM:SS`), formatos ISO e variações de acentuação sem descarte indevido de notas fiscais.

### 4. Auditoria Fiscal: Faturamento Baseado em Notas Autorizadas
A apuração contábil baseia-se **estritamente em notas com status AUTORIZADO**. Notas fiscais canceladas e denegadas são segregadas em colunas independentes para conferência de conformidade e auditoria tributária.

### 5. Atualizador Inteligente & Preservação Total de Dados
O instalador detecta versões legadas instaladas, destaca o botão de atualização com comparativo de versões, fecha processos travados mediante confirmação e garante que o banco SQLite (`data/db/siga_fiscal.db`), certificados e relatórios nunca sejam excluídos, exibindo diálogo explícito de confirmação de sucesso com inicialização direta.

---

## 📊 Relatórios Gerados

O sistema produz automaticamente três níveis de documentação a cada lote consultado:

1. **Relatório Consolidado do Lote (Multi-Empresas):**
   - Disponível em **Excel (XLSX)** e **PDF Executivo**.
   - Resumo corporativo direto:
     ```text
     # | EMPRESAS | VALOR ENTRADAS | VALOR SAÍDAS
     ```
   - Totalizadores gerais e auditoria de notas canceladas por contribuinte.
2. **Relatório Analítico Individual (Por Empresa):**
   - Quadros demonstrativos segmentados por abrangência (Operações Internas, Interestaduais e Exterior).
   - Segregação clara entre NF-e (Modelo 55) e NFC-e (Modelo 65).
3. **Planilhas Originais da SEFAZ:**
   - Armazenadas e organizadas por lote e CNPJ na pasta de consultas para fins de compliance fiscal.

---

## 📥 Como Baixar e Instalar

### 1. Pré-requisitos
- **Windows 10 ou 11 (64 bits)**.
- **Python 3.11 ou superior**:
  - Baixe no site oficial: [python.org/downloads](https://www.python.org/downloads/)
  - > [!IMPORTANT]
    > Na primeira tela do instalador do Python, marque obrigatoriamente:  
    > ☑️ **"Add python.exe to PATH"** (Adicionar Python ao PATH).
- **Certificado Digital A1** (da empresa ou contador).

---

### 2. Download do Instalador Oficial

Clique no link abaixo para baixar a versão mais recente:

👉 **[Baixar Instalador_Giro_Empresarial.exe (Download Direto)](https://github.com/matiehusdev/consultas_fiscais_siga_ce/releases/latest/download/Instalador_Giro_Empresarial.exe)**

*(Todas as versões e notas de atualização estão disponíveis na [página de Releases no GitHub](https://github.com/matiehusdev/consultas_fiscais_siga_ce/releases)).*

#### Como utilizar o Instalador:
1. Dê um clique duplo em `Instalador_Giro_Empresarial.exe`.
2. O instalador configura todo o ecossistema em **1 clique**:
   - Prepara e copia os componentes do sistema para o seu usuário.
   - Instala as dependências necessárias de alto desempenho.
   - Configura o navegador Chromium com suporte a mTLS para SEFAZ-CE.
   - Inicializa o banco de dados SQLite local.
   - **Cria automaticamente os atalhos oficiais na Área de Trabalho e no Menu Iniciar**.
3. Ao finalizar, o sistema já inicia e abre seu navegador padrão em `http://127.0.0.1:8000`.

---

## 🚀 Como Iniciar a Aplicação

### Após a Instalação (Recomendado)
- Pressione a tecla `Windows`, digite **"Giro Empresarial"** e pressione `Enter`.
- Ou clique no **atalho na Área de Trabalho** criado pelo instalador.

O servidor web é inicializado e o navegador padrão abre automaticamente em:  
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

### Modo Desenvolvedor / Terminal

Para desenvolvedores que desejam executar o código-fonte via Git:

```bash
# 1. Clonar o repositório
git clone https://github.com/matiehusdev/consultas_fiscais_siga_ce.git
cd consultas_fiscais_siga_ce

# 2. Instalação e configuração inicial
install.bat

# 3. Iniciar o servidor
run.bat
# (Ou execute diretamente: python main.py)
```

---

## 🏗️ Arquitetura do Sistema

```text
consultas_fiscais_siga_ce/
├── src/
│   ├── config.py                 # Configurações globais e diretórios de execução
│   ├── bootstrap.py              # Auto-setup inicial de ambiente, deps e atalhos
│   ├── database/                 # Camada de persistência (SQLAlchemy + SQLite WAL)
│   │   ├── models.py             # Modelos (Empresa, Consulta, Solicitacao, etc.)
│   │   ├── crud.py               # Operações transacionais e criptografia de senhas
│   │   └── connection.py         # Gerenciamento de sessões do banco de dados
│   ├── orchestrator/             # Orquestrador de fila e eventos em tempo real
│   │   ├── queue_manager.py      # Execução sequencial, retry e guarda SHA-256
│   │   └── status_broadcaster.py # Publicador SSE de progresso para a UI
│   ├── processor/                # Parsers fiscais contábeis
│   │   ├── nfe_processor.py      # Normalizador analítico/sintético de NF-e (Mod 55)
│   │   ├── nfce_processor.py     # Processador e auto-detecção de NFC-e (Mod 65)
│   │   └── aggregator.py         # Consolidador contábil e auditor de notas
│   ├── reports/                  # Mecanismo de exportação de relatórios
│   │   ├── batch_reporter.py     # Relatório consolidado executivo do lote
│   │   ├── excel_reporter.py     # Relatório individual formatado em XLSX
│   │   └── pdf_reporter.py       # Relatório executivo institucional em PDF
│   ├── siga/                     # Integração com o portal SIGA SEFAZ-CE
│   │   ├── browser_session.py    # Contexto Playwright isolado com TLS multi-origem
│   │   ├── authentication.py     # Fluxo SSO mTLS e autenticação A1
│   │   ├── contribuinte_selector # Seletor de unidades e outorgantes
│   │   ├── ui_downloader.py      # Robô visual para downloads assíncronos
│   │   ├── nfe_client.py         # Cliente REST / API para NF-e
│   │   └── nfce_client.py        # Cliente REST / API para NFC-e
│   ├── utils/                    # Utilitários, criptografia e validação
│   │   ├── crypto.py             # Criptografia simétrica Fernet de senhas locais
│   │   ├── cert_parser.py        # Modernizador PKCS#12 e extrator X.509
│   │   ├── cnpj_validator.py     # Validador e formatador estrito de CNPJ
│   │   └── date_helpers.py       # Normalizadores temporais e matching de períodos
│   └── web/                      # Interface Web (FastAPI + Jinja2 + SSE)
│       ├── app.py                # Rotas da aplicação, dashboards e APIs
│       ├── templates/            # Telas HTML modernas (Meta Design System)
│       └── static/               # Folhas de estilo, ícones e assets visuais
├── tests/                        # Suíte de testes unitários e de integração (70 testes)
├── installer.py                  # Código-fonte do Instalador Gráfico em 1 clique
├── launcher.py                   # Inicializador executável desktop
├── Giro Empresarial.spec         # Especificação de compilação PyInstaller do App
└── Instalador_Giro_Empresarial.spec # Especificação de compilação do Instalador
```

---

## 🧪 Testes Automatizados

O projeto possui uma suíte rigorosa de **74 testes automatizados**, cobrindo validação de CNPJ, criptografia e modernização de certificados A1, isolamento de sessões no navegador, integridade de downloads assíncronos, proteção contra colisão de hash, parsers fiscais, renderização dinâmica de versão e rotinas de atualização do instalador:

```bash
pytest
```

---

## 📄 Licença e Direitos

Projeto desenvolvido para automação fiscal corporativa — **Giro Empresarial**.  
Todos os direitos reservados.

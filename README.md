# Consultas Fiscais SIGA SEFAZ-CE

Sistema automatizado de alta confiabilidade em Python para consultas e consolidação fiscal de **NF-e (Nota Fiscal Eletrônica - Modelo 55)** e **NFC-e (Nota Fiscal de Consumidor Eletrônica - Modelo 65)** no portal **SIGA (Sistema de Interface Guiada à Autorregularização)** da SEFAZ-CE.

---

## 🔒 Diretriz de Segurança e Certificados Digitais

> [!IMPORTANT]
> **POLÍTICA DE PRIVACIDADE E CERTIFICADOS LOCAIS:**
> - **NENHUM certificado digital, arquivo `.pfx`, `.p12`, chave privada ou senha é versionado neste repositório.**
> - O arquivo `.gitignore` bloqueia estritamente quaisquer chaves, certificados, credenciais locais (`.env`) e dados de bancos locais.
> - **Cada usuário/máquina que baixar ou clonar o projeto deve configurar seus próprios certificados digital A1 localmente** (instalado no repositório de certificados do Windows ou cadastrado via interface local em ambiente seguro).

---

## 🚀 Principais Funcionalidades

- **Automação Visual Resiliente:** Execução do fluxo de consulta diretamente na interface do portal SIGA (`Informações Fiscais` -> Seleção de Ano -> Alternância `Emissor`/`Destinatário` -> Solicitação e Download via `Downloads Assíncronos`).
- **Relatório Executivo Consolidado:** Layout executivo no padrão solicitado:
  `EMPRESAS | VALOR ENTRADAS | VALOR SAIDAS`
  com filtro estrito para o mês/competência escolhido.
- **Suporte Multi-Empresa em Lote:** Processamento sequencial com sessões isoladas para cada empresa no navegador.
- **Segregação de Auditoria Fiscal:** Contabiliza exclusivamente documentos fiscais **autorizados**, segregando canceladas e denegadas para fins de conferência e auditoria.
- **Interface Web em Tempo Real:** Painel web moderno construído com FastAPI e TailwindCSS, com acompanhamento de progresso via Server-Sent Events (SSE) e exportação em Excel e PDF.

---

## 🛠️ Instalação e Execução em uma Nova Máquina

### Pré-requisitos
- **Windows 10 ou 11**
- **Python 3.11 ou superior**
- **Certificado Digital A1** válido instalado no Windows ou arquivo `.pfx` para importação local.

### 1. Clonar o repositório
```bash
git clone https://github.com/matiehusdev/consultas_fiscais_siga_ce.git
cd consultas_fiscais_siga_ce
```

### 2. Configurar o ambiente local
Copie o arquivo de exemplo de ambiente:
```bash
copy .env.example .env
```

### 3. Instalar dependências e navegadores
Execute o script automatizado:
```cmd
install.bat
```
*(Ou manualmente: `pip install -r requirements.txt && python -m playwright install chromium`)*

### 4. Iniciar a aplicação
```cmd
run.bat
```
*(Ou manualmente: `python main.py`)*

Acesse no navegador: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 🧪 Testes Automatizados

O projeto conta com suite completa de testes automatizados unitários e de integração:
```bash
pytest
```

---

## 📚 Documentação Técnica

- [`docs/SETUP.md`](docs/SETUP.md): Guia detalhado de configuração e primeiros passos.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): Arquitetura das camadas (Siga, Processor, Orchestrator, Web, Reports).
- [`docs/SIGA_INTEGRATION.md`](docs/SIGA_INTEGRATION.md): Fluxos de navegação e integração com o portal SIGA.
- [`docs/DATABASE.md`](docs/DATABASE.md): Estrutura do banco de dados SQLite local.
- [`docs/REPORTS.md`](docs/REPORTS.md): Regras de cálculo e layouts dos relatórios.
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md): Guia de resolução de problemas e mensagens da SEFAZ.

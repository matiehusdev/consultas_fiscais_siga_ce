# Giro Empresarial — Gestão Fiscal & Automação SEFAZ-CE

<p align="center">
  <img src="src/web/static/img/logo_giro_empresarial.png" alt="Giro Empresarial" width="380">
</p>

Sistema automatizado de alta performance e confiabilidade em Python para consultas fiscais em lote, auditoria e consolidação executiva de **NF-e (Nota Fiscal Eletrônica - Modelo 55)** e **NFC-e (Nota Fiscal de Consumidor Eletrônica - Modelo 65)** no portal **SIGA (Sistema de Interface Guiada à Autorregularização)** da SEFAZ-CE.

---

## 🔒 Diretriz de Segurança e Certificados Digitais

> [!IMPORTANT]
> **POLÍTICA DE PRIVACIDADE E CERTIFICADOS LOCAIS:**
> - **NENHUM certificado digital, arquivo `.pfx`, `.p12`, chave privada ou senha é versionado neste repositório.**
> - O arquivo `.gitignore` bloqueia estritamente quaisquer chaves, certificados, credenciais locais (`.env`), dados de bancos SQLite locais e relatórios de clientes.
> - **Cada usuário/máquina deve configurar seus próprios certificados digitais A1 localmente** (instalado no repositório de certificados do Windows ou cadastrado via interface web em ambiente seguro).

---

## 🚀 Principais Funcionalidades

- **Auto-Setup na Primeira Abertura:** O sistema configura automaticamente dependências, navegador Chromium do Playwright, banco de dados SQLite e atalhos na primeira execução.
- **Execução via Clique Duplo:** Aplicativo desktop com inicializador executável nativo (`Giro Empresarial.exe`) com ícone oficial da marca.
- **Atalho no Pesquisar do SO:** Criação automática de atalho no Menu Iniciar (`Start Menu`), permitindo abrir a aplicação pesquisando "Giro Empresarial" no Windows.
- **Abertura Automática do Navegador:** Ao iniciar o servidor local, o navegador padrão é aberto automaticamente em `http://127.0.0.1:8000`.
- **Automação SEFAZ-CE Resiliente:** Processamento sequencial com isolamento estrito de unidades/contribuintes, retry automático para instabilidades da SEFAZ e suporte a Certificado Digital A1.
- **Relatório Executivo Consolidado:** Layout corporativo executivo sintetizado:
  `# | EMPRESAS | VALOR ENTRADAS | VALOR SAÍDAS`
  com filtro estrito para o mês/competência escolhido e exportação em **PDF** e **Excel (XLSX)**.
- **Tolerância a Falhas & Repetir Erros:** Detecção inteligente de erros parciais com opção de repetir processamento apenas para as empresas com falha no lote.

---

## 🛠️ Instalação e Execução

### Pré-requisitos
- **Windows 10 ou 11 (64 bits)**
- **Python 3.11 ou superior**
- **Certificado Digital A1** válido (instalado no Windows ou configurado no painel da aplicação).

---

### Opção 1: Execução Direta / Desktop (Recomendada)

Se você já possui o repositório ou recebeu o pacote da aplicação:

1. Dê um **clique duplo** em **`Giro Empresarial.exe`** (ou no atalho da Área de Trabalho / Menu Iniciar).
2. Na **primeira abertura**, o sistema executa o *Auto-Setup* (prepara o banco de dados, verifica componentes e cria os atalhos com ícone no Menu Iniciar e Desktop).
3. O servidor web iniciará e seu navegador padrão abrirá automaticamente em **[http://127.0.0.1:8000](http://127.0.0.1:8000)**.

> [!TIP]
> Você também pode abrir a aplicação a qualquer momento pressionando a tecla `Windows` e digitando **"Giro Empresarial"**.

---

### Opção 2: Instalador Guiado

Para configurar o ambiente do zero via assistente:

```cmd
python installer.py
```
*(Ou execute `Instalador_Giro_Empresarial.exe`)*

O instalador verificará o ambiente, instalará dependências, configurará o Chromium e gerará os atalhos do sistema com um único clique.

---

### Opção 3: Modo Desenvolvedor / Terminal

Para desenvolvedores que clonaram o código-fonte via Git:

#### 1. Clonar o repositório
```bash
git clone https://github.com/matiehusdev/consultas_fiscais_siga_ce.git
cd consultas_fiscais_siga_ce
```

#### 2. Instalação e Configuração Inicial
Execute o script automatizado:
```cmd
install.bat
```
*(Ele verifica o Python, instala os pacotes do `requirements.txt` e roda o `src/bootstrap.py` para criar banco, `.env` e atalhos).*

#### 3. Iniciar o servidor
```cmd
run.bat
```
*(Ou execute: `python main.py`)*

O sistema iniciará o servidor FastAPI/Uvicorn em `http://127.0.0.1:8000` e abrirá o navegador automaticamente.

---

## 🧪 Testes Automatizados

O projeto conta com uma suíte de 65 testes automatizados cobrindo autenticação, seleção de contribuintes, validação de CNPJ, processamento de relatórios e endpoints da API:

```bash
pytest
```

---

## 📚 Documentação Técnica

- [`docs/SETUP.md`](docs/SETUP.md): Guia detalhado de configuração e primeiros passos.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): Arquitetura das camadas (Siga, Processor, Orchestrator, Web, Reports).
- [`docs/SIGA_INTEGRATION.md`](docs/SIGA_INTEGRATION.md): Fluxos de navegação e integração com o portal SIGA SEFAZ-CE.
- [`docs/DATABASE.md`](docs/DATABASE.md): Estrutura do banco de dados SQLite local.
- [`docs/REPORTS.md`](docs/REPORTS.md): Regras de cálculo e layouts dos relatórios consolidados.
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md): Guia de resolução de problemas e mensagens da SEFAZ.

---

## 📄 Licença
Uso interno e restrito — Giro Empresarial. Todos os direitos reservados.

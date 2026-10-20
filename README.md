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
> - **Cada usuário/máquina deve configurar seus próprios certificados digitais A1 localmente:**
>   - **Vinculação direta via Web (.pfx / .p12):** Você pode anexar o arquivo do Certificado A1 diretamente no cadastro da empresa na tela **Empresas** informando a senha. O sistema valida os dados do titular em tempo de execução, moderniza a criptografia para compatibilidade com o navegador (AES-256) e protege a senha em repouso com chave simétrica local.
>   - **Repositório nativo do Windows:** Alternativamente, o certificado A1 pode ser instalado no repositório de certificados do Windows (`certmgr.msc`) para seleção interativa durante a consulta.

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

## 📥 Como Baixar (Download)

### 1. O que você precisa ter instalado na máquina
Antes de abrir o programa, certifique-se de que a máquina possui:
- **Windows 10 ou 11 (64 bits)**
- **Python 3.11 ou superior**:
  - Baixe no site oficial: [python.org/downloads](https://www.python.org/downloads/)
  - > [!IMPORTANT]
    > Na primeira tela do instalador do Python, **marque obrigatoriamente a opção:**  
    > ☑️ **"Add python.exe to PATH"** (Adicionar Python ao PATH).
- **Certificado Digital A1** da empresa ou do escritório de contabilidade (instalado no Windows ou arquivo `.pfx`).

---

### 2. Passo a passo para baixar o Giro Empresarial

Você tem duas formas de baixar:

#### Opção A: Download Direto em Arquivo ZIP (Mais Simples)
1. Acesse a página do projeto no GitHub: **[consultas_fiscais_siga_ce](https://github.com/matiehusdev/consultas_fiscais_siga_ce)**.
2. Clique no botão verde **`Code` ▾** (localizado no canto superior direito).
3. Clique em **`Download ZIP`** (ou baixe diretamente por [este link](https://github.com/matiehusdev/consultas_fiscais_siga_ce/archive/refs/heads/main.zip)).
4. Após o download, clique com o botão direito no arquivo baixado (`consultas_fiscais_siga_ce-main.zip`) e selecione **"Extrair Tudo..."** para uma pasta do seu computador (por exemplo: `C:\Giro Empresarial` ou em `Documentos`).

#### Opção B: Via Git (Para Desenvolvedores)
```bash
git clone https://github.com/matiehusdev/consultas_fiscais_siga_ce.git
cd consultas_fiscais_siga_ce
```

---

### 3. O que vem no pacote baixado
Ao extrair o pacote, você terá:
- **`Giro Empresarial.exe`:** Executável principal para iniciar o sistema com clique duplo.
- **`installer.py`:** Assistente gráfico de instalação e verificação rápida.
- **`run.bat` e `install.bat`:** Scripts em lote alternativos para inicialização rápida via prompt.
- **Estrutura completa da aplicação:** Código-fonte seguro, pastas de dados locais e ícones da marca.

---

## 🛠️ Como Iniciar a Aplicação

### Opção 1: Inicialização Rápida Desktop (Recomendada)

1. Entre na pasta extraída e dê um **clique duplo** em **`Giro Empresarial.exe`**.
2. **Na primeira abertura**, o sistema roda o **Auto-Setup** automaticamente:
   - Instala as bibliotecas necessárias.
   - Configura o navegador Chromium do Playwright para automação SEFAZ.
   - Inicializa o banco de dados SQLite local.
   - **Cria automaticamente o atalho oficial com a logo na Área de Trabalho e no Menu Iniciar**.
3. O servidor web inicia e o seu **navegador padrão abre sozinho** no endereço:  
   👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

> [!TIP]
> Após a primeira abertura, você nunca mais precisa procurar a pasta: basta pressionar a tecla `Windows` no teclado, digitar **"Giro Empresarial"** e apertar `Enter`, ou clicar no atalho da sua Área de Trabalho!

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

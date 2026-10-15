# Guia de Configuração e Instalação (SETUP.md)

Este documento fornece um guia passo a passo detalhado para que qualquer desenvolvedor ou operador consiga configurar e executar o **SIGA Fiscal** em uma máquina Windows totalmente nova do zero.

---

## 1. Requisitos do Sistema Operacional

- **Sistema:** Windows 10 ou Windows 11 (64 bits).
- **Acesso à Internet:** Liberado para os domínios `siga.sefaz.ce.gov.br` e `sefaz-ce-aplicacoes-prod.s3.sa-east-1.amazonaws.com`.
- **Privilégios:** Usuário padrão ou administrador para instalação do Python.

---

## 2. Passo a Passo de Instalação

### Passo 1: Instalação do Python
1. Baixe o instalador oficial do Python 3.11 ou superior em [python.org/downloads](https://www.python.org/downloads/).
2. Ao executar o instalador, **marque obrigatoriamente a opção**:
   `[x] Add python.exe to PATH`
3. Conclua a instalação e abra um novo terminal PowerShell ou Prompt de Comando (CMD).
4. Confirme a versão digitando:
   ```powershell
   python --version
   ```

---

### Passo 2: Instalação das Dependências do Projeto
1. Navegue até o diretório do projeto:
   ```powershell
   cd "C:\caminho\para\siga_fiscal"
   ```
2. Instale todas as bibliotecas necessárias listadas em `requirements.txt`:
   ```powershell
   pip install -r requirements.txt
   ```

---

### Passo 3: Instalação dos Navegadores do Playwright
O Playwright necessita dos binários de navegador para automação:
```powershell
python -m playwright install chromium
```
*(Caso deseje utilizar o navegador Google Chrome ou Microsoft Edge já instalado no Windows, o sistema suporta o canal nativo).*

---

### Passo 4: Verificação do Certificado Digital A1
1. Certifique-se de que o certificado digital A1 da empresa está devidamente importado no repositório de certificados do Windows.
2. Para conferir:
   - Pressione `Win + R`, digite `certmgr.msc` e pressione Enter.
   - Navegue em: **Pessoal > Certificados**.
   - O certificado deve constar na lista com validade ativa e chave privada associada.
3. **Importante:** O SIGA Fiscal não exige que você informe senhas no código ou no banco. O navegador exibirá a janela nativa de seleção quando a SEFAZ solicitar.

---

### Passo 5: Configuração do Ambiente (.env)
1. Na raiz do projeto, copie o arquivo `.env.example` para `.env`:
   ```powershell
   copy .env.example .env
   ```
2. Caso deseje alterar a porta padrão (`8000`) ou o tempo de espera para a seleção do certificado (`CERTIFICATE_SELECTION_TIMEOUT_SECONDS=120`), edite o arquivo `.env`.

---

### Passo 6: Inicialização Automática (Scripts Windows)
Se preferir, os passos 2 a 5 podem ser realizados automaticamente com um duplo clique no script:
- `install.bat`

---

### Passo 7: Iniciar a Aplicação
Execute no terminal:
```powershell
python main.py
```
ou dê um duplo clique no arquivo:
- `run.bat`

O terminal exibirá a mensagem indicando que o servidor está no ar:
```text
INFO: Servidor Web acessível em: http://127.0.0.1:8000
```
Abra seu navegador em `http://127.0.0.1:8000`.

---

### Passo 8: Cadastrar Empresas
1. Na barra superior, clique na aba **Empresas**.
2. Clique no botão verde **Adicionar Empresa**.
3. Preencha a Razão Social, CNPJ (com validação automática) e o CGF da SEFAZ-CE.
4. Salve o cadastro.

---

### Passo 9: Executar a Primeira Consulta
1. Na barra superior, clique em **Nova Consulta**.
2. Marque a(s) empresa(s) desejada(s).
3. Defina a data inicial e a data final (ex: `2026-01-01` a `2026-09-30`).
4. Selecione os tipos de documentos (NF-e, NFC-e) e as operações (Entradas, Saídas).
5. Clique em **INICIAR CONSULTA SEQUENCIAL**.
6. Quando o navegador abrir a página do SIGA, selecione o certificado digital A1 correspondente na tela do Windows.
7. O sistema detectará o login e conduzirá automaticamente as solicitações, downloads e consolidação de relatórios.

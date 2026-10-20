# Guia de Resolução de Problemas (TROUBLESHOOTING.md)

Este documento reúne diagnósticos, causas raízes e soluções para os cenários de erro mais comuns durante a operação do **SIGA Fiscal**.

---

## 1. Problemas de Certificado Digital e Autenticação

### 1.1 A janela de seleção de certificados não aparece no navegador
- **Causa:** O certificado A1 não está importado no repositório de certificados do Windows do usuário atual ou expirou.
- **Solução:**
  1. Abra o Executar (`Win + R`), digite `certmgr.msc` e vá em **Pessoal > Certificados**.
  2. Verifique se o certificado da empresa consta na lista e se a data de validade está vigente.
  3. Se não constar, instale o arquivo `.pfx` com duplo clique, marcando a opção de repositório "Usuário Atual" e "Marcar esta chave como exportável".
  4. Reinicie a aplicação e tente novamente.

### 1.2 Certificado selecionado incorreto pelo operador
- **Causa:** O usuário selecionou na janela nativa o certificado de outra empresa diferente da empresa indicada na fila da aplicação.
- **Solução:**
  1. O sistema exibirá aviso de divergência de CNPJ se o login for concluído sob outra titularidade.
  2. Cancele a execução da empresa no painel ou feche a janela do navegador. O orquestrador registrará a falha nessa empresa e passará para a próxima sem afetar o lote.

### 1.3 O login no SIGA não conclui após selecionar o certificado
- **Causa:** Instabilidade temporária no portal da SEFAZ-CE ou bloqueio de firewall corporativo.
- **Solução:**
  1. Verifique se o portal `https://siga.sefaz.ce.gov.br/` abre normalmente no seu navegador de uso diário (Google Chrome ou Edge).
  2. Ajuste o parâmetro `CERTIFICATE_SELECTION_TIMEOUT_SECONDS` no arquivo `.env` para um valor maior (ex: `180` ou `240`) se a SEFAZ estiver com latência elevada.

### 1.4 Erro ao anexar ou vincular o Certificado Digital A1 (.pfx/.p12) na tela Empresas
- **Causa:** O ambiente Python da máquina pode não ter a biblioteca `python-multipart` instalada (necessária para upload de formulários e arquivos no FastAPI), ou a senha informada para o certificado está incorreta.
- **Solução:**
  1. O sistema inclui auto-recuperação automática. Execute o script `install.bat` na pasta do programa para garantir que todas as dependências estejam instaladas.
  2. Se preferir pelo terminal, execute: `pip install python-multipart`.
  3. Certifique-se de preencher a senha correta do arquivo `.pfx` no modal de vinculação. O sistema informa exatamente na tela se a senha for inválida ou se o arquivo estiver expirado.

---

## 2. Sessão e Contribuinte no SIGA

### 2.1 Empresa não encontrada na listagem de contribuintes do SIGA
- **Causa:** O certificado digital utilizado não possui procuração eletrônica ou vínculo ativo com o CNPJ cadastrado na base da SEFAZ-CE.
- **Solução:**
  1. Acesse manualmente o portal da SEFAZ com o mesmo certificado e confirme se a empresa aparece na lista de outorgas/procurações.
  2. Cadastre a procuração eletrônica no portal da SEFAZ-CE antes de executar a automação.

### 2.2 Sessão expirou durante o processamento
- **Causa:** O portal da SEFAZ encerrou o token de acesso por inatividade do servidor da Fazenda.
- **Solução:**
  1. O orquestrador encerra o navegador automaticamente e registra status de erro na empresa afetada.
  2. Utilize o botão **Repetir Consultas com Erro** no histórico para executar novamente a empresa isoladamente.

---

## 3. Solicitação e Download de Arquivos

### 3.1 A solicitação não conclui (fica em PENDENTE ou PROCESSANDO por muito tempo)
- **Causa:** Fila de processamento assíncrono sobrecarregada nos servidores da SEFAZ-CE para períodos longos.
- **Solução:**
  1. Aumente o `MAX_POLLING_ATTEMPTS` no `.env` (ex: de 60 para 120 tentativas).
  2. Experimente consultar períodos menores (ex: trimestre a trimestre em vez do ano completo).

### 3.2 O download do arquivo falha após o status CONCLUIDO
- **Causa:** Expiração do redirecionamento HTTP 302 ou bloqueio de rede para o bucket Amazon S3 (`sefaz-ce-aplicacoes-prod.s3.sa-east-1.amazonaws.com`).
- **Solução:**
  1. Confirme se o firewall corporativo não bloqueia conexões diretas para buckets S3 na região `sa-east-1` (São Paulo).
  2. O sistema possui retry automático com timeout configurável no `downloader.py`.

### 3.3 Arquivo baixado é um XLSX inválido ou corrompido
- **Causa:** A SEFAZ respondeu com página HTML de erro (ex: 500 ou 503) em vez de binário XLSX real.
- **Solução:**
  1. O validador de integridade do sistema verifica o cabeçalho PK (`b"PK\x03\x04"`) antes de passar ao processador.
  2. Se corrompido, o arquivo é descartado, a falha é registrada e o download pode ser repetido.

---

## 4. Diferenças entre NF-e e NFC-e

### 4.1 NF-e funciona normalmente, mas NFC-e apresenta erro
- **Causa:** A empresa pode ser do regime ou atividade que não emite NFC-e (ex: indústria pura ou comércio atacadista interestadual exclusivo), ou o layout da NFC-e possui parâmetros de data específicos na SEFAZ.
- **Solução:**
  1. Verifique se a empresa possui autorização/emissões de NFC-e na SEFAZ.
  2. Inspecione o endpoint de NFC-e utilizando o modo de captura (`scripts/discover_nfce.py`).

### 4.2 NFC-e funciona, mas NF-e não
- **Causa:** Filtro de data de NF-e fora do limite permitido ou indisponibilidade temporária do módulo de NF-e na SEFAZ.
- **Solução:**
  1. Verifique se a data final atende à regra de competência do SIGA.
  2. Acompanhe os logs estruturados no painel em **Histórico**.

---

## 5. Mudanças no Portal do SIGA

### 5.1 O layout da página ou a estrutura de colunas do XLSX mudou
- **Causa:** A SEFAZ-CE publicou uma nova versão de suas APIs internas ou modificou o template Excel.
- **Solução:**
  1. Consulte a especificação em `docs/SIGA_INTEGRATION.md`.
  2. O processador em `src/processor/normalizer.py` possui mapeamento por sinônimos de colunas para absorver variações menores de cabeçalhos sem quebrar a aplicação.

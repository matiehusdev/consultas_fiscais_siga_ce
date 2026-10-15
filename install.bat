@echo off
chcp 65001 >nul
echo ========================================================
echo        INSTALAÇÃO DO SISTEMA SIGA FISCAL (SEFAZ-CE)
echo ========================================================

echo.
echo [1/4] Verificando versão do Python...
python --version
if errorlevel 1 (
    echo [ERRO] Python não foi encontrado no PATH. Instale o Python 3.11+ e tente novamente.
    pause
    exit /b 1
)

echo.
echo [2/4] Instalando dependências do projeto (requirements.txt)...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependências.
    pause
    exit /b 1
)

echo.
echo [3/4] Instalando binários do navegador Playwright (Chromium)...
python -m playwright install chromium

echo.
echo [4/4] Verificando arquivo de configuração (.env)...
if not exist .env (
    copy .env.example .env
    echo Arquivo .env criado a partir de .env.example.
) else (
    echo Arquivo .env já existente mantido.
)

echo.
echo Inicializando banco de dados...
python -c "from src.database.connection import init_db; init_db(); print('Banco de dados SQLite inicializado com sucesso!')"

echo.
echo ========================================================
echo   Instalação concluída com sucesso!
echo   Execute 'run.bat' para iniciar a aplicação.
echo ========================================================
pause

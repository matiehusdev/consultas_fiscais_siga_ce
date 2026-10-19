@echo off
chcp 65001 >nul
title Instalador — Giro Empresarial
echo ========================================================
echo               GIRO EMPRESARIAL
echo      Instalação e Configuração Automática SEFAZ-CE
echo ========================================================
echo.

echo [1/3] Verificando versão do Python...
python --version
if errorlevel 1 (
    echo [ERRO] Python não foi encontrado no PATH. Instale o Python 3.11+ e tente novamente.
    pause
    exit /b 1
)

echo.
echo [2/3] Instalando dependências e componentes do sistema...
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [AVISO] Tentando instalar pacotes diretamente...
    pip install -r requirements.txt
)

echo.
echo [3/3] Executando configuração do ambiente, banco de dados e atalhos...
python src/bootstrap.py

echo.
echo ========================================================
echo   Configuração concluída com sucesso!
echo   O atalho 'Giro Empresarial' foi criado na Área de
echo   Trabalho e no Menu Iniciar (Pesquisar do Windows).
echo   Execute 'run.bat' ou dê clique duplo no atalho.
echo ========================================================
pause


@echo off
chcp 65001 >nul
title Giro Empresarial
echo ========================================================
echo               GIRO EMPRESARIAL
echo      Sistema de Gestao Fiscal e Automacao SEFAZ-CE
echo ========================================================
echo.
echo Verificando ambiente e iniciando servidor...
echo Abrindo navegador automaticamente em http://127.0.0.1:8000 ...
echo Para encerrar o sistema, feche esta janela ou pressione CTRL+C.
echo.
python main.py
if errorlevel 1 (
    echo.
    echo [AVISO] O processo foi finalizado.
    pause
)

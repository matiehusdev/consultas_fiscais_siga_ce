@echo off
chcp 65001 >nul
echo ========================================================
echo        INICIANDO SIGA FISCAL — SEFAZ-CE
echo ========================================================
echo.
echo Abrindo servidor em http://127.0.0.1:8000 ...
echo Pressione CTRL+C para encerrar.
echo.
python main.py
pause

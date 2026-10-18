import sys
import time
import threading
import webbrowser
import uvicorn
from src.config import settings
from src.database.connection import init_db
from src.utils.logger import logger
from src.bootstrap import run_first_time_setup

def _open_browser_when_ready():
    """Abre o navegador padrão automaticamente assim que o servidor subir."""
    time.sleep(1.2)
    url = f"http://{settings.app_host}:{settings.app_port}"
    logger.info(f"Abrindo navegador padrão automaticamente em: {url}")
    try:
        webbrowser.open(url)
    except Exception as e:
        logger.debug(f"Aviso ao abrir navegador: {e}")

def main():
    # 1. Garante instalação de dependências, navegador Chromium e atalhos na primeira abertura
    run_first_time_setup()

    logger.info("Iniciando Giro Empresarial...")
    logger.info(f"Ambiente: {settings.app_env}")
    logger.info(f"Banco de Dados: {settings.database_path}")
    logger.info(f"Diretório de Consultas: {settings.consultas_dir}")
    
    # Garante inicialização das tabelas
    init_db()
    
    # Dispara abertura automática do navegador em background
    threading.Thread(target=_open_browser_when_ready, daemon=True).start()

    is_frozen = getattr(sys, "frozen", False)
    if is_frozen or not settings.debug:
        from src.web.app import app as fastapi_app
        uvicorn.run(
            fastapi_app,
            host=settings.app_host,
            port=settings.app_port
        )
    else:
        uvicorn.run(
            "src.web.app:app",
            host=settings.app_host,
            port=settings.app_port,
            reload=True
        )

if __name__ == "__main__":
    main()

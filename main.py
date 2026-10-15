import uvicorn
from src.config import settings
from src.database.connection import init_db
from src.utils.logger import logger

def main():
    logger.info("Iniciando Sistema SIGA Fiscal...")
    logger.info(f"Ambiente: {settings.app_env}")
    logger.info(f"Banco de Dados: {settings.database_path}")
    logger.info(f"Diretório de Consultas: {settings.consultas_dir}")
    
    # Garante inicialização das tabelas
    init_db()
    
    logger.info(f"Servidor Web acessível em: http://{settings.app_host}:{settings.app_port}")
    uvicorn.run(
        "src.web.app:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug
    )

if __name__ == "__main__":
    main()

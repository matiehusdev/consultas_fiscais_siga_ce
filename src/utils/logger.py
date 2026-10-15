import logging
import sys
from datetime import datetime
from src.utils.sanitizers import sanitize_text

class SanitizedFormatter(logging.Formatter):
    """Formatador de logs com mascaramento obrigatório de dados sensíveis."""
    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        return sanitize_text(original)

def get_logger(name: str = "siga_fiscal") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = SanitizedFormatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False
    return logger

logger = get_logger()

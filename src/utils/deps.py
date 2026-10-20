import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional
from src.utils.logger import logger

def get_python_exe() -> str:
    """Retorna o executável real do Python no sistema."""
    if not getattr(sys, "frozen", False):
        return sys.executable
    py = shutil.which("python") or shutil.which("py")
    if py:
        return py
    userprofile = os.environ.get("USERPROFILE", "")
    if userprofile:
        for p in Path(userprofile).glob("AppData/Local/Programs/Python/Python*/python.exe"):
            if p.exists():
                return str(p)
    return "python"

def ensure_package(module_name: str, pip_spec: Optional[str] = None) -> bool:
    """Verifica e instala automaticamente um pacote ausente sem intervenção do usuário."""
    try:
        __import__(module_name)
        return True
    except ImportError:
        pass

    target = pip_spec or module_name
    logger.info(f"Módulo '{module_name}' ausente. Instalando automaticamente '{target}' em segundo plano...")
    py_exe = get_python_exe()
    try:
        res = subprocess.run(
            [py_exe, "-m", "pip", "install", target, "--quiet"],
            capture_output=True,
            text=True,
            timeout=120
        )
        if res.returncode != 0:
            res_retry = subprocess.run(
                [py_exe, "-m", "pip", "install", target],
                capture_output=True,
                text=True,
                timeout=120
            )
            if res_retry.returncode != 0:
                logger.error(f"Falha ao instalar automaticamente '{target}': {res_retry.stderr}")
                return False
        __import__(module_name)
        logger.info(f"Módulo '{module_name}' instalado e carregado com sucesso!")
        return True
    except Exception as e:
        logger.error(f"Erro inesperado ao auto-instalar '{target}': {e}")
        return False

def ensure_cryptography() -> bool:
    """Garante disponibilidade da biblioteca cryptography."""
    return ensure_package("cryptography", "cryptography>=42.0.0")

import os
import sys
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional

import shutil

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

def log_msg(msg: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [BOOTSTRAP] {msg}")

def get_python_executable() -> str:
    """Retorna o executável real do Python no sistema."""
    if not getattr(sys, "frozen", False):
        return sys.executable
    py = shutil.which("python") or shutil.which("py")
    if py:
        return py
    userprofile = os.environ.get("USERPROFILE", "")
    for p in Path(userprofile).glob("AppData/Local/Programs/Python/Python*/python.exe"):
        if p.exists():
            return str(p)
    return "python"

def is_chromium_installed() -> bool:
    """Verifica se o navegador Chromium do Playwright está presente no sistema."""
    # 1. Verificação direta no diretório padrão do Playwright no Windows
    localappdata = os.environ.get("LOCALAPPDATA", "")
    if localappdata:
        pw_dir = Path(localappdata) / "ms-playwright"
        if pw_dir.exists():
            for p in pw_dir.glob("chromium-*/chrome-win*/chrome.exe"):
                if p.exists():
                    return True

    # 2. Verificação via API do Playwright
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            exec_path = Path(p.chromium.executable_path)
            if exec_path.exists():
                return True
    except Exception:
        pass

    return False

def check_and_install_packages(on_progress: Optional[Callable[[str], None]] = None) -> bool:
    """Verifica e instala dependências Python do requirements.txt se necessário."""
    try:
        import fastapi
        import uvicorn
        import jinja2
        import playwright
        import openpyxl
        import reportlab
        import pandas
        import sqlalchemy
        import cryptography
        import multipart
        return True
    except ImportError as e:
        log_msg(f"Dependência ausente detectada ({e}). Instalando pacotes necessários...")
        if on_progress:
            on_progress("Instalando dependências do sistema...")
        req_file = BASE_DIR / "requirements.txt"
        success = True
        if req_file.exists():
            cmd = [get_python_executable(), "-m", "pip", "install", "-r", str(req_file), "--quiet"]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                # Tenta novamente sem --quiet para registrar detalhes
                cmd_retry = [get_python_executable(), "-m", "pip", "install", "-r", str(req_file)]
                res_retry = subprocess.run(cmd_retry, capture_output=True, text=True)
                success = (res_retry.returncode == 0)

        # Garante explicitamente a presença da biblioteca cryptography
        try:
            import cryptography
        except ImportError:
            log_msg("Instalando biblioteca cryptography diretamente...")
            cmd_crypto = [get_python_executable(), "-m", "pip", "install", "cryptography>=42.0.0"]
            res_crypto = subprocess.run(cmd_crypto, capture_output=True, text=True)
            if res_crypto.returncode != 0:
                success = False

        return success

def check_and_install_playwright(on_progress: Optional[Callable[[str], None]] = None) -> bool:
    """Verifica e instala os binários do Chromium do Playwright se necessário."""
    if is_chromium_installed():
        return True

    log_msg("Navegador Chromium não encontrado. Instalando binários do Playwright...")
    if on_progress:
        on_progress("Instalando navegador Chromium para automação da SEFAZ...")
    cmd = [get_python_executable(), "-m", "playwright", "install", "chromium"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode == 0

def create_windows_shortcuts(target_path: Optional[Path] = None, icon_path: Optional[Path] = None) -> bool:
    """
    Cria atalhos do Windows no Menu Iniciar (para indexação no Pesquisar do SO)
    e na Área de Trabalho (para inicialização rápida via clique duplo).
    """
    try:
        appdata = os.environ.get("APPDATA")
        userprofile = os.environ.get("USERPROFILE")
        if not appdata or not userprofile:
            return False

        start_menu_dir = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        desktop_dir = Path(userprofile) / "Desktop"
        start_menu_dir.mkdir(parents=True, exist_ok=True)
        desktop_dir.mkdir(parents=True, exist_ok=True)

        if not target_path:
            exe_target = BASE_DIR / "Giro Empresarial.exe"
            bat_target = BASE_DIR / "run.bat"
            target_path = exe_target if exe_target.exists() else bat_target

        if not icon_path:
            icon_simbolo = BASE_DIR / "logo_simbolo.ico"
            icon_candidate = BASE_DIR / "giro_empresarial.ico"
            icon_fallback = BASE_DIR / "src" / "web" / "static" / "img" / "logo_simbolo.ico"
            if icon_simbolo.exists():
                icon_path = icon_simbolo
            elif icon_candidate.exists():
                icon_path = icon_candidate
            else:
                icon_path = icon_fallback

        start_lnk = start_menu_dir / "Giro Empresarial.lnk"
        desktop_lnk = desktop_dir / "Giro Empresarial.lnk"

        ps_script = f"""$w = New-Object -ComObject WScript.Shell
$s1 = $w.CreateShortcut("{start_lnk}")
$s1.TargetPath = "{target_path}"
$s1.WorkingDirectory = "{BASE_DIR}"
$s1.Description = "Giro Empresarial - Gestao Fiscal e Automacao SEFAZ-CE"
if ("{icon_path}" -ne "" -and (Test-Path "{icon_path}")) {{ $s1.IconLocation = "{icon_path},0" }}
$s1.Save()

$s2 = $w.CreateShortcut("{desktop_lnk}")
$s2.TargetPath = "{target_path}"
$s2.WorkingDirectory = "{BASE_DIR}"
$s2.Description = "Giro Empresarial - Gestao Fiscal e Automacao SEFAZ-CE"
if ("{icon_path}" -ne "" -and (Test-Path "{icon_path}")) {{ $s2.IconLocation = "{icon_path},0" }}
$s2.Save()
"""

        temp_ps = BASE_DIR / "data" / "_create_shortcuts.ps1"
        temp_ps.write_text(ps_script, encoding="utf-8")
        res = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(temp_ps)],
            capture_output=True,
            text=True
        )
        try:
            temp_ps.unlink()
        except Exception:
            pass

        # Força atualização do cache de ícones do Windows Explorer
        try:
            import ctypes
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        except Exception:
            pass

        sucesso = start_lnk.exists() and desktop_lnk.exists()
        if sucesso:
            log_msg(f"Atalhos do Windows criados com sucesso: Menu Iniciar ({start_lnk}) e Desktop ({desktop_lnk}).")
        return sucesso
    except Exception as e:
        log_msg(f"Aviso ao criar atalhos do Windows: {e}")
        return False

def check_and_setup_environment(on_progress: Optional[Callable[[str], None]] = None) -> bool:
    """Garante existência de .env, pastas de dados e tabelas do banco de dados SQLite."""
    try:
        if on_progress:
            on_progress("Inicializando banco de dados e pastas...")

        # .env
        env_file = BASE_DIR / ".env"
        env_example = BASE_DIR / ".env.example"
        if not env_file.exists() and env_example.exists():
            env_file.write_bytes(env_example.read_bytes())
            log_msg("Arquivo .env criado a partir de .env.example.")

        # Diretórios e banco
        from src.config import settings
        from src.database.connection import init_db
        settings.ensure_directories()
        init_db()
        log_msg("Estrutura de diretórios e tabelas do banco de dados verificadas.")
        return True
    except Exception as e:
        log_msg(f"Erro ao inicializar ambiente: {e}")
        return False

def run_first_time_setup(on_progress: Optional[Callable[[str], None]] = None) -> bool:
    """
    Executa a rotina completa de instalação e configuração na primeira abertura.
    Garante que pacotes essenciais e Chromium estejam presentes mesmo se o diretório
    for copiado entre máquinas com o arquivo .bootstrap_completed já existente.
    """
    # 1. Verificação rápida de pacotes essenciais (execução instantânea se já instalados)
    check_and_install_packages(on_progress)
    check_and_setup_environment(on_progress)

    flag_file = BASE_DIR / "data" / ".bootstrap_completed"
    if flag_file.exists() and is_chromium_installed():
        return True

    log_msg("Iniciando rotina de configuração inicial (Auto-Setup)...")
    if on_progress:
        on_progress("Iniciando configuração inicial do Giro Empresarial...")

    check_and_install_playwright(on_progress)

    if on_progress:
        on_progress("Criando atalho de inicialização no Menu Iniciar e Área de Trabalho...")
    create_windows_shortcuts()

    try:
        flag_file.parent.mkdir(parents=True, exist_ok=True)
        flag_file.write_text(f"installed_at={time.time()}\nversion=1.0.0\n", encoding="utf-8")
        log_msg("Configuração concluída com êxito! Marcador salvo em data/.bootstrap_completed.")
    except Exception:
        pass

    if on_progress:
        on_progress("✓ Configuração concluída com sucesso! Iniciando aplicação...")
        time.sleep(1.0)

    return True

if __name__ == "__main__":
    run_first_time_setup()

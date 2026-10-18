import os
import sys
import subprocess
from pathlib import Path

# Localização do projeto
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent

os.chdir(str(APP_DIR))

def find_python() -> str:
    # 1. Ambiente virtual se existir
    venv_py = APP_DIR / ".venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        return str(venv_py)
    
    # 2. Python no PATH do sistema
    import shutil
    py = shutil.which("python")
    if py:
        return py
    
    # 3. Caminhos de instalação padrão do Python no Windows
    userprofile = os.environ.get("USERPROFILE", "")
    for p in Path(userprofile).glob("AppData/Local/Programs/Python/Python*/python.exe"):
        if p.exists():
            return str(p)
            
    program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
    for p in Path(program_files).glob("Python*/python.exe"):
        if p.exists():
            return str(p)

    return "python"

if __name__ == "__main__":
    os.system("title Giro Empresarial")
    py_bin = find_python()
    main_script = APP_DIR / "main.py"
    
    cmd = [py_bin, str(main_script)] + sys.argv[1:]
    sys.exit(subprocess.call(cmd))

import os
import sys
import shutil
import subprocess
from pathlib import Path

# Localização do executável ou script
if getattr(sys, "frozen", False):
    EXE_DIR = Path(sys.executable).resolve().parent
else:
    EXE_DIR = Path(__file__).resolve().parent

# Se main.py estiver na pasta do executável, usa ela.
# Se não estiver (ex: executável solto no Downloads), tenta a pasta padrão em LocalAppData.
if (EXE_DIR / "main.py").exists():
    APP_DIR = EXE_DIR
else:
    local_appdata = os.environ.get("LOCALAPPDATA")
    installed_dir = Path(local_appdata) / "Giro Empresarial" if local_appdata else None
    if installed_dir and (installed_dir / "main.py").exists():
        APP_DIR = installed_dir
    else:
        APP_DIR = EXE_DIR

os.chdir(str(APP_DIR))

def find_python() -> str:
    # 1. Ambiente virtual se existir
    venv_py = APP_DIR / ".venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        return str(venv_py)
    
    # 2. Python no PATH do sistema
    py = shutil.which("python") or shutil.which("py")
    if py:
        return py
    
    # 3. Caminhos de instalação padrão do Python no Windows
    userprofile = os.environ.get("USERPROFILE", "")
    if userprofile:
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
    main_script = APP_DIR / "main.py"
    
    if not main_script.exists():
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Giro Empresarial",
                f"Arquivos do sistema não encontrados em:\n{APP_DIR}\n\n"
                "Por favor, execute o Instalador_Giro_Empresarial.exe para configurar o sistema."
            )
            root.destroy()
        except Exception:
            print(f"[ERRO] Arquivos não encontrados em {APP_DIR}. Execute o Instalador_Giro_Empresarial.exe.")
        sys.exit(1)

    py_bin = find_python()
    cmd = [py_bin, str(main_script)] + sys.argv[1:]
    sys.exit(subprocess.call(cmd))

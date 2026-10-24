import os
import sys
import time
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Define diretório do payload (de onde os arquivos serão copiados)
if getattr(sys, "frozen", False):
    PAYLOAD_DIR = Path(sys._MEIPASS).resolve()
else:
    PAYLOAD_DIR = Path(__file__).resolve().parent

# Define diretório de destino padrão da instalação
def get_target_dir() -> Path:
    # Se chamado com argumento --target, respeita o caminho fornecido
    for i, arg in enumerate(sys.argv):
        if arg == "--target" and i + 1 < len(sys.argv):
            return Path(sys.argv[i + 1]).resolve()
        if arg == "--here":
            return Path.cwd().resolve()

    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / "Giro Empresarial"
    user_profile = os.environ.get("USERPROFILE", "C:\\")
    return Path(user_profile) / "Giro Empresarial"

TARGET_DIR = get_target_dir()

# Garante que módulos em src do payload ou destino possam ser importados
if str(PAYLOAD_DIR) not in sys.path:
    sys.path.insert(0, str(PAYLOAD_DIR))

from src.bootstrap import (
    set_base_dir,
    get_python_executable,
    is_python_installed,
    check_and_install_packages,
    check_and_install_playwright,
    check_and_setup_environment,
    create_windows_shortcuts,
    is_chromium_installed
)

def deploy_payload_files(on_progress: Optional[Callable[[str], None]] = None) -> bool:
    """Extrai e copia todos os arquivos essenciais do payload para a pasta de instalação."""
    if PAYLOAD_DIR.resolve() == TARGET_DIR.resolve():
        if on_progress:
            on_progress("Arquivos já se encontram no diretório de destino.")
        return True

    if on_progress:
        on_progress("Preparando pasta de instalação no sistema...")
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Copia recursiva do src (código fonte, telas web, imagens, templates)
    src_payload = PAYLOAD_DIR / "src"
    src_target = TARGET_DIR / "src"
    if src_payload.exists():
        if on_progress:
            on_progress("Copiando componentes da aplicação (src)...")
        shutil.copytree(
            src_payload,
            src_target,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")
        )

    # 2. Copia de arquivos raiz fundamentais
    root_files = [
        "main.py",
        "launcher.py",
        "requirements.txt",
        ".env.example",
        "giro_empresarial.ico",
        "logo_simbolo.ico",
        "run.bat",
        "install.bat",
        "Giro Empresarial.exe"
    ]

    for fname in root_files:
        src_f = PAYLOAD_DIR / fname
        if src_f.exists():
            dst_f = TARGET_DIR / fname
            try:
                shutil.copy2(src_f, dst_f)
            except Exception:
                pass

    # 3. Criação de .env inicial se não existir
    env_target = TARGET_DIR / ".env"
    env_example = TARGET_DIR / ".env.example"
    if not env_target.exists() and env_example.exists():
        try:
            shutil.copy2(env_example, env_target)
        except Exception:
            pass

    # 4. Estrutura de pastas locais de dados (preservando dados se já existirem)
    for sub in ["certificados", "consultas", "db", "empresas"]:
        d = TARGET_DIR / "data" / sub
        d.mkdir(parents=True, exist_ok=True)
        keep = d / ".gitkeep"
        if not keep.exists():
            try:
                keep.touch()
            except Exception:
                pass

    return True

def run_full_installation(on_progress: Optional[Callable[[str], None]] = None) -> bool:
    """Executa a rotina completa de instalação e configuração no TARGET_DIR."""
    # Passo 1: Verificar se o Python está presente no sistema
    if on_progress:
        on_progress("1/5 Verificando instalação do Python no Windows...")
    if not is_python_installed():
        raise RuntimeError(
            "Python 3.11 ou superior não foi encontrado no seu computador.\n\n"
            "Por favor, instale o Python através do site oficial (https://python.org)\n"
            "e certifique-se de marcar a opção 'Add python.exe to PATH' durante a instalação."
        )

    # Passo 2: Copiar arquivos da aplicação
    if on_progress:
        on_progress("2/5 Instalando arquivos do Giro Empresarial...")
    deploy_payload_files(on_progress)

    # Seta o base_dir do bootstrap para o destino definitivo
    set_base_dir(TARGET_DIR)

    # Passo 3: Dependências Python
    if on_progress:
        on_progress("3/5 Instalando e verificando pacotes necessários...")
    check_and_install_packages(on_progress, base_dir=TARGET_DIR)

    # Passo 4: Playwright Chromium
    if on_progress:
        on_progress("4/5 Configurando navegador Chromium para automação SEFAZ-CE...")
    check_and_install_playwright(on_progress)

    # Passo 5: Banco de Dados SQLite, Diretórios e Atalhos
    if on_progress:
        on_progress("5/5 Configurando banco de dados e criando atalhos no Windows...")
    check_and_setup_environment(on_progress, base_dir=TARGET_DIR)
    create_windows_shortcuts(base_dir=TARGET_DIR)

    # Cria flag de instalação concluída
    flag = TARGET_DIR / "data" / ".bootstrap_completed"
    try:
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text(f"installed_at={time.time()}\nversion=1.0.0\n", encoding="utf-8")
    except Exception:
        pass

    if on_progress:
        on_progress("[OK] Instalacao concluida com sucesso! Giro Empresarial pronto.")

    return True

def launch_installed_app():
    """Inicia o Giro Empresarial a partir do diretório instalado."""
    exe_target = TARGET_DIR / "Giro Empresarial.exe"
    bat_target = TARGET_DIR / "run.bat"
    main_target = TARGET_DIR / "main.py"

    if exe_target.exists():
        os.startfile(str(exe_target))
    elif bat_target.exists():
        os.startfile(str(bat_target))
    elif main_target.exists():
        py = get_python_executable()
        subprocess.Popen([py, str(main_target)], cwd=str(TARGET_DIR))

def run_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox

    root = tk.Tk()
    root.title("Instalador — Giro Empresarial")
    root.geometry("520x420")
    root.resizable(False, False)
    root.configure(bg="#023047")

    # Ícone da janela
    ico_path = PAYLOAD_DIR / "giro_empresarial.ico"
    if not ico_path.exists():
        ico_path = TARGET_DIR / "giro_empresarial.ico"
    if ico_path.exists():
        try:
            root.iconbitmap(str(ico_path))
        except Exception:
            pass

    # Centraliza janela
    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (w // 2)
    y = (root.winfo_screenheight() // 2) - (h // 2)
    root.geometry(f"+{x}+{y}")

    # Cabeçalho
    header_frame = tk.Frame(root, bg="#023047")
    header_frame.pack(pady=15, fill="x")

    lbl_title = tk.Label(
        header_frame,
        text="GIRO EMPRESARIAL",
        font=("Segoe UI", 18, "bold"),
        fg="#ffb703",
        bg="#023047"
    )
    lbl_title.pack()

    lbl_sub = tk.Label(
        header_frame,
        text="Instalação e Configuração Automática SEFAZ-CE",
        font=("Segoe UI", 10),
        fg="#8ecae6",
        bg="#023047"
    )
    lbl_sub.pack(pady=3)

    # Card central
    card = tk.Frame(root, bg="#ffffff", bd=0, relief="flat")
    card.pack(padx=22, pady=5, fill="both", expand=True)

    is_already_installed = (TARGET_DIR / "data" / ".bootstrap_completed").exists()

    desc_text = (
        "Este instalador configura o Giro Empresarial de forma 100% autônoma:\n"
        "• Instala componentes, dependências e automação SEFAZ-CE\n"
        "• Cria atalho oficial na Área de Trabalho com a logo da marca\n"
        "• Cria atalho no Menu Iniciar (pesquisável no Windows)\n"
        f"• Local: {TARGET_DIR}"
    )

    lbl_desc = tk.Label(
        card,
        text=desc_text,
        font=("Segoe UI", 8),
        fg="#334155",
        bg="#ffffff",
        justify="left"
    )
    lbl_desc.pack(padx=14, pady=10, anchor="w")

    status_initial = (
        "O Giro Empresarial já se encontra configurado neste computador."
        if is_already_installed
        else "Pronto para iniciar a instalação automática."
    )

    lbl_status = tk.Label(
        card,
        text=status_initial,
        font=("Segoe UI", 9, "bold" if is_already_installed else "italic"),
        fg="#059669" if is_already_installed else "#0284c7",
        bg="#ffffff",
        wraplength=460,
        justify="left"
    )
    lbl_status.pack(padx=14, pady=5, anchor="w")

    progress = ttk.Progressbar(card, mode="indeterminate", length=460)
    progress.pack(padx=14, pady=8)

    # Botões de ação
    btn_frame = tk.Frame(root, bg="#023047")
    btn_frame.pack(pady=12, fill="x", padx=22)

    def do_install():
        btn_action.config(state="disabled")
        btn_cancel.config(state="disabled")
        progress.start(10)

        def worker():
            def update_status(text):
                root.after(0, lambda: lbl_status.config(text=text, fg="#0284c7"))

            try:
                run_full_installation(update_status)

                def on_done():
                    progress.stop()
                    lbl_status.config(
                        text="Instalação concluída com sucesso! Atalhos criados.",
                        fg="#059669"
                    )
                    btn_action.config(
                        text="Iniciar Giro Empresarial",
                        state="normal",
                        bg="#22c55e",
                        command=on_launch
                    )
                    btn_cancel.config(state="normal", text="Fechar")

                root.after(0, on_done)

            except Exception as e:
                def on_err():
                    progress.stop()
                    lbl_status.config(text=f"Aviso/Erro: {e}", fg="#dc2626")
                    btn_action.config(state="normal", text="Tentar Novamente", bg="#fb8500")
                    btn_cancel.config(state="normal")
                    messagebox.showerror("Instalação do Giro Empresarial", str(e))
                root.after(0, on_err)

        threading.Thread(target=worker, daemon=True).start()

    def on_launch():
        launch_installed_app()
        root.destroy()

    if is_already_installed:
        action_btn_text = "Iniciar Giro Empresarial"
        action_cmd = on_launch
        action_bg = "#22c55e"
    else:
        action_btn_text = "Instalar e Configurar Agora"
        action_cmd = do_install
        action_bg = "#fb8500"

    btn_action = tk.Button(
        btn_frame,
        text=action_btn_text,
        font=("Segoe UI", 10, "bold"),
        bg=action_bg,
        fg="#ffffff",
        activebackground="#ffb703",
        activeforeground="#023047",
        relief="flat",
        padx=14,
        pady=7,
        cursor="hand2",
        command=action_cmd
    )
    btn_action.pack(side="right")

    if is_already_installed:
        btn_reinstall = tk.Button(
            btn_frame,
            text="Reinstalar / Atualizar",
            font=("Segoe UI", 9),
            bg="#0284c7",
            fg="#ffffff",
            relief="flat",
            padx=10,
            pady=7,
            cursor="hand2",
            command=do_install
        )
        btn_reinstall.pack(side="right", padx=8)

    btn_cancel = tk.Button(
        btn_frame,
        text="Sair",
        font=("Segoe UI", 9),
        bg="#023047",
        fg="#94a3b8",
        relief="flat",
        cursor="hand2",
        command=root.destroy
    )
    btn_cancel.pack(side="left")

    root.mainloop()

def run_cli():
    print("========================================================")
    print("      INSTALADOR DO GIRO EMPRESARIAL (SEFAZ-CE)")
    print("========================================================")
    print(f"Diretório de Destino: {TARGET_DIR}")
    print()
    try:
        run_full_installation(lambda msg: print(f"-> {msg}"))
        print()
        print("========================================================")
        print("  [OK] Instalacao concluida com sucesso!")
        print("  O atalho 'Giro Empresarial' ja esta disponivel")
        print("  na Pesquisa do Windows e na sua Area de Trabalho.")
        print("========================================================")
        if "--launch" in sys.argv:
            launch_installed_app()
    except Exception as e:
        print(f"\n[ERRO NA INSTALAÇÃO]: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if "--cli" in sys.argv or "--silent" in sys.argv:
        run_cli()
    else:
        try:
            run_gui()
        except Exception as e:
            print(f"Interface gráfica indisponível ({e}). Executando em modo texto:")
            run_cli()

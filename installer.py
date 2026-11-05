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

try:
    from src.config import APP_VERSION
except Exception:
    APP_VERSION = "1.3.1"

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

def get_installed_version() -> Optional[str]:
    """Detecta a versão atualmente instalada em TARGET_DIR."""
    flag = TARGET_DIR / "data" / ".bootstrap_completed"
    if flag.exists():
        try:
            for line in flag.read_text(encoding="utf-8").splitlines():
                if line.startswith("version="):
                    v = line.split("=", 1)[1].strip()
                    if v:
                        return v
        except Exception:
            pass
    init_f = TARGET_DIR / "src" / "__init__.py"
    if init_f.exists():
        try:
            for line in init_f.read_text(encoding="utf-8").splitlines():
                if "__version__" in line and "=" in line:
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
    if (TARGET_DIR / "data").exists() or (TARGET_DIR / "src").exists() or (TARGET_DIR / "Giro Empresarial.exe").exists():
        return "1.0.0"
    return None

def is_app_running() -> bool:
    """Verifica se há processos do Giro Empresarial em execução."""
    if sys.platform != "win32":
        return False
    try:
        # 1. Verifica processo do executável
        cmd = ["tasklist", "/FI", "IMAGENAME eq Giro Empresarial.exe", "/FO", "CSV", "/NH"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
        if "Giro Empresarial.exe" in res.stdout:
            return True

        # 2. Verifica se a porta 8000 está ocupada por processo local
        cmd_port = [
            "powershell", "-NoProfile", "-Command",
            "$conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue; if ($conn) { $conn.OwningProcess }"
        ]
        res_port = subprocess.run(cmd_port, capture_output=True, text=True, timeout=4)
        if res_port.stdout.strip():
            return True
    except Exception:
        pass
    return False

def close_running_app() -> bool:
    """Encerra processos do Giro Empresarial para permitir substituição segura de arquivos."""
    try:
        subprocess.run(["taskkill", "/F", "/IM", "Giro Empresarial.exe", "/T"], capture_output=True)
        cmd_kill = [
            "powershell", "-NoProfile", "-Command",
            "$p = (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue).OwningProcess; if ($p) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }"
        ]
        subprocess.run(cmd_kill, capture_output=True, timeout=5)
        time.sleep(1.2)
        return True
    except Exception:
        return False

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
        on_progress("2/5 Atualizando arquivos e módulos do Giro Empresarial...")
    deploy_payload_files(on_progress)

    # Seta o base_dir do bootstrap para o destino definitivo
    set_base_dir(TARGET_DIR)

    # Passo 3: Dependências Python
    if on_progress:
        on_progress("3/5 Verificando pacotes e bibliotecas necessárias...")
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

    # Cria flag de instalação concluída atualizada
    flag = TARGET_DIR / "data" / ".bootstrap_completed"
    try:
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text(f"installed_at={time.time()}\nversion={APP_VERSION}\n", encoding="utf-8")
    except Exception:
        pass

    if on_progress:
        on_progress(f"[OK] Concluído com sucesso! Versão v{APP_VERSION} pronta.")

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
    root.title(f"Giro Empresarial — v{APP_VERSION}")
    root.geometry("540x440")
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

    installed_version = get_installed_version()
    is_update = installed_version is not None

    sub_title = (
        f"Atualizador Oficial SEFAZ-CE — Versão v{APP_VERSION}"
        if is_update
        else f"Instalação e Configuração Automática SEFAZ-CE — Versão v{APP_VERSION}"
    )

    lbl_sub = tk.Label(
        header_frame,
        text=sub_title,
        font=("Segoe UI", 10),
        fg="#8ecae6",
        bg="#023047"
    )
    lbl_sub.pack(pady=3)

    # Card central
    card = tk.Frame(root, bg="#ffffff", bd=0, relief="flat")
    card.pack(padx=22, pady=5, fill="both", expand=True)

    if is_update:
        desc_text = (
            f"Atualização do Giro Empresarial para a Versão v{APP_VERSION}:\n\n"
            f"• Versão anterior detectada: v{installed_version}  ➜  Nova versão: v{APP_VERSION}\n"
            "• Suas empresas cadastradas e histórico serão 100% preservados\n"
            "• Certificados digitais e relatórios locais permanecem intactos\n"
            "• Motor fiscal atualizado com integridade SHA-256 e sem corrida de downloads\n"
            f"• Local: {TARGET_DIR}"
        )
        status_initial = f"Pronto para atualizar para a versão v{APP_VERSION}."
        status_color = "#0064e0"
        action_btn_text = f"Atualizar para a Versão {APP_VERSION}"
        action_bg = "#0064e0"
    else:
        desc_text = (
            f"Instalação do Giro Empresarial versão v{APP_VERSION}:\n\n"
            "• Configura componentes, dependências e automação SEFAZ-CE\n"
            "• Cria atalho oficial na Área de Trabalho com a logo da marca\n"
            "• Cria atalho no Menu Iniciar (pesquisável no Windows)\n"
            f"• Local: {TARGET_DIR}"
        )
        status_initial = "Pronto para iniciar a instalação automática."
        status_color = "#0284c7"
        action_btn_text = "Instalar e Configurar Agora"
        action_bg = "#fb8500"

    lbl_desc = tk.Label(
        card,
        text=desc_text,
        font=("Segoe UI", 8),
        fg="#334155",
        bg="#ffffff",
        justify="left"
    )
    lbl_desc.pack(padx=14, pady=10, anchor="w")

    lbl_status = tk.Label(
        card,
        text=status_initial,
        font=("Segoe UI", 9, "bold" if is_update else "italic"),
        fg=status_color,
        bg="#ffffff",
        wraplength=480,
        justify="left"
    )
    lbl_status.pack(padx=14, pady=5, anchor="w")

    progress = ttk.Progressbar(card, mode="indeterminate", length=480)
    progress.pack(padx=14, pady=8)

    # Botões de ação
    btn_frame = tk.Frame(root, bg="#023047")
    btn_frame.pack(pady=12, fill="x", padx=22)

    def on_launch():
        launch_installed_app()
        root.destroy()

    def do_install():
        # Verifica se há processos do Giro Empresarial em execução
        if is_app_running():
            msg = (
                "O Giro Empresarial está em execução neste computador.\n\n"
                "Para aplicar as novas atualizações sem conflitos de arquivos, "
                "o sistema precisa ser encerrado temporariamente.\n\n"
                "Deseja encerrá-lo agora para continuar a atualização?"
            )
            resp = messagebox.askyesno(
                "Giro Empresarial em Execução",
                msg,
                icon="warning"
            )
            if resp:
                lbl_status.config(text="Fechando instâncias do sistema em execução...", fg="#0284c7")
                root.update_idletasks()
                close_running_app()
            else:
                lbl_status.config(
                    text="Atualização cancelada. Feche o Giro Empresarial antes de tentar novamente.",
                    fg="#dc2626"
                )
                return

        btn_action.config(state="disabled")
        btn_cancel.config(state="disabled")
        if btn_secondary:
            btn_secondary.config(state="disabled")
        progress.start(10)

        def worker():
            def update_status(text):
                root.after(0, lambda: lbl_status.config(text=text, fg="#0284c7"))

            try:
                run_full_installation(update_status)

                def on_done():
                    progress.stop()
                    if is_update:
                        lbl_status.config(
                            text=f"Sucesso ao atualizar para a versão v{APP_VERSION}!",
                            fg="#059669"
                        )
                        success_msg = (
                            "Sucesso ao atualizar!\n\n"
                            f"O Giro Empresarial foi atualizado com sucesso para a Versão {APP_VERSION}.\n\n"
                            "✓ Todas as suas empresas cadastradas foram mantidas.\n"
                            "✓ Seus certificados digitais e relatórios estão preservados.\n\n"
                            "Clique em OK para iniciar o sistema agora."
                        )
                        messagebox.showinfo("Atualização Concluída — Giro Empresarial", success_msg)
                    else:
                        lbl_status.config(
                            text=f"Instalação da versão v{APP_VERSION} concluída com sucesso!",
                            fg="#059669"
                        )
                        success_msg = (
                            "Instalação concluída com sucesso!\n\n"
                            f"O Giro Empresarial versão {APP_VERSION} foi instalado e configurado.\n\n"
                            "✓ Atalhos oficiais criados na Área de Trabalho e no Menu Iniciar.\n\n"
                            "Clique em OK para iniciar o sistema agora."
                        )
                        messagebox.showinfo("Instalação Concluída — Giro Empresarial", success_msg)

                    # Ação imediata: abre o sistema atualizado e fecha o instalador
                    launch_installed_app()
                    root.destroy()

                root.after(0, on_done)

            except Exception as e:
                def on_err():
                    progress.stop()
                    action_title = "Falha na Atualização — Giro Empresarial" if is_update else "Falha na Instalação — Giro Empresarial"
                    lbl_status.config(text=f"Aviso/Erro: {e}", fg="#dc2626")
                    btn_action.config(state="normal", text="Tentar Novamente", bg="#dc2626")
                    btn_cancel.config(state="normal")
                    if btn_secondary:
                        btn_secondary.config(state="normal")
                    err_msg = (
                        "Não foi possível concluir a operação no Giro Empresarial.\n\n"
                        f"Detalhes do erro:\n{str(e)}\n\n"
                        "Por favor, feche qualquer janela do programa que possa estar aberta e tente novamente."
                    )
                    messagebox.showerror(action_title, err_msg)
                root.after(0, on_err)

        threading.Thread(target=worker, daemon=True).start()

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
        command=do_install
    )
    btn_action.pack(side="right")

    btn_secondary = None
    if is_update:
        btn_secondary = tk.Button(
            btn_frame,
            text="Apenas Abrir Sistema",
            font=("Segoe UI", 9),
            bg="#334155",
            fg="#ffffff",
            relief="flat",
            padx=10,
            pady=7,
            cursor="hand2",
            command=on_launch
        )
        btn_secondary.pack(side="right", padx=8)

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
    installed_v = get_installed_version()
    is_upd = installed_v is not None
    mode_str = f"ATUALIZAÇÃO (v{installed_v} -> v{APP_VERSION})" if is_upd else f"INSTALAÇÃO (v{APP_VERSION})"

    print("========================================================")
    print(f"      GIRO EMPRESARIAL (SEFAZ-CE) — {mode_str}")
    print("========================================================")
    print(f"Diretório de Destino: {TARGET_DIR}")
    print()

    if is_app_running():
        print("-> Fechando instâncias do sistema em execução...")
        close_running_app()

    try:
        run_full_installation(lambda msg: print(f"-> {msg}"))
        print()
        print("========================================================")
        if is_upd:
            print(f"  [OK] Sucesso ao atualizar para a versao v{APP_VERSION}!")
            print("  Suas empresas e configuracoes foram 100% mantidas.")
        else:
            print(f"  [OK] Instalacao da versao v{APP_VERSION} concluida com sucesso!")
        print("  O atalho 'Giro Empresarial' esta disponivel no Windows.")
        print("========================================================")
        if "--launch" in sys.argv:
            launch_installed_app()
    except Exception as e:
        print(f"\n[ERRO]: {e}")
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

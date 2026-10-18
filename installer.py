import os
import sys
import time
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.bootstrap import (
    run_first_time_setup,
    create_windows_shortcuts,
    check_and_install_packages,
    check_and_install_playwright,
    check_and_setup_environment
)

def run_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox

    root = tk.Tk()
    root.title("Instalador — Giro Empresarial")
    root.geometry("500x380")
    root.resizable(False, False)
    root.configure(bg="#023047")

    # Ícone da janela
    ico_path = BASE_DIR / "giro_empresarial.ico"
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
    header_frame.pack(pady=20, fill="x")

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
        text="Instalação, Configuração Inicial e Atalho de Inicialização",
        font=("Segoe UI", 10),
        fg="#8ecae6",
        bg="#023047"
    )
    lbl_sub.pack(pady=4)

    # Card central
    card = tk.Frame(root, bg="#ffffff", bd=0, relief="flat")
    card.pack(padx=25, pady=5, fill="both", expand=True)

    lbl_desc = tk.Label(
        card,
        text="Este instalador prepara o ambiente completo do Giro Empresarial:\n"
             "• Cria o atalho no Menu Iniciar (visível na Pesquisa do Windows)\n"
             "• Cria o atalho na Área de Trabalho para inicialização via clique duplo\n"
             "• Instala componentes e navegador de automação SEFAZ-CE",
        font=("Segoe UI", 9),
        fg="#334155",
        bg="#ffffff",
        justify="left"
    )
    lbl_desc.pack(padx=15, pady=12, anchor="w")

    lbl_status = tk.Label(
        card,
        text="Pronto para iniciar a instalação.",
        font=("Segoe UI", 9, "italic"),
        fg="#0284c7",
        bg="#ffffff"
    )
    lbl_status.pack(padx=15, pady=5, anchor="w")

    progress = ttk.Progressbar(card, mode="indeterminate", length=440)
    progress.pack(padx=15, pady=10)

    # Botões
    btn_frame = tk.Frame(root, bg="#023047")
    btn_frame.pack(pady=15, fill="x", padx=25)

    def do_install():
        btn_action.config(state="disabled")
        progress.start(10)
        
        def worker():
            def update_status(text):
                root.after(0, lambda: lbl_status.config(text=text))

            try:
                update_status("1/4 Verificando dependências Python...")
                check_and_install_packages(update_status)
                
                update_status("2/4 Configurando navegador Chromium SEFAZ-CE...")
                check_and_install_playwright(update_status)
                
                update_status("3/4 Inicializando banco de dados e diretórios...")
                check_and_setup_environment(update_status)
                
                update_status("4/4 Criando atalhos no Menu Iniciar e Desktop...")
                create_windows_shortcuts()

                # Marca conclusão
                flag = BASE_DIR / "data" / ".bootstrap_completed"
                flag.parent.mkdir(parents=True, exist_ok=True)
                flag.write_text(f"installed_at={time.time()}\nversion=1.0.0\n", encoding="utf-8")

                def on_done():
                    progress.stop()
                    lbl_status.config(text="✓ Instalação concluída com sucesso! Atalhos criados.", fg="#059669")
                    btn_action.config(
                        text="Iniciar Giro Empresarial",
                        state="normal",
                        bg="#22c55e",
                        command=launch_app
                    )

                root.after(0, on_done)

            except Exception as e:
                def on_err():
                    progress.stop()
                    lbl_status.config(text=f"Erro na instalação: {e}", fg="#dc2626")
                    btn_action.config(state="normal", text="Tentar Novamente")
                root.after(0, on_err)

        threading.Thread(target=worker, daemon=True).start()

    def launch_app():
        root.destroy()
        # Inicia run.bat ou main.py
        bat_file = BASE_DIR / "run.bat"
        if bat_file.exists():
            os.startfile(str(bat_file))
        else:
            os.system(f'start python "{BASE_DIR / "main.py"}"')

    btn_action = tk.Button(
        btn_frame,
        text="Instalar e Configurar Agora",
        font=("Segoe UI", 11, "bold"),
        bg="#fb8500",
        fg="#ffffff",
        activebackground="#ffb703",
        activeforeground="#023047",
        relief="flat",
        padx=18,
        pady=8,
        cursor="hand2",
        command=do_install
    )
    btn_action.pack(side="right")

    btn_cancel = tk.Button(
        btn_frame,
        text="Sair",
        font=("Segoe UI", 10),
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
    print()
    run_first_time_setup(lambda msg: print(f"-> {msg}"))
    print()
    print("========================================================")
    print("  Instalação concluída com sucesso!")
    print("  O atalho 'Giro Empresarial' já está disponível")
    print("  na Pesquisa do Windows e na sua Área de Trabalho.")
    print("========================================================")

if __name__ == "__main__":
    if "--cli" in sys.argv:
        run_cli()
    else:
        try:
            run_gui()
        except Exception as e:
            print(f"Interface gráfica indisponível ({e}). Executando em modo texto:")
            run_cli()

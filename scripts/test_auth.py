import sys
import argparse
from pathlib import Path

# Adiciona raiz do projeto ao sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.siga.browser_session import BrowserSession
from src.siga.authentication import Authenticator, AuthStatusUpdate
from src.utils.logger import logger
from src.config import settings

def main():
    parser = argparse.ArgumentParser(description="Teste de abertura de navegador e autenticação com Certificado Digital A1 no SIGA.")
    parser.add_argument("--razao", default="Empresa de Teste", help="Razão social para exibição no prompt")
    parser.add_argument("--cnpj", default="00.000.000/0001-00", help="CNPJ da empresa")
    parser.add_argument("--timeout", type=int, default=settings.certificate_selection_timeout_seconds, help="Timeout em segundos")
    args = parser.parse_args()

    print("=" * 65)
    print("      TESTE PRÁTICO DA FASE 2: NAVEGADOR E CERTIFICADO A1")
    print("=" * 65)
    print(f"Empresa: {args.razao}")
    print(f"CNPJ: {args.cnpj}")
    print(f"URL Alvo: {settings.siga_base_url}")
    print(f"Timeout: {args.timeout}s")
    print("-" * 65)

    def on_status_change(update: AuthStatusUpdate):
        if update.acao_necessaria:
            print("\n" + "=" * 65)
            print("  [AÇÃO NECESSÁRIA]")
            print(f"  {update.mensagem}")
            print("=" * 65 + "\n")
        else:
            print(f"[{update.status}] {update.mensagem}")

    session = BrowserSession(headless=False)
    authenticator = Authenticator(timeout_seconds=args.timeout)

    try:
        session.start()
        print("✓ Navegador iniciado em modo visível com sucesso.")
        print("Acessando o portal do SIGA e aguardando autenticação...\n")

        sucesso = authenticator.authenticate(
            session=session,
            empresa_razao_social=args.razao,
            empresa_cnpj=args.cnpj,
            on_status_change=on_status_change
        )

        print("-" * 65)
        if sucesso:
            print(">>> SUCESSO: Autenticação no SIGA confirmada com êxito! <<<")
            print("A página atual está autenticada. A sessão isolada funcionou perfeitamente.")
        else:
            print(">>> FALHA: Autenticação não concluída dentro do tempo limite ou navegador fechado. <<<")
        print("-" * 65)

    except KeyboardInterrupt:
        print("\nTeste interrompido pelo usuário.")
    except Exception as e:
        print(f"\n[ERRO] Ocorreu uma exceção durante o teste: {e}")
    finally:
        print("Encerrando navegador e limpando sessão...")
        session.close()
        print("Sessão finalizada com sucesso.")

if __name__ == "__main__":
    main()

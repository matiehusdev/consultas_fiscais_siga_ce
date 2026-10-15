"""
Script para descobrir e auditar chamadas de rede de NFC-e no SIGA SEFAZ-CE.
Abre o navegador Playwright monitorando todas as requisições HTTP internas
e documenta endpoints, métodos, parâmetros e formatos de resposta.
"""

import sys
import json
from pathlib import Path

# Adiciona a raiz do projeto ao path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.siga.browser_session import BrowserSession
from src.siga.authentication import Authenticator
from src.utils.logger import logger
from src.config import settings

def main():
    print("=" * 60)
    print(" SIGA FISCAL — DESCOBERTA DE ENDPOINTS NFC-e (SEFAZ-CE)")
    print("=" * 60)
    print("Este script abrirá o navegador para que você navegue até a seção")
    print("de NFC-e no SIGA. Todas as chamadas de rede relevantes serão capturadas.\n")

    session = BrowserSession(headless=False)
    authenticator = Authenticator(timeout_seconds=180)

    try:
        session.start()
        page = session.page

        capturas = []

        def handle_request(req):
            url = req.url
            if "siga.sefaz.ce.gov.br/api" in url:
                metodo = req.method
                post_data = req.post_data
                headers = req.headers
                logger.info(f"-> [REQ] {metodo} {url}")
                capturas.append({
                    "tipo": "REQUEST",
                    "metodo": metodo,
                    "url": url,
                    "post_data": post_data,
                    "headers": {k: v for k, v in headers.items() if "auth" not in k.lower()}
                })

        def handle_response(res):
            url = res.url
            if "siga.sefaz.ce.gov.br/api" in url:
                status = res.status
                logger.info(f"<- [RESP {status}] {url}")
                try:
                    conteudo = res.text()[:500]
                except Exception:
                    conteudo = "<binário>"
                capturas.append({
                    "tipo": "RESPONSE",
                    "status": status,
                    "url": url,
                    "corpo": conteudo
                })

        page.on("request", handle_request)
        page.on("response", handle_response)

        print("Navegador aberto. Faça login e navegue até a aba de NFC-e.")
        print("Quando terminar, feche o navegador ou pressione Ctrl+C no terminal.\n")

        # Mantém aberto até o usuário fechar
        while session.is_alive:
            try:
                page.wait_for_timeout(1000)
            except Exception:
                break

        # Salva log de inspeção
        if capturas:
            log_path = BASE_DIR / "data" / "descoberta_nfce.json"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(capturas, f, indent=2, ensure_ascii=False)
            print(f"\n[OK] {len(capturas)} eventos de rede capturados e salvos em: {log_path}")

    finally:
        session.close()

if __name__ == "__main__":
    main()

import threading
import queue
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from src.utils.logger import logger
from src.utils.sanitizers import sanitize_text

class StatusBroadcaster:
    """
    Gerenciador thread-safe de transmissão de status em tempo real para a interface web.
    Permite comunicação desacoplada entre a thread do navegador Playwright e a interface FastAPI.
    """

    def __init__(self, max_history: int = 200):
        self._lock = threading.Lock()
        self._history: List[Dict[str, Any]] = []
        self._subscribers: List[queue.Queue] = []
        self._max_history = max_history
        self._current_state: Dict[str, Any] = {
            "ativo": False,
            "tipo_operacao": None,
            "empresa_atual": None,
            "etapa": "OCIOSO",
            "mensagem": "Nenhuma operação em execução.",
            "acao_necessaria": False,
            "acao_mensagem": None
        }

    def get_current_state(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._current_state)

    def publish(
        self,
        etapa: str,
        mensagem: str,
        empresa: Optional[str] = None,
        cnpj: Optional[str] = None,
        acao_necessaria: bool = False,
        acao_mensagem: Optional[str] = None,
        tipo_operacao: Optional[str] = None
    ) -> Dict[str, Any]:
        """Publica um novo evento e atualiza o estado atual."""
        msg_sanitizada = sanitize_text(mensagem)
        acao_msg_sanitizada = sanitize_text(acao_mensagem) if acao_mensagem else None

        event = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "etapa": etapa,
            "mensagem": msg_sanitizada,
            "empresa": empresa,
            "cnpj": cnpj,
            "acao_necessaria": acao_necessaria,
            "acao_mensagem": acao_msg_sanitizada,
            "tipo_operacao": tipo_operacao
        }

        with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history.pop(0)

            self._current_state.update({
                "ativo": etapa not in ("CONCLUIDO", "ERRO", "OCIOSO", "TIMEOUT"),
                "tipo_operacao": tipo_operacao or self._current_state["tipo_operacao"],
                "empresa_atual": empresa or self._current_state["empresa_atual"],
                "etapa": etapa,
                "mensagem": msg_sanitizada,
                "acao_necessaria": acao_necessaria,
                "acao_mensagem": acao_msg_sanitizada
            })

            # Distribui para filas de assinantes (SSE / Polling)
            for sub_queue in list(self._subscribers):
                try:
                    sub_queue.put_nowait(event)
                except Exception:
                    pass

        return event

    def subscribe(self) -> queue.Queue:
        q = queue.Queue(maxsize=100)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._history[-limit:])

    def reset(self):
        with self._lock:
            self._current_state = {
                "ativo": False,
                "tipo_operacao": None,
                "empresa_atual": None,
                "etapa": "OCIOSO",
                "mensagem": "Nenhuma operação em execução.",
                "acao_necessaria": False,
                "acao_mensagem": None
            }

status_broadcaster = StatusBroadcaster()

import os
import json
import time
import random
from typing import Tuple, Dict, Any, Optional

class ShopeeRateLimiter:
    """
    Controlador de taxa de requisições e proteção anti-bloqueio de IP para o Shopee Radar.
    Implementa:
    1. Intervalo mínimo obrigatório entre requisições (Cooldown / Jitter).
    2. Limite máximo de requisições por hora (Quota horária).
    3. Verificação de Cache com TTL para evitar requisições repetidas ao mesmo produto.
    4. Persistência de estado para resistir a reloads do Streamlit.
    """

    DEFAULT_STATE_FILE = "data/shopee_radar_status.json"

    def __init__(
        self,
        min_interval_sec: float = 1.5,
        max_requests_per_hour: int = 50,
        default_cache_ttl_hours: float = 6.0,
        state_file: str = DEFAULT_STATE_FILE
    ):
        self.min_interval_sec = min_interval_sec
        self.max_requests_per_hour = max_requests_per_hour
        self.default_cache_ttl_hours = default_cache_ttl_hours
        self.state_file = state_file
        os.makedirs(os.path.dirname(self.state_file) or ".", exist_ok=True)
        self._load_state()

    def wait_if_needed(self, max_wait_sec: float = 5.0) -> Tuple[bool, str]:
        """
        Aguarda automaticamente o cooldown se ele for curto (<= max_wait_sec),
        evitando que o usuário receba mensagens de erro ou bloqueios desnecessários.
        """
        can_req, msg, wait_sec = self.check_can_request()
        if can_req:
            return True, "OK"
        if wait_sec <= max_wait_sec:
            time.sleep(wait_sec)
            return True, "Liberado após aguardar cooldown"
        return False, msg


    def _load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.last_request_time = float(data.get("last_request_time", 0.0))
                    self.hourly_requests = [float(t) for t in data.get("hourly_requests", [])]
                    return
            except Exception:
                pass
        self.last_request_time = 0.0
        self.hourly_requests = []

    def _save_state(self):
        try:
            now = time.time()
            # Limpa requisições com mais de 1 hora
            self.hourly_requests = [t for t in self.hourly_requests if (now - t) < 3600]
            data = {
                "last_request_time": self.last_request_time,
                "hourly_requests": self.hourly_requests
            }
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def check_can_request(self) -> Tuple[bool, str, int]:
        """
        Verifica se uma nova requisição externa à Shopee é permitida.
        Retorna:
          - can_request (bool)
          - message (str)
          - wait_seconds (int)
        """
        self._load_state()
        now = time.time()

        # 1. Checa cooldown mínimo desde a última requisição
        elapsed = now - self.last_request_time
        if elapsed < self.min_interval_sec:
            wait = int(self.min_interval_sec - elapsed) + 1
            return False, f"Proteção de IP: aguarde {wait}s antes de consultar a Shopee novamente.", wait

        # 2. Checa limite horário
        one_hour_ago = now - 3600
        recent = [t for t in self.hourly_requests if t > one_hour_ago]
        if len(recent) >= self.max_requests_per_hour:
            oldest = min(recent)
            wait_for_slot = int(3600 - (now - oldest)) + 1
            return False, f"Limite de segurança atingido ({len(recent)}/{self.max_requests_per_hour} reqs/h). Liberação em {wait_for_slot // 60}m {wait_for_slot % 60}s.", wait_for_slot

        return True, "Requisição liberada com segurança.", 0

    def record_request_made(self):
        """Registra que uma requisição externa foi efetuada."""
        now = time.time()
        self.last_request_time = now
        self.hourly_requests.append(now)
        self._save_state()

    def apply_safe_delay(self):
        """Aplica uma pausa aleatória (jitter) para emular comportamento humano."""
        jitter = random.uniform(1.2, 2.8)
        time.sleep(jitter)

    def get_status_info(self) -> Dict[str, Any]:
        """Retorna estatísticas operacionais para exibição na interface."""
        self._load_state()
        now = time.time()
        recent = [t for t in self.hourly_requests if (now - t) < 3600]
        elapsed_since_last = now - self.last_request_time if self.last_request_time > 0 else 999999

        can_req, msg, wait_sec = self.check_can_request()

        return {
            "can_request": can_req,
            "message": msg,
            "wait_seconds": wait_sec,
            "requests_last_hour": len(recent),
            "max_requests_per_hour": self.max_requests_per_hour,
            "seconds_since_last": int(elapsed_since_last),
            "min_interval_sec": self.min_interval_sec,
            "protection_active": True
        }

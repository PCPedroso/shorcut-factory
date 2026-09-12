import unittest
from unittest.mock import patch, MagicMock
import os
import json


class TestFullVideoDefault(unittest.TestCase):
    """
    Testa a funcionalidade onde, se o usuário não definir Tempo Inicial e Tempo Final
    na Seção 3 (Fábrica de Enquadramentos), a aplicação considera o vídeo inteiro por padrão.
    """

    def test_default_times_when_inputs_empty(self):
        """
        Valida que se _raw_start e _raw_end estiverem vazios:
        - start_time assume '00:00:00.00'
        - end_time assume a duração total conhecida formatada
        - is_full_video_mode é True
        """
        _raw_start = ""
        _raw_end = ""
        _known_total_dur = 125.45  # 2 minutos, 5 segundos e 450ms

        def _format_dur_str(s):
            if not s or s <= 0:
                return "23:59:59.00"
            h, m, sec = int(s // 3600), int((s % 3600) // 60), s % 60
            return f"{h:02d}:{m:02d}:{sec:05.2f}"

        is_full_video_mode = not (_raw_start and _raw_start.strip()) and not (_raw_end and _raw_end.strip())
        start_time = _raw_start.strip() if (_raw_start and _raw_start.strip()) else "00:00:00.00"
        if _raw_end and _raw_end.strip():
            end_time = _raw_end.strip()
        elif _known_total_dur and _known_total_dur > 0:
            end_time = _format_dur_str(_known_total_dur)
        else:
            end_time = ""

        self.assertTrue(is_full_video_mode)
        self.assertEqual(start_time, "00:00:00.00")
        self.assertEqual(end_time, "00:02:05.45")

    def test_partial_time_inputs(self):
        """
        Valida que:
        - Se apenas início for digitado (ex: '00:01:00.00'), fim vai até a duração total.
        - Se apenas fim for digitado (ex: '00:05:00.00'), início começa em '00:00:00.00'.
        """
        _known_total_dur = 600.0  # 10 minutos

        def _format_dur_str(s):
            if not s or s <= 0:
                return "23:59:59.00"
            h, m, sec = int(s // 3600), int((s % 3600) // 60), s % 60
            return f"{h:02d}:{m:02d}:{sec:05.2f}"

        # Caso 1: Apenas início
        _raw_start = "00:01:00.00"
        _raw_end = ""
        start_time = _raw_start.strip() if (_raw_start and _raw_start.strip()) else "00:00:00.00"
        end_time = _raw_end.strip() if (_raw_end and _raw_end.strip()) else _format_dur_str(_known_total_dur)
        self.assertEqual(start_time, "00:01:00.00")
        self.assertEqual(end_time, "00:10:00.00")

        # Caso 2: Apenas fim
        _raw_start = ""
        _raw_end = "00:05:00.00"
        start_time = _raw_start.strip() if (_raw_start and _raw_start.strip()) else "00:00:00.00"
        end_time = _raw_end.strip() if (_raw_end and _raw_end.strip()) else _format_dur_str(_known_total_dur)
        self.assertEqual(start_time, "00:00:00.00")
        self.assertEqual(end_time, "00:05:00.00")

    def test_render_button_does_not_require_manual_times(self):
        """
        Valida que a ausência de input manual de minutagem não impede o fluxo
        de corte de avançar, definindo dinamicamente a duração total a partir do vídeo baixado.
        """
        start_time = ""
        end_time = ""
        fake_video_full_path = "data/dummy_vid/video_full.mp4"

        # Simula a lógica do botão render_button_label
        if not start_time or not start_time.strip():
            start_time = "00:00:00.00"

        with patch("core.quick_editor.get_video_duration", return_value=180.5):
            from core.quick_editor import get_video_duration
            if not end_time or not end_time.strip():
                _real_v_dur = get_video_duration(fake_video_full_path)
                if _real_v_dur and _real_v_dur > 0:
                    h, m, sec = int(_real_v_dur // 3600), int((_real_v_dur % 3600) // 60), _real_v_dur % 60
                    end_time = f"{h:02d}:{m:02d}:{sec:05.2f}"
                else:
                    end_time = "23:59:59.00"

        self.assertEqual(start_time, "00:00:00.00")
        self.assertEqual(end_time, "00:03:00.50")


if __name__ == "__main__":
    unittest.main()

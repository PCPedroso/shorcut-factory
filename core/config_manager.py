"""
config_manager.py — Gerenciador de Configurações Persistentes do ViralCut
Salva e restaura automaticamente todas as preferências do usuário em data/app_settings.json
garantindo que qualquer alteração seja mantida mesmo ao fechar a aplicação.
"""

import os
import json

SETTINGS_FILE = os.path.join("data", "app_settings.json")

DEFAULT_SETTINGS = {
    # Dispositivo e Modelos
    "device_option": "cpu",
    "model_size": "small",
    "ollama_model": "llama3",
    "analysis_strategy": "🎙️ Entrevistas & Sabatinas (Detecção Q&A [INÍCIO -> FIM])",

    # Enquadramento selecionado (índice da lista)
    "aspect_option": "📱 Vertical 9:16 (🎯 Rastreamento Inteligente de Rosto / Auto-Reframing)",

    # Rastreamento Facial Inteligente (Smart Face)
    "face_auto_zoom": True,
    "face_margin_ratio": 1.55,
    "person_preference": "auto",

    # Split Screen 9:16
    "split_preset": "Entrevistador(es) no Topo / Entrevistado na Base",
    "split_top_pan": -0.65,
    "split_bottom_pan": 0.65,
    "split_zoom": 1.15,
    "split_divider_color": "black",
    "split_divider_width": 4,
    "split_auto_switch": True,

    # Fundo Desfocado (Blur)
    "blur_preset": "Zoom Suave (1.35x) - Padrão",
    "blur_zoom_custom": 1.35,
    "blur_intensity": 25,
    "blur_pan_preset": "Centralizado (0.0)",
    "blur_pan_custom": 0.0,

    # Legendas Dinâmicas (Fase 2)
    "subtitle_enabled": False,
    "subtitle_highlight_color": "#FFFF00",
    "subtitle_base_color": "#FFFFFF",
    "subtitle_font_size": 80,

    # Headline de Retenção Superior (Fase 3)
    "headline_enabled": False,
    "headline_preset": "yellow_black",
    "headline_text_color": "#000000",
    "headline_bg_color": "#FFE600",
    "headline_font_size": 46,
    "headline_margin_top": 120,

    # Efeitos Visuais & Retenção (Fase 3)
    "emojis_enabled": False,
    "zoom_punch_enabled": False,

    # Trilha Sonora & Audio Ducking (Fase 3)
    "bg_music_enabled": False,
    "bg_music_track_id": "lofi_chill",
    "bg_music_volume": 0.15,
    "ducking_preset": "medio",

    # Integrações & Exportação Direta (Fase 3)
    "webhook_url": "",
    "webhook_auth_header": "",
    "youtube_client_secrets_path": "data/client_secrets.json",
    "youtube_privacy_status": "unlisted",

    # Última URL aberta
    "last_video_url": ""
}


def load_settings() -> dict:
    """Carrega as configurações salvas em data/app_settings.json mescladas aos valores padrão."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                merged = dict(DEFAULT_SETTINGS)
                merged.update(saved)
                return merged
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def save_setting(key: str, value):
    """Salva uma chave específica no arquivo de configurações."""
    settings = load_settings()
    settings[key] = value
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE) or "data", exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def save_all_settings(new_settings: dict):
    """Atualiza e salva um conjunto de configurações."""
    settings = load_settings()
    settings.update(new_settings)
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE) or "data", exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

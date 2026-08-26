---
name: viralcut-audio-sfx
description: >-
  Guia de engenharia sonora para o ViralCut: trilhas sonoras royalty-free, Sidechain Audio Ducking, injeção de Sound FX (SFX) sincronizados e normalização de áudio (Fase 5).
---

# ViralCut: Motor de Áudio, Trilha Sonora & SFX Engine

Este guia documenta o módulo `core/audio_mixer.py` e a implementação do motor de efeitos sonoros da Fase 5 (`core/sfx_manager.py`).

---

## 1. Trilha Sonora de Fundo & Sidechain Audio Ducking (`core/audio_mixer.py`)

- **Catálogo de Trilhas (`assets/audio/`)**:
  - `lofi_chill`: Ideal para vídeos educativos, reflexivos e podcasts calmos.
  - `dynamic_pulse`: Batida moderna para cortes de ação, negócios e tecnologia.
  - `tension_suspense`: Clima dramático para revelações, debates e polêmicas.
  - `inspirational_epic`: Trilha crescente para histórias de superação e motivação.
- **Filtro FFmpeg Sidechain Ducking**:
  - Utiliza o compressor de áudio lateral do FFmpeg (`sidechaincompress` / `acompressor`):
  - Quando a voz do orador ultrapassa o limiar (threshold), o volume da música de fundo é atenuado de forma imperceptível (ducking de 15% a 30%).
  - Nas pausas de fala, a música sobe suavemente mantendo a energia do corte.

---

## 2. Biblioteca de Sound FX Inteligentes (SFX Engine - Fase 5)

Para aumentar a retenção e dinamismo dos cortes:
1. **Eventos Sonoros Sincronizados**:
   - **Whoosh / Swish**: Sincronizado com transições de câmera, Zoom Punch e revelações de texto.
   - **Pop / Bubble / Ka-ching**: Sincronizado com a aparição de emojis de destaque nas legendas dinâmicas (ex: 💰, 💡, 🔥).
   - **Boom / Sub-Drop / Alerta**: Inserido na punchline ou momento de clímax identificado pelo score de retenção.
2. **Normalização de Áudio**:
   - Aplicação do filtro `loudnorm` do FFmpeg de acordo com as normas EBU R128 (integrado a $-14\text{ LUFS}$ e pico máximo de $-1.0\text{ dBTP}$ para TikTok, Reels e Shorts).

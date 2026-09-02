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
  - `phonk_power_override`: Grave 808 pesado, cowbell Memphis e batida acelerada para superação, força extrema e mindset.
  - `heavy_rock_overdrive`: Riffs de guitarra com distorção pesada e bateria explosiva para adrenalina, debates e confrontos.
  - `comedy_meme_funny`: Melodia ragtime saltitante e efeitos cartoon para gafes, piadas e momentos hilários.
  - `epic_hype_glory`: Orquestra cinematográfica imponente e tímpanos para glória, superação e vitória.
  - `lofi_chill`: Ideal para conversas reflexivas, estudos e tecnologia.
  - `dynamic_pulse`: Batida moderna e acelerada para dicas rápidas e vendas.
  - `tension_suspense`: Clima de mistério, curiosidade e revelações.
  - `inspirational_epic`: Harmonia expansiva para discursos motivacionais suaves.
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

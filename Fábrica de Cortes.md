# ViralCut — Fábrica de Cortes

## 🎯 Objetivo

Automatizar a esteira completa de criação, inteligência editorial, recorte e empacotamento de cortes virais (Shorts, Reels, TikTok e vídeos médios de YouTube) a partir de links do YouTube ou arquivos locais, com foco em retenção máxima, coerência semântica e padrão profissional de edição humana.

---

## 🛠️ Stack Tecnológica

| Componente | Tecnologia | Finalidade |
|---|---|---|
| **Linguagem** | Python 3.10+ | Núcleo de processamento e automação |
| **Interface** | Streamlit | Web UI interativa local, modular e minimalista |
| **Extração & Download** | `yt-dlp` (Multi-thread 16x) | Download ultra-rápido de áudio, metadados oficiais e vídeo em até 1080p Full HD (com suporte a lives e `post_live`) |
| **Transcrição** | `faster-whisper` + ASR YouTube | Transcrição com timestamps por palavra acelerada por GPU CUDA |
| **Visão Computacional** | `MediaPipe` + `OpenCV` | Face tracking, Target Lock e transição dinâmica Split/Full Screen |
| **Inteligência Editorial** | `Ollama` (Llama 3 local / Qwen) | Análise semântica, detecção Q&A e Kit Viral de Publicação |
| **Processamento de Vídeo** | `FFmpeg` (com `libass` e NVENC) | Recorte, filtros complexos, sidechain compress, equalização e queima de legendas/overlays |
| **Configurações & Cache** | JSON local estruturado | Persistência contínua de preferências e catálogo multi-formato |
| **Testes Unitários** | `pytest` | Validação contínua de integridade dos módulos centrais (68 testes) |

---

## 🏗️ Arquitetura de Módulos & Estrutura de Diretórios

```
shorcut-factory/
├── app.py                     # Interface Web Streamlit (4 seções + Edição Rápida Pós-Corte + Integrações)
├── conftest.py                # Configuração de ambiente para pytest
├── assets/
│   ├── audio/                 # Trilhas sonoras royalty-free categorizadas (.wav / .mp3)
│   └── fonts/                 # Tipografias bundled (Montserrat-ExtraBold)
├── tests/                     # Suíte de Testes Unitários Automatizados (68 testes)
│   ├── test_quick_editor.py      # Testes de duração, trim, corte cirúrgico e concatenação
│   ├── test_thumbnail_generator.py # Testes de frames, nitidez e capas 9:16
│   ├── test_headline_drawer.py   # Testes de headlines, quebras, presets ASS e overlay visual
│   ├── test_audio_processor.py   # Testes de equalização, anti-estouro e nivelamento dinâmico
│   ├── test_split_secondary_media.py # Testes de Split Screen com mídias secundárias e margens de blur
│   ├── test_export_kit.py        # Testes de pastas, prefixos e kit viral
│   ├── test_cuts_catalog.py      # Testes de catálogo, instâncias e exclusão
│   ├── test_audio_mixer.py       # Testes de trilhas e áudio ducking
│   ├── test_retention_effects.py # Testes de zoom punch, progress bar e callouts
│   ├── test_config_manager.py    # Testes de persistência de configurações
│   ├── test_integrations.py      # Testes de webhooks e payloads
│   └── test_analyzer_utils.py    # Testes de conversão de tempo e textos
├── core/
│   ├── quick_editor.py        # Edição rápida / ajuste fino: Trim (início/fim) e Snip & Merge de trechos
│   ├── audio_processor.py     # Equalização, anti-estouro (de-clipping/limiter), nivelador dinâmico de voz/torcida
│   ├── overlay_manager.py     # Motor de sobreposição de banners, tarjas (GC), logos com modos fill/fit/cover
│   ├── headline_drawer.py     # Estilização de Headlines magnéticas de topo (Live Preview, box por linha, card e outline)
│   ├── extractor.py           # Extração acelerada 16-thread de áudio, canais e metadados via yt-dlp
│   ├── transcriber.py         # Transcrição faster-whisper (CUDA) + fallback ASR YouTube com ID limpo
│   ├── analyzer.py            # Análise Q&A/Temática, Séries Sugeridas flexíveis e Kit Viral com IA
│   ├── video_processor.py     # Pipeline FFmpeg para os 5 formatos de enquadramento + download multi-thread
│   ├── face_tracker.py        # Detecção facial MediaPipe, Deadband Anchor e Split Screen Auto-Switch
│   ├── subtitle_burner.py     # Geração de legendas dinâmicas em ASS + Headlines + Emojis + Callout
│   ├── thumbnail_generator.py # Extração de melhor frame (MediaPipe/sharpness) e capas 9:16 multicamadas
│   ├── audio_mixer.py         # Mixagem de áudio com Ducking dinâmico via sidechaincompress FFmpeg
│   ├── retention_effects.py   # Barra de progresso, Zoom Punch, Climax Zoom e Callout ASS
│   ├── integrations.py        # Upload YouTube Shorts API v3 e despachante de Webhooks
│   ├── export_kit.py          # Nomenclatura estrita (VLDSS, VRIRA...) e pastas de publicação com thumbnail
│   ├── cuts_catalog.py        # Catálogo e cache inteligente multi-instância (cuts_catalog.json)
│   ├── batch_processor.py     # Processamento sequencial em lote com Smart Skip e Phase 4
│   ├── library_manager.py     # Catálogo global de vídeos processados (library.json)
│   └── config_manager.py      # Persistência contínua de preferências (app_settings.json)
├── data/
│   ├── library.json           # Biblioteca geral de vídeos processados
│   ├── app_settings.json      # Configurações do usuário persistidas
│   ├── youtube_token.json     # Token de autorização OAuth do YouTube Shorts
│   └── <video_id>/
│       ├── audio.mp3          # Cache do áudio extraído
│       ├── transcript.json    # Transcrição com timestamps por palavra
│       ├── video_full.mp4     # Vídeo original Full HD 1080p
│       ├── cuts_catalog.json  # Catálogo de cortes e formatos gerados para este vídeo
│       └── <PREFIXO>_<NOME>/  # Pasta final do corte (Vídeo + Thumbnail + Kit de Publicação)
└── requirements.txt
```

---

## 📐 Regras de Ouro Editoriais para Cortes e Micro-Cortes (Shorts / Reels)

A esteira de inteligência artificial segue estritamente as seguintes 6 diretrizes editoriais:

1. **🎬 Ponto de Entrada Limpo (*Clean Entry & Audio Snapping*)**: O corte inicia no milissegundo exato da primeira palavra falada (com margem de **100ms a 150ms** de respiro inicial).
2. **🏁 Ponto de Saída com Conclusão e Respiro (*Punchline & Breath-out*)**: O corte termina após o fechamento da última oração do raciocínio, mantendo **200ms a 300ms** de pausa natural antes do corte. É terminantemente proibido vazar o início da fala ou pauta seguinte.
3. **🧠 Autonomia Semântica (*Standalone Comprehensibility*)**: O espectador compreende 100% da mensagem sem precisar do contexto do vídeo completo.
4. **🗂️ Tipologia Editorial dos Cortes**:
   - `🏷️ [Q&A] Pergunta & Resposta Completa [35s a 80s]`
   - `🏷️ [Punchline] Declaração / Tese de Impacto [25s a 55s]`
   - `🏷️ [Debate] Confronto & Réplica Rápida [35s a 70s]`
5. **🚫 Filtro Anti-Vazamento e Isolamento de Pautas**: Raciocínios e temas diferentes nunca são misturados no mesmo corte curto.
6. **⏱️ Janela Temporal de Retenção**: Duração ideal de **20 a 75 segundos** para Shorts/Reels/TikTok.

---

## 📐 Formatos de Enquadramento Disponíveis (Seção 3)

| Formato | Prefixo da Pasta | Descrição |
|---|---|---|
| **Layout Dividido (Split Screen)** | `VLDSS` | Estilo Podpah/Flow. Possui **Transição Dinâmica (Auto-Switch)**: se 2+ pessoas visíveis $\to$ Split Screen; se close de 1 pessoa $\to$ 9:16 Full Screen com MediaPipe. Suporta mídia secundária (vídeo em looping ou slideshow de imagens) e margens de blur anti-sobreposição. |
| **Auto-Reframing Facial** | `VRIRA` | Rastreamento inteligente de rosto com Deadband Anchor, Target Lock e Auto-Zoom suave. |
| **Fundo Desfocado (Blur)** | `VFDBS` | Vídeo central nítido com fundo desfocado preenchendo a tela 9:16. |
| **Corte Central (Crop)** | `VCCFT` | Corte centralizado direto em 9:16. |
| **Horizontal Original 16:9** | `HOFHD` | Mantém o enquadramento original Full HD 1080p com suporte a zoom horizontal proporcional (1.0x a 1.5x). |

---

## ✅ Fases Concluídas e Sincronizadas

### 🔹 Fase 1 — Estrutura Base, Análise e Enquadramentos 9:16
- **Interface Streamlit** modular (`app.py`).
- **Biblioteca de Vídeos & Download** via `yt-dlp` em até 1080p Full HD com persistência de metadados e canal.
- **Transcrição** acelerada por GPU CUDA via `faster-whisper` e fallback automático para ASR do YouTube.
- **Inteligência Temática Dual** com Ollama (Llama 3 local):
  - Modo `🎙️ Entrevistas & Sabatinas`: Detecção de turnos Q&A com timestamp exato `[INÍCIO → FIM]`.
  - Modo `🧠 Temático / Monólogos`: Mapeamento de transições de tópicos e ganchos contínuos.
- **Ganchos Virais (Shorts / Reels)** estruturados sob as **6 Regras de Ouro Editoriais**.
- **5 Modos de Enquadramento de Vídeo** em `core/video_processor.py` (Split Screen Auto-Switch, Auto-Reframing, Blur, Crop, 16:9).

### 🔹 Fase 2 — Legendas Dinâmicas, Kit Viral, Lote e Catálogo Inteligente
- **Legendas Dinâmicas Estilo CapCut / Alex Hormozi** (`core/subtitle_burner.py`):
  - Renderização nativa em ASS (`libass` do FFmpeg) com efeito karaokê palavra-a-palavra sincronizado.
  - Cores configuráveis (Destaque e Base), sliders de fonte e contorno nítido.
- **Kit de Publicação Viral com IA com Guia Editorial (`core/analyzer.py`, `app.py`)**:
  - Título Magnético, Variações Alternativas, Legenda com CTA e Hashtags/SEO contextuais. Geração individualizada de cada texto sob demanda.
  - **Direção Editorial Personalizada (`user_guidance`)**: Campo dedicado para instruir a IA sobre tom (ex: polêmico, indignado, bem-humorado, sério, urgente) e assunto ou gancho central a priorizar na geração dos textos.
- **Exportação Padronizada com Nomenclatura Estrita** (`core/export_kit.py`):
  - Prefixos de 5 letras (`VLDSS`, `VRIRA`, `VFDBS`, `VCCFT`, `HOFHD`) + limite de 25 caracteres em palavras completas do título.
- **Catálogo & Cache Inteligente por Minutagem e Formato** (`core/cuts_catalog.py`):
  - Rastreamento em `data/<video_id>/cuts_catalog.json` de múltiplas instâncias de enquadramento com abertura instantânea (0s).

---

## ⚡ Recursos Implementados & Em Produção

- **✂️ Ferramenta Integrada de Edição Rápida, Ajuste Fino & Histórico Persistente (`core/quick_editor.py`, `app.py`)**:
  - **Sinalização Persistente de Conclusão**: Após qualquer ajuste pós-corte (*Trim*, *Remover Trecho*, *Banner*, *Headline*, *Equalização de Áudio*), um card verde de confirmação permanece no topo do componente com carimbo de data/hora, ação realizada, detalhes dos parâmetros e arquivo gerado.
  - **Histórico Completo de Edições (`historico_edicoes.json`)**: Cada pasta de corte armazena o histórico em JSON de todos os ajustes aplicados cronologicamente, com visualizador em expander exibindo a linha do tempo de alterações.
  - **5 Abas de Pós-Corte**:
    1. *✂️ Aparar (Trim)* com prévia de frames de início e fim.
    2. *🗑️ Remover Trecho (Snip & Merge)* para corte de gafes e silêncios.
    3. *🎨 Banner / Tarja (Overlay)* com suporte a logo embutido.
    4. *🏷️ Headline de Topo* com renderização acelerada por GPU.
    5. *🎙️ Equalizador & Áudio* com preset para lives/estouro e torcida/ambiente.
- **🏷️ Headline / Título de Topo Magnético Pós-Corte (`core/headline_drawer.py`, `app.py`)**:
  - Adição ou troca do título fixo do corte sem necessidade de reprocessar o vídeo do zero.
  - Modos de container: *Caixa por Linha (TikTok/Reels)*, *Card Único (Bloco)* e *Sem Caixa (Contorno/Outline)*.
  - Controle completo de margem do topo (Offset Y), tamanho de fonte, largura do container, padding horizontal/vertical, espaçamento entre linhas, cantos arredondados, alinhamento, opacidade e sombra projetada.
  - **Prévia visual instantânea no frame em tempo real** e queima no vídeo acelerada por GPU (NVENC).
- **🎙️ Equalizador, Anti-Estouro & Nivelador Dinâmico de Áudio no Pós-Corte (`core/audio_processor.py`, `app.py`)**:
  - Nova aba no pós-corte para tratamento cirúrgico de microfones sobrecarregados em lives e eventos.
  - **Perfil Anti-Estouro & Voz + Torcida (Recomendado)**: Aplica De-Clipper + Brickwall Limiter + Nivelador Dinâmico (`dynaudnorm`), suavizando a voz saturada do microfone enquanto eleva de forma harmônica a vibração da torcida e som ambiente nos momentos certos.
  - Presets especializados: *Clareza de Voz (Podcast)*, *De-Clipper Suave*, *Nivelador Agressivo (Rua/IRL)* e *Normalização Social (-14 LUFS)*.
  - **Prévia sonora imediata via player** e aplicação instantânea no vídeo via *Stream Copy* (~1s sem re-renderizar vídeo).
- **⚡ Download Ultra-Acelerado Multi-Thread do YouTube (`core/extractor.py`, `core/video_processor.py`)**:
  - Download paralelo em **16 conexões simultâneas** com chunks HTTP de 10 MB e buffers de 1 MB, eliminando throttling do YouTube.
  - Áudio de transmissões de mais de 2 horas baixando em **~8 segundos** (35 MB/s).
  - Suporte completo a lives ativas e transmissões recém-encerradas (`post_live` / `was_live`) com fallback multi-estratégia.
- **🎬 Split Screen com Mídia Secundária & Margens Desfocadas (Blur Margins) (`core/face_tracker.py`, `core/video_processor.py`)**:
  - Suporte para preencher a metade inferior (ou superior) do Split Screen com **Vídeo em Looping Contínuo** ou **Conjunto de Imagens (Slideshow Dinâmico)** com tempo de exibição proporcional à duração do corte.
  - **Margens Desfocadas no Topo e Rodapé (`split_blur_margin_pct`)**: Margens de 0% a 20% com blur para afastar os participantes das bordas e evitar que a interface do TikTok/Reels cubra os rostos.
- **💡 Séries Sugeridas com Duração Mínima Configurável (`core/analyzer.py`, `app.py`)**:
  - Campo numérico para definir o tempo mínimo por corte de série (ex: 5, 10, 15 min) com agrupamento instantâneo sem re-executar IA.
- **🖼️ Gerador Avançado de Capas / Thumbnails Multicamadas com 3 Variações (`core/thumbnail_generator.py`)**:
  - Extração do frame mais expressivo via nitidez Laplaciana + MediaPipe BlazeFace.
  - Isolamento de sujeito por IA via `Rembg` (U2-Net) + micro-contraste adaptativo `OpenCV CLAHE` + Unsharp Mask.
  - Geração automática das 3 variações: `⚡ Impacto Neon (Glow)`, `✨ Clean Focus (Sombra 3D)` e `🎬 Moldura Dinâmica (HDR)`.
- **⏳ Barra de Progresso Animada & Banner de Chamada (Lower Third)** (`core/retention_effects.py`).
- **👥 Enquadramento Plano Conjunto & Dual Shot (`core/face_tracker.py`)**:
  - Auto-detecção espacial de debate/sabatina com Bounding Box composta.
- **🎨 Motor de Sobreposição de Banners, Tarjas (GC) e Logos (`core/overlay_manager.py`)**:
  - Modos `fill`, `fit`, `cover`, logo embutido secundário e prévia instantânea de frame.
- **🔍 Aproximação / Zoom no Modo Horizontal 16:9 (1.0x a 1.5x)** (`core/video_processor.py`).
- **🛡️ Estabilização Deadband Anchor no Rastreamento Facial (Zona Morta 90px)** (`core/face_tracker.py`).
- **🧪 Suíte de 69 Testes Unitários Automatizados (`tests/`)**:
  - 100% de aprovação contínua validando todos os módulos do pipeline via `pytest`.

---

## 🔮 Roadmap de Evolução Futura

### 🚀 Fase 5 — Sound FX (SFX) Inteligentes, B-Roll / Overlays de Contexto & Refinamento Visual (Médio a Avançado)
*Foco: Imersão sonora dinâmica, quebra de padrão visual com materiais visuais de apoio e aperfeiçoamento fino de capas e zooms.*

1. **🔊 Biblioteca de Efeitos Sonoros Inteligentes (SFX Engine)** (`core/sfx_manager.py`):
   - Inserção de efeitos sonoros curtos sincronizados: *Whoosh* no Zoom Punch, *Pop/Ka-ching* ao surgir emojis de destaque, *Boom/Alerta* em momentos de tensão.
   - Seleção automática da trilha sonora com base na análise de tom do Ollama.
2. **🎬 B-Roll Inteligente & Split Screen Híbrido** (`core/broll_engine.py`):
   - Detecção de entidades e tópicos visuais na fala (nomes de pessoas, notícias, dados, gráficos).
   - Inserção de imagens/vídeos de apoio na metade secundária do Split Screen ou em overlays curtos de 2 a 3 segundos (cutaways).

---

### 🚀 Fase 6 — Automação Total, Agendamento e Pipeline Sem Supervisão (Avançado)
*Foco: Escala de publicação autônoma em canais e redes sociais.*

1. **📅 Fila de Agendamento Automático de Postagens**:
   - Agendamento de publicações com cronograma e espaçamento de horários pré-definido via YouTube Data API v3 e Webhooks.
2. **🤖 Modo Fábrica 100% Autônomo (Zero-Touch Batch)**:
   - Processamento de ponta a ponta a partir de uma lista de URLs do YouTube: download $\to$ análise $\to$ recorte multi-formato $\to$ empacotamento $\to$ disparo sem intervenção manual.

---

### 🎯 Diretrizes & Regras do Projeto
1. **Documento Mestre Vivo**: `Fábrica de Cortes.md` é a base viva do projeto e deve ser mantida sempre sincronizada com as novas decisões e módulos.
2. **Regra de Git**: `git commit` normalmente durante o desenvolvimento, mas **`git push` SOMENTE quando o usuário solicitar explicitamente.**
3. **Ambiente**: Python em Windows com venv em `d:\Repository\shorcut-factory\venv`. Executar comandos com caminhos absolutos para o python/pip do venv.

# ViralCut — Fábrica de Cortes

## 🎯 Objetivo

Automatizar a esteira completa de criação, inteligência editorial, recorte e empacotamento de cortes virais (Shorts, Reels, TikTok e vídeos médios de YouTube) a partir de links do YouTube ou arquivos locais, com foco em retenção máxima, coerência semântica e padrão profissional de edição humana.

---

## 🛠️ Stack Tecnológica

| Componente | Tecnologia | Finalidade |
|---|---|---|
| **Linguagem** | Python 3.10+ | Núcleo de processamento e automação |
| **Interface** | Streamlit | Web UI interativa local, modular e minimalista |
| **Extração & Download** | `yt-dlp` (Multi-thread 16x) | Download ultra-rápido de YouTube, Instagram Reels, TikTok, Twitter/X e Web com metadados e cookies |
| **Transcrição** | `faster-whisper` + ASR YouTube | Transcrição com timestamps por palavra acelerada por GPU CUDA |
| **Visão Computacional** | `MediaPipe` + `OpenCV` | Face tracking, Target Lock e transição dinâmica Split/Full Screen |
| **Inteligência Editorial** | `Ollama` (Llama 3 local / Qwen) | Análise semântica, detecção Q&A e Kit Viral de Publicação |
| **Processamento de Vídeo** | `FFmpeg` (com `libass` e NVENC) | Recorte, filtros complexos, sidechain compress, equalização e queima de legendas/overlays |
| **Configurações & Cache** | JSON local estruturado | Persistência contínua de preferências e catálogo multi-formato |
| **Testes Unitários** | `pytest` | Validação contínua de integridade dos módulos centrais (75 testes) |

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
  - **Direção Editorial Personalizada (`user_guidance`)**: Campo dedicado para instruir a IA sobre tom e assunto prioritário.
- **Exportação Padronizada com Nomenclatura Estrita** (`core/export_kit.py`):
  - Prefixos de 5 letras (`VLDSS`, `VRIRA`, `VFDBS`, `VCCFT`, `HOFHD`) + limite de 25 caracteres em palavras completas do título.
- **Catálogo & Cache Inteligente por Minutagem e Formato** (`core/cuts_catalog.py`):
  - Rastreamento em `data/<video_id>/cuts_catalog.json` de múltiplas instâncias de enquadramento com abertura instantânea (0s).

---

## ⚡ Recursos Implementados & Em Produção

- **📝 Extração Automática de Legendas & Transcrição do Corte (`core/subtitle_burner.py`, `core/export_kit.py`)**:
  - Ao renderizar qualquer corte (individual ou em lote), o sistema gera automaticamente na mesma pasta do vídeo:
    1. `<PREFIXO_Titulo>.srt` e `legendas.srt`: Formato SubRip universal com timestamps relativos ao corte (`00:00:00,000`).
    2. `<PREFIXO_Titulo>.vtt`: Formato WebVTT para web players.
    3. `transcricao_corte.txt`: Transcrição contínua limpa em texto corrido exclusivamente da fala do corte.
- **✂️ Ferramenta Integrada de Edição Rápida, Ajuste Fino & Histórico Persistente (`core/quick_editor.py`, `app.py`)**:
  - **Sinalização Persistente de Conclusão**: Card verde com carimbo de data/hora, ação realizada, detalhes dos parâmetros e arquivo gerado.
  - **Histórico Completo de Edições (`historico_edicoes.json`)**: Histórico JSON de todos os ajustes aplicados cronologicamente.
  - **5 Abas de Pós-Corte**: *Trim*, *Snip & Merge*, *Banner*, *Headline de Topo* e *Equalizador & Áudio*.
- **🏷️ Headline / Título de Topo Magnético Pós-Corte (`core/headline_drawer.py`, `app.py`)**:
  - Modos: *Caixa por Linha (TikTok/Reels)*, *Card Único* e *Sem Caixa (Contorno)* com live preview e aceleração GPU (NVENC).
  - **Paleta Padrão Viral**: Texto em Preto Absoluto (`#000000`) sobre Fundo Amarelo Ouro Viral (`#FFDA29`) com sincronização automática entre Edição Rápida e pipeline principal.
- **🎙️ Equalizador, Anti-Estouro & Nivelador Dinâmico de Áudio no Pós-Corte (`core/audio_processor.py`, `app.py`)**:
  - *Perfil Anti-Estouro & Voz + Torcida*: De-Clipper + Brickwall Limiter + Nivelador Dinâmico (`dynaudnorm`).
  - Prévia sonora e Stream Copy (~1s sem re-renderizar vídeo).
- **⚡ Download Ultra-Acelerado Multi-Thread do YouTube (`core/extractor.py`, `core/video_processor.py`)**:
  - 16 conexões simultâneas, buffers de 10 MB, suporte a lives e `post_live`.
- **🎬 Split Screen com Mídia Secundária & Margens Desfocadas (Blur Margins) (`core/face_tracker.py`, `core/video_processor.py`)**:
  - Suporte a vídeo em loop, slideshow dinâmico e margens de blur no topo/rodapé de 0% a 20%.
- **💡 Séries Sugeridas com Duração Mínima Configurável (`core/analyzer.py`, `app.py`)**:
  - Tempo mínimo por corte de série (ex: 5, 10, 15 min) com agrupamento instantâneo.
- **🖼️ Gerador Avançado de Capas / Thumbnails Multicamadas com 3 Variações (`core/thumbnail_generator.py`)**:
  - Variações: `⚡ Impacto Neon (Glow)`, `✨ Clean Focus (Sombra 3D)` e `🎬 Moldura Dinâmica (HDR)`.
- **⏳ Barra de Progresso Animada & Banner de Chamada (Lower Third)** (`core/retention_effects.py`).
- **👥 Enquadramento Plano Conjunto & Dual Shot (`core/face_tracker.py`)**:
  - Auto-detecção espacial de debate/sabatina com Bounding Box composta.
- **🎨 Motor de Sobreposição de Banners, Tarjas (GC) e Logos (`core/overlay_manager.py`)**:
  - Modos `fill`, `fit`, `cover`, logo embutido secundário e prévia instantânea de frame.
- **🌐 Priorização Estrita de Português (PT-BR) & Detecção Multilinguagem (`core/transcriber.py`, `app.py`)**:
  - Prioridade máxima e estrita para transcrições oficiais do YouTube em Português (`pt-BR`, `pt`, `pt-PT`), evitando o download de legendas em inglês por engano.
  - Mapeamento dinâmico de todas as faixas de legenda disponíveis no YouTube com badge/sinalização de múltiplos idiomas detectados.
  - Fixação mandatória de `language="pt"` no fallback do Faster-Whisper, garantindo transcrição em português mesmo em vídeos com vinhetas musicais ou ruídos no início.
- **⏱️ Máscara Interativa & Normalização de Tempo com Milissegundos (`HH:MM:SS.ms`) (`core/analyzer.py`, `app.py`)**:
  - Injeção de máscara interativa JavaScript nos campos de tempo (`Tempo Inicial` e `Tempo Final`) formatando dígitos automaticamente no padrão `HH:MM:SS.ms` (com 2 dígitos de milissegundos) durante a digitação.
  - Normalizador Python de alta precisão (`normalize_time_mask`) e parser float (`parse_time_str_to_seconds`) com suporte integral a cortes no milissegundo exato (ex: `00:01:30.50`, `00:00:45.00`, `1000` -> `00:10:00.00`).
- **📱 Ingestão Multi-Plataforma & Download Automático (Instagram, TikTok, YouTube & Web) (`core/extractor.py`, `core/video_processor.py`, `app.py`)**:
  - Reconhecimento automático de links de múltiplas redes sociais: **Instagram Reels / Posts / TV** (`ig_...`), **TikTok** (`tt_...`), **Twitter/X** (`tw_...`), **YouTube** e links web genéricos.
  - Suporte automático a arquivos de autenticação/cookies (`data/cookies.txt` ou `data/instagram_cookies.txt`) para extração sem restrições de bloqueio de bots.
  - Transcrição automática instantânea com Faster-Whisper em Português-BR para qualquer vídeo baixado das redes.
- **🔥 Ganchos Virais & Duração Máxima Configurável para Shorts (`core/analyzer.py`, `app.py`)**:
  - Opção interativa para definir o teto de duração máxima dos Shorts/Reels/TikTok (ex: 30s, 45s, 60s, 90s até 180s) com persistência automática em `app_settings.json`.
  - Reestruturação instantânea de micro-cortes sob as 6 Regras de Ouro sem necessidade de reprocessar o Ollama.
- **🎵 Biblioteca Expandida de Trilhas Sonoras & Audio Ducking (`core/audio_mixer.py`, `app.py`)**:
  - **8 Categorias Pré-configuradas**: `Phonk Agressivo / Sigma` (808 + Cowbell Memphis para superação e força), `Heavy Rock / Overdrive` (Guitarras distorcidas e bateria pesada para adrenalina), `Cômico / Meme & Humor` (Ragtime e efeitos cartoon para gafes e piadas), `Épico / Glória` (Orquestra imponente para discursos e vitórias), além de `Lo-Fi Chill`, `Dinâmica / Ritmo Moderno`, `Tensão / Suspense` e `Inspiracional Suave`.
  - **Player de Pré-Escuta Integrado**: Permite ouvir qualquer trilha antes de renderizar o corte.
  - **Importação Direta & Abertura de Pasta**: Uploader na interface para adicionar arquivos `.mp3`/`.wav` personalizados e botão para abrir diretamente a pasta `assets/audio` no Windows Explorer.
- **🎬 Composição Sequencial Dupla no Carregamento de Arquivo (Split P&B ➔ Full Screen) (`core/video_processor.py`, `app.py`)**:
  - Suporte ao upload de até **2 arquivos de vídeo locais** com escolha interativa da **ordem de reprodução**.
  - **Parte 1 (Início)**: Tela dividida (Split Screen) com o 1º vídeo reproduzindo normalmente no topo e o 2º vídeo congelado na base em modo **Monocromático (Preto e Branco)**.
  - **Parte 2 (Transição)**: Assim que o 1º vídeo termina, o 2º vídeo assume automaticamente **100% da tela cheia** com áudio ativo.
  - **Ambientação Sonora Independente**: Possibilidade de escolher uma trilha sonora específica para o 1º vídeo (ex: Cômico / Humor / Lo-Fi) e outra para o 2º vídeo (ex: Phonk Agressivo / Heavy Rock / Superação) com volumes individuais e **Audio Ducking inteligente** aplicado em ambas as partes.
  - Renderização acelerada via NVENC GPU/FFmpeg (`compose_dual_video_split_sequence`) com geração unificada de áudio (`audio.mp3`) e transcrição Whisper contínua para alimentação de toda a esteira de cortes, IA e legendas.
- **🎵 Extração de Áudio Isolado, Reconhecimento de Música & Biblioteca (`core/extractor.py`, `core/music_recognizer.py`, `core/audio_mixer.py`, `core/export_kit.py`, `app.py`)**:
  - **Motor Especializado de Reconhecimento Musical (`core/music_recognizer.py`)**:
    - Filtra automaticamente títulos genéricos de posts de redes sociais (ex: *"Video by dosesdepsico"*, *"Post by user"*).
    - Extrai o **Artista e Nome Real da Música** (ex: *Iron Maiden - Fear of the Dark*, *Kordhell - Murder In My Mind*) a partir dos metadados oficiais (`track`, `artist`, `album`), créditos citados na descrição e transcrição de trechos de letras (Whisper) combinada com IA local (Ollama).
  - **Inclusão na Biblioteca de Trilhas (`assets/audio/`)**: Botão `🌟 Adicionar à Biblioteca de Trilhas de Fundo` que salva o som extraído na pasta de assets com metadados persistentes (`custom_tracks.json`), disponibilizando-o imediatamente em todas as seleções de música e composições duplas.
  - **Links da Web (YouTube, Instagram, TikTok, etc.)**: Extração direta de áudio em 192kbps MP3 com player e download imediato.
  - **Arquivos Locais (1 ou 2 Vídeos)**: Extração ultra-rápida via FFmpeg do áudio individual ou unificado da composição dupla com ambientação musical personalizada.
  - **Vídeos Processados & Galeria de Cortes**: Player e botão `📥 Baixar Áudio Completo (MP3)` no cabeçalho do projeto ativo e `🎵 Baixar Áudio do Corte (MP3)` em cada corte/instância gerada no pacote de publicação viral.
- **🛡️ Estabilização Deadband Anchor no Rastreamento Facial (Zona Morta 90px)** (`core/face_tracker.py`).
- **🧪 Suíte de 84 Testes Unitários Automatizados (`tests/`)**:
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
3. **🌐 Seletor Interativo e Tradução de Transcrições Multilinguagem**:
   - Menu dropdown para alternar e baixar transcrições em diferentes idiomas disponíveis no YouTube quando detectadas faixas multilíngues, ou gerar versões legendadas traduzidas automaticamente (PT/EN/ES).

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

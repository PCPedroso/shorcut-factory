# ViralCut — Fábrica de Cortes

## 🎯 Objetivo

Automatizar a esteira completa de criação, inteligência editorial, recorte e empacotamento de cortes virais (Shorts, Reels, TikTok e vídeos médios de YouTube) a partir de links do YouTube, com foco em retenção máxima, coerência semântica e padrão profissional de edição humana.

---

## 🛠️ Stack Tecnológica

| Componente | Tecnologia | Finalidade |
|---|---|---|
| **Linguagem** | Python 3.10+ | Núcleo de processamento e automação |
| **Interface** | Streamlit | Web UI interativa local, modular e minimalista |
| **Extração & Download** | `yt-dlp` | Download de áudio, metadados oficiais e vídeo em até 1080p Full HD |
| **Transcrição** | `faster-whisper` + ASR YouTube | Transcrição com timestamps por palavra acelerada por GPU CUDA |
| **Visão Computacional** | `MediaPipe` + `OpenCV` | Face tracking, Target Lock e transição dinâmica Split/Full Screen |
| **Inteligência Editorial** | `Ollama` (Llama 3 local / Qwen) | Análise semântica, detecção Q&A e Kit Viral de Publicação |
| **Processamento de Vídeo** | `FFmpeg` (com `libass`) | Recorte, filtros complexos, sidechain compress e queima de legendas nativas |
| **Configurações & Cache** | JSON local estruturado | Persistência contínua de preferências e catálogo multi-formato |
| **Testes Unitários** | `pytest` | Validação contínua de integridade dos módulos centrais |

---

## 🏗️ Arquitetura de Módulos & Estrutura de Diretórios

```
shorcut-factory/
├── app.py                     # Interface Web Streamlit (4 seções + Integrações)
├── conftest.py                # Configuração de ambiente para pytest
├── assets/
│   └── audio/                 # Trilhas sonoras royalty-free categorizadas (.wav / .mp3)
├── tests/                     # Suíte de Testes Unitários Automatizados
│   ├── test_quick_editor.py      # Testes de duração, trim, corte cirúrgico e concatenação
│   ├── test_thumbnail_generator.py # Testes de frames, nitidez e capas 9:16
│   ├── test_headline_drawer.py   # Testes de headlines, quebras e formato ASS
│   ├── test_export_kit.py        # Testes de pastas, prefixos e kit viral
│   ├── test_cuts_catalog.py      # Testes de catálogo, instâncias e exclusão
│   ├── test_audio_mixer.py       # Testes de trilhas e áudio ducking
│   ├── test_retention_effects.py # Testes de zoom punch, progress bar e callouts
│   ├── test_config_manager.py    # Testes de persistência de configurações
│   ├── test_integrations.py      # Testes de webhooks e payloads
│   └── test_analyzer_utils.py    # Testes de conversão de tempo e textos
├── core/
│   ├── quick_editor.py        # Edição rápida / ajuste fino: Trim (início/fim) e Snip & Merge de trechos
│   ├── extractor.py           # Extração de áudio, canais e metadados via yt-dlp
│   ├── transcriber.py         # Transcrição faster-whisper (CUDA) + fallback ASR YouTube
│   ├── analyzer.py            # Análise Q&A/Temática e geração do Kit Viral com IA
│   ├── video_processor.py     # Pipeline FFmpeg para os 5 formatos de enquadramento + efeitos
│   ├── face_tracker.py        # Detecção facial MediaPipe e Split Screen Auto-Switch
│   ├── subtitle_burner.py     # Geração de legendas dinâmicas em ASS + Headlines + Emojis + Callout
│   ├── headline_drawer.py     # Estilização de Headlines magnéticas de topo (Amarelo, Red, Dark, Custom)
│   ├── thumbnail_generator.py # Extração de melhor frame (MediaPipe/sharpness) e capas 9:16
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
| **Layout Dividido (Split Screen)** | `VLDSS` | Estilo Podpah/Flow. Possui **Transição Dinâmica (Auto-Switch)**: se 2+ pessoas visíveis $\to$ Split Screen; se close de 1 pessoa $\to$ 9:16 Full Screen automático com MediaPipe. |
| **Auto-Reframing Facial** | `VRIRA` | Rastreamento inteligente de rosto com Target Lock e Auto-Zoom suave. |
| **Fundo Desfocado (Blur)** | `VFDBS` | Vídeo central nítido com fundo desfocado preenchendo a tela 9:16. |
| **Corte Central (Crop)** | `VCCFT` | Corte centralizado direto em 9:16. |
| **Horizontal Original 16:9** | `HOFHD` | Mantém o enquadramento original Full HD 1080p. |

---

## ✅ Fases Concluídas e Sincronizadas

### 🔹 Fase 1 — Estrutura Base, Análise e Enquadramentos 9:16
- **Interface Streamlit** modular (`app.py`).
- **Biblioteca de Vídeos & Download** via `yt-dlp` em até 1080p Full HD com persistência de metadados e canal.
- **Transcrição** acelerada por GPU CUDA via `faster-whisper` e fallback automático para ASR do YouTube.
- **Inteligência Temática Dual** com Ollama (Llama 3 local):
  - Modo `🎙️ Entrevistas & Sabatinas`: Detecção de turnos Q&A com timestamp exato `[INÍCIO → FIM]`.
  - Modo `🧠 Temático / Monólogos`: Mapeamento de transições de tópicos e ganchos contínuos (10+ min).
- **Ganchos Virais (Shorts / Reels)** estruturados sob as **6 Regras de Ouro Editoriais**.
- **5 Modos de Enquadramento de Vídeo** em `core/video_processor.py` (Split Screen Auto-Switch, Auto-Reframing, Blur, Crop, 16:9).

### 🔹 Fase 2 — Legendas Dinâmicas, Kit Viral, Lote e Catálogo Inteligente
- **Legendas Dinâmicas Estilo CapCut / Alex Hormozi** (`core/subtitle_burner.py`):
  - Renderização nativa em ASS (`libass` do FFmpeg) com efeito karaokê palavra-a-palavra sincronizado.
  - Cores configuráveis (Destaque e Base), sliders de fonte e contorno nítido.
- **Kit de Publicação Viral com IA** (`core/analyzer.py`):
  - Título Magnético, Variações Alternativas, Legenda com CTA e Hashtags/SEO contextuais.
- **Exportação Padronizada com Nomenclatura Estrita** (`core/export_kit.py`):
  - Prefixos de 5 letras (`VLDSS`, `VRIRA`, `VFDBS`, `VCCFT`, `HOFHD`) + limite de 25 caracteres em palavras completas do título.
  - Criação da pasta `data/<video_id>/<PREFIXO>_<Palavras>/` com `.mp4`, `info_publicacao.txt`, `descricao.txt` e `tags.txt`.
- **Catálogo & Cache Inteligente por Minutagem e Formato** (`core/cuts_catalog.py`):
  - Rastreamento em `data/<video_id>/cuts_catalog.json` de múltiplas instâncias de enquadramento com abertura instantânea (0s).

### 🔹 Fase 3 — Retenção de Topo, Áudio Ducking & Integrações
- **🏷️ Headline / Título Fixo de Retenção no Topo (9:16)** (`core/headline_drawer.py`):
  - Presets (Amarelo, Red, Dark, Branco, Flutuante, Custom), margem de Safe Zone, IA focada em pensamento completo sem cortes no final e quebra harmoniosa em 2 linhas.
- **🎵 Trilha Sonora de Fundo & Audio Ducking Inteligente** (`core/audio_mixer.py`):
  - 4 trilhas royalty-free (`lofi_chill`, `dynamic_pulse`, `tension_suspense`, `inspirational_epic`) + suporte a MP3s customizados.
  - Atenuação fluida da música enquanto o orador fala via sidechain FFmpeg (`suave`, `medio`, `intenso`).
- **🔍 Efeitos Visuais de Retenção** (`core/retention_effects.py`):
  - Zoom Punch periódico sutil (1.08x) a cada ~8.5s e injeção de emojis contextuais nas legendas.
- **🌐 Exportação Direta & Integrações** (`core/integrations.py`):
  - Upload para o YouTube Shorts via OAuth2 e disparo estruturado para Webhooks (n8n/Make/Zapier).

### 🔹 Fase 4 — Polimento Visual, Thumbnails Multicamadas & Retenção Dinâmica
- **🖼️ Gerador Avançado de Capas / Thumbnails Multicamadas com 3 Variações (`core/thumbnail_generator.py`)**:
  - Extração do frame mais expressivo via nitidez Laplaciana + MediaPipe BlazeFace.
  - Isolamento de sujeito por IA via `Rembg` (modelo U2-Net) + realce de micro-contraste adaptativo local `OpenCV CLAHE` + Unsharp Mask nos olhos e feições.
  - Suporte total a **16:9 Full HD (1920x1080)** para YouTube e **9:16 Vertical (1080x1920)** para Shorts/Reels.
  - **Geração Automática de 3 Variações Estilizadas por Corte**:
    1. `thumbnail_1.jpg`: **⚡ Impacto Neon (Glow)** (Fundo desfocado com vinheta escura + Orador isolado com Glow Neon + Caixa de alto contraste).
    2. `thumbnail_2.jpg`: **✨ Clean Focus (Sombra 3D)** (Fundo bokeh suave + Orador com sombra projetada + Tipografia com stroke grosso e sombra 3D sem caixa).
    3. `thumbnail_3.jpg`: **🎬 Moldura Dinâmica (HDR)** (Fundo com contraste/saturação elevados + Tarja translúcida moderna + Badge de destaque).
  - **Seletor Interativo de Capas no Streamlit (`app.py`)**: Mini-galeria com prévia das 3 variações e botão *"⭐ Definir como Principal"* para alternar a capa oficial (`thumbnail.jpg`) instantaneamente na **Seção 3** e na **Galeria (Seção 4)**.
- **⏳ Barra de Progresso Animada de Retenção (Dynamic Progress Bar)**:
  - Linha fluida no rodapé do vídeo animada dinamicamente quadro a quadro via `overlay` do FFmpeg (`-w + w*(t/duration)`), progredindo de 0% a 100% com cores customizáveis (Vermelho, Amarelo, Ciano, Branco, Verde).
- **📌 Banner de Chamada / Lower Third Dinâmico (Engagement Callout)**:
  - Aparição elegante nos últimos 4-5 segundos provocando engajamento (*"💬 O que você acha? Comente!"*, *"🔔 Siga para mais cortes diários"*) em ASS com contorno de alto contraste (`BorderStyle=1`), sombra suave e fade `\fad(300,300)`.
- **🎯 Zoom de Ênfase no Clímax & Zoom Punch**:
  - Zoom dinâmico via camadas `scale + crop + overlay` condicional no FFmpeg para pulsos periódicos de retenção e aproximação dramática na punchline final.
- **✂️ Ferramenta Integrada de Edição Rápida & Ajuste Fino (`core/quick_editor.py`)**:
  - **Aparar Início e Fim (Trim)**: Ajuste milimétrico de pontos de corte com prévia visual dos frames inicial e final no navegador.
  - **Remover Trecho do Meio (Snip & Merge)**: Eliminação de gafes, silêncios ou tosses com junção contínua e sem emendas de áudio e vídeo via filtros FFmpeg concat.
  - Disponível instantaneamente no editor de cortes ativos e em todos os cards da galeria de cortes gerados.
- **🎛️ Controles em Massa & Modo Vídeo Normal (16:9)**:
  - Controles de *Marcar Tudo*, *Desmarcar Tudo* e *Inverter Seleção* em Séries e Ganchos Virais, com travas de segurança para desabilitar efeitos verticais de Shorts em vídeos longos 16:9.
- **🧪 Suíte de 35 Testes Unitários Automatizados (`tests/`)**:
  - 100% de aprovação contínua validando toda a suíte do `core/` via `pytest`.

---

## 🔮 Roadmap de Evolução Futura

### 🚀 Fase 5 — Sound FX (SFX) Inteligentes, B-Roll / Overlays de Contexto & Refinamento Visual (Médio a Avançado)
*Foco: Imersão sonora dinâmica, quebra de padrão visual com materiais visuais de apoio e aperfeiçoamento fino de capas e zooms.*

1. **🔊 Biblioteca de Efeitos Sonoros Inteligentes (SFX Engine)** (`core/sfx_manager.py`):
   - Inserção de efeitos sonoros curtos sincronizados: *Whoosh* no Zoom Punch, *Pop/Ka-ching* ao surgir emojis de dinheiro, *Boom/Alerta* em momentos de tensão.
   - Seleção automática da trilha sonora com base na análise de tom do Ollama (Polêmico $\to$ Tensão, Motivacional $\to$ Épico, Aula $\to$ Lo-Fi).
2. **🎬 B-Roll Inteligente & Split Screen Híbrido** (`core/broll_engine.py`):
   - Detecção de entidades e tópicos visuais na fala (nomes de pessoas, notícias, dados, gráficos).
   - Inserção de imagens/vídeos de apoio na metade superior do Split Screen ou em overlays curtos de 2 a 3 segundos (cutaways).
3. **🎨 Aperfeiçoamento de Capas 9:16 & Zooms de Retenção**:
   - Refinamento de presets visuais de capas, templates e ajustes finos de transição de zoom.

---

### 🚀 Fase 6 — Automação Total, Agendamento e Pipeline Sem Supervisão (Avançado)
*Foco: Escala de publicação autônoma em canais e redes sociais.*

1. **📅 Fila de Agendamento Automático de Postagens**:
   - Agendamento de publicações com cronograma e espaçamento de horários pré-definido via YouTube Data API v3 e Webhooks.
2. **🤖 Modo Fábrica 100% Autônomo (Zero-Touch Batch)**:
   - Processamento de ponta a ponta a partir de uma lista de URLs do YouTube: download $\to$ análise $\to$ recorte multi-formato $\to$ empacotamento $\to$ disparo sem intervenção manual.

---

### 🎯 Diretrizes & Regras do Projeto
1. **Documento Mestre Vivo**: `Fábrica de Cortes.md` é a base viva do projeto e deve ser mantida atualizada com novas decisões.
2. **Regra de Git**: `git commit` normalmente durante o desenvolvimento, mas **`git push` SOMENTE quando o usuário solicitar explicitamente.**
3. **Ambiente**: Python em Windows com venv em `d:\Repository\shorcut-factory\venv`. Executar comandos com caminhos absolutos para o python/pip do venv.

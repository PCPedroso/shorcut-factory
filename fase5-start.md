# 📋 Prompt de Contexto — Início da Fase 5: ViralCut / Fábrica de Cortes

Copie todo o conteúdo abaixo para abrir o novo chat da Fase 5:

---

## 🚀 Prompt de Contexto — ViralCut: Fábrica de Cortes (Fase 5)

**Olá! Vamos dar início ao desenvolvimento da Fase 5 da aplicação ViralCut — Fábrica de Cortes.**

### 📁 Repositório
`d:\Repository\shorcut-factory` → GitHub: `PCPedroso/shorcut-factory`

---

### ✅ Fases Anteriores Concluídas e Sincronizadas no GitHub

O projeto possui quatro fases 100% concluídas, testadas com 31 testes unitários automatizados (`pytest`) e sincronizadas na branch `main`:

#### 🔹 Fase 1 — Estrutura Base, Análise e Enquadramentos 9:16
- **Interface Streamlit** modular (`app.py`).
- **Biblioteca de Vídeos & Download** via `yt-dlp` em até 1080p Full HD com persistência de metadados e canal.
- **Transcrição** acelerada por GPU CUDA via `faster-whisper` e fallback automático para ASR do YouTube.
- **Inteligência Temática Dual** com Ollama (Llama 3 local):
  - Modo `🎙️ Entrevistas & Sabatinas`: Detecção de turnos Q&A com timestamp exato `[INÍCIO → FIM]`.
  - Modo `🧠 Temático / Monólogos`: Mapeamento de transições de tópicos e ganchos contínuos (10+ min).
- **Ganchos Virais (Shorts / Reels)** estruturados sob as **6 Regras de Ouro Editoriais** (Clean Entry, Clean Exit, Autonomia Semântica, Tipologia, Filtro Anti-Vazamento e Janela 20s–75s).
- **5 Modos de Enquadramento de Vídeo** em `core/video_processor.py`:
  - `📱 9:16 Layout Dividido (Split Screen)` com **Transição Dinâmica Inteligente (Auto-Switch)** via MediaPipe.
  - `📱 9:16 Auto-Reframing` com Face Tracking inteligente e Target Lock.
  - `📱 9:16 Blur` com Auto-Zoom e Pan suave.
  - `📱 9:16 Center Crop`.
  - `💻 16:9 Full HD`.

#### 🔹 Fase 2 — Legendas Dinâmicas, Kit Viral, Lote e Catálogo Inteligente
- **Legendas Dinâmicas Estilo CapCut / Alex Hormozi** (`core/subtitle_burner.py`):
  - Renderização nativa em ASS (`libass` do FFmpeg) com efeito karaokê palavra-a-palavra sincronizado.
  - Cores configuráveis (Destaque e Base), sliders de fonte (40px a 160px) e contorno nítido.
- **Kit de Publicação Viral com IA** (`core/analyzer.py`):
  - Título Magnético, Variações Alternativas, Legenda com CTA e Hashtags/SEO contextuais.
- **Exportação Padronizada com Nomenclatura Estrita** (`core/export_kit.py`):
  - Prefixos de 5 letras (`VLDSS`, `VRIRA`, `VFDBS`, `VCCFT`, `HOFHD`) + limite de 25 caracteres em palavras completas do título.
  - Criação da pasta `data/<video_id>/<PREFIXO>_<Palavras>/` com `.mp4`, `info_publicacao.txt`, `descricao.txt` e `tags.txt`.
- **Catálogo & Cache Inteligente por Minutagem e Formato** (`core/cuts_catalog.py`):
  - Rastreamento em `data/<video_id>/cuts_catalog.json` de múltiplas instâncias de enquadramento com abertura instantânea (0s).
- **Esteira de Renderização em Lote (Batch Pipeline)** (`core/batch_processor.py`):
  - Seleção por checkboxes unificados, botão *"Selecionar Todos para Lote"*, barra de progresso visual e Smart Skip.
- **Galeria de Cortes Produzidos (Seção 4)**:
  - Players verticais 9:16 compactos, download direto e exclusão granular.

#### 🔹 Fase 3 — Retenção de Topo, Áudio Ducking & Integrações
- **🏷️ Headline / Título Fixo de Retenção no Topo (9:16)** (`core/headline_drawer.py`):
  - Presets (Amarelo, Red, Dark, Branco, Flutuante, Custom), margem de Safe Zone, IA focada em pensamento completo sem cortes no final e quebra harmoniosa em 2 linhas.
- **🎵 Trilha Sonora de Fundo & Audio Ducking Inteligente** (`core/audio_mixer.py`):
  - 4 trilhas royalty-free (`lofi_chill`, `dynamic_pulse`, `tension_suspense`, `inspirational_epic`) + suporte a MP3s customizados.
  - Atenuação fluida da música enquanto o orador fala via sidechain FFmpeg (`suave`, `medio`, `intenso`).
- **🔍 Efeitos Visuais de Retenção** (`core/retention_effects.py`):
  - Zoom Punch periódico sutil (1.08x) a cada ~8.5s e injeção de emojis contextuais nas legendas.
- **🌐 Exportação Direta & Integrações** (`core/integrations.py`):
  - Upload para o YouTube Shorts via OAuth2 e disparo estruturado para Webhooks (n8n/Make/Zapier).

#### 🔹 Fase 4 — Polimento Visual, Thumbnails Inteligentes & Retenção Dinâmica
- **🖼️ Gerador Automático de Capas / Thumbnails 9:16 (`core/thumbnail_generator.py`)**:
  - Extração do frame mais expressivo via nitidez Laplaciana + MediaPipe BlazeFace e overlay de Headline `Montserrat-ExtraBold`.
  - Salvamento automático de `thumbnail.jpg` na pasta do corte (`export_kit.py`), catálogo (`cuts_catalog.json`) e botões de download nas Seções 3 e 4.
- **⏳ Barra de Progresso Animada de Retenção (Dynamic Progress Bar)**:
  - Linha fluida no rodapé animada dinamicamente quadro a quadro (0% a 100%) via `overlay` per-frame no FFmpeg com cores configuráveis.
- **📌 Banner de Chamada / Lower Third Dinâmico (Engagement Callout)**:
  - Banner elegante nos últimos 4-5 segundos (*"💬 Comente" / "🔔 Siga"*) em ASS com contorno de alto contraste (`BorderStyle=1`), sombra suave e fade `\fad(300,300)`.
- **🎯 Zoom de Ênfase no Clímax & Zoom Punch**:
  - Zoom dinâmico via camadas `scale + crop + overlay` condicional no FFmpeg para pulsos de retenção e punchline final.

---

### 🚀 Fase 5 — ESCOPO DE IMPLEMENTAÇÃO
**Objetivo: Sound FX (SFX) Inteligentes, B-Roll / Overlays de Contexto & Refinamento Visual (Médio a Avançado)**

1. **🔊 Biblioteca de Efeitos Sonoros Inteligentes (SFX Engine) (`core/sfx_manager.py`)**:
   - Inserção de micro-efeitos sonoros curtos e sincronizados na esteira de áudio:
     - *Whoosh*: sincronizado com as transições de Zoom Punch e Climax Zoom.
     - *Pop / Ka-ching / Ding*: sincronizado ao surgirem palavras com emojis destacados nas legendas (dinheiro, fogo, alerta, etc.).
     - *Boom / Tensão*: no início de punchlines ou momentos de alta intensidade.
   - Seleção inteligente e automática da trilha sonora com base na análise de tom do Ollama (Polêmico $\to$ Tensão, Motivacional $\to$ Épico, Conversa $\to$ Lo-Fi).

2. **🎬 B-Roll Inteligente & Split Screen Híbrido (`core/broll_engine.py`)**:
   - Detecção de entidades e tópicos visuais na fala (nomes de personalidades, dados, gráficos, manchetes, termos conceituais).
   - Inserção de imagens/vídeos de apoio contextuais na metade superior do Split Screen ou em overlays curtos de 2 a 3 segundos (cutaways de retenção).

3. **🎨 Aperfeiçoamento Fino de Capas 9:16 & Zooms de Retenção**:
   - Refinamento adicional dos presets e templates visuais de capas/thumbnails.
   - Polimento na curva de aceleração/transição dos zooms de impacto.

---

### 🎯 Diretrizes & Regras do Projeto
1. **Documento Mestre Vivo**: `Fábrica de Cortes.md` é a base viva do projeto e deve ser mantida atualizada com novas decisões.
2. **Regra de Git**: `git commit` normalmente durante o desenvolvimento, mas **`git push` SOMENTE quando o usuário solicitar explicitamente.**
3. **Ambiente**: Python em Windows com venv em `d:\Repository\shorcut-factory\venv`. Executar comandos com caminhos absolutos para o python/pip do venv.

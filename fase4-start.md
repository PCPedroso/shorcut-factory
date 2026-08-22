# 📋 Prompt de Contexto — Início da Fase 4: ViralCut / Fábrica de Cortes

Copie todo o conteúdo abaixo para abrir o novo chat da Fase 4:

---

## 🚀 Prompt de Contexto — ViralCut: Fábrica de Cortes (Fase 4)

**Olá! Vamos dar início ao desenvolvimento da Fase 4 da aplicação ViralCut — Fábrica de Cortes.**

### 📁 Repositório
`d:\Repository\shorcut-factory` → GitHub: `PCPedroso/shorcut-factory`

---

### ✅ Fases Anteriores Concluídas e Sincronizadas no GitHub

O projeto possui três fases 100% concluídas, testadas e sincronizadas na branch `main`:

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
- **🧪 Suíte de 24 Testes Unitários Automatizados (`tests/`)**:
  - 100% de aprovação contínua validando toda a suíte do `core/` via `pytest`.

---

### 🚀 Fase 4 — ESCOPO DE IMPLEMENTAÇÃO
**Objetivo: Polimento Visual, Thumbnails Inteligentes & Retenção Dinâmica (Simples a Médio)**

1. **🖼️ Gerador Automático de Capas / Thumbnails 9:16 (`core/thumbnail_generator.py`)**:
   - Detecção do frame mais expressivo do corte via MediaPipe (olhos abertos, expressão facial nítida).
   - Composição automática com a Headline magnética de topo e salvamento de `thumbnail.jpg` dentro da pasta do corte (`export_kit.py`).
   - Prévia da miniatura e botão de download na Seção 3 e na Galeria de Cortes.
2. **⏳ Barra de Progresso Animada de Retenção (Dynamic Progress Bar)**:
   - Linha minimalista e personalizável no rodapé do vídeo (via FFmpeg) indicando o progresso do corte para reter o espectador até o último segundo.
3. **📌 Banner de Chamada / Lower Third Dinâmico (Engagement Callout)**:
   - Aparição sutil e elegante nos últimos 4-5 segundos provocando engajamento (*"💬 O que você acha? Comente!"* / *"🔔 Siga para mais cortes diários"*).
4. **🎯 Zoom de Ênfase no Clímax (Climax Punchline Zoom)**:
   - Aplicação de zoom dramático e focado no rosto do orador no exato segundo da frase de impacto/punchline final.

---

### 🎯 Diretrizes & Regras do Projeto
1. **Documento Mestre Vivo**: `Fábrica de Cortes.md` é a base viva do projeto e deve ser mantida atualizada com novas decisões.
2. **Regra de Git**: `git commit` normalmente durante o desenvolvimento, mas **`git push` SOMENTE quando o usuário solicitar explicitamente.**
3. **Ambiente**: Python em Windows com venv em `d:\Repository\shorcut-factory\venv`. Executar comandos com caminhos absolutos para o python/pip do venv.

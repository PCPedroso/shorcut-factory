# 📋 Prompt de Contexto — Início da Fase 3: ViralCut / Fábrica de Cortes

Copie todo o conteúdo abaixo para abrir o novo chat da Fase 3:

---

## 🚀 Prompt de Contexto — ViralCut: Fábrica de Cortes (Fase 3)

**Olá! Vamos continuar o desenvolvimento da aplicação ViralCut — Fábrica de Cortes.**

### 📁 Repositório
`d:\Repository\shorcut-factory` → GitHub: `PCPedroso/shorcut-factory`

---

### ✅ Fases Anteriores Concluídas e Sincronizadas no GitHub

O projeto possui duas fases 100% concluídas, testadas e commitadas:

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
  - Renderização nativa em ASS (`libass` do FFmpeg) com efeito karaokê palavra-a-palavra sincronizado com Whisper/YouTube.
  - Cores configuráveis (Destaque e Base), sliders de fonte (40px a 160px) e contorno nítido.
  - Integração perfeita com todos os 5 enquadramentos de vídeo.
- **Kit de Publicação Viral com IA** (`core/analyzer.py`):
  - Geração automática de Título Magnético, 2 Variações Alternativas, Legenda com CTA e Hashtags/SEO contextuais.
- **Exportação Padronizada com Nomenclatura Estrita** (`core/export_kit.py`):
  - Prefixos de 5 letras (`VLDSS`, `VRIRA`, `VFDBS`, `VCCFT`, `HOFHD`) + limite de 25 caracteres em palavras completas do título.
  - Criação da pasta `data/<video_id>/<PREFIXO>_<Palavras>/` com `.mp4`, `info_publicacao.txt`, `descricao.txt` e `tags.txt`.
- **Catálogo & Cache Inteligente por Minutagem e Formato** (`core/cuts_catalog.py`):
  - Rastreamento em `data/<video_id>/cuts_catalog.json` de múltiplas instâncias de enquadramento para a mesma minutagem com abertura em 0s.
- **Esteira de Renderização em Lote (Batch Pipeline)** (`core/batch_processor.py`):
  - Seleção por checkboxes unificados e botão *"Selecionar Todos para Lote"*, com barra de progresso visual e Smart Skip de cortes já gerados.
- **Galeria de Cortes Produzidos (Seção 4)**:
  - Visualização de todas as minutagens com players verticais 9:16 compactos e elegantes.
  - Botão de download direto do MP4 e botão de exclusão individual com confirmação granular (*Apenas Vídeo* vs *Pasta Completa*).
- **Persistência de Configurações** (`data/app_settings.json` via `core/config_manager.py`).

---

### 🚀 Fase 3 — A IMPLEMENTAR agora

Objetivo: Elevar o nível de **retenção visual, dinamismo sonoro e automação de publicação** dos cortes gerados:

1. **🏷️ Headline / Título Fixo de Retenção no Topo (9:16)**:
   - Inserção de caixa de chamada magnética superior (estilo headline viral de retenção) com fundo contrastante customizável (amarelo, vermelho, preto, gradiente), fonte bold e posicionamento que não colide com rostos ou legendas.
2. **🎵 Trilha Sonora de Fundo & Audio Ducking Inteligente**:
   - Biblioteca de trilhas sonoras de fundo livres de direitos (Lo-Fi, Tensão, Inspiracional, Dinâmica).
   - Efeito de **Audio Ducking via FFmpeg**: a música diminui suavemente de volume enquanto a pessoa fala e sobe sutilmente nas pausas/silêncios.
3. **🖼️ B-Roll / Overlays Visuais & Efeitos de Retenção (Zoom Punch / Emojis)**:
   - Efeito de *Zoom Punch / Jump Cut suave* em palavras de alta ênfase para quebrar monotonia visual no feed do TikTok/Reels/Shorts.
   - Inserção automática de emojis ou stickers contextuais sobre as falas.
4. **🌐 Exportação Direta & Integrações**:
   - Upload de rascunhos direto para o YouTube Shorts via YouTube Data API v3 ou exportação em lote para Google Drive / Webhooks.

---

### 🎯 Diretrizes & Regras do Projeto
1. **Documento Mestre Vivo**: `Fábrica de Cortes.md` é a base viva do projeto e deve ser mantida atualizada com novas decisões.
2. **Regra de Git**: `git commit` normalmente durante o desenvolvimento, mas **`git push` SOMENTE quando o usuário solicitar explicitamente.**
3. **Ambiente**: Python em Windows com venv em `d:\Repository\shorcut-factory\venv`. Executar comandos com caminhos absolutos para o python/pip do venv.

---

**Pode analisar o repositório e iniciar o planejamento e implementação dos recursos da Fase 3!**

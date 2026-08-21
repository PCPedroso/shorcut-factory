# 📋 Prompt de Contexto — Início da Fase 3: ViralCut / Fábrica de Cortes

Copie o conteúdo abaixo e utilize na abertura do novo chat:

---

## 🚀 Prompt de Contexto — ViralCut: Fábrica de Cortes (Fase 3)

**Olá! Vamos continuar o desenvolvimento da aplicação ViralCut — Fábrica de Cortes.**

### 📁 Repositório
`d:\Repository\shorcut-factory` → GitHub: `PCPedroso/shorcut-factory`

---

### ✅ Fases Anteriores Concluídas e Sincronizadas no GitHub

#### 🔹 Fase 1 — Estrutura Base, Análise e Enquadramentos 9:16
- **Interface Streamlit** modular e moderna (`app.py`).
- **Biblioteca de Vídeos & Download** via `yt-dlp` em até 1080p Full HD com persistência de metadados.
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
  - Criação da pasta `data/<video_id>/<PREFIXO>_<Palavras>/` contendo:
    - 🎬 `[PREFIXO]_[Palavras].mp4`
    - 📌 `info_publicacao.txt` (incluindo dados do vídeo original: título, canal, lançamento e link)
    - 📝 `descricao.txt`
    - 🏷️ `tags.txt`
- **Catálogo & Cache Inteligente por Minutagem e Formato** (`core/cuts_catalog.py`):
  - Rastreamento em `data/<video_id>/cuts_catalog.json` de múltiplas instâncias de enquadramento para a mesma minutagem.
  - Detecção imediata de cortes existentes com reprodução instantânea (0s de espera) e botão de atualização de textos do kit sem re-renderizar vídeo.
- **Esteira de Renderização em Lote (Batch Pipeline)** (`core/batch_processor.py`):
  - Seleção por checkboxes individuais e botão *"Selecionar Todos para Lote"* na aba de Pequenos Cortes.
  - Painel de controle da fila em lote com barra de progresso visual em tempo real e Smart Skip (ignora cortes já existentes a menos que forçado).
- **Galeria de Cortes Produzidos (Seção 4)**:
  - Visualização de todas as minutagens com players verticais 9:16 compactos e elegantes lado a lado.
  - Botão de download direto do MP4 e botão de exclusão individual com confirmação granular (*Apenas Vídeo* vs *Pasta Completa*).
- **Persistência de Configurações** (`data/app_settings.json` via `core/config_manager.py`).

---

### 🎯 Diretrizes & Regras do Projeto
1. **Regra de Git**: `git commit` normalmente durante o desenvolvimento, mas **`git push` SOMENTE quando o usuário solicitar explicitamente.**
2. **Ambiente**: Python em Windows com venv em `d:\Repository\shorcut-factory\venv`. Executar comandos com caminhos absolutos para o python/pip do venv.

---

**Pode analisar o repositório e aguardar as instruções para os objetivos da Fase 3!**

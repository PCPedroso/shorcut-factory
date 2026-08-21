Viewed F%C3%A1brica%20de%20Cortes.md:1-105

Aqui está o prompt de contexto completo para você usar na abertura do novo chat:

---

## 📋 Prompt de Contexto — Fase 2: ViralCut / Fábrica de Cortes

---

**Olá! Vamos continuar o desenvolvimento da aplicação ViralCut — Fábrica de Cortes.**

### 📁 Repositório
`d:\Repository\shorcut-factory` → GitHub: `PCPedroso/shorcut-factory`

---

### ✅ Fase 1 — Concluída e no GitHub

A Fase 1 foi 100% concluída. O que foi implementado:

- **Interface Streamlit** (`app.py`) com 3 seções principais
- **Biblioteca de Vídeos** com título, data de lançamento do YouTube, reabertura instantânea e exclusão
- **Transcrição automática** com `faster-whisper` (GPU CUDA) + cache em `data/<video_id>/`
- **Análise semântica dual** via Ollama (Llama 3 local):
  - Modo `🎙️ Entrevistas & Sabatinas`: Detecção de turnos Q&A com timestamp exato `[INÍCIO → FIM]`
  - Modo `🧠 Temático / Monólogos`: Mapeamento semântico por transição de assunto
- **Ganchos Virais (Shorts)** com micro-cortes respeitando as **6 Regras de Ouro Editoriais** (Clean Entry, Clean Exit, Autonomia Semântica, Tipologia, Filtro Anti-Vazamento, Janela de Retenção 20s–75s)
- **Persistência modular por ação** (pautas, series, shorts e steps salvos em JSONs separados por `video_id`)
- **Fábrica de Cortes (Seção 3)** com 5 modos de enquadramento:
  - `📱 9:16 Layout Dividido (Split Screen)` — **Estilo Podpah/Flow** — `NEW`
    - **Transição Dinâmica Inteligente (Auto-Switch)**: Se 2+ pessoas visíveis → Split Screen. Se câmera fecha em close-up de 1 pessoa → Full Screen 9:16 automático. Detecção via MediaPipe frame a frame com filtro de histerese.
    - Presets de distribuição: Entrevistador(es) no Topo / Entrevistado na Base (e inverso)
    - Zoom configurável, linha divisória customizável, botão de prévia instantânea
  - `📱 9:16 Auto-Reframing` com Face Tracking (Target Lock + Seletor de Alvo)
  - `📱 9:16 Blur` com Auto-Zoom Inteligente + prévia
  - `📱 9:16 Center Crop`
  - `💻 16:9 Full HD`

---

### 🚀 Fase 2 — A IMPLEMENTAR agora

**Legendas Dinâmicas no Vídeo (Estilo CapCut / Alex Hormozi)**

Objetivo: Queimar legendas sincronizadas **palavra por palavra** diretamente no vídeo renderizado, com destaque visual animado (estilo reels virais). As especificações são:

1. **Sincronização palavra-a-palavra** com os timestamps do Whisper (já disponíveis em `data/<video_id>/transcript.json`)
2. **Highlight dinâmico**: A palavra atual em destaque (cor vibrante, negrito, talvez leve escala) enquanto as demais palavras da mesma frase ficam visíveis mas mais apagadas (opacidade reduzida)
3. **Posicionamento**: Legendas no terço inferior da tela 9:16 (compatível com todos os 5 modos de enquadramento já existentes)
4. **Estilo visual premium**: Fontes modernas (ex: `Montserrat Bold`, `Inter ExtraBold`), sombra suave ou contorno para legibilidade em qualquer fundo
5. **Configurável via UI**: Ativar/desativar legendas, escolha de cor do highlight, tamanho da fonte
6. **Integrado ao `cut_video` em `core/video_processor.py`**: Deve funcionar para todos os modos de aspect ratio (inclusive o 9:16_split com Dynamic Auto-Switch que usa pipeline frame-a-frame em `core/face_tracker.py`)

**Regra de Git**: `git commit` normalmente durante o desenvolvimento, mas **`git push` SOMENTE quando eu solicitar explicitamente.**

---

**Pode analisar o repositório e iniciar a implementação da Fase 2!**
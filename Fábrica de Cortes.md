# ViralCut — Fábrica de Cortes

## Objetivo

Automatizar a criação de cortes virais (curtos e médios) a partir de vídeos do YouTube, com foco em retenção real, integridade temática e esteira de múltiplos vídeos interligados.

---

## Stack Tecnológica

| Componente | Tecnologia |
|---|---|
| Linguagem | Python 3.10+ |
| Interface | Streamlit (Web UI Local) |
| Extração | `yt-dlp` (metadados, heatmap, download em até 1080p) |
| Transcrição | `faster-whisper` (GPU GTX 1650 via CUDA float32) |
| Inteligência Temática | `Ollama` (Llama 3 local, mistral, qwen2.5) |
| Processamento de Vídeo | `FFmpeg` + `MoviePy` (corte direto por stream copy) |

---

## Arquitetura de Módulos

```
shorcut-factory/
├── app.py                  # Interface Streamlit principal com cards interativos
├── core/
│   ├── extractor.py        # yt-dlp: metadados + download de áudio
│   ├── transcriber.py      # faster-whisper: transcrição com GPU CUDA
│   ├── analyzer.py         # Ollama: análise semântica + encadeamento de ganchos (>=10 min)
│   └── video_processor.py  # FFmpeg/MoviePy: download HD (1080p/720p) e corte de vídeo
├── data/
│   └── <video_id>/
│       ├── audio.mp3       # Cache do áudio extraído
│       ├── transcript.json # Cache da transcrição Whisper com timestamps
│       └── video_full.mp4  # Cache do vídeo completo em alta qualidade
└── requirements.txt
```

---

## Estratégia de Inteligência Temática & Encadeamento

### 1. Blocos Semânticos para YouTube (Mínimo de 10 minutos)
* **Identificação Semântica**: A IA analisa as transições reais de assunto e perguntas na transcrição com timestamps ancorados nos chunks do Whisper.
* **Regra de 10+ Minutos & Gancho de Continuação (Cliffhanger)**:
  - Se um assunto durar **>= 10 minutos**, o corte conclui no fechamento natural daquele assunto.
  - Se um assunto durar **< 10 minutos** (ex: 6 ou 7 min), o algoritmo **"invade" o início do próximo assunto** até atingir 10+ minutos.
  - O trecho invadido atua como **Gancho (Teaser)** para o próximo vídeo da série.
  - A interface marca automaticamente:
    * `Vídeo 1`: *Tema A (com Gancho para Tema B)*
    * `Vídeo 2`: *Tema B (com Gancho para Tema C ou Conclusão)*

### 2. Ganchos Virais para Shorts / TikTok (< 60 segundos)
* Identificação de frases contundentes, momentos polêmicos ou respostas de alto impacto com duração ideal de 45 a 60 segundos.

---

## 📐 Regras de Ouro Editoriais para Cortes e Micro-Cortes (Shorts / Reels)

Para garantir que todos os cortes gerados pela IA possuam padrão profissional de edição humana (com início, meio e fim perfeitos), a aplicação segue estritamente as seguintes 6 diretrizes:

### 1. 🎬 Ponto de Entrada Limpo (*Clean Entry & Audio Snapping*)
* **Regra**: O corte deve iniciar no milissegundo exato da primeira palavra falada (com margem de **100ms a 150ms** de respiro inicial).
* **Critério**:
  * Em cortes com pergunta: inicia na saudação ou pergunta do jornalista (`"Simone, boa noite..."` ou `"Candidato..."`).
  * Em declarações diretas: inicia na primeira frase completa da resposta do entrevistado, sem cortar a primeira sílaba.

### 2. 🏁 Ponto de Saída com Conclusão e Respiro (*Punchline & Breath-out*)
* **Regra**: O corte termina após o fechamento da última oração do raciocínio, mantendo **200ms a 300ms** de pausa natural antes do corte.
* **Proibição Estrita**: É terminantemente proibido deixar "vazar" o início da pergunta ou tema seguinte (ex: cortar antes do repórter começar a próxima pauta).

### 3. 🧠 Autonomia Semântica (*Standalone Comprehensibility*)
* **Regra**: O espectador no feed do Instagram, TikTok ou YouTube Shorts deve compreender 100% da mensagem sem precisar ter assistido à entrevista completa.
* **Critério**: Cortes não podem começar com pronomes anafóricos soltos sem antecedente (ex: *"Como eu disse antes a respeito dele..."*). Caso falte contexto, a pergunta do jornalista deve ser obrigatoriamente incluída.

### 4. 🗂️ Tipologia dos Pequenos Cortes
A esteira classifica os cortes em 3 formatos:
* **🏷️ [Q&A] Pergunta & Resposta Completa [35s a 80s]**: Pergunta rápida do jornalista $\to$ Resposta estruturada $\to$ Conclusão.
* **🏷️ [Punchline] Declaração / Tese de Impacto [25s a 55s]**: Foco direto na frase mais contundente do entrevistado.
* **🏷️ [Debate] Confronto & Réplica Rápida [35s a 70s]**: Contestação do entrevistador $\to$ Argumento forte do entrevistado.

### 5. 🚫 Filtro Anti-Vazamento e Isolamento de Pautas
* **Regra**: Todo corte é estritamente limitado aos limites daquela pauta. Assuntos diferentes nunca são misturados, a não ser quando há conclusão explícita de raciocínio prévio.

### 6. ⏱️ Janela Temporal de Retenção
* **Duração Mínima**: `20 segundos` (tempo mínimo para desenvolver uma ideia completa).
* **Duração Máxima para Shorts/Reels**: `60 a 75 segundos` (janela ideal de 100% de retenção).

---

## Fluxo da Aplicação

1. **Entrada da URL**: Informa o link do YouTube.
2. **Download & Transcrição Inteligente (com Cache)**:
   - Metadados oficiais (Título, Data de Lançamento no YouTube, Duração) são registrados na Biblioteca.
   - Transcrição oficial do YouTube e áudio são salvos em `data/<video_id>/` para reuso instantâneo.
3. **Seleção de Cortes & Estratégias**:
   - **Modo Entrevistas, Sabatinas & Podcasts**: Identificação de turnos de diálogo Q&A no segundo exato `[INÍCIO → FIM]`.
   - **Modo Temático / Aulas & Monólogos**: Mapeamento contínuo de transições de tópicos.
   - **Modo Ganchos Virais (Shorts / Reels)**: Geração de micro-cortes respeitando as 6 Regras de Ouro.
4. **Fábrica de Cortes**:
   - Enquadramentos 9:16 (Auto-Reframing com Face Tracking, Blur com Auto-Zoom, Center Crop) e 16:9 Full HD.
   - Renderização ultra-rápida via FFmpeg.

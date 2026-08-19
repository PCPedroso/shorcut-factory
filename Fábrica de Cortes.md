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

## Fluxo da Aplicação

1. **Entrada da URL**: Informa o link do YouTube.
2. **Download & Transcrição Inteligente (com Cache)**:
   - Áudio e Transcrição são salvos em `data/<video_id>/` para reuso instantâneo.
3. **Seleção de Cortes**:
   - **Aba Manual**: Navegação minuto a minuto por chunks.
   - **Aba IA (Llama 3)**: Apresenta os cortes semânticos estruturados em cards com duração, tags de gancho e botão direto de recorte.
4. **Fábrica de Cortes**:
   - Baixa o vídeo original em 1080p/720p (com cache local) e executa o corte ultra-rápido via FFmpeg.
   - Exibe o player de prévia e botão de download do arquivo `.mp4`.

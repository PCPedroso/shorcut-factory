# ViralCut — Fábrica de Cortes

## Objetivo

Automatizar a criação de cortes virais (curtos e médios) a partir de vídeos do YouTube, com foco em retenção real e integridade temática.

---

## Stack Tecnológica

| Componente | Tecnologia |
|---|---|
| Linguagem | Python 3.10+ |
| Interface | Streamlit (Web UI Local) |
| Extração | `yt-dlp` (metadados, heatmap, download) |
| Transcrição | `faster-whisper` (GPU GTX 1650 via CUDA float32) |
| Inteligência Temática | `Ollama` (Llama 3 local, ou mistral/qwen2.5) |
| Processamento de Vídeo | `FFmpeg` + `MoviePy` |

---

## Arquitetura de Módulos

```
shorcut-factory/
├── app.py                  # Interface Streamlit principal
├── core/
│   ├── extractor.py        # yt-dlp: metadados + download de áudio
│   ├── transcriber.py      # faster-whisper: transcrição com CUDA
│   ├── analyzer.py         # Ollama: análise temática em 2 fases
│   └── video_processor.py  # FFmpeg/MoviePy: download e corte de vídeo
├── data/
│   └── <video_id>/
│       ├── audio.mp3       # Cache do áudio (evita re-download)
│       ├── transcript.json # Cache da transcrição (evita re-transcrição)
│       └── video_full.mp4  # Cache do vídeo (evita re-download para corte)
└── requirements.txt
```

---

## Fluxo da Aplicação

### Fase 1 — Download & Transcrição (com cache)
1. Usuário cola a URL do YouTube
2. `extractor.py` busca metadados e baixa o áudio em `data/<id>/audio.mp3`
3. `transcriber.py` roda o Whisper na GPU e salva `data/<id>/transcript.json`
4. Se o cache já existir, pula as etapas anteriores diretamente

### Fase 2 — Análise Temática (IA em 2 chamadas)
A transcrição é agrupada em chunks de 1 minuto e enviada ao Ollama.

**Fase 2A — Identificação de temas (resposta em texto livre):**
> "Quais são os 3 a 5 principais temas discutidos nesta transcrição?"

O modelo responde livremente em PT-BR com uma lista numerada — sem formato rígido, o que maximiza a confiabilidade do llama3 8B.

**Fase 2B — Localização de timestamps (uma chamada por tema):**
> "Em que minuto começa e termina o tema X? Responda: START=HH:MM:SS END=HH:MM:SS"

Formato ultra-simples, dois tokens apenas. Regex extrai `START=` e `END=`.

**Fallback automático:** Se a IA não retornar timestamps válidos para um tema, o sistema divide o vídeo uniformemente entre os temas identificados (heurística proporcional).

### Fase 3 — Seleção de Cortes
- **Aba Manual:** O usuário seleciona "Chunk de Início" e "Chunk de Fim" numa lista de blocos de 1 minuto com prévia do texto
- **Aba IA:** Exibe a lista de cortes sugeridos pelo Ollama. O usuário seleciona um e clica "Usar este trecho"

### Fase 4 — Geração do Corte
1. `video_processor.py` baixa o vídeo completo em MP4 (cacheado)
2. FFmpeg recorta o trecho exato com os timestamps selecionados
3. O vídeo recortado é exibido na tela e disponibilizado para download

---

## Configurações (sidebar)

| Configuração | Opções | Padrão |
|---|---|---|
| Dispositivo Whisper | cpu / cuda | cpu |
| Modelo Whisper | tiny / small / medium / large-v3 | small |
| Modelo Ollama | llama3 / mistral / qwen2.5 / llama3.1 / gemma2 | llama3 |

> **Recomendação de modelos Ollama por qualidade:**
> 1. `qwen2.5` — melhor em seguir formatos e instruções (pull: ~5GB)
> 2. `mistral` — excelente em texto estruturado (pull: ~4GB)  
> 3. `llama3` — padrão instalado, funcional com a abordagem de 2 fases

---

## Correções Técnicas Conhecidas

### GTX 1650 (4GB VRAM sem Tensor Cores)
- `compute_type` definido como `float32` em vez de `float16`
- DLLs CUDA injetadas via `sys.path` dinâmico no `transcriber.py`

### Ollama Llama 3 8B — Limitações de Format Following
- Modelos 8B não seguem schemas JSON complexos de forma confiável
- **Solução:** Abordagem de 2 fases separando identificação de temas (texto livre) da localização de timestamps (2 tokens)
- **Fallback:** Heurística proporcional quando timestamps da IA são inválidos

---

## Diferenciais Estratégicos (Roadmap)

1. **Filtro de Segurança:** Detecção de termos sensíveis para evitar shadowban
2. **Preservação de Pausas Intelectuais:** Diferenciação de silêncio vazio vs. reflexivo
3. **Blocos Semânticos:** Cortes baseados em unidade de sentido, não apenas em tempo
4. **Score de Retenção:** Integração com heatmap do YouTube para priorizar picos de audiência

# ViralCut — Fábrica de Cortes

## 🎯 Objetivo

Automatizar a esteira completa de criação, inteligência editorial, recorte e empacotamento de cortes virais (Shorts, Reels, TikTok e vídeos médios de YouTube) a partir de links do YouTube, com foco em retenção máxima, coerência semântica e padrão profissional de edição humana.

---

## 🛠️ Stack Tecnológica

| Componente | Tecnologia | Finalidade |
|---|---|---|
| **Linguagem** | Python 3.10+ | Núcleo de processamento e automação |
| **Interface** | Streamlit | Web UI interativa local e intuitiva |
| **Extração & Catálogo** | `yt-dlp` | Download de áudio, metadados oficiais e vídeo em 1080p |
| **Transcrição** | `faster-whisper` + ASR YouTube | Transcrição palavra por palavra acelerada por GPU CUDA |
| **Visão Computacional** | `MediaPipe` + `OpenCV` | Face tracking, Target Lock e transição dinâmica Split/Full Screen |
| **Inteligência Editorial** | `Ollama` (Llama 3 local / Qwen) | Análise semântica, detecção Q&A e Kit Viral de Publicação |
| **Processamento de Vídeo** | `FFmpeg` (com `libass`) | Recorte, filtros complexos de vídeo e queima de legendas nativas |
| **Configurações & Cache** | JSON local estruturado | Persistência contínua de preferências e catálogo multi-formato |

---

## 🏗️ Arquitetura de Módulos & Estrutura de Diretórios

```
shorcut-factory/
├── app.py                     # Interface Web Streamlit (4 seções + Integrações)
├── assets/
│   └── audio/                 # Trilhas sonoras royalty-free categorizadas (.wav / .mp3)
├── core/
│   ├── extractor.py           # Extração de áudio, canais e metadados via yt-dlp
│   ├── transcriber.py         # Transcrição faster-whisper (CUDA) + fallback ASR YouTube
│   ├── analyzer.py            # Análise Q&A/Temática e geração do Kit Viral com IA
│   ├── video_processor.py     # Pipeline FFmpeg para os 5 formatos de enquadramento + efeitos
│   ├── face_tracker.py        # Detecção facial MediaPipe e Split Screen Auto-Switch
│   ├── subtitle_burner.py     # Geração de legendas dinâmicas em ASS + Headlines + Emojis
│   ├── headline_drawer.py     # Estilização de Headlines magnéticas de topo (Amarelo, Red, Dark, Custom)
│   ├── audio_mixer.py         # Mixagem de áudio com Ducking dinâmico via sidechaincompress FFmpeg
│   ├── retention_effects.py   # Filtro Zoom Punch e emojis/stickers contextuais
│   ├── integrations.py        # Upload YouTube Shorts API v3 e despachante de Webhooks
│   ├── export_kit.py          # Nomenclatura estrita (VLDSS, VRIRA...) e pastas de publicação
│   ├── cuts_catalog.py        # Catálogo e cache inteligente multi-instância (cuts_catalog.json)
│   ├── batch_processor.py     # Processamento sequencial em lote com Smart Skip e Phase 3
│   ├── library_manager.py     # Catálogo global de vídeos processados (library.json)
│   └── config_manager.py      # Persistência contínua de preferências (app_settings.json)
├── data/
│   ├── library.json           # Biblioteca geral de vídeos
│   ├── app_settings.json      # Configurações do usuário persistidas
│   ├── youtube_token.json     # Token de autorização OAuth do YouTube Shorts
│   └── <video_id>/
│       ├── audio.mp3          # Cache do áudio extraído
│       ├── transcript.json    # Transcrição com timestamps por palavra
│       ├── video_full.mp4     # Vídeo original Full HD 1080p
│       ├── cuts_catalog.json  # Catálogo de cortes e formatos gerados para este vídeo
│       └── <PREFIXO>_<NOME>/  # Pasta final do corte (Vídeo + Kit de Publicação)
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

## 📝 Legendas Dinâmicas & Headlines de Retenção (Fase 2 & 3)

- **Padrão SSA/ASS nativo via `libass` no FFmpeg**: Renderização em alta performance com nitidez absoluta.
- **Efeito Karaokê Palavra-a-Palavra**: A palavra sendo pronunciada fica em destaque (cor vibrante) enquanto o restante da frase permanece com menor opacidade.
- **🏷️ Headline / Título Fixo de Retenção no Topo**:
  - Caixa de destaque superior estilo viral TikTok/Reels com presets pré-definidos (`Amarelo Vibrante`, `Alerta Vermelho`, `Dark Box`, `Box Branco`, `Flutuante Bold` ou `Personalizado`).
  - Margem superior ajustável para Safe Zone de interfaces móveis e quebra de linhas inteligente.
- **😃 Emojis & Stickers Contextuais**:
  - Mapeamento dinâmico de termos de impacto (dinheiro, fogo, segredo, foco, etc.) com inserção de emojis visuais nas falas.
- **🔍 Zoom Punch Dinâmico**:
  - Aplicação de pulsos suaves de aproximação (1.07x) a cada ~8s para quebra de padrão visual.

---

## 🎵 Trilha Sonora de Fundo & Audio Ducking Inteligente

- **Biblioteca de Trilhas Categorizadas (`assets/audio/`)**:
  - `🧘 Lo-Fi Chill / Relax`, `⚡ Dinâmica / Ritmo`, `🔥 Tensão / Suspense`, `✨ Inspiracional / Motivacional` + Suporte a MP3s customizados.
- **Audio Ducking via FFmpeg**:
  - O volume da música é atenuado de forma fluida quando a voz está ativa (sidechain compression) e sobe sutilmente nos silêncios.
  - Presets de intensidade: `Suave (-12dB)`, `Médio / Padrão (-18dB)`, `Intenso (-24dB)`.

---

## 🌐 Exportação Direta & Integrações

- **🔴 Upload Direto para o YouTube Shorts (YouTube Data API v3)**:
  - Autenticação OAuth2 integrada.
  - Envio com 1 clique direto na Seção 3 e na Galeria, com seleção de privacidade (`Rascunho / Não Listado / Público`).
- **📡 Webhooks HTTP (n8n / Make / Zapier / Automações)**:
  - Disparo de payload estruturado contendo caminho do MP4, metadados do kit viral, hashtags, tags SEO e minutagens.

---

## 📁 Padrão de Exportação & Kit de Publicação Viral

Para cada corte gerado, a aplicação cria automaticamente uma pasta estruturada:
- **Nome da Pasta**: `[PREFIXO]_[Palavras_Completas]` (onde `[PREFIXO]` são as 5 letras do formato e o nome contém as primeiras palavras completas do título com limite estrito de 25 caracteres).
- **Conteúdo da Pasta**:
  - 🎬 `[PREFIXO]_[Palavras_Completas].mp4` (Vídeo renderizado com legendas, headline, áudio e enquadramento)
  - 📌 `info_publicacao.txt` (Contém: Título Viral, Legenda para Redes, Hashtags, Tags SEO, Nome do Vídeo gerado e Seção com Metadados do Vídeo Original: Título, Canal, Data e Link)
  - 📝 `descricao.txt` (Legenda pronta para copiar e colar)
  - 🏷️ `tags.txt` (Hashtags e Tags SEO separadas)

---

## ⚡ Catálogo & Cache Inteligente por Minutagem (`cuts_catalog.json`)

- Cada vídeo mantém seu catálogo estruturado em `data/<video_id>/cuts_catalog.json`.
- **Diferenciação por Formato**: A mesma minutagem pode conter múltiplas instâncias independentes (`VRIRA`, `VLDSS`, `VFDBS`, etc.).
- **Carregamento Instantâneo**: Se a minutagem já foi gerada no formato escolhido, o player e o botão de download abrem com **0 segundos de espera**.
- **Atualização sem Re-renderizar**: Botão para atualizar os textos do kit de publicação em **0.1 segundo** sem reprocessar o vídeo no FFmpeg.

---

## 📦 Esteira de Produção em Lote (Batch Render) & Galeria

- **Seleção em Lote**: Checkboxes individuais e botão rápido *"⚡ Selecionar Todos para Lote"* na aba de Ganchos Virais.
- **Smart Skip**: Pula automaticamente cortes que já foram gerados naquele formato, processando apenas novidades (com opção de forçar re-renderização se desejado).
- **Galeria de Cortes Produzidos (Seção 4)**:
  - Players de vídeo 9:16 compactos e elegantes dispostos lado a lado.
  - Botão de download direto, botões de publicação direta no YouTube Shorts e Webhook, e botão de exclusão individual `🗑️` com confirmação (*Apenas Vídeo* vs *Pasta Completa*).

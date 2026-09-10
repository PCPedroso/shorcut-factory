---
name: viralcut-video-pipeline
description: >-
  Guia de engenharia de vídeo com FFmpeg, MoviePy, aceleração de hardware NVENC GPU, overlays, tarjas (GC), recortes 9:16/16:9 e otimizações de streaming para o ViralCut.
---

# ViralCut: Motor de Processamento de Vídeo & FFmpeg Pipeline

Este guia estabelece os padrões técnicos para manipulação, edição, efeitos visuais e renderização de vídeo no ViralCut.

---

## 1. Diretrizes de Aceleração por Hardware (GPU NVIDIA)

- **Placa Gráfica do Usuário**: NVIDIA GeForce GTX 1650 (4 GB VRAM).
- **Encoder Padrão**: `h264_nvenc`.
  - Preset recomendado: `p4` (equilíbrio ideal entre velocidade e qualidade).
  - Bitrate: `8M` (para 1080p Full HD) / `6M` (para 9:16 vertical).
  - Fallback automático: Se o NVENC não estiver disponível (ex: limite de sessões ou drivers), usar `libx264` com preset `veryfast` e `crf 18`.

```bash
# Exemplo padrão de renderização FFmpeg com NVENC
ffmpeg -y -ss {start} -to {end} -i "{input_mp4}" \
  -filter_complex "{filter_graph}" \
  -c:v h264_nvenc -preset p4 -b:v 8M -maxrate 10M -bufsize 16M \
  -c:a aac -b:a 192k \
  -movflags +faststart \
  "{output_mp4}"
```

---

## 2. Preservação de Áudio e Streaming (`+faststart`)

1. **Streaming Instantâneo no Navegador / Streamlit**:
   - Sempre utilize a flag `-movflags +faststart` ao renderizar arquivos MP4. Isso move a tabela de metadados (`moov atom`) para o início do arquivo, permitindo que o Streamlit (`st.video`) inicie o playback imediatamente sem precisar baixar o arquivo inteiro na memória.
2. **Edição Rápida sem Perda (Trim sem Re-encode quando possível)**:
   - Para cortes simples nas bordas onde não há filtros adicionais: `-c copy -avoid_negative_ts make_zero`.

---

## 3. Motor de Overlays e Banners (`core/overlay_manager.py`)

- **Modos de Escala de Banner**:
  - `fill`: Estica a imagem para cobrir exatamente a largura e altura especificadas (ideal para cobrir GCs e tarjas antigas de TV como TMC 360).
  - `fit`: Redimensiona proporcionalmente adicionando canal alfa/transparência nas sobras.
  - `cover`: Amplia e corta centralizado preenchendo 100% da área sem distorção.
- **Composição com Logo Secundário**: Suporte a embutir imagem secundária (logo do canal, selo "AO VIVO", foto) internamente no banner com alinhamento (`left`, `center`, `right`) e margem ajustável.
- **Formato RGBA**: As sobreposições são geradas em PNG 32-bit (RGBA) e aplicadas via filtro `overlay=x:y:format=auto`.

---

## 4. Layouts de Enquadramento 9:16

1. **Smart Face (9:16)**:
   - Corte dinâmico na região do rosto centralizado com margem de segurança configurável (1.30x a 1.85x) e auto-zoom máximo.
2. **Blur / Fundo Desfocado (9:16)**:
   - Duas camadas: Camada de fundo ampliada com desfoque forte (`boxblur=25:5`) + Camada frontal nítida com auto-zoom e pan horizontal.
   - **Regra de Dual Shot**: Quando 2 oradores são detectados lado a lado, o sistema fixa `zoom = 1.0` e `pan = 0.0`, exibindo o vídeo 16:9 completo centralizado sobre o fundo desfocado.
3. **Split Screen (9:16)**:
   - Duas metades (topo e base) com foco horizontal independente e divisor customizável, acompanhado de *Auto-Switch* para transição inteligente quando houver plano individual.

---

## 5. Aceleração de Velocidade com Preservação Natural de Voz (`core/quick_editor.py`)

- **Fórmula de Filtros FFmpeg**:
  - Vídeo: `setpts=(1/SPEED)*PTS` (aceleração da cadência visual).
  - Áudio: `atempo=SPEED` (aceleração do áudio sem alterar o pitch/tom da voz).
  - Flags de Renderização: `-c:v h264_nvenc -preset p4 -c:a aac -b:a 192k -movflags +faststart`.
- **Limpeza de Versões Intermediárias**:
  - `cleanup_all_edited_versions(video_path, keep_path=...)`: Exclui versões anteriores editadas (`_trimmed`, `_snipped`, `_speed_...`, `_banner`, `_headline`, etc.), garantindo diretórios limpos e eliminando confusão no catálogo.

---

## 6. Motor Fast Live Snapshot para Transmissões Ao Vivo (`core/extractor.py` & `core/video_processor.py`)

Para streams ao vivo do YouTube em andamento (`is_live: True`):

## 7. Estratégia de Qualidade Máxima para Mídias Sociais (`get_optimal_video_format`)

Para evitar rebaixamento de qualidade ou perda de resolução em redes sociais:

1. **Instagram (Reels, Stories, TV)**:
   - Os vídeos verticais têm dimensões nativas de `1080x1920`.
   - **Regra**: Nunca restringir com `[height<=1080]`, pois isso descartaria o Full HD vertical (height=1920) e forçaria o download para 540p com apenas ~350 kbps.
   - **Formato Otimizado**: `bestvideo[width<=1920][height<=1920][ext=mp4]+bestaudio[ext=m4a]/bestvideo[width<=1920][height<=1920]+bestaudio/...`, garantindo 1080x1920 com bitrate de 1600+ kbps.

2. **Twitter / X**:
   - O Twitter disponibiliza arquivos progressivos MP4 via HTTPS (`http-10368`, `http-2176`, `http-832`) com bitrates originais de até 10+ Mbps.
   - Paralelamente, fornece fluxos HLS adaptativos com bitrate severamente comprimido (1/3 a 1/4 da qualidade).
   - **Regra**: Priorizar `best[ext=mp4][width<=1920][height<=1920]` para capturar o stream HTTP integral nativo de alta qualidade antes de recorrer a HLS fragmentado.

3. **YouTube & Geral**:
   - Dimensionamento Full HD equilibrado: `[width<=1920][height<=1920]`, cobrindo tanto 1920x1080 horizontal quanto 1080x1920 vertical (Shorts) sem rebaixamento acidental.

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

1. **Prevenção de Gravação em Loop Contínuo:**
   - O comportamento padrão de livestreams em downloaders mantém a conexão aberta gravando indefinidamente em tempo real (1.0x).
   - O ViralCut contorna isso gerando uma playlist snapshot HLS com injeção mandatória de `#EXT-X-ENDLIST`.
   - Isso instrui o FFmpeg a tratar a transmissão existente até aquele segundo como um arquivo completo e finito, finalizando o download na velocidade máxima da rede sem esperar a live continuar transmitindo.
2. **Corte Direto de Vídeo via Stream Copy (`-c copy`):**
   - Ao fatiar um trecho na Seção 3 (`start_sec` e `end_sec`), conecta diretamente na master manifest HLS (`manifest_url` / `hls_variant`) aplicando `-ss` e `-t` com `-c copy`, gerando o MP4 1080p cortado em menos de 25 segundos sem re-encoding.
3. **Sanitização de Clientes:**
   - O cliente `android` do YouTube não suporta streams HLS com `live_from_start`. Ele é automaticamente omitido em streams ao vivo para eliminar o erro `No video formats found!`.




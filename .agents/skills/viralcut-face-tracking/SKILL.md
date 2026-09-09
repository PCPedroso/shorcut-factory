---
name: viralcut-face-tracking
description: >-
  Guia de visão computacional com MediaPipe BlazeFace, detecção de oradores duplos (Dual Shot), filtragem de janelas secundárias (Libras), Auto-Reframing e cálculo de Bounding Boxes compostas no ViralCut.
---

# ViralCut: Motor de Rastreamento Facial & Enquadramento Inteligente

Este guia documenta o funcionamento do módulo `core/face_tracker.py` para detecção de rostos, plano conjunto (debate/entrevistas) e auto-reframing 9:16.

---

## 1. Detecção Facial com MediaPipe BlazeFace

- **Modelo**: `mediapipe.tasks.vision.FaceDetector` com modelo `blazeface` (rápido e preciso para CPUs e GPUs modestas).
- **Filtragem de Ruído e Janelas Secundárias**:
  - A função `filter_prominent_faces` descarta rostos que ocupem menos de 1.8% da área do frame ou estejam posicionados no canto inferior/lateral em proporção reduzida (ex: intérpretes de Libras ou logos de TV).

---

## 2. Heurística de Dual Shot / Plano Conjunto (`is_dual_interlocutor_shot`)

Para programas de TV, sabatinas e podcasts onde dois entrevistados/apresentadores aparecem simultaneamente:

1. **Critérios de Ativação**:
   - Pelo menos 2 rostos proeminentes detectados no frame.
   - Distância horizontal entre centros dos rostos (`span_x = |center_x1 - center_x2|`) $\ge 0.22$ da largura do frame.
   - Proporção de tamanho entre os dois rostos principais $\ge 0.35$ (evita falsos positivos com pessoas no fundo).
2. **Comportamento no Enquadramento 9:16 Blur**:
   - Define automaticamente `zoom = 1.0` e `pan = 0.0`.
   - O frame 16:9 completo é centralizado no terço médio da tela vertical sem cortes nas laterais, preservando os dois oradores e eventuais molduras gráficas do estúdio.
3. **Comportamento no Enquadramento 9:16 Smart Face**:
   - Cria uma **Bounding Box Composta** englobando ambos os rostos (`min_x` do primeiro até `max_x` do segundo), centralizando a câmera vertical no ponto médio dos dois oradores.

---

## 3. Fórmulas de Calibração de Auto-Zoom e Pan Horizontal

Para enquadramento individual de um orador:
- **Pan Horizontal**:
  $$\text{pan} = 2.0 \times (\text{face\_center\_x} - 0.5)$$
  (Limitado no intervalo $[-1.0, +1.0]$).
- **Auto-Zoom com Margem de Segurança**:
  $$\text{zoom} = \text{clamp}\left(\frac{1.0}{\text{face\_width} \times \text{margin\_ratio}}, 1.0, 2.2\right)$$
  - Margem Estreita (Close-up Máximo): `1.30`
  - Margem Equilibrada (Busto & Rosto - Padrão): `1.55`
  - Margem Ampla (Plano Médio): `1.85`

---

## 4. Enquadramento Proporcional Estrito em Split Screen (`extract_proportional_crop`)

Para layouts divididos (Split Screen 9:16) com slots de proporções variáveis (por exemplo, ao aplicar margens desfocadas de 0% a 20%):

1. **Prevenção de Distorção Anamórfica**:
   - Nunca utilizar relações de aspecto fixas pré-concebidas (como `1.125`), pois quando a altura do slot é reduzida por margens de blur (ex: de 960px para 576px), a distorção anamórfica pode deformar e esticar a imagem horizontalmente em até 67%.
   - Calcular a razão de aspecto exata do slot destino:
     $$\text{slot\_aspect} = \frac{\text{target\_w}}{\text{target\_h}}$$
2. **Cálculo da Janela de Corte**:
   - Ajustar as dimensões de recorte (`crop_w`, `crop_h`) preservando estritamente `slot_aspect`:
     - Se $\text{frame\_aspect} > \text{slot\_aspect}$: $\text{crop\_h} = \frac{H}{\text{zoom}}$, $\text{crop\_w} = \text{crop\_h} \times \text{slot\_aspect}$.
     - Caso contrário: $\text{crop\_w} = \frac{W}{\text{zoom}}$, $\text{crop\_h} = \frac{\text{crop\_w}}{\text{slot\_aspect}}$.
3. **Controle Bidirecional de Pan (`pan_x` e `pan_y`)**:
   - `pan_x` $[-1.0, +1.0]$: Desloca o enquadramento horizontalmente (esquerda $\leftrightarrow$ direita).
   - `pan_y` $[-1.0, +1.0]$: Desloca o enquadramento verticalmente (baixo $\leftrightarrow$ cima), permitindo manter os olhos do orador na linha dos terços sem cortes na cabeça ou tronco.


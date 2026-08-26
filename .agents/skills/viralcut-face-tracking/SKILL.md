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

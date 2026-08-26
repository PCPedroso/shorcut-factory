---
name: viralcut-ai-mining
description: >-
  Guia de inteligência artificial para transcrição com Faster-Whisper, fatiamento contínuo em falas longas de podcasts, pontuação de viralidade e prompts Ollama (Llama 3) no ViralCut.
---

# ViralCut: Mineração de Cortes, Transcrição & IA

Este guia orienta o funcionamento dos módulos `core/extractor.py` e `core/analyzer.py` para extração de áudio, transcrição temporal e mineração de momentos de alto impacto viral.

---

## 1. Transcrição com Faster-Whisper (`core/extractor.py`)

- **Biblioteca**: `faster-whisper` (CTranslate2 com suporte a CPU e GPU CUDA).
- **Parâmetros Críticos**:
  - `word_timestamps=True`: Obrigatório para legendas dinâmicas palavra-a-palavra e alinhamento milimétrico de cortes.
  - `beam_size=5`: Equilíbrio ideal entre precisão fonética e velocidade.
  - Modelos recomendados: `small` (padrão) e `medium` (para precisão máxima).
- **Live Streams em Andamento**:
  - Detecção via yt-dlp (`is_live`, `live_status == 'is_live'`).
  - Utilização de `live_from_start: True` com `hls_use_mpegts: True` para permitir o download e transcrição do primeiro minuto até o instante atual sem travar o processo.

---

## 2. Mineração Multi-Corte em Falas Longas (`core/analyzer.py`)

Em entrevistas e podcasts, respostas de convidados frequentemente duram entre 3 e 10 minutos. O algoritmo `multi_cut_mining`:
1. **Varredura Semântica**: Identifica quebras de turno (`>>`), perguntas (`?`) e conectivos lógicos de transição (*"Por exemplo"*, *"Veja bem"*, *"O ponto central"*, *"Na verdade"*, etc.).
2. **Janelas Ótimas de Retenção**: Gera cortes autônomos entre **35 e 120 segundos** (duração perfeita para TikTok/Reels/Shorts).
3. **Autonomia Semântica**: Garante que cada corte inicie com uma frase de introdução compreensível e finalize em um pensamento concluído (evitando cortes bruscos no meio da fala).

---

## 3. Engenharia de Prompts com Ollama / Llama 3

O ViralCut se comunica com o Ollama local (`http://localhost:11434`):
- **Estratégias de Análise**:
  - 🎙️ Entrevistas & Sabatinas (Foco em Q&A e punchlines).
  - 📈 Desenvolvimento Pessoal & Negócios (Foco em hacks práticos e lições).
  - ⚡ Histórias & Narrativas (Foco em storytelling e reviravoltas).
- **Estrutura de Saída (JSON Strict)**:
  - `title`: Título chamativo com gatilhos de curiosidade (sem clickbait falso).
  - `description`: Legenda envolvente para redes sociais com Call-To-Action (CTA).
  - `hashtags`: 4 a 6 hashtags estratégicas e nichadas.
  - `tags_seo`: Termos de busca para ranqueamento no algoritmo.
  - `virality_score`: Nota de 0 a 100 baseada em retenção, clareza e impacto emocional.

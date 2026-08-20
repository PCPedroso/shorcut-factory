import os, sys, json, re
sys.path.insert(0, os.path.abspath("."))
import ollama
from core.transcriber import fetch_youtube_transcript, build_youtube_transcript_blocks

video_id = "NRLvjdjvnag"
res = fetch_youtube_transcript(video_id)
segments = res.get("transcript_segments", [])

# Cria blocos semânticos completos da transcrição com timestamp
blocks = build_youtube_transcript_blocks(segments, target_duration=12.0)

formatted_transcript_lines = []
for b in blocks:
    formatted_transcript_lines.append(f"[{b['time_full']}] {b['text']}")

full_formatted_transcript = "\n".join(formatted_transcript_lines)

prompt = f"""Você é um editor sênior de telejornalismo e podcasts.
Analise a transcrição completa da sabatina/entrevista abaixo.

Identifique TODAS as perguntas ou temas discutidos, indicando exatamente onde cada pergunta/assunto COMEÇA (quando o jornalista pergunta) e onde a resposta TERMINA (antes da próxima pergunta).

TRANSCRIÇÃO:
{full_formatted_transcript}

REGRAS:
1. Responda ESTRITAMENTE em Português.
2. Cada pauta DEVE conter o timestamp de INÍCIO e FIM no formato:
   1. [MM:SS - MM:SS] Título claro e objetivo do tema/pergunta
3. NÃO invente horários fora da transcrição. Use os horários reais indicados nos blocos.
4. NÃO inclua saudações, introduções ou notas. Apenas a lista numerada.

Exemplo de formato esperado:
1. [00:00 - 01:15] Abertura e apresentação da sabatina
2. [01:16 - 02:44] Falta de experiência parlamentar e executiva
3. [02:45 - 04:02] Como conquistar o voto do eleitor mais velho além da internet
"""

print("--- Calling Ollama with full formatted transcript ---")
try:
    response = ollama.chat(
        model="llama3",
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.1}
    )
    output = response["message"]["content"]
    print("=== OLLAMA OUTPUT ===")
    print(output)
except Exception as e:
    print("Error:", e)

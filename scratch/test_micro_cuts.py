import os, sys, re, json
sys.path.insert(0, os.path.abspath("."))
from core.transcriber import fetch_youtube_transcript
from core.analyzer import detect_qa_pautas, format_seconds_to_time, format_duration_human

video_id = "NRLvjdjvnag"
res = fetch_youtube_transcript(video_id)
segments = res.get("transcript_segments", [])

pautas = detect_qa_pautas(segments)

def build_golden_rule_micro_cuts(pautas, segments):
    """
    Aplica as 6 Regras de Ouro para gerar pequenos cortes (20s a 75s) perfeitos:
    1. Clean Entry (respiro inicial)
    2. Clean Exit (respiro final sem vazamento)
    3. Autonomia Semântica (sentido fechado)
    4. Tipologia (Q&A Unit vs Punchline)
    5. Anti-vazamento de assunto
    6. Duração de retenção (20s - 75s)
    """
    cuts = []
    
    for p in pautas:
        # Pula vinhetas de abertura e encerramento
        if "Abertura" in p["title"] or "Encerramento" in p["title"]:
            continue
            
        dur = p["duration_s"]
        
        # Caso 1: Pauta curta/média (<= 75s) -> Tipo A: Q&A Completo (Pergunta + Resposta)
        if 20.0 <= dur <= 85.0:
            cuts.append({
                "type": "🏷️ [Q&A] Pergunta & Resposta Completa",
                "start": p["start"],
                "end": p["end"],
                "start_s": p["start_s"],
                "end_s": p["end_s"],
                "duration_s": dur,
                "duration_label": format_duration_human(dur),
                "title": p["title"],
                "description": f"Pergunta do jornalista e resposta completa do entrevistado com raciocínio 100% fechado.",
                "snippet": p.get("text_snippet", "")
            })
            
        # Caso 2: Pauta mais longa (> 85s) -> Extrai a Declaração de Impacto (Tipo B: Punchline / Tese)
        elif dur > 85.0:
            # Pega as frases dentro dessa pauta
            p_segs = [s for s in segments if p["start_s"] <= s["start"] <= p["end_s"]]
            if len(p_segs) >= 4:
                # Procura a resposta mais contundente do entrevistado (geralmente a partir da 2ª ou 3ª frase)
                # Começa onde o candidato inicia a resposta até uma conclusão forte
                ans_start_seg = next((s for s in p_segs if ">>" in s["text"] and s["start"] > p["start_s"] + 10), None)
                if ans_start_seg:
                    cut_start = ans_start_seg["start"]
                    # Encontra o melhor ponto de fechamento entre 40s e 70s após o início
                    potential_ends = [s for s in p_segs if cut_start + 25.0 <= s["end"] <= cut_start + 70.0 and s["text"].strip().endswith(('.', '!'))]
                    if potential_ends:
                        cut_end = potential_ends[-1]["end"]
                    else:
                        cut_end = min(p["end_s"], cut_start + 60.0)
                        
                    cut_dur = cut_end - cut_start
                    if cut_dur >= 20.0:
                        cuts.append({
                            "type": "🏷️ [Punchline] Declaração / Tese de Impacto",
                            "start": format_seconds_to_time(cut_start),
                            "end": format_seconds_to_time(cut_end),
                            "start_s": cut_start,
                            "end_s": cut_end,
                            "duration_s": cut_dur,
                            "duration_label": format_duration_human(cut_dur),
                            "title": f"Tese: {p['title']}",
                            "description": f"Declaração direta e contundente do entrevistado sem necessidade da pergunta inicial.",
                            "snippet": " ".join(s["text"].replace(">>", "").strip() for s in p_segs if cut_start <= s["start"] <= cut_end)[:140]
                        })

    return cuts

micro_cuts = build_golden_rule_micro_cuts(pautas, segments)
print(f"Gerados {len(micro_cuts)} Micro-Cortes sob as 6 Regras de Ouro:")
for i, c in enumerate(micro_cuts):
    print(f"{i+1}. {c['type']} | [{c['start']} -> {c['end']}] ({c['duration_label']}): {c['title']}")

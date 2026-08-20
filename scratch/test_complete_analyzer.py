import os, sys, re, json
sys.path.insert(0, os.path.abspath("."))
from core.transcriber import fetch_youtube_transcript

video_id = "NRLvjdjvnag"
res = fetch_youtube_transcript(video_id)
segments = res.get("transcript_segments", [])

def format_seconds_to_time(secs: float) -> str:
    secs = max(0, int(secs))
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def format_duration_human(secs: float) -> str:
    m = int(secs // 60)
    s = int(secs % 60)
    if m > 0:
        return f"{m}m {s:02d}s"
    return f"{s}s"

def extract_qa_pautas(segments):
    # Identifica pontos onde um jornalista/entrevistador inicia uma nova pergunta
    question_starts = []
    
    # 1. Abertura inicial (0.0s)
    question_starts.append({"start_s": 0.0, "is_opening": True})
    
    for i, s in enumerate(segments):
        txt = s["text"].strip()
        t = s["start"]
        
        # Padrões que marcam início de pergunta de entrevistador
        is_new_speaker = ">>" in txt
        is_q_pattern = bool(re.search(r"(candidato|jornalista|primeira pergunta|gostaria de|o senhor disse|como defender|que que é|já que o senhor|dá tempo da gente|muitíssimo obrigado)", txt, re.IGNORECASE))
        
        # Se for o início da 1ª pergunta da jornalista por volta de 70s-80s
        if is_new_speaker and t >= 65.0 and len(question_starts) == 1:
            question_starts.append({"start_s": t, "is_opening": False})
            continue
            
        # Perguntas subsequentes (distância mínima de 35s entre perguntas)
        if is_new_speaker and is_q_pattern and (t - question_starts[-1]["start_s"] >= 35.0):
            question_starts.append({"start_s": t, "is_opening": False})

    # Monta as pautas delimitadas por início e fim
    total_dur = segments[-1]["end"]
    pautas = []
    
    for idx, q in enumerate(question_starts):
        st_s = q["start_s"]
        if idx + 1 < len(question_starts):
            # O final da pauta é o final do segmento imediatamente anterior à próxima pergunta
            next_st = question_starts[idx + 1]["start_s"]
            prev_seg = next((s for s in reversed(segments) if s["end"] <= next_st + 1.0), None)
            end_s = prev_seg["end"] if prev_seg else next_st
        else:
            end_s = total_dur
            
        dur_s = max(0, end_s - st_s)
        
        # Pega o texto da pauta
        p_texts = [s["text"].replace(">>", "").strip() for s in segments if st_s <= s["start"] <= end_s]
        p_text = " ".join(p_texts)
        
        # Gera título descritivo inicial
        if q.get("is_opening"):
            title = "Abertura e Apresentação da Sabatina"
        elif "muitíssimo obrigado" in p_text.lower() and dur_s < 30:
            title = "Encerramento e Agradecimentos Finais"
        else:
            # Extrai o tema da pergunta inicial
            first_sentence = p_text.split('.')[0] if '.' in p_text else p_text[:80]
            title = first_sentence[:75].strip()
            
        pautas.append({
            "id": len(pautas) + 1,
            "start": format_seconds_to_time(st_s),
            "end": format_seconds_to_time(end_s),
            "start_s": st_s,
            "end_s": end_s,
            "duration_s": dur_s,
            "duration_label": format_duration_human(dur_s),
            "title": title,
            "text_snippet": p_text[:150]
        })
        
    return pautas

pautas = extract_qa_pautas(segments)
print(f"Mapeadas {len(pautas)} pautas com início e fim exatos:")
for p in pautas:
    print(f"{p['id']}. [{p['start']} -> {p['end']}] ({p['duration_label']}): {p['title']}")

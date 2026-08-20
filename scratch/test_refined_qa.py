import os, sys, re, json
sys.path.insert(0, os.path.abspath("."))
from core.transcriber import fetch_youtube_transcript

video_id = "NRLvjdjvnag"
res = fetch_youtube_transcript(video_id)
segments = res.get("transcript_segments", [])

def detect_interview_qa_blocks(segments):
    raw_blocks = []
    curr_q_start = 0.0
    curr_q_texts = []
    
    for i, s in enumerate(segments):
        txt = s["text"].strip()
        t_start = s["start"]
        
        is_new_speaker = ">>" in txt
        is_q_pattern = bool(re.search(r"(candidato|jornalista|primeira pergunta|gostaria de|o senhor disse|como defender|que que é|já que o senhor|dá tempo da gente|muitíssimo obrigado)", txt, re.IGNORECASE))
        
        # Quebra quando um novo orador faz uma pergunta ou após uma introdução
        if (is_new_speaker and (is_q_pattern or i > 2) and (t_start - curr_q_start >= 30.0)):
            if curr_q_texts:
                prev_end = segments[i-1]["end"]
                raw_blocks.append({
                    "start_s": curr_q_start,
                    "end_s": prev_end,
                    "text": " ".join(curr_q_texts)
                })
            curr_q_start = t_start
            curr_q_texts = []
            
        curr_q_texts.append(txt.replace(">>", "").strip())
        
    if curr_q_texts:
        prev_end = segments[-1]["end"]
        raw_blocks.append({
            "start_s": curr_q_start,
            "end_s": prev_end,
            "text": " ".join(curr_q_texts)
        })
        
    # Se o primeiro bloco começou em 0.0 e a primeira pergunta começou em ~77s, separa a abertura:
    refined = []
    for b in raw_blocks:
        if b["start_s"] == 0.0 and b["end_s"] > 100.0:
            split_seg = next((s for s in segments if s["start"] >= 70.0 and ">>" in s["text"]), None)
            if split_seg:
                s_idx = segments.index(split_seg)
                refined.append({
                    "start_s": 0.0,
                    "end_s": segments[s_idx - 1]["end"],
                    "text": " ".join(s["text"].replace(">>", "").strip() for s in segments[:s_idx])
                })
                refined.append({
                    "start_s": split_seg["start"],
                    "end_s": b["end_s"],
                    "text": " ".join(s["text"].replace(">>", "").strip() for s in segments[s_idx:] if s["end"] <= b["end_s"])
                })
                continue
        refined.append(b)
    return refined

blocks = detect_interview_qa_blocks(segments)
print(f"Total blocos refinados: {len(blocks)}")
for i, b in enumerate(blocks):
    m1, s1 = int(b['start_s']//60), int(b['start_s']%60)
    m2, s2 = int(b['end_s']//60), int(b['end_s']%60)
    dur = b['end_s'] - b['start_s']
    txt = b['text'][:85]
    print(f"{i+1}. [{m1:02d}:{s1:02d} - {m2:02d}:{s2:02d}] ({dur:.0f}s): {txt}...")

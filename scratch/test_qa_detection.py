import os, sys, re
sys.path.insert(0, os.path.abspath("."))
from core.transcriber import fetch_youtube_transcript

video_id = "NRLvjdjvnag"
res = fetch_youtube_transcript(video_id)
segments = res.get("transcript_segments", [])

def detect_qa_blocks(segments):
    blocks = []
    curr_q_start = 0.0
    curr_q_texts = []
    
    for i, s in enumerate(segments):
        txt = s["text"].strip()
        t_start = s["start"]
        
        # Indica início de nova pergunta
        is_new_speaker = ">>" in txt
        is_q_pattern = bool(re.search(r"(candidato|jornalista|primeira pergunta|gostaria de|o senhor disse|como defender|que que é|já que o senhor|dá tempo da gente)", txt, re.IGNORECASE))
        
        if (is_new_speaker and is_q_pattern and i > 2 and (t_start - curr_q_start >= 35.0)):
            if curr_q_texts:
                prev_end = segments[i-1]["end"]
                blocks.append({
                    "start_s": curr_q_start,
                    "end_s": prev_end,
                    "start_fmt": f"{int(curr_q_start//60):02d}:{int(curr_q_start%60):02d}",
                    "end_fmt": f"{int(prev_end//60):02d}:{int(prev_end%60):02d}",
                    "text": " ".join(curr_q_texts)
                })
            curr_q_start = t_start
            curr_q_texts = []
            
        curr_q_texts.append(txt.replace(">>", "").strip())
        
    if curr_q_texts:
        prev_end = segments[-1]["end"]
        blocks.append({
            "start_s": curr_q_start,
            "end_s": prev_end,
            "start_fmt": f"{int(curr_q_start//60):02d}:{int(curr_q_start%60):02d}",
            "end_fmt": f"{int(prev_end//60):02d}:{int(prev_end%60):02d}",
            "text": " ".join(curr_q_texts)
        })
    return blocks

blocks = detect_qa_blocks(segments)
print(f"Detectados {len(blocks)} blocos de pauta:")
for i, b in enumerate(blocks):
    dur = b['end_s'] - b['start_s']
    print(f"{i+1}. [{b['start_fmt']} - {b['end_fmt']}] ({dur:.0f}s): {b['text'][:100]}...")

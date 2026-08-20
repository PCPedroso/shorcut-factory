import os, sys
sys.path.insert(0, os.path.abspath("."))
import json
from core.transcriber import fetch_youtube_transcript

video_id = "NRLvjdjvnag"
res = fetch_youtube_transcript(video_id)
print("Source:", res.get("source"))
segments = res.get("transcript_segments", [])
print("Total segments:", len(segments))

for s in segments:
    st_t = s["start"]
    end_t = s["end"]
    if 60 <= st_t <= 180:
        m = int(st_t // 60)
        sec = int(st_t % 60)
        print(f"[{m:02d}:{sec:02d}] ({st_t:.1f}s - {end_t:.1f}s): {s['text']}")

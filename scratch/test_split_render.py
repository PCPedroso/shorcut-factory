import os, sys, cv2, subprocess
sys.path.insert(0, os.path.abspath("."))
import imageio_ffmpeg

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
video_path = "data/NRLvjdjvnag/video_full.mp4"
output_preview = "scratch/test_split_preview.jpg"
output_cut = "scratch/test_split_cut.mp4"

def build_split_filter(top_pan: float = -0.5, bottom_pan: float = 0.5, zoom: float = 1.1, divider_color: str = "black", divider_width: int = 4):
    """
    Constrói o filtro FFmpeg para Split Screen 9:16 (1080x1920):
    Top: Interlocutor 1 (1080x960)
    Bottom: Interlocutor 2 (1080x960)
    Divider: Linha divisória entre os dois
    """
    # 9:8 aspect ratio = 1080 / 960 = 1.125
    base_w = int(1080 * 1.125 / zoom)
    base_h = int(1080 / zoom)
    
    # Range horizontal em 1920
    max_x = max(0, 1920 - base_w)
    
    # Top X
    top_x = int(max(0, min(max_x, (max_x / 2.0) + (top_pan * (max_x / 2.0)))))
    top_y = int(max(0, min(1080 - base_h, (1080 - base_h) / 2.0)))
    
    # Bottom X
    bottom_x = int(max(0, min(max_x, (max_x / 2.0) + (bottom_pan * (max_x / 2.0)))))
    bottom_y = top_y
    
    filter_complex = (
        f"[0:v]split=2[v_top_in][v_bot_in]; "
        f"[v_top_in]crop={base_w}:{base_h}:{top_x}:{top_y},scale=1080:960[v_top]; "
        f"[v_bot_in]crop={base_w}:{base_h}:{bottom_x}:{bottom_y},scale=1080:960[v_bot]; "
        f"[v_top][v_bot]vstack=inputs=2[v_stacked]; "
        f"[v_stacked]drawbox=y=958:h={divider_width}:color={divider_color}@0.9:t=fill[v_out]"
    )
    return filter_complex

# Testa geração de 5 segundos de corte em Split Screen
flt = build_split_filter(top_pan=-0.65, bottom_pan=0.65, zoom=1.15)
cmd = [
    FFMPEG_EXE, "-y",
    "-ss", "00:01:25",
    "-to", "00:01:30",
    "-i", video_path,
    "-filter_complex", flt,
    "-map", "[v_out]",
    "-map", "0:a?",
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-crf", "22",
    "-c:a", "aac",
    output_cut
]

print("Running FFmpeg split screen render...")
res = subprocess.run(cmd, capture_output=True, text=True)
if res.returncode == 0:
    print(f"Sucesso! Gerado {output_cut} (Tamanho: {os.path.getsize(output_cut)} bytes)")
    
    # Extrai 1 frame de preview
    cap = cv2.VideoCapture(output_cut)
    ret, frame = cap.read()
    if ret:
        cv2.imwrite(output_preview, frame)
        print(f"Prévia salva em {output_preview}")
    cap.release()
else:
    print("FFmpeg error:", res.stderr)

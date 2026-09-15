import os
import pytest
from core.video_processor import generate_local_video_id, extract_audio_from_local_video, extract_thumbnail_from_video
from core.library_manager import format_upload_date, add_or_update_video_in_library

def test_generate_local_video_id():
    vid1 = generate_local_video_id("Meu Video de Entrevista.mp4")
    assert vid1.startswith("local_meu_video_de_entrevista_")
    
    vid2 = generate_local_video_id("podcast_episodio_10.mkv")
    assert vid2.startswith("local_podcast_episodio_10_")
    
    # IDs para o mesmo nome devem ser consistentes
    vid3 = generate_local_video_id("Meu Video de Entrevista.mp4")
    assert vid1 == vid3

def test_format_upload_date_local():
    assert format_upload_date("") == "Arquivo Local"
    assert format_upload_date(None) == "Arquivo Local"
    assert format_upload_date("27/08/2026") == "27/08/2026"
    assert format_upload_date("20260827") == "27/08/2026"

def test_extract_audio_and_thumbnail():
    sample_video = os.path.join("data", "W43edxthuZ4", "video_full.mp4")
    if not os.path.exists(sample_video):
        pytest.skip("Vídeo de amostra não encontrado para teste de extração.")
        
    out_audio = os.path.join("data", "temp_test_audio.mp3")
    out_thumb = os.path.join("data", "temp_test_thumb.jpg")
    
    try:
        audio_res = extract_audio_from_local_video(sample_video, out_audio)
        assert audio_res.get("error") is None
        assert os.path.exists(out_audio)
        assert os.path.getsize(out_audio) > 0
        
        thumb_res = extract_thumbnail_from_video(sample_video, out_thumb, timestamp_sec=2.0)
        assert thumb_res.get("error") is None
        assert os.path.exists(out_thumb)
        assert os.path.getsize(out_thumb) > 0
    finally:
        if os.path.exists(out_audio):
            os.remove(out_audio)
        if os.path.exists(out_thumb):
            os.remove(out_thumb)


def test_generate_local_video_id_with_cut():
    vid_normal = generate_local_video_id("podcast.mp4")
    vid_cut = generate_local_video_id("podcast.mp4", start_time_str="00:01:00", end_time_str="00:02:30")
    
    assert vid_normal != vid_cut
    assert "_cut_60s_150s_" in vid_cut
    
    # Repetir com os mesmos tempos deve dar o mesmo ID
    vid_cut2 = generate_local_video_id("podcast.mp4", start_time_str="00:01:00", end_time_str="00:02:30")
    assert vid_cut == vid_cut2
    
    # Início 0 e fim vazio/0 deve ser idêntico ao normal
    vid_zero = generate_local_video_id("podcast.mp4", start_time_str="00:00:00", end_time_str="")
    assert vid_zero == vid_normal


def test_slice_or_copy_local_video():
    import subprocess
    import imageio_ffmpeg
    from core.video_processor import slice_or_copy_local_video
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    os.makedirs("data", exist_ok=True)
    src_video = os.path.join("data", "temp_unit_test_src.mp4")
    dst_copy = os.path.join("data", "temp_unit_test_copy.mp4")
    dst_cut = os.path.join("data", "temp_unit_test_cut.mp4")
    
    try:
        # Gera vídeo de teste de 4 segundos
        cmd = [
            ffmpeg_exe, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=4:size=320x240:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=4",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            src_video
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        assert os.path.exists(src_video)
        
        # 1. Cópia integral (sem corte)
        res_copy = slice_or_copy_local_video(src_video, dst_copy, start_time_str="00:00:00", end_time_str="")
        assert res_copy["error"] is None
        assert not res_copy["is_trimmed"]
        assert os.path.exists(dst_copy)
        assert res_copy["duration"] >= 3.5
        
        # 2. Corte com início e fim (1s a 3s = duração ~ 2s)
        res_cut = slice_or_copy_local_video(src_video, dst_cut, start_time_str="00:00:01", end_time_str="00:00:03")
        assert res_cut["error"] is None
        assert res_cut["is_trimmed"]
        assert os.path.exists(dst_cut)
        assert 1.5 <= res_cut["duration"] <= 2.5
        
        # 3. Validação de erro se start >= end
        res_invalid = slice_or_copy_local_video(src_video, dst_cut, start_time_str="00:00:05", end_time_str="00:00:02")
        assert res_invalid["error"] is not None
        
    finally:
        for f in [src_video, dst_copy, dst_cut]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

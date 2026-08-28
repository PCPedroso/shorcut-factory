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

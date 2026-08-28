import os
import pytest
from core.face_tracker import crop_video_with_smart_blur_tracking
from core.video_processor import get_video_resolution

def test_crop_video_with_smart_blur_tracking():
    sample_video = os.path.join("data", "W43edxthuZ4", "video_full.mp4")
    if not os.path.exists(sample_video):
        pytest.skip("Vídeo de amostra não encontrado para teste de blur tracking.")

    out_path = os.path.join("data", "temp_test_blur_cut.mp4")

    try:
        res = crop_video_with_smart_blur_tracking(
            input_video_path=sample_video,
            start_time_str="00:03:18",
            end_time_str="00:03:20",
            output_video_path=out_path,
            blur_zoom=1.35,
            person_preference="auto",
            auto_tracking=True
        )

        assert res.get("error") is None
        assert os.path.exists(out_path)
        assert os.path.getsize(out_path) > 0

        # Verifica resolução gerada 1080x1920
        res_info = get_video_resolution(out_path)
        assert res_info == "1080x1920"

    finally:
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except Exception:
                pass

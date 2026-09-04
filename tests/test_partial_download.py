import pytest
from unittest.mock import patch, MagicMock
from core.extractor import parse_time_str, format_time_sec, download_audio
from core.video_processor import download_full_video


def test_parse_time_str_valid_formats():
    assert parse_time_str("01:15:30") == 4530.0
    assert parse_time_str("15:30") == 930.0
    assert parse_time_str("90") == 90.0
    assert parse_time_str("90.5") == 90.5
    assert parse_time_str(120) == 120.0
    assert parse_time_str(45.5) == 45.5
    assert parse_time_str("1h30m10s") == 5410.0
    assert parse_time_str("1h 30m") == 5400.0
    assert parse_time_str("45m") == 2700.0
    assert parse_time_str("30s") == 30.0


def test_parse_time_str_invalid_formats():
    assert parse_time_str(None) is None
    assert parse_time_str("") is None
    assert parse_time_str("   ") is None
    assert parse_time_str("invalido") is None
    assert parse_time_str(-10) is None


def test_format_time_sec():
    assert format_time_sec(4530.0) == "01:15:30"
    assert format_time_sec(930.0) == "15:30"
    assert format_time_sec(45.0) == "00:45"
    assert format_time_sec(0) == "00:00"
    assert format_time_sec(-5) == "00:00"
    assert format_time_sec(None) == "00:00"


@patch("yt_dlp.YoutubeDL")
@patch("os.path.exists", return_value=True)
@patch("os.path.getsize", return_value=1024)
def test_download_audio_with_range_options(mock_getsize, mock_exists, mock_ydl_cls):
    mock_instance = MagicMock()
    mock_ydl_cls.return_value.__enter__.return_value = mock_instance

    res = download_audio(
        "https://www.youtube.com/watch?v=mock123",
        output_path="test_audio.mp3",
        start_sec="00:05:00",
        end_sec="00:10:00"
    )

    assert res["error"] is None
    assert mock_ydl_cls.called
    called_opts = mock_ydl_cls.call_args[0][0]
    assert "download_ranges" in called_opts
    assert called_opts.get("force_keyframes_at_cuts") is False


@patch("os.remove")
@patch("yt_dlp.YoutubeDL")
@patch("os.path.exists", return_value=True)
@patch("os.path.getsize", return_value=2048)
def test_download_full_video_with_range_options(mock_getsize, mock_exists, mock_ydl_cls, mock_remove):
    mock_instance = MagicMock()
    mock_ydl_cls.return_value.__enter__.return_value = mock_instance

    res = download_full_video(
        "https://www.youtube.com/watch?v=mock123",
        output_path="test_video.mp4",
        start_sec="01:00:00",
        end_sec="01:05:00"
    )

    assert res["error"] is None
    assert mock_ydl_cls.called
    called_opts = mock_ydl_cls.call_args[0][0]
    assert "download_ranges" in called_opts
    assert called_opts.get("force_keyframes_at_cuts") is False


def test_get_current_active_video_id():
    from app import get_current_active_video_id
    import streamlit as st

    # 1. Base URL sem slice
    st.session_state.clear()
    assert get_current_active_video_id("https://www.youtube.com/watch?v=mock_unit_vid_999") == "mock_unit_vid_999"

    # 2. Com slice configurado
    st.session_state["input_yt_slice_start"] = "01:29:04"
    st.session_state["input_yt_slice_end"] = "01:32:14"
    assert get_current_active_video_id("https://www.youtube.com/watch?v=mock_unit_vid_999") == "mock_unit_vid_999_t_5344_5534"

    # 3. Com active_video_id explícito na sessão
    st.session_state["active_video_id"] = "custom_slice_123"
    with patch("os.path.exists", return_value=True):
        assert get_current_active_video_id("https://www.youtube.com/watch?v=mock_unit_vid_999") == "custom_slice_123"



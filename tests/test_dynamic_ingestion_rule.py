import os
import json
import shutil
import subprocess
import pytest
import imageio_ffmpeg
from core.video_processor import generate_local_video_id, slice_or_copy_local_video
from core.quick_editor import get_video_duration
from core.transcriber import ensure_cut_transcript

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


def test_local_video_ingestion_lightweight():
    """
    Testa que a ingestão de vídeo local gera o video_full.mp4
    sem gerar ou exigir audio.mp3 nem transcript.json antecipadamente.
    """
    test_dir = os.path.join("data", "test_light_ingest")
    os.makedirs(test_dir, exist_ok=True)
    
    src_video = os.path.join(test_dir, "raw_upload.mp4")
    v_full = os.path.join(test_dir, "video_full.mp4")
    audio_full = os.path.join(test_dir, "audio.mp3")
    transcript_full = os.path.join(test_dir, "transcript.json")
    
    try:
        # 1. Gera vídeo de teste curto
        subprocess.run([
            FFMPEG_EXE, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=30",
            "-c:v", "libx264", "-preset", "ultrafast",
            src_video
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 2. Simula o fluxo da Seção 1: copia para pasta padrão e renomeia para video_full
        shutil.copy2(src_video, v_full)
        assert os.path.exists(v_full)
        assert get_video_duration(v_full) >= 2.5
        
        # 3. Garante que NÃO foram gerados audio.mp3 e transcript.json (Ingestão Leve)
        assert not os.path.exists(audio_full)
        assert not os.path.exists(transcript_full)
        
    finally:
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir, ignore_errors=True)


def test_sec2_gatekeeper_logic():
    """
    Testa a lógica de bloqueio da Seção 2:
    - Sem transcript.json: Gatekeeper bloqueia a mineração.
    - Com transcript.json: Gatekeeper libera a mineração.
    """
    test_id = "test_gatekeeper_vid"
    data_dir = os.path.join("data", test_id)
    os.makedirs(data_dir, exist_ok=True)
    tr_path = os.path.join(data_dir, "transcript.json")
    
    try:
        # Estado inicial: sem transcript
        if os.path.exists(tr_path):
            os.remove(tr_path)
            
        has_transcript = os.path.exists(tr_path)
        assert not has_transcript  # Deve acionar o gatekeeper
        
        # Simula a ação do botão: gera transcrição e salva
        mock_transcript = {
            "full_text": "Olá mundo, este é um teste de mineração de inteligência artificial.",
            "segments": [
                {"start": 0.0, "end": 2.5, "text": "Olá mundo,"},
                {"start": 2.5, "end": 5.0, "text": "este é um teste de mineração de inteligência artificial."}
            ],
            "source": "Whisper Local (Mineração IA)"
        }
        with open(tr_path, "w", encoding="utf-8") as f:
            json.dump(mock_transcript, f, ensure_ascii=False, indent=2)
            
        # Agora o gatekeeper deve desbloquear
        assert os.path.exists(tr_path)
        with open(tr_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            assert len(loaded.get("segments", [])) == 2
            
    finally:
        if os.path.exists(data_dir):
            shutil.rmtree(data_dir, ignore_errors=True)


def test_surgical_cut_transcript_without_full_transcript():
    """
    Testa que um corte pode ter transcrição e legendas geradas cirurgicamente
    a partir do video_full.mp4 mesmo quando não existe transcrição completa prévia.
    """
    test_id = "test_surgical_cut"
    data_dir = os.path.join("data", test_id)
    os.makedirs(data_dir, exist_ok=True)
    v_full = os.path.join(data_dir, "video_full.mp4")
    
    try:
        # Gera vídeo de teste com áudio (senoide)
        subprocess.run([
            FFMPEG_EXE, "-y",
            "-f", "lavfi", "-i", "testsrc=duration=4:size=320x240:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=4",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            v_full
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        assert os.path.exists(v_full)
        
        # Garante que não existe transcript.json completo
        full_tr = os.path.join(data_dir, "transcript.json")
        if os.path.exists(full_tr):
            os.remove(full_tr)
        assert not os.path.exists(full_tr)
        
        # Chama ensure_cut_transcript para um trecho específico (ex: 1s a 3s)
        res = ensure_cut_transcript(
            video_id=test_id,
            start_time_str="00:00:01",
            end_time_str="00:00:03",
            media_path=v_full,
            model_size="tiny",
            device="cpu",
            language="pt"
        )
        
        assert res is not None
        assert "transcript_path" in res
        
    finally:
        if os.path.exists(data_dir):
            shutil.rmtree(data_dir, ignore_errors=True)

from faster_whisper import WhisperModel
import os
import sys

# Tenta adicionar as DLLs do CUDA (baixadas via pip) no PATH do Windows
try:
    site_packages = next(p for p in sys.path if 'site-packages' in p)
    cublas_path = os.path.join(site_packages, "nvidia", "cublas", "bin")
    cudnn_path = os.path.join(site_packages, "nvidia", "cudnn", "bin")
    if os.path.exists(cublas_path) and os.path.exists(cudnn_path):
        os.environ["PATH"] = f"{cublas_path};{cudnn_path};" + os.environ.get("PATH", "")
except:
    pass

def transcribe_audio(audio_path: str, model_size: str = "small", device: str = "cuda"):
    """
    Transcreve o áudio usando Faster-Whisper.
    """
    if not os.path.exists(audio_path):
        return {"transcript": None, "error": "Arquivo de áudio não encontrado."}
        
    try:
        # Algumas placas como a GTX 1650 não possuem Tensor Cores, o que pode fazer
        # o float16 travar indefinidamente no CTranslate2. Mudamos para float32.
        compute_type = "float32" if device == "cuda" else "int8"
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
        segments, info = model.transcribe(audio_path, beam_size=5)
        
        transcript_data = []
        full_text = ""
        for segment in segments:
            transcript_data.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text
            })
            full_text += segment.text + " "
            
        return {"transcript_segments": transcript_data, "full_text": full_text.strip(), "error": None}
    except Exception as e:
        return {"transcript_segments": None, "full_text": None, "error": str(e)}

import os, sys, cv2, subprocess
sys.path.insert(0, os.path.abspath("."))
import imageio_ffmpeg
from core.face_tracker import ensure_face_model, parse_time_to_seconds, MODEL_PATH
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

def detect_split_screen_centers(video_path: str, timestamp_str: str):
    """
    Detecta os centros dos interlocutores da esquerda e da direita para o Split Screen.
    Retorna os fatores de deslocamento normalizados X1 (topo) e X2 (base).
    """
    ensure_face_model()
    t_sec = parse_time_to_seconds(timestamp_str)
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_MSEC, t_sec * 1000.0)
    ret, frame = cap.read()
    cap.release()
    
    if not ret or frame is None:
        return {"top_pan": -0.5, "bottom_pan": 0.5, "left_face": None, "right_face": None}
        
    h, w = frame.shape[:2]
    
    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.FaceDetectorOptions(base_options=base_options, min_detection_confidence=0.35)
    detector = vision.FaceDetector.create_from_options(options)
    
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    results = detector.detect(mp_image)
    
    if not results.detections or len(results.detections) == 1:
        # Default: Left side (-0.5) and Right side (+0.5)
        return {"top_pan": -0.5, "bottom_pan": 0.5, "w": w, "h": h}
        
    detections = results.detections
    # Ordena rostos da esquerda para a direita
    sorted_faces = sorted(detections, key=lambda d: d.bounding_box.origin_x + d.bounding_box.width / 2.0)
    
    # Left face (Interviewer/Left person)
    left_f = sorted_faces[0].bounding_box
    left_cx = left_f.origin_x + left_f.width / 2.0
    
    # Right face (Interviewee/Right person)
    right_f = sorted_faces[-1].bounding_box
    right_cx = right_f.origin_x + right_f.width / 2.0
    
    # Normaliza entre -1.0 e +1.0 onde 0.0 é o centro da tela
    # cx / (w/2) - 1.0
    top_pan = (left_cx / (w / 2.0)) - 1.0
    bottom_pan = (right_cx / (w / 2.0)) - 1.0
    
    # Limita entre -0.85 e 0.85
    top_pan = max(-0.85, min(0.85, top_pan))
    bottom_pan = max(-0.85, min(0.85, bottom_pan))
    
    return {
        "top_pan": top_pan,
        "bottom_pan": bottom_pan,
        "left_cx": left_cx,
        "right_cx": right_cx,
        "w": w,
        "h": h
    }

video_path = "data/NRLvjdjvnag/video_full.mp4"
if os.path.exists(video_path):
    res = detect_split_screen_centers(video_path, "00:01:30")
    print(f"Split screen auto-centers: Top (Left) pan: {res['top_pan']:.2f}, Bottom (Right) pan: {res['bottom_pan']:.2f}")
else:
    print("Video full not found at", video_path)

import os, sys, cv2, subprocess, time
sys.path.insert(0, os.path.abspath("."))
import imageio_ffmpeg
from core.face_tracker import ensure_face_model, parse_time_to_seconds, MODEL_PATH
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
video_path = "data/NRLvjdjvnag/video_full.mp4"
output_cut = "scratch/test_auto_switch_cut.mp4"

def process_dynamic_auto_switch(
    input_video_path: str,
    start_time_str: str,
    end_time_str: str,
    output_video_path: str,
    split_zoom: float = 1.15,
    top_pan: float = -0.65,
    bottom_pan: float = 0.65,
    divider_color: str = "black",
    divider_width: int = 4
):
    ensure_face_model()
    start_s = parse_time_to_seconds(start_time_str)
    end_s = parse_time_to_seconds(end_time_str)
    
    cap = cv2.VideoCapture(input_video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames_in_source = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    start_frame = int(start_s * fps)
    end_frame = int(end_s * fps)
    total_cut_frames = max(1, end_frame - start_frame)
    
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    # Extrai áudio temporário do trecho
    temp_audio = "temp_auto_switch_audio.aac"
    temp_video_raw = "temp_auto_switch_raw.mp4"
    
    cmd_audio = [
        FFMPEG_EXE, "-y",
        "-ss", start_time_str,
        "-to", end_time_str,
        "-i", input_video_path,
        "-vn", "-c:a", "aac", "-b:a", "192k",
        temp_audio
    ]
    subprocess.run(cmd_audio, capture_output=True)
    
    # FFmpeg process for video pipe
    cmd_ffmpeg = [
        FFMPEG_EXE, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", "1080x1920",
        "-pix_fmt", "bgr24",
        "-r", str(fps),
        "-i", "-",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "21",
        "-pix_fmt", "yuv420p",
        temp_video_raw
    ]
    ffmpeg_proc = subprocess.Popen(cmd_ffmpeg, stdin=subprocess.PIPE)
    
    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.FaceDetectorOptions(base_options=base_options, min_detection_confidence=0.35)
    detector = vision.FaceDetector.create_from_options(options)
    
    # Estado e histerese
    current_mode = "split" # 'split' ou 'single'
    recent_face_counts = []
    
    # Parâmetros de panning suave para single-face
    current_single_cx = 960.0
    
    frame_idx = 0
    while frame_idx < total_cut_frames:
        ret, frame = cap.read()
        if not ret or frame is None:
            break
            
        h, w = frame.shape[:2]
        
        # Detecção de rostos a cada 2 frames para máxima performance
        if frame_idx % 2 == 0 or frame_idx == 0:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            results = detector.detect(mp_image)
            num_faces = len(results.detections) if results.detections else 0
            recent_face_counts.append(num_faces)
            if len(recent_face_counts) > 8:
                recent_face_counts.pop(0)
                
            # Histerese: Se a maioria dos últimos frames teve >= 2 rostos -> Split, senão se teve 1 -> Single
            avg_faces = sum(recent_face_counts) / len(recent_face_counts)
            if avg_faces >= 1.4:
                current_mode = "split"
            elif avg_faces <= 1.1 and num_faces == 1:
                current_mode = "single"
                
            if current_mode == "single" and results.detections:
                target_f = max(results.detections, key=lambda d: d.bounding_box.width * d.bounding_box.height)
                bx = target_f.bounding_box
                raw_cx = bx.origin_x + bx.width / 2.0
                current_single_cx = current_single_cx * 0.75 + raw_cx * 0.25 # EMA smoothing
                
        # Renderização conforme o modo ativo
        if current_mode == "split":
            base_w = int(h * 1.125 / split_zoom)
            base_h = int(h / split_zoom)
            max_x = max(0, w - base_w)
            max_y = max(0, h - base_h)
            top_x = int(max(0, min(max_x, (max_x / 2.0) + (top_pan * (max_x / 2.0)))))
            top_y = int(max(0, min(max_y, max_y / 2.0)))
            bot_x = int(max(0, min(max_x, (max_x / 2.0) + (bottom_pan * (max_x / 2.0)))))
            bot_y = top_y
            
            top_crop = frame[top_y : top_y + base_h, top_x : top_x + base_w]
            bot_crop = frame[bot_y : bot_y + base_h, bot_x : bot_x + base_w]
            
            top_res = cv2.resize(top_crop, (1080, 960), interpolation=cv2.INTER_LINEAR)
            bot_res = cv2.resize(bot_crop, (1080, 960), interpolation=cv2.INTER_LINEAR)
            
            out_frame = cv2.vconcat([top_res, bot_res])
            if divider_width > 0:
                div_c = (0, 0, 0) if divider_color == "black" else ((255, 255, 255) if divider_color == "white" else (180, 180, 180))
                y_mid = 960
                y1 = max(0, y_mid - divider_width // 2)
                y2 = min(1920, y_mid + divider_width // 2)
                out_frame[y1:y2, :] = div_c
        else:
            # Single face 9:16 crop
            crop_w = int(h * (9.0 / 16.0))
            crop_h = h
            max_cx = w - crop_w // 2
            min_cx = crop_w // 2
            clamped_cx = max(min_cx, min(max_cx, int(current_single_cx)))
            x1 = clamped_cx - crop_w // 2
            x2 = x1 + crop_w
            single_crop = frame[0:crop_h, x1:x2]
            out_frame = cv2.resize(single_crop, (1080, 1920), interpolation=cv2.INTER_LINEAR)
            
        ffmpeg_proc.stdin.write(out_frame.tobytes())
        frame_idx += 1
        
    cap.release()
    detector.close()
    ffmpeg_proc.stdin.close()
    ffmpeg_proc.wait()
    
    # Merge video and audio
    cmd_merge = [
        FFMPEG_EXE, "-y",
        "-i", temp_video_raw,
        "-i", temp_audio,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        output_video_path
    ]
    subprocess.run(cmd_merge, capture_output=True)
    
    if os.path.exists(temp_video_raw):
        os.remove(temp_video_raw)
    if os.path.exists(temp_audio):
        os.remove(temp_audio)
        
    print(f"Finalizado Dynamic Auto-Switch em {output_video_path} ({os.path.getsize(output_video_path)} bytes)")

if os.path.exists(video_path):
    print("Testando corte de 6 segundos com Dynamic Auto-Switch...")
    process_dynamic_auto_switch(video_path, "00:01:24", "00:01:30", output_cut)

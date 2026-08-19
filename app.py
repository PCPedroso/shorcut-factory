import streamlit as st
import os
import re
import json
from core.extractor import download_audio, get_video_metadata
from core.transcriber import transcribe_audio
from core.analyzer import analyze_transcript
from urllib.parse import urlparse, parse_qs

st.set_page_config(page_title="Fábrica de Cortes", layout="wide")

def get_video_id(url):
    query = urlparse(url)
    if query.hostname == 'youtu.be': return query.path[1:]
    if query.hostname in ('www.youtube.com', 'youtube.com'):
        if query.path == '/watch': return parse_qs(query.query)['v'][0]
        if query.path[:7] == '/embed/': return query.path.split('/')[2]
        if query.path[:3] == '/v/': return query.path.split('/')[2]
    return None

st.title("✂️ ViralCut - Fábrica de Cortes")

# Barra Lateral (Configurações)
st.sidebar.header("Configurações")
device_option = st.sidebar.selectbox("Dispositivo de Processamento", ["cpu", "cuda"], index=0)
model_size = st.sidebar.selectbox("Tamanho do Modelo Whisper", ["tiny", "small", "medium", "large-v3"], index=1)

st.sidebar.markdown("---")
st.sidebar.subheader("Modelo de IA (Ollama)")
ollama_model = st.sidebar.selectbox(
    "Modelo:",
    ["llama3", "mistral", "qwen2.5", "llama3.1", "gemma2"],
    index=0,
    help="Para usar mistral ou qwen2.5 rode: ollama pull mistral"
)

# Estado da sessão
if 'transcription_done' not in st.session_state:
    st.session_state.transcription_done = False
if 'full_text' not in st.session_state:
    st.session_state.full_text = ""
if 'segments' not in st.session_state:
    st.session_state.segments = []
if 'ai_results' not in st.session_state:
    st.session_state.ai_results = ""

video_url = st.text_input("Cole a URL do vídeo do YouTube:")

if st.button("Iniciar Processamento"):
    if not video_url:
        st.warning("Por favor, insira uma URL válida.")
    else:
        video_id = get_video_id(video_url)
        if not video_id:
            st.error("URL do YouTube inválida.")
        else:
            data_dir = os.path.join("data", video_id)
            os.makedirs(data_dir, exist_ok=True)
            transcript_file = os.path.join(data_dir, "transcript.json")
            audio_path = os.path.join(data_dir, "audio.mp3")
            
            # CACHE: Verifica se já temos a transcrição pronta
            if os.path.exists(transcript_file):
                st.success("✅ Cache encontrado! Carregando transcrição salva...")
                with open(transcript_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    st.session_state.full_text = data["full_text"]
                    st.session_state.segments = data["segments"]
                st.session_state.transcription_done = True
            else:
                st.info("Iniciando extração do YouTube...")
                
                # Passo 1: Metadados
                with st.spinner("Extraindo metadados e heatmap..."):
                    meta = get_video_metadata(video_url)
                    if meta.get("error"):
                        st.error(f"Erro ao extrair dados: {meta['error']}")
                    else:
                        st.success(f"Vídeo encontrado: {meta['title']}")
                        
                        # CACHE: Verifica se já baixou o áudio
                        if os.path.exists(audio_path):
                            st.success("Áudio já baixado anteriormente. Pulando download.")
                            audio_res = {"path": audio_path, "error": None}
                        else:
                            with st.spinner("Baixando áudio..."):
                                audio_res = download_audio(video_url, output_path=audio_path)
                                
                        if audio_res.get("error"):
                            st.error(f"Erro no download: {audio_res['error']}")
                        else:
                            st.success("Áudio baixado/carregado com sucesso.")
                            
                            # Passo 3: Transcrição
                            with st.spinner(f"Transcrevendo áudio na {device_option.upper()}..."):
                                transcribe_res = transcribe_audio(
                                    audio_res["path"], 
                                    model_size=model_size, 
                                    device=device_option
                                )
                                
                                if transcribe_res.get("error"):
                                    st.error(f"Erro na transcrição: {transcribe_res['error']}")
                                else:
                                    st.success("Transcrição concluída!")
                                    st.session_state.transcription_done = True
                                    st.session_state.full_text = transcribe_res["full_text"]
                                    st.session_state.segments = transcribe_res["transcript_segments"]
                                    
                                    # Salvar no cache
                                    with open(transcript_file, "w", encoding="utf-8") as f:
                                        json.dump({
                                            "full_text": st.session_state.full_text,
                                            "segments": st.session_state.segments
                                        }, f, ensure_ascii=False, indent=4)

if st.session_state.transcription_done:
    def format_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    formatted_transcript = ""
    for seg in st.session_state.segments:
        formatted_transcript += f"[{format_time(seg['start'])} - {format_time(seg['end'])}] {seg['text']}\n"

    with st.expander("Ver Transcrição Completa"):
        st.text_area("Texto:", value=formatted_transcript, height=300)
    
    st.header("2. Inteligência Temática (Llama 3)")
    st.markdown("Use a Inteligência Artificial para extrair os tempos exatos para cortes.")
    
    # Construir lista de chunks estruturada (com start/end em segundos)
    def build_chunks_list(segments, chunk_seconds=60):
        """Retorna lista de dicts com start, end, text para cada chunk de 1 minuto."""
        if not segments:
            return []
        chunks = []
        chunk_start = segments[0]['start']
        chunk_texts = []
        
        for seg in segments:
            chunk_texts.append(seg['text'].strip())
            if seg['end'] - chunk_start >= chunk_seconds:
                chunks.append({
                    'start': chunk_start,
                    'end': seg['end'],
                    'text': ' '.join(chunk_texts)
                })
                chunk_start = seg['end']
                chunk_texts = []
        
        if chunk_texts:
            chunks.append({
                'start': chunk_start,
                'end': segments[-1]['end'],
                'text': ' '.join(chunk_texts)
            })
        return chunks

    chunks_list = build_chunks_list(st.session_state.segments)
    chunked_transcript = "\n".join(
        f"[{format_time(c['start'])} - {format_time(c['end'])}] {c['text']}"
        for c in chunks_list
    )

    # --- Seção 2A: Seletor Manual ---
    st.header("2. Seleção de Cortes")
    
    tab_manual, tab_ai = st.tabs(["🖱️ Seleção Manual", "🧠 Sugestão por IA (Llama 3)"])
    
    with tab_manual:
        st.markdown("Selecione o chunk de **início** e o chunk de **fim** do trecho que deseja cortar.")
        
        if chunks_list:
            chunk_labels = [
                f"[{format_time(c['start'])} - {format_time(c['end'])}]  {c['text'][:80]}..."
                for c in chunks_list
            ]
            
            col_s, col_e = st.columns(2)
            idx_start = col_s.selectbox("Chunk de Início:", range(len(chunks_list)),
                                         format_func=lambda i: chunk_labels[i], key="manual_start")
            idx_end   = col_e.selectbox("Chunk de Fim:",   range(len(chunks_list)),
                                         format_func=lambda i: chunk_labels[i],
                                         index=min(len(chunks_list)-1, 9), key="manual_end")
            
            if idx_end >= idx_start:
                start_s = chunks_list[idx_start]['start']
                end_s   = chunks_list[idx_end]['end']
                st.success(f"Trecho selecionado: **{format_time(start_s)}** → **{format_time(end_s)}** "
                           f"({(end_s - start_s)/60:.1f} min)")
                if st.button("✂️ Usar este trecho na Fábrica de Cortes", key="btn_manual"):
                    st.session_state.selected_cut = (format_time(start_s), format_time(end_s), "Corte Manual")
                    st.rerun()
            else:
                st.warning("O chunk de fim deve ser igual ou posterior ao de início.")

    with tab_ai:
        st.markdown("Use a IA para sugerir blocos temáticos ou ganchos virais.")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🧠 Extrair Blocos (10 min)", key="btn_blocos"):
                with st.spinner("Fase 1: identificando temas... (aguarde, pode demorar 1-2 min)"):
                    res = analyze_transcript(
                        chunked_transcript, "blocos",
                        model=ollama_model,
                        chunks_list=chunks_list
                    )
                    if res.get("error"):
                        st.error(f"Erro ao contatar o Ollama: {res['error']}")
                    else:
                        st.session_state.ai_cortes = res.get("cortes", [])
                        st.session_state.ai_raw = res.get("raw", "")
                        
        with col2:
            if st.button("🔥 Extrair Ganchos Virais", key="btn_ganchos"):
                with st.spinner("Fase 1: identificando ganchos... (aguarde, pode demorar 1-2 min)"):
                    res = analyze_transcript(
                        chunked_transcript, "ganchos",
                        model=ollama_model,
                        chunks_list=chunks_list
                    )
                    if res.get("error"):
                        st.error(f"Erro ao contatar o Ollama: {res['error']}")
                    else:
                        st.session_state.ai_cortes = res.get("cortes", [])
                        st.session_state.ai_raw = res.get("raw", "")
                        
        if 'ai_cortes' in st.session_state and st.session_state.ai_cortes:
            st.markdown("### 🎬 Cortes Identificados pela IA:")
            
            for idx, c in enumerate(st.session_state.ai_cortes):
                with st.container():
                    col_info, col_btn = st.columns([4, 1])
                    with col_info:
                        badge = f"**{c.get('series_label', f'Corte {idx+1}')}**"
                        hook_badge = " 🔗 *(Com Gancho para Próximo Vídeo)*" if c.get('has_hook') else ""
                        st.markdown(f"{badge}: `[{c['start']} - {c['end']}]` **{c['title']}**{hook_badge}")
                        if c.get('notes'):
                            st.caption(c['notes'])
                    with col_btn:
                        if st.button("✂️ Usar", key=f"btn_use_ai_{idx}"):
                            st.session_state.selected_cut = (c['start'], c['end'], c['title'])
                            st.rerun()
                    st.divider()

            options = [(c['start'], c['end'], c['title']) for c in st.session_state.ai_cortes]
            st.session_state.selected_cut = st.selectbox(
                "Ou escolha no menu suspenso:",
                options=options,
                format_func=lambda x: f"[{x[0]} - {x[1]}] {x[2]}"
            )
        
        if 'ai_raw' in st.session_state and st.session_state.ai_raw:
            with st.expander("🔍 Detalhes da Análise Semântica (Log da IA)"):
                st.code(st.session_state.ai_raw)
                
        if 'ai_cortes' in st.session_state and not st.session_state.ai_cortes:
            st.warning("A IA não identificou cortes. Use a aba de Seleção Manual ou tente novamente.")

    st.markdown("---")
    st.header("3. Fábrica de Cortes (Recorte Final)")
    st.markdown("Baixe o vídeo real usando o trecho selecionado.")
    
    # Preenchimento automático se um corte foi selecionado
    default_start = ""
    default_end = ""
    if 'selected_cut' in st.session_state and st.session_state.selected_cut:
        default_start = st.session_state.selected_cut[0]
        default_end = st.session_state.selected_cut[1]
    
    col_start, col_end = st.columns(2)
    start_time = col_start.text_input("Tempo Inicial", value=default_start, placeholder="00:01:25")
    end_time = col_end.text_input("Tempo Final", value=default_end, placeholder="00:02:30")
    
    if st.button("✂️ Gerar Corte Viral"):
        if not start_time or not end_time:
            st.warning("Preencha o tempo inicial e final.")
        else:
            from core.video_processor import download_full_video, cut_video
            
            video_id = get_video_id(video_url)
            data_dir = os.path.join("data", video_id) if video_id else "data"
            os.makedirs(data_dir, exist_ok=True)
            video_full_path = os.path.join(data_dir, "video_full.mp4")
            corte_output_path = os.path.join(data_dir, "corte_viral.mp4")
            
            # Cache do vídeo final
            if not os.path.exists(video_full_path):
                with st.spinner("Baixando vídeo completo em alta qualidade..."):
                    video_res = download_full_video(video_url, video_full_path)
            else:
                st.success("Vídeo completo encontrado no cache!")
                video_res = {"path": video_full_path, "error": None}
                
            if video_res.get("error"):
                st.error(f"Erro ao baixar vídeo: {video_res['error']}")
            else:
                with st.spinner("Processando o corte (isso pode demorar dependendo da sua CPU)..."):
                    cut_res = cut_video(video_res["path"], start_time, end_time, corte_output_path)
                    if cut_res.get("error"):
                        st.error(f"Erro ao cortar: {cut_res['error']}")
                    else:
                        st.success("Corte gerado com sucesso!")
                        st.video(corte_output_path)
                        
                        with open(corte_output_path, "rb") as file:
                            st.download_button(
                                label="💾 Baixar Arquivo MP4",
                                data=file,
                                file_name="corte_viral.mp4",
                                mime="video/mp4"
                            )

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

    # --- Seção 2: Seleção de Cortes e Compositor ---
    st.header("2. Seleção e Composição de Cortes")
    
    tab_composer, tab_series, tab_shorts, tab_manual = st.tabs([
        "🧩 Compositor de Pautas (Micro-Assuntos)",
        "💡 Séries Sugeridas (10+ min)",
        "🔥 Ganchos Virais (Shorts)",
        "🖱️ Seleção Manual (Chunks)"
    ])
    
    # ── TAB 1: COMPOSITOR DE PAUTAS ───────────────────────────────────────────
    with tab_composer:
        st.markdown(
            "Em entrevistas e podcasts dinâmicos, repórteres mudam de assunto a cada 1-4 minutos. "
            "Use a IA para mapear todas as pautas e selecione múltiplas para compor cortes de **10+ minutos**."
        )
        
        col_act1, col_act2 = st.columns([1, 2])
        with col_act1:
            if st.button("🔍 Mapear Todas as Pautas (IA)", key="btn_map_pautas"):
                with st.spinner("Mapeando perguntas e mudanças de pauta com IA..."):
                    res = analyze_transcript(
                        chunked_transcript, "pautas",
                        model=ollama_model,
                        chunks_list=chunks_list
                    )
                    if res.get("error"):
                        st.error(f"Erro no Ollama: {res['error']}")
                    else:
                        st.session_state.pautas = res.get("pautas", [])
                        st.session_state.bundles = res.get("bundles", [])
                        st.session_state.ai_raw = res.get("raw", "")
                        st.rerun()

        if 'pautas' in st.session_state and st.session_state.pautas:
            pautas = st.session_state.pautas
            st.markdown(f"### 📋 Pautas Detectadas ({len(pautas)} encontradas):")
            st.caption("Marque as caixas das pautas que deseja juntar no corte final:")

            selected_pauta_ids = []
            
            for p in pautas:
                label = f"**[{p['start']} - {p['end']}]** `({p['duration_label']})` — {p['title']}"
                checked = st.checkbox(label, key=f"chk_pauta_{p['id']}")
                if checked:
                    selected_pauta_ids.append(p)

            # Painel Dinâmico de Composição (Sincronização em Tempo Real)
            if selected_pauta_ids:
                total_composed_s = sum(x['duration_s'] for x in selected_pauta_ids)
                total_min = total_composed_s / 60
                earliest_start = min(selected_pauta_ids, key=lambda x: x['start_s'])['start']
                latest_end = max(selected_pauta_ids, key=lambda x: x['end_s'])['end']
                composed_title = f"{selected_pauta_ids[0]['title']} (+ {len(selected_pauta_ids)-1} pautas)"

                # Sincronização automática e instantânea com a Fábrica de Cortes (Seção 3)
                st.session_state.final_start_time = earliest_start
                st.session_state.final_end_time = latest_end
                st.session_state.final_corte_title = composed_title
                st.session_state.cut_ready_banner = f"✅ Composição ativa: [{earliest_start} → {latest_end}] ({composed_title})"

                st.markdown("---")
                st.markdown("#### ⏱️ Resumo da Composição Selecionada *(Sincronizado Automaticamente)*:")
                
                col_m1, col_m2, col_m3 = st.columns(3)
                col_m1.metric("Pautas Selecionadas", f"{len(selected_pauta_ids)}")
                col_m2.metric("Duração Total Composta", f"{int(total_min)}m {int(total_composed_s%60):02d}s")
                col_m3.metric("Intervalo Contínuo", f"{earliest_start} → {latest_end}")

                if total_min >= 10.0:
                    st.success(f"✅ Meta de 10+ minutos atingida ({total_min:.1f} min)! Campos da Seção 3 preenchidos automaticamente.")
                else:
                    st.info(f"⏳ Duração atual: {total_min:.1f} min. Faltam {(10.0 - total_min):.1f} min para atingir 10 minutos.")
            else:
                if 'cut_ready_banner' in st.session_state:
                    st.session_state.cut_ready_banner = ""

    # ── TAB 2: SÉRIES AUTOMÁTICAS ─────────────────────────────────────────────
    with tab_series:
        st.markdown("Cortes automáticos de **10+ minutos** sugeridos agrupando sequências de pautas.")
        
        if st.button("🧠 Gerar Séries Automáticas (10 min)", key="btn_series"):
            with st.spinner("Agrupando pautas em séries de 10+ min..."):
                res = analyze_transcript(
                    chunked_transcript, "blocos",
                    model=ollama_model,
                    chunks_list=chunks_list
                )
                if res.get("error"):
                    st.error(f"Erro no Ollama: {res['error']}")
                else:
                    st.session_state.pautas = res.get("pautas", [])
                    st.session_state.bundles = res.get("bundles", [])
                    st.session_state.ai_raw = res.get("raw", "")
                    st.rerun()

        if 'bundles' in st.session_state and st.session_state.bundles:
            for idx, b in enumerate(st.session_state.bundles):
                with st.container():
                    col_info, col_btn = st.columns([4, 1])
                    with col_info:
                        badge = f"**{b.get('series_label', f'Vídeo {idx+1}')}**"
                        hook_tag = " 🔗 *(Com Gancho)*" if b.get('has_hook') else ""
                        st.markdown(f"{badge}: `[{b['start']} - {b['end']}]` **{b['title']}** {hook_tag}")
                        st.caption(f"⏱️ Duração: {b.get('duration_label', '')} | {b.get('notes', '')}")
                        if b.get('pautas_incluidas'):
                            with st.expander("Ver pautas inclusas neste vídeo"):
                                for pt in b['pautas_incluidas']:
                                    st.write(f"• {pt}")
                    with col_btn:
                        if st.button("✂️ Usar", key=f"btn_use_bundle_{idx}"):
                            st.session_state.final_start_time = b['start']
                            st.session_state.final_end_time = b['end']
                            st.session_state.final_corte_title = b['title']
                            st.session_state.cut_ready_banner = f"✅ Série selecionada: [{b['start']} → {b['end']}] ({b['title']})"
                            st.rerun()
                    st.divider()

    # ── TAB 3: GANCHOS VIRAIS (SHORTS) ────────────────────────────────────────
    with tab_shorts:
        st.markdown("Momentos curtos de alto impacto (45 a 60 segundos) para **YouTube Shorts / TikTok**.")
        
        if st.button("🔥 Extrair Ganchos Virais (< 60s)", key="btn_shorts"):
            with st.spinner("Identificando declarações polêmicas e momentos de impacto..."):
                res = analyze_transcript(
                    chunked_transcript, "ganchos",
                    model=ollama_model,
                    chunks_list=chunks_list
                )
                if res.get("error"):
                    st.error(f"Erro no Ollama: {res['error']}")
                else:
                    st.session_state.shorts = res.get("cortes", [])
                    st.session_state.ai_raw = res.get("raw", "")
                    st.rerun()

        if 'shorts' in st.session_state and st.session_state.shorts:
            for idx, s in enumerate(st.session_state.shorts):
                with st.container():
                    col_info, col_btn = st.columns([4, 1])
                    with col_info:
                        st.markdown(f"**{s.get('series_label', f'Short {idx+1}')}**: `[{s['start']} - {s['end']}]` **{s['title']}**")
                        st.caption(s.get('notes', ''))
                    with col_btn:
                        if st.button("✂️ Usar", key=f"btn_use_short_{idx}"):
                            st.session_state.final_start_time = s['start']
                            st.session_state.final_end_time = s['end']
                            st.session_state.final_corte_title = s['title']
                            st.session_state.cut_ready_banner = f"✅ Short selecionado: [{s['start']} → {s['end']}] ({s['title']})"
                            st.rerun()
                    st.divider()

    # ── TAB 4: SELEÇÃO MANUAL ────────────────────────────────────────────────
    with tab_manual:
        st.markdown("Navegue minuto a minuto pelos chunks de áudio e selecione início e fim:")
        if chunks_list:
            chunk_labels = [
                f"[{format_time(c['start'])} - {format_time(c['end'])}]  {c['text'][:80]}..."
                for c in chunks_list
            ]
            col_s, col_e = st.columns(2)
            idx_start = col_s.selectbox("Chunk de Início:", range(len(chunks_list)),
                                         format_func=lambda i: chunk_labels[i], key="manual_start")
            idx_end = col_e.selectbox("Chunk de Fim:", range(len(chunks_list)),
                                       format_func=lambda i: chunk_labels[i],
                                       index=min(len(chunks_list)-1, 9), key="manual_end")
            
            if idx_end >= idx_start:
                start_s = chunks_list[idx_start]['start']
                end_s = chunks_list[idx_end]['end']
                st.success(f"Trecho: **{format_time(start_s)}** → **{format_time(end_s)}** ({(end_s - start_s)/60:.1f} min)")
                if st.button("✂️ Usar este trecho na Fábrica de Cortes", key="btn_manual"):
                    st.session_state.final_start_time = format_time(start_s)
                    st.session_state.final_end_time = format_time(end_s)
                    st.session_state.final_corte_title = "Corte Manual"
                    st.session_state.cut_ready_banner = f"✅ Corte manual: [{format_time(start_s)} → {format_time(end_s)}]"
                    st.rerun()

    if 'ai_raw' in st.session_state and st.session_state.ai_raw:
        with st.expander("🔍 Detalhes do Log da IA (Debug)"):
            st.code(st.session_state.ai_raw)

    st.markdown("---")
    st.header("3. Fábrica de Cortes (Recorte Final)")
    st.markdown("Baixe o vídeo real usando o trecho selecionado.")
    
    if 'cut_ready_banner' in st.session_state and st.session_state.cut_ready_banner:
        st.success(st.session_state.cut_ready_banner)
    
    if 'final_start_time' not in st.session_state:
        st.session_state.final_start_time = ""
    if 'final_end_time' not in st.session_state:
        st.session_state.final_end_time = ""

    col_start, col_end = st.columns(2)
    start_time = col_start.text_input("Tempo Inicial (HH:MM:SS)", key="final_start_time", placeholder="00:00:00")
    end_time = col_end.text_input("Tempo Final (HH:MM:SS)", key="final_end_time", placeholder="00:10:00")

    
    if st.button("✂️ Gerar Corte Viral", type="primary"):
        if not start_time or not end_time:
            st.warning("Preencha o tempo inicial e final.")
        else:
            import importlib
            import core.video_processor
            importlib.reload(core.video_processor)
            from core.video_processor import download_full_video, cut_video, get_video_resolution
            
            video_id = get_video_id(video_url)
            data_dir = os.path.join("data", video_id) if video_id else "data"
            os.makedirs(data_dir, exist_ok=True)
            video_full_path = os.path.join(data_dir, "video_full.mp4")
            corte_output_path = os.path.join(data_dir, "corte_viral.mp4")
            
            # Detecta se o vídeo no cache é de baixa resolução (< 720p) e força o download em 1080p
            need_download = not os.path.exists(video_full_path)
            if os.path.exists(video_full_path):
                current_res = get_video_resolution(video_full_path)
                try:
                    h = int(current_res.split('x')[1])
                    if h < 720:
                        st.info(f"🔄 Cache antigo detectado em baixa resolução ({current_res}). Baixando automaticamente em 1080p Full HD...")
                        if os.path.exists(video_full_path):
                            os.remove(video_full_path)
                        need_download = True
                except Exception:
                    pass

            if need_download:
                with st.spinner("Baixando vídeo original na máxima resolução disponível (1080p Full HD)..."):
                    video_res = download_full_video(video_url, video_full_path)
            else:
                current_res = get_video_resolution(video_full_path)
                st.success(f"Vídeo em alta qualidade encontrado no cache ({current_res})!")
                video_res = {"path": video_full_path, "error": None}
                
            if video_res.get("error"):
                st.error(f"Erro ao baixar vídeo: {video_res['error']}")
            else:
                with st.spinner(f"Processando corte [{start_time} → {end_time}] em alta qualidade..."):
                    cut_res = cut_video(video_res["path"], start_time, end_time, corte_output_path)
                    if cut_res.get("error"):
                        st.error(f"Erro ao cortar: {cut_res['error']}")
                    else:
                        st.success(f"🎉 Corte gerado com sucesso em alta qualidade! ({get_video_resolution(corte_output_path)})")
                        st.video(corte_output_path)
                        
                        with open(corte_output_path, "rb") as file:
                            st.download_button(
                                label="💾 Baixar Arquivo MP4 em Alta Qualidade",
                                data=file,
                                file_name="corte_viral.mp4",
                                mime="video/mp4"
                            )

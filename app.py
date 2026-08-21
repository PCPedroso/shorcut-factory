import streamlit as st
import os
import re
import json
import importlib
from urllib.parse import urlparse, parse_qs

import core.extractor
import core.transcriber
import core.analyzer
import core.video_processor
import core.face_tracker
import core.library_manager

importlib.reload(core.extractor)
importlib.reload(core.transcriber)
importlib.reload(core.analyzer)
importlib.reload(core.video_processor)
importlib.reload(core.face_tracker)
importlib.reload(core.library_manager)


from core.extractor import download_audio, get_video_metadata
from core.transcriber import transcribe_audio, fetch_youtube_transcript
from core.analyzer import analyze_transcript
from core.video_processor import download_full_video, cut_video, get_video_resolution
from core.library_manager import get_library, add_or_update_video_in_library, remove_video_from_library


st.set_page_config(page_title="Fábrica de Cortes", layout="wide")

def get_video_id(url):
    if not url:
        return None
    query = urlparse(url)
    if query.hostname == 'youtu.be': return query.path[1:]
    if query.hostname in ('www.youtube.com', 'youtube.com'):
        if query.path == '/watch': return parse_qs(query.query).get('v', [None])[0]
        if query.path[:7] == '/embed/': return query.path.split('/')[2]
        if query.path[:3] == '/v/': return query.path.split('/')[2]
    return None

st.title("✂️ ViralCut - Fábrica de Cortes")

def load_video_saved_artifacts(video_id: str):
    """Carrega todas as ações e análises salvas individualmente para o vídeo."""
    if not video_id:
        return
    v_dir = os.path.join("data", video_id)
    
    # 1. Transcrição
    t_file = os.path.join(v_dir, "transcript.json")
    if os.path.exists(t_file):
        try:
            with open(t_file, "r", encoding="utf-8") as f:
                t_data = json.load(f)
                st.session_state.full_text = t_data.get("full_text", "")
                st.session_state.segments = t_data.get("segments", [])
                st.session_state.transcript_source = t_data.get("source", "YouTube Oficial")
                st.session_state.transcription_done = True
        except Exception:
            pass
            
    # 2. Pautas Mapeadas
    p_file = os.path.join(v_dir, "pautas.json")
    if os.path.exists(p_file):
        try:
            with open(p_file, "r", encoding="utf-8") as f:
                p_data = json.load(f)
                st.session_state.pautas = p_data.get("pautas", []) if isinstance(p_data, dict) else p_data
        except Exception:
            st.session_state.pautas = []
    else:
        st.session_state.pautas = []

    # 3. Séries (10+ min)
    s_file = os.path.join(v_dir, "series.json")
    if os.path.exists(s_file):
        try:
            with open(s_file, "r", encoding="utf-8") as f:
                st.session_state.bundles = json.load(f)
        except Exception:
            st.session_state.bundles = []
    else:
        st.session_state.bundles = []

    # 4. Ganchos Virais & Pequenos Cortes (Shorts / Reels)
    sh_file = os.path.join(v_dir, "shorts.json")
    if os.path.exists(sh_file):
        try:
            with open(sh_file, "r", encoding="utf-8") as f:
                st.session_state.shorts = json.load(f)
        except Exception:
            st.session_state.shorts = []
    else:
        st.session_state.shorts = []

    # 5. Histórico de Passos / Cortes Montados
    steps_file = os.path.join(v_dir, "saved_steps.json")
    if os.path.exists(steps_file):
        try:
            with open(steps_file, "r", encoding="utf-8") as f:
                st.session_state.saved_steps = json.load(f)
        except Exception:
            st.session_state.saved_steps = []
    else:
        st.session_state.saved_steps = []


# Barra Lateral (Biblioteca & Configurações)
st.sidebar.header("📚 Biblioteca de Vídeos")

library_videos = get_library()
if library_videos:
    st.sidebar.caption(f"**{len(library_videos)}** vídeos registrados")
    for v in library_videos:
        v_title = v.get("title", "Vídeo sem título")
        v_date = v.get("upload_date", "Data N/D")
        v_id = v.get("video_id")
        
        with st.sidebar.expander(f"🎬 {v_title[:35]}...", expanded=False):
            st.markdown(f"**Título:** {v_title}")
            st.markdown(f"📅 **Lançado em:** `{v_date}`")
            if v.get("added_at"):
                st.caption(f"➕ Adicionado: {v['added_at']}")
            
            col_l1, col_l2 = st.columns(2)
            with col_l1:
                if st.button("📥 Abrir", key=f"btn_load_{v_id}", use_container_width=True):
                    v_url = v.get("url", f"https://www.youtube.com/watch?v={v_id}")
                    st.session_state.video_url = v_url
                    st.session_state.input_yt_url = v_url
                    load_video_saved_artifacts(v_id)
                    st.rerun()

            with col_l2:
                if st.button("🗑️ Excluir", key=f"btn_del_{v_id}", use_container_width=True):
                    remove_video_from_library(v_id, delete_folder=True)
                    if st.session_state.get("video_url") == v.get("url") or st.session_state.get("input_yt_url") == v.get("url"):
                        st.session_state.transcription_done = False
                        st.session_state.full_text = ""
                        st.session_state.segments = []
                        st.session_state.pautas = []
                        st.session_state.bundles = []
                        st.session_state.shorts = []
                        st.session_state.saved_steps = []
                        st.session_state.video_url = ""
                        st.session_state.input_yt_url = ""
                    st.rerun()
else:
    st.sidebar.info("Nenhum vídeo registrado ainda. Insira uma URL abaixo para começar!")

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Configurações")
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
if 'video_url' not in st.session_state:
    st.session_state.video_url = ""
if 'input_yt_url' not in st.session_state:
    st.session_state.input_yt_url = st.session_state.video_url

# Seção 1
st.header("1. Ingestão e Transcrição do Vídeo")
video_url = st.text_input("Cole a URL do vídeo do YouTube:", key="input_yt_url")

if st.button("🚀 Processar Vídeo / Atualizar", type="primary"):
    if not video_url:
        st.warning("Por favor, insira uma URL válida.")
    else:
        st.session_state.video_url = video_url
        video_id = get_video_id(video_url)
        if not video_id:
            st.error("URL do YouTube inválida.")
        else:
            data_dir = os.path.join("data", video_id)
            os.makedirs(data_dir, exist_ok=True)
            transcript_file = os.path.join(data_dir, "transcript.json")
            audio_path = os.path.join(data_dir, "audio.mp3")
            
            # Passo 1: Extrai e Registra Metadados na Biblioteca
            with st.spinner("Buscando informações e metadados oficiais do vídeo..."):
                meta = get_video_metadata(video_url)
                v_title = meta.get("title") or f"Vídeo {video_id}"
                v_date = meta.get("upload_date")
                v_thumb = meta.get("thumbnail")
                v_dur = meta.get("duration")

                add_or_update_video_in_library(
                    video_id=video_id,
                    title=v_title,
                    upload_date_raw=v_date,
                    url=video_url,
                    thumbnail_url=v_thumb,
                    duration_sec=v_dur
                )

            # CACHE: Verifica se já temos a transcrição pronta
            if os.path.exists(transcript_file):
                st.success("✅ Cache encontrado! Carregando transcrição e histórico salvo...")
                load_video_saved_artifacts(video_id)
            else:
                st.info("Iniciando extração do YouTube...")
                if meta.get("title"):
                    st.success(f"🎬 Vídeo: **{meta['title']}** (Publicado em: `{meta.get('upload_date')}`) ")

                # Passo 2: Transcrição (Tenta legendas oficiais do YouTube primeiro, fallback para Whisper)
                with st.spinner("Buscando transcrição oficial do YouTube (alta precisão e fidelidade)..."):
                    transcribe_res = fetch_youtube_transcript(video_id)
                    
                    if transcribe_res.get("transcript_segments"):
                        st.success(f"⚡ Transcrição oficial do YouTube carregada ({len(transcribe_res['transcript_segments'])} segmentos)! Máxima precisão.")
                    else:
                        st.info("Legendas oficiais não encontradas no YouTube. Processando áudio via Whisper local...")
                        if os.path.exists(audio_path):
                            audio_res = {"path": audio_path, "error": None}
                        else:
                            with st.spinner("Baixando áudio para transcrição local..."):
                                audio_res = download_audio(video_url, output_path=audio_path)
                                
                        if audio_res.get("error"):
                            st.error(f"Erro no download: {audio_res['error']}")
                            transcribe_res = {"error": audio_res["error"]}
                        else:
                            with st.spinner(f"Transcrevendo áudio com Whisper ({model_size}) na {device_option.upper()}..."):
                                transcribe_res = transcribe_audio(
                                    audio_res["path"], 
                                    model_size=model_size, 
                                    device=device_option
                                )
                            
                if transcribe_res.get("error"):
                    st.error(f"Erro na transcrição: {transcribe_res['error']}")
                else:
                    st.success("Transcrição concluída com sucesso!")
                    st.session_state.transcription_done = True
                    st.session_state.full_text = transcribe_res["full_text"]
                    st.session_state.segments = transcribe_res["transcript_segments"]
                    st.session_state.transcript_source = transcribe_res.get("source", "YouTube Oficial")
                    
                    # Salvar no cache
                    with open(transcript_file, "w", encoding="utf-8") as f:
                        json.dump({
                            "full_text": st.session_state.full_text,
                            "segments": st.session_state.segments,
                            "source": st.session_state.transcript_source
                        }, f, ensure_ascii=False, indent=4)

if st.session_state.transcription_done:
    def format_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    from core.transcriber import build_youtube_transcript_blocks, format_badge_time
    
    yt_blocks = build_youtube_transcript_blocks(st.session_state.segments)

    src_badge = st.session_state.get("transcript_source", "YouTube Oficial")
    with st.expander(f"📜 Transcrição em Blocos (Estilo YouTube Oficial)", expanded=False):
        col_search, col_cnt = st.columns([3, 1])
        with col_search:
            search_term = st.text_input("🔍 Pesquisar na transcrição:", placeholder="Ex: ministro, justiça, reforma, imposto...", key="yt_transcript_search")
        
        # Filtra blocos se houver termo de busca
        displayed_blocks = yt_blocks
        if search_term.strip():
            displayed_blocks = [b for b in yt_blocks if search_term.lower() in b['text'].lower()]
            with col_cnt:
                st.caption(f"🎯 **{len(displayed_blocks)}** blocos encontrados")
        else:
            with col_cnt:
                st.caption(f"Total: **{len(yt_blocks)}** blocos ({src_badge})")
        
        # Container nativo do Streamlit com rolagem e renderização visual limpa
        with st.container(height=420):
            for b in displayed_blocks:
                text_display = b['text']
                if search_term.strip():
                    escaped = re.escape(search_term.strip())
                    text_display = re.sub(
                        f"({escaped})",
                        r"<mark style='background-color:#ffe082;color:#111;font-weight:bold;padding:1px 4px;border-radius:3px;'>\1</mark>",
                        text_display,
                        flags=re.IGNORECASE
                    )
                
                # HTML em linha única sem recuo de espaços para não ser interpretado como código
                line_html = (
                    f"<div style='display:flex;align-items:flex-start;margin-bottom:10px;line-height:1.5;'>"
                    f"<span style='display:inline-block;min-width:48px;background-color:#2b2b2b;color:#58a6ff;font-size:12px;font-weight:700;padding:2px 8px;border-radius:12px;margin-right:12px;text-align:center;letter-spacing:0.5px;'>{b['time_label']}</span>"
                    f"<span style='color:#e6edf3;font-size:14px;flex:1;'>{text_display}</span>"
                    f"</div>"
                )
                st.markdown(line_html, unsafe_allow_html=True)
    
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
            "Selecione o tipo de conteúdo para o mapeamento inteligente de cortes e pautas:"
        )
        
        col_strat, col_act = st.columns([3, 1])
        with col_strat:
            strategy_choice = st.radio(
                "🎯 Estratégia de Identificação de Pautas:",
                [
                    "🎙️ Entrevistas, Sabatinas & Podcasts (Perguntas e Respostas Exatas)",
                    "🧠 Temático / Monólogos, Aulas & Palestras (Transições de Assunto)"
                ],
                horizontal=False,
                key="analysis_strategy_radio"
            )
            strat_code = "qa_interview" if "Entrevistas" in strategy_choice else "semantic_topics"

        with col_act:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("🔍 Mapear Pautas (IA)", key="btn_map_pautas", type="primary", use_container_width=True):
                with st.spinner("Mapeando perguntas e limites de pauta com IA..."):
                    res = analyze_transcript(
                        chunked_transcript, "pautas",
                        model=ollama_model,
                        chunks_list=chunks_list,
                        segments=st.session_state.segments,
                        strategy=strat_code
                    )
                    if res.get("error"):
                        st.error(f"Erro na análise: {res['error']}")
                    else:
                        st.session_state.pautas = res.get("pautas", [])
                        st.session_state.bundles = res.get("bundles", [])
                        st.session_state.ai_raw = res.get("raw", "")
                        
                        active_u = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
                        v_id = get_video_id(active_u)
                        if v_id:
                            p_file = os.path.join("data", v_id, "pautas.json")
                            with open(p_file, "w", encoding="utf-8") as f:
                                json.dump({"pautas": st.session_state.pautas, "raw": st.session_state.ai_raw}, f, ensure_ascii=False, indent=4)
                        st.rerun()

        if 'pautas' in st.session_state and st.session_state.pautas:
            pautas = st.session_state.pautas
            
            # Carrega passos salvos do disco se existirem
            active_u = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
            v_id = get_video_id(active_u)
            steps_file = os.path.join("data", v_id, "saved_steps.json") if v_id else "data/saved_steps.json"
            if 'saved_steps' not in st.session_state or not st.session_state.saved_steps:
                if os.path.exists(steps_file):
                    try:
                        with open(steps_file, "r", encoding="utf-8") as f:
                            st.session_state.saved_steps = json.load(f)
                    except Exception:
                        st.session_state.saved_steps = []
                else:
                    st.session_state.saved_steps = []

            def _save_steps_to_disk():
                os.makedirs(os.path.dirname(steps_file), exist_ok=True)
                with open(steps_file, "w", encoding="utf-8") as f:
                    json.dump(st.session_state.saved_steps, f, indent=2, ensure_ascii=False)

            col_head1, col_head2 = st.columns([3, 2])
            with col_head1:
                st.markdown(f"### 📋 Pautas Detectadas ({len(pautas)} encontradas):")
            with col_head2:
                col_btn_uncheck, col_btn_reanalyze = st.columns(2)
                with col_btn_uncheck:
                    if st.button("🧹 Desmarcar Tudo", key="btn_uncheck_all", help="Limpa as seleções para iniciar um novo corte"):
                        for p in pautas:
                            st.session_state[f"chk_pauta_{p['id']}"] = False
                        st.rerun()
                with col_btn_reanalyze:
                    pass

            # Monta lista de pautas em cards selecionáveis
            st.markdown("")
            selected_pauta_objs = []

            for p in pautas:
                chk_key = f"chk_pauta_{p['id']}"
                if chk_key not in st.session_state:
                    st.session_state[chk_key] = False

                col_chk, col_p_info, col_dur = st.columns([0.5, 4.5, 1.2])
                with col_chk:
                    is_checked = st.checkbox("", key=chk_key)
                    if is_checked:
                        selected_pauta_objs.append(p)
                with col_p_info:
                    st.markdown(f"**Pauta #{p['id']}**: `[{p['start']} → {p['end']}]` **{p['title']}**")
                    if p.get('text_snippet'):
                        st.caption(f"💬 *\"{p['text_snippet']}...\"*")
                with col_dur:
                    st.markdown(f"⏱️ **{p['duration_label']}**")
                st.divider()

            # ── BARRA INFORMATIVA DA SELEÇÃO (COMPOSITOR) ─────────────────────────
            if selected_pauta_objs:
                # Ordena por timestamp de início
                selected_pauta_objs = sorted(selected_pauta_objs, key=lambda x: x["start_s"])
                comb_start = selected_pauta_objs[0]["start"]
                comb_end = selected_pauta_objs[-1]["end"]
                comb_dur_s = sum(x["duration_s"] for x in selected_pauta_objs)
                comb_dur_fmt = format_time(comb_dur_s)
                
                # Título composto inteligente
                if len(selected_pauta_objs) == 1:
                    comb_title = selected_pauta_objs[0]["title"]
                else:
                    comb_title = f"{selected_pauta_objs[0]['title']} (+ {len(selected_pauta_objs)-1} pautas)"

                st.info(
                    f"🎯 **Corte Composto**: `[{comb_start} → {comb_end}]` | "
                    f"⏱️ Duração Total: **{comb_dur_fmt}** | "
                    f"Pautas Inclusas: **{len(selected_pauta_objs)}** ({', '.join(f'#{x['id']}' for x in selected_pauta_objs)})"
                )

                col_ap1, col_ap2 = st.columns([2, 1])
                with col_ap1:
                    if st.button("✂️ Carregar Seleção para Exportação (Seção 3)", key="btn_apply_composed", type="primary", use_container_width=True):
                        st.session_state.final_start_time = comb_start
                        st.session_state.final_end_time = comb_end
                        st.session_state.final_corte_title = comb_title
                        st.session_state.cut_ready_banner = f"✅ Composição pronta para corte: [{comb_start} → {comb_end}] ({comb_dur_fmt})"
                        st.rerun()

                with col_ap2:
                    step_num = len(st.session_state.saved_steps) + 1
                    if st.button("💾 Guardar como Passo", key="btn_save_step", use_container_width=True, help="Salva esta composição no histórico de passos para poder montar múltiplos cortes sem perder o progresso"):
                        new_step = {
                            "step_id": step_num,
                            "start": comb_start,
                            "end": comb_end,
                            "start_s": selected_pauta_objs[0]["start_s"],
                            "end_s": selected_pauta_objs[-1]["end_s"],
                            "duration_s": comb_dur_s,
                            "duration_label": comb_dur_fmt,
                            "title": comb_title,
                            "pauta_ids": [x["id"] for x in selected_pauta_objs],
                            "pautas_titles": [f"Pauta #{x['id']}: {x['title']} ({x['duration_label']})" for x in selected_pauta_objs]
                        }
                        st.session_state.saved_steps.append(new_step)
                        _save_steps_to_disk()
                        st.success(f"🎉 Passo #{step_num} guardado com sucesso!")
                        st.rerun()

            else:
                if 'cut_ready_banner' in st.session_state:
                    st.session_state.cut_ready_banner = ""

            # ── PAINEL DE PASSOS GUARDADOS ────────────────────────────────────────
            st.markdown("---")
            st.markdown("### 🗂️ Histórico de Passos / Cortes Salvos:")
            if 'saved_steps' in st.session_state and st.session_state.saved_steps:
                st.caption(f"Você possui **{len(st.session_state.saved_steps)} passos/cortes** guardados.")
                
                for idx, step in enumerate(st.session_state.saved_steps):
                    with st.container():
                        col_s_info, col_s_redo, col_s_del = st.columns([4, 1.2, 1])
                        with col_s_info:
                            st.markdown(f"**Passo #{idx+1}**: `[{step['start']} → {step['end']}]` **{step['title']}**")
                            st.caption(f"⏱️ Duração: **{step['duration_label']}**")
                        
                        with col_s_redo:
                            if st.button("🔁 Carregar", key=f"btn_redo_step_{idx}"):
                                st.session_state.final_start_time = step['start']
                                st.session_state.final_end_time = step['end']
                                st.session_state.final_corte_title = step['title']
                                st.rerun()

                        with col_s_del:
                            if st.button("🗑️ Excluir", key=f"btn_del_step_{idx}"):
                                st.session_state.saved_steps.pop(idx)
                                _save_steps_to_disk()
                                st.rerun()
                        st.divider()

                if st.button("🗑️ Excluir Todos os Passos", key="btn_clear_all_steps"):
                    st.session_state.saved_steps = []
                    _save_steps_to_disk()
                    st.success("Todos os passos foram excluídos.")
                    st.rerun()
            else:
                st.info("Nenhum passo guardado ainda. Selecione pautas acima e clique em **'💾 Guardar como Passo'** para montar sua fila de cortes!")


    # ── TAB 2: SÉRIES AUTOMÁTICAS ─────────────────────────────────────────────
    with tab_series:
        st.markdown("Cortes automáticos de **10+ minutos** sugeridos agrupando sequências de pautas.")
        
        if st.button("🧠 Gerar Séries Automáticas (10 min)", key="btn_series"):
            with st.spinner("Agrupando pautas em séries de 10+ min..."):
                res = analyze_transcript(
                    chunked_transcript, "blocos",
                    model=ollama_model,
                    chunks_list=chunks_list,
                    segments=st.session_state.segments,
                    strategy="qa_interview" if "Entrevistas" in strategy_choice else "semantic_topics"
                )
                if res.get("error"):
                    st.error(f"Erro no Ollama: {res['error']}")
                else:
                    st.session_state.bundles = res.get("bundles", [])
                    st.session_state.pautas = res.get("pautas", [])
                    st.session_state.ai_raw = res.get("raw", "")
                    
                    active_u = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
                    v_id = get_video_id(active_u)
                    if v_id:
                        s_file = os.path.join("data", v_id, "series.json")
                        with open(s_file, "w", encoding="utf-8") as f:
                            json.dump(st.session_state.bundles, f, ensure_ascii=False, indent=4)
                    st.rerun()

        if 'bundles' in st.session_state and st.session_state.bundles:
            for idx, b in enumerate(st.session_state.bundles):
                with st.container():
                    col_info, col_btn = st.columns([4, 1])
                    with col_info:
                        badge = f"**{b.get('series_label', f'Vídeo {idx+1}')}**"
                        st.markdown(f"{badge}: `[{b['start']} - {b['end']}]` **{b['title']}**")
                        st.caption(f"⏱️ Duração: {b.get('duration_label', '')}")
                    with col_btn:
                        if st.button("✂️ Usar", key=f"btn_use_bundle_{idx}"):
                            st.session_state.final_start_time = b['start']
                            st.session_state.final_end_time = b['end']
                            st.session_state.final_corte_title = b['title']
                            st.session_state.cut_ready_banner = f"✅ Série selecionada: [{b['start']} → {b['end']}] ({b['title']})"
                            st.rerun()
                    st.divider()

    # ── TAB 3: GANCHOS VIRAIS & PEQUENOS CORTES (SHORTS / REELS) ───────────────
    with tab_shorts:
        st.markdown(
            "Geração de **Pequenos Cortes (20s a 75s)** estruturados sob as **6 Regras de Ouro Editoriais**."
        )
        
        if st.button("🔥 Gerar Pequenos Cortes", key="btn_shorts", type="primary"):
            with st.spinner("Estruturando pequenos cortes com coerência editorial..."):
                res = analyze_transcript(
                    chunked_transcript, "ganchos",
                    model=ollama_model,
                    chunks_list=chunks_list,
                    segments=st.session_state.segments,
                    strategy="qa_interview" if "Entrevistas" in strategy_choice else "semantic_topics"
                )
                if res.get("error"):
                    st.error(f"Erro na análise: {res['error']}")
                else:
                    st.session_state.shorts = res.get("micro_cuts", []) or res.get("cortes", [])
                    st.session_state.pautas = res.get("pautas", [])
                    st.session_state.ai_raw = res.get("raw", "")
                    
                    active_u = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
                    v_id = get_video_id(active_u)
                    if v_id:
                        sh_file = os.path.join("data", v_id, "shorts.json")
                        with open(sh_file, "w", encoding="utf-8") as f:
                            json.dump(st.session_state.shorts, f, ensure_ascii=False, indent=4)
                    st.rerun()

        if 'shorts' in st.session_state and st.session_state.shorts:
            st.markdown(f"### 🎬 Pequenos Cortes Gerados ({len(st.session_state.shorts)}):")
            for idx, s in enumerate(st.session_state.shorts):
                with st.container():
                    col_info, col_btn = st.columns([4, 1.2])
                    with col_info:
                        st.markdown(f"**{s.get('type', 'Corte')}** | `[{s['start']} → {s['end']}]` **{s['title']}**")
                        st.caption(f"⏱️ Duração: **{s.get('duration_label', '')}**")
                        if s.get('snippet'):
                            st.markdown(f"💬 *\"{s['snippet']}\"*")
                    with col_btn:
                        if st.button("✂️ Usar este Corte", key=f"btn_use_short_{idx}", use_container_width=True):
                            st.session_state.final_start_time = s['start']
                            st.session_state.final_end_time = s['end']
                            st.session_state.final_corte_title = s['title']
                            st.session_state.cut_ready_banner = f"✅ Short selecionado: [{s['start']} → {s['end']}] ({s['title']})"
                            st.rerun()
                    st.divider()

    # ── TAB 4: SELEÇÃO MANUAL ────────────────────────────────────────────────
    with tab_manual:
        
        mode_manual = st.radio("Modo de Seleção:", ["📜 Blocos de Legenda (Estilo YouTube)", "⏱️ Intervalos de 1 Minuto"], horizontal=True)
        
        if mode_manual == "📜 Blocos de Legenda (Estilo YouTube)":
            block_labels = [
                f"[{b['time_label']}]  {b['text'][:90]}..."
                for b in yt_blocks
            ]
            col_s, col_e = st.columns(2)
            idx_start = col_s.selectbox("Fala de Início:", range(len(yt_blocks)),
                                         format_func=lambda i: block_labels[i], key="yt_block_start")
            idx_end = col_e.selectbox("Fala de Fim:", range(len(yt_blocks)),
                                       format_func=lambda i: block_labels[i],
                                       index=min(len(yt_blocks)-1, 50), key="yt_block_end")
            
            if idx_end >= idx_start:
                start_s = yt_blocks[idx_start]['start']
                end_s = yt_blocks[idx_end]['end']
                st.success(f"Trecho Selecionado: **{format_time(start_s)}** → **{format_time(end_s)}** ({(end_s - start_s)/60:.1f} min)")
                if st.button("✂️ Usar este trecho na Fábrica de Cortes", key="btn_manual_yt"):
                    st.session_state.final_start_time = format_time(start_s)
                    st.session_state.final_end_time = format_time(end_s)
                    st.session_state.final_corte_title = f"Corte Manual [{yt_blocks[idx_start]['time_label']} - {yt_blocks[idx_end]['time_label']}]"
                    st.session_state.cut_ready_banner = f"✅ Corte manual: [{format_time(start_s)} → {format_time(end_s)}]"
                    st.rerun()
        else:
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

    st.markdown("#### 📐 Formato de Exportação do Vídeo")
    aspect_option = st.radio(
        "Escolha o enquadramento:",
        [
            "📱 Vertical 9:16 (👥 Layout Dividido / Split Screen - Estilo Podpah & Flow)",
            "📱 Vertical 9:16 (🎯 Rastreamento Inteligente de Rosto / Auto-Reframing)",
            "📱 Vertical 9:16 (Fundo Desfocado / Blur - Shorts/TikTok/Reels)",
            "📱 Vertical 9:16 (Corte Central 100% Tela)",
            "💻 Horizontal 16:9 (Original 1080p Full HD)"
        ],
        horizontal=False,
        key="aspect_ratio_choice"
    )
    
    aspect_map = {
        "📱 Vertical 9:16 (👥 Layout Dividido / Split Screen - Estilo Podpah & Flow)": "9:16_split",
        "📱 Vertical 9:16 (🎯 Rastreamento Inteligente de Rosto / Auto-Reframing)": "9:16_smart_face",
        "📱 Vertical 9:16 (Fundo Desfocado / Blur - Shorts/TikTok/Reels)": "9:16_blur",
        "📱 Vertical 9:16 (Corte Central 100% Tela)": "9:16_crop",
        "💻 Horizontal 16:9 (Original 1080p Full HD)": "16:9"
    }
    selected_aspect = aspect_map[aspect_option]

    blur_zoom_val = 1.0
    blur_pan_val = 0.0
    blur_int_val = 25
    face_zoom_active = True
    face_margin_val = 1.55
    person_pref_val = "auto"
    split_top_pan = -0.65
    split_bottom_pan = 0.65
    split_zoom_val = 1.15
    split_div_color = "black"
    split_div_w = 4
    split_auto_switch = True

    if selected_aspect == "9:16_split":
        with st.expander("👥 Ajustes do Layout Dividido (Split Screen 9:16)", expanded=True):
            split_auto_switch = st.toggle(
                "🤖 Transição Dinâmica Inteligente (Auto-Switch)",
                value=True,
                help="Recomendado: Quando houver 2+ pessoas no enquadramento, aplica o Split Screen. Se a câmera fechar em Close-up de apenas 1 pessoa, expande suavemente para 9:16 Full Screen sem cortar ninguém!"
            )
            col_sp1, col_sp2 = st.columns(2)
            with col_sp1:
                split_preset = st.selectbox(
                    "🎬 Distribuição dos Personagens:",
                    [
                        "👈 Entrevistador(es) no Topo | 👉 Entrevistado na Base (Padrão Podpah/Flow)",
                        "👉 Entrevistado no Topo | 👈 Entrevistador(es) na Base",
                        "🎛️ Personalizado (Sliders Manuais)"
                    ],
                    key="split_preset_choice"
                )
                
                if split_preset == "👈 Entrevistador(es) no Topo | 👉 Entrevistado na Base (Padrão Podpah/Flow)":
                    split_top_pan = -0.65
                    split_bottom_pan = 0.65
                elif split_preset == "👉 Entrevistado no Topo | 👈 Entrevistador(es) na Base":
                    split_top_pan = 0.65
                    split_bottom_pan = -0.65
                else:
                    split_top_pan = st.slider("↔️ Foco Horizontal do Topo:", -1.0, 1.0, -0.65, 0.05)
                    split_bottom_pan = st.slider("↔️ Foco Horizontal da Base:", -1.0, 1.0, 0.65, 0.05)

            with col_sp2:
                split_zoom_val = st.slider(
                    "🔍 Zoom / Aproximação dos Quadros:",
                    min_value=1.0,
                    max_value=2.0,
                    value=1.15,
                    step=0.05,
                    format="%.2fx",
                    help="Aumente para aproximar o enquadramento de rosto e busto nos dois quadros."
                )
                col_div1, col_div2 = st.columns(2)
                with col_div1:
                    split_div_color = st.selectbox("Linha Divisória:", ["black", "white", "gray", "none"], index=0, format_func=lambda x: {"black": "⬛ Preta", "white": "⬜ Branca", "gray": "🔘 Cinza", "none": "🚫 Sem Linha"}[x])
                with col_div2:
                    split_div_w = st.slider("Espessura:", 0, 8, 4)

            if start_time:
                if st.button("👁️ Visualizar Prévia do Split Screen", key="btn_prev_split"):
                    active_u = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
                    v_id = get_video_id(active_u)
                    v_full = os.path.join("data", v_id, "video_full.mp4") if v_id else ""
                    if os.path.exists(v_full):
                        from core.face_tracker import generate_split_preview_image
                        prev_sp_path = os.path.join("data", v_id, "preview_split.jpg")
                        p_res = generate_split_preview_image(
                            v_full,
                            start_time,
                            prev_sp_path,
                            top_pan=split_top_pan,
                            bottom_pan=split_bottom_pan,
                            zoom=split_zoom_val,
                            divider_color=split_div_color,
                            divider_width=split_div_w
                        )
                        if p_res.get("path") and os.path.exists(p_res["path"]):
                            st.image(p_res["path"], caption=f"Prévia 9:16 Split Screen em {start_time}", use_container_width=True)
                        else:
                            st.error(f"Erro na prévia: {p_res.get('error')}")
                    else:
                        st.info("O vídeo precisa ser baixado para gerar a prévia.")

    elif selected_aspect == "9:16_smart_face":
        with st.expander("🎯 Ajustes de Rastreamento, Foco e Margens do Personagem", expanded=True):
            col_fz1, col_fz2 = st.columns(2)
            with col_fz1:
                target_choice = st.selectbox(
                    "👤 Personagem Alvo (Trava de Continuidade):",
                    [
                        "👉 Personagem da Direita / Entrevistado",
                        "👈 Personagem da Esquerda",
                        "🔍 Personagem Mais Central",
                        "🎯 Automático (Maior Dominância)"
                    ],
                    help="Trava o rastreamento 100% no interlocutor selecionado, impedindo que a câmera pule para outra pessoa na cena."
                )
                target_map = {
                    "👉 Personagem da Direita / Entrevistado": "right",
                    "👈 Personagem da Esquerda": "left",
                    "🔍 Personagem Mais Central": "center",
                    "🎯 Automático (Maior Dominância)": "auto"
                }
                person_pref_val = target_map[target_choice]

                face_zoom_active = st.toggle(
                    "🔍 Auto-Zoom Máximo no Personagem",
                    value=True,
                    help="Aproxima a câmera vertical no interlocutor principal detectado, eliminando espaços vazios com máxima nitidez."
                )

            with col_fz2:
                margin_choice = st.select_slider(
                    "📏 Margem Lateral de Segurança:",
                    options=["Estreita (Close-up Máximo)", "Equilibrada (Busto & Rosto - Recomendado)", "Ampla (Plano Médio)"],
                    value="Equilibrada (Busto & Rosto - Recomendado)"
                )
                if margin_choice == "Estreita (Close-up Máximo)":
                    face_margin_val = 1.30
                elif margin_choice == "Ampla (Plano Médio)":
                    face_margin_val = 1.85
                else:
                    face_margin_val = 1.55

                # Botão de prévia instantânea de enquadramento
                if start_time:
                    if st.button("👁️ Visualizar Prévia do Enquadramento", key="btn_preview_face"):
                        video_id = get_video_id(video_url)
                        v_full = os.path.join("data", video_id, "video_full.mp4") if video_id else ""
                        if os.path.exists(v_full):
                            from core.face_tracker import generate_face_preview_image
                            prev_path = os.path.join("data", video_id, "preview_face.jpg")
                            p_res = generate_face_preview_image(
                                v_full,
                                start_time,
                                prev_path,
                                person_preference=person_pref_val,
                                auto_zoom=face_zoom_active,
                                margin_ratio=face_margin_val
                            )
                            if p_res.get("path") and os.path.exists(p_res["path"]):
                                st.image(p_res["path"], caption=f"Prévia em {start_time} (Alvo em Verde, Moldura 9:16 em Ciano)", use_container_width=True)
                            else:
                                st.error(f"Erro na prévia: {p_res.get('error')}")
                        else:
                            st.info("O vídeo precisa ser baixado para gerar a prévia.")

    elif selected_aspect == "9:16_blur":
        with st.expander("🌫️ Ajustes do Fundo Desfocado (Auto-Zoom e Margens)", expanded=True):
            mode_blur_ctrl = st.radio(
                "Modo de Enquadramento:",
                ["🤖 Auto-Zoom Inteligente no Personagem (Recomendado)", "🎛️ Manual (Sliders de Zoom e Posição)"],
                horizontal=True,
                key="mode_blur_ctrl_radio"
            )

            if mode_blur_ctrl == "🤖 Auto-Zoom Inteligente no Personagem (Recomendado)":
                col_ab1, col_ab2 = st.columns(2)
                with col_ab1:
                    blur_target_choice = st.selectbox(
                        "👤 Personagem Alvo:",
                        [
                            "👉 Personagem da Direita / Entrevistado",
                            "👈 Personagem da Esquerda",
                            "🔍 Personagem Mais Central",
                            "🎯 Automático"
                        ],
                        key="blur_target_sel"
                    )
                    blur_target_map = {
                        "👉 Personagem da Direita / Entrevistado": "right",
                        "👈 Personagem da Esquerda": "left",
                        "🔍 Personagem Mais Central": "center",
                        "🎯 Automático": "auto"
                    }
                    blur_person_pref = blur_target_map[blur_target_choice]

                with col_ab2:
                    blur_margin_choice = st.select_slider(
                        "📏 Margem Lateral de Segurança:",
                        options=["Estreita (Close-up Máximo / Menor Desfoque)", "Equilibrada (Busto & Rosto)", "Ampla (Plano Médio)"],
                        value="Equilibrada (Busto & Rosto)",
                        key="blur_margin_sel"
                    )
                    if blur_margin_choice == "Estreita (Close-up Máximo / Menor Desfoque)":
                        blur_margin_val = 1.30
                    elif blur_margin_choice == "Ampla (Plano Médio)":
                        blur_margin_val = 1.85
                    else:
                        blur_margin_val = 1.55

                # Calcula automaticamente o Zoom e Pan
                video_id = get_video_id(video_url)
                v_full = os.path.join("data", video_id, "video_full.mp4") if video_id else ""
                if os.path.exists(v_full) and start_time:
                    from core.face_tracker import calculate_auto_blur_params, generate_blur_preview_image
                    auto_p = calculate_auto_blur_params(v_full, start_time, blur_person_pref, blur_margin_val)
                    blur_zoom_val = auto_p["zoom"]
                    blur_pan_val = auto_p["pan"]
                    st.caption(f"✨ Auto-Zoom Calculado: **{blur_zoom_val:.2f}x** | Foco Horizontal: **{blur_pan_val:+.2f}**")

                    if st.button("👁️ Visualizar Prévia com Fundo Desfocado", key="btn_prev_blur"):
                        prev_b_path = os.path.join("data", video_id, "preview_blur.jpg")
                        p_res = generate_blur_preview_image(v_full, start_time, prev_b_path, blur_zoom_val, blur_pan_val, blur_int_val)
                        if p_res.get("path") and os.path.exists(p_res["path"]):
                            st.image(p_res["path"], caption=f"Prévia 9:16 com Fundo Desfocado em {start_time} (Zoom: {blur_zoom_val:.2f}x)", use_container_width=True)
                        else:
                            st.error(f"Erro na prévia: {p_res.get('error')}")
                else:
                    blur_zoom_val = 1.45
                    blur_pan_val = 0.6 if blur_person_pref == "right" else (-0.6 if blur_person_pref == "left" else 0.0)

            else:
                col_z1, col_z2 = st.columns(2)
                with col_z1:
                    blur_zoom_val = st.slider(
                        "🔍 Nível de Aproximação (Zoom Manual):",
                        min_value=1.0,
                        max_value=2.5,
                        value=1.35,
                        step=0.05,
                        format="%.2fx",
                        help="Aumente para o vídeo preencher mais a tela e diminuir as faixas superior/inferior de desfoque."
                    )
                with col_z2:
                    pan_preset = st.selectbox(
                        "↔️ Posição / Foco Horizontal:",
                        [
                            "Centro (0%)",
                            "Personagem à Esquerda (-60%)",
                            "Personagem à Direita (+60%)",
                            "Extrema Esquerda (-100%)",
                            "Extrema Direita (+100%)",
                            "Ajuste Fino Personalizado"
                        ]
                    )
                    if pan_preset == "Personagem à Esquerda (-60%)":
                        blur_pan_val = -0.6
                    elif pan_preset == "Personagem à Direita (+60%)":
                        blur_pan_val = 0.6
                    elif pan_preset == "Extrema Esquerda (-100%)":
                        blur_pan_val = -1.0
                    elif pan_preset == "Extrema Direita (+100%)":
                        blur_pan_val = 1.0
                    elif pan_preset == "Ajuste Fino Personalizado":
                        blur_pan_val = st.slider("Deslocamento Horizontal:", -1.0, 1.0, 0.0, 0.05)
                    else:
                        blur_pan_val = 0.0

    # ─────────────────────────────────────────────────────────────────
    # Legendas Dinâmicas (Fase 2)
    # ─────────────────────────────────────────────────────────────────
    subtitle_enabled = False
    subtitle_highlight_color = "#FFFF00"
    subtitle_base_color = "#FFFFFF"
    subtitle_font_size = 80

    with st.expander("📝 Legendas Dinâmicas (Estilo CapCut / Alex Hormozi)", expanded=False):
        subtitle_enabled = st.toggle(
            "✨ Ativar Legendas Palavra-a-Palavra",
            value=False,
            help="Queima legendas sincronizadas diretamente no vídeo renderizado, com destaque animado na palavra atual."
        )
        if subtitle_enabled:
            # Verifica se a transcrição está disponível com timestamps
            _vid_id_sub = get_video_id(video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or "")
            _transcript_path_sub = os.path.join("data", _vid_id_sub, "transcript.json") if _vid_id_sub else ""
            _has_transcript = os.path.exists(_transcript_path_sub)

            if not _has_transcript:
                st.warning("⚠️ Transcrição não encontrada. Realize a transcrição na Seção 1 antes de ativar as legendas.")
                subtitle_enabled = False
            else:
                # Verifica se há word_timestamps no transcript salvo
                import json as _json_sub
                try:
                    with open(_transcript_path_sub, encoding="utf-8") as _tf:
                        _td = _json_sub.load(_tf)
                    _segs = _td.get("segments", [])
                    _has_words = any(s.get("words") for s in _segs[:5])
                    if not _has_words:
                        st.info("ℹ️ Transcrição sem timestamps por palavra. As legendas usarão distribuição proporcional (recomenda-se retranscrever com Whisper para precisão máxima).")
                except Exception:
                    pass

                col_sub1, col_sub2, col_sub3 = st.columns([2, 2, 1])
                with col_sub1:
                    subtitle_highlight_color = st.color_picker(
                        "🎨 Cor do Destaque (Palavra Atual)",
                        value="#FFFF00",
                        key="sub_highlight_color",
                        help="Cor vibrante que pisca na palavra sendo falada."
                    )
                with col_sub2:
                    subtitle_base_color = st.color_picker(
                        "💤 Cor das Demais Palavras",
                        value="#FFFFFF",
                        key="sub_base_color",
                        help="Cor das palavras da linha atual que ainda não foram ditas."
                    )
                with col_sub3:
                    subtitle_font_size = st.slider(
                        "🔤 Fonte",
                        min_value=40,
                        max_value=160,
                        value=80,
                        step=5,
                        key="sub_font_size",
                        help="Tamanho da fonte das legendas (recomendado entre 75 e 110 para cortes 9:16 estilo Alex Hormozi)."
                    )
                st.caption("📌 Legendas no terço inferior da tela • Fonte Montserrat Bold (ou Arial como fallback) • Contorno preto para legibilidade em qualquer fundo")

    st.markdown("")
    if st.button("✂️ Gerar Corte no Formato Escolhido", type="primary", use_container_width=True):
        if not start_time or not end_time:
            st.warning("Preencha o tempo inicial e final.")
        else:
            import importlib
            import core.video_processor
            importlib.reload(core.video_processor)
            from core.video_processor import download_full_video, cut_video, get_video_resolution
            
            active_url = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
            video_id = get_video_id(active_url)
            
            if not video_id:
                st.error("URL do vídeo do YouTube não identificada. Por favor, confirme a URL na Seção 1.")
            else:
                data_dir = os.path.join("data", video_id)
                os.makedirs(data_dir, exist_ok=True)
                video_full_path = os.path.join(data_dir, "video_full.mp4")
                # Normaliza o aspect ratio para nome de arquivo seguro no Windows
                # (substituindo ':' por '-' para evitar Alternate Data Streams)
                safe_aspect_name = selected_aspect.replace(":", "-")
                corte_output_path = os.path.join(data_dir, f"corte_{safe_aspect_name}.mp4")
                
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
                        video_res = download_full_video(active_url, video_full_path)
                else:
                    current_res = get_video_resolution(video_full_path)
                    st.success(f"Vídeo em alta qualidade encontrado no cache ({current_res})!")
                    video_res = {"path": video_full_path, "error": None}
                    
                if video_res.get("error"):
                    st.error(f"Erro ao baixar vídeo: {video_res['error']}")
                else:
                    extra_info = ""
                    if selected_aspect == "9:16_blur":
                        extra_info = f" (Zoom: {blur_zoom_val:.2f}x)"
                    elif selected_aspect == "9:16_smart_face" and face_zoom_active:
                        extra_info = f" (Auto-Zoom Inteligente)"
                    elif selected_aspect == "9:16_split":
                        extra_info = f" (Split Screen + Auto-Switch)" if split_auto_switch else " (Split Screen Fixo)"
                    if subtitle_enabled:
                        extra_info += " + 📝 Legendas"

                    with st.spinner(f"Renderizando corte [{start_time} → {end_time}] no formato {aspect_option}{extra_info}..."):
                        # Caminho do transcript para as legendas dinâmicas
                        _transcript_path_cut = os.path.join(data_dir, "transcript.json")
                        cut_res = cut_video(
                            video_res["path"],
                            start_time,
                            end_time,
                            corte_output_path,
                            aspect_ratio_mode=selected_aspect,
                            blur_zoom=blur_zoom_val,
                            blur_pan=blur_pan_val,
                            blur_intensity=blur_int_val,
                            face_auto_zoom=face_zoom_active,
                            face_margin_ratio=face_margin_val,
                            person_preference=person_pref_val,
                            split_top_pan=split_top_pan,
                            split_bottom_pan=split_bottom_pan,
                            split_zoom=split_zoom_val,
                            split_divider_color=split_div_color,
                            split_divider_width=split_div_w,
                            split_auto_switch=split_auto_switch,
                            # Legendas Dinâmicas (Fase 2)
                            subtitle_enabled=subtitle_enabled,
                            subtitle_transcript_path=_transcript_path_cut,
                            subtitle_highlight_color=subtitle_highlight_color,
                            subtitle_base_color=subtitle_base_color,
                            subtitle_font_size=subtitle_font_size,
                        )
                        if cut_res.get("error"):
                            st.error(f"Erro ao cortar: {cut_res['error']}")
                        else:
                            out_res = get_video_resolution(corte_output_path)
                            _sub_badge = " 📝 Legendas" if subtitle_enabled and not cut_res.get("subtitle_error") and not cut_res.get("subtitle_warning") else ""
                            st.success(f"🎉 Corte gerado com sucesso! Resolução: **{out_res}** | Formato: **{aspect_option}**{_sub_badge}")
                            
                            # Avisos de legendas (não-fatais — o vídeo ainda foi gerado)
                            if cut_res.get("subtitle_error"):
                                st.warning(f"⚠️ Legendas não aplicadas: {cut_res['subtitle_error']}")
                            elif cut_res.get("subtitle_warning"):
                                st.info(f"ℹ️ {cut_res['subtitle_warning']}")
                            
                            if "9:16" in selected_aspect:
                                col_v1, col_v2, col_v3 = st.columns([1, 2, 1])
                                with col_v2:
                                    st.video(corte_output_path)
                            else:
                                st.video(corte_output_path)
                            
                            with open(corte_output_path, "rb") as file:
                                st.download_button(
                                    label=f"💾 Baixar Vídeo ({out_res})",
                                    data=file,
                                    file_name=f"corte_{selected_aspect}.mp4",
                                    mime="video/mp4",
                                    use_container_width=True
                                )



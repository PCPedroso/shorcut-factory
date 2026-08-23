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
import core.config_manager
import core.export_kit
import core.cuts_catalog
import core.batch_processor
import core.headline_drawer
import core.audio_mixer
import core.retention_effects
import core.integrations
import core.thumbnail_generator

importlib.reload(core.extractor)
importlib.reload(core.transcriber)
importlib.reload(core.analyzer)
importlib.reload(core.video_processor)
importlib.reload(core.face_tracker)
importlib.reload(core.library_manager)
importlib.reload(core.config_manager)
importlib.reload(core.export_kit)
importlib.reload(core.cuts_catalog)
importlib.reload(core.batch_processor)
importlib.reload(core.headline_drawer)
importlib.reload(core.audio_mixer)
importlib.reload(core.retention_effects)
importlib.reload(core.integrations)
importlib.reload(core.thumbnail_generator)

from core.extractor import download_audio, get_video_metadata
from core.transcriber import transcribe_audio, fetch_youtube_transcript
from core.analyzer import analyze_transcript
from core.video_processor import download_full_video, cut_video, get_video_resolution
from core.library_manager import get_library, add_or_update_video_in_library, remove_video_from_library
from core.config_manager import load_settings, save_all_settings, save_setting
from core.export_kit import build_cut_folder_name, create_viral_package
from core.cuts_catalog import get_cut_entry, get_format_instance, register_cut_instance, update_cut_texts_only, delete_entire_cut, delete_format_instance, load_cuts_catalog
from core.batch_processor import process_batch_cuts
from core.headline_drawer import HEADLINE_PRESETS
from core.audio_mixer import list_available_tracks, DUCKING_PRESETS
from core.retention_effects import PROGRESS_BAR_COLORS, ENGAGEMENT_CALLOUT_PRESETS
from core.thumbnail_generator import create_cut_thumbnail
from core.integrations import get_youtube_auth_status, authenticate_youtube_oauth, upload_to_youtube_shorts, send_to_webhook

# Carrega todas as configurações persistentes salvas
_cfg = load_settings()


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

_devices = ["cpu", "cuda"]
_dev_idx = _devices.index(_cfg.get("device_option", "cpu")) if _cfg.get("device_option") in _devices else 0
device_option = st.sidebar.selectbox("Dispositivo de Processamento", _devices, index=_dev_idx)

_model_sizes = ["tiny", "small", "medium", "large-v3"]
_ms_idx = _model_sizes.index(_cfg.get("model_size", "small")) if _cfg.get("model_size") in _model_sizes else 1
model_size = st.sidebar.selectbox("Tamanho do Modelo Whisper", _model_sizes, index=_ms_idx)

st.sidebar.markdown("---")
st.sidebar.subheader("Modelo de IA (Ollama)")
_ollama_models = ["llama3", "mistral", "qwen2.5", "llama3.1", "gemma2"]
_om_idx = _ollama_models.index(_cfg.get("ollama_model", "llama3")) if _cfg.get("ollama_model") in _ollama_models else 0
ollama_model = st.sidebar.selectbox(
    "Modelo:",
    _ollama_models,
    index=_om_idx,
    help="Para usar mistral ou qwen2.5 rode: ollama pull mistral"
)

# 🌐 Integrações & Exportação Direta (Fase 3)
st.sidebar.markdown("---")
with st.sidebar.expander("🌐 Integrações & Webhooks (Fase 3)", expanded=False):
    st.markdown("##### 🔴 YouTube Shorts API")
    yt_secrets_path = st.text_input(
        "Caminho do client_secrets.json:",
        value=_cfg.get("youtube_client_secrets_path", "data/client_secrets.json"),
        help="Arquivo de credenciais baixado do Google Cloud Console para envio direto ao YouTube Shorts."
    )
    auth_status = get_youtube_auth_status(yt_secrets_path)
    if auth_status.get("authenticated"):
        st.success(f"✅ {auth_status['message']}")
    else:
        st.info(f"ℹ️ {auth_status['message']}")
        if os.path.exists(yt_secrets_path):
            if st.button("🔑 Conectar Conta Google / YouTube", key="btn_auth_yt_side", use_container_width=True):
                with st.spinner("Abrindo autenticação Google no navegador..."):
                    auth_res = authenticate_youtube_oauth(yt_secrets_path)
                    if auth_res.get("success"):
                        st.success("🎉 Conectado com sucesso ao YouTube!")
                        st.rerun()
                    else:
                        st.error(f"Erro na autenticação: {auth_res.get('error')}")

    st.markdown("##### 📡 Webhook (n8n / Make / Zapier)")
    sb_webhook_url = st.text_input(
        "URL do Webhook:",
        value=_cfg.get("webhook_url", ""),
        placeholder="https://sua-instancia-n8n.com/webhook/cortes",
        help="Endpoint HTTP para disparo de automação quando um corte for concluído."
    )
    sb_webhook_auth = st.text_input(
        "Header de Autorização (Opcional):",
        value=_cfg.get("webhook_auth_header", ""),
        placeholder="Bearer seu_token_aqui",
        type="password"
    )
    if sb_webhook_url:
        if st.button("🧪 Testar Webhook", key="btn_test_webhook", use_container_width=True):
            with st.spinner("Enviando payload de teste..."):
                test_res = send_to_webhook(
                    sb_webhook_url,
                    {"event": "test_ping", "message": "Conexão com ViralCut testada com sucesso!"},
                    auth_header=sb_webhook_auth
                )
                if test_res.get("success"):
                    st.success(f"✅ Conexão OK! HTTP {test_res.get('status_code')}")
                else:
                    st.error(f"❌ Falha: {test_res.get('error')}")

    save_setting("youtube_client_secrets_path", yt_secrets_path)
    save_setting("webhook_url", sb_webhook_url)
    save_setting("webhook_auth_header", sb_webhook_auth)


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
                    duration_sec=v_dur,
                    channel=meta.get("channel")
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
            _strat_options = [
                "🎙️ Entrevistas, Sabatinas & Podcasts (Perguntas e Respostas Exatas)",
                "🧠 Temático / Monólogos, Aulas & Palestras (Transições de Assunto)"
            ]
            _strat_idx = 0 if "Entrevistas" in _cfg.get("analysis_strategy", "") else 1
            strategy_choice = st.radio(
                "🎯 Estratégia de Identificação de Pautas:",
                _strat_options,
                index=_strat_idx,
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
                    is_checked = st.checkbox(f"Pauta {p['id']}", key=chk_key, label_visibility="collapsed")
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
        st.markdown("Cortes de **10+ minutos** sugeridos agrupando sequências de pautas para publicação como **Vídeos Normais no YouTube** (Horizontal 16:9 Full HD).")
        st.info("ℹ️ **Modo Vídeo Normal (YouTube 16:9)**: Séries e vídeos longos de 10+ minutos são renderizados no formato original widescreen limpo (sem tarjas de topo, zoom punches periódicos ou barras de progresso de Shorts), preservando a experiência de vídeo tradicional do YouTube.")

        if "batch_feedback" in st.session_state:
            fb = st.session_state.pop("batch_feedback")
            if fb.get("type") == "success":
                st.success(fb.get("msg", ""))
            elif fb.get("type") == "warning":
                st.warning(fb.get("msg", ""))
            else:
                st.error(fb.get("msg", ""))
        
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
            # Reseta seleção de checkboxes de forma segura antes da instanciação dos widgets
            if st.session_state.get("_reset_bundles_selection"):
                st.session_state["_reset_bundles_selection"] = False
                for b_i in range(len(st.session_state.bundles)):
                    st.session_state[f"chk_bundle_{b_i}"] = False
                st.session_state["batch_bundle_selected"] = {}

            if "batch_bundle_selected" not in st.session_state:
                st.session_state["batch_bundle_selected"] = {}

            col_bb1, col_bb2, col_bb3, _ = st.columns([1.4, 1.4, 1.4, 1.8])
            with col_bb1:
                if st.button("☑️ Marcar Tudo", key="btn_sel_all_bundles", use_container_width=True):
                    for b_i, b_item in enumerate(st.session_state.bundles):
                        st.session_state[f"chk_bundle_{b_i}"] = True
                        st.session_state["batch_bundle_selected"][b_i] = b_item
                    st.rerun()
            with col_bb2:
                if st.button("⬜ Desmarcar Tudo", key="btn_clear_bundles_batch", use_container_width=True):
                    st.session_state["_reset_bundles_selection"] = True
                    st.rerun()
            with col_bb3:
                if st.button("🔄 Inverter Seleção", key="btn_invert_bundles_batch", use_container_width=True):
                    for b_i, b_item in enumerate(st.session_state.bundles):
                        cur_val = st.session_state.get(f"chk_bundle_{b_i}", False)
                        new_val = not cur_val
                        st.session_state[f"chk_bundle_{b_i}"] = new_val
                        if new_val:
                            st.session_state["batch_bundle_selected"][b_i] = b_item
                        else:
                            st.session_state["batch_bundle_selected"].pop(b_i, None)
                    st.rerun()

            st.markdown(f"### 📦 Séries Sugeridas ({len(st.session_state.bundles)}):")
            for idx, b in enumerate(st.session_state.bundles):
                with st.container():
                    col_chk, col_info, col_btn = st.columns([0.3, 3.7, 1])
                    with col_chk:
                        chk_val = st.checkbox("Fila", key=f"chk_bundle_{idx}", label_visibility="collapsed")
                        if chk_val:
                            st.session_state["batch_bundle_selected"][idx] = b
                        else:
                            st.session_state["batch_bundle_selected"].pop(idx, None)
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

            # Painel da Fila de Produção em Lote para Séries
            selected_bundles = list(st.session_state["batch_bundle_selected"].values())
            if selected_bundles:
                with st.container():
                    st.markdown("---")
                    st.markdown(f"### 📦 Fila de Produção em Lote para Séries (**{len(selected_bundles)}** séries selecionadas)")
                    
                    col_sp1, col_sp2 = st.columns([2, 2])
                    with col_sp1:
                        _series_aspect_map = {
                            "💻 Horizontal 16:9 (Original 1080p Full HD - Padrão YouTube)": "16:9",
                            "📱 Vertical 9:16 (Fundo Desfocado / Blur)": "9:16_blur",
                            "📱 Vertical 9:16 (🎯 Auto-Reframing Facial)": "9:16_smart_face",
                            "📱 Vertical 9:16 (👥 Split Screen)": "9:16_split",
                            "📱 Vertical 9:16 (Corte Central 100%)": "9:16_crop"
                        }
                        series_aspect_choice = st.selectbox(
                            "Formato de Enquadramento:",
                            list(_series_aspect_map.keys()),
                            index=0,
                            key="series_aspect_choice"
                        )
                        series_aspect_mode = _series_aspect_map[series_aspect_choice]
                    with col_sp2:
                        series_sub_enabled = st.toggle("✨ Ativar Legendas Dinâmicas", value=_cfg.get("subtitle_enabled", False), key="series_sub_toggle")
                        st.caption(f"Fontes e cores: {_cfg.get('subtitle_font_size', 80)}px • Destaque {_cfg.get('subtitle_highlight_color', '#FFFF00')}")

                    if st.button(f"⚡ Iniciar Renderização em Lote ({len(selected_bundles)} Séries)", type="primary", use_container_width=True, key="btn_start_series_batch"):
                        _active_u_sbatch = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
                        _vid_id_sbatch = get_video_id(_active_u_sbatch)
                        if not _vid_id_sbatch:
                            st.error("URL do vídeo do YouTube não identificada.")
                        else:
                            s_prog_bar = st.progress(0)
                            s_status_box = st.empty()
                            s_live_logs = []

                            def _s_batch_cb(cur, tot, msg):
                                pct = int((cur / max(tot, 1)) * 100)
                                s_prog_bar.progress(min(pct, 100))
                                s_status_box.info(f"**Progresso ({cur}/{tot}):** {msg}")

                            def _s_log_cb(line):
                                s_live_logs.append(line)

                            s_batch_res = process_batch_cuts(
                                video_id=_vid_id_sbatch,
                                active_url=_active_u_sbatch,
                                cut_items=selected_bundles,
                                aspect_ratio_mode=series_aspect_mode,
                                subtitle_enabled=series_sub_enabled,
                                subtitle_highlight_color=_cfg.get("subtitle_highlight_color", "#FFFF00"),
                                subtitle_base_color=_cfg.get("subtitle_base_color", "#FFFFFF"),
                                subtitle_font_size=_cfg.get("subtitle_font_size", 80),
                                ollama_model=ollama_model,
                                aspect_params=dict(_cfg),
                                force_rerender=False,
                                progress_callback=_s_batch_cb,
                                log_callback=_s_log_cb
                            )

                            s_prog_bar.progress(100)
                            success_count = sum(1 for r in s_batch_res if r.get("success"))
                            error_items = [r for r in s_batch_res if r.get("error")]

                            if error_items:
                                err_details = "\n".join([f"- **{e.get('title', 'Série')}**: {e.get('error')}" for e in error_items])
                                st.session_state["batch_feedback"] = {
                                    "type": "warning" if success_count > 0 else "error",
                                    "msg": f"Processamento de séries concluído com {success_count} sucesso(s) e {len(error_items)} erro(s):\n{err_details}"
                                }
                            else:
                                st.session_state["batch_feedback"] = {
                                    "type": "success",
                                    "msg": f"🎉 **Renderização de séries em lote concluída com sucesso!** {success_count} séries geradas e disponíveis na Galeria (Seção 4)."
                                }
                            st.session_state["_reset_bundles_selection"] = True
                            st.rerun()

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

        if "batch_feedback" in st.session_state:
            fb = st.session_state.pop("batch_feedback")
            if fb.get("type") == "success":
                st.success(fb.get("msg", ""))
            elif fb.get("type") == "warning":
                st.warning(fb.get("msg", ""))
            else:
                st.error(fb.get("msg", ""))

        if 'shorts' in st.session_state and st.session_state.shorts:
            # Reseta seleção de checkboxes de forma segura antes da instanciação dos widgets
            if st.session_state.get("_reset_batch_selection"):
                st.session_state["_reset_batch_selection"] = False
                for s_i in range(len(st.session_state.shorts)):
                    st.session_state[f"chk_short_{s_i}"] = False
                st.session_state["batch_short_selected"] = {}

            if "batch_short_selected" not in st.session_state:
                st.session_state["batch_short_selected"] = {}

            col_bk1, col_bk2, col_bk3, _ = st.columns([1.4, 1.4, 1.4, 1.8])
            with col_bk1:
                if st.button("☑️ Marcar Tudo", key="btn_sel_all_shorts", use_container_width=True):
                    for s_i, s_item in enumerate(st.session_state.shorts):
                        st.session_state[f"chk_short_{s_i}"] = True
                        st.session_state["batch_short_selected"][s_i] = s_item
                    st.rerun()
            with col_bk2:
                if st.button("⬜ Desmarcar Tudo", key="btn_clear_shorts_batch", use_container_width=True):
                    st.session_state["_reset_batch_selection"] = True
                    st.rerun()
            with col_bk3:
                if st.button("🔄 Inverter Seleção", key="btn_invert_shorts_batch", use_container_width=True):
                    for s_i, s_item in enumerate(st.session_state.shorts):
                        cur_val = st.session_state.get(f"chk_short_{s_i}", False)
                        new_val = not cur_val
                        st.session_state[f"chk_short_{s_i}"] = new_val
                        if new_val:
                            st.session_state["batch_short_selected"][s_i] = s_item
                        else:
                            st.session_state["batch_short_selected"].pop(s_i, None)
                    st.rerun()

            st.markdown(f"### 🎬 Pequenos Cortes Gerados ({len(st.session_state.shorts)}):")
            for idx, s in enumerate(st.session_state.shorts):
                with st.container():
                    col_chk, col_info = st.columns([0.3, 4.7])
                    with col_chk:
                        chk_val = st.checkbox("Fila", key=f"chk_short_{idx}", label_visibility="collapsed")
                        if chk_val:
                            st.session_state["batch_short_selected"][idx] = s
                        else:
                            st.session_state["batch_short_selected"].pop(idx, None)
                    with col_info:
                        st.markdown(f"**{s.get('type', 'Corte')}** | `[{s['start']} → {s['end']}]` **{s['title']}**")
                        st.caption(f"⏱️ Duração: **{s.get('duration_label', '')}**")
                        if s.get('snippet'):
                            st.markdown(f"💬 *\"{s['snippet']}\"*")
                    st.divider()

            # ── PAINEL DA FILA DE PRODUÇÃO EM LOTE ────────────────────────────
            selected_items = list(st.session_state["batch_short_selected"].values())
            if selected_items:
                with st.container():
                    st.markdown("---")
                    st.markdown(f"### 📦 Fila de Produção em Lote (**{len(selected_items)}** cortes selecionados)")
                    
                    _batch_aspect_list = [
                        "📱 Vertical 9:16 (Fundo Desfocado / Blur - Shorts/TikTok/Reels)",
                        "📱 Vertical 9:16 (🎯 Rastreamento Inteligente de Rosto / Auto-Reframing)",
                        "📱 Vertical 9:16 (👥 Layout Dividido / Split Screen - Estilo Podpah & Flow)",
                        "📱 Vertical 9:16 (Corte Central 100% Tela)",
                        "💻 Horizontal 16:9 (Original 1080p Full HD)"
                    ]
                    _default_b_aspect = _cfg.get("aspect_option", _batch_aspect_list[0])
                    _b_idx = _batch_aspect_list.index(_default_b_aspect) if _default_b_aspect in _batch_aspect_list else 0

                    col_bp1, col_bp2 = st.columns(2)
                    with col_bp1:
                        batch_aspect_choice = st.selectbox(
                            "📐 Enquadramento para o Lote:",
                            _batch_aspect_list,
                            index=_b_idx,
                            key="batch_aspect_select"
                        )
                        b_aspect_map = {
                            "📱 Vertical 9:16 (Fundo Desfocado / Blur - Shorts/TikTok/Reels)": "9:16_blur",
                            "📱 Vertical 9:16 (🎯 Rastreamento Inteligente de Rosto / Auto-Reframing)": "9:16_smart_face",
                            "📱 Vertical 9:16 (👥 Layout Dividido / Split Screen - Estilo Podpah & Flow)": "9:16_split",
                            "📱 Vertical 9:16 (Corte Central 100% Tela)": "9:16_crop",
                            "💻 Horizontal 16:9 (Original 1080p Full HD)": "16:9"
                        }
                        batch_aspect_mode = b_aspect_map[batch_aspect_choice]
                        st.caption(f"🎯 Modo ativo: `{batch_aspect_mode}`")

                    with col_bp2:
                        batch_sub_enabled = st.toggle("✨ Ativar Legendas Dinâmicas", value=_cfg.get("subtitle_enabled", True), key="batch_sub_toggle")
                        st.caption(f"Fontes e cores: {_cfg.get('subtitle_font_size', 80)}px • Destaque {_cfg.get('subtitle_highlight_color', '#FFFF00')}")

                    with st.expander("⚙️ Personalizações da Fase 3 & 4 para o Lote (Headlines, Retenção, Capas & Áudio)", expanded=False):
                        col_bopt1, col_bopt2 = st.columns(2)
                        with col_bopt1:
                            b_hl_on = st.toggle("🏷️ Headline de Retenção no Topo", value=_cfg.get("headline_enabled", False), key="b_hl_toggle")
                            b_em_on = st.toggle("😃 Emojis Contextuais", value=_cfg.get("emojis_enabled", False), key="b_em_toggle")
                            b_zp_on = st.toggle("🔍 Zoom Punch Dinâmico", value=_cfg.get("zoom_punch_enabled", False), key="b_zp_toggle")
                            b_cz_on = st.toggle("🎯 Zoom de Clímax na Frase Final", value=_cfg.get("climax_zoom_enabled", False), key="b_cz_toggle")
                        with col_bopt2:
                            b_pb_on = st.toggle("⏳ Barra de Progresso no Rodapé", value=_cfg.get("progress_bar_enabled", False), key="b_pb_toggle")
                            b_co_on = st.toggle("📌 Banner de Chamada / Callout", value=_cfg.get("callout_enabled", False), key="b_co_toggle")
                            b_th_on = st.toggle("🖼️ Gerar Capa / Thumbnail 9:16", value=_cfg.get("thumbnail_enabled", True), key="b_th_toggle")
                            b_bgm_on = st.toggle("🎵 Trilha Sonora & Ducking", value=_cfg.get("bg_music_enabled", False), key="b_bgm_toggle")
                            if b_bgm_on:
                                b_bgm_trk = st.selectbox(
                                    "Trilha:",
                                    ["lofi_chill", "dynamic_pulse", "tension_suspense", "inspirational_epic"],
                                    format_func=lambda x: {"lofi_chill": "🧘 Lo-Fi Chill", "dynamic_pulse": "⚡ Dinâmica", "tension_suspense": "🔥 Tensão", "inspirational_epic": "✨ Inspiracional"}.get(x, x),
                                    key="b_bgm_trk_sel"
                                )
                            else:
                                b_bgm_trk = _cfg.get("bg_music_track_id", "lofi_chill")

                    batch_force_rerender = st.checkbox(
                        "🔄 Forçar Re-renderização de Cortes Já Gerados",
                        value=False,
                        help="Por padrão, a aplicação pula e reaproveita cortes que já foram gerados neste formato. Marque para reprocessar tudo."
                    )

                    if st.button(f"⚡ Iniciar Renderização em Lote ({len(selected_items)} Cortes)", type="primary", use_container_width=True, key="btn_start_batch"):
                        _active_u_batch = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
                        _vid_id_batch = get_video_id(_active_u_batch)
                        if not _vid_id_batch:
                            st.error("URL do vídeo do YouTube não identificada.")
                        else:
                            prog_bar = st.progress(0)
                            status_box = st.empty()

                            live_logs_list = []

                            def _batch_cb(cur, tot, msg):
                                pct = int((cur / max(tot, 1)) * 100)
                                prog_bar.progress(min(pct, 100))
                                status_box.info(f"**Progresso ({cur}/{tot}):** {msg}")

                            def _log_cb(line):
                                live_logs_list.append(line)

                            batch_params_merged = dict(_cfg)
                            batch_params_merged.update({
                                "headline_enabled": b_hl_on,
                                "emojis_enabled": b_em_on,
                                "zoom_punch_enabled": b_zp_on,
                                "climax_zoom_enabled": b_cz_on,
                                "progress_bar_enabled": b_pb_on,
                                "callout_enabled": b_co_on,
                                "callout_text": _cfg.get("callout_text", "💬 O que você acha? Comente abaixo!"),
                                "thumbnail_enabled": b_th_on,
                                "bg_music_enabled": b_bgm_on,
                                "bg_music_track_id": b_bgm_trk,
                            })

                            batch_res = process_batch_cuts(
                                video_id=_vid_id_batch,
                                active_url=_active_u_batch,
                                cut_items=selected_items,
                                aspect_ratio_mode=batch_aspect_mode,
                                subtitle_enabled=batch_sub_enabled,
                                subtitle_highlight_color=_cfg.get("subtitle_highlight_color", "#FFFF00"),
                                subtitle_base_color=_cfg.get("subtitle_base_color", "#FFFFFF"),
                                subtitle_font_size=_cfg.get("subtitle_font_size", 80),
                                ollama_model=ollama_model,
                                aspect_params=batch_params_merged,
                                force_rerender=batch_force_rerender,
                                progress_callback=_batch_cb,
                                log_callback=_log_cb
                            )

                            prog_bar.progress(100)

                            # Salva todos os logs completos para visualização e cópia
                            full_logs_text = "\n".join(live_logs_list)
                            st.session_state["last_batch_logs"] = full_logs_text

                            # Agenda o reset limpo dos checkboxes para a próxima renderização
                            st.session_state["_reset_batch_selection"] = True

                            success_count = sum(1 for r in batch_res if r.get("success"))
                            error_items = [r for r in batch_res if r.get("error")]

                            if error_items:
                                err_details = "\n".join([f"- **{e.get('title', 'Corte')}**: {e.get('error')}" for e in error_items])
                                st.session_state["batch_feedback"] = {
                                    "type": "warning" if success_count > 0 else "error",
                                    "msg": f"Processamento concluído com {success_count} sucesso(s) e {len(error_items)} erro(s):\n{err_details}"
                                }
                            else:
                                st.session_state["batch_feedback"] = {
                                    "type": "success",
                                    "msg": f"🎉 **Renderização em lote concluída com sucesso!** {success_count} cortes gerados e disponíveis na Galeria (Seção 4)."
                                }
                            st.rerun()

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

    _aspect_list = [
        "📱 Vertical 9:16 (👥 Layout Dividido / Split Screen - Estilo Podpah & Flow)",
        "📱 Vertical 9:16 (🎯 Rastreamento Inteligente de Rosto / Auto-Reframing)",
        "📱 Vertical 9:16 (Fundo Desfocado / Blur - Shorts/TikTok/Reels)",
        "📱 Vertical 9:16 (Corte Central 100% Tela)",
        "💻 Horizontal 16:9 (Original 1080p Full HD)"
    ]
    _saved_aspect = _cfg.get("aspect_option", _aspect_list[1])
    _asp_idx = _aspect_list.index(_saved_aspect) if _saved_aspect in _aspect_list else 1

    st.markdown("#### 📐 Formato de Exportação do Vídeo")
    aspect_option = st.radio(
        "Escolha o enquadramento:",
        _aspect_list,
        index=_asp_idx,
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
    subtitle_enabled = _cfg.get("subtitle_enabled", False)
    subtitle_highlight_color = _cfg.get("subtitle_highlight_color", "#FFFF00")
    subtitle_base_color = _cfg.get("subtitle_base_color", "#FFFFFF")
    subtitle_font_size = _cfg.get("subtitle_font_size", 80)

    with st.expander("📝 Legendas Dinâmicas (Estilo CapCut / Alex Hormozi)", expanded=subtitle_enabled):
        subtitle_enabled = st.toggle(
            "✨ Ativar Legendas Palavra-a-Palavra",
            value=subtitle_enabled,
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
                        value=subtitle_highlight_color,
                        key="sub_highlight_color",
                        help="Cor vibrante que pisca na palavra sendo falada."
                    )
                with col_sub2:
                    subtitle_base_color = st.color_picker(
                        "💤 Cor das Demais Palavras",
                        value=subtitle_base_color,
                        key="sub_base_color",
                        help="Cor das palavras da linha atual que ainda não foram ditas."
                    )
                with col_sub3:
                    subtitle_font_size = st.slider(
                        "🔤 Fonte",
                        min_value=40,
                        max_value=160,
                        value=subtitle_font_size,
                        step=5,
                        key="sub_font_size",
                        help="Tamanho da fonte das legendas (recomendado entre 75 e 110 para cortes 9:16 estilo Alex Hormozi)."
                    )
                st.caption("📌 Legendas no terço inferior da tela • Fonte Montserrat Bold • Contorno preto para legibilidade em qualquer fundo")

    # ─────────────────────────────────────────────────────────────────
    # 🏷️ Headline / Título Fixo de Retenção no Topo (Fase 3)
    # ─────────────────────────────────────────────────────────────────
    headline_enabled = _cfg.get("headline_enabled", False)
    headline_preset = _cfg.get("headline_preset", "yellow_black")
    headline_text_color = _cfg.get("headline_text_color", "#000000")
    headline_bg_color = _cfg.get("headline_bg_color", "#FFE600")
    headline_font_size = _cfg.get("headline_font_size", 46)
    headline_margin_top = _cfg.get("headline_margin_top", 120)

    with st.expander("🏷️ Headline / Título Fixo de Retenção no Topo (9:16 - Fase 3)", expanded=headline_enabled):
        headline_enabled = st.toggle(
            "📌 Fixar Título Chamativo no Topo do Vídeo",
            value=headline_enabled,
            help="Adiciona uma caixa de headline magnética na parte superior do corte 9:16 (estilo vídeos virais de TikTok/Reels) que segura a atenção nos primeiros segundos."
        )
        if headline_enabled:
            col_hp1, col_hp2, col_hp3 = st.columns([2, 1.2, 1.2])
            with col_hp1:
                preset_keys = list(HEADLINE_PRESETS.keys()) + ["custom"]
                preset_labels = [HEADLINE_PRESETS[k]["name"] for k in HEADLINE_PRESETS] + ["🎨 Cores Personalizadas"]
                cur_preset_idx = preset_keys.index(headline_preset) if headline_preset in preset_keys else 0
                sel_preset_label = st.selectbox("Estilo Visual da Headline:", preset_labels, index=cur_preset_idx)
                headline_preset = preset_keys[preset_labels.index(sel_preset_label)]

            with col_hp2:
                headline_font_size = st.slider("Tamanho da Fonte:", 28, 70, headline_font_size, 2, key="hl_font_sz")

            with col_hp3:
                headline_margin_top = st.slider("Margem do Topo:", 60, 240, headline_margin_top, 10, key="hl_margin_tp", help="Distância da borda superior para não cobrir elementos da interface do TikTok/Shorts.")

            if headline_preset == "custom":
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    headline_text_color = st.color_picker("Cor do Texto:", headline_text_color, key="hl_txt_col")
                with col_c2:
                    headline_bg_color = st.color_picker("Cor da Caixa de Fundo:", headline_bg_color, key="hl_bg_col")

            st.caption("💡 O texto da Headline puxará automaticamente o Título Viral gerado pela IA ou digitado no Kit de Publicação abaixo.")

    # ─────────────────────────────────────────────────────────────────
    # 🖼️ Efeitos Visuais & Retenção de Feed (Fases 3 e 4)
    # ─────────────────────────────────────────────────────────────────
    zoom_punch_enabled = _cfg.get("zoom_punch_enabled", False)
    emojis_enabled = _cfg.get("emojis_enabled", False)

    with st.expander("🖼️ Efeitos de Retenção Visual (Zoom Punch & Emojis - Fase 3)", expanded=(zoom_punch_enabled or emojis_enabled)):
        col_ef1, col_ef2 = st.columns(2)
        with col_ef1:
            zoom_punch_enabled = st.toggle(
                "🔍 Zoom Punch Dinâmico",
                value=zoom_punch_enabled,
                help="Aplica pulsos suaves de aproximação (1.07x) a cada ~8 segundos para quebrar a monotonia visual e elevar a retenção de feed."
            )
        with col_ef2:
            emojis_enabled = st.toggle(
                "😃 Emojis Contextuais nas Legendas",
                value=emojis_enabled,
                help="Insere automaticamente stickers e emojis (💰, 🔥, 🚀, 🧠, ⚠️) ao lado de palavras de alta carga emocional."
            )

    # ─────────────────────────────────────────────────────────────────
    # 🚀 Polimento Visual, Thumbnails & Retenção Dinâmica (Fase 4)
    # ─────────────────────────────────────────────────────────────────
    progress_bar_enabled = _cfg.get("progress_bar_enabled", False)
    progress_bar_color = _cfg.get("progress_bar_color", "#FF0000")
    progress_bar_height = int(_cfg.get("progress_bar_height", 8))
    callout_enabled = _cfg.get("callout_enabled", False)
    callout_preset = _cfg.get("callout_preset", "comment")
    callout_text = _cfg.get("callout_text", "💬 O que você acha? Comente abaixo!")
    callout_duration = float(_cfg.get("callout_duration", 4.5))
    climax_zoom_enabled = _cfg.get("climax_zoom_enabled", False)
    climax_zoom_factor = float(_cfg.get("climax_zoom_factor", 1.14))
    thumbnail_enabled = _cfg.get("thumbnail_enabled", True)

    with st.expander("🚀 Retenção Dinâmica, Thumbnails & Callout (Fase 4)", expanded=(progress_bar_enabled or callout_enabled or climax_zoom_enabled or thumbnail_enabled)):
        col_f4_1, col_f4_2 = st.columns(2)
        with col_f4_1:
            progress_bar_enabled = st.toggle(
                "⏳ Barra de Progresso no Rodapé",
                value=progress_bar_enabled,
                help="Desenha uma linha minimalista no rodapé indicando o progresso do corte para reter o espectador até o final."
            )
            if progress_bar_enabled:
                col_pb1, col_pb2 = st.columns([1.5, 1])
                with col_pb1:
                    pb_color_keys = list(PROGRESS_BAR_COLORS.keys())
                    pb_color_labels = [PROGRESS_BAR_COLORS[k]["name"] for k in pb_color_keys]
                    cur_pb_col_idx = 0
                    for i_k, k in enumerate(pb_color_keys):
                        if PROGRESS_BAR_COLORS[k]["color"].upper() == progress_bar_color.upper():
                            cur_pb_col_idx = i_k
                            break
                    sel_pb_label = st.selectbox("Cor da Barra:", pb_color_labels, index=cur_pb_col_idx, key="sel_pb_color")
                    progress_bar_color = PROGRESS_BAR_COLORS[pb_color_keys[pb_color_labels.index(sel_pb_label)]]["color"]
                with col_pb2:
                    progress_bar_height = st.slider("Espessura (px):", 4, 18, progress_bar_height, 2, key="sl_pb_height")

            st.divider()

            climax_zoom_enabled = st.toggle(
                "🎯 Zoom de Ênfase no Clímax (Punchline Final)",
                value=climax_zoom_enabled,
                help="Aproxima dramaticamente no rosto do orador nos últimos segundos da conclusão para reforçar a frase de impacto."
            )
            if climax_zoom_enabled:
                climax_zoom_factor = st.slider(
                    "Intensidade do Zoom de Clímax:",
                    1.06, 1.25, climax_zoom_factor, 0.02,
                    format="%.2fx",
                    help="1.08x = Suave | 1.14x = Médio/Dramático | 1.20x = Impacto Forte"
                )

        with col_f4_2:
            thumbnail_enabled = st.toggle(
                "🖼️ Gerar Capa / Thumbnail 9:16 com IA",
                value=thumbnail_enabled,
                help="Captura automaticamente o melhor frame com MediaPipe/nitidez, compõe com a Headline magnética e salva thumbnail.jpg na pasta do corte."
            )

            st.divider()

            callout_enabled = st.toggle(
                "📌 Banner de Chamada / Lower Third (Callout)",
                value=callout_enabled,
                help="Exibe um banner elegante nos últimos 4-5 segundos provocando comentários e seguidores nas redes."
            )
            if callout_enabled:
                co_keys = list(ENGAGEMENT_CALLOUT_PRESETS.keys())
                co_labels = [ENGAGEMENT_CALLOUT_PRESETS[k]["name"] for k in co_keys]
                cur_co_idx = co_keys.index(callout_preset) if callout_preset in co_keys else 0
                sel_co_label = st.selectbox("Modelo de Chamada:", co_labels, index=cur_co_idx, key="sel_co_preset")
                callout_preset = co_keys[co_labels.index(sel_co_label)]

                if callout_preset != "custom":
                    callout_text = ENGAGEMENT_CALLOUT_PRESETS[callout_preset]["text"]

                callout_text = st.text_input(
                    "Texto do Banner:",
                    value=callout_text,
                    key="txt_callout_val"
                )
                callout_duration = st.slider("Duração do Banner (segundos no final):", 3.0, 7.0, callout_duration, 0.5, key="sl_co_dur")

    # ─────────────────────────────────────────────────────────────────
    # 🎵 Trilha Sonora de Fundo & Audio Ducking Inteligente (Fase 3)
    # ─────────────────────────────────────────────────────────────────
    bg_music_enabled = _cfg.get("bg_music_enabled", False)
    bg_music_track_id = _cfg.get("bg_music_track_id", "lofi_chill")
    bg_music_volume = float(_cfg.get("bg_music_volume", 0.15))
    ducking_preset = _cfg.get("ducking_preset", "medio")

    available_tracks = list_available_tracks()
    track_ids = [t["id"] for t in available_tracks]
    track_labels = [f"{t['title']} — {t['description']}" for t in available_tracks]
    cur_track_idx = track_ids.index(bg_music_track_id) if bg_music_track_id in track_ids else 0

    with st.expander("🎵 Trilha Sonora & Audio Ducking Inteligente (Fase 3)", expanded=bg_music_enabled):
        bg_music_enabled = st.toggle(
            "🎶 Adicionar Música de Fundo com Audio Ducking",
            value=bg_music_enabled,
            help="A música toca no fundo e reduz suavemente de volume sempre que alguém estiver falando (via sidechaincompress FFmpeg)."
        )
        bg_music_track_path = None
        if bg_music_enabled and available_tracks:
            col_m1, col_m2 = st.columns([2, 1.2])
            with col_m1:
                sel_track_label = st.selectbox("Escolha a Trilha Sonora:", track_labels, index=cur_track_idx)
                selected_track_obj = available_tracks[track_labels.index(sel_track_label)]
                bg_music_track_id = selected_track_obj["id"]
                bg_music_track_path = selected_track_obj["path"]

                # Player de áudio para prévia da música
                if os.path.exists(bg_music_track_path):
                    with open(bg_music_track_path, "rb") as af_prev:
                        st.audio(af_prev.read(), format="audio/wav")

            with col_m2:
                bg_music_volume = st.slider("Volume da Música:", 0.05, 0.40, bg_music_volume, 0.02, format="%.2f", help="Volume base da música quando não houver fala.")
                duck_keys = list(DUCKING_PRESETS.keys())
                duck_labels = [DUCKING_PRESETS[k]["name"] for k in duck_keys]
                cur_duck_idx = duck_keys.index(ducking_preset) if ducking_preset in duck_keys else 1
                sel_duck_label = st.selectbox("Atenuação na Fala (Ducking):", duck_labels, index=cur_duck_idx)
                ducking_preset = duck_keys[duck_labels.index(sel_duck_label)]

        elif not available_tracks:
            st.info("Nenhuma trilha encontrada em assets/audio.")

    # Salva continuamente todas as configurações ativas
    save_all_settings({
        "device_option": device_option,
        "model_size": model_size,
        "ollama_model": ollama_model,
        "analysis_strategy": strategy_choice,
        "aspect_option": aspect_option,
        "face_auto_zoom": face_zoom_active,
        "face_margin_ratio": face_margin_val,
        "person_preference": person_pref_val,
        "split_auto_switch": split_auto_switch,
        "split_zoom": split_zoom_val,
        "split_divider_color": split_div_color,
        "split_divider_width": split_div_w,
        "blur_zoom_custom": blur_zoom_val,
        "blur_intensity": blur_int_val,
        "blur_pan_custom": blur_pan_val,
        "subtitle_enabled": subtitle_enabled,
        "subtitle_highlight_color": subtitle_highlight_color,
        "subtitle_base_color": subtitle_base_color,
        "subtitle_font_size": subtitle_font_size,
        "headline_enabled": headline_enabled,
        "headline_preset": headline_preset,
        "headline_text_color": headline_text_color,
        "headline_bg_color": headline_bg_color,
        "headline_font_size": headline_font_size,
        "headline_margin_top": headline_margin_top,
        "zoom_punch_enabled": zoom_punch_enabled,
        "emojis_enabled": emojis_enabled,
        "progress_bar_enabled": progress_bar_enabled,
        "progress_bar_color": progress_bar_color,
        "progress_bar_height": progress_bar_height,
        "callout_enabled": callout_enabled,
        "callout_preset": callout_preset,
        "callout_text": callout_text,
        "callout_duration": callout_duration,
        "climax_zoom_enabled": climax_zoom_enabled,
        "climax_zoom_factor": climax_zoom_factor,
        "thumbnail_enabled": thumbnail_enabled,
        "bg_music_enabled": bg_music_enabled,
        "bg_music_track_id": bg_music_track_id,
        "bg_music_volume": bg_music_volume,
        "ducking_preset": ducking_preset,
    })

    # ─────────────────────────────────────────────────────────────────
    # Kit de Publicação Viral & Título (IA)
    # ─────────────────────────────────────────────────────────────────
    _active_url_cat = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
    _vid_id_cat = get_video_id(_active_url_cat) or ""

    # Consulta se a minutagem e o formato específico já foram gerados anteriormente
    existing_cut = get_cut_entry(_vid_id_cat, start_time, end_time) if (_vid_id_cat and start_time and end_time) else None
    existing_inst = get_format_instance(_vid_id_cat, start_time, end_time, selected_aspect) if (_vid_id_cat and start_time and end_time) else None

    if "meta_generated" not in st.session_state:
        st.session_state["meta_generated"] = False

    # Se existe entrada salva no catálogo para esta minutagem, sincroniza automaticamente
    if existing_cut and not st.session_state.get("meta_generated"):
        st.session_state["input_cut_title"] = existing_cut.get("title", "Corte Selecionado")
        st.session_state["input_cut_desc"] = existing_cut.get("description", "")
        st.session_state["input_cut_hashtags"] = " ".join(existing_cut.get("hashtags", []))
        st.session_state["input_cut_tags_seo"] = existing_cut.get("tags_seo", "")
        st.session_state["meta_generated"] = True
    elif "input_cut_title" not in st.session_state or not st.session_state["input_cut_title"]:
        if st.session_state.get("final_corte_title"):
            st.session_state["input_cut_title"] = st.session_state["final_corte_title"]
            st.session_state["meta_generated"] = True

    with st.expander("🚀 Kit de Publicação Viral (Título, Descrição & Tags para Redes)", expanded=True):
        col_meta_btn, col_meta_status = st.columns([1.8, 2.2])
        with col_meta_btn:
            if st.button("✨ Gerar Título e Textos com IA", use_container_width=True, type="secondary", help="Analisa o trecho exato do corte e gera Título Viral específico, Descrição contextualizada com CTA e Hashtags estratégicas."):
                _transcript_path_meta = os.path.join("data", _vid_id_cat, "transcript.json") if _vid_id_cat else ""
                if not os.path.exists(_transcript_path_meta):
                    st.warning("⚠️ Transcrição não encontrada. Transcreva o vídeo na Seção 1 primeiro.")
                elif not start_time or not end_time:
                    st.warning("⚠️ Defina o tempo inicial e final do corte primeiro.")
                else:
                    with st.spinner(f"Analisando falas de [{start_time} → {end_time}] e gerando kit viral com {ollama_model}..."):
                        import core.analyzer
                        from core.subtitle_burner import extract_words_in_range
                        words_meta = extract_words_in_range(_transcript_path_meta, start_time, end_time)
                        snippet_text = " ".join(w["word"] for w in words_meta)
                        if not snippet_text:
                            st.warning("Nenhuma fala encontrada no intervalo selecionado.")
                        else:
                            model_for_meta = ollama_model if 'ollama_model' in locals() and ollama_model else "llama3"
                            meta_res = core.analyzer.generate_viral_cut_metadata(snippet_text, model=model_for_meta)
                            
                            st.session_state["input_cut_title"] = meta_res.get("titulo_principal", "Corte Selecionado")
                            st.session_state["input_cut_headline"] = meta_res.get("headline_topo") or meta_res.get("titulo_principal", "Corte Selecionado")
                            st.session_state["input_cut_desc"] = meta_res.get("descricao", "")
                            st.session_state["input_cut_hashtags"] = " ".join(meta_res.get("hashtags", ["#shorts", "#viral", "#cortes"]))
                            st.session_state["input_cut_tags_seo"] = meta_res.get("tags_seo", "")
                            st.session_state["meta_alt_titles"] = meta_res.get("titulos_alternativos", [])
                            st.session_state["meta_generated"] = True
                            st.rerun()

        with col_meta_status:
            if existing_inst:
                st.success(f"⚡ **Instância Encontrada no Cache ({existing_inst.get('rendered_at')})!**")
            elif existing_cut:
                other_formats = list(existing_cut.get("formats", {}).keys())
                st.info(f"💡 Minutagem já gerada em: `{', '.join(other_formats)}`. Textos reaproveitados!")
            elif st.session_state.get("meta_generated"):
                st.success("✅ **Textos Gerados pela IA!** Conteúdo contextual pronto para postagem.")
            else:
                st.info("ℹ️ Clique no botão ao lado para gerar textos específicos com base no áudio.")

        # Sinalização visual no título de cada campo
        is_gen = st.session_state.get("meta_generated", False)
        badge_title = "🟢 [GERADO POR IA]" if is_gen else "⚪ [PADRÃO - CLIQUE ACIMA PARA GERAR]"
        badge_desc = "🟢 [GERADA POR IA COM CTA]" if is_gen else "⚪ [PADRÃO]"
        badge_tags = "🟢 [TAGS CONTEXTUAIS]" if is_gen else "⚪ [PADRÃO]"

        col_t1, col_t2 = st.columns([1.4, 1.0])
        with col_t1:
            cut_title_val = st.text_input(
                f"🏷️ Título do Corte (YouTube/Redes) {badge_title}:",
                value=st.session_state.get("input_cut_title", "Corte Selecionado"),
                key="input_cut_title"
            )
        with col_t2:
            cut_headline_val = st.text_input(
                f"📌 Headline de Topo 9:16 (Curta) {badge_title}:",
                value=st.session_state.get("input_cut_headline", st.session_state.get("input_cut_title", "Corte Selecionado")),
                key="input_cut_headline",
                help="Frase de gancho curta e completa (máx 35-40 caracteres) fixada na caixa magnética no topo do vídeo."
            )
        
        # Prévia do nome da pasta e do arquivo de vídeo gerados
        _preview_folder = build_cut_folder_name(selected_aspect, cut_title_val)
        st.caption(f"📁 **Pasta da Instância ({selected_aspect}):** `data/{_vid_id_cat}/{_preview_folder}/`  |  🎬 **Vídeo:** `{_preview_folder}.mp4`")

        # Se houver títulos alternativos sugeridos pela IA, exibe botões rápidos de troca
        alt_titles = st.session_state.get("meta_alt_titles", [])
        if alt_titles:
            st.markdown("💡 **Variações de Título Sugeridas pela IA (Clique para aplicar):**")
            col_alts = st.columns(len(alt_titles))
            for idx_alt, alt_t in enumerate(alt_titles):
                with col_alts[idx_alt]:
                    if st.button(f"📌 {alt_t}", key=f"btn_alt_title_{idx_alt}", use_container_width=True):
                        st.session_state["input_cut_title"] = alt_t
                        st.rerun()

        col_desc, col_tags = st.columns([1.5, 1])
        with col_desc:
            cut_desc_val = st.text_area(
                f"📝 Descrição / Legenda {badge_desc}:",
                value=st.session_state.get("input_cut_desc", "Confira a declaração e participe do debate nos comentários!"),
                height=110,
                key="input_cut_desc"
            )
        with col_tags:
            cut_hashtags_val = st.text_input(
                f"🏷️ Hashtags {badge_tags}:",
                value=st.session_state.get("input_cut_hashtags", "#shorts #viral #cortes #reels"),
                key="input_cut_hashtags"
            )
            cut_tags_seo_val = st.text_input(
                f"🔍 Tags SEO {badge_tags}:",
                value=st.session_state.get("input_cut_tags_seo", "cortes, viral, shorts, podcast, debate"),
                key="input_cut_tags_seo"
            )

        # Se a minutagem já existe no catálogo, botão para salvar edições de texto instantaneamente
        if existing_cut:
            if st.button("💾 Atualizar Apenas Textos no Disco (Sem Re-renderizar Vídeo)", use_container_width=True):
                _meta_file_quick = os.path.join("data", _vid_id_cat, "metadata.json")
                orig_info_quick = {}
                if os.path.exists(_meta_file_quick):
                    try:
                        with open(_meta_file_quick, "r", encoding="utf-8") as _mfq:
                            orig_info_quick = json.load(_mfq)
                    except Exception:
                        pass
                update_res = update_cut_texts_only(
                    video_id=_vid_id_cat,
                    start_time=start_time,
                    end_time=end_time,
                    title=cut_title_val,
                    description=cut_desc_val,
                    hashtags=cut_hashtags_val.split(),
                    tags_seo=cut_tags_seo_val,
                    orig_video_info=orig_info_quick
                )
                st.success("✅ Arquivos de texto atualizados com sucesso em todas as instâncias existentes deste corte!")

    # Exibição imediata da instância existente do cache se já renderizada
    if existing_inst and os.path.exists(existing_inst.get("video_path", "")):
        st.markdown(f"#### 🎬 Prévia da Instância Pronta ({aspect_option})")
        
        cached_thumb = existing_inst.get("thumbnail_path") or os.path.join(existing_inst.get("folder_path", ""), "thumbnail.jpg")
        has_cached_thumb = cached_thumb and os.path.exists(cached_thumb)

        if "9:16" in selected_aspect:
            if has_cached_thumb:
                col_pv1, col_pv2, col_pv3, col_pv4 = st.columns([1.0, 1.2, 1.2, 1.0])
                with col_pv2:
                    st.caption("🎬 **Vídeo Renderizado:**")
                    st.video(existing_inst["video_path"])
                with col_pv3:
                    st.caption("🖼️ **Capa / Thumbnail (9:16):**")
                    st.image(cached_thumb, use_container_width=True)
            else:
                col_pv1, col_pv2, col_pv3 = st.columns([1.6, 1.2, 1.6])
                with col_pv2:
                    st.video(existing_inst["video_path"])
        else:
            col_pv1, col_pv2, col_pv3 = st.columns([1, 2, 1])
            with col_pv2:
                st.video(existing_inst["video_path"])

        col_dl1, col_dl2 = st.columns([2, 1.2] if has_cached_thumb else [1, 0.001])
        with col_dl1:
            with open(existing_inst["video_path"], "rb") as vf_cached:
                st.download_button(
                    label=f"💾 Baixar Vídeo Pronto do Cache ({existing_inst['video_filename']})",
                    data=vf_cached,
                    file_name=existing_inst["video_filename"],
                    mime="video/mp4",
                    type="primary",
                    use_container_width=True,
                    key="btn_dl_cached_instance"
                )
        if has_cached_thumb:
            with col_dl2:
                with open(cached_thumb, "rb") as tf_cached:
                    st.download_button(
                        label="🖼️ Baixar Thumbnail (JPG)",
                        data=tf_cached,
                        file_name="thumbnail.jpg",
                        mime="image/jpeg",
                        type="secondary",
                        use_container_width=True,
                        key="btn_dl_cached_thumb"
                    )
        st.caption(f"⚡ Carregado instantaneamente do cache: `{existing_inst['folder_path']}`")

    st.markdown("")
    render_button_label = "🔄 Forçar Re-renderização no Formato Escolhido" if existing_inst else "✂️ Gerar Corte no Formato Escolhido"
    if st.button(render_button_label, type="primary" if not existing_inst else "secondary", use_container_width=True):
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
                # Normaliza o aspect ratio para nome de arquivo temporário seguro
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
                    if headline_enabled:
                        extra_info += " + 🏷️ Headline"
                    if bg_music_enabled:
                        extra_info += " + 🎵 Música/Ducking"

                    with st.spinner(f"Renderizando corte [{start_time} → {end_time}] no formato {aspect_option}{extra_info}..."):
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
                            # Fase 3: Retenção & Áudio
                            headline_enabled=headline_enabled,
                            headline_text=cut_headline_val,
                            headline_preset=headline_preset,
                            headline_text_color=headline_text_color,
                            headline_bg_color=headline_bg_color,
                            headline_font_size=headline_font_size,
                            headline_margin_top=headline_margin_top,
                            emojis_enabled=emojis_enabled,
                            zoom_punch_enabled=zoom_punch_enabled,
                            bg_music_enabled=bg_music_enabled,
                            bg_music_track_path=bg_music_track_path,
                            bg_music_volume=bg_music_volume,
                            ducking_preset=ducking_preset,
                            # Fase 4: Retenção Dinâmica & Thumbnails
                            progress_bar_enabled=progress_bar_enabled,
                            progress_bar_color=progress_bar_color,
                            progress_bar_height=progress_bar_height,
                            callout_enabled=callout_enabled,
                            callout_text=callout_text,
                            callout_duration=callout_duration,
                            climax_zoom_enabled=climax_zoom_enabled,
                            climax_zoom_factor=climax_zoom_factor,
                            thumbnail_enabled=thumbnail_enabled,
                        )
                        if cut_res.get("error"):
                            st.error(f"Erro ao cortar: {cut_res['error']}")
                        else:
                            out_res = get_video_resolution(corte_output_path)
                            _sub_badge = " 📝 Legendas" if subtitle_enabled and not cut_res.get("subtitle_error") and not cut_res.get("subtitle_warning") else ""
                            _hl_badge = " 🏷️ Headline" if headline_enabled else ""
                            _mus_badge = " 🎵 Ducking" if bg_music_enabled else ""
                            _pb_badge = " ⏳ Barra" if progress_bar_enabled else ""
                            _cz_badge = " 🎯 Clímax" if climax_zoom_enabled else ""
                            _th_badge = " 🖼️ Thumbnail" if thumbnail_enabled and cut_res.get("thumbnail_path") else ""
                            st.success(f"🎉 Corte gerado com sucesso! Resolução: **{out_res}** | Formato: **{aspect_option}**{_sub_badge}{_hl_badge}{_mus_badge}{_pb_badge}{_cz_badge}{_th_badge}")
                            
                            # Avisos de legendas / áudio
                            if cut_res.get("subtitle_error"):
                                st.warning(f"⚠️ Legendas não aplicadas: {cut_res['subtitle_error']}")
                            elif cut_res.get("subtitle_warning"):
                                st.info(f"ℹ️ {cut_res['subtitle_warning']}")
                            if cut_res.get("audio_warning"):
                                st.info(f"ℹ️ {cut_res['audio_warning']}")
                            
                            gen_thumb_path = cut_res.get("thumbnail_path")
                            has_gen_thumb = gen_thumb_path and os.path.exists(gen_thumb_path)

                            if "9:16" in selected_aspect:
                                if has_gen_thumb:
                                    col_v1, col_v2, col_v3, col_v4 = st.columns([1.0, 1.2, 1.2, 1.0])
                                    with col_v2:
                                        st.caption("🎬 **Vídeo Renderizado:**")
                                        st.video(corte_output_path)
                                    with col_v3:
                                        st.caption("🖼️ **Capa / Thumbnail (9:16):**")
                                        st.image(gen_thumb_path, use_container_width=True)
                                else:
                                    col_v1, col_v2, col_v3 = st.columns([1.6, 1.2, 1.6])
                                    with col_v2:
                                        st.video(corte_output_path)
                            else:
                                col_v1, col_v2, col_v3 = st.columns([1, 2, 1])
                                with col_v2:
                                    st.video(corte_output_path)
                            
                            # Carrega metadados do vídeo original
                            _meta_file = os.path.join(data_dir, "metadata.json")
                            orig_info = {}
                            if os.path.exists(_meta_file):
                                try:
                                    with open(_meta_file, "r", encoding="utf-8") as _mf:
                                        orig_info = json.load(_mf)
                                except Exception:
                                    pass
                            if not orig_info:
                                orig_info = {
                                    "title": f"Vídeo {video_id}",
                                    "channel": "Canal Oficial",
                                    "upload_date": "N/D",
                                    "url": active_url
                                }

                            # Criação da Pasta Estruturada do Corte (sem arquivo ZIP)
                            import core.export_kit
                            package_res = core.export_kit.create_viral_package(
                                video_path=corte_output_path,
                                title=cut_title_val,
                                description=cut_desc_val,
                                hashtags=cut_hashtags_val.split(),
                                tags_seo=cut_tags_seo_val,
                                aspect_mode=selected_aspect,
                                output_base_dir=data_dir,
                                orig_video_info=orig_info,
                                thumbnail_path=gen_thumb_path
                            )

                            # Registra no Catálogo de Cortes
                            register_cut_instance(
                                video_id=video_id,
                                start_time=start_time,
                                end_time=end_time,
                                title=cut_title_val,
                                description=cut_desc_val,
                                hashtags=cut_hashtags_val.split(),
                                tags_seo=cut_tags_seo_val,
                                aspect_mode=selected_aspect,
                                folder_name=package_res["folder_name"],
                                folder_path=package_res["package_dir"],
                                video_path=package_res["video_dest_path"],
                                resolution=out_res,
                                thumbnail_path=package_res.get("thumbnail_dest_path")
                            )

                            # Botões de Ação do Corte Renderizado
                            saved_thumb = package_res.get("thumbnail_dest_path")
                            has_saved_thumb = saved_thumb and os.path.exists(saved_thumb)

                            if has_saved_thumb:
                                col_b1, col_b_th, col_b2, col_b3 = st.columns([1.5, 1.2, 1.2, 1.2])
                            else:
                                col_b1, col_b2, col_b3 = st.columns([1.5, 1.2, 1.2])

                            with col_b1:
                                with open(package_res["video_dest_path"], "rb") as vf:
                                    st.download_button(
                                        label=f"💾 Baixar Vídeo ({package_res['video_filename']})",
                                        data=vf,
                                        file_name=package_res["video_filename"],
                                        mime="video/mp4",
                                        type="primary",
                                        use_container_width=True
                                    )

                            if has_saved_thumb:
                                with col_b_th:
                                    with open(saved_thumb, "rb") as tf_btn:
                                        st.download_button(
                                            label="🖼️ Baixar Thumbnail",
                                            data=tf_btn,
                                            file_name="thumbnail.jpg",
                                            mime="image/jpeg",
                                            type="secondary",
                                            use_container_width=True
                                        )
                            with col_b2:
                                with st.popover("🔴 Publicar no Shorts", use_container_width=True):
                                    st.markdown("##### 🚀 Enviar para o YouTube Shorts")
                                    yt_priv = st.selectbox(
                                        "Privacidade:",
                                        ["unlisted", "private", "public"],
                                        format_func=lambda x: {"unlisted": "🔗 Não Listado (Recomendado)", "private": "🔒 Privado / Rascunho", "public": "🌍 Público"}[x],
                                        key="yt_priv_single"
                                    )
                                    if st.button("Confirmar Upload", key="btn_conf_yt_single", type="primary", use_container_width=True):
                                        with st.spinner("Enviando vídeo para o canal do YouTube..."):
                                            yt_res = upload_to_youtube_shorts(
                                                video_path=package_res["video_dest_path"],
                                                title=cut_title_val,
                                                description=cut_desc_val,
                                                tags=cut_hashtags_val.split(),
                                                privacy_status=yt_priv,
                                                client_secrets_path=_cfg.get("youtube_client_secrets_path")
                                            )
                                            if yt_res.get("success"):
                                                st.success(f"🎉 Publicado com sucesso! [Ver no Shorts]({yt_res.get('url')})")
                                            else:
                                                st.error(f"Erro no upload: {yt_res.get('error')}")
                            with col_b3:
                                if st.button("📡 Disparar Webhook", key="btn_send_wh_single", use_container_width=True, help="Envia o pacote com vídeo e metadados para seu webhook configurado (n8n, Make, Zapier)"):
                                    wh_url = _cfg.get("webhook_url", "")
                                    if not wh_url:
                                        st.warning("Configure a URL do Webhook na barra lateral primeiro.")
                                    else:
                                        with st.spinner("Despachando para o Webhook..."):
                                            wh_payload = {
                                                "event": "cut_ready",
                                                "video_id": video_id,
                                                "title": cut_title_val,
                                                "description": cut_desc_val,
                                                "hashtags": cut_hashtags_val.split(),
                                                "tags_seo": cut_tags_seo_val,
                                                "start_time": start_time,
                                                "end_time": end_time,
                                                "aspect_mode": selected_aspect,
                                                "video_path": package_res["video_dest_path"],
                                                "video_filename": package_res["video_filename"],
                                                "folder_path": package_res["package_dir"],
                                                "original_video": orig_info
                                            }
                                            wh_res = send_to_webhook(wh_url, wh_payload, auth_header=_cfg.get("webhook_auth_header", ""))
                                            if wh_res.get("success"):
                                                st.success(f"✅ Webhook acionado! HTTP {wh_res.get('status_code')}")
                                            else:
                                                st.error(f"Falha no webhook: {wh_res.get('error')}")

                            with st.expander(f"📁 Pasta de Publicação Criada em: data/{video_id}/{package_res['folder_name']}/", expanded=True):
                                st.markdown(f"**🎬 Arquivo de Vídeo:** `{package_res['video_filename']}`")
                                st.markdown(f"**📌 Título:** `{cut_title_val}`")
                                st.markdown(f"**📝 Legenda para Redes:**\n```\n{cut_desc_val}\n```")
                                st.markdown(f"**🏷️ Hashtags:** `{cut_hashtags_val}`")
                                st.markdown(f"**🔍 Tags SEO:** `{cut_tags_seo_val}`")
                                st.divider()
                                st.markdown("##### 📺 Dados do Vídeo Original Salvos no `info_publicacao.txt`:")
                                st.markdown(f"• **Título Original:** {orig_info.get('title')}\n• **Canal:** {orig_info.get('channel')}\n• **Lançamento:** {orig_info.get('upload_date')}\n• **Link:** {orig_info.get('url')}")


    # ─────────────────────────────────────────────────────────────────
    # SEÇÃO 4: GALERIA DE CORTES PRODUZIDOS
    # ─────────────────────────────────────────────────────────────────
    _active_u_gal = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
    _vid_id_gal = get_video_id(_active_u_gal) or ""

    if _vid_id_gal:
        st.markdown("---")
        st.header("4. 🎬 Galeria de Cortes Produzidos")
        st.markdown("Visualize, reproduza e baixe todos os cortes finalizados para este vídeo.")

        catalog_gal = load_cuts_catalog(_vid_id_gal)
        if not catalog_gal:
            st.info("Nenhum corte registrado nesta galeria ainda. Gere cortes individuais na **Seção 3** ou use a **Renderização em Lote** na **Seção 2**!")
        else:
            st.caption(f"📁 Total de **{len(catalog_gal)}** minutagens e instâncias registradas no catálogo.")
            for c_idx, (t_key, cut_item) in enumerate(catalog_gal.items()):
                with st.container():
                    # Cabeçalho do corte
                    st.subheader(f"📌 {cut_item.get('title', 'Corte sem título')}")
                    st.caption(f"⏱️ Trecho: `[{cut_item.get('start_time')} → {cut_item.get('end_time')}]` • Atualizado em: `{cut_item.get('updated_at', 'N/D')}`")

                    # Instâncias de formatos renderizadas para esta minutagem
                    formats_dict = cut_item.get("formats", {})
                    if formats_dict:
                        num_fmt = len(formats_dict)
                        if num_fmt == 1:
                            f_cols = st.columns([1.3, 2.7])
                        elif num_fmt == 2:
                            f_cols = st.columns([1.3, 1.3, 1.4])
                        elif num_fmt == 3:
                            f_cols = st.columns([1.1, 1.1, 1.1, 0.7])
                        else:
                            f_cols = st.columns(num_fmt)

                        for f_idx, (fmt_key, fmt_data) in enumerate(formats_dict.items()):
                            with f_cols[f_idx]:
                                fmt_badge = {
                                    "9:16_smart_face": "📱 9:16 Smart Face (VRIRA)",
                                    "9:16_split": "📱 9:16 Split Screen (VLDSS)",
                                    "9:16_blur": "📱 9:16 Blur (VFDBS)",
                                    "9:16_crop": "📱 9:16 Crop (VCCFT)",
                                    "16:9": "💻 16:9 Original (HOFHD)"
                                }.get(fmt_key, fmt_key)
                                
                                st.markdown(f"**{fmt_badge}**")
                                v_file = fmt_data.get("video_path")
                                g_thumb = fmt_data.get("thumbnail_path") or os.path.join(fmt_data.get("folder_path", ""), "thumbnail.jpg")
                                has_g_thumb = g_thumb and os.path.exists(g_thumb)

                                if v_file and os.path.exists(v_file):
                                    st.video(v_file)
                                    
                                    if has_g_thumb:
                                        with st.expander("🖼️ Visualizar Capa / Thumbnail (9:16)", expanded=False):
                                            st.image(g_thumb, use_container_width=True)
                                            with open(g_thumb, "rb") as tf_gal:
                                                st.download_button(
                                                    label="💾 Baixar Thumbnail (JPG)",
                                                    data=tf_gal,
                                                    file_name="thumbnail.jpg",
                                                    mime="image/jpeg",
                                                    key=f"dl_thumb_gal_{c_idx}_{f_idx}",
                                                    use_container_width=True
                                                )

                                    col_b_dl, col_b_yt, col_b_wh, col_b_del = st.columns([2, 1.2, 1.2, 0.8])
                                    with col_b_dl:
                                        with open(v_file, "rb") as vf_gal:
                                            st.download_button(
                                                label=f"💾 Baixar ({fmt_data.get('resolution', 'HD')})",
                                                data=vf_gal,
                                                file_name=fmt_data.get("video_filename", f"{fmt_key}.mp4"),
                                                mime="video/mp4",
                                                key=f"dl_gal_{c_idx}_{f_idx}",
                                                use_container_width=True
                                            )
                                    with col_b_yt:
                                        with st.popover("🔴 Shorts", use_container_width=True, help="Publicar no YouTube Shorts"):
                                            st.markdown(f"##### 🚀 Upload: {cut_item.get('title', 'Corte')[:30]}...")
                                            g_yt_priv = st.selectbox(
                                                "Privacidade:",
                                                ["unlisted", "private", "public"],
                                                format_func=lambda x: {"unlisted": "🔗 Não Listado", "private": "🔒 Privado", "public": "🌍 Público"}[x],
                                                key=f"yt_priv_gal_{c_idx}_{f_idx}"
                                            )
                                            if st.button("Enviar", key=f"btn_send_yt_gal_{c_idx}_{f_idx}", type="primary", use_container_width=True):
                                                with st.spinner("Enviando vídeo para o YouTube..."):
                                                    yt_res = upload_to_youtube_shorts(
                                                        video_path=v_file,
                                                        title=cut_item.get('title', 'Corte'),
                                                        description=cut_item.get('description', ''),
                                                        tags=cut_item.get('hashtags', []),
                                                        privacy_status=g_yt_priv,
                                                        client_secrets_path=_cfg.get("youtube_client_secrets_path")
                                                    )
                                                    if yt_res.get("success"):
                                                        st.success(f"🎉 Publicado! [Ver Shorts]({yt_res.get('url')})")
                                                    else:
                                                        st.error(f"Erro: {yt_res.get('error')}")
                                    with col_b_wh:
                                        if st.button("📡 Webhook", key=f"btn_wh_gal_{c_idx}_{f_idx}", use_container_width=True, help="Disparar para Webhook (n8n/Make)"):
                                            wh_url = _cfg.get("webhook_url", "")
                                            if not wh_url:
                                                st.warning("Configure o Webhook na barra lateral.")
                                            else:
                                                with st.spinner("Enviando..."):
                                                    wh_payload = {
                                                        "event": "cut_ready",
                                                        "video_id": _vid_id_gal,
                                                        "title": cut_item.get('title', 'Corte'),
                                                        "description": cut_item.get('description', ''),
                                                        "hashtags": cut_item.get('hashtags', []),
                                                        "tags_seo": cut_item.get('tags_seo', ''),
                                                        "start_time": cut_item.get('start_time'),
                                                        "end_time": cut_item.get('end_time'),
                                                        "aspect_mode": fmt_key,
                                                        "video_path": v_file,
                                                        "video_filename": fmt_data.get("video_filename"),
                                                        "folder_path": fmt_data.get("folder_path")
                                                    }
                                                    wh_res = send_to_webhook(wh_url, wh_payload, auth_header=_cfg.get("webhook_auth_header", ""))
                                                    if wh_res.get("success"):
                                                        st.success(f"✅ OK! HTTP {wh_res.get('status_code')}")
                                                    else:
                                                        st.error(f"Falha: {wh_res.get('error')}")
                                    with col_b_del:
                                        with st.popover("🗑️", use_container_width=True, help=f"Excluir este vídeo ({fmt_key})"):
                                            st.markdown(f"⚠️ **Excluir {fmt_badge}?**")
                                            del_fmt_choice = st.radio(
                                                "Opção de exclusão:",
                                                [
                                                    "🎬 Apenas este Vídeo (.mp4)\n*(Preserva textos e kit)*",
                                                    "💥 Pasta e Kit deste formato"
                                                ],
                                                key=f"rad_del_fmt_{c_idx}_{f_idx}"
                                            )
                                            if st.button("Confirmar", key=f"btn_cnf_fmt_del_{c_idx}_{f_idx}", type="primary", use_container_width=True):
                                                is_full = "Pasta e Kit" in del_fmt_choice
                                                delete_format_instance(_vid_id_gal, cut_item.get('start_time'), cut_item.get('end_time'), fmt_key, delete_publication_kit=is_full)
                                                st.success("Excluído com sucesso.")
                                                st.rerun()
                                    st.caption(f"📁 `{fmt_data.get('folder_name')}`")
                                else:
                                    st.warning("Vídeo excluído / não encontrado.")
                                    if st.button("🗑️ Remover do Catálogo", key=f"btn_clean_fmt_{c_idx}_{f_idx}"):
                                        delete_format_instance(_vid_id_gal, cut_item.get('start_time'), cut_item.get('end_time'), fmt_key, delete_publication_kit=True)
                                        st.rerun()

                    with st.expander("📝 Visualizar Textos e Tags de Publicação"):
                        st.markdown(f"**Legenda:**\n```\n{cut_item.get('description', '')}\n```")
                        st.markdown(f"**Hashtags:** `{' '.join(cut_item.get('hashtags', []))}`")
                        st.markdown(f"**Tags SEO:** `{cut_item.get('tags_seo', '')}`")

                    st.divider()



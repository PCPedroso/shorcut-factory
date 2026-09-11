---
name: viralcut-ui-gallery
description: >-
  Guia de interface Streamlit para o ViralCut: padrões de design, gerenciamento de estado e persistência (config_manager), galeria de cortes, prévias em tempo real e integração com Windows Explorer.
---

# ViralCut: Interface Streamlit & Catálogo de Cortes

Este guia define as boas práticas de desenvolvimento de interface no `app.py` e persistência em `core/config_manager.py`.

---

## 1. Persistência de Configurações (`core/config_manager.py`)

- **Arquivo de Configurações**: `data/app_settings.json`.
- **Regra de Sincronização**:
  - Todo input, slider, selectbox ou toggle crítico deve carregar seu valor padrão via `_cfg.get("chave", padrao)`.
  - Mudanças de valores devem ser salvas imediatamente usando callbacks `on_change=lambda: save_setting("chave", st.session_state.widget_key)`.
  - As preferências de enquadramento (Smart Face, Blur, Split Screen, Crop e 16:9) são memorizadas de forma independente, permitindo alternar livremente entre formatos sem perder customizações manuais.

---

## 2. Padrões de Layout e Componentes do Streamlit

1. **Abas sem Transbordamento (`st.tabs`)**:
   - Manter títulos de abas concisos (ex: `✂️ Aparar (Trim)`, `🗑️ Remover Trecho`, `🎨 Banner (Overlay)`) para evitar quebras ou paginação horizontal oculta em telas menores.
2. **Prévias em Tempo Real**:
   - Qualquer ajuste dimensional (enquadramento facial, blur, overlays, capas) deve fornecer botão ou slider de prévia visual imediata extraindo o frame via `cv2.VideoCapture` e exibindo no `st.image`.
3. **Integração com o Sistema Operacional (Windows Explorer)**:
   - Botão *"📂 Abrir Pasta"* disponível em todos os cards de cortes gerados.
   - Utiliza `os.startfile(os.path.normpath(folder_path))` ou `subprocess.Popen(f'explorer /select,"{video_path}"')` para abrir a pasta nativa no Windows.
   - Fornecer link markdown no formato `[Nome](file:///D:/Repository/shorcut-factory/...)` e texto monoespaçado do caminho absoluto.
4. **Design System & Glassmorphism (`core/ui_theme.py`)**:
   - Sempre chamar `inject_viralcut_theme()` no início do `app.py`.
   - Utilizar componentes utilitários: `render_status_badge()`, `render_empty_state_html()` e `render_section_header()`.
   - Manter paleta Dark Studio (`#090d16`, Indigo `#6366f1`, Pink Neon `#ec4899`) e fontes *Plus Jakarta Sans* / *JetBrains Mono*.
5. **Navegação Progressiva (Workflow Stepper)**:
   - Topo da aplicação organizado por `render_workflow_stepper()` para eliminar fadiga de scroll.
   - Utilizar `navigate_to_step("X")` ao encaminhar fluxos entre etapas automaticamente.
6. **Acesso Imediato ao Vídeo na Ingestão (Seção 1)**:
   - Logo após o processamento inicial ou transcrição, disponibilizar card/expander de visualização do vídeo completo (`video_full.mp4`) com streaming nativo (`safe_display_video`), metadados (resolução, duração, tamanho) e botões diretos de download e abertura no Explorer, eliminando a necessidade de avançar para a Seção 3 apenas para conferir o material de origem.
7. **Sincronização Atômica Player-to-Section3**:
   - **Zero-Freeze Seek**: Nunca escutar `timeupdate` disparando eventos para React/Streamlit durante o playback ou arraste com mouse; o arraste deve ser 100% nativo.
   - **Captura Precisa de Timestamp**: Escutar apenas `pause` e `seeked` para atualizar badge DOM leve (`#viralcut-player-time-badge`), e nos cliques de botão de setar tempo (`Setar Tempo Inicial` / `Setar Tempo Final`), injetar via URL query params (`sync_s1_start`/`sync_s1_end`) e limpar `_valueTracker` no React 18.
   - **Manutenção de Posição (`start_time`)**: Passar `start_time` em `safe_display_video` com base no timestamp selecionado para evitar que o player resete para o início (`00:00`) após cliques e reruns.



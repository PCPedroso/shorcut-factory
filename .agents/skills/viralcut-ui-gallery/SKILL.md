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

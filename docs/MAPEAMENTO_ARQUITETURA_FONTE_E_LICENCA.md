# Mapeamento de Arquitetura: Recurso "Fonte e Licença" — ViralCut

> **Contexto:** Documento de diagnóstico e mapeamento arquitetural para orientar a implementação do recurso de **Fonte e Licença** (campos de origem, campanha, link de briefing e status de autorização, persistência de metadados e bloqueio de publicação para status "Não verificado").

---

## 1. Stack e Estrutura

### a) Linguagens, Framework e Inicialização
- **Linguagem Principal:** Python 3.12 (interpretador local no virtual environment `.\venv312\`).
- **Framework de Interface:** Streamlit (Web App reativa executada localmente).
- **Como a aplicação é iniciada:**
  ```powershell
  streamlit run app.py
  # Ou apontando diretamente para o executável do ambiente virtual:
  .\venv312\Scripts\streamlit.exe run app.py
  ```

### b) Árvore de Pastas (até 2 níveis essenciais)
```text
shorcut-factory/
├── app.py                     # Ponto de entrada, orquestração de UI e workflow
├── requirements.txt           # Especificação das dependências Python
├── Fábrica de Cortes.md       # Documentação mestre de arquitetura e convenções
├── assets/                    # Recursos e mídias estáticas
│   ├── audio/                 # Trilhas de fundo e catálogo custom_tracks.json
│   ├── fonts/                 # Tipografias para headlines e legendas (.ttf)
│   └── templates/             # Assets visuais e vinhetas
├── core/                      # Módulos de lógica de negócio e processamento
│   ├── analyzer.py            # Mineração de pautas via IA (Ollama / Llama 3)
│   ├── cuts_catalog.py        # Catálogo unificado, minutagens e metadados de cortes
│   ├── export_kit.py          # Geração do kit de publicação (vídeo, legendas, textos)
│   ├── library_manager.py     # Gerenciamento de biblioteca e histórico de vídeos
│   ├── publishing/            # Motor de publicação multiplataforma (YouTube, X, etc.)
│   ├── video_processor.py     # Ingestão (yt-dlp), cortes cirúrgicos e pipeline FFmpeg
│   └── ...
├── data/                      # Dados de execução e persistência local
│   ├── app_settings.json      # Configurações globais persistentes da aplicação
│   ├── library.json           # Registro de vídeos ingeridos na biblioteca
│   ├── publish_queue.db       # Banco de dados SQLite da fila assíncrona de postagens
│   └── [video_id]/            # Pasta isolada de cada vídeo de origem
├── docs/                      # Guias técnicos e relatórios de arquitetura
└── tests/                     # Bateria de testes automatizados com pytest
```

### c) Onde ficam as dependências
- Arquivo central: [`requirements.txt`](../requirements.txt) na raiz do repositório.

### d) Testes Automatizados e Execução
- **Localização:** Pasta [`tests/`](../tests/) contendo mais de 30 suítes de teste (mais de 400 testes unitários).
- **Como rodar:**
  ```powershell
  pytest tests/
  # Ou com saída detalhada:
  .\venv312\Scripts\python.exe -m pytest tests/ -v
  ```

### e) Documento de Convenções
- **Documento:** [`Fábrica de Cortes.md`](../F%C3%A1brica%20de%20Cortes.md) na raiz.
- **Resumo:** Define os pilares das 5 fases da esteira. Estabelece a regra mandatória de **Ingestão Leve em Poucos Segundos** (o download do vídeo original extrai apenas `video_full.mp4` e metadados rápidos, proibindo a extração de áudio ou transcrição Whisper pesada antes do corte), processamento cirúrgico sob demanda apenas sobre intervalos cortados, desacoplamento em módulos em `core/`, e persistência resiliente em JSON com retrocompatibilidade garantida.

---

## 2. Fluxo de Criação do Projeto e do Corte

### a) Cadastro do Vídeo de Origem
- **Arquivos/Funções:**
  - [`core/library_manager.py`](../core/library_manager.py): Função `add_or_update_video_in_library()`.
  - [`core/video_processor.py`](../core/video_processor.py): Função `download_full_video()`.
  - [`app.py`](../app.py): Bloco `render_step_1_ingestion()`.
- **Código:**
  ```python
  # core/library_manager.py
  def add_or_update_video_in_library(video_id: str, title: str, channel: str = "",
                                     duration_sec: float = 0, thumbnail: str = "",
                                     url: str = "", is_live: bool = False,
                                     raw_upload_date: str = "") -> dict:
      meta_path = get_video_metadata_path(video_id)
      with open(meta_path, "w", encoding="utf-8") as f:
          json.dump(entry, f, indent=4, ensure_ascii=False)
      return entry
  ```

### b) Criação e Processamento de Cada Corte
- **Corte de Vídeo:** [`core/video_processor.py`](../core/video_processor.py) na função `cut_video()`.
- **Empacotamento do Kit:** [`core/export_kit.py`](../core/export_kit.py) na função `create_viral_package()`.
- **Registro no Catálogo:** [`core/cuts_catalog.py`](../core/cuts_catalog.py) na função `register_cut_instance()`.
- **Código:**
  ```python
  # core/cuts_catalog.py
  def register_cut_instance(
      video_id: str, start_time: str, end_time: str, aspect_mode: str,
      cut_folder_path: str, cut_video_path: str, title: str = "",
      description: str = "", hashtags: list = None, tags_seo: str = "",
      thumbnail_path: str = None, subtitle_path: str = None, ...
  ) -> dict:
      catalog = load_cuts_catalog(video_id)
      # Grava metadados do corte indexados pela minutagem no cuts_catalog.json
      save_cuts_catalog(video_id, catalog)
  ```

### c) Conceito de "Projeto / Vídeo de Origem" vs "Corte"
A aplicação possui separação hierárquica completa em disco:
- **Nível do Vídeo de Origem:** Pasta `data/<video_id>/` contendo:
  - `video_full.mp4` (mídia integral bruta)
  - `metadata.json` (metadados do vídeo baixado/importado)
  - `cuts_catalog.json` (catálogo geral de todos os cortes gerados para o vídeo)
  - `transcript.json` (transcrição do vídeo completo, caso solicitada)
- **Nível do Corte Individual:** Subpasta dentro do vídeo `data/<video_id>/<PREFIXO_FORMATO>_<SLUG_TITULO>_<MINUTAGEM>/` (ex.: `data/40vTnhMIrAE/VFDBS_Corte_C2_07m37s_09m50s/`) contendo:
  - `[nome_do_corte].mp4` (vídeo renderizado final)
  - `[nome_do_corte].mp3` (áudio extraído do corte)
  - `legendas.srt` / `[nome_do_corte].srt` (legendas sincronizadas)
  - `info_publicacao.txt` (guia com título, descrição, hashtags e minutagem)
  - `descricao.txt` (texto de legenda pronto para colar)
  - `tags.txt` (hashtags e palavras-chave de SEO)
  - `transcricao_corte.json` (dados de transcrição e alinhamento do trecho)
  - `historico_edicoes.json` (histórico de modificações rápidas)

### d) Os 4 Métodos de Criação de Cortes
1. **JSON Externo de Curadoria:** [`core/cuts_catalog.py`](../core/cuts_catalog.py) (`parse_json_cuts()`, `register_cuts_from_parsed()`) e [`app.py`](../app.py) (Aba 1 e Aba 3).
2. **Mineração por IA (Ollama / Llama 3):** [`core/analyzer.py`](../core/analyzer.py) (`analyze_transcript()`, `generate_viral_cut_metadata()`) e [`app.py`](../app.py) (Aba 2).
3. **Carrossel Inteligente:** [`core/video_processor.py`](../core/video_processor.py) (`split_video_smart()`) e [`core/cuts_catalog.py`](../core/cuts_catalog.py) (`sync_carrossel_parts_to_catalog()`), acionado na Aba 1 de [`app.py`](../app.py).
4. **Manual / Cirúrgico:** [`core/video_processor.py`](../core/video_processor.py) (`cut_video()`), acionado diretamente pelos inputs de tempo na Aba 1 e Aba 3 de [`app.py`](../app.py).

---

## 3. Metadados

### a) Onde e quando o metadados.json é gerado e gravado
- **Arquivo `metadados.json` isolado por corte:** **NÃO ENCONTRADO**.
- *Estrutura Real:* Os metadados de cada corte não são gravados em um arquivo `metadados.json` individual dentro de sua pasta, mas sim de forma centralizada em **`data/<video_id>/cuts_catalog.json`** pela função `save_cuts_catalog()` em [`core/cuts_catalog.py`](../core/cuts_catalog.py). Os metadados em texto legível para publicação (`info_publicacao.txt`, `descricao.txt`, `tags.txt`) são gerados pela função `create_viral_package()` em [`core/export_kit.py`](../core/export_kit.py).

### b) Exemplo REAL de Metadados de um Corte
*(Registro real extraído do catálogo `data/40vTnhMIrAE/cuts_catalog.json`)*:
```json
{
  "start_time": "00:07:37.05",
  "end_time": "00:09:50.88",
  "title": "Corte C2",
  "description": "O Copom pausou a Selic. O apresentador diz que não se deve derrubar a taxa na marra, mas que está alta demais. Cita o relato de um profissional sobre juros de empresas apertadas e fala do endividamento.",
  "hashtags": [],
  "tags_seo": "cortes, viral, shorts",
  "created_at": "09/11/2026 11:19",
  "updated_at": "09/11/2026 11:22",
  "formats": {
    "9:16_blur": {
      "cut_code": "iXY7OuFt26B",
      "aspect_mode": "9:16_blur",
      "folder_name": "VFDBS_Corte_C2_07m37s_09m50s",
      "folder_path": "data\\40vTnhMIrAE\\VFDBS_Corte_C2_07m37s_09m50s",
      "video_path": "data\\40vTnhMIrAE\\VFDBS_Corte_C2_07m37s_09m50s\\VFDBS_Corte_C2_07m37s_09m50s.mp4",
      "video_filename": "VFDBS_Corte_C2_07m37s_09m50s.mp4",
      "thumbnail_path": null,
      "thumbnail_filename": null,
      "thumbnail_variations": [],
      "active_variation": 1,
      "subtitle_path": "data\\40vTnhMIrAE\\VFDBS_Corte_C2_07m37s_09m50s\\VFDBS_Corte_C2_07m37s_09m50s.srt",
      "subtitle_filename": "VFDBS_Corte_C2_07m37s_09m50s.srt",
      "resolution": "1080x1920",
      "rendered_at": "09/11/2026 11:22"
    }
  },
  "headline": "Peça a taxa Selic no seu banco: o juro que a empresa paga é bem maior.",
  "observacoes": [
    {
      "tipo": "dados",
      "texto": "Conferir número e indicador antes de publicar."
    }
  ],
  "potencial_viralizacao": {
    "nota": 8,
    "justificativa": "Impacto no bolso, explicação simples e fechamento forte."
  },
  "risco_contexto": "medio",
  "depende_visual": false,
  "json_cut_id": "C2",
  "ranking_posicao": 1,
  "ranking_ponderacao": "Melhor equilíbrio entre gancho forte e segurança."
}
```

### c) Arquivo de Metadados no Nível do Vídeo de Origem
- **Arquivo:** `data/<video_id>/metadata.json`.
- **Exemplo REAL e completo** *(extraído de `data/40vTnhMIrAE/metadata.json`)*:
```json
{
    "video_id": "40vTnhMIrAE",
    "video_code": "UsUahfFcOF2",
    "title": "O alerta vermelho para as gigantes da tecnologia",
    "upload_date": "08/11/2026",
    "raw_upload_date": "20261108",
    "url": "https://youtu.be/40vTnhMIrAE?si=sM__E4wt3dpYp2mM",
    "thumbnail": "https://i.ytimg.com/vi/40vTnhMIrAE/maxresdefault.jpg",
    "duration_sec": 2759.6666666666665,
    "channel": "Economista Sincero",
    "is_live": false,
    "added_at": "08/11/2026 23:21"
}
```

### d) Versão/Schema e Leitura de Arquivos Antigos
- **Schema ou Versão:** **NÃO ENCONTRADO** (não existe campo `_version` ou validador formal Pydantic).
- **Tratamento de Retrocompatibilidade:** Toda a leitura é implementada de forma defensiva via métodos `.get("chave", default)` em Python (por exemplo: `c_data.get("headline", "")`, `c_data.get("description", "")`). Se um campo novo for adicionado, arquivos legados continuam funcionando sem exceções de `KeyError`.

### e) Outros Arquivos que Leem Metadados
1. [`app.py`](../app.py): Exibição dos cards, rankings, badges e preenchimento de formulários nas Abas 1, 2, 3 e 4.
2. [`core/cuts_catalog.py`](../core/cuts_catalog.py): Operações de carga, consulta e atualização de textos.
3. [`core/library_manager.py`](../core/library_manager.py): Gestão da biblioteca de vídeos e histórico lateral.
4. [`core/publishing/ui_tab.py`](../core/publishing/ui_tab.py): Leitura de cortes disponíveis para postagem.
5. [`core/publishing/worker.py`](../core/publishing/worker.py): Adaptação de títulos e legendas no momento do disparo.
6. [`core/integrations.py`](../core/integrations.py): Montagem de payloads HTTP para webhooks externos.
7. [`core/quick_editor.py`](../core/quick_editor.py): Edição rápida e atualização pontual sem re-render.

---

## 4. Interface

### a) Telas e Abas da Aplicação
- **Arquivo:** [`app.py`](../app.py).
- **Abas Disponíveis no Topo:**
  1. `1. Ingestão & Processamento` (Download/carregamento, divisão de carrossel, importador JSON e biblioteca).
  2. `2. Mineração & Pautas IA` (Transcrição Whisper e geração de pautas pelo Ollama).
  3. `3. Fábrica de Enquadramento 9:16` (Enquadramento inteligente/manual, legendas dinâmicas, headline e renderização).
  4. `4. Galeria de Cortes & Pós` (Reprodutor, edição rápida de metadados, downloads e atalho para abrir pasta local).
  5. `5. Central de Publicação Multiplataforma` (Fila assíncrona, status de publicação e conexões de redes).

### b) Onde o Usuário Informa a Origem e Edita os Cortes
- **Origem do Vídeo:** Na **Aba 1**, bloco `📥 Entrada de Mídia` em [`app.py`](../app.py) (campo de texto para URL web ou seletor de arquivo local).
- **Edição dos Dados do Corte:**
  - Na **Aba 3**, durante a pré-produção do corte (título, headline, hashtags).
  - Na **Aba 4**, no bloco expansível `✏️ Editar Metadados` presente no card de cada corte.

### c) Estrutura da Galeria (Aba 4)
- **Onde é montada:** Em [`app.py`](../app.py) na função `render_step_4_gallery()`.
- **Botões e Ações Disponíveis:**
  - `st.download_button`: Download direto do vídeo MP4 gerado no navegador.
  - `st.download_button`: Download do arquivo de legenda `.srt`.
  - Botão `📁 Abrir Pasta`: Invoca `open_in_file_explorer()` executando `os.startfile` no Windows ou link `file:///`.
  - Botão `✏️ Editar Metadados`: Edita textos e persiste no catálogo e nos arquivos `.txt`.
  - Botão `📡 Disparar Webhook`: Envia payload com vídeo e metadados para webhook.
  - Botão `🗑️ Excluir Corte`: Remove os arquivos em disco e o registro no catálogo.

### d) Exibição de Avisos e Mensagens
- **Mecanismos:** Notificações nativas do Streamlit (`st.toast`, `st.success`, `st.warning`, `st.error`, `st.info`) e cards formatados com CSS/HTML seguro.
- **Exemplo de Código:**
  ```python
  # app.py
  st.toast("✅ Metadados atualizados com sucesso!", icon="💾")
  st.warning("⚠️ Atenção: este corte possui observações de risco moderado de contexto.")
  ```

---

## 5. Publicação e Envio

### a) Módulos e Funções de Publicação
- **YouTube Shorts:** [`core/publishing/youtube.py`](../core/publishing/youtube.py) (`YouTubePublisher.publish()`) e [`core/integrations.py`](../core/integrations.py) (`upload_to_youtube_shorts()`).
- **X (Twitter):** [`core/publishing/x_publisher.py`](../core/publishing/x_publisher.py) (`XPublisher.publish()`).
- **Instagram / TikTok / Kwai:** [`core/publishing/instagram.py`](../core/publishing/instagram.py), [`core/publishing/tiktok.py`](../core/publishing/tiktok.py), [`core/publishing/kwai.py`](../core/publishing/kwai.py) (`publish()`).
- **Webhooks:** [`core/integrations.py`](../core/integrations.py) (`send_to_webhook()`).
- **Fila & Worker:** [`core/publishing/publish_queue.py`](../core/publishing/publish_queue.py) (`PublishQueue.enqueue()`) e [`core/publishing/worker.py`](../core/publishing/worker.py) (`PublishWorker._process_single_job()`).

### b) Validações Antes da Publicação
- **Módulo:** [`core/publishing/media_preflight.py`](../core/publishing/media_preflight.py) na classe `MediaPreflight` e método `validate_for_platform()`.
- **Validações Realizadas:**
  1. Verificação de existência física do arquivo de vídeo.
  2. Duração máxima permitida para a rede de destino.
  3. Aspect ratio / proporção vertical (ex.: 9:16).
  4. Tamanho máximo em megabytes suportado pelas APIs.
  5. Posição do átomo `moov` (`faststart` para reprodução imediata na web).
  6. Validade de credenciais ou tokens OAuth conectados via `get_auth_status()`.

### c) Outros Pontos de Entrega do Vídeo
1. **Download pelo navegador:** `st.download_button` de arquivos MP4 e SRT na Aba 3 e Aba 4.
2. **Explorador de Arquivos:** Botões `Abrir Pasta` e links `file:///` abrindo a pasta no Windows Explorer.
3. **Área de Transferência do Windows:** Métodos `_copy_to_windows_clipboard()` e `_reveal_in_windows_explorer()` em [`core/publishing/x_publisher.py`](../core/publishing/x_publisher.py) e [`core/publishing/kwai.py`](../core/publishing/kwai.py) (fluxo semi-automático).
4. **Envio por Webhook:** Botão `Disparar Webhook` na Galeria enviando o pacote completo para serviços de automação (Make, n8n, Zapier).
5. **Streaming HTTP Local:** Servidor em [`core/media_streamer.py`](../core/media_streamer.py) (`http://127.0.0.1:<port>/stream?file=...`) para reprodução instantânea no navegador.

---

## 6. Dados Existentes e Ambiente

### a) Contagem Atual em `data/`
- **Vídeos de origem identificados:** **15** pastas de projetos de vídeo (com `metadata.json` ou `cuts_catalog.json`).
- **Pastas de cortes identificadas:** **19** pastas de cortes individuais renderizados.

### b) Sistema Operacional e Caminhos no Código
- **Sistema Operacional:** Projetado primordialmente para **Windows** (utiliza `os.startfile`, `explorer.exe`, fontes do sistema em `C:\Windows\Fonts\` e criptografia de credenciais via Windows DPAPI).
- **Caminhos Fixos Hardcoded:** **NÃO ENCONTRADO** caminho absoluto fixo (ex.: `d:/Repository/...`) na lógica de negócio. Todas as operações utilizam caminhos relativos ou construídos a partir de `data/` via `os.path.join()`.

### c) Configurações do Usuário e Segredos
- **Configurações Gerais:** [`data/app_settings.json`](../data/app_settings.json), gerenciado por [`core/config_manager.py`](../core/config_manager.py) (`load_settings()`, `save_setting()`).
- **Segredos e Tokens:** Armazenados de forma criptografada em `data/credential_vault.json` através do módulo [`core/publishing/credentials.py`](../core/publishing/credentials.py) usando Windows DPAPI (`CryptProtectData`), e `data/client_secrets.json` para OAuth do Google. Não há arquivo `.env` obrigatório.

---

## 7. Riscos Percebidos

1. **Inexistência de `metadados.json` individual nos cortes:** A aplicação concentra todos os metadados dos cortes em `data/<video_id>/cuts_catalog.json`. Se for criado um `metadados.json` avulso dentro de cada pasta de corte, haverá duplicidade de fontes da verdade, exigindo sincronização contínua.
2. **Múltiplos canais de publicação e entrega:** O bloqueio para status "Não verificado" deve interceptar o worker da fila (`core/publishing/worker.py`), o enfileiramento na UI (`core/publishing/ui_tab.py`), o envio de webhooks (`core/integrations.py`) e, se desejado, avisar ou bloquear downloads na Galeria (`app.py`).
3. **Retrocompatibilidade dos 19 cortes existentes:** Nenhum corte legado possui os campos `status_autorizacao`, `origem`, `campanha` ou `link_briefing`. Um valor padrão seguro (ex.: `"Nao Verificado"` ou `"Pendente"`) bloqueará imediatamente a publicação de todo o acervo histórico se não houver opção de regularização em lote ou fallback configurável.
4. **Hierarquia de formatos por corte:** No `cuts_catalog.json`, cada minutagem agrupa múltiplos formatos renderizados (ex.: `9:16_blur`, `1:1_box`). O status de licença deve ser posicionado no nível do corte (raiz da minutagem), evitando inconsistências entre variações de enquadramento do mesmo trecho.
5. **Herança entre vídeo de origem e cortes:** Um vídeo de origem pode ter status de autorização aprovado, mas cortes específicos podem conter músicas comerciais ou declarações sensíveis com status reprovado. A relação de herança (origem $\rightarrow$ corte) deve permitir sobreposição individual.
6. **Múltiplos fluxos de criação de cortes:** Os 4 métodos existentes (JSON de curadoria, IA Ollama, Carrossel Inteligente e Manual) instanciam cortes em pontos distintos de [`app.py`](../app.py). Todos os 4 métodos deverão receber os novos campos para não gerar entradas com metadados incompletos.
7. **Disparo assíncrono via `PublishQueue`:** A fila de postagens persiste jobs em SQLite (`publish_queue.db`). A checagem de autorização precisa ocorrer antes do enfileiramento (`PublishQueue.enqueue()`) e ser revalidada no worker (`_process_single_job()`) para prevenir disparos de jobs previamente aprovados que foram revogados.
8. **Edição rápida na Galeria sem atualização de licença:** A função `update_cut_texts_only()` em [`core/cuts_catalog.py`](../core/cuts_catalog.py) atualiza apenas título, descrição e tags. Ela precisará ser estendida para suportar os novos campos de licença quando editados na Aba 4.


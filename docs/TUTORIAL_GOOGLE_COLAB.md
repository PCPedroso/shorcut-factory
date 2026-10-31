# ☁️ Guia Oficial: Executando a Fábrica de Cortes (ViralCut) no Google Colab

Este tutorial documenta passo a passo a configuração, instalação e execução da **Fábrica de Cortes (ViralCut)** no **Google Colab** (com GPU NVIDIA T4/L4 gratuita ou Colab Pro), na ordem exata testada e homologada.

---

## 📋 Pré-Requisito: Ativar a GPU no Notebook
Antes de executar a primeira célula:
1. No menu superior do Google Colab, clique em **Ambiente de execução (Runtime)** $\to$ **Alterar o tipo de ambiente de execução (Change runtime type)**.
2. Em **Acelerador de hardware (Hardware accelerator)**, selecione **T4 GPU** (ou L4/A100).
3. Clique em **Salvar**.

---

## 🚀 Passo 1 — Montar o Google Drive
Permite salvar ou sincronizar dados persistentes no seu Google Drive caso deseje preservar os vídeos e cortes gerados entre sessões.

```python
from google.colab import drive
drive.mount('/content/drive')
```
> **Resultado esperado:** `Mounted at /content/drive`

---

## 🎬 Passo 2 — Instalar o FFmpeg no Sistema Linux
Garante que os binários nativos `/usr/bin/ffmpeg` e `/usr/bin/ffprobe` estejam instalados e atualizados para mesclagem de streams 1080p (`yt-dlp`) e renderização acelerada.

```bash
!apt-get update && apt-get install -y ffmpeg
```

---

## 📦 Passo 3 — Clonar o Repositório Oficial e Entrar na Pasta
Baixa o código-fonte mais recente da aplicação diretamente do GitHub para `/content/shorcut-factory`.

```python
!git clone https://github.com/PCPedroso/shorcut-factory.git
%cd shorcut-factory
```

> **💡 Dica (Se a pasta já existir e você quiser apenas atualizar o código sem apagar seus cortes):**
> ```python
> %cd /content/shorcut-factory
> !git pull
> ```

---

## 🐍 Passo 4 — Instalar as Dependências Python (`requirements.txt`)
Instala todas as bibliotecas da aplicação (Streamlit, Faster-Whisper, MoviePy, OpenCV, MediaPipe, Canvas, APIs de publicação) e garante a versão mais recente do `yt-dlp`.

```bash
%cd /content/shorcut-factory
!pip install -r requirements.txt
!pip install -U yt-dlp
```

---

## 🤖 Passo 5 (Opcional) — Instalar e Iniciar o Ollama + Llama 3 (Para Mineração por IA na Seção 2)
Caso você utilize a **Seção 2 (Mineração Automática de Cortes Virais com Llama 3)** dentro do Colab, rode esta célula uma vez para subir o servidor local do Ollama na própria máquina virtual do Colab:

```bash
!sudo apt-get install -y zstd pciutils lshw
!curl -fsSL https://ollama.com/install.sh | sh
!nohup ollama serve > /content/ollama.log 2>&1 &
!sleep 5
!ollama pull llama3
```

---

## 🌐 Passo 6 — Iniciar o Streamlit e Abrir o Túnel de Acesso (Cloudflare Tunnel)
Inicia o servidor Streamlit em segundo plano na porta `8501` e cria um túnel HTTPS de alta velocidade via **Cloudflare Tunnel (`cloudflared`)** — sem pedir senha de IP e sem o erro `HTTP 429 Too Many Requests` que ocorre no LocalTunnel (`loca.lt`).

```bash
%cd /content/shorcut-factory
!wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O /usr/local/bin/cloudflared
!chmod +x /usr/local/bin/cloudflared
!pkill -f streamlit || true
!nohup streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.enableCORS false --server.enableXsrfProtection false > /content/logs.txt 2>&1 &
!sleep 3
!cloudflared tunnel --url http://localhost:8501
```

### 🔗 Como acessar a interface:
Após 3 a 5 segundos, aparecerá no log da célula uma caixa como esta:
```text
+--------------------------------------------------------------------------------------------+
|  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
|  https://xxxx-xxxx-xxxx-xxxx.trycloudflare.com                                             |
+--------------------------------------------------------------------------------------------+
```
Basta clicar no link **`https://...trycloudflare.com`** para abrir a **Fábrica de Cortes** completa no seu navegador!

---

## 🛠️ Comandos Úteis de Manutenção no Colab

### 1. Ver logs da aplicação em tempo real (caso queira depurar algo)
Pare a célula do túnel e execute:
```bash
!tail -n 80 /content/logs.txt
```

### 2. Atualizar a aplicação após um novo `git push`
```bash
%cd /content/shorcut-factory
!git pull
```
*(O Streamlit recarrega automaticamente o `app.py` assim que o `git pull` termina, ou basta clicar em **Rerun** no navegador).*

### 3. Fazer backup da pasta `data/` (Vídeos, Cortes e Catálogo) para o seu Google Drive
```bash
!mkdir -p "/content/drive/MyDrive/ViralCut_Backup"
!cp -r /content/shorcut-factory/data/* "/content/drive/MyDrive/ViralCut_Backup/"
```

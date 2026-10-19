"""
media_streamer.py — Servidor HTTP local leve com suporte a Range Requests (HTTP 206 Partial Content).
Permite reprodução e busca (seeking) instantânea de vídeos grandes (>100MB ou >4GB) no Streamlit
sem carregar os arquivos inteiros na memória RAM e evitando estouro de buffer (WSASend ValueError: buffer too large) no Windows asyncio.
"""

import os
import re
import atexit
import threading
import mimetypes
from urllib.parse import urlparse, parse_qs, quote, unquote
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

_SERVER_LOCK = threading.Lock()
_STREAM_SERVER = None
_SERVER_PORT = None

# Tamanho padrão do chunk de envio (64 KB): leve na RAM e seguro para buffers de socket no Windows
CHUNK_SIZE = 64 * 1024

# Limiar de tamanho para considerar um arquivo grande (100 MB)
LARGE_MEDIA_THRESHOLD_BYTES = 100 * 1024 * 1024


class RangeMediaHandler(BaseHTTPRequestHandler):
    """
    Handler HTTP com suporte a Range Requests (RFC 7233).
    Transmite pedaços do arquivo sob demanda conforme o player do navegador solicita.
    """

    def do_HEAD(self):
        self._handle_media(head_only=True)

    def do_GET(self):
        self._handle_media(head_only=False)

    def _handle_media(self, head_only: bool = False):
        parsed = urlparse(self.path)
        if parsed.path != "/stream":
            self.send_error(404, "Not Found")
            return

        query = parse_qs(parsed.query)
        encoded_file = query.get("file", [""])[0]
        if not encoded_file:
            self.send_error(400, "Missing file parameter")
            return

        file_path = os.path.normpath(unquote(encoded_file))
        if not os.path.isfile(file_path):
            self.send_error(404, "File Not Found")
            return

        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            self.send_error(500, "Cannot access file")
            return

        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in [".mp4", ".m4v"]:
                mime_type = "video/mp4"
            elif ext in [".webm"]:
                mime_type = "video/webm"
            elif ext in [".mp3"]:
                mime_type = "audio/mpeg"
            elif ext in [".wav"]:
                mime_type = "audio/wav"
            else:
                mime_type = "application/octet-stream"

        range_header = self.headers.get("Range")
        start = 0
        end = file_size - 1
        status_code = 200

        if range_header:
            match = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if match:
                start = int(match.group(1))
                if match.group(2):
                    end = int(match.group(2))
                end = min(end, file_size - 1)
                if start <= end and start < file_size:
                    status_code = 206
                else:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{file_size}")
                    self.end_headers()
                    return

        content_length = end - start + 1

        try:
            self.send_response(status_code)
            self.send_header("Content-Type", mime_type)
            self.send_header("Accept-Ranges", "bytes")
            if status_code == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.send_header("Content-Length", str(content_length))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Range, Content-Type")
            self.end_headers()

            if head_only:
                return

            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    read_n = min(CHUNK_SIZE, remaining)
                    chunk = f.read(read_n)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            # Normal em streaming quando o usuário pausa, avança a timeline ou fecha a aba
            pass
        except Exception:
            pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range, Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        # Suprime logs de requisições de chunks para não poluir o terminal
        pass


def start_media_streamer_if_needed() -> int:
    """
    Inicializa o servidor de streaming em thread daemon local na porta disponível.
    Retorna o número da porta ativa.
    """
    global _STREAM_SERVER, _SERVER_PORT
    with _SERVER_LOCK:
        if _STREAM_SERVER is not None and _SERVER_PORT is not None:
            return _SERVER_PORT

        server = ThreadingHTTPServer(("127.0.0.1", 0), RangeMediaHandler)
        _SERVER_PORT = server.server_port
        _STREAM_SERVER = server

        stream_thread = threading.Thread(
            target=_STREAM_SERVER.serve_forever,
            daemon=True,
            name="ViralCut-MediaStreamer"
        )
        stream_thread.start()

        def _cleanup():
            global _STREAM_SERVER
            if _STREAM_SERVER:
                try:
                    _STREAM_SERVER.shutdown()
                except Exception:
                    pass

        atexit.register(_cleanup)
        return _SERVER_PORT


def get_media_stream_url(file_path: str) -> str:
    """
    Gera uma URL HTTP local com suporte a Range Requests para o arquivo informado.
    Exemplo: http://127.0.0.1:54321/stream?file=D%3A%2F...
    """
    port = start_media_streamer_if_needed()
    norm_abs = os.path.abspath(file_path)
    encoded = quote(norm_abs)
    return f"http://127.0.0.1:{port}/stream?file={encoded}"


def is_large_media(file_path: str, threshold: int = LARGE_MEDIA_THRESHOLD_BYTES) -> bool:
    """
    Verifica se o arquivo excede o limite recomendado para carregamento direto em RAM no Streamlit.
    """
    if not file_path or not os.path.exists(file_path):
        return False
    try:
        return os.path.getsize(file_path) >= threshold
    except OSError:
        return False

"""
integrations.py — Exportação Direta & Integrações (YouTube Shorts API & Webhooks)
Permite upload de rascunhos para o YouTube Shorts e envio de metadados/arquivos para Webhooks (n8n, Make, Zapier).
"""

import os
import json
import requests
import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
YOUTUBE_TOKEN_PATH = os.path.join(DATA_DIR, "youtube_token.json")

# Escopo necessário para upload de vídeos no YouTube
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]


# ==========================================================
# 1. YOUTUBE SHORTS UPLOADER
# ==========================================================

def get_youtube_auth_status(client_secrets_path: str = None) -> dict:
    """Verifica se há credenciais válidas salvas para a API do YouTube."""
    if os.path.exists(YOUTUBE_TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(YOUTUBE_TOKEN_PATH, YOUTUBE_SCOPES)
            if creds and creds.valid:
                return {"authenticated": True, "message": "Autenticado e pronto para upload."}
            elif creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    with open(YOUTUBE_TOKEN_PATH, "w") as token_file:
                        token_file.write(creds.to_json())
                    return {"authenticated": True, "message": "Token renovado com sucesso."}
                except Exception as e:
                    return {"authenticated": False, "message": f"Token expirado: {e}"}
        except Exception as e:
            return {"authenticated": False, "message": f"Erro ao ler token: {e}"}
            
    if client_secrets_path and os.path.exists(client_secrets_path):
        return {"authenticated": False, "message": "Client Secrets configurado. Clique em 'Conectar Conta Google'."}
    
    return {"authenticated": False, "message": "Nenhum arquivo client_secrets.json configurado."}


def authenticate_youtube_oauth(client_secrets_path: str, port: int = 8080) -> dict:
    """
    Inicia o fluxo OAuth local no navegador para autorizar acesso ao YouTube do usuário.
    Salva o token em data/youtube_token.json.
    """
    if not os.path.exists(client_secrets_path):
        return {"success": False, "error": f"Arquivo client_secrets.json não encontrado: {client_secrets_path}"}

    try:
        flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, YOUTUBE_SCOPES)
        creds = flow.run_local_server(port=port, prompt="consent")
        
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(YOUTUBE_TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())
            
        return {"success": True, "error": None}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def upload_to_youtube_shorts(
    video_path: str,
    title: str,
    description: str,
    tags: list = None,
    privacy_status: str = "unlisted",  # 'private', 'unlisted', 'public'
    client_secrets_path: str = None,
) -> dict:
    """
    Faz o upload do vídeo diretamente para o canal do YouTube como Shorts.
    Retorna o ID do vídeo e o link de acesso.
    """
    if not os.path.exists(video_path):
        return {"success": False, "error": f"Arquivo de vídeo não encontrado: {video_path}"}

    creds = None
    if os.path.exists(YOUTUBE_TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(YOUTUBE_TOKEN_PATH, YOUTUBE_SCOPES)
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(YOUTUBE_TOKEN_PATH, "w") as token_file:
                    token_file.write(creds.to_json())
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if client_secrets_path and os.path.exists(client_secrets_path):
            auth_res = authenticate_youtube_oauth(client_secrets_path)
            if not auth_res["success"]:
                return {"success": False, "error": f"Falha na autenticação: {auth_res['error']}"}
            creds = Credentials.from_authorized_user_file(YOUTUBE_TOKEN_PATH, YOUTUBE_SCOPES)
        else:
            return {"success": False, "error": "Credenciais do YouTube não configuradas."}

    try:
        youtube = build("youtube", "v3", credentials=creds)

        # Garante que tenha a hashtag #Shorts no título/descrição para o algoritmo indexar
        final_title = title.strip()
        if len(final_title) > 90:
            final_title = final_title[:87] + "..."
        if "#Shorts" not in final_title and len(final_title) <= 80:
            final_title += " #Shorts"

        final_desc = description.strip()
        if "#Shorts" not in final_desc:
            final_desc += "\n\n#Shorts #Viral"

        body = {
            "snippet": {
                "title": final_title,
                "description": final_desc,
                "tags": tags or ["Shorts", "ViralCut"],
                "categoryId": "22",  # People & Blogs
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            }
        }

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        
        response = request.execute()
        video_id = response.get("id")
        video_url = f"https://youtube.com/shorts/{video_id}"

        return {
            "success": True,
            "video_id": video_id,
            "url": video_url,
            "error": None
        }

    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ==========================================================
# 2. WEBHOOKS & AUTOMAÇÕES (N8N, MAKE, ZAPIER, CUSTOM)
# ==========================================================

def send_to_webhook(
    webhook_url: str,
    payload: dict,
    auth_header: str = "",
    timeout: int = 15,
) -> dict:
    """
    Envia o pacote completo de metadados e informações do corte para um Webhook HTTP.
    Ideal para fluxos no n8n, Make, Zapier ou bots de publicação automática.
    """
    if not webhook_url or not webhook_url.startswith("http"):
        return {"success": False, "error": "URL de Webhook inválida."}

    headers = {"Content-Type": "application/json"}
    if auth_header:
        headers["Authorization"] = auth_header.strip()

    try:
        # Enriquece payload com timestamp de envio
        full_payload = dict(payload)
        full_payload["dispatched_at"] = datetime.datetime.now().isoformat()
        full_payload["source"] = "ViralCut_v3"

        response = requests.post(webhook_url, json=full_payload, headers=headers, timeout=timeout)
        
        if 200 <= response.status_code < 300:
            return {
                "success": True,
                "status_code": response.status_code,
                "response_text": response.text[:500],
                "error": None
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": f"Webhook retornou status HTTP {response.status_code}: {response.text[:300]}"
            }

    except Exception as exc:
        return {"success": False, "error": str(exc)}

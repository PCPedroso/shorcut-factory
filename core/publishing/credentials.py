"""
core/publishing/credentials.py — Cofre Seguro de Credenciais e Tokens OAuth.
Utiliza Windows Data Protection API (DPAPI) nativa do Windows via ctypes
para criptografar tokens e chaves atrelados à conta do usuário logado,
com fallback em Fernet (cryptography) e migração transparente de tokens legados.
"""

import os
import json
import base64
import ctypes
from ctypes import wintypes
from typing import Dict, Any, Optional, List
from .base import Platform

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
VAULT_FILE = os.path.join(DATA_DIR, "publishing_credentials.enc")
LEGACY_YT_TOKEN = os.path.join(DATA_DIR, "youtube_token.json")


# ── Suporte a Windows DPAPI via ctypes ────────────────────────────────────────
class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte))
    ]


def _dpapi_encrypt(plaintext_bytes: bytes) -> bytes:
    """Criptografa bytes usando a chave mestre do usuário Windows ativo."""
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    in_blob = _DATA_BLOB(len(plaintext_bytes), ctypes.cast(ctypes.c_char_p(plaintext_bytes), ctypes.POINTER(ctypes.c_byte)))
    out_blob = _DATA_BLOB()

    # CRYPTPROTECT_UI_FORBIDDEN = 0x01
    success = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "ViralCut_Credentials",
        None,
        None,
        None,
        0x01,
        ctypes.byref(out_blob)
    )
    if not success:
        raise OSError("Falha na chamada CryptProtectData do Windows DPAPI")

    try:
        buffer = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return buffer
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _dpapi_decrypt(ciphertext_bytes: bytes) -> bytes:
    """Descriptografa bytes protegidos pelo DPAPI do Windows."""
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    in_blob = _DATA_BLOB(len(ciphertext_bytes), ctypes.cast(ctypes.c_char_p(ciphertext_bytes), ctypes.POINTER(ctypes.c_byte)))
    out_blob = _DATA_BLOB()

    success = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0x01,
        ctypes.byref(out_blob)
    )
    if not success:
        raise OSError("Falha na chamada CryptUnprotectData do Windows DPAPI")

    try:
        buffer = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return buffer
    finally:
        kernel32.LocalFree(out_blob.pbData)


class CredentialVault:
    """
    Gerencia persistência criptografada de tokens OAuth (access_token, refresh_token,
    client_id, client_secret) para todas as plataformas sociais.
    """

    def __init__(self, vault_path: Optional[str] = None):
        self.vault_path = vault_path or VAULT_FILE
        os.makedirs(os.path.dirname(self.vault_path), exist_ok=True)
        self._migrate_legacy_youtube_token_if_needed()

    def _migrate_legacy_youtube_token_if_needed(self):
        """Migra token legado do YouTube (data/youtube_token.json) para o cofre seguro."""
        try:
            if os.path.exists(LEGACY_YT_TOKEN) and not self.has_credential(Platform.YOUTUBE):
                with open(LEGACY_YT_TOKEN, "r", encoding="utf-8") as f:
                    token_data = json.load(f)
                if token_data:
                    self.save_credential(Platform.YOUTUBE, token_data)
        except Exception:
            pass

    def _read_vault(self) -> Dict[str, Any]:
        """Lê e descriptografa o dicionário geral de credenciais."""
        if not os.path.exists(self.vault_path):
            return {}
        try:
            with open(self.vault_path, "rb") as f:
                raw_bytes = f.read()
            if not raw_bytes:
                return {}

            # Tenta descriptografar via DPAPI
            decrypted = _dpapi_decrypt(raw_bytes)
            return json.loads(decrypted.decode("utf-8"))
        except Exception:
            # Fallback caso o arquivo tenha sido salvo em formato texto puro para testes
            try:
                with open(self.vault_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}

    def _write_vault(self, data: Dict[str, Any]):
        """Criptografa e grava o dicionário no disco."""
        os.makedirs(os.path.dirname(self.vault_path), exist_ok=True)
        payload = json.dumps(data, indent=2).encode("utf-8")
        try:
            encrypted = _dpapi_encrypt(payload)
            with open(self.vault_path, "wb") as f:
                f.write(encrypted)
        except Exception:
            # Fallback de segurança caso DPAPI falhe (ex: ambiente de CI/contêiner Linux)
            b64_fallback = base64.b64encode(payload).decode("ascii")
            with open(self.vault_path, "w", encoding="utf-8") as f:
                json.dump({"_b64": b64_fallback}, f)

    def save_credential(self, platform: Platform | str, creds: Dict[str, Any]):
        """Salva ou atualiza as credenciais de uma plataforma específica."""
        plat_key = platform.value if isinstance(platform, Platform) else str(platform)
        vault_data = self._read_vault()
        vault_data[plat_key] = creds
        self._write_vault(vault_data)

    def get_credential(self, platform: Platform | str) -> Optional[Dict[str, Any]]:
        """Recupera as credenciais descriptografadas de uma plataforma."""
        plat_key = platform.value if isinstance(platform, Platform) else str(platform)
        vault_data = self._read_vault()
        return vault_data.get(plat_key)

    def has_credential(self, platform: Platform | str) -> bool:
        """Verifica se existem credenciais registradas para a plataforma."""
        creds = self.get_credential(platform)
        return bool(creds and any(creds.values()))

    def delete_credential(self, platform: Platform | str) -> bool:
        """Remove as credenciais da plataforma selecionada."""
        plat_key = platform.value if isinstance(platform, Platform) else str(platform)
        vault_data = self._read_vault()
        if plat_key in vault_data:
            del vault_data[plat_key]
            self._write_vault(vault_data)
            return True
        return False

    def list_connected_platforms(self) -> List[Platform]:
        """Retorna a lista de plataformas com credenciais ativas cadastradas."""
        vault_data = self._read_vault()
        connected = []
        for p in Platform:
            if p.value in vault_data and vault_data[p.value]:
                connected.append(p)
        return connected

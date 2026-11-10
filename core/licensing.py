"""core/licensing.py — Gestão de Fonte, Licença e Autorização do ViralCut.

Módulo puro (sem dependências de interface gráfica como Streamlit) responsável
por definir as constantes, validações, normalização fail-safe e resolução de
herança entre vídeos de origem e cortes individuais.

Declaração feita pelo usuário: o app não verifica direitos autorais.
"""

import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

STATUS_NAO_VERIFICADO = "nao_verificado"
STATUS_PROPRIO = "proprio"
STATUS_CAMPANHA = "campanha_autorizada"
STATUS_LICENCA_LIVRE = "licenca_livre"
STATUS_AUTORIZACAO_DIRETA = "autorizacao_direta"

STATUS_BLOQUEADO = STATUS_NAO_VERIFICADO

STATUS_LABELS: Dict[str, str] = {
    STATUS_NAO_VERIFICADO: "Não verificado",
    STATUS_PROPRIO: "Conteúdo próprio",
    STATUS_CAMPANHA: "Campanha autorizada",
    STATUS_LICENCA_LIVRE: "Licença livre (CC / domínio público)",
    STATUS_AUTORIZACAO_DIRETA: "Autorização direta do criador",
}

STATUS_VALIDOS: List[str] = list(STATUS_LABELS.keys())

AVISO_DECLARACAO_USUARIO = (
    "Declaração feita por você. O app não verifica direitos autorais."
)

AVISO_BLOQUEIO_PUBLICACAO = (
    "Bloqueado: fonte/licença não verificada. Declare a fonte e autorização para liberar a publicação."
)

# Limites de caracteres
MAX_LEN_ORIGEM = 300
MAX_LEN_CAMPANHA = 300
MAX_LEN_LINK = 500
MAX_LEN_OBSERVACAO = 1000


def get_default_license() -> Dict[str, Any]:
    """Retorna uma estrutura de licença padrão (fail-safe com status não verificado)."""
    return {
        "status": STATUS_NAO_VERIFICADO,
        "origem": "",
        "campanha": "",
        "link_briefing": "",
        "observacao": "",
        "atualizado_em": "",
    }


def normalize_license(license_dict: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normaliza um dicionário de licença de forma defensiva (fail-safe).

    Se o dicionário for inválido, None, contiver tipo incorreto ou status
    desconhecido, retorna um dicionário válido com status `nao_verificado`.
    Garante que todos os campos esperados existam e sejam strings limpas.
    """
    if not isinstance(license_dict, dict):
        return get_default_license()

    status = str(license_dict.get("status", "")).strip()
    if status not in STATUS_VALIDOS:
        status = STATUS_NAO_VERIFICADO

    origem = str(license_dict.get("origem", "") or "").strip()[:MAX_LEN_ORIGEM]
    campanha = str(license_dict.get("campanha", "") or "").strip()[:MAX_LEN_CAMPANHA]
    link_briefing = str(license_dict.get("link_briefing", "") or "").strip()[:MAX_LEN_LINK]
    observacao = str(license_dict.get("observacao", "") or "").strip()[:MAX_LEN_OBSERVACAO]
    atualizado_em = str(license_dict.get("atualizado_em", "") or "").strip()

    return {
        "status": status,
        "origem": origem,
        "campanha": campanha,
        "link_briefing": link_briefing,
        "observacao": observacao,
        "atualizado_em": atualizado_em,
    }


def validate_license(license_dict: Optional[Dict[str, Any]]) -> List[str]:
    """Valida as regras de negócio para declaração de fonte e licença ao SALVAR.

    Retorna uma lista de mensagens de erro em português. Lista vazia indica que a
    declaração é válida.
    """
    errors: List[str] = []

    if not isinstance(license_dict, dict):
        return ["Estrutura de licença inválida ou ausente."]

    raw_status = license_dict.get("status")
    if not raw_status or str(raw_status).strip() not in STATUS_VALIDOS:
        return [f"Status inválido. Escolha um dos valores permitidos: {', '.join(STATUS_VALIDOS)}."]

    status = str(raw_status).strip()
    origem = str(license_dict.get("origem", "") or "").strip()
    campanha = str(license_dict.get("campanha", "") or "").strip()
    link_briefing = str(license_dict.get("link_briefing", "") or "").strip()
    observacao = str(license_dict.get("observacao", "") or "").strip()

    # Validação de limites
    if len(origem) > MAX_LEN_ORIGEM:
        errors.append(f"O campo 'Origem' excede o limite de {MAX_LEN_ORIGEM} caracteres.")
    if len(campanha) > MAX_LEN_CAMPANHA:
        errors.append(f"O campo 'Campanha' excede o limite de {MAX_LEN_CAMPANHA} caracteres.")
    if len(link_briefing) > MAX_LEN_LINK:
        errors.append(f"O campo 'Link do briefing / licença' excede o limite de {MAX_LEN_LINK} caracteres.")
    if len(observacao) > MAX_LEN_OBSERVACAO:
        errors.append(f"O campo 'Observação' excede o limite de {MAX_LEN_OBSERVACAO} caracteres.")

    # Validação de URL no link_briefing quando preenchido
    if link_briefing:
        if not (link_briefing.startswith("http://") or link_briefing.startswith("https://")):
            errors.append("O link do briefing / licença deve começar com 'http://' ou 'https://'.")

    # Regras por status
    if status == STATUS_CAMPANHA:
        if not campanha:
            errors.append("Para 'Campanha autorizada', o nome da campanha é obrigatório.")
        if not link_briefing:
            errors.append("Para 'Campanha autorizada', o link do briefing ou contrato é obrigatório.")

    elif status == STATUS_LICENCA_LIVRE:
        if not link_briefing:
            errors.append("Para 'Licença livre', o link da licença ou fonte original é obrigatório.")

    elif status == STATUS_AUTORIZACAO_DIRETA:
        if not observacao:
            errors.append("Para 'Autorização direta do criador', a observação é obrigatória (especifique quem autorizou e como).")

    elif status in (STATUS_PROPRIO, STATUS_NAO_VERIFICADO):
        # Nenhum campo adicional é obrigatório
        pass

    return errors


def is_publishable(license_dict: Optional[Dict[str, Any]]) -> bool:
    """Verifica se a licença informada permite publicação externa.

    Critério: Qualquer status diferente de 'nao_verificado' é liberado.
    Em caso de estrutura ausente, inválida ou status desconhecido, retorna False (fail-safe).
    """
    normalized = normalize_license(license_dict)
    return normalized.get("status") != STATUS_BLOQUEADO


def resolve_effective_license(
    video_license: Optional[Dict[str, Any]],
    cut_license: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], str]:
    """Resolve a licença efetiva de um corte aplicando a regra de herança.

    Regra de herança:
    1. Se o corte tiver licença explícita (objeto dict com status presente), prevalece
       a licença do corte (origem = "corte"). Isso permite que um corte seja 'nao_verificado'
       mesmo que o vídeo de origem seja 'proprio'.
    2. Caso contrário, se o vídeo de origem tiver licença (origem = "video").
    3. Caso ambos sejam nulos/vazios, retorna o padrão não verificado (origem = "padrao").

    Retorna:
        Tuple[licenca_efetiva (dict normalizado), origem_da_regra ("corte" | "video" | "padrao")]
    """
    if isinstance(cut_license, dict) and cut_license.get("status"):
        norm_cut = normalize_license(cut_license)
        return norm_cut, "corte"

    if isinstance(video_license, dict) and video_license.get("status"):
        norm_vid = normalize_license(video_license)
        return norm_vid, "video"

    return normalize_license(None), "padrao"


def format_license_for_saving(
    status: str,
    origem: str = "",
    campanha: str = "",
    link_briefing: str = "",
    observacao: str = "",
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Formata um dicionário pronto para ser persistido, aplicando timestamp atual."""
    ts = timestamp or datetime.now().strftime("%d/%m/%Y %H:%M")
    return {
        "status": str(status or "").strip(),
        "origem": str(origem or "").strip()[:MAX_LEN_ORIGEM],
        "campanha": str(campanha or "").strip()[:MAX_LEN_CAMPANHA],
        "link_briefing": str(link_briefing or "").strip()[:MAX_LEN_LINK],
        "observacao": str(observacao or "").strip()[:MAX_LEN_OBSERVACAO],
        "atualizado_em": ts,
    }


def resolve_cut_reference_from_path(video_or_folder_path: str) -> Tuple[Optional[str], Optional[str]]:
    """Deduz (video_id, cut_key) a partir do caminho do arquivo de vídeo ou pasta do corte.

    Exemplos aceitos:
    - data/40vTnhMIrAE/VFDBS_Corte_C2_07m37s_09m50s/VFDBS_...mp4 -> ("40vTnhMIrAE", "00:07:37.05_00:09:50.88")
    - data/x-gczsHxywc/carrossel/parte_01_9-16.mp4 -> ("x-gczsHxywc", "00:00:00.00_00:05:46.00")
    - D:/Repository/shorcut-factory/data/40vTnhMIrAE/... -> ("40vTnhMIrAE", ...)

    Retorna:
        Tuple[video_id, cut_key], sendo (None, None) em caso de falha de resolução.
    """
    if not video_or_folder_path:
        return None, None

    norm_path = os.path.normpath(str(video_or_folder_path).strip())
    parts = norm_path.split(os.sep)

    # Procura pelo diretório 'data' no caminho
    video_id: Optional[str] = None
    if "data" in parts:
        try:
            d_idx = parts.index("data")
            if d_idx + 1 < len(parts):
                cand_vid = parts[d_idx + 1]
                # Não confunde arquivos raiz em data/ com pastas de vídeo
                if not cand_vid.endswith(".json") and not cand_vid.endswith(".db"):
                    video_id = cand_vid
        except Exception:
            video_id = None

    if not video_id:
        return None, None

    # Tenta resolver o cut_key correspondente no cuts_catalog.json do vídeo
    cut_key: Optional[str] = None
    catalog_path = os.path.join("data", video_id, "cuts_catalog.json")
    if os.path.exists(catalog_path):
        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                catalog = json.load(f)
            if isinstance(catalog, dict):
                norm_lower = norm_path.lower()
                base_name = os.path.basename(norm_lower)

                for t_key, entry in catalog.items():
                    if not isinstance(entry, dict):
                        continue

                    # 1. Checa formatos renderizados
                    formats = entry.get("formats", {})
                    if isinstance(formats, dict):
                        for fmt_k, fmt_v in formats.items():
                            if not isinstance(fmt_v, dict):
                                continue
                            vp = fmt_v.get("video_path")
                            fp = fmt_v.get("folder_path")
                            fn = fmt_v.get("folder_name")
                            vfn = fmt_v.get("video_filename")

                            if vp and os.path.normpath(vp).lower() == norm_lower:
                                return video_id, t_key
                            if fp and os.path.normpath(fp).lower() in norm_lower:
                                return video_id, t_key
                            if fn and fn.lower() in norm_lower:
                                return video_id, t_key
                            if vfn and vfn.lower() == base_name:
                                return video_id, t_key

                    # 2. Checa chave direta no caminho
                    if t_key.lower() in norm_lower:
                        return video_id, t_key
        except Exception:
            pass

    return video_id, cut_key


def check_publishable(
    video_id: Optional[str] = None,
    cut_key: Optional[str] = None,
    video_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Guard central de publicação: valida se o corte possui autorização declarada.

    Se video_id ou cut_key não forem informados, deduz a partir de video_path.
    Se não for possível identificar a origem do vídeo, trata como fail-closed (bloqueado).

    Retorna:
    {
        "ok": bool,
        "motivo": str,
        "licenca": dict (normalizado),
        "origem_regra": "corte" | "video" | "padrao",
        "video_id": Optional[str],
        "cut_key": Optional[str]
    }
    """
    resolved_vid = video_id
    resolved_key = cut_key

    if (not resolved_vid or not resolved_key) and video_path:
        deduced_vid, deduced_key = resolve_cut_reference_from_path(video_path)
        if not resolved_vid:
            resolved_vid = deduced_vid
        if not resolved_key:
            resolved_key = deduced_key

    # Se não foi possível identificar o vídeo de origem: fail-closed
    if not resolved_vid:
        return {
            "ok": False,
            "motivo": "Bloqueado: não foi possível identificar a origem do vídeo para validação de licença.",
            "licenca": get_default_license(),
            "origem_regra": "padrao",
            "video_id": None,
            "cut_key": None,
        }

    from core.cuts_catalog import get_effective_license_for_cut

    effective_lic, rule_source = get_effective_license_for_cut(resolved_vid, resolved_key)
    ok = is_publishable(effective_lic)
    motivo = "" if ok else AVISO_BLOQUEIO_PUBLICACAO

    return {
        "ok": ok,
        "motivo": motivo,
        "licenca": effective_lic,
        "origem_regra": rule_source,
        "video_id": resolved_vid,
        "cut_key": resolved_key,
    }


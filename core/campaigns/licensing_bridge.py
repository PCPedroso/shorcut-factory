"""
core/campaigns/licensing_bridge.py — Ponte entre Cadastro de Campanhas e Fonte/Licença.

Implementa a Decisão 11 / Requisito V3:
- Nunca automática ou silenciosa: disparada exclusivamente por ação explícita do usuário;
- Constrói o payload de licença compatível com core/licensing.py (status: campanha_autorizada);
- Exige briefing_url válido (se não houver, recusa com explicação);
- Valida com validate_license antes de salvar;
- Aplica via set_cut_license (só o corte) ou set_video_license (o vídeo inteiro);
- Se o alvo já possuir licença diferente de nao_verificado, exige confirmação explícita (confirm_override=True);
- Sem efeitos colaterais além de set_cut_license e set_video_license.
"""

from typing import Dict, Any, Optional, Tuple, List

from core.licensing import (
    STATUS_CAMPANHA,
    STATUS_NAO_VERIFICADO,
    validate_license,
    format_license_for_saving,
)
from core.cuts_catalog import get_cut_license, set_cut_license
from core.library_manager import get_video_license, set_video_license


def can_apply_campaign_license(campaign: Optional[Dict[str, Any]]) -> Tuple[bool, str]:
    """Verifica se a campanha possui os dados necessários para gerar licença autorizada.

    Para o status 'campanha_autorizada', o link_briefing é estritamente obrigatório.
    """
    if not campaign:
        return False, "Nenhuma campanha informada."

    briefing_url = str(campaign.get("briefing_url") or "").strip()
    if not briefing_url:
        return False, "A campanha não possui link de briefing cadastrado. Preencha o link do briefing na edição da campanha para habilitar a declaração."

    if not (briefing_url.startswith("http://") or briefing_url.startswith("https://")):
        return False, "O link do briefing da campanha é inválido (deve iniciar com http:// ou https://)."

    camp_name = str(campaign.get("name") or "").strip()
    if not camp_name:
        return False, "A campanha não possui um nome válido."

    return True, ""


def build_campaign_license_dict(campaign: Dict[str, Any]) -> Dict[str, Any]:
    """Monta a estrutura de dicionário de licença a partir dos dados da campanha."""
    camp_id = campaign.get("id", "")
    camp_name = str(campaign.get("name") or "").strip()
    source_name = str(campaign.get("source_name") or "").strip()
    origem = source_name if source_name else camp_name
    briefing_url = str(campaign.get("briefing_url") or "").strip()

    return {
        "status": STATUS_CAMPANHA,
        "origem": origem,
        "campanha": camp_name,
        "link_briefing": briefing_url,
        "observacao": f"Gerada a partir do cadastro de campanhas (id {camp_id})",
    }


def check_existing_target_license(
    video_id: str,
    cut_key: Optional[str] = None,
    target: str = "corte",
) -> Optional[Dict[str, Any]]:
    """Recupera a licença explícita atualmente configurada no alvo (corte ou vídeo)."""
    if target == "corte":
        if not video_id or not cut_key:
            return None
        return get_cut_license(video_id, cut_key)
    else:
        if not video_id:
            return None
        return get_video_license(video_id)


def apply_campaign_license(
    campaign: Dict[str, Any],
    video_id: str,
    cut_key: Optional[str] = None,
    target: str = "corte",
    confirm_override: bool = False,
) -> Dict[str, Any]:
    """Aplica a declaração de campanha autorizada no corte ou no vídeo pai.

    Parâmetros:
    - campaign: dicionário com os dados da campanha (id, name, source_name, briefing_url);
    - video_id: ID do vídeo no app;
    - cut_key: chave do corte no cuts_catalog.json (obrigatório se target == 'corte');
    - target: 'corte' ou 'video';
    - confirm_override: True para autorizar a substituição de uma licença prévia que não seja nao_verificado.

    Retorna:
    {"success": bool, "error": Optional[str], "license": Optional[dict], "requires_confirmation": bool}
    """
    if target not in ("corte", "video"):
        return {"success": False, "error": f"Alvo inválido: '{target}'. Deve ser 'corte' ou 'video'."}

    if not video_id:
        return {"success": False, "error": "ID do vídeo não informado."}

    if target == "corte" and not cut_key:
        return {"success": False, "error": "Chave do corte (cut_key) obrigatória para aplicar no corte."}

    # 1. Verifica pré-requisitos da campanha
    ok_camp, msg_camp = can_apply_campaign_license(campaign)
    if not ok_camp:
        return {"success": False, "error": msg_camp}

    # 2. Verifica se o alvo já possui licença ativa diferente de nao_verificado
    existing_lic = check_existing_target_license(video_id=video_id, cut_key=cut_key, target=target)
    if existing_lic:
        existing_status = str(existing_lic.get("status") or "").strip()
        if existing_status and existing_status != STATUS_NAO_VERIFICADO and not confirm_override:
            return {
                "success": False,
                "error": f"O {target} já possui uma licença configurada ('{existing_status}'). É necessária confirmação explícita para substituir.",
                "requires_confirmation": True,
                "existing_license": existing_lic,
            }

    # 3. Constrói dicionário e valida
    new_lic = build_campaign_license_dict(campaign)
    errors = validate_license(new_lic)
    if errors:
        return {
            "success": False,
            "error": f"Erro de validação na licença da campanha: {'; '.join(errors)}",
        }

    formatted_lic = format_license_for_saving(
        status=new_lic["status"],
        origem=new_lic.get("origem", ""),
        campanha=new_lic.get("campanha", ""),
        link_briefing=new_lic.get("link_briefing", ""),
        observacao=new_lic.get("observacao", ""),
    )

    # 4. Aplica no destino apropriado
    try:
        if target == "corte":
            saved = set_cut_license(video_id, cut_key, formatted_lic)
        else:
            saved = set_video_license(video_id, formatted_lic)

        return {
            "success": True,
            "error": None,
            "license": saved,
            "target": target,
        }
    except Exception as exc:
        return {
            "success": False,
            "error": f"Falha ao salvar licença no {target}: {str(exc)}",
        }

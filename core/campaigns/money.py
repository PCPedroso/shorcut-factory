"""
core/campaigns/money.py — Regras de Negócio Puras, Cálculos Financeiros e Validações.

Implementa:
- Tratamento estrito de valores monetários em centavos inteiros (INTEGER);
- Parse flexível de entradas decimais ("1,50", "1.50", "1.234,56");
- Formatação padrão para BRL ("R$ 1.234,56") e USD ("US$ 1.234,56");
- Fórmulas puras de comissão, teto, valor bruto, líquido e RPM real;
- Validações de campanha, post e lançamento retornando listas de erros.
"""

import re
import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, Dict, Any, List, Tuple, Union


SUPPORTED_PLATFORMS: List[str] = [
    "youtube",
    "instagram",
    "tiktok",
    "x",
    "kwai",
    "facebook",
    "outra",
]

PLATFORM_LABELS: Dict[str, str] = {
    "youtube": "YouTube",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "x": "X (Twitter)",
    "kwai": "Kwai",
    "facebook": "Facebook",
    "outra": "Outra",
}

PLATFORM_ICONS: Dict[str, str] = {
    "youtube": "🔴",
    "instagram": "📸",
    "tiktok": "🎵",
    "x": "✖️",
    "kwai": "🟠",
    "facebook": "🔵",
    "outra": "🌐",
}


def parse_money_cents(
    val: Union[str, int, float, Decimal, None],
    allow_none: bool = False
) -> Optional[int]:
    """Converte valores arbitrários (string com vírgula ou ponto, int, Decimal) em centavos inteiros.

    Exemplos:
    - "1,50" -> 150
    - "1.50" -> 150
    - "1.234,56" -> 123456
    - "1234.56" -> 123456
    - 150 -> 15000 (se numérico, assume unidades reais, ex: 150.0 = R$ 150,00)
    - "" ou None -> None (se allow_none=True) ou erro ValueError

    Lança ValueError em caso de número negativo ou texto não numérico inválido.
    """
    if val is None:
        if allow_none:
            return None
        raise ValueError("Valor monetário não pode ser nulo.")

    if isinstance(val, (int, Decimal)):
        # Se for int direto, se for muito grande já pode ser centavos, mas a interface passa string
        dec_val = Decimal(str(val))
        cents = int((dec_val * 100).quantize(Decimal("1")))
        if cents < 0:
            raise ValueError("Valor monetário não pode ser negativo.")
        return cents

    if isinstance(val, float):
        dec_val = Decimal(str(round(val, 2)))
        cents = int((dec_val * 100).quantize(Decimal("1")))
        if cents < 0:
            raise ValueError("Valor monetário não pode ser negativo.")
        return cents

    s = str(val).strip()
    if not s:
        if allow_none:
            return None
        raise ValueError("Valor monetário não pode ser vazio.")

    # Remove símbolos de moeda comuns
    s = s.replace("R$", "").replace("US$", "").replace("$", "").strip()

    # Normaliza separadores de milhar e decimal
    # Se contém '.' e ',', assume formato brasileiro '1.234,56'
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        # Apenas vírgula, ex: '1234,56' ou '1,5'
        s = s.replace(",", ".")
    # Se contém apenas pontos: pode ser '1.234' (milhar) ou '12.34' (decimal)
    elif "." in s:
        parts = s.split(".")
        if len(parts) > 2:
            # Vários pontos: '1.000.000'
            s = "".join(parts)
        elif len(parts) == 2 and len(parts[1]) == 3 and int(parts[1]) >= 0:
            # Ponto único seguido de 3 dígitos pode ser milhar (ex: '1.500')
            # Porém para dinheiro em input web normalmente '1.50' ou '1500' é digitado.
            # Se tiver mais de 2 casas após o ponto e começar com número pequeno, tratar com cuidado
            pass

    try:
        dec = Decimal(s)
    except InvalidOperation:
        raise ValueError(f"Formato numérico inválido para valor monetário: '{val}'")

    if dec < 0:
        raise ValueError("Valor monetário não pode ser negativo.")

    # Converte para centavos com arredondamento seguro
    cents = int((dec * Decimal(100)).quantize(Decimal("1")))
    return cents


def format_money_cents(cents: Optional[int], currency: str = "BRL") -> str:
    """Formata valor em centavos inteiros como string monetária legível.

    Exemplos:
    - 123456, "BRL" -> "R$ 1.234,56"
    - 123456, "USD" -> "US$ 1.234,56"
    - None -> "—"
    """
    if cents is None:
        return "—"

    prefix = "US$ " if currency.upper() == "USD" else "R$ "
    abs_cents = abs(int(cents))
    reais = abs_cents // 100
    resto = abs_cents % 100

    # Formata milhares com ponto
    reais_str = f"{reais:,}".replace(",", ".")
    sign = "-" if cents < 0 else ""
    return f"{sign}{prefix}{reais_str},{resto:02d}"


def calculate_cut_earnings(
    views: int,
    rate_per_1000_cents: int,
    cap_per_clip_cents: Optional[int] = None,
    fee_bp: int = 0,
    earnings_reported_cents: Optional[int] = None,
    hold_days: int = 0,
    snapshot_date: Optional[Union[str, datetime.date]] = None,
) -> Dict[str, Any]:
    """Calcula os valores brutos, comissão, líquido e ganho considerado segundo a Decisão 8.

    Fórmulas:
    - bruto = (views * rate_per_1000_cents + 500) // 1000
    - se cap_per_clip_cents: bruto = min(bruto, cap_per_clip_cents)
    - comissao = (bruto * fee_bp + 5000) // 10000
    - liquido = bruto - comissao
    - considerado = earnings_reported_cents se informado; senão liquido
    - rpm_real = (considerado * 1000 / views) se views > 0 senão None

    Retorna dicionário completo com todos os valores calculados.
    """
    v = max(0, int(views or 0))
    rate = max(0, int(rate_per_1000_cents or 0))
    fee = max(0, min(10000, int(fee_bp or 0)))

    # Valor Bruto estimado (arredondamento .5 para cima com +500)
    bruto = (v * rate + 500) // 1000

    # Aplicação de Teto por Clipe se configurado
    if cap_per_clip_cents is not None and cap_per_clip_cents >= 0:
        bruto = min(bruto, int(cap_per_clip_cents))

    # Comissão de agência / taxa (fee_bp em pontos-base: 1000 = 10%)
    comissao = (bruto * fee + 5000) // 10000
    liquido = bruto - comissao

    # Ganho considerado
    has_reported = earnings_reported_cents is not None and earnings_reported_cents >= 0
    considerado = int(earnings_reported_cents) if has_reported else liquido

    # Ganho real por mil views (RPM real em centavos)
    rpm_cents = (considerado * 1000 / v) if v > 0 else None

    # Previsão de liberação
    liberacao_dt: Optional[datetime.date] = None
    if snapshot_date:
        d = parse_iso_date(snapshot_date) if isinstance(snapshot_date, str) else snapshot_date
        if d:
            liberacao_dt = d + datetime.timedelta(days=max(0, int(hold_days or 0)))

    return {
        "views": v,
        "bruto_cents": bruto,
        "comissao_cents": comissao,
        "liquido_cents": liquido,
        "earnings_reported_cents": int(earnings_reported_cents) if has_reported else None,
        "considerado_cents": considerado,
        "rpm_real_cents": rpm_cents,
        "liberacao_date": liberacao_dt.isoformat() if liberacao_dt else None,
        "is_reported": has_reported,
    }


def parse_iso_date(val: Optional[Union[str, datetime.date]]) -> Optional[datetime.date]:
    """Valida e converte uma data em formato ISO 'YYYY-MM-DD'."""
    if not val:
        return None
    if isinstance(val, datetime.date):
        return val
    s = str(val).strip()
    try:
        # Se vier timestamp completo ISO, pega só a parte da data
        if "T" in s:
            s = s.split("T")[0]
        return datetime.datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def format_date_br(val: Optional[Union[str, datetime.date]]) -> str:
    """Converte data ISO para exibição no padrão brasileiro 'DD/MM/AAAA'."""
    if not val:
        return "—"
    d = parse_iso_date(val) if isinstance(val, str) else val
    if not d:
        return str(val)
    return d.strftime("%d/%m/%Y")


def is_campaign_expired(ends_on: Optional[Union[str, datetime.date]], ref_date: Optional[datetime.date] = None) -> bool:
    """Determina se uma campanha está vencida.

    Regra da Decisão 5: Campanha 'vencida' = hoje > ends_on (o último dia vale até 23:59).
    """
    if not ends_on:
        return False
    d_end = parse_iso_date(ends_on) if isinstance(ends_on, str) else ends_on
    if not d_end:
        return False
    today = ref_date or datetime.date.today()
    return today > d_end


def days_until_expiration(ends_on: Optional[Union[str, datetime.date]], ref_date: Optional[datetime.date] = None) -> Optional[int]:
    """Retorna número de dias restantes até o encerramento da campanha.

    Positivo = faltam N dias; 0 = termina hoje; Negativo = já expirou.
    """
    if not ends_on:
        return None
    d_end = parse_iso_date(ends_on) if isinstance(ends_on, str) else ends_on
    if not d_end:
        return None
    today = ref_date or datetime.date.today()
    return (d_end - today).days


# ── VALIDAÇÕES DE DADOS ───────────────────────────────────────────────────────

def validate_campaign_data(data: Dict[str, Any]) -> List[str]:
    """Valida os dados para criação ou edição de Campanha."""
    errors: List[str] = []
    if not isinstance(data, dict):
        return ["Dados da campanha devem ser um dicionário."]

    name = str(data.get("name") or "").strip()
    if not name:
        errors.append("O nome da campanha é obrigatório.")
    elif len(name) > 120:
        errors.append(f"O nome da campanha excede o limite de 120 caracteres ({len(name)}).")

    currency = str(data.get("currency") or "BRL").upper().strip()
    if currency not in ("BRL", "USD"):
        errors.append("A moeda da campanha deve ser 'BRL' ou 'USD'.")

    rate = data.get("rate_per_1000_cents")
    if rate is None or not isinstance(rate, int) or rate < 0:
        errors.append("O valor por 1.000 views (em centavos) é obrigatório e deve ser maior ou igual a zero.")

    cap = data.get("cap_per_clip_cents")
    if cap is not None:
        if not isinstance(cap, int) or cap < 0:
            errors.append("O teto por clipe (em centavos) deve ser maior ou igual a zero ou nulo.")

    fee_bp = data.get("fee_bp", 0)
    if not isinstance(fee_bp, int) or fee_bp < 0 or fee_bp > 10000:
        errors.append("A comissão da campanha deve estar entre 0% e 100% (0 a 10.000 pontos-base).")

    hold_days = data.get("hold_days", 0)
    if not isinstance(hold_days, int) or hold_days < 0 or hold_days > 365:
        errors.append("O prazo de retenção (hold days) deve estar entre 0 e 365 dias.")

    starts_on = data.get("starts_on")
    ends_on = data.get("ends_on")
    d_start = parse_iso_date(starts_on) if starts_on else None
    d_end = parse_iso_date(ends_on) if ends_on else None

    if starts_on and not d_start:
        errors.append("A data de início deve estar no formato 'YYYY-MM-DD'.")
    if ends_on and not d_end:
        errors.append("A data de término deve estar no formato 'YYYY-MM-DD'.")
    if d_start and d_end and d_start > d_end:
        errors.append(f"A data de início ({format_date_br(d_start)}) não pode ser posterior à data de término ({format_date_br(d_end)}).")

    briefing_url = str(data.get("briefing_url") or "").strip()
    if briefing_url:
        if not (briefing_url.startswith("http://") or briefing_url.startswith("https://")):
            errors.append("O link do briefing deve começar com 'http://' ou 'https://'.")

    platforms = data.get("platforms", [])
    if not isinstance(platforms, (list, set)) or not platforms:
        errors.append("A campanha deve aceitar pelo menos uma plataforma.")
    else:
        for p in platforms:
            if str(p).lower().strip() not in SUPPORTED_PLATFORMS:
                errors.append(f"Plataforma inválida: '{p}'.")

    status = str(data.get("status") or "ativa").lower().strip()
    if status not in ("ativa", "pausada", "encerrada"):
        errors.append("O status da campanha deve ser 'ativa', 'pausada' ou 'encerrada'.")

    return errors


def validate_post_data(data: Dict[str, Any]) -> List[str]:
    """Valida os dados para registro de Publicação (Post)."""
    errors: List[str] = []
    if not isinstance(data, dict):
        return ["Dados da publicação devem ser um dicionário."]

    platform = str(data.get("platform") or "").lower().strip()
    if not platform or platform not in SUPPORTED_PLATFORMS:
        errors.append(f"Plataforma de publicação inválida ou não suportada: '{platform}'.")

    posted_on = data.get("posted_on")
    d_posted = parse_iso_date(posted_on) if posted_on else None
    if not d_posted:
        errors.append("A data de publicação é obrigatória e deve estar no formato 'YYYY-MM-DD'.")

    post_url = str(data.get("post_url") or "").strip()
    if post_url:
        if not (post_url.startswith("http://") or post_url.startswith("https://")):
            errors.append("O link da publicação deve começar com 'http://' ou 'https://'.")

    currency = str(data.get("currency") or "BRL").upper().strip()
    if currency not in ("BRL", "USD"):
        errors.append("A moeda da publicação deve ser 'BRL' ou 'USD'.")

    return errors


def validate_snapshot_data(data: Dict[str, Any], ref_date: Optional[datetime.date] = None) -> List[str]:
    """Valida os dados para um Lançamento de Visualizações / Ganhos."""
    errors: List[str] = []
    if not isinstance(data, dict):
        return ["Dados do lançamento devem ser um dicionário."]

    views = data.get("views")
    if views is None or not isinstance(views, int) or views < 0:
        errors.append("A quantidade de visualizações acumuladas deve ser um número inteiro maior ou igual a zero.")

    snapshot_on = data.get("snapshot_on")
    d_snap = parse_iso_date(snapshot_on) if snapshot_on else None
    if not d_snap:
        errors.append("A data do lançamento é obrigatória e deve estar no formato 'YYYY-MM-DD'.")
    else:
        today = ref_date or datetime.date.today()
        if d_snap > today:
            errors.append(f"A data do lançamento ({format_date_br(d_snap)}) não pode ser uma data futura.")

    earnings = data.get("earnings_cents")
    if earnings is not None:
        if not isinstance(earnings, int) or earnings < 0:
            errors.append("O ganho informado deve ser maior ou igual a zero.")

    return errors


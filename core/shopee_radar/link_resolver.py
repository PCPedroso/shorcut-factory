import re
import urllib.parse
from typing import Optional, Dict, Any, Tuple
import requests

class ShopeeLinkResolver:
    """
    Resolve URLs de afiliados (shope.ee, s.shopee.com.br, bit.ly) e links canônicos
    da Shopee, extraindo o shop_id e item_id necessários para consultar métricas de vendas.
    """

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    }

    # Regex para capturar shope.ee / s.shopee.com.br
    SHORT_DOMAINS_REGEX = re.compile(
        r"(https?:\/\/(?:shope\.ee|s\.shopee\.com\.br|shp\.ee)\/[A-Za-z0-9_-]+)",
        re.IGNORECASE
    )

    # Regex para URLs canônicas da Shopee:
    # 1. /product/{shop_id}/{item_id}
    PATTERN_PRODUCT = re.compile(
        r"shopee\.[a-z\.]+\/product\/(\d+)\/(\d+)",
        re.IGNORECASE
    )
    # 2. /{slug}-i.{shop_id}.{item_id}
    PATTERN_SLUG_I = re.compile(
        r"-i\.(\d+)\.(\d+)",
        re.IGNORECASE
    )
    # 3. Parâmetros na query string: itemid=... & shopid=...
    PATTERN_ITEMID_QUERY = re.compile(r"[?&]itemid=(\d+)", re.IGNORECASE)
    PATTERN_SHOPID_QUERY = re.compile(r"[?&]shopid=(\d+)", re.IGNORECASE)

    def __init__(self, timeout: int = 12, session: Optional[requests.Session] = None):
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)

    def extract_short_urls(self, text: str) -> list[str]:
        """Encontra todos os links curtos da Shopee em um texto/legenda."""
        if not text:
            return []
        matches = self.SHORT_DOMAINS_REGEX.findall(text)
        # Remove duplicatas preservando ordem
        seen = set()
        unique = []
        for url in matches:
            if url not in seen:
                seen.add(url)
                unique.append(url)
        return unique

    def resolve_url(self, raw_url: str) -> Dict[str, Any]:
        """
        Segue redirects para desmascarar a URL final e extrai shop_id e item_id.
        Retorna dicionário com status, url_final, shop_id, item_id e url canônica limpa.
        """
        raw_url = raw_url.strip()
        result: Dict[str, Any] = {
            "original_url": raw_url,
            "final_url": raw_url,
            "shop_id": None,
            "item_id": None,
            "canonical_url": None,
            "success": False,
            "error": None
        }

        # Se já tiver os parâmetros diretamente na URL original, tenta extrair antes de fazer requisição
        shop_id, item_id = self.parse_ids_from_url(raw_url)
        if shop_id and item_id:
            result["shop_id"] = shop_id
            result["item_id"] = item_id
            result["canonical_url"] = f"https://shopee.com.br/product/{shop_id}/{item_id}"
            result["success"] = True

        # Se for link encurtado ou não tiver IDs ainda, segue redirecionamentos
        if not (shop_id and item_id) or any(d in raw_url for d in ["shope.ee", "s.shopee.com.br", "shp.ee", "bit.ly"]):
            try:
                # Faz requisição HEAD primeiro; se não permitir, usa GET com stream=True para economizar banda
                response = self.session.get(
                    raw_url,
                    allow_redirects=True,
                    timeout=self.timeout,
                    stream=True
                )
                final_url = response.url
                result["final_url"] = final_url

                # Se a URL tiver redirecionamento embutido (ex: universal-link?redir=...)
                parsed = urllib.parse.urlparse(final_url)
                qs = urllib.parse.parse_qs(parsed.query)
                if "redir" in qs and qs["redir"]:
                    nested_redir = urllib.parse.unquote(qs["redir"][0])
                    s_id, i_id = self.parse_ids_from_url(nested_redir)
                    if s_id and i_id:
                        shop_id, item_id = s_id, i_id

                # Se ainda não encontrou, busca na final_url
                if not (shop_id and item_id):
                    shop_id, item_id = self.parse_ids_from_url(final_url)

                if shop_id and item_id:
                    result["shop_id"] = shop_id
                    result["item_id"] = item_id
                    result["canonical_url"] = f"https://shopee.com.br/product/{shop_id}/{item_id}"
                    result["success"] = True
                elif "error_page" in final_url:
                    result["error"] = "Link da Shopee expirado ou desativado pelo vendedor (redirecionou para error_page)."
                    result["is_expired"] = True
                elif any(x in final_url for x in ["/m/", "flash_sale", "collection/", "universal-link"]):
                    result["error"] = "Link aponta para uma página de categoria ou campanha promocional da Shopee, não um produto individual."
                    result["is_category"] = True
                elif "linktr.ee" in final_url or "beacons.ai" in final_url:
                    result["error"] = "Link aponta para outra vitrine/agregador, não diretamente para a Shopee."
                    result["is_sub_vitrine"] = True
                else:
                    result["error"] = "Não foi possível extrair shop_id e item_id da URL final."

            except Exception as e:
                result["error"] = f"Falha na resolução de redirecionamento: {str(e)}"

        return result

    @classmethod
    def parse_ids_from_url(cls, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extrai (shop_id, item_id) a partir de qualquer variante de URL da Shopee.
        """
        if not url:
            return None, None

        # 1. Padrão: /product/{shop_id}/{item_id}
        m = cls.PATTERN_PRODUCT.search(url)
        if m:
            return m.group(1), m.group(2)

        # 2. Padrão: /{slug}-i.{shop_id}.{item_id}
        m = cls.PATTERN_SLUG_I.search(url)
        if m:
            return m.group(1), m.group(2)

        # 3. Padrão: query parameters (itemid=... & shopid=...)
        m_item = cls.PATTERN_ITEMID_QUERY.search(url)
        m_shop = cls.PATTERN_SHOPID_QUERY.search(url)
        if m_item and m_shop:
            return m_shop.group(1), m_item.group(1)

        return None, None

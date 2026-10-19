import json
import re
from urllib.parse import urlparse
from typing import Optional, List, Dict, Any, Tuple
import requests

class CatalogResolver:
    """
    Resolve coleções e agregadores de links usados por criadores de Achadinhos:
    - Minha Coleção Shopee (mycollection.shop/{username})
    - Linktree (linktr.ee/{username})
    - Beacons (beacons.ai/{username})
    Permite encontrar o link da Shopee pelo número/código mencionado no Reel (ex: "Link 415"),
    além de suportar vitrines com menus de sub-categorias / pastas.
    """

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9",
    }

    SHOPEE_DOMAINS = ("shope.ee", "s.shopee.com.br", "shp.ee", "shopee.com.br", "shopee.com")
    AGGREGATOR_DOMAINS = ("linktr.ee", "beacons.ai", "mycollection.shop", "heylink.me")

    def __init__(self, timeout: int = 10, session: Optional[requests.Session] = None):
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)

    def is_shopee_product_url(self, url: str) -> bool:
        """Verifica se a URL aponta estritamente para um produto ou link encurtado da Shopee."""
        if not url:
            return False
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            if any(d in netloc for d in ("shope.ee", "s.shopee.com.br", "shp.ee")):
                return True
            if "shopee.com.br" in netloc or "shopee.com" in netloc:
                return bool("/product/" in url or "-i." in url or "itemid=" in url)
            return False
        except Exception:
            return False

    def is_aggregator_url(self, url: str) -> bool:
        """Verifica se a URL aponta para outro agregador (sub-vitrine / pasta / categoria)."""
        if not url:
            return False
        try:
            netloc = urlparse(url).netloc.lower()
            return any(d in netloc for d in self.AGGREGATOR_DOMAINS)
        except Exception:
            return False

    def inspect_storefront(self, url: str) -> Dict[str, Any]:
        """
        Inspeciona a vitrine e classifica os links encontrados em:
        - direct_products: links que apontam para a Shopee
        - categories: links que apontam para outras sub-vitrines / pastas de categorias
        - store_or_campaigns: links que apontam para lojas ou categorias gerais da Shopee
        """
        result: Dict[str, Any] = {
            "url": url,
            "direct_products": [],
            "categories": [],
            "store_or_campaigns": [],
            "all_extracted_count": 0
        }

        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code != 200:
                return result

            html = resp.text

            # 1. Procura blocos application/json (Next.js props no Linktree)
            scripts = re.findall(r'<script[^>]*type=[\'"]application\/json[\'"][^>]*>(.*?)<\/script>', html, re.DOTALL)
            found_json_links = False
            for s in scripts:
                if "pageProps" in s:
                    try:
                        data = json.loads(s)
                        props = data.get("props", {}).get("pageProps", {})
                        links_data = (
                            props.get("account", {}).get("links", [])
                            or props.get("links", [])
                        )
                        for item in links_data:
                            found_json_links = True
                            title = (item.get("title") or "").strip()
                            target_url = (item.get("url") or "").strip()
                            if not target_url:
                                continue

                            entry = {
                                "title": title,
                                "url": target_url,
                                "source": "linktree"
                            }

                            if self.is_aggregator_url(target_url) and target_url.rstrip("/") != url.rstrip("/"):
                                entry["type"] = "category"
                                result["categories"].append(entry)
                            elif self.is_shopee_product_url(target_url):
                                entry["type"] = "shopee_product"
                                result["direct_products"].append(entry)
                            elif any(d in target_url for d in self.SHOPEE_DOMAINS):
                                entry["type"] = "shopee_store_or_campaign"
                                result["store_or_campaigns"].append(entry)
                    except Exception:
                        pass

            # 2. Fallback: extração direta de hrefs no HTML
            if not found_json_links:
                matches = re.findall(r'href=[\'"]([^\'"]+)[\'"]', html)
                seen = set()
                for m in matches:
                    if m in seen:
                        continue
                    seen.add(m)
                    entry = {"title": "", "url": m, "source": "html_href"}
                    if self.is_aggregator_url(m) and m.rstrip("/") != url.rstrip("/"):
                        entry["type"] = "category"
                        result["categories"].append(entry)
                    elif self.is_shopee_product_url(m):
                        entry["type"] = "shopee_product"
                        result["direct_products"].append(entry)
                    elif any(d in m for d in self.SHOPEE_DOMAINS):
                        entry["type"] = "shopee_store_or_campaign"
                        result["store_or_campaigns"].append(entry)

            result["all_extracted_count"] = (
                len(result["direct_products"]) +
                len(result["categories"]) +
                len(result["store_or_campaigns"])
            )
        except Exception:
            pass

        return result

    def extract_linktree_items(self, url: str) -> List[Dict[str, Any]]:
        """
        Extrai itens de uma página Linktree.
        Se for uma página com produtos diretos, retorna os produtos.
        Se for um Hub de Categorias (sub-Linktrees), explora as sub-categorias para achar produtos.
        """
        inspection = self.inspect_storefront(url)
        if inspection["direct_products"]:
            return inspection["direct_products"]

        # Se não há produtos diretos, mas há links de campanhas Shopee (ex: shope.ee/... de categoria)
        # retornamos para que o serviço possa avaliar/diagnosticar
        if not inspection["categories"] and inspection["store_or_campaigns"]:
            return inspection["store_or_campaigns"]

        # Se for um Hub com sub-categorias, explora as sub-vitrines
        items: List[Dict[str, Any]] = []
        for cat in inspection["categories"][:4]:
            cat_url = cat.get("url")
            cat_title = cat.get("title") or "Categoria"
            if cat_url and "linktr.ee" in cat_url:
                try:
                    sub_insp = self.inspect_storefront(cat_url)
                    for p in sub_insp["direct_products"] or sub_insp["store_or_campaigns"]:
                        p["category_name"] = cat_title
                        items.append(p)
                except Exception:
                    pass

        return items

    def extract_storefront_items(self, url: str) -> List[Dict[str, Any]]:
        """
        Extrai todos os produtos de qualquer agregador ou vitrine pública:
        - Linktree (linktr.ee/...)
        - Beacons (beacons.ai/...)
        - Minha Coleção Shopee (mycollection.shop/...)
        - Páginas genéricas com links de afiliados Shopee
        """
        url_lower = url.lower()
        if "linktr.ee" in url_lower:
            return self.extract_linktree_items(url)
        elif "mycollection.shop" in url_lower:
            return self.extract_mycollection_items(url)
        else:
            inspection = self.inspect_storefront(url)
            return inspection["direct_products"] or inspection["store_or_campaigns"]

    def extract_mycollection_items(self, url: str) -> List[Dict[str, Any]]:
        """
        Extrai links e títulos de páginas Shopee MyCollection (mycollection.shop/{user}).
        """
        items: List[Dict[str, Any]] = []
        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code != 200:
                return items

            html = resp.text
            links = re.findall(r'href=[\'"](https?:\/\/(?:shope\.ee|s\.shopee\.com\.br|shopee\.com\.br)[^\'"]+)[\'"]', html)
            seen = set()
            for link in links:
                if link not in seen:
                    seen.add(link)
                    items.append({
                        "title": "",
                        "url": link,
                        "source": "mycollection"
                    })
        except Exception:
            pass
        return items

    def find_item_by_code(self, catalog_url: str, code: str | int) -> Optional[str]:
        """
        Busca o link de um produto no catálogo a partir do código mencionado no post (ex: 412).
        """
        code_str = str(code).strip()
        if not code_str:
            return None

        items: List[Dict[str, Any]] = self.extract_storefront_items(catalog_url)

        # Procura correspondência exata ou prefixada do código no título
        code_pattern = re.compile(rf"\b0*{re.escape(code_str)}\b", re.IGNORECASE)

        for item in items:
            title = item.get("title", "")
            if code_pattern.search(title):
                return item.get("url")

        return None

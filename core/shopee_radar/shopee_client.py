import time
from typing import Optional, Dict, Any
import requests

class ShopeeClient:
    """
    Cliente para consulta e enriquecimento de dados de produtos da Shopee.
    Extrai métricas reais de vendas (historical_sold, sold mensal, rating, estoque, preço).
    """

    API_BASE = "https://shopee.com.br/api/v4/item/get"
    IMAGE_BASE = "https://down-br.img.susercontent.com/file"

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://shopee.com.br/",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "X-Requested-With": "XMLHttpRequest",
    }

    def __init__(self, timeout: int = 10, session: Optional[requests.Session] = None):
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)

    def get_product_details(self, shop_id: str | int, item_id: str | int) -> Dict[str, Any]:
        """
        Consulta os dados detalhados de um produto pelo shop_id e item_id.
        """
        shop_id = str(shop_id).strip()
        item_id = str(item_id).strip()

        params = {
            "itemid": item_id,
            "shopid": shop_id
        }

        result: Dict[str, Any] = {
            "item_id": item_id,
            "shop_id": shop_id,
            "url": f"https://shopee.com.br/product/{shop_id}/{item_id}",
            "title": "",
            "price": 0.0,
            "price_min": 0.0,
            "price_max": 0.0,
            "currency": "BRL",
            "historical_sold": 0,
            "monthly_sold": 0,
            "rating_star": 0.0,
            "rating_count": 0,
            "stock": 0,
            "image_url": "",
            "shop_location": "",
            "is_official_shop": False,
            "liked_count": 0,
            "timestamp": int(time.time()),
            "success": False,
            "error": None
        }

        try:
            resp = self.session.get(self.API_BASE, params=params, timeout=self.timeout)
            
            if resp.status_code != 200:
                result["error"] = f"HTTP {resp.status_code} ao consultar Shopee API"
                return result

            payload = resp.json()

            # Estrutura padrão: { "data": { ... } }
            data = payload.get("data")
            if not data:
                error_msg = payload.get("error_msg") or payload.get("message") or "Produto não encontrado ou indisponível"
                result["error"] = f"Erro retornado pela Shopee: {error_msg}"
                return result

            # Extração e normalização
            result["title"] = data.get("name", "").strip()
            
            # Preços na Shopee vêm multiplicados por 100.000
            price_raw = data.get("price", 0)
            price_min_raw = data.get("price_min", price_raw)
            price_max_raw = data.get("price_max", price_raw)

            result["price"] = round(price_raw / 100000.0, 2)
            result["price_min"] = round(price_min_raw / 100000.0, 2)
            result["price_max"] = round(price_max_raw / 100000.0, 2)

            result["historical_sold"] = int(data.get("historical_sold", 0))
            result["monthly_sold"] = int(data.get("sold", 0))

            # Avaliações
            item_rating = data.get("item_rating") or {}
            result["rating_star"] = round(float(item_rating.get("rating_star", 0.0)), 2)
            rating_counts = item_rating.get("rating_count", [])
            result["rating_count"] = sum(rating_counts) if isinstance(rating_counts, list) else int(rating_counts or 0)

            # Estoque e atributos
            result["stock"] = int(data.get("stock", 0))
            result["shop_location"] = data.get("shop_location", "")
            result["is_official_shop"] = bool(data.get("is_official_shop", False))
            result["liked_count"] = int(data.get("liked_count", 0))

            # Imagem principal
            image_hash = data.get("image")
            if image_hash:
                result["image_url"] = f"{self.IMAGE_BASE}/{image_hash}"
            elif data.get("images") and len(data.get("images")) > 0:
                result["image_url"] = f"{self.IMAGE_BASE}/{data.get('images')[0]}"

            result["success"] = True

        except requests.exceptions.RequestException as e:
            result["error"] = f"Erro de conexão com a Shopee: {str(e)}"
        except Exception as e:
            result["error"] = f"Erro ao processar dados da Shopee: {str(e)}"

        return result

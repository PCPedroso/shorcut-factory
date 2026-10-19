import os
import sqlite3
import time
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

class ShopeeTrendEngine:
    """
    Motor de persistência e análise de aceleração de vendas de produtos da Shopee
    correlacionados com posts do Instagram.
    """

    def __init__(self, db_path: str = "data/shopee_trends.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Tabela de Produtos
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                shop_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                title TEXT,
                url TEXT,
                image_url TEXT,
                price REAL,
                rating_star REAL,
                rating_count INTEGER,
                stock INTEGER,
                created_at INTEGER,
                updated_at INTEGER,
                UNIQUE(shop_id, item_id)
            )
            """)

            # Tabela de Snapshots de Vendas (para cálculo do Delta ao longo do tempo)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shop_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                historical_sold INTEGER NOT NULL,
                monthly_sold INTEGER,
                price REAL,
                timestamp INTEGER NOT NULL
            )
            """)

            # Tabela de Menções do Instagram (Reels que promoveram o produto)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS instagram_mentions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_url TEXT UNIQUE,
                shortcode TEXT,
                creator TEXT,
                caption TEXT,
                views INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                intent_score REAL DEFAULT 0,
                shop_id TEXT,
                item_id TEXT,
                detected_at INTEGER NOT NULL
            )
            """)
            conn.commit()

    def record_product(self, product_data: Dict[str, Any]) -> str:
        """
        Insere ou atualiza um produto e registra um snapshot no histórico de vendas.
        """
        shop_id = str(product_data.get("shop_id"))
        item_id = str(product_data.get("item_id"))
        prod_key = f"{shop_id}_{item_id}"
        now = int(time.time())

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO products (
                id, shop_id, item_id, title, url, image_url, price,
                rating_star, rating_count, stock, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(shop_id, item_id) DO UPDATE SET
                title = excluded.title,
                url = excluded.url,
                image_url = excluded.image_url,
                price = excluded.price,
                rating_star = excluded.rating_star,
                rating_count = excluded.rating_count,
                stock = excluded.stock,
                updated_at = excluded.updated_at
            """, (
                prod_key,
                shop_id,
                item_id,
                product_data.get("title", ""),
                product_data.get("url", f"https://shopee.com.br/product/{shop_id}/{item_id}"),
                product_data.get("image_url", ""),
                product_data.get("price", 0.0),
                product_data.get("rating_star", 0.0),
                product_data.get("rating_count", 0),
                product_data.get("stock", 0),
                now,
                now
            ))

            # Registra snapshot de vendas
            historical_sold = product_data.get("historical_sold", 0)
            monthly_sold = product_data.get("monthly_sold", 0)
            cursor.execute("""
            INSERT INTO sales_snapshots (
                shop_id, item_id, historical_sold, monthly_sold, price, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                shop_id,
                item_id,
                historical_sold,
                monthly_sold,
                product_data.get("price", 0.0),
                now
            ))
            conn.commit()

        return prod_key

    def get_cached_product(self, shop_id: str, item_id: str, max_age_hours: float = 6.0) -> Optional[Dict[str, Any]]:
        """
        Retorna os dados do produto salvos em cache caso a última atualização
        tenha ocorrido dentro da janela max_age_hours. Evita requisições externas à Shopee.
        """
        now = int(time.time())
        max_age_sec = int(max_age_hours * 3600)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM products
            WHERE shop_id = ? AND item_id = ?
            """, (str(shop_id), str(item_id)))
            row = cursor.fetchone()

            if not row:
                return None

            data = dict(row)
            updated_at = data.get("updated_at") or 0
            age_sec = now - updated_at

            if age_sec > max_age_sec:
                # Cache expirado
                return None

            # Busca também o último snapshot de vendas
            cursor.execute("""
            SELECT historical_sold, monthly_sold, timestamp
            FROM sales_snapshots
            WHERE shop_id = ? AND item_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """, (str(shop_id), str(item_id)))
            snap_row = cursor.fetchone()
            if snap_row:
                data["historical_sold"] = snap_row["historical_sold"]
                data["monthly_sold"] = snap_row["monthly_sold"]
            else:
                data["historical_sold"] = 0
                data["monthly_sold"] = 0

            data["cached"] = True
            data["cache_age_minutes"] = int(age_sec / 60)
            data["success"] = True
            return data

    def record_instagram_mention(
        self,
        post_url: str,
        shop_id: Optional[str] = None,
        item_id: Optional[str] = None,
        creator: str = "",
        caption: str = "",
        views: int = 0,
        likes: int = 0,
        comments: int = 0,
        intent_score: float = 0.0
    ):
        """Registra a menção de um produto em um post do Instagram."""
        now = int(time.time())
        shortcode = post_url.split("/")[-2] if "/reel/" in post_url or "/p/" in post_url else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO instagram_mentions (
                post_url, shortcode, creator, caption, views, likes,
                comments, intent_score, shop_id, item_id, detected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(post_url) DO UPDATE SET
                views = excluded.views,
                likes = excluded.likes,
                comments = excluded.comments,
                intent_score = excluded.intent_score,
                shop_id = coalesce(excluded.shop_id, instagram_mentions.shop_id),
                item_id = coalesce(excluded.item_id, instagram_mentions.item_id)
            """, (
                post_url, shortcode, creator, caption, views, likes,
                comments, intent_score, shop_id, item_id, now
            ))
            conn.commit()

    def get_sales_velocity(self, shop_id: str, item_id: str) -> Dict[str, Any]:
        """
        Calcula a velocidade de vendas (Delta) comparando o primeiro e o último snapshot.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT historical_sold, monthly_sold, timestamp
            FROM sales_snapshots
            WHERE shop_id = ? AND item_id = ?
            ORDER BY timestamp ASC
            """, (str(shop_id), str(item_id)))
            rows = cursor.fetchall()

        if not rows:
            return {
                "snapshots_count": 0,
                "delta_sold": 0,
                "hours_elapsed": 0.0,
                "sales_per_hour": 0.0,
                "monthly_sold": 0
            }

        first_snap = rows[0]
        last_snap = rows[-1]

        delta_sold = max(0, last_snap["historical_sold"] - first_snap["historical_sold"])
        time_diff_sec = max(1, last_snap["timestamp"] - first_snap["timestamp"])
        hours_elapsed = round(time_diff_sec / 3600.0, 2)
        sales_per_hour = round(delta_sold / max(0.1, hours_elapsed), 2) if hours_elapsed > 0 else 0.0

        return {
            "snapshots_count": len(rows),
            "delta_sold": delta_sold,
            "hours_elapsed": hours_elapsed,
            "sales_per_hour": sales_per_hour,
            "monthly_sold": last_snap["monthly_sold"] or 0
        }

    def get_top_trending_products(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Retorna o ranking de produtos com maior score comercial cruzado
        (Velocidade de vendas na Shopee + Intenção viral no Instagram).
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT p.*,
                   COUNT(DISTINCT m.id) as mentions_count,
                   MAX(m.views) as max_reel_views,
                   MAX(m.intent_score) as max_intent_score
            FROM products p
            LEFT JOIN instagram_mentions m ON p.shop_id = m.shop_id AND p.item_id = m.item_id
            GROUP BY p.id
            ORDER BY p.updated_at DESC
            LIMIT ?
            """, (limit,))
            products = [dict(row) for row in cursor.fetchall()]

        results = []
        for prod in products:
            velocity = self.get_sales_velocity(prod["shop_id"], prod["item_id"])
            prod["velocity"] = velocity

            # Score Composto de Viralidade & Vendas (0 a 100):
            # 1. Volume mensal (até 40 pts)
            monthly_pts = min(40.0, (velocity["monthly_sold"] / 1000.0) * 10.0)
            # 2. Delta / Vendas por hora (até 30 pts)
            delta_pts = min(30.0, velocity["delta_sold"] * 3.0)
            # 3. Intenção do Instagram (até 30 pts)
            ig_pts = min(30.0, (prod.get("max_intent_score") or 0.0) * 0.3)

            viral_score = round(monthly_pts + delta_pts + ig_pts, 1)
            prod["viral_score"] = viral_score
            results.append(prod)

        # Ordena pelo score decrescente
        results.sort(key=lambda x: x["viral_score"], reverse=True)
        return results

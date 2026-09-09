# ABOUTME: Places customer orders for a product.
# ABOUTME: Resolves the product before writing the order through the store.
from psycopg_pool import ConnectionPool

from app.store.orders import OrderStore, OutOfStock
from app.store.products import ProductStore


class UnknownProduct(Exception):
    pass


class OrderService:
    def __init__(self, pool: ConnectionPool) -> None:
        self.pool = pool
        self.products = ProductStore()
        self.orders = OrderStore()

    def place(self, product_id: int, quantity: int, customer: str) -> dict:
        with self.pool.connection() as conn:
            with conn.transaction():
                product = self.products.get(conn, product_id)
                if product is None:
                    raise UnknownProduct(product_id)
                order = self.orders.insert(conn, product["shop_id"], product_id, quantity, customer)
                return {**order, "product_name": product["name"]}


__all__ = ["OrderService", "UnknownProduct", "OutOfStock"]

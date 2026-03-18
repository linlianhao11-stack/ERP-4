"""v010 — 性能索引

大批量索引 + warehouses.customer_id FK + partial indexes (products category/brand)。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    indexes = [
        ("idx_stock_logs_type_date", "stock_logs", "change_type, created_at"),
        ("idx_stock_logs_product", "stock_logs", "product_id"),
        ("idx_orders_type_date", "orders", "order_type, created_at"),
        ("idx_orders_customer_date", "orders", "customer_id, created_at"),
        ("idx_order_items_order", "order_items", "order_id"),
        ("idx_order_items_product", "order_items", "product_id"),
        ("idx_payments_customer_confirmed", "payments", "customer_id, is_confirmed"),
        ("idx_sn_codes_status", "sn_codes", "status"),
        ("idx_rebate_logs_target", "rebate_logs", "target_type, target_id"),
        ("idx_shipments_order", "shipments", "order_id"),
        ("idx_warehouse_stocks_product", "warehouse_stocks", "product_id"),
        ("idx_payment_orders_payment", "payment_orders", "payment_id"),
        ("idx_payment_orders_order", "payment_orders", "order_id"),
        ("idx_customers_name", "customers", "name"),
        ("idx_suppliers_name", "suppliers", "name"),
        ("idx_products_name", "products", "name"),
        ("idx_products_sku", "products", "sku"),
        ("idx_shipments_tracking_no", "shipments", "tracking_no"),
        ("idx_operation_logs_target", "operation_logs", "target_type, target_id"),
        ("idx_operation_logs_created_at", "operation_logs", "created_at"),
        ("idx_sn_codes_warehouse_product", "sn_codes", "warehouse_id, product_id, status"),
        ("idx_stock_logs_warehouse_product", "stock_logs", "warehouse_id, product_id"),
        ("idx_purchase_orders_status", "purchase_orders", "status"),
        ("idx_purchase_orders_supplier_created", "purchase_orders", "supplier_id, created_at"),
        # --- 性能优化批次 2026-03-16 ---
        ("idx_products_is_active", "products", "is_active"),
        ("idx_customers_is_active", "customers", "is_active"),
        ("idx_suppliers_is_active", "suppliers", "is_active"),
        ("idx_orders_shipping_status", "orders", "shipping_status"),
        ("idx_warehouse_stocks_wh_product", "warehouse_stocks", "warehouse_id, product_id"),
        ("idx_vouchers_status", "vouchers", "status"),
        ("idx_shipments_status_date", "shipments", "status, created_at"),
        ("idx_operation_logs_operator_date", "operation_logs", "operator_id, created_at"),
        # --- 游标分页 + unpaid 优化索引 ---
        ("idx_orders_is_cleared", "orders", "is_cleared"),
        ("idx_orders_created_desc", "orders", "created_at DESC, id DESC"),
        ("idx_orders_updated_desc", "orders", "updated_at DESC, id DESC"),
        ("idx_stock_logs_created_desc", "stock_logs", "created_at DESC, id DESC"),
        ("idx_operation_logs_created_desc", "operation_logs", "created_at DESC, id DESC"),
        ("idx_payments_is_confirmed", "payments", "is_confirmed"),
        ("idx_orders_account_set", "orders", "account_set_id"),
        # --- 寄售页面优化索引 ---
        ("idx_orders_order_type", "orders", "order_type"),
        ("idx_stock_logs_change_ref", "stock_logs", "change_type, reference_type, reference_id"),
        ("idx_warehouse_stocks_qty", "warehouse_stocks", "quantity"),
    ]
    created = 0
    for name, table, columns in indexes:
        try:
            await conn.execute_query(
                f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})"
            )
            created += 1
        except Exception as e:
            logger.warning(f"创建索引 {name} 失败: {e}")
    if created:
        logger.info(f"性能索引检查完成: {created} 个索引已确认存在")

    # C7: warehouses.customer_id FK constraint
    try:
        await conn.execute_query(
            "ALTER TABLE warehouses ADD COLUMN IF NOT EXISTS customer_id INT REFERENCES customers(id) ON DELETE SET NULL"
        )
    except Exception as e:
        logger.warning(f"添加 warehouses.customer_id FK 失败（可忽略）: {e}")

    # M1: partial unique index for virtual warehouses per customer
    try:
        await conn.execute_query(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_warehouse_customer_virtual ON warehouses(customer_id) WHERE is_virtual = TRUE AND customer_id IS NOT NULL"
        )
    except Exception as e:
        logger.warning(f"创建 idx_warehouse_customer_virtual 失败（可忽略）: {e}")

    # M8: indexes on product.category and product.brand
    try:
        await conn.execute_query(
            "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category) WHERE category IS NOT NULL AND category != ''"
        )
    except Exception as e:
        logger.warning(f"创建 idx_products_category 失败（可忽略）: {e}")

    try:
        await conn.execute_query(
            "CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand) WHERE brand IS NOT NULL AND brand != ''"
        )
    except Exception as e:
        logger.warning(f"创建 idx_products_brand 失败（可忽略）: {e}")

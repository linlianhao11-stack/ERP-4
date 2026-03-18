"""v022 — 代采代发模块

创建 dropship_orders 表 + receivable_bills 新列 + shipped_at + 付款方式种子数据。
"""
from __future__ import annotations

from app.logger import get_logger

logger = get_logger("migrations")


async def up(conn):
    # 1. 创建 dropship_orders 表
    await conn.execute_script("""
        CREATE TABLE IF NOT EXISTS dropship_orders (
            id SERIAL PRIMARY KEY,
            ds_no VARCHAR(30) UNIQUE NOT NULL,
            account_set_id INT NOT NULL REFERENCES account_sets(id) ON DELETE RESTRICT,
            status VARCHAR(20) NOT NULL DEFAULT 'draft',

            -- 采购信息
            supplier_id INT NOT NULL REFERENCES suppliers(id) ON DELETE RESTRICT,
            product_id INT REFERENCES products(id) ON DELETE SET NULL,
            product_name VARCHAR(200) NOT NULL,
            purchase_price DECIMAL(12,2) NOT NULL,
            quantity INT NOT NULL,
            purchase_total DECIMAL(12,2) NOT NULL,
            invoice_type VARCHAR(10) NOT NULL DEFAULT 'special',
            purchase_tax_rate DECIMAL(5,2) NOT NULL DEFAULT 13,

            -- 销售信息
            customer_id INT NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
            platform_order_no VARCHAR(100) NOT NULL,
            sale_price DECIMAL(12,2) NOT NULL,
            sale_total DECIMAL(12,2) NOT NULL,
            sale_tax_rate DECIMAL(5,2) NOT NULL DEFAULT 13,
            settlement_type VARCHAR(10) NOT NULL DEFAULT 'credit',
            advance_receipt_id INT REFERENCES receipt_bills(id) ON DELETE SET NULL,

            -- 毛利
            gross_profit DECIMAL(12,2) NOT NULL DEFAULT 0,
            gross_margin DECIMAL(5,2) NOT NULL DEFAULT 0,

            -- 物流信息
            shipping_mode VARCHAR(10) NOT NULL DEFAULT 'direct',
            carrier_code VARCHAR(30),
            carrier_name VARCHAR(50),
            tracking_no VARCHAR(100),
            kd100_subscribed BOOLEAN NOT NULL DEFAULT FALSE,
            last_tracking_info TEXT,

            -- 状态管理
            urged_at TIMESTAMPTZ,
            cancel_reason VARCHAR(200),
            note TEXT,

            -- 关联财务单据
            payable_bill_id INT REFERENCES payable_bills(id) ON DELETE SET NULL,
            disbursement_bill_id INT REFERENCES disbursement_bills(id) ON DELETE SET NULL,
            receivable_bill_id INT REFERENCES receivable_bills(id) ON DELETE SET NULL,

            -- 付款信息
            payment_method VARCHAR(50),
            payment_employee_id INT REFERENCES employees(id) ON DELETE SET NULL,

            creator_id INT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_dropship_orders_account_set ON dropship_orders(account_set_id);
        CREATE INDEX IF NOT EXISTS idx_dropship_orders_supplier ON dropship_orders(supplier_id);
        CREATE INDEX IF NOT EXISTS idx_dropship_orders_customer ON dropship_orders(customer_id);
        CREATE INDEX IF NOT EXISTS idx_dropship_orders_status ON dropship_orders(status);
        CREATE INDEX IF NOT EXISTS idx_dropship_orders_created_desc ON dropship_orders(created_at DESC, id DESC);
    """)
    logger.info("代采代发: dropship_orders 表已确认存在")

    # 2. receivable_bills 表添加 platform_order_no 列
    await conn.execute_query("""
        DO $$ BEGIN
            ALTER TABLE receivable_bills ADD COLUMN platform_order_no VARCHAR(100);
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$
    """)

    # 3. receivable_bills 表添加 dropship_order_id FK 列
    await conn.execute_query("""
        DO $$ BEGIN
            ALTER TABLE receivable_bills ADD COLUMN dropship_order_id INT REFERENCES dropship_orders(id) ON DELETE SET NULL;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$
    """)

    # 4. dropship_orders 表添加 shipped_at 列
    await conn.execute_query("""
        DO $$ BEGIN
            ALTER TABLE dropship_orders ADD COLUMN shipped_at TIMESTAMPTZ;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$
    """)

    # 5. 插入 "冲减借支" 付款方式（code='employee_advance'）
    await conn.execute_query("""
        INSERT INTO disbursement_methods (code, name, sort_order, is_active)
        SELECT 'employee_advance', '冲减借支', 10, TRUE
        WHERE NOT EXISTS (
            SELECT 1 FROM disbursement_methods WHERE code = 'employee_advance'
        )
    """)

    logger.info("代采代发模块迁移完成")

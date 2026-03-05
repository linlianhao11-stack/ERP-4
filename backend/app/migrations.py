"""数据库迁移逻辑 - 初始化默认数据"""
from app.auth.password import hash_password
from tortoise import connections
from app.models import User, Warehouse, Location, PaymentMethod, DisbursementMethod
from app.logger import get_logger

logger = get_logger("migrations")


async def run_migrations():
    """初始化默认数据（幂等操作）"""
    # DDL 迁移必须在 ORM 查询之前执行（否则新字段不存在会报错）
    await migrate_user_must_change_password()
    await migrate_user_token_version()
    await migrate_order_updated_at()
    await migrate_order_item_warehouse()
    await migrate_purchase_order_payment_method()
    await migrate_purchase_return_fields()
    await migrate_shipping_flow()
    await migrate_accounting_phase1()
    await migrate_accounting_phase3()
    await migrate_accounting_phase4()
    await migrate_accounting_phase5()

    # 初始化默认收款方式
    if not await PaymentMethod.exists():
        defaults = [
            ("cash", "现金", 1),
            ("bank_public", "对公转账", 2),
            ("bank_private", "对私转账", 3),
            ("wechat", "微信", 4),
            ("alipay", "支付宝", 5),
        ]
        for code, name, sort in defaults:
            await PaymentMethod.create(code=code, name=name, sort_order=sort)
        logger.info("默认收款方式已初始化")

    # 初始化默认付款方式
    if not await DisbursementMethod.exists():
        defaults = [
            ("bank_public", "对公转账", 1),
            ("bank_private", "对私转账", 2),
            ("wechat", "微信", 3),
            ("alipay", "支付宝", 4),
            ("cash", "现金", 5),
        ]
        for code, name, sort in defaults:
            await DisbursementMethod.create(code=code, name=name, sort_order=sort)
        logger.info("默认付款方式已初始化")

    # 创建默认管理员
    admin = await User.filter(username="admin").first()
    if not admin:
        await User.create(
            username="admin",
            password_hash=hash_password("admin123"),
            display_name="系统管理员",
            role="admin",
            must_change_password=True,
            permissions=["dashboard", "sales", "stock_view", "stock_edit", "finance",
                         "logs", "admin", "purchase", "purchase_pay", "purchase_receive",
                         "purchase_approve"]
        )
        logger.info("默认管理员已创建: admin（首次登录需修改密码）")

    # 创建默认仓库
    default_wh = await Warehouse.filter(is_default=True).first()
    if not default_wh:
        default_wh = await Warehouse.create(name="默认仓库", is_default=True)
        logger.info("默认仓库已创建")

    # 迁移：仓位关联仓库
    await migrate_location_warehouse(default_wh)

    # 新增字段迁移
    await migrate_add_timestamp_columns()

    # 性能索引
    await migrate_add_indexes()

    # 供应商返利按账套隔离
    await migrate_supplier_account_balance()

    logger.info("数据库初始化完成")


async def migrate_location_warehouse(default_wh):
    """给 locations 表添加 warehouse_id 列，将现有仓位归入默认仓库（幂等）"""
    conn = connections.get("default")
    # 检查 locations 表是否已有 warehouse_id 列（PostgreSQL 兼容）
    columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'locations'"
    )
    has_warehouse_id = any(col["name"] == "warehouse_id" for col in columns)

    if not has_warehouse_id:
        wh_id = int(default_wh.id)
        logger.info("迁移: 为 locations 表添加 warehouse_id 列")
        await conn.execute_query(
            f"ALTER TABLE locations ADD COLUMN IF NOT EXISTS warehouse_id INT REFERENCES warehouses(id) DEFAULT {wh_id}"
        )
        # 将所有现有仓位归入默认仓库（参数化查询）
        await conn.execute_query(
            "UPDATE locations SET warehouse_id = $1 WHERE warehouse_id IS NULL", [wh_id]
        )
        # 移除旧的 code 唯一索引/约束（如果存在）
        try:
            await conn.execute_query("DROP INDEX IF EXISTS uid_locations_code_91776a")
        except Exception as e:
            logger.warning(f"删除旧索引失败（可忽略）: {e}")
        try:
            await conn.execute_query("ALTER TABLE locations DROP CONSTRAINT IF EXISTS locations_code_key")
        except Exception as e:
            logger.warning(f"删除旧约束失败（可忽略）: {e}")
        # 创建 (warehouse_id, code) 联合唯一索引
        try:
            await conn.execute_query(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_location_warehouse_code ON locations(warehouse_id, code)"
            )
        except Exception as e:
            logger.warning(f"创建联合唯一索引失败: {e}")
        logger.info("迁移完成: 现有仓位已归入默认仓库")
    else:
        # 确保所有仓位都有 warehouse_id
        null_count = await conn.execute_query_dict(
            "SELECT COUNT(*) as cnt FROM locations WHERE warehouse_id IS NULL"
        )
        if null_count and null_count[0]["cnt"] > 0:
            await conn.execute_query(
                "UPDATE locations SET warehouse_id = $1 WHERE warehouse_id IS NULL", [int(default_wh.id)]
            )
            logger.info(f"迁移: {null_count[0]['cnt']} 个仓位已归入默认仓库")


async def migrate_order_item_warehouse():
    """给 order_items 表添加 warehouse_id 和 location_id 列（幂等）"""
    conn = connections.get("default")
    columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'order_items'"
    )
    col_names = [col["name"] for col in columns]

    if "warehouse_id" not in col_names:
        await conn.execute_query(
            "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS warehouse_id INT REFERENCES warehouses(id) ON DELETE SET NULL"
        )
        logger.info("迁移: order_items 表添加 warehouse_id 列")

    if "location_id" not in col_names:
        await conn.execute_query(
            "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS location_id INT REFERENCES locations(id) ON DELETE SET NULL"
        )
        logger.info("迁移: order_items 表添加 location_id 列")


async def migrate_add_indexes():
    """添加性能索引（幂等）"""
    conn = connections.get("default")
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


async def migrate_purchase_order_payment_method():
    """给 purchase_orders 表添加 payment_method 列（幂等）"""
    conn = connections.get("default")
    columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'purchase_orders'"
    )
    col_names = [col["name"] for col in columns]

    if "payment_method" not in col_names:
        await conn.execute_query(
            "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS payment_method VARCHAR(50)"
        )
        logger.info("迁移: purchase_orders 表添加 payment_method 列")


async def migrate_purchase_return_fields():
    """给采购相关表添加退货字段（幂等）"""
    conn = connections.get("default")

    # purchase_orders 表
    po_columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'purchase_orders'"
    )
    po_col_names = [col["name"] for col in po_columns]

    po_new_cols = [
        ("return_tracking_no", "VARCHAR(100)"),
        ("is_refunded", "BOOLEAN DEFAULT FALSE"),
        ("return_amount", "DECIMAL(12,2) DEFAULT 0"),
        ("credit_used", "DECIMAL(12,2) DEFAULT 0"),
        ("returned_by_id", "INT REFERENCES users(id)"),
        ("returned_at", "TIMESTAMPTZ"),
    ]
    for col_name, col_type in po_new_cols:
        if col_name not in po_col_names:
            await conn.execute_query(f"ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
            logger.info(f"迁移: purchase_orders 表添加 {col_name} 列")

    # purchase_order_items 表
    poi_columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'purchase_order_items'"
    )
    poi_col_names = [col["name"] for col in poi_columns]

    if "returned_quantity" not in poi_col_names:
        await conn.execute_query("ALTER TABLE purchase_order_items ADD COLUMN IF NOT EXISTS returned_quantity INT DEFAULT 0")
        logger.info("迁移: purchase_order_items 表添加 returned_quantity 列")

    # suppliers 表
    sup_columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'suppliers'"
    )
    sup_col_names = [col["name"] for col in sup_columns]

    if "credit_balance" not in sup_col_names:
        await conn.execute_query("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS credit_balance DECIMAL(12,2) DEFAULT 0")
        logger.info("迁移: suppliers 表添加 credit_balance 列")

    # rebate_logs.type 列扩展到 20 字符（支持 credit_charge 等新类型）
    try:
        await conn.execute_query("ALTER TABLE rebate_logs ALTER COLUMN type TYPE VARCHAR(20)")
    except Exception as e:
        logger.warning(f"修改 rebate_logs.type 列类型失败（可忽略）: {e}")


async def migrate_add_timestamp_columns():
    """为缺少时间戳的表添加 updated_at / created_at 列（幂等）"""
    conn = connections.get("default")
    additions = [
        ("customers", "updated_at", "TIMESTAMPTZ DEFAULT NOW()"),
        ("suppliers", "updated_at", "TIMESTAMPTZ DEFAULT NOW()"),
        ("salespersons", "updated_at", "TIMESTAMPTZ DEFAULT NOW()"),
        ("purchase_order_items", "created_at", "TIMESTAMPTZ DEFAULT NOW()"),
        ("shipment_items", "created_at", "TIMESTAMPTZ DEFAULT NOW()"),
        ("payment_orders", "created_at", "TIMESTAMPTZ DEFAULT NOW()"),
    ]
    for table, col, col_type in additions:
        try:
            await conn.execute_query(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type}"
            )
        except Exception as e:
            logger.warning(f"添加 {table}.{col} 失败（可忽略）: {e}")


async def migrate_user_must_change_password():
    """给 users 表添加 must_change_password 列（幂等）"""
    conn = connections.get("default")
    columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'users'"
    )
    col_names = [col["name"] for col in columns]

    if "must_change_password" not in col_names:
        await conn.execute_query(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE"
        )
        logger.info("迁移: users 表添加 must_change_password 列")


async def migrate_shipping_flow():
    """发货流程重构迁移（幂等）"""
    conn = connections.get("default")

    ws_columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'warehouse_stocks'"
    )
    ws_col_names = [col["name"] for col in ws_columns]
    if "reserved_qty" not in ws_col_names:
        await conn.execute_query("ALTER TABLE warehouse_stocks ADD COLUMN IF NOT EXISTS reserved_qty INT DEFAULT 0")
        logger.info("迁移: warehouse_stocks 表添加 reserved_qty 列")

    o_columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'orders'"
    )
    o_col_names = [col["name"] for col in o_columns]
    if "shipping_status" not in o_col_names:
        await conn.execute_query(
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS shipping_status VARCHAR(20) DEFAULT 'completed'"
        )
        logger.info("迁移: orders 表添加 shipping_status 列")

    oi_columns = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'order_items'"
    )
    oi_col_names = [col["name"] for col in oi_columns]
    if "shipped_qty" not in oi_col_names:
        await conn.execute_query("ALTER TABLE order_items ADD COLUMN IF NOT EXISTS shipped_qty INT DEFAULT 0")
        await conn.execute_query("UPDATE order_items SET shipped_qty = ABS(quantity) WHERE shipped_qty = 0")
        logger.info("迁移: order_items 表添加 shipped_qty 列（历史数据已回填）")

    tables = await conn.execute_query_dict(
        "SELECT table_name as name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'shipment_items'"
    )
    if not any(t["name"] == "shipment_items" for t in tables):
        await conn.execute_query("""
            CREATE TABLE shipment_items (
                id SERIAL PRIMARY KEY,
                shipment_id INT NOT NULL REFERENCES shipments(id) ON DELETE CASCADE,
                order_item_id INT NOT NULL REFERENCES order_items(id) ON DELETE RESTRICT,
                product_id INT NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
                quantity INT NOT NULL,
                sn_codes TEXT
            )
        """)
        await conn.execute_query("CREATE INDEX IF NOT EXISTS idx_shipment_items_shipment ON shipment_items(shipment_id)")
        await conn.execute_query("CREATE INDEX IF NOT EXISTS idx_shipment_items_order_item ON shipment_items(order_item_id)")
        logger.info("迁移: 创建 shipment_items 表")


async def migrate_user_token_version():
    """给 users 表添加 token_version 列（幂等，多 worker 安全）"""
    conn = connections.get("default")
    await conn.execute_query(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INT DEFAULT 0"
    )


async def migrate_order_updated_at():
    """给 orders 表添加 updated_at 列（幂等，多 worker 安全）"""
    conn = connections.get("default")
    await conn.execute_query(
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()"
    )
    await conn.execute_query(
        "UPDATE orders SET updated_at = created_at WHERE updated_at IS NULL"
    )


async def migrate_accounting_phase1():
    """阶段1财务基础设施迁移：现有表新增字段 + 会计索引（幂等）"""
    from tortoise import Tortoise
    conn = connections.get("default")

    # ── 凭证表结构升级（旧表→新表）──
    # 检测旧版 vouchers 表（有 company_name 列 = 旧表结构）
    v_cols = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'vouchers'"
    )
    v_col_names = [c["name"] for c in v_cols]
    if "company_name" in v_col_names or ("account_set_id" not in v_col_names and v_cols):
        logger.info("迁移: 检测到旧版 vouchers 表结构，重建为新版")
        await conn.execute_query("DROP TABLE IF EXISTS voucher_entries CASCADE")
        await conn.execute_query("DROP TABLE IF EXISTS vouchers CASCADE")
        await Tortoise.generate_schemas(safe=True)
        logger.info("迁移: vouchers / voucher_entries 表已重建")

    # Warehouse: account_set_id
    wh_cols = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'warehouses'"
    )
    wh_col_names = [c["name"] for c in wh_cols]
    if "account_set_id" not in wh_col_names:
        await conn.execute_query(
            "ALTER TABLE warehouses ADD COLUMN IF NOT EXISTS account_set_id INT REFERENCES account_sets(id) ON DELETE SET NULL"
        )
        logger.info("迁移: warehouses 表添加 account_set_id 列")

    # Orders: account_set_id
    o_cols = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'orders'"
    )
    if "account_set_id" not in [c["name"] for c in o_cols]:
        await conn.execute_query(
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS account_set_id INT REFERENCES account_sets(id) ON DELETE SET NULL"
        )
        logger.info("迁移: orders 表添加 account_set_id 列")

    # PurchaseOrders: account_set_id
    po_cols = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'purchase_orders'"
    )
    if "account_set_id" not in [c["name"] for c in po_cols]:
        await conn.execute_query(
            "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS account_set_id INT REFERENCES account_sets(id) ON DELETE SET NULL"
        )
        logger.info("迁移: purchase_orders 表添加 account_set_id 列")

    # Payments: account_set_id
    pay_cols = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'payments'"
    )
    if "account_set_id" not in [c["name"] for c in pay_cols]:
        await conn.execute_query(
            "ALTER TABLE payments ADD COLUMN IF NOT EXISTS account_set_id INT REFERENCES account_sets(id) ON DELETE SET NULL"
        )
        logger.info("迁移: payments 表添加 account_set_id 列")

    # Products: tax_rate
    prod_cols = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'products'"
    )
    if "tax_rate" not in [c["name"] for c in prod_cols]:
        await conn.execute_query(
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS tax_rate DECIMAL(5,2) DEFAULT 13.00"
        )
        logger.info("迁移: products 表添加 tax_rate 列")

    # 会计相关索引
    accounting_indexes = [
        ("idx_chart_of_accounts_set_code", "chart_of_accounts", "account_set_id, code"),
        ("idx_accounting_periods_set_name", "accounting_periods", "account_set_id, period_name"),
        ("idx_vouchers_set_period", "vouchers", "account_set_id, period_name"),
        ("idx_vouchers_set_type_no", "vouchers", "account_set_id, voucher_type, voucher_no"),
        ("idx_voucher_entries_voucher", "voucher_entries", "voucher_id"),
        ("idx_voucher_entries_account", "voucher_entries", "account_id"),
        ("idx_orders_account_set", "orders", "account_set_id"),
        ("idx_purchase_orders_account_set", "purchase_orders", "account_set_id"),
        ("idx_payments_account_set", "payments", "account_set_id"),
        ("idx_warehouses_account_set", "warehouses", "account_set_id"),
    ]
    for name, table, columns in accounting_indexes:
        try:
            await conn.execute_query(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})")
        except Exception as e:
            logger.warning(f"创建索引 {name} 失败（可忽略）: {e}")

    # 更新默认管理员的权限列表（添加会计权限）
    try:
        admin = await User.filter(username="admin", role="admin").first()
        if admin:
            existing_perms = admin.permissions or []
            new_perms = ["accounting_view", "accounting_edit", "accounting_approve", "accounting_post", "period_end"]
            added = [p for p in new_perms if p not in existing_perms]
            if added:
                admin.permissions = existing_perms + added
                await admin.save()
                logger.info(f"管理员权限已更新，添加: {added}")
    except Exception as e:
        logger.warning(f"更新管理员权限失败（可忽略）: {e}")

    logger.info("阶段1财务迁移完成")


async def migrate_accounting_phase3():
    """阶段3应收应付迁移：7张新表 + 索引 + AR/AP权限（幂等）"""
    from tortoise import Tortoise
    await Tortoise.generate_schemas(safe=True)

    conn = connections.get("default")

    # AR/AP 索引
    ar_ap_indexes = [
        ("idx_receivable_bills_set_customer", "receivable_bills", "account_set_id, customer_id"),
        ("idx_receivable_bills_set_status", "receivable_bills", "account_set_id, status"),
        ("idx_receipt_bills_customer", "receipt_bills", "customer_id"),
        ("idx_receipt_bills_receivable", "receipt_bills", "receivable_bill_id"),
        ("idx_receipt_refund_bills_original", "receipt_refund_bills", "original_receipt_id"),
        ("idx_receivable_write_offs_receivable", "receivable_write_offs", "receivable_bill_id"),
        ("idx_payable_bills_set_supplier", "payable_bills", "account_set_id, supplier_id"),
        ("idx_payable_bills_set_status", "payable_bills", "account_set_id, status"),
        ("idx_disbursement_bills_payable", "disbursement_bills", "payable_bill_id"),
        ("idx_disbursement_refund_bills_original", "disbursement_refund_bills", "original_disbursement_id"),
    ]
    for name, table, columns in ar_ap_indexes:
        try:
            await conn.execute_query(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})")
        except Exception as e:
            logger.warning(f"创建索引 {name} 失败（可忽略）: {e}")

    # 为 admin 用户添加 AR/AP 权限
    new_perms = [
        "accounting_ar_view", "accounting_ar_edit", "accounting_ar_confirm",
        "accounting_ap_view", "accounting_ap_edit", "accounting_ap_confirm",
    ]
    admin = await User.filter(username="admin").first()
    if admin:
        current = admin.permissions or []
        added = [p for p in new_perms if p not in current]
        if added:
            admin.permissions = current + added
            await admin.save()
            logger.info(f"admin 用户新增 AR/AP 权限: {added}")

    logger.info("阶段3应收应付迁移完成")


async def migrate_accounting_phase4():
    """阶段4迁移：出入库单+发票 6表 + 索引 + 科目补充"""
    conn = connections.get("default")
    from tortoise import Tortoise
    await Tortoise.generate_schemas(safe=True)

    indexes = [
        ("idx_sdb_account_customer", "sales_delivery_bills", "account_set_id, customer_id"),
        ("idx_sdb_order", "sales_delivery_bills", "order_id"),
        ("idx_sdi_bill", "sales_delivery_items", "delivery_bill_id"),
        ("idx_prb_account_supplier", "purchase_receipt_bills", "account_set_id, supplier_id"),
        ("idx_prb_po", "purchase_receipt_bills", "purchase_order_id"),
        ("idx_pri_bill", "purchase_receipt_items", "receipt_bill_id"),
        ("idx_inv_account_direction", "invoices", "account_set_id, direction"),
        ("idx_inv_account_status", "invoices", "account_set_id, status"),
        ("idx_inv_receivable", "invoices", "receivable_bill_id"),
        ("idx_inv_payable", "invoices", "payable_bill_id"),
        ("idx_inv_items_invoice", "invoice_items", "invoice_id"),
    ]
    for idx_name, table, columns in indexes:
        try:
            await conn.execute_query(
                f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({columns})"
            )
        except Exception:
            pass

    try:
        from app.models.accounting import AccountSet, ChartOfAccount
        account_sets = await AccountSet.all()
        for a in account_sets:
            exists = await ChartOfAccount.filter(account_set_id=a.id, code="1407").exists()
            if not exists:
                await ChartOfAccount.create(
                    account_set_id=a.id, code="1407", name="发出商品",
                    level=1, category="asset", direction="debit", is_leaf=True
                )
    except Exception:
        pass

    logger.info("阶段4迁移完成：出入库单+发票表 + 索引 + 1407科目")


async def migrate_accounting_phase5():
    """阶段5迁移：确保 period_end 权限（幂等）"""
    admin = await User.filter(username="admin").first()
    if admin:
        current = admin.permissions or []
        # period_end 权限应该在 phase1 已添加，这里只是确认
        if "period_end" not in current:
            admin.permissions = current + ["period_end"]
            await admin.save()
            logger.info("admin 用户补充 period_end 权限")
    logger.info("阶段5迁移完成")


async def migrate_supplier_account_balance():
    """供应商返利按账套隔离迁移：新表 + RebateLog 新列 + 数据迁移 + 预置科目（幂等）"""
    from tortoise import Tortoise
    await Tortoise.generate_schemas(safe=True)

    conn = connections.get("default")

    # RebateLog 增加 account_set_id 列
    rl_cols = await conn.execute_query_dict(
        "SELECT column_name as name FROM information_schema.columns WHERE table_name = 'rebate_logs'"
    )
    if "account_set_id" not in [c["name"] for c in rl_cols]:
        await conn.execute_query(
            "ALTER TABLE rebate_logs ADD COLUMN IF NOT EXISTS account_set_id INT REFERENCES account_sets(id) ON DELETE SET NULL"
        )
        logger.info("迁移: rebate_logs 表添加 account_set_id 列")

    # 索引
    sab_indexes = [
        ("idx_supplier_account_balances_supplier", "supplier_account_balances", "supplier_id"),
        ("idx_supplier_account_balances_account_set", "supplier_account_balances", "account_set_id"),
        ("idx_rebate_logs_account_set", "rebate_logs", "account_set_id"),
    ]
    for name, table, columns in sab_indexes:
        try:
            await conn.execute_query(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})")
        except Exception as e:
            logger.warning(f"创建索引 {name} 失败（可忽略）: {e}")

    # 迁移现有余额数据到第一个活跃账套
    from app.models.accounting import AccountSet, ChartOfAccount
    from app.models.supplier_balance import SupplierAccountBalance

    first_set = await AccountSet.filter(is_active=True).order_by("id").first()
    if first_set:
        # 查找有非零余额的供应商
        rows = await conn.execute_query_dict(
            "SELECT id, name, rebate_balance, credit_balance FROM suppliers "
            "WHERE (rebate_balance > 0 OR credit_balance > 0)"
        )
        for row in rows:
            result = await conn.execute_query(
                "INSERT INTO supplier_account_balances (supplier_id, account_set_id, rebate_balance, credit_balance) "
                "VALUES ($1, $2, $3, $4) ON CONFLICT (supplier_id, account_set_id) DO NOTHING",
                [row["id"], first_set.id, row["rebate_balance"], row["credit_balance"]]
            )
            if result[0] > 0:
                logger.info(f"迁移: 供应商 {row['name']} 余额已迁移到账套 {first_set.name}")

    # 确保凭证所需科目存在（ON CONFLICT 防竞态）
    for aset in await AccountSet.all():
        try:
            result = await conn.execute_query(
                "INSERT INTO chart_of_accounts (account_set_id, code, name, level, category, direction, is_leaf) "
                "VALUES ($1, '5401', '主营业务成本', 1, 'cost', 'debit', TRUE) "
                "ON CONFLICT (account_set_id, code) DO NOTHING",
                [aset.id]
            )
            if result[0] > 0:
                logger.info(f"账套 {aset.name} 创建科目 5401 主营业务成本")
        except Exception as e:
            logger.warning(f"创建科目 5401 失败（可忽略）: {e}")
        try:
            result = await conn.execute_query(
                "INSERT INTO chart_of_accounts (account_set_id, code, name, level, category, direction, is_leaf) "
                "VALUES ($1, '2221', '应交税费', 1, 'liability', 'credit', TRUE) "
                "ON CONFLICT (account_set_id, code) DO NOTHING",
                [aset.id]
            )
            if result[0] > 0:
                logger.info(f"账套 {aset.name} 创建科目 2221 应交税费")
        except Exception as e:
            logger.warning(f"创建科目 2221 失败（可忽略）: {e}")

    logger.info("供应商返利账套隔离迁移完成")

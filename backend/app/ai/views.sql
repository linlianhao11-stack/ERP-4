-- ERP AI 语义视图 — 由 erp 主用户创建，erp_ai_readonly 只读访问

-- 1. 销售明细宽表
CREATE OR REPLACE VIEW vw_sales_detail AS
SELECT
    o.order_no,
    o.created_at::date AS order_date,
    o.order_type,
    c.name AS customer_name,
    s.name AS salesperson_name,
    p.sku,
    p.name AS product_name,
    p.brand,
    p.category,
    oi.quantity,
    oi.unit_price,
    ROUND((oi.quantity * oi.unit_price)::numeric, 2) AS amount,
    ROUND((oi.quantity * COALESCE(oi.cost_price, 0))::numeric, 2) AS cost,
    ROUND((oi.quantity * (oi.unit_price - COALESCE(oi.cost_price, 0)))::numeric, 2) AS profit,
    ROUND(
        CASE WHEN oi.unit_price > 0
             THEN ((oi.unit_price - COALESCE(oi.cost_price, 0)) / oi.unit_price * 100)::numeric
             ELSE 0 END,
        2
    ) AS profit_rate,
    ast.name AS account_set_name
FROM orders o
JOIN order_items oi ON oi.order_id = o.id
JOIN products p ON p.id = oi.product_id
LEFT JOIN customers c ON c.id = o.customer_id
LEFT JOIN salespersons s ON s.id = o.salesperson_id
LEFT JOIN account_sets ast ON ast.id = o.account_set_id
WHERE o.shipping_status != 'cancelled'
  AND o.order_type != 'return';

-- 2. 销售按月汇总
CREATE OR REPLACE VIEW vw_sales_summary AS
SELECT
    TO_CHAR(o.created_at, 'YYYY-MM') AS year_month,
    COUNT(DISTINCT o.id) AS order_count,
    ROUND(SUM(oi.quantity * oi.unit_price)::numeric, 2) AS total_amount,
    ROUND(SUM(oi.quantity * COALESCE(oi.cost_price, 0))::numeric, 2) AS total_cost,
    ROUND(SUM(oi.quantity * (oi.unit_price - COALESCE(oi.cost_price, 0)))::numeric, 2) AS total_profit,
    ROUND(
        CASE WHEN SUM(oi.quantity * oi.unit_price) > 0
             THEN (SUM(oi.quantity * (oi.unit_price - COALESCE(oi.cost_price, 0)))
                   / NULLIF(SUM(oi.quantity * oi.unit_price), 0) * 100)::numeric
             ELSE 0 END,
        2
    ) AS profit_rate,
    COUNT(DISTINCT o.customer_id) AS customer_count,
    ast.name AS account_set_name
FROM orders o
JOIN order_items oi ON oi.order_id = o.id
LEFT JOIN account_sets ast ON ast.id = o.account_set_id
WHERE o.shipping_status != 'cancelled'
  AND o.order_type != 'return'
GROUP BY TO_CHAR(o.created_at, 'YYYY-MM'), ast.name;

-- 3. 采购明细宽表
CREATE OR REPLACE VIEW vw_purchase_detail AS
SELECT
    po.po_no,
    po.created_at::date AS purchase_date,
    sup.name AS supplier_name,
    p.sku,
    p.name AS product_name,
    p.brand,
    poi.quantity,
    poi.tax_inclusive_price,
    poi.tax_exclusive_price,
    ROUND((poi.quantity * poi.tax_inclusive_price)::numeric, 2) AS amount,
    po.status,
    ast.name AS account_set_name
FROM purchase_orders po
JOIN purchase_order_items poi ON poi.purchase_order_id = po.id
JOIN products p ON p.id = poi.product_id
LEFT JOIN suppliers sup ON sup.id = po.supplier_id
LEFT JOIN account_sets ast ON ast.id = po.account_set_id
WHERE po.status != 'cancelled';

-- 4. 当前库存状态
CREATE OR REPLACE VIEW vw_inventory_status AS
SELECT
    p.sku,
    p.name AS product_name,
    p.brand,
    w.name AS warehouse_name,
    COALESCE(loc.name, loc.code, '') AS location_name,
    ws.quantity,
    COALESCE(ws.reserved_qty, 0) AS reserved_qty,
    ws.quantity - COALESCE(ws.reserved_qty, 0) AS available_qty,
    ROUND(COALESCE(p.cost_price, 0)::numeric, 2) AS avg_cost,
    ROUND((ws.quantity * COALESCE(p.cost_price, 0))::numeric, 2) AS stock_value
FROM warehouse_stocks ws
JOIN products p ON p.id = ws.product_id
JOIN warehouses w ON w.id = ws.warehouse_id
LEFT JOIN locations loc ON loc.id = ws.location_id
WHERE ws.quantity >= 0
  AND w.is_virtual = false;

-- 5. 库存周转分析
CREATE OR REPLACE VIEW vw_inventory_turnover AS
SELECT
    p.sku,
    p.name AS product_name,
    p.brand,
    COALESCE(SUM(ws.quantity), 0) AS current_stock,
    COALESCE(sold_30.qty, 0) AS sold_30d,
    COALESCE(sold_90.qty, 0) AS sold_90d,
    CASE WHEN COALESCE(SUM(ws.quantity), 0) > 0
         THEN ROUND((COALESCE(sold_30.qty, 0)::numeric / NULLIF(SUM(ws.quantity), 0)), 2)
         ELSE 0 END AS turnover_rate
FROM products p
LEFT JOIN warehouse_stocks ws ON ws.product_id = p.id
LEFT JOIN (
    SELECT oi.product_id, SUM(oi.quantity) AS qty
    FROM order_items oi
    JOIN orders o ON o.id = oi.order_id
    WHERE o.created_at >= CURRENT_DATE - INTERVAL '30 days'
      AND o.shipping_status != 'cancelled' AND o.order_type != 'return'
    GROUP BY oi.product_id
) sold_30 ON sold_30.product_id = p.id
LEFT JOIN (
    SELECT oi.product_id, SUM(oi.quantity) AS qty
    FROM order_items oi
    JOIN orders o ON o.id = oi.order_id
    WHERE o.created_at >= CURRENT_DATE - INTERVAL '90 days'
      AND o.shipping_status != 'cancelled' AND o.order_type != 'return'
    GROUP BY oi.product_id
) sold_90 ON sold_90.product_id = p.id
GROUP BY p.id, p.sku, p.name, p.brand, sold_30.qty, sold_90.qty;

-- 6. 应收账款
CREATE OR REPLACE VIEW vw_receivables AS
SELECT
    rb.bill_no,
    c.name AS customer_name,
    rb.bill_date,
    rb.total_amount,
    rb.received_amount,
    rb.unreceived_amount,
    rb.status,
    (CURRENT_DATE - rb.bill_date) AS age_days,
    ast.name AS account_set_name
FROM receivable_bills rb
LEFT JOIN customers c ON c.id = rb.customer_id
LEFT JOIN account_sets ast ON ast.id = rb.account_set_id;

-- 7. 应付账款
CREATE OR REPLACE VIEW vw_payables AS
SELECT
    pb.bill_no,
    sup.name AS supplier_name,
    pb.bill_date,
    pb.total_amount,
    pb.paid_amount,
    pb.unpaid_amount,
    pb.status,
    (CURRENT_DATE - pb.bill_date) AS age_days,
    ast.name AS account_set_name
FROM payable_bills pb
LEFT JOIN suppliers sup ON sup.id = pb.supplier_id
LEFT JOIN account_sets ast ON ast.id = pb.account_set_id;

-- 授权只读用户 — 语义视图
GRANT SELECT ON vw_sales_detail TO erp_ai_readonly;
GRANT SELECT ON vw_sales_summary TO erp_ai_readonly;
GRANT SELECT ON vw_purchase_detail TO erp_ai_readonly;
GRANT SELECT ON vw_inventory_status TO erp_ai_readonly;
GRANT SELECT ON vw_inventory_turnover TO erp_ai_readonly;
GRANT SELECT ON vw_receivables TO erp_ai_readonly;
GRANT SELECT ON vw_payables TO erp_ai_readonly;

-- 授权只读用户 — 基础参考表
GRANT SELECT ON warehouses TO erp_ai_readonly;
GRANT SELECT ON products TO erp_ai_readonly;
GRANT SELECT ON customers TO erp_ai_readonly;
GRANT SELECT ON suppliers TO erp_ai_readonly;
GRANT SELECT ON account_sets TO erp_ai_readonly;

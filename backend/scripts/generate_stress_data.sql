-- =============================================================
-- ERP-4 压力测试数据生成脚本
-- 目标: ~100万条记录 (跨主要业务表)
-- 用法: docker exec -i erp-4-db-1 psql -U erp -d erp < scripts/generate_stress_data.sql
-- =============================================================

BEGIN;

-- 标记: 测试数据起始ID边界 (用于清除)
-- 先记住各表当前最大 ID
CREATE TEMP TABLE _boundary AS
SELECT 'products' AS t, COALESCE(MAX(id),0) AS max_id FROM products
UNION ALL SELECT 'customers', COALESCE(MAX(id),0) FROM customers
UNION ALL SELECT 'suppliers', COALESCE(MAX(id),0) FROM suppliers
UNION ALL SELECT 'orders', COALESCE(MAX(id),0) FROM orders
UNION ALL SELECT 'order_items', COALESCE(MAX(id),0) FROM order_items
UNION ALL SELECT 'stock_logs', COALESCE(MAX(id),0) FROM stock_logs
UNION ALL SELECT 'payments', COALESCE(MAX(id),0) FROM payments
UNION ALL SELECT 'shipments', COALESCE(MAX(id),0) FROM shipments
UNION ALL SELECT 'shipment_items', COALESCE(MAX(id),0) FROM shipment_items
UNION ALL SELECT 'purchase_orders', COALESCE(MAX(id),0) FROM purchase_orders
UNION ALL SELECT 'purchase_order_items', COALESCE(MAX(id),0) FROM purchase_order_items
UNION ALL SELECT 'operation_logs', COALESCE(MAX(id),0) FROM operation_logs;

-- 将边界写入持久表（供清除脚本使用）
DROP TABLE IF EXISTS _stress_test_boundary;
CREATE TABLE _stress_test_boundary AS SELECT * FROM _boundary;

\echo '>>> 阶段 1/7: 生成商品 (5000 条)'
INSERT INTO products (sku, name, brand, category, retail_price, cost_price, unit, tax_rate, is_active, created_at, updated_at)
SELECT
  'ST-' || LPAD(i::text, 6, '0'),
  '压测商品-' || (ARRAY['手机壳','数据线','充电器','耳机','保护膜','支架','转接头','移动电源','鼠标','键盘'])[1 + (i % 10)] || '-' || i,
  (ARRAY['品牌A','品牌B','品牌C','品牌D','品牌E'])[1 + (i % 5)],
  (ARRAY['配件','数码','办公','生活','工具'])[1 + (i % 5)],
  ROUND((10 + random() * 990)::numeric, 2),
  ROUND((5 + random() * 500)::numeric, 2),
  (ARRAY['个','条','件','套','台'])[1 + (i % 5)],
  13.00,
  TRUE,
  NOW() - (random() * INTERVAL '365 days'),
  NOW()
FROM generate_series(1, 5000) AS i;

\echo '>>> 阶段 2/7: 生成客户 (2000) + 供应商 (500)'
INSERT INTO customers (name, contact_person, phone, address, balance, rebate_balance, is_active, invoice_address, invoice_phone, created_at, updated_at)
SELECT
  '压测客户-' || (ARRAY['科技','贸易','电子','实业','商贸'])[1 + (i % 5)] || i || '号',
  '联系人' || i,
  '1' || (30 + (i % 70))::text || LPAD((i % 100000000)::text, 8, '0'),
  '广东省深圳市南山区' || i || '号',
  ROUND((random() * 50000)::numeric, 2),
  ROUND((random() * 5000)::numeric, 2),
  TRUE, '', '',
  NOW() - (random() * INTERVAL '365 days'),
  NOW()
FROM generate_series(1, 2000) AS i;

INSERT INTO suppliers (name, contact_person, phone, address, rebate_balance, credit_balance, is_active, created_at, updated_at)
SELECT
  '压测供应商-' || (ARRAY['电子','科技','制造','工业','材料'])[1 + (i % 5)] || i || '厂',
  '供应联系人' || i,
  '1' || (50 + (i % 50))::text || LPAD((i % 100000000)::text, 8, '0'),
  '广东省东莞市' || i || '号',
  ROUND((random() * 10000)::numeric, 2),
  ROUND((random() * 5000)::numeric, 2),
  TRUE,
  NOW() - (random() * INTERVAL '365 days'),
  NOW()
FROM generate_series(1, 500) AS i;

-- 获取有效仓库和用户ID
\echo '>>> 阶段 3/7: 生成销售订单 (100000) + 订单明细 (~300000)'

-- 先获取有效的 warehouse_id 列表 和 user_id
DO $$
DECLARE
  wh_ids INT[];
  user_id INT;
  cust_min INT;
  cust_max INT;
  prod_min INT;
  prod_max INT;
  batch_size INT := 10000;
  total_orders INT := 100000;
  i INT;
  j INT;
  batch_start INT;
  batch_end INT;
  order_types TEXT[] := ARRAY['CASH','CREDIT','CONSIGN_OUT','RETURN','CASH','CASH','CREDIT','CASH'];
  ship_statuses TEXT[] := ARRAY['pending','shipped','completed','completed','completed','completed'];
BEGIN
  SELECT ARRAY_AGG(id) INTO wh_ids FROM warehouses WHERE NOT is_virtual AND is_active LIMIT 5;
  SELECT id INTO user_id FROM users LIMIT 1;
  SELECT MIN(id), MAX(id) INTO cust_min, cust_max FROM customers WHERE is_active;
  SELECT MIN(id), MAX(id) INTO prod_min, prod_max FROM products WHERE is_active;

  -- 分批插入订单
  FOR batch_start IN 1..total_orders BY batch_size LOOP
    batch_end := LEAST(batch_start + batch_size - 1, total_orders);

    INSERT INTO orders (
      order_no, order_type, customer_id, warehouse_id,
      total_amount, total_cost, total_profit, paid_amount,
      is_cleared, shipping_status, creator_id, remark,
      created_at, updated_at
    )
    SELECT
      'ST-SO-' || LPAD(n::text, 7, '0'),
      order_types[1 + (n % 8)],
      cust_min + (n % (cust_max - cust_min + 1)),
      wh_ids[1 + (n % array_length(wh_ids, 1))],
      ROUND((50 + random() * 9950)::numeric, 2),
      ROUND((30 + random() * 5000)::numeric, 2),
      ROUND((10 + random() * 3000)::numeric, 2),
      CASE WHEN random() > 0.3 THEN ROUND((50 + random() * 9950)::numeric, 2) ELSE 0 END,
      random() > 0.4,
      ship_statuses[1 + (n % 6)],
      user_id,
      CASE WHEN random() > 0.7 THEN '压测备注' || n ELSE NULL END,
      NOW() - ((random() * 365)::int || ' days')::INTERVAL - ((random() * 86400)::int || ' seconds')::INTERVAL,
      NOW()
    FROM generate_series(batch_start, batch_end) AS n;

    RAISE NOTICE '订单批次 %-%  已插入', batch_start, batch_end;
  END LOOP;

  -- 插入订单明细 (每单 1-5 个商品, 平均 3 个)
  RAISE NOTICE '开始插入订单明细...';

  INSERT INTO order_items (
    order_id, product_id, warehouse_id, quantity, unit_price, cost_price, amount, profit, shipped_qty
  )
  SELECT
    o.id,
    prod_min + ((o.id * item_seq + item_seq * 7) % (prod_max - prod_min + 1)),
    o.warehouse_id,
    1 + (o.id * item_seq % 10),
    ROUND((10 + (o.id * item_seq % 500))::numeric, 2),
    ROUND((5 + (o.id * item_seq % 300))::numeric, 2),
    ROUND(((1 + (o.id * item_seq % 10)) * (10 + (o.id * item_seq % 500)))::numeric, 2),
    ROUND(((1 + (o.id * item_seq % 10)) * ((o.id * item_seq % 200)))::numeric, 2),
    CASE WHEN o.shipping_status = 'completed' THEN 1 + (o.id * item_seq % 10) ELSE 0 END
  FROM orders o
  CROSS JOIN generate_series(1, 3) AS item_seq
  WHERE o.order_no LIKE 'ST-SO-%';

  RAISE NOTICE '订单明细插入完成';
END $$;

\echo '>>> 阶段 4/7: 生成采购订单 (20000) + 采购明细 (~60000)'

DO $$
DECLARE
  wh_ids INT[];
  user_id INT;
  supp_min INT;
  supp_max INT;
  prod_min INT;
  prod_max INT;
  po_statuses TEXT[] := ARRAY['pending_review','pending','paid','completed','completed','completed','completed'];
BEGIN
  SELECT ARRAY_AGG(id) INTO wh_ids FROM warehouses WHERE NOT is_virtual AND is_active LIMIT 5;
  SELECT id INTO user_id FROM users LIMIT 1;
  SELECT MIN(id), MAX(id) INTO supp_min, supp_max FROM suppliers WHERE is_active;
  SELECT MIN(id), MAX(id) INTO prod_min, prod_max FROM products WHERE is_active;

  INSERT INTO purchase_orders (
    po_no, supplier_id, status, total_amount,
    target_warehouse_id, creator_id, remark,
    created_at, updated_at
  )
  SELECT
    'ST-PO-' || LPAD(n::text, 6, '0'),
    supp_min + (n % (supp_max - supp_min + 1)),
    po_statuses[1 + (n % 7)],
    ROUND((100 + random() * 50000)::numeric, 2),
    wh_ids[1 + (n % array_length(wh_ids, 1))],
    user_id,
    CASE WHEN random() > 0.8 THEN '采购备注' || n ELSE NULL END,
    NOW() - ((random() * 365)::int || ' days')::INTERVAL,
    NOW()
  FROM generate_series(1, 20000) AS n;

  -- 采购明细 (每单 3 个)
  INSERT INTO purchase_order_items (
    purchase_order_id, product_id, quantity,
    tax_inclusive_price, tax_rate, tax_exclusive_price, amount,
    received_quantity, created_at
  )
  SELECT
    po.id,
    prod_min + ((po.id * item_seq + item_seq * 13) % (prod_max - prod_min + 1)),
    5 + (po.id * item_seq % 50),
    ROUND((10 + (po.id * item_seq % 800))::numeric, 2),
    0.13,
    ROUND(((10 + (po.id * item_seq % 800)) / 1.13)::numeric, 2),
    ROUND(((5 + (po.id * item_seq % 50)) * (10 + (po.id * item_seq % 800)))::numeric, 2),
    CASE WHEN po.status IN ('completed','paid') THEN 5 + (po.id * item_seq % 50) ELSE 0 END,
    po.created_at
  FROM purchase_orders po
  CROSS JOIN generate_series(1, 3) AS item_seq
  WHERE po.po_no LIKE 'ST-PO-%';

  RAISE NOTICE '采购订单和明细插入完成';
END $$;

\echo '>>> 阶段 5/7: 生成库存日志 (200000)'

DO $$
DECLARE
  wh_ids INT[];
  user_id INT;
  prod_min INT;
  prod_max INT;
  change_types TEXT[] := ARRAY['RESTOCK','SALE','RETURN','CONSIGN_OUT','PURCHASE_IN','ADJUST','SALE','SALE','PURCHASE_IN','RESTOCK'];
BEGIN
  SELECT ARRAY_AGG(id) INTO wh_ids FROM warehouses WHERE NOT is_virtual AND is_active LIMIT 5;
  SELECT id INTO user_id FROM users LIMIT 1;
  SELECT MIN(id), MAX(id) INTO prod_min, prod_max FROM products WHERE is_active;

  INSERT INTO stock_logs (
    product_id, warehouse_id, change_type,
    quantity, before_qty, after_qty,
    reference_type, remark, creator_id, created_at
  )
  SELECT
    prod_min + (n % (prod_max - prod_min + 1)),
    wh_ids[1 + (n % array_length(wh_ids, 1))],
    change_types[1 + (n % 10)],
    CASE WHEN change_types[1 + (n % 10)] IN ('SALE','CONSIGN_OUT') THEN -(1 + n % 20) ELSE 1 + n % 50 END,
    50 + (n % 200),
    50 + (n % 200) + CASE WHEN change_types[1 + (n % 10)] IN ('SALE','CONSIGN_OUT') THEN -(1 + n % 20) ELSE 1 + n % 50 END,
    'stress_test',
    NULL,
    user_id,
    NOW() - ((random() * 365)::int || ' days')::INTERVAL - ((random() * 86400)::int || ' seconds')::INTERVAL
  FROM generate_series(1, 200000) AS n;

  RAISE NOTICE '库存日志插入完成';
END $$;

\echo '>>> 阶段 6/7: 生成收款记录 (50000) + 发货单 (80000)'

DO $$
DECLARE
  user_id INT;
  cust_min INT;
  cust_max INT;
  order_min INT;
  order_max INT;
  pay_methods TEXT[] := ARRAY['cash','wechat','alipay','bank_transfer','cash','wechat'];
BEGIN
  SELECT id INTO user_id FROM users LIMIT 1;
  SELECT MIN(id), MAX(id) INTO cust_min, cust_max FROM customers WHERE is_active;
  SELECT MIN(id), MAX(id) INTO order_min, order_max FROM orders WHERE order_no LIKE 'ST-SO-%';

  -- 收款记录
  INSERT INTO payments (
    payment_no, customer_id, order_id, amount,
    payment_method, source, is_confirmed, creator_id, created_at
  )
  SELECT
    'ST-PAY-' || LPAD(n::text, 6, '0'),
    cust_min + (n % (cust_max - cust_min + 1)),
    order_min + (n % (order_max - order_min + 1)),
    ROUND((50 + random() * 5000)::numeric, 2),
    pay_methods[1 + (n % 6)],
    CASE WHEN random() > 0.5 THEN 'CASH' ELSE 'CREDIT' END,
    random() > 0.2,
    user_id,
    NOW() - ((random() * 365)::int || ' days')::INTERVAL
  FROM generate_series(1, 50000) AS n;

  RAISE NOTICE '收款记录插入完成';

  -- 发货单
  INSERT INTO shipments (
    shipment_no, order_id, carrier_code, carrier_name, tracking_no,
    status, status_text, created_at, updated_at
  )
  SELECT
    'ST-SHP-' || LPAD(n::text, 7, '0'),
    order_min + (n % (order_max - order_min + 1)),
    (ARRAY['SF','YTO','ZTO','STO','YD'])[1 + (n % 5)],
    (ARRAY['顺丰','圆通','中通','申通','韵达'])[1 + (n % 5)],
    'ST' || LPAD(n::text, 12, '0'),
    CASE WHEN random() > 0.3 THEN 'completed' ELSE 'shipped' END,
    CASE WHEN random() > 0.3 THEN '已签收' ELSE '运输中' END,
    NOW() - ((random() * 365)::int || ' days')::INTERVAL,
    NOW()
  FROM generate_series(1, 80000) AS n;

  RAISE NOTICE '发货单插入完成';
END $$;

\echo '>>> 阶段 7/7: 生成操作日志 (200000)'

DO $$
DECLARE
  user_id INT;
  actions TEXT[] := ARRAY['create_order','update_order','create_payment','confirm_payment','create_shipment','update_stock','create_purchase','approve_purchase'];
  targets TEXT[] := ARRAY['order','payment','shipment','stock','purchase_order','customer','product','warehouse'];
BEGIN
  SELECT id INTO user_id FROM users LIMIT 1;

  INSERT INTO operation_logs (
    action, target_type, target_id, detail, operator_id, created_at
  )
  SELECT
    actions[1 + (n % 8)],
    targets[1 + (n % 8)],
    1 + (n % 50000),
    NULL,
    user_id,
    NOW() - ((random() * 365)::int || ' days')::INTERVAL - ((random() * 86400)::int || ' seconds')::INTERVAL
  FROM generate_series(1, 200000) AS n;

  RAISE NOTICE '操作日志插入完成';
END $$;

COMMIT;

-- 最终统计
\echo ''
\echo '=== 压力测试数据生成完成 ==='
SELECT t AS "表名", count AS "总记录数" FROM (
  SELECT 'products' AS t, count(*) FROM products
  UNION ALL SELECT 'customers', count(*) FROM customers
  UNION ALL SELECT 'suppliers', count(*) FROM suppliers
  UNION ALL SELECT 'orders', count(*) FROM orders
  UNION ALL SELECT 'order_items', count(*) FROM order_items
  UNION ALL SELECT 'purchase_orders', count(*) FROM purchase_orders
  UNION ALL SELECT 'purchase_order_items', count(*) FROM purchase_order_items
  UNION ALL SELECT 'stock_logs', count(*) FROM stock_logs
  UNION ALL SELECT 'payments', count(*) FROM payments
  UNION ALL SELECT 'shipments', count(*) FROM shipments
  UNION ALL SELECT 'operation_logs', count(*) FROM operation_logs
) sub ORDER BY t;

SELECT '总计' AS "汇总", SUM(c) AS "总记录数" FROM (
  SELECT count(*) AS c FROM products
  UNION ALL SELECT count(*) FROM customers
  UNION ALL SELECT count(*) FROM suppliers
  UNION ALL SELECT count(*) FROM orders
  UNION ALL SELECT count(*) FROM order_items
  UNION ALL SELECT count(*) FROM purchase_orders
  UNION ALL SELECT count(*) FROM purchase_order_items
  UNION ALL SELECT count(*) FROM stock_logs
  UNION ALL SELECT count(*) FROM payments
  UNION ALL SELECT count(*) FROM shipments
  UNION ALL SELECT count(*) FROM operation_logs
) sub;

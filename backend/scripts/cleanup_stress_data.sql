-- =============================================================
-- ERP-4 压力测试数据清除脚本
-- 根据 _stress_test_boundary 表记录的边界ID删除测试数据
-- 用法: docker exec -i erp-4-db-1 psql -U erp -d erp < scripts/cleanup_stress_data.sql
-- =============================================================

-- 检查边界表是否存在
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '_stress_test_boundary') THEN
    RAISE EXCEPTION '未找到 _stress_test_boundary 表，可能尚未生成过压测数据';
  END IF;
END $$;

\echo '>>> 开始清除压测数据...'

BEGIN;

-- 按外键依赖顺序反向删除
\echo '  删除 operation_logs...'
DELETE FROM operation_logs WHERE id > (SELECT max_id FROM _stress_test_boundary WHERE t = 'operation_logs');

\echo '  删除 shipment_items...'
DELETE FROM shipment_items WHERE id > (SELECT max_id FROM _stress_test_boundary WHERE t = 'shipment_items');

\echo '  删除 shipments...'
DELETE FROM shipments WHERE id > (SELECT max_id FROM _stress_test_boundary WHERE t = 'shipments');

\echo '  删除 payments...'
DELETE FROM payments WHERE id > (SELECT max_id FROM _stress_test_boundary WHERE t = 'payments');

\echo '  删除 stock_logs...'
DELETE FROM stock_logs WHERE id > (SELECT max_id FROM _stress_test_boundary WHERE t = 'stock_logs');

\echo '  删除 order_items...'
DELETE FROM order_items WHERE id > (SELECT max_id FROM _stress_test_boundary WHERE t = 'order_items');

\echo '  删除 orders...'
DELETE FROM orders WHERE id > (SELECT max_id FROM _stress_test_boundary WHERE t = 'orders');

\echo '  删除 purchase_order_items...'
DELETE FROM purchase_order_items WHERE id > (SELECT max_id FROM _stress_test_boundary WHERE t = 'purchase_order_items');

\echo '  删除 purchase_orders...'
DELETE FROM purchase_orders WHERE id > (SELECT max_id FROM _stress_test_boundary WHERE t = 'purchase_orders');

\echo '  删除 suppliers...'
DELETE FROM suppliers WHERE id > (SELECT max_id FROM _stress_test_boundary WHERE t = 'suppliers');

\echo '  删除 customers...'
DELETE FROM customers WHERE id > (SELECT max_id FROM _stress_test_boundary WHERE t = 'customers');

\echo '  删除 products...'
DELETE FROM products WHERE id > (SELECT max_id FROM _stress_test_boundary WHERE t = 'products');

-- 删除边界表
DROP TABLE IF EXISTS _stress_test_boundary;

COMMIT;

\echo ''
\echo '=== 压测数据清除完成 ==='

-- 显示清除后的数据量
SELECT t AS "表名", count AS "剩余记录数" FROM (
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

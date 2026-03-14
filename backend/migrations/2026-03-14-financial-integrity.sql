BEGIN;

-- 1. 创建 departments 表
CREATE TABLE IF NOT EXISTS departments (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. 创建 employees 表（含临时迁移列 _legacy_salesperson_id）
CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(30) DEFAULT '',
    department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL,
    is_salesperson BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    _legacy_salesperson_id INTEGER
);

-- 3. 迁移 Salesperson → Employee（幂等：仅在 employees 表为空时执行）
INSERT INTO employees (code, name, phone, is_salesperson, is_active, _legacy_salesperson_id)
SELECT 'SP' || LPAD(id::TEXT, 3, '0'), name, COALESCE(phone, ''), TRUE, is_active, id
FROM salespersons
WHERE NOT EXISTS (SELECT 1 FROM employees WHERE _legacy_salesperson_id IS NOT NULL LIMIT 1);

-- 4. orders 表加 employee_id（使用 _legacy_salesperson_id 精确映射）
ALTER TABLE orders ADD COLUMN IF NOT EXISTS employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL;
UPDATE orders SET employee_id = (
    SELECT e.id FROM employees e WHERE e._legacy_salesperson_id = orders.salesperson_id
) WHERE salesperson_id IS NOT NULL AND employee_id IS NULL;

-- 4b. 验证迁移（如有未映射的记录则报错中止）
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM orders WHERE salesperson_id IS NOT NULL AND employee_id IS NULL) THEN
        RAISE EXCEPTION '存在未映射的 salesperson_id，请检查数据';
    END IF;
END $$;

-- 4c. 清理迁移列（确认数据无误后执行）
ALTER TABLE employees DROP COLUMN IF EXISTS _legacy_salesperson_id;
-- 注意：salesperson_id 列暂时保留，待确认迁移无误后在后续迁移中删除
-- ALTER TABLE orders DROP COLUMN IF EXISTS salesperson_id;

-- 5. orders 表加退款字段
ALTER TABLE orders ADD COLUMN IF NOT EXISTS refund_method VARCHAR(50);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS refund_amount DECIMAL(18,2);

-- 6. purchase_returns 加退款字段
ALTER TABLE purchase_returns ADD COLUMN IF NOT EXISTS refund_method VARCHAR(50);
ALTER TABLE purchase_returns ADD COLUMN IF NOT EXISTS refund_amount DECIMAL(18,2);

-- 7. PaymentMethod/DisbursementMethod 加 account_set_id
ALTER TABLE payment_methods ADD COLUMN IF NOT EXISTS account_set_id INTEGER REFERENCES account_sets(id) ON DELETE RESTRICT;

-- 动态查找并删除旧的 unique 约束（约束名可能因 ORM 版本而异）
DO $$
DECLARE
    _conname TEXT;
BEGIN
    SELECT conname INTO _conname FROM pg_constraint
    WHERE conrelid = 'payment_methods'::regclass AND contype = 'u'
    AND array_length(conkey, 1) = 1;
    IF _conname IS NOT NULL THEN
        EXECUTE format('ALTER TABLE payment_methods DROP CONSTRAINT %I', _conname);
    END IF;
    SELECT conname INTO _conname FROM pg_constraint
    WHERE conrelid = 'disbursement_methods'::regclass AND contype = 'u'
    AND array_length(conkey, 1) = 1;
    IF _conname IS NOT NULL THEN
        EXECUTE format('ALTER TABLE disbursement_methods DROP CONSTRAINT %I', _conname);
    END IF;
END $$;

ALTER TABLE payment_methods ADD CONSTRAINT payment_methods_account_set_code_unique UNIQUE (account_set_id, code);

ALTER TABLE disbursement_methods ADD COLUMN IF NOT EXISTS account_set_id INTEGER REFERENCES account_sets(id) ON DELETE RESTRICT;
ALTER TABLE disbursement_methods ADD CONSTRAINT disbursement_methods_account_set_code_unique UNIQUE (account_set_id, code);

-- 8. 为每个账套复制收付款方式
DO $$
DECLARE
    as_rec RECORD;
    pm_rec RECORD;
    dm_rec RECORD;
BEGIN
    FOR as_rec IN SELECT id FROM account_sets WHERE is_active = TRUE LOOP
        FOR pm_rec IN SELECT code, name, sort_order FROM payment_methods WHERE account_set_id IS NULL AND is_active = TRUE LOOP
            INSERT INTO payment_methods (code, name, sort_order, account_set_id, is_active)
            VALUES (pm_rec.code, pm_rec.name, pm_rec.sort_order, as_rec.id, TRUE)
            ON CONFLICT (account_set_id, code) DO NOTHING;
        END LOOP;
        FOR dm_rec IN SELECT code, name, sort_order FROM disbursement_methods WHERE account_set_id IS NULL AND is_active = TRUE LOOP
            INSERT INTO disbursement_methods (code, name, sort_order, account_set_id, is_active)
            VALUES (dm_rec.code, dm_rec.name, dm_rec.sort_order, as_rec.id, TRUE)
            ON CONFLICT (account_set_id, code) DO NOTHING;
        END LOOP;
    END LOOP;
END $$;
DELETE FROM payment_methods WHERE account_set_id IS NULL;
DELETE FROM disbursement_methods WHERE account_set_id IS NULL;

-- 9. ReceiptBill 加 bill_type 和 return_order_id
ALTER TABLE receipt_bills ADD COLUMN IF NOT EXISTS bill_type VARCHAR(20) DEFAULT 'normal';
ALTER TABLE receipt_bills ADD COLUMN IF NOT EXISTS return_order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL;

-- 10. DisbursementBill 加 bill_type 和 purchase_return_id
ALTER TABLE disbursement_bills ADD COLUMN IF NOT EXISTS bill_type VARCHAR(20) DEFAULT 'normal';
ALTER TABLE disbursement_bills ADD COLUMN IF NOT EXISTS purchase_return_id INTEGER REFERENCES purchase_returns(id) ON DELETE SET NULL;

-- 11. ChartOfAccount 加辅助核算字段
ALTER TABLE chart_of_accounts ADD COLUMN IF NOT EXISTS aux_employee BOOLEAN DEFAULT FALSE;
ALTER TABLE chart_of_accounts ADD COLUMN IF NOT EXISTS aux_department BOOLEAN DEFAULT FALSE;

-- 12. 设置预置科目的辅助核算标记
UPDATE chart_of_accounts SET aux_employee = TRUE WHERE code = '1221';
UPDATE chart_of_accounts SET aux_employee = TRUE WHERE code = '2241';
UPDATE chart_of_accounts SET aux_employee = TRUE, aux_department = TRUE WHERE code IN ('6001', '6401', '6601', '6602', '6603');

-- 13. VoucherEntry 加辅助核算字段
ALTER TABLE voucher_entries ADD COLUMN IF NOT EXISTS aux_employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL;
ALTER TABLE voucher_entries ADD COLUMN IF NOT EXISTS aux_department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL;

-- 14. 性能索引
CREATE INDEX IF NOT EXISTS idx_voucher_entries_aux_employee ON voucher_entries(aux_employee_id) WHERE aux_employee_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_voucher_entries_aux_department ON voucher_entries(aux_department_id) WHERE aux_department_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_receipt_bills_bill_type ON receipt_bills(bill_type) WHERE bill_type = 'return_refund';
CREATE INDEX IF NOT EXISTS idx_disbursement_bills_bill_type ON disbursement_bills(bill_type) WHERE bill_type = 'return_refund';

-- 15. 清理（确认数据迁移无误后执行）
-- DROP TABLE IF EXISTS salespersons CASCADE;
-- ALTER TABLE orders DROP COLUMN IF EXISTS salesperson_id;

COMMIT;

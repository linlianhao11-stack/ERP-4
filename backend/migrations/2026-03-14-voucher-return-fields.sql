-- Order 增加凭证关联（仅 RETURN 类型使用）
ALTER TABLE orders ADD COLUMN IF NOT EXISTS voucher_id INTEGER REFERENCES vouchers(id) ON DELETE SET NULL;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS voucher_no VARCHAR(30);
CREATE INDEX IF NOT EXISTS idx_orders_voucher_id ON orders(voucher_id);

-- PurchaseReturn 增加凭证关联
ALTER TABLE purchase_returns ADD COLUMN IF NOT EXISTS voucher_id INTEGER REFERENCES vouchers(id) ON DELETE SET NULL;
ALTER TABLE purchase_returns ADD COLUMN IF NOT EXISTS voucher_no VARCHAR(30);
CREATE INDEX IF NOT EXISTS idx_purchase_returns_voucher_id ON purchase_returns(voucher_id);

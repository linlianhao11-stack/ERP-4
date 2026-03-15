-- B1: BankAccount 表 + ChartOfAccount/VoucherEntry 新增 aux_product/aux_bank 字段

-- 1. 创建银行账户表
CREATE TABLE IF NOT EXISTS bank_accounts (
    id SERIAL PRIMARY KEY,
    account_set_id INTEGER NOT NULL REFERENCES account_sets(id) ON DELETE RESTRICT,
    bank_name VARCHAR(100) NOT NULL,
    account_number VARCHAR(50) NOT NULL,
    short_name VARCHAR(50) DEFAULT '',
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (account_set_id, account_number)
);

-- 2. ChartOfAccount 新增辅助核算标记
ALTER TABLE chart_of_accounts ADD COLUMN IF NOT EXISTS aux_product BOOLEAN DEFAULT FALSE;
ALTER TABLE chart_of_accounts ADD COLUMN IF NOT EXISTS aux_bank BOOLEAN DEFAULT FALSE;

-- 3. VoucherEntry 新增辅助核算外键
ALTER TABLE voucher_entries ADD COLUMN IF NOT EXISTS aux_product_id INTEGER REFERENCES products(id) ON DELETE SET NULL;
ALTER TABLE voucher_entries ADD COLUMN IF NOT EXISTS aux_bank_account_id INTEGER REFERENCES bank_accounts(id) ON DELETE SET NULL;

-- 4. 性能索引
CREATE INDEX IF NOT EXISTS idx_bank_accounts_account_set ON bank_accounts(account_set_id) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_voucher_entries_aux_product ON voucher_entries(aux_product_id) WHERE aux_product_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_voucher_entries_aux_bank ON voucher_entries(aux_bank_account_id) WHERE aux_bank_account_id IS NOT NULL;

-- 5. 预设科目辅助核算标记
UPDATE chart_of_accounts SET aux_product = TRUE WHERE code IN ('1405', '1403', '1407');
UPDATE chart_of_accounts SET aux_bank = TRUE WHERE code = '1002';

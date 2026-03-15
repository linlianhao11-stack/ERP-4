-- Plan D: 发票多单合并来源字段 + 客户开票字段
-- 2026-03-15

-- Invoice: 新增多单来源 JSON 字段
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS source_receivable_bill_ids JSONB DEFAULT '[]'::jsonb;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS source_payable_bill_ids JSONB DEFAULT '[]'::jsonb;

-- Customer: 新增开票地址和电话字段
ALTER TABLE customers ADD COLUMN IF NOT EXISTS invoice_address VARCHAR(200) DEFAULT '';
ALTER TABLE customers ADD COLUMN IF NOT EXISTS invoice_phone VARCHAR(50) DEFAULT '';

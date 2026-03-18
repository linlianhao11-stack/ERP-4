-- 样机管理模块初始化

-- 1. 样机台账
CREATE TABLE IF NOT EXISTS demo_units (
    id SERIAL PRIMARY KEY,
    code VARCHAR(30) NOT NULL UNIQUE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    sn_code_id INTEGER REFERENCES sn_codes(id) ON DELETE SET NULL,
    warehouse_id INTEGER NOT NULL REFERENCES warehouses(id) ON DELETE RESTRICT,
    status VARCHAR(20) NOT NULL DEFAULT 'in_stock',
    condition VARCHAR(10) NOT NULL DEFAULT 'new',
    cost_price DECIMAL(12,2) NOT NULL DEFAULT 0,
    current_holder_type VARCHAR(10),
    current_holder_id INTEGER,
    total_loan_count INTEGER NOT NULL DEFAULT 0,
    total_loan_days INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_demo_units_status ON demo_units(status);
CREATE INDEX IF NOT EXISTS idx_demo_units_product ON demo_units(product_id);
CREATE INDEX IF NOT EXISTS idx_demo_units_warehouse ON demo_units(warehouse_id);

-- 2. 借还记录
CREATE TABLE IF NOT EXISTS demo_loans (
    id SERIAL PRIMARY KEY,
    loan_no VARCHAR(30) NOT NULL UNIQUE,
    demo_unit_id INTEGER NOT NULL REFERENCES demo_units(id) ON DELETE RESTRICT,
    loan_type VARCHAR(20) NOT NULL,
    borrower_type VARCHAR(10) NOT NULL,
    borrower_id INTEGER NOT NULL,
    handler_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending_approval',
    loan_date DATE,
    expected_return_date DATE NOT NULL,
    actual_return_date DATE,
    condition_on_loan VARCHAR(10) NOT NULL,
    condition_on_return VARCHAR(10),
    return_notes TEXT,
    approved_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    purpose TEXT,
    created_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_demo_loans_unit ON demo_loans(demo_unit_id);
CREATE INDEX IF NOT EXISTS idx_demo_loans_status ON demo_loans(status);
CREATE INDEX IF NOT EXISTS idx_demo_loans_borrower ON demo_loans(borrower_type, borrower_id);

-- 3. 处置记录
CREATE TABLE IF NOT EXISTS demo_disposals (
    id SERIAL PRIMARY KEY,
    demo_unit_id INTEGER NOT NULL REFERENCES demo_units(id) ON DELETE RESTRICT,
    disposal_type VARCHAR(20) NOT NULL,
    amount DECIMAL(12,2),
    refurbish_cost DECIMAL(12,2),
    order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    receivable_bill_id INTEGER,
    voucher_id INTEGER,
    target_warehouse_id INTEGER REFERENCES warehouses(id) ON DELETE SET NULL,
    target_location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    reason TEXT,
    approved_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_demo_disposals_unit ON demo_disposals(demo_unit_id);

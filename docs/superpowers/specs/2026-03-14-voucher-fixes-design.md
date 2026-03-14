# 凭证系统三项修复 — 设计规格

**日期**：2026-03-14
**状态**：待审阅

---

## 背景

当前凭证系统存在三个问题：

1. 采购入库时加权成本使用了含税价，导致出库凭证和发票确认结转成本均为含税金额
2. 销售/采购退货后，原出入库凭证未被冲回，且 AR/AP 管理界面缺少退货单据，无法生成退货凭证
3. 批量生成凭证时只能处理当前会计期间的单据，无法跨月生成

## 修复 1：成本含税 bug

### 问题根源

`backend/app/routers/purchase_orders.py:640`：

```python
cost_price = poi.amount / poi.quantity if poi.quantity > 0 else poi.tax_inclusive_price
```

`poi.amount` 是含税总金额（`tax_inclusive_price × quantity - rebate`），除以数量后得到含税单价。该值传入 `update_weighted_entry_date()`，导致 `WarehouseStock.weighted_cost` 存储含税成本。

### 影响链路

1. `WarehouseStock.weighted_cost` → 含税
2. `Product.cost_price`（通过 `get_product_weighted_cost` 同步）→ 含税
3. 销售出库 `SalesDeliveryBill.total_cost` → 含税
4. 出库凭证 1407/1405 → 含税
5. 发票确认结转 COGS 6401/1407 → 含税

### 修复方案

将 `purchase_orders.py:640` 改为：

```python
cost_price = poi.tax_exclusive_price
```

同时检查 `purchase_orders.py:786`（采购退货取值），如有相同问题一并修复。

### 历史数据

不追溯。仅修复代码，新数据走不含税逻辑，已有的 `weighted_cost` 和历史凭证不修改。

---

## 修复 2：退货凭证 + AR/AP 退货单据

### 2.1 数据模型变更

- `Order` 模型增加 `voucher_id`（FK → Voucher, nullable）和 `voucher_no`（CharField, nullable）字段
- `PurchaseReturn` 模型增加 `voucher_id`（FK → Voucher, nullable）和 `voucher_no`（CharField, nullable）字段
- 与现有 `SalesDeliveryBill`、`ReceiptBill` 等模型保持一致

### 2.2 销售退货 → 红字出库凭证

**触发时机**：AR 批量生成凭证时（`ar_service.py:generate_ar_vouchers`）

**查询条件**：`Order` where `order_type="RETURN"`, `voucher_id=None`，且订单创建日期在选中期间内

**凭证结构**：

| 行 | 科目 | 方向 | 金额 | 辅助核算 |
|----|------|------|------|----------|
| 1 | 1405 库存商品 | 借（红字） | 退货成本（不含税） | — |
| 2 | 1407 发出商品 | 贷（红字） | 退货成本（不含税） | — |

- 凭证类型：记
- 摘要：`销售退货冲回 {order_no}`
- `source_type`：`sales_return`
- `source_bill_id`：退货订单 ID
- 退货成本来源：退货订单的 `total_cost`（加权成本 × 数量）

**凭证关联**：生成后回写 `Order.voucher_id` 和 `Order.voucher_no`。

### 2.3 采购退货 → 红字入库凭证

**触发时机**：AP 批量生成凭证时（`ap_service.py:generate_ap_vouchers`）

**查询条件**：`PurchaseReturn` where `voucher_id=None`，且退货创建日期在选中期间内

**凭证结构**：

| 行 | 科目 | 方向 | 金额 | 辅助核算 |
|----|------|------|------|----------|
| 1 | 2202 应付账款 | 借（红字） | 退货含税金额 | 供应商 |
| 2 | 1405 库存商品 | 贷（红字） | 退货不含税金额 | — |
| 3 | 222101 进项税额 | 贷（红字） | 退货税额 | — |

- 凭证类型：记
- 摘要：`采购退货冲回 {return_no}`
- `source_type`：`purchase_return`
- `source_bill_id`：PurchaseReturn ID
- 税额换算：`total_amount` 为含税总额，按关联 `PurchaseOrderItem` 的 `tax_rate` 拆分不含税金额和税额

**凭证关联**：生成后回写 `PurchaseReturn.voucher_id` 和 `PurchaseReturn.voucher_no`。

### 2.4 前端 AR/AP 面板

**ReceivablePanel.vue**：
- 新增"销售退货单"tab
- 数据源：`GET /receivables/sales-returns`（新增 API，查询 `Order` where `order_type="RETURN"`）
- 列表字段：退货单号、客户名称、退货金额、退货日期、凭证状态（已生成/未生成）
- 批量生成凭证按钮同时覆盖退货单

**PayablePanel.vue**：
- 新增"采购退货单"tab
- 数据源：`GET /payables/purchase-returns`（新增 API，查询 `PurchaseReturn`）
- 列表字段：退货单号、供应商名称、退货金额、退货日期、凭证状态
- 批量生成凭证按钮同时覆盖退货单

---

## 修复 3：批量生成凭证支持多月选择

### 后端

**接口签名变更**：

```python
# 改前
async def generate_ar_vouchers(account_set_id: int, period_name: str, user) -> list

# 改后
async def generate_ar_vouchers(account_set_id: int, period_names: list[str], user) -> list
```

`generate_ap_vouchers` 同理。

**处理逻辑**：
1. 遍历 `period_names`，对每个月份：
   - 查找对应的 `AccountingPeriod`，不存在则跳过并记录警告
   - 已结账（`is_closed=True`）则跳过并在返回结果中标记
   - 计算 `period_start` / `period_end`，查询该月的待生成单据
   - 生成凭证，`period_name` 跟随单据所在月份
2. 返回结果包含：每个月份的凭证数量 + 跳过月份的原因

**API 路由变更**：

```
POST /receivables/generate-ar-vouchers
请求体：{ "period_names": ["2026-01", "2026-02", "2026-03"] }

POST /payables/generate-ap-vouchers
请求体：{ "period_names": ["2026-01", "2026-02", "2026-03"] }
```

**返回结构**：

```json
{
  "vouchers": [...],
  "summary": {
    "2026-01": { "count": 3 },
    "2026-02": { "count": 0, "skipped": false },
    "2026-03": { "count": 0, "skipped": true, "reason": "期间已结账" }
  }
}
```

### 前端

**ReceivablePanel.vue / PayablePanel.vue**：
- 月份选择器从单选改为多选（checkbox 列表或多选下拉）
- 默认勾选当前会计期间
- 生成结果按月展示凭证数量，已结账月份显示跳过提示

---

## 涉及文件清单

### 后端
| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `backend/app/routers/purchase_orders.py` | 修改 | 修复 L640/L786 cost_price 取值 |
| `backend/app/services/ar_service.py` | 修改 | 增加销售退货凭证生成；`period_name` → `period_names` |
| `backend/app/services/ap_service.py` | 修改 | 增加采购退货凭证生成；`period_name` → `period_names` |
| `backend/app/routers/receivables.py` | 修改 | 新增销售退货列表 API；批量接口改多月 |
| `backend/app/routers/payables.py` | 修改 | 新增采购退货列表 API；批量接口改多月 |
| `backend/app/models/order.py` | 修改 | Order 增加 `voucher_id` + `voucher_no` |
| `backend/app/models/purchase.py` | 修改 | PurchaseReturn 增加 `voucher_id` + `voucher_no` |
| `backend/migrations/` | 新增 | 数据库迁移脚本 |

### 前端
| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `frontend/src/components/business/ReceivablePanel.vue` | 修改 | 增加销售退货 tab；月份多选 |
| `frontend/src/components/business/PayablePanel.vue` | 修改 | 增加采购退货 tab；月份多选 |
| `frontend/src/api/accounting.js` | 修改 | API 参数调整 |

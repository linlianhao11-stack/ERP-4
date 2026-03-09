# ERP-4 API 端点索引

> 基于 v4.14.0 代码生成，共 **192** 个端点
> 运行时 Swagger 文档：启动后端后访问 http://localhost:8090/docs（需设置 `DEBUG=true`）

## 目录

1. [认证与用户](#1-认证与用户)
2. [商品与库存](#2-商品与库存)
3. [销售管理](#3-销售管理)
4. [采购管理](#4-采购管理)
5. [物流管理](#5-物流管理)
6. [财务管理](#6-财务管理)
7. [会计管理](#7-会计管理)
8. [系统管理](#8-系统管理)

---

## 1. 认证与用户

### 认证 (`/api/auth`)

> 路由文件：`app/routers/auth.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/auth/login` | 用户登录（含频率限制） | 无 |
| GET | `/api/auth/me` | 获取当前用户信息 | 登录（允许待改密） |
| POST | `/api/auth/change-password` | 修改密码 | 登录（允许待改密） |
| POST | `/api/auth/logout` | 登出（使 token 失效） | 登录（允许待改密） |

### 用户管理 (`/api/users`)

> 路由文件：`app/routers/users.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/users` | 获取用户列表 | `admin` |
| POST | `/api/users` | 创建用户 | `admin` |
| PUT | `/api/users/{user_id}` | 更新用户信息 | `admin` |
| POST | `/api/users/{user_id}/toggle` | 启用/禁用用户 | `admin` |

---

## 2. 商品与库存

### 商品管理 (`/api/products`)

> 路由文件：`app/routers/products.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/products` | 商品列表（支持关键词/分类/仓库筛选） | 登录 |
| GET | `/api/products/categories/list` | 获取商品分类列表 | 登录 |
| GET | `/api/products/export` | 导出商品 Excel | `stock_view` |
| GET | `/api/products/template` | 下载导入模板 Excel | `stock_edit` |
| POST | `/api/products/import/preview` | 批量导入预览 | `stock_edit` |
| POST | `/api/products/import` | 批量导入商品 | `stock_edit` |
| GET | `/api/products/{product_id}` | 商品详情 | 登录 |
| POST | `/api/products` | 创建商品 | `stock_edit` |
| PUT | `/api/products/{product_id}` | 更新商品 | `stock_edit` |
| DELETE | `/api/products/{product_id}` | 删除商品（软删除） | `stock_edit` |

### 商品品牌 (`/api`)

> 路由文件：`app/routers/product_brands.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/product-brands` | 获取品牌列表（从商品表 distinct） | 登录 |

### 仓库管理 (`/api/warehouses`)

> 路由文件：`app/routers/warehouses.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/warehouses` | 仓库列表（含仓位） | 登录 |
| POST | `/api/warehouses` | 创建仓库 | `stock_edit` |
| PUT | `/api/warehouses/{warehouse_id}` | 更新仓库 | `stock_edit` |
| DELETE | `/api/warehouses/{warehouse_id}` | 删除仓库（软删除） | `stock_edit` |

### 仓位管理 (`/api/locations`)

> 路由文件：`app/routers/locations.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/locations` | 仓位列表 | 登录 |
| POST | `/api/locations` | 创建仓位 | `stock_edit` |
| PUT | `/api/locations/{location_id}` | 更新仓位 | `stock_edit` |
| DELETE | `/api/locations/{location_id}` | 删除仓位（软删除） | `stock_edit` |

### 库存管理 (`/api/stock`)

> 路由文件：`app/routers/stock.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/stock/restock` | 入库 | `stock_edit` |
| POST | `/api/stock/adjust` | 库存调整 | `stock_edit` |
| POST | `/api/stock/transfer` | 库存调拨 | `stock_edit` |
| GET | `/api/stock/logs` | 出入库日志 | `logs` |
| GET | `/api/stock/export` | 导出库存 CSV | `stock_view` |

### SN 码管理 (`/api`)

> 路由文件：`app/routers/sn.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/sn-configs` | 获取 SN 配置列表 | `settings` / `admin` |
| POST | `/api/sn-configs` | 创建 SN 配置 | `settings` / `admin` |
| DELETE | `/api/sn-configs/{config_id}` | 删除 SN 配置（软删除） | `settings` / `admin` |
| GET | `/api/sn-codes/check-required` | 检查是否需要 SN 码 | 登录 |
| GET | `/api/sn-codes/available` | 查询可用 SN 码 | `stock_view` / `logistics` / `sales` |

---

## 3. 销售管理

### 订单管理 (`/api/orders`)

> 路由文件：`app/routers/orders.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/orders` | 创建订单（现款/账期/寄售/退货） | `sales` |
| GET | `/api/orders` | 订单列表 | 登录 |
| GET | `/api/orders/{order_id}` | 订单详情 | 登录 |
| GET | `/api/orders/{order_id}/cancel-preview` | 取消订单预览 | `sales` |
| POST | `/api/orders/{order_id}/cancel` | 取消订单（支持拆单） | `sales` |

### 客户管理 (`/api/customers`)

> 路由文件：`app/routers/customers.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/customers` | 客户列表 | 登录 |
| POST | `/api/customers` | 创建客户 | `customer` / `sales` |
| PUT | `/api/customers/{customer_id}` | 更新客户 | `customer` / `sales` |
| DELETE | `/api/customers/{customer_id}` | 删除客户（软删除） | `customer` / `sales` |
| GET | `/api/customers/{customer_id}/transactions` | 客户交易记录 | 登录 |

### 销售员管理 (`/api/salespersons`)

> 路由文件：`app/routers/salespersons.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/salespersons` | 销售员列表 | 登录 |
| POST | `/api/salespersons` | 创建销售员 | `admin` |
| PUT | `/api/salespersons/{sp_id}` | 更新销售员 | `admin` |
| DELETE | `/api/salespersons/{sp_id}` | 删除销售员（软删除） | `admin` |

### 寄售管理 (`/api/consignment`)

> 路由文件：`app/routers/consignment.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/consignment/summary` | 寄售汇总数据 | `sales` |
| GET | `/api/consignment/customer/{customer_id}` | 指定客户寄售详情 | `sales` |
| GET | `/api/consignment/customers` | 有寄售记录的客户列表 | `sales` |
| POST | `/api/consignment/return` | 寄售退货 | `sales` |

---

## 4. 采购管理

### 采购订单 (`/api/purchase-orders`)

> 路由文件：`app/routers/purchase_orders.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/purchase-orders` | 采购订单列表 | `purchase` / `purchase_approve` / `purchase_pay` / `purchase_receive` |
| GET | `/api/purchase-orders/export` | 导出采购订单 CSV | `purchase` / `finance` |
| POST | `/api/purchase-orders` | 创建采购订单 | `purchase` |
| GET | `/api/purchase-orders/receivable` | 待收货采购单列表 | `purchase_receive` |
| GET | `/api/purchase-orders/{po_id}` | 采购订单详情 | `purchase` / `purchase_approve` / `purchase_pay` / `purchase_receive` |
| POST | `/api/purchase-orders/{po_id}/pay` | 确认付款 | `purchase_pay` |
| POST | `/api/purchase-orders/{po_id}/approve` | 审核通过 | `purchase_approve` |
| POST | `/api/purchase-orders/{po_id}/reject` | 审核拒绝 | `purchase_approve` |
| POST | `/api/purchase-orders/{po_id}/cancel` | 取消采购单 | `purchase_pay` |
| POST | `/api/purchase-orders/{po_id}/receive` | 采购收货 | `purchase_receive` |
| POST | `/api/purchase-orders/{po_id}/return` | 采购退货 | `purchase` |

### 供应商管理 (`/api/suppliers`)

> 路由文件：`app/routers/suppliers.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/suppliers` | 供应商列表 | `purchase` |
| POST | `/api/suppliers` | 创建供应商 | `purchase` |
| PUT | `/api/suppliers/{supplier_id}` | 更新供应商 | `purchase` |
| DELETE | `/api/suppliers/{supplier_id}` | 删除供应商（软删除） | `purchase` |
| GET | `/api/suppliers/{supplier_id}/transactions` | 供应商交易记录 | `purchase` |
| POST | `/api/suppliers/{supplier_id}/credit-refund` | 供应商在账资金退款 | `purchase` |

---

## 5. 物流管理

### 物流 (`/api/logistics`)

> 路由文件：`app/routers/logistics.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/logistics/carriers` | 快递公司列表 | 登录 |
| GET | `/api/logistics/pending-orders` | 待发货订单列表 | 登录 |
| GET | `/api/logistics` | 物流列表（按订单分组） | 登录 |
| GET | `/api/logistics/{order_id}` | 物流详情 | 登录 |
| POST | `/api/logistics/{order_id}/ship` | 发货操作 | `logistics` / `sales` |
| POST | `/api/logistics/{order_id}/add` | 为订单添加物流单 | `logistics` / `sales` |
| PUT | `/api/logistics/shipment/{shipment_id}/ship` | 更新物流单发货信息 | `logistics` / `sales` |
| POST | `/api/logistics/shipment/{shipment_id}/update-sn` | 更新物流单 SN 码 | `logistics` / `sales` |
| DELETE | `/api/logistics/shipment/{shipment_id}` | 删除物流单（回滚库存） | `logistics` / `sales` |
| POST | `/api/logistics/shipment/{shipment_id}/refresh` | 刷新物流跟踪信息 | 登录 |
| POST | `/api/logistics/kd100/callback` | 快递100回调接口 | 无（签名验证） |

---

## 6. 财务管理

### 财务/回款 (`/api/finance`)

> 路由文件：`app/routers/finance.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/finance/all-orders` | 所有订单（财务视角） | `finance` |
| GET | `/api/finance/all-orders/export` | 导出订单 CSV | `finance` |
| GET | `/api/finance/stock-logs` | 出入库日志（财务视角） | `finance` |
| GET | `/api/finance/unpaid-orders` | 未结清订单 | `finance` |
| POST | `/api/finance/payment` | 账期收款核销 | `finance` |
| GET | `/api/finance/payments` | 收款记录列表 | `finance` |
| POST | `/api/finance/payment/{payment_id}/confirm` | 确认收款到账 | `finance_confirm` / `finance` |
| GET | `/api/finance/customer-statement/{customer_id}` | 客户对账单 | `finance` |

### 返利管理 (`/api/rebates`)

> 路由文件：`app/routers/rebates.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/rebates/summary` | 返利汇总 | `finance` |
| GET | `/api/rebates/logs` | 返利流水明细 | `finance` |
| POST | `/api/rebates/charge` | 返利充值 | `finance` |

### 收款方式 (`/api/payment-methods`)

> 路由文件：`app/routers/payment_methods.py`（使用 `crud_factory` 工厂模式）

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/payment-methods` | 收款方式列表 | 登录 |
| POST | `/api/payment-methods` | 创建收款方式 | `finance` |
| PUT | `/api/payment-methods/{method_id}` | 更新收款方式 | `finance` |
| DELETE | `/api/payment-methods/{method_id}` | 删除收款方式（软删除） | `finance` |

### 付款方式 (`/api/disbursement-methods`)

> 路由文件：`app/routers/disbursement_methods.py`（使用 `crud_factory` 工厂模式）

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/disbursement-methods` | 付款方式列表 | 登录 |
| POST | `/api/disbursement-methods` | 创建付款方式 | `finance` |
| PUT | `/api/disbursement-methods/{method_id}` | 更新付款方式 | `finance` |
| DELETE | `/api/disbursement-methods/{method_id}` | 删除付款方式（软删除） | `finance` |

---

## 7. 会计管理

### 账套管理 (`/api/account-sets`)

> 路由文件：`app/routers/account_sets.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/account-sets` | 账套列表 | 登录 |
| GET | `/api/account-sets/{set_id}` | 账套详情 | 登录 |
| POST | `/api/account-sets` | 创建账套（自动初始化科目+期间） | `admin` |
| PUT | `/api/account-sets/{set_id}` | 更新账套信息 | `admin` |

### 会计科目 (`/api/chart-of-accounts`)

> 路由文件：`app/routers/chart_of_accounts.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/chart-of-accounts` | 科目列表 | 登录 |
| POST | `/api/chart-of-accounts` | 创建科目 | `accounting_edit` |
| PUT | `/api/chart-of-accounts/{account_id}` | 更新科目 | `accounting_edit` |
| DELETE | `/api/chart-of-accounts/{account_id}` | 停用科目 | `accounting_edit` |

### 会计期间 (`/api/accounting-periods`)

> 路由文件：`app/routers/accounting_periods.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/accounting-periods` | 期间列表 | 登录 |
| POST | `/api/accounting-periods/init-year` | 初始化年度期间 | `period_end` |

### 凭证管理 (`/api/vouchers`)

> 路由文件：`app/routers/vouchers.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/vouchers` | 凭证列表（分页） | `accounting_view` |
| GET | `/api/vouchers/{voucher_id}` | 凭证详情（含分录） | `accounting_view` |
| POST | `/api/vouchers` | 创建凭证 | `accounting_edit` |
| PUT | `/api/vouchers/{voucher_id}` | 编辑凭证（仅草稿） | `accounting_edit` |
| DELETE | `/api/vouchers/{voucher_id}` | 删除凭证（仅草稿） | `accounting_edit` |
| POST | `/api/vouchers/{voucher_id}/submit` | 提交审核 | `accounting_edit` |
| POST | `/api/vouchers/{voucher_id}/approve` | 审核通过 | `accounting_approve` |
| POST | `/api/vouchers/{voucher_id}/reject` | 审核驳回 | `accounting_approve` |
| POST | `/api/vouchers/{voucher_id}/post` | 过账 | `accounting_post` |
| POST | `/api/vouchers/{voucher_id}/unpost` | 反过账 | `accounting_post` |
| GET | `/api/vouchers/{voucher_id}/pdf` | 单张凭证 PDF 下载 | `accounting_view` |
| POST | `/api/vouchers/batch-pdf` | 批量凭证 PDF 下载 | `accounting_view` |

### 账簿查询 (`/api/ledgers`)

> 路由文件：`app/routers/ledgers.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/ledgers/general-ledger` | 总分类账查询 | `accounting_view` |
| GET | `/api/ledgers/detail-ledger` | 明细分类账查询 | `accounting_view` |
| GET | `/api/ledgers/trial-balance` | 科目余额表 | `accounting_view` |
| GET | `/api/ledgers/general-ledger/export` | 导出总分类账 Excel | `accounting_view` |
| GET | `/api/ledgers/detail-ledger/export` | 导出明细分类账 Excel | `accounting_view` |
| GET | `/api/ledgers/trial-balance/export` | 导出科目余额表 Excel | `accounting_view` |

### 应收管理 (`/api/receivables`)

> 路由文件：`app/routers/receivables.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/receivables/receivable-bills` | 应收单列表 | `accounting_ar_view` |
| GET | `/api/receivables/receivable-bills/{bill_id}` | 应收单详情 | `accounting_ar_view` |
| POST | `/api/receivables/receivable-bills` | 创建应收单 | `accounting_ar_edit` |
| POST | `/api/receivables/receivable-bills/{bill_id}/cancel` | 取消应收单 | `accounting_ar_edit` |
| GET | `/api/receivables/receipt-bills` | 收款单列表 | `accounting_ar_view` |
| POST | `/api/receivables/receipt-bills` | 创建收款单 | `accounting_ar_edit` |
| POST | `/api/receivables/receipt-bills/{bill_id}/confirm` | 确认收款单 | `accounting_ar_confirm` |
| GET | `/api/receivables/receipt-refund-bills` | 收款退款单列表 | `accounting_ar_view` |
| POST | `/api/receivables/receipt-refund-bills` | 创建收款退款单 | `accounting_ar_edit` |
| POST | `/api/receivables/receipt-refund-bills/{bill_id}/confirm` | 确认收款退款 | `accounting_ar_confirm` |
| GET | `/api/receivables/receivable-write-offs` | 应收核销单列表 | `accounting_ar_view` |
| POST | `/api/receivables/receivable-write-offs` | 创建应收核销单 | `accounting_ar_edit` |
| POST | `/api/receivables/receivable-write-offs/{bill_id}/confirm` | 确认应收核销 | `accounting_ar_confirm` |
| POST | `/api/receivables/generate-ar-vouchers` | 应收期末凭证生成 | `accounting_ar_confirm` |

### 应付管理 (`/api/payables`)

> 路由文件：`app/routers/payables.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/payables/payable-bills` | 应付单列表 | `accounting_ap_view` |
| GET | `/api/payables/payable-bills/{bill_id}` | 应付单详情 | `accounting_ap_view` |
| POST | `/api/payables/payable-bills` | 创建应付单 | `accounting_ap_edit` |
| POST | `/api/payables/payable-bills/{bill_id}/cancel` | 取消应付单 | `accounting_ap_edit` |
| GET | `/api/payables/disbursement-bills` | 付款单列表 | `accounting_ap_view` |
| POST | `/api/payables/disbursement-bills` | 创建付款单 | `accounting_ap_edit` |
| POST | `/api/payables/disbursement-bills/{bill_id}/confirm` | 确认付款单 | `accounting_ap_confirm` |
| GET | `/api/payables/disbursement-refund-bills` | 付款退款单列表 | `accounting_ap_view` |
| POST | `/api/payables/disbursement-refund-bills` | 创建付款退款单 | `accounting_ap_edit` |
| POST | `/api/payables/disbursement-refund-bills/{bill_id}/confirm` | 确认付款退款 | `accounting_ap_confirm` |
| POST | `/api/payables/generate-ap-vouchers` | 应付期末凭证生成 | `accounting_ap_confirm` |

### 发票管理 (`/api/invoices`)

> 路由文件：`app/routers/invoices.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/invoices` | 发票列表 | `accounting_view` |
| GET | `/api/invoices/{invoice_id}` | 发票详情（含明细行） | `accounting_view` |
| POST | `/api/invoices/from-receivable` | 从应收单生成销项发票 | `accounting_edit` |
| POST | `/api/invoices` | 创建进项发票 | `accounting_edit` |
| PUT | `/api/invoices/{invoice_id}` | 编辑发票（仅草稿） | `accounting_edit` |
| POST | `/api/invoices/{invoice_id}/confirm` | 确认发票 | `accounting_approve` |
| POST | `/api/invoices/{invoice_id}/cancel` | 作废发票 | `accounting_edit` |

### 销售出库单 (`/api/sales-delivery`)

> 路由文件：`app/routers/sales_delivery.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/sales-delivery` | 出库单列表 | `accounting_view` |
| GET | `/api/sales-delivery/{bill_id}` | 出库单详情（含明细行） | `accounting_view` |
| GET | `/api/sales-delivery/{bill_id}/pdf` | 单张出库单 PDF 下载 | `accounting_view` |
| POST | `/api/sales-delivery/batch-pdf` | 批量出库单 PDF 下载 | `accounting_view` |

### 采购入库单 (`/api/purchase-receipt`)

> 路由文件：`app/routers/purchase_receipt.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/purchase-receipt` | 入库单列表 | `accounting_view` |
| GET | `/api/purchase-receipt/{bill_id}` | 入库单详情（含明细行） | `accounting_view` |
| GET | `/api/purchase-receipt/{bill_id}/pdf` | 单张入库单 PDF 下载 | `accounting_view` |
| POST | `/api/purchase-receipt/batch-pdf` | 批量入库单 PDF 下载 | `accounting_view` |

### 期末处理 (`/api/period-end`)

> 路由文件：`app/routers/period_end.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/period-end/carry-forward/preview` | 结转损益预览 | `period_end` |
| POST | `/api/period-end/carry-forward` | 执行结转损益 | `period_end` |
| POST | `/api/period-end/close-check` | 结账检查 | `period_end` |
| POST | `/api/period-end/close` | 期末结账 | `period_end` |
| POST | `/api/period-end/reopen` | 反结账 | `admin` |
| POST | `/api/period-end/year-close` | 年度结转 | `period_end` |

### 财务报表 (`/api/financial-reports`)

> 路由文件：`app/routers/financial_reports.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/financial-reports/balance-sheet` | 资产负债表 | `accounting_view` |
| GET | `/api/financial-reports/income-statement` | 利润表 | `accounting_view` |
| GET | `/api/financial-reports/cash-flow` | 现金流量表 | `accounting_view` |
| GET | `/api/financial-reports/balance-sheet/export` | 导出资产负债表（Excel/PDF） | `accounting_view` |
| GET | `/api/financial-reports/income-statement/export` | 导出利润表（Excel/PDF） | `accounting_view` |
| GET | `/api/financial-reports/cash-flow/export` | 导出现金流量表（Excel/PDF） | `accounting_view` |

---

## 8. 系统管理

### 系统设置 (`/api/settings`)

> 路由文件：`app/routers/settings.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/settings/{key}` | 获取系统设置 | 登录 |
| PUT | `/api/settings/{key}` | 更新系统设置 | `admin` |

### 操作日志 (`/api/operation-logs`)

> 路由文件：`app/routers/operation_logs.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/operation-logs` | 操作日志列表 | `logs` / `admin` |

### 备份管理 (`/api`)

> 路由文件：`app/routers/backup.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/backup` | 手动创建备份 | `admin` |
| GET | `/api/backups` | 备份列表 | `admin` |
| GET | `/api/backups/{filename}` | 下载备份文件 | `admin` |
| POST | `/api/backups/upload-restore` | 上传备份并恢复 | `admin` |
| POST | `/api/backups/{filename}/restore` | 从已有备份恢复 | `admin` |
| DELETE | `/api/backups/{filename}` | 删除备份文件 | `admin` |

### 仪表盘 (`/api`)

> 路由文件：`app/routers/dashboard.py`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/dashboard` | 仪表盘数据（今日销售/库存/畅销） | 登录 |

---

## 权限说明

| 权限标识 | 说明 |
|----------|------|
| `admin` | 系统管理员 |
| `sales` | 销售管理 |
| `customer` | 客户管理 |
| `stock_view` | 库存查看 |
| `stock_edit` | 库存编辑 |
| `logistics` | 物流管理 |
| `finance` | 财务管理 |
| `finance_confirm` | 财务确认 |
| `purchase` | 采购管理 |
| `purchase_approve` | 采购审核 |
| `purchase_pay` | 采购付款 |
| `purchase_receive` | 采购收货 |
| `logs` | 日志查看 |
| `settings` | 系统设置 |
| `accounting_view` | 会计查看 |
| `accounting_edit` | 会计编辑 |
| `accounting_approve` | 会计审核 |
| `accounting_post` | 会计过账 |
| `accounting_ar_view` | 应收查看 |
| `accounting_ar_edit` | 应收编辑 |
| `accounting_ar_confirm` | 应收确认 |
| `accounting_ap_view` | 应付查看 |
| `accounting_ap_edit` | 应付编辑 |
| `accounting_ap_confirm` | 应付确认 |
| `period_end` | 期末处理 |

> **注意：** 权限列中的 `/` 表示 "或" 关系，即拥有其中任一权限即可访问。`admin` 角色拥有所有权限。"登录" 表示仅需有效的 JWT token。

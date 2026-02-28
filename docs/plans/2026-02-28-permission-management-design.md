# 权限管理系统改造设计

## 目标

1. 设置页新增"权限管理"Tab，按主页模块分组的开关卡片式权限编辑
2. 主页 Tab 根据权限动态显示/隐藏（现有机制已实现，无需改动）
3. 按钮级细粒度权限控制审查补全

## 设计

### 权限管理 Tab 布局

左侧用户列表 + 右侧模块卡片。选中用户后显示权限卡片，每个卡片对应主页一个 Tab。

### 权限分组

| 模块 | 主开关 | 子权限 |
|------|--------|--------|
| 首页 | dashboard | — |
| 销售 | sales | — |
| 库存 | stock_view | stock_edit |
| 采购 | purchase | purchase_approve / purchase_pay / purchase_receive |
| 寄售 | consignment | — |
| 物流 | logistics | — |
| 财务 | finance | finance_confirm |
| 会计 | accounting_view | accounting_edit / accounting_approve / accounting_post / accounting_ar_view / accounting_ar_edit / accounting_ar_confirm / accounting_ap_view / accounting_ap_edit / accounting_ap_confirm / period_end |
| 客户 | customer | — |
| 系统 | settings | logs / admin |

### 交互规则

- 关闭主开关 → 自动取消所有子权限
- admin 用户显示提示，不显示卡片
- 用户编辑弹窗中权限区域替换为跳转链接

### 按钮权限审查

VoucherPanel / ReceiptBillsTab / DisbursementBillsTab 已有权限检查。
PeriodEndPanel 需补充 `period_end` 权限检查。

### 改动文件

- `frontend/src/utils/constants.js` — 新增 permissionGroups
- `frontend/src/views/SettingsView.vue` — 新增权限管理Tab + 用户弹窗改造
- `frontend/src/components/business/PeriodEndPanel.vue` — 补充 period_end 权限

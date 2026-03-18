# SN 码订单详情 UI 优化设计

## 背景

订单详情弹窗（`FinanceOrderDetailModal`）中的 SN 码展示存在以下问题：

1. **数据源断层**：SN 码存储在两处——`ShipmentItem.sn_codes`（发货时写入）和 `Shipment.sn_code`（"更新 SN"写入），但模板的 `v-if/v-else-if` 结构导致有 ShipmentItem 但 sn_codes 为空时，Shipment 级的 SN 码不会显示
2. **展示过于简陋**：SN 码缺少复制功能，物流单与 SN 码的对应关系不清晰
3. **`parseSN` 解析 bug**：纯数字字符串被 `JSON.parse` 解析为数字而非数组（已修复）

## 方案：物流卡片内嵌 SN 面板

将 SN 码集中在物流信息区域展示，与物流单绑定显示，提供复制能力。

### 布局结构

```
┌──────────────────────────────────────────────────┐
│ 物流单 1  京东物流                      ● 已签收  │
├──────────────────────────────────────────────────┤
│ 运单号: JDV026161923437                  [复制]  │
├──────────────────────────────────────────────────┤
│ 希沃seewo 平板V20 (6+128GB) 极光蓝         × 1  │
│   SKU0001                                        │
├─ SN码 ──────────────────────────────────────────┤
│ ┌──────────────────────────────────────────┐     │
│ │  111111111111                        📋  │     │
│ └──────────────────────────────────────────┘     │
│ ┌──────────────────────────────────────────┐     │
│ │  222222222222                        📋  │     │
│ └──────────────────────────────────────────┘     │
│                                [复制全部SN码]    │
├──────────────────────────────────────────────────┤
│ 最新物流: 已签收...                               │
└──────────────────────────────────────────────────┘
```

### SN 码数据源合并逻辑

优先级：ShipmentItem.sn_codes > Shipment.sn_code，去重后显示。

```
getShipmentSNCodes(sh):
  codes = []
  for si in sh.items:
    codes.push(...parseSN(si.sn_codes))
  if codes.length == 0 and sh.sn_code:
    codes = parseSN(sh.sn_code)
  return deduplicate(codes)
```

### 交互设计

- **单个复制**：每行 SN 码右侧有复制图标按钮，点击复制该 SN 码
- **批量复制**：底部「复制全部SN码」按钮，复制换行分隔的所有 SN 码
- **运单号复制**：运单号行增加复制按钮
- **无 SN 码**：该区域不显示（不显示"未填写"占位）

### 视觉规范

- SN 码区域：`bg-elevated` + `border border-line` + `rounded-lg`
- SN 码标题：`text-[11px] font-semibold text-muted`
- SN 码文本：`text-[12px] font-mono text-text`
- 复制按钮：`lucide-vue-next` 的 `Copy` 图标，14px，hover 变 primary

### 变更范围

**修改文件：**
- `frontend/src/components/business/finance/FinanceOrderDetailModal.vue`
  - 重写物流卡片的 SN 码显示区域
  - 移除商品明细表格中的 `snByProduct` 标签
  - 移除 `snByProduct` 计算属性
  - 新增 `getShipmentSNCodes(sh)` 辅助函数
  - 新增 `copyToClipboard(text)` 辅助函数
  - 新增 `Copy` 图标 import

**不修改：**
- 后端 API（数据结构不变）
- Excel 导出逻辑（已实现，保持不变）

### 已知边界情况

1. **重复 SN**：`ship_order_items` 同时写入 ShipmentItem 和 Shipment，合并时用 Set 去重
2. **多商品物流单**：ShipmentItem 级的 SN 码天然关联商品，Shipment 级的无法区分归属——统一显示在物流单维度，不按商品拆分
3. **空字符串**：`ShipmentItem.sn_codes = ''` 在数据库中是空字符串而非 NULL，`parseSN` 已处理

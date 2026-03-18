# 样机明细弹窗 + SN码搜索修复 设计文档

## 背景

样机管理页面存在两个问题：
1. 样机台账列表无法点击查看完整明细，缺少借出流程和时间线等关键信息
2. 搜索框使用 SN 码搜索时无法匹配到对应样机

## 问题 1：样机明细弹窗

### 方案

新增 `DemoUnitDetailModal.vue` 组件，采用全屏 Modal 弹窗（与现有 `FinanceOrderDetailModal`、`DropshipOrderDetail` 等一致的交互模式）。

### 数据来源

后端已有 `GET /api/demo/units/{id}` 接口，返回样机基本信息 + 完整借还历史（loans）+ 处置记录（disposals），无需新增 API。

### 弹窗布局（从上到下）

#### 1. 头部
- 左：样机编号（如 DM000001）+ 状态徽章（在库/借出中/已转销售等）
- 右：关闭按钮

#### 2. 基本信息卡片
- 产品名称、SKU
- SN 码
- 仓库 / 仓位
- 成色（全新/良好/一般/较差）
- 成本价
- 当前持有人（借出中时显示）
- 累计借出次数 / 天数
- 创建时间、创建人
- 备注

#### 3. 时间线概览
- 按时间倒序排列，展示样机全生命周期关键节点
- 节点类型：创建入库、借出申请、审批通过/拒绝、确认出库、归还、处置（转销售/翻新/报废/丢失）
- 每个节点显示：时间戳、操作类型、操作人/相关人、关键信息摘要
- 超期借出节点标红提示
- 数据源：合并 loans + disposals 按时间排序

#### 4. 借还记录表格
- 字段：单号、借出类型、借用人、经手人、借出日期、预期归还、实际归还、借出成色、归还成色、状态
- 超期行高亮
- 无记录时显示空状态

#### 5. 处置记录（如有）
- 字段：处置类型、金额、原因、审批人、时间
- 无记录时不显示此区块

### 交互

- 点击样机台账列表的行 → 打开弹窗
- 控制方式：`v-model:visible` + `:unitId` props
- 弹窗内只读，不包含操作按钮（操作仍在列表行内完成）

### 组件位置

`frontend/src/components/business/demo/DemoUnitDetailModal.vue`

## 问题 2：SN码搜索修复

### 原因

后端 `GET /api/demo/units` 的搜索过滤逻辑（`demo.py` 约 300-307 行）只包含：
- `code__icontains`
- `product__name__icontains`
- `product__sku__icontains`

缺少 `sn_code__code__icontains`。

### 修复

在搜索 Q 表达式中增加 `Q(sn_code__code__icontains=search)` 条件。

### 涉及文件
- `backend/app/routers/demo.py` — 搜索过滤逻辑

## 涉及文件总览

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `frontend/src/components/business/demo/DemoUnitDetailModal.vue` | 新增 | 样机明细弹窗组件 |
| `frontend/src/components/business/demo/DemoUnitList.vue` | 修改 | 添加行点击事件 + 引入弹窗 |
| `backend/app/routers/demo.py` | 修改 | 搜索增加 SN 码字段 |

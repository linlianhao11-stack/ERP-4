# 代采代发 — 订单详情弹窗 + 物流跟踪设计

> 日期: 2026-03-16
> 状态: 已批准

## 背景

代采代发模块当前缺少两个基础功能：
1. **无法查看订单明细** — 列表只有操作按钮（编辑/发货/取消），没有"查看详情"入口
2. **物流信息不可见** — 模型存储了 `tracking_no`/`last_tracking_info`，但前端没有展示

## 改动范围

### 改动 1：订单详情弹窗

**新组件**: `DropshipOrderDetail.vue`

**触发方式**: 点击列表中的订单号（ds_no 做成可点击链接样式）

**内容分区（从上到下）**:

| 区块 | 内容 |
|------|------|
| 顶部标题栏 | 单号 + 状态 badge + 创建时间 |
| 采购信息 | 供应商、商品、数量、采购单价/税率/总额、发票类型 |
| 销售信息 | 客户、平台订单号、销售单价/税率/总额、结算方式 |
| 毛利计算 | 毛利金额 + 毛利率（正绿负红） |
| 物流摘要 | 快递公司 + 单号 + 当前状态 + 最后一条轨迹，带"查看全部"展开完整时间线 |
| 财务单据 | 应付单、付款单、应收单的状态和金额 |
| 操作日志 | 创建、提交、付款、催付、发货、完成/取消等时间节点 |

**数据来源**: `GET /api/dropship/{order_id}`（已存在）

### 改动 2：发货弹窗增加手机尾号

- 当选择顺丰(`shunfeng`)或中通(`zhongtong`)时，动态显示"收/寄件人手机号后四位"输入框
- 后端 `DropshipOrder` 模型新增 `phone` 字段（`CharField(max_length=11, null=True)`）
- 发货 API `POST /dropship/{id}/ship` 接收 `phone` 参数
- 订阅快递100时传入 phone，参考 `ShipmentDetailModal` 的处理逻辑
- 需要手机号的快递公司: `PHONE_REQUIRED_CARRIERS = {"shunfeng", "shunfengkuaiyun", "zhongtong"}`

### 改动 3：列表增加物流状态列

- 在 `tracking_no` 列后增加"物流状态"列
- 显示解析后的中文状态（运输中/已签收/待揽收等）
- 后端列表 API 返回新增 `tracking_status` 字段（从 `last_tracking_info` 解析）
- 默认显示此列（不隐藏）

## 技术要点

- 物流时间线样式复用现有 `ShipmentDetailModal` 的时间线组件样式
- 详情弹窗内"刷新物流"按钮调用后端查询快递100并更新
- 后端需要新增一个专门给代采代发用的物流刷新接口（或复用现有 logistics refresh）
- `last_tracking_info` 是 JSON 文本，存储快递100返回的完整轨迹数组

## 涉及文件

**前端**:
- `frontend/src/components/business/dropship/DropshipOrderDetail.vue`（新建）
- `frontend/src/components/business/DropshipOrdersPanel.vue`（改：单号可点击 + 物流状态列 + 发货弹窗加 phone）
- `frontend/src/api/dropship.js`（改：新增物流刷新 API 调用）

**后端**:
- `backend/app/models/dropship.py`（改：新增 phone 字段）
- `backend/app/schemas/dropship.py`（改：ship schema 加 phone、列表 schema 加 tracking_status）
- `backend/app/routers/dropship.py`（改：发货接收 phone、新增物流刷新端点或复用）
- `backend/app/services/dropship_service.py`（改：发货时传 phone 给快递100订阅）
- `backend/app/migrations.py`（改：新增 phone 字段迁移）

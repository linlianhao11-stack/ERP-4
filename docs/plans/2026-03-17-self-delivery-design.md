# 自配送选项 + 快递公司扩充设计

## 背景

代采代发模块的新建发货单功能中，需要增加"自配送"物流选项。同时扩充快递公司列表，并将下拉框改为可搜索。

## 需求

1. 新增"自配送"选项：选中后不需要填快递单号，提交后直接变为"已签收"状态，状态文本显示"已送达"
2. 扩充快递公司列表：从 12 项增至 29 项，覆盖国内主流快递
3. 快递公司下拉框改为带模糊搜索的 SearchableSelect 组件

## 自配送 vs 自提

| | 上门自提 | 自配送 |
|---|---|---|
| 业务含义 | 客户来取货 | 我方送货上门 |
| carrier_code | `self_pickup` | `self_delivery` |
| 快递单号 | 不需要 | 不需要 |
| 最终状态 | `signed` | `signed` |
| 状态文本 | 已自提 | 已送达 |
| 快递100跟踪 | 跳过 | 跳过 |

## 技术方案：复用 self_pickup 逻辑路径

自配送和自提的技术处理完全一致（无快递单号、直接签收、跳过物流跟踪），仅名称和状态文本不同。不引入新模型字段，只新增一个 carrier_code。

## 改动清单

### 后端

**`backend/app/config.py`**
- CARRIER_LIST 扩充至 29 项（+自配送 +16 家快递公司）
- 新增快递公司：顺丰快运、中通快运、韵达快运、百世快递、天天快递、邮政标准快递、丰网速运、安能快运、壹米滴答、中铁快运、宅急送、国通快递、加运美、信丰物流、京广速递、中国邮政（修正名称）

**`backend/app/routers/logistics.py`**
- 提取 `NO_LOGISTICS_CARRIERS` 常量：`{"self_pickup", "self_delivery"}`
- 3 处自提判断（创建/添加/编辑物流单）统一改用该常量
- 自配送时 status_text = "已送达"，返回消息 = "已标记送达"

### 前端

**`frontend/src/components/business/logistics/ShipmentDetailModal.vue`**
- 两处原生 `<select>` 替换为 `SearchableSelect`
- carriers 数据映射为 `{id: code, label: name}`
- 自配送时隐藏快递单号，显示提示文案
- 提交按钮文案区分：自提/自配送/普通发货

### 不改动

- Shipment 模型、Schema、状态枚举、快递100集成逻辑、前端常量

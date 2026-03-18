# 订单备注行内编辑

> **目标**: 订单创建后，允许在财务-订单详情中编辑备注（发货地址/手机号），修改实时生效于物流展示。

## 约束

- 权限复用现有订单模块权限
- 物流 Shipment 模型不改动（实时读 order.remark）
- 操作日志记录修改历史（旧值 → 新值）
- UI 风格与项目一致（lucide 图标 + 语义色文字按钮）

## 后端

### 新增端点

`PATCH /api/orders/{order_id}/remark`

```json
Request:  { "remark": "新备注内容" }
Response: { "id": 123, "remark": "新备注内容" }
```

- 校验：`remark` 最大 2000 字符，允许空字符串（清空备注）
- 副作用：写入 `operation_logs`（module=order, action=update_remark, detail=旧值→新值）
- 订单不存在返回 404，account_set_id 过滤

## 前端

### 修改文件

`FinanceOrderDetailModal.vue`

### 查看态

备注文字右侧显示铅笔图标（`Edit2 :size="14"`），样式 `text-muted hover:text-primary transition-colors`。无备注时显示「无备注」+ 铅笔图标。

### 编辑态

点击铅笔后：
- 备注区域展开为 `<textarea class="input text-sm" rows="3">`，自动 focus
- 下方两个文字按钮：「保存」(`text-success-emphasis text-xs font-medium`) / 「取消」(`text-muted text-xs`)
- Escape 键取消编辑
- 保存成功后 `showToast('备注更新成功')`

### API 调用

`orders.js` 中新增 `updateOrderRemark(orderId, remark)` 方法。

## 操作日志

```json
{
  "module": "order",
  "action": "update_remark",
  "target_id": 123,
  "detail": "备注修改: 旧内容 → 新内容",
  "operator_id": 1
}
```

## 不做的事

- 不加备注修改历史弹窗（通过操作日志查）
- 不给 Shipment 模型加 remark 字段
- 不加审批流程
- 不限制修改次数

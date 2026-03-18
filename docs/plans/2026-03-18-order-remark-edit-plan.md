# 订单备注行内编辑 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 允许在财务订单详情弹窗中行内编辑订单备注，修改记录写入操作日志。

**Architecture:** 后端新增 `PATCH /api/orders/{order_id}/remark` 端点，复用现有订单权限。前端在 `FinanceOrderDetailModal.vue` 的备注区域加入 view/edit 切换，使用项目已有的 lucide 图标和语义色文字按钮。

**Tech Stack:** FastAPI + Tortoise ORM / Vue 3 Composition API + lucide-vue-next

---

### Task 1: 后端 — 新增备注修改 Schema

**Files:**
- Modify: `backend/app/schemas/order.py`

**Step 1: 添加 RemarkUpdate schema**

在 `backend/app/schemas/order.py` 末尾添加：

```python
class RemarkUpdate(BaseModel):
    remark: str = Field("", max_length=2000)
```

**Step 2: 验证 import 无误**

Run: `cd /Users/lin/Desktop/erp-4/backend && python -c "from app.schemas.order import RemarkUpdate; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add backend/app/schemas/order.py
git commit -m "feat(order): add RemarkUpdate schema"
```

---

### Task 2: 后端 — 新增备注修改端点

**Files:**
- Modify: `backend/app/routers/orders.py:35` (router 定义之后)

**Step 1: 在 `orders.py` 添加 PATCH 端点**

在 `backend/app/routers/orders.py` 的 import 区域追加 `RemarkUpdate`：

```python
from app.schemas.order import OrderCreate, CancelRequest, RemarkUpdate
```

在 `create_order` 函数之后（`list_orders` 之前，约第 272 行前）插入新端点：

```python
@router.patch("/{order_id}/remark")
async def update_order_remark(order_id: int, data: RemarkUpdate, user: User = Depends(require_permission("sales", "finance"))):
    order = await Order.filter(id=order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    old_remark = order.remark or ""
    new_remark = data.remark

    if old_remark == new_remark:
        return {"id": order.id, "remark": order.remark}

    order.remark = new_remark
    await order.save(update_fields=["remark", "updated_at"])

    await log_operation(
        user, "ORDER_UPDATE_REMARK", "ORDER", order.id,
        f"修改订单 {order.order_no} 备注: {old_remark[:50] or '(空)'} → {new_remark[:50] or '(空)'}"
    )

    return {"id": order.id, "remark": order.remark}
```

**Step 2: 验证语法**

Run: `cd /Users/lin/Desktop/erp-4/backend && python -c "from app.routers.orders import router; print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add backend/app/routers/orders.py
git commit -m "feat(order): add PATCH endpoint for remark update with audit log"
```

---

### Task 3: 前端 — 添加 API 方法

**Files:**
- Modify: `frontend/src/api/orders.js`

**Step 1: 在 `orders.js` 末尾添加**

```javascript
export const updateOrderRemark = (id, remark) => api.patch('/orders/' + id + '/remark', { remark })
```

**Step 2: 验证构建**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npm run build`
Expected: 构建成功，无错误

**Step 3: Commit**

```bash
git add frontend/src/api/orders.js
git commit -m "feat(order): add updateOrderRemark API method"
```

---

### Task 4: 前端 — FinanceOrderDetailModal 行内编辑

**Files:**
- Modify: `frontend/src/components/business/finance/FinanceOrderDetailModal.vue`

**Step 1: 在 `<script setup>` 中添加状态和方法**

1a. 在 import 区域添加图标和 API：

```javascript
import { Maximize2, Minimize2, Copy, Pencil } from 'lucide-vue-next'
import { getOrder, createOrder, updateOrderRemark } from '../../../api/orders'
```

1b. 在 `// --- 退货状态 ---` 之前添加备注编辑状态：

```javascript
// --- 备注编辑状态 ---
const isEditingRemark = ref(false)
const editingRemark = ref('')
const remarkSaving = ref(false)

const startEditRemark = () => {
  editingRemark.value = orderDetail.remark || ''
  isEditingRemark.value = true
}

const cancelEditRemark = () => {
  isEditingRemark.value = false
  editingRemark.value = ''
}

const saveRemark = async () => {
  remarkSaving.value = true
  try {
    await updateOrderRemark(orderDetail.id, editingRemark.value)
    orderDetail.remark = editingRemark.value
    isEditingRemark.value = false
    appStore.showToast('备注更新成功')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '备注保存失败', 'error')
  } finally {
    remarkSaving.value = false
  }
}
```

1c. 在 `watch` 的 `else if (!val)` 分支中增加重置：

```javascript
} else if (!val) {
    // 关闭时重置状态
    showReturnForm.value = false
    isDetailExpanded.value = false
    isEditingRemark.value = false
}
```

**Step 2: 替换模板中的备注展示区域**

将 `FinanceOrderDetailModal.vue` 第 290 行的备注展示：

```html
<div v-if="orderDetail.remark" class="col-span-2 pt-2 border-t border-line"><span class="text-muted">备注:</span> <span class="text-secondary">{{ orderDetail.remark }}</span></div>
```

替换为：

```html
<div class="col-span-2 pt-2 border-t border-line">
  <template v-if="isEditingRemark">
    <div class="text-muted text-xs mb-1.5">备注</div>
    <textarea
      v-model="editingRemark"
      class="input text-sm"
      rows="3"
      placeholder="输入订单备注信息..."
      @keyup.escape="cancelEditRemark"
      ref="remarkTextarea"
    ></textarea>
    <div class="flex items-center gap-3 mt-2">
      <button @click="saveRemark" :disabled="remarkSaving" class="text-success-emphasis text-xs font-medium">
        {{ remarkSaving ? '保存中...' : '保存' }}
      </button>
      <button @click="cancelEditRemark" class="text-muted text-xs">取消</button>
    </div>
  </template>
  <template v-else>
    <div class="flex items-start gap-2">
      <div class="flex-1 min-w-0">
        <span class="text-muted">备注:</span>
        <span class="text-secondary">{{ orderDetail.remark || '无备注' }}</span>
      </div>
      <button
        @click="startEditRemark"
        class="text-muted hover:text-primary transition-colors flex-shrink-0 mt-0.5"
        title="编辑备注"
      >
        <Pencil :size="14" />
      </button>
    </div>
  </template>
</div>
```

**Step 3: 验证构建**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npm run build`
Expected: 构建成功，无错误

**Step 4: Commit**

```bash
git add frontend/src/components/business/finance/FinanceOrderDetailModal.vue
git commit -m "feat(order): add inline remark editing in finance order detail modal"
```

---

### Task 5: Docker 集成验证

**Step 1: 构建前端到 static**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npm run build`

**Step 2: 构建 Docker 镜像并启动**

Run: `cd /Users/lin/Desktop/erp-4 && docker compose up --build -d`

**Step 3: 验证后端端点存在**

Run: `curl -s http://localhost:8090/openapi.json | python3 -c "import sys,json; d=json.load(sys.stdin); print('/api/orders/{order_id}/remark' in [k for k in d.get('paths',{})])"`

注意：如果 openapi 被禁用（非 DEBUG），改为直接测试端点：

Run: `curl -s -X PATCH http://localhost:8090/api/orders/1/remark -H 'Content-Type: application/json' -d '{"remark":"test"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print(d)"`

Expected: 返回 401（未认证）或正常响应，不是 404/405

**Step 4: 检查容器日志无启动错误**

Run: `docker compose logs erp --tail=20`
Expected: 无 ImportError 或 SyntaxError

**Step 5: Commit（如有未提交的修复）**

```bash
git add -A && git commit -m "fix: address issues found during Docker integration test"
```

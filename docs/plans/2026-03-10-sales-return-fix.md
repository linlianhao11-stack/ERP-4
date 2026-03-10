# 销售退货修复 + 订单详情内退货 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复销售退货加载失败 bug，并在订单详情弹窗内新增直接退货功能。

**Architecture:** Bug 修复是一行代码（响应结构 `data` → `data.items`）。订单详情退货功能在 FinanceOrdersTab.vue 中新增退货表单 UI + 提交逻辑，完全复用后端现有 `POST /api/orders`（order_type=RETURN）接口，零后端改动。退货入库自动使用原订单仓库 + 第一个活跃仓位。

**Tech Stack:** Vue 3 (Composition API) / FastAPI + Tortoise ORM

---

### Task 1: 修复 SalesView.vue 退货加载订单失败

**Files:**
- Modify: `frontend/src/views/SalesView.vue:196`

**Step 1: 修复响应结构**

后端 `GET /api/orders` 返回 `{ items: [...], total: N }`，前端直接 `data.filter(...)` 导致 TypeError。

找到 `searchReturnOrders` 函数（约 line 189-202），将 line 196 从：

```javascript
salesOrders.value = data.filter(o => ['CASH', 'CREDIT'].includes(o.order_type))
```

改为：

```javascript
salesOrders.value = (data.items || data).filter(o => ['CASH', 'CREDIT'].includes(o.order_type))
```

**Step 2: 验证编译**

```bash
cd /Users/lin/Desktop/erp-4/frontend && npx vite build --outDir ../backend/static 2>&1 | tail -5
```

---

### Task 2: FinanceOrdersTab — 新增退货状态与 UI

**Files:**
- Modify: `frontend/src/components/business/finance/FinanceOrdersTab.vue`

这是最核心的改动，分为多个 Step。

**Step 1: 添加 import**

在 `<script setup>` 的 import 区域（约 line 426-437），增加：

```javascript
import { createOrder } from '../../../api/orders'
import { getLocations } from '../../../api/warehouses'
```

**Step 2: 添加退货相关 reactive 状态**

在 `// --- 取消订单相关状态 ---` 注释之前（约 line 486 附近），添加：

```javascript
// --- 退货相关状态 ---
/** 是否显示退货表单 */
const showReturnForm = ref(false)
/** 退货表单数据 */
const returnForm = reactive({
  items: [],       // [{ product_id, product_name, product_sku, unit_price, cost_price, max_qty, qty }]
  refunded: false, // 已退款给客户
})
/** 退货提交中 */
const returnSubmitting = ref(false)
```

**Step 3: 添加退货辅助 computed**

在退货状态后面添加：

```javascript
/** 当前订单是否可发起退货 */
const canReturn = computed(() => {
  if (!orderDetail.order_type) return false
  if (!['CASH', 'CREDIT'].includes(orderDetail.order_type)) return false
  if (orderDetail.shipping_status === 'cancelled') return false
  return orderDetail.items?.some(i => i.available_return_quantity > 0)
})

/** 退货表单是否可提交 */
const canSubmitReturn = computed(() => {
  return returnForm.items.some(i => i.qty > 0)
})
```

**Step 4: 添加退货操作函数**

在 `// ===== 取消订单 =====` 注释之前添加：

```javascript
// ===== 销售退货 =====
/** 打开退货表单 */
const openReturnForm = () => {
  returnForm.items = orderDetail.items
    .filter(i => i.available_return_quantity > 0)
    .map(i => ({
      product_id: i.product_id,
      product_name: i.product_name,
      product_sku: i.product_sku,
      unit_price: i.unit_price,
      cost_price: i.cost_price,
      max_qty: i.available_return_quantity,
      qty: 0
    }))
  returnForm.refunded = false
  showReturnForm.value = true
}

/** 提交退货 */
const submitReturn = async () => {
  const items = returnForm.items.filter(i => i.qty > 0)
  if (!items.length) {
    appStore.showToast('请至少选择一件退货商品', 'error')
    return
  }
  // 校验数量
  for (const item of items) {
    if (item.qty > item.max_qty) {
      appStore.showToast(`${item.product_name} 最多可退 ${item.max_qty} 件`, 'error')
      return
    }
  }

  returnSubmitting.value = true
  try {
    // 获取原订单仓库的第一个活跃仓位
    const warehouseId = orderDetail.warehouse?.id
    let locationId = null
    if (warehouseId) {
      try {
        const { data: locs } = await getLocations({ warehouse_id: warehouseId })
        if (locs.length) locationId = locs[0].id
      } catch {}
    }

    await createOrder({
      order_type: 'RETURN',
      customer_id: orderDetail.customer?.id,
      warehouse_id: warehouseId,
      related_order_id: orderDetail.id,
      refunded: returnForm.refunded,
      items: items.map(i => ({
        product_id: i.product_id,
        quantity: i.qty,
        unit_price: i.unit_price,
        warehouse_id: warehouseId,
        location_id: locationId,
      }))
    })

    appStore.showToast('退货单创建成功')
    showReturnForm.value = false
    showOrderDetailModal.value = false
    loadOrders()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '退货失败', 'error')
  } finally {
    returnSubmitting.value = false
  }
}

/** 取消退货表单 */
const cancelReturnForm = () => {
  showReturnForm.value = false
}
```

**Step 5: 修改订单详情弹窗底部按钮——增加「销售退货」按钮**

找到底部按钮区域（约 line 263-267）：

```html
      <!-- 底部操作按钮（独立于滚动区域） -->
      <div class="flex gap-3 px-6 py-4 border-t border-line">
        <button type="button" @click="showOrderDetailModal = false" class="btn btn-secondary flex-1">关闭</button>
        <button v-if="orderDetail.shipping_status && ['pending', 'partial'].includes(orderDetail.shipping_status)" type="button" @click="handleCancelOrder(orderDetail.id)" class="btn flex-1" style="background:var(--error);color:#fff">取消订单</button>
      </div>
```

替换为：

```html
      <!-- 底部操作按钮（独立于滚动区域） -->
      <div v-if="!showReturnForm" class="flex gap-3 px-6 py-4 border-t border-line">
        <button type="button" @click="showOrderDetailModal = false" class="btn btn-secondary flex-1">关闭</button>
        <button v-if="canReturn" type="button" @click="openReturnForm" class="btn btn-primary flex-1">销售退货</button>
        <button v-if="orderDetail.shipping_status && ['pending', 'partial'].includes(orderDetail.shipping_status)" type="button" @click="handleCancelOrder(orderDetail.id)" class="btn flex-1" style="background:var(--error);color:#fff">取消订单</button>
      </div>
```

**Step 6: 在详情弹窗 modal-body 末尾、物流信息 div 之后，加入退货表单 UI**

在 `</div>` （modal-body 关闭标签，约 line 262）之前，在物流信息区域之后插入退货表单：

```html
        <!-- 退货表单 -->
        <div v-if="showReturnForm" class="mb-2">
          <div class="flex items-center gap-2 mb-2.5">
            <span class="text-[13px] font-semibold text-secondary">退货商品</span>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-[13px]">
              <thead class="bg-elevated">
                <tr>
                  <th class="px-3 py-2 text-left text-xs font-semibold text-secondary">商品</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-secondary">单价</th>
                  <th class="px-3 py-2 text-right text-xs font-semibold text-secondary">可退</th>
                  <th class="px-3 py-2 text-center text-xs font-semibold text-secondary" style="width:100px">退货数量</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-line">
                <tr v-for="item in returnForm.items" :key="item.product_id">
                  <td class="px-3 py-2.5">
                    <div class="font-medium">{{ item.product_name }}</div>
                    <div class="text-[11px] text-muted font-mono">{{ item.product_sku }}</div>
                  </td>
                  <td class="px-3 py-2.5 text-right">{{ fmt(item.unit_price) }}</td>
                  <td class="px-3 py-2.5 text-right text-muted">{{ item.max_qty }}</td>
                  <td class="px-3 py-2.5 text-center">
                    <input type="number" v-model.number="item.qty" :min="0" :max="item.max_qty" class="input text-center" style="width:80px" />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="mt-3 px-1">
            <label class="flex items-center gap-2 cursor-pointer text-[13px]">
              <input type="checkbox" v-model="returnForm.refunded" class="rounded" />
              <span>已退款给客户</span>
              <span class="text-[11px] text-muted">（不勾选则形成在账资金）</span>
            </label>
          </div>
          <!-- 退货操作按钮 -->
          <div class="flex gap-3 pt-4 mt-4 border-t border-line">
            <button type="button" @click="cancelReturnForm" class="btn btn-secondary flex-1">取消</button>
            <button type="button" @click="submitReturn" :disabled="!canSubmitReturn || returnSubmitting" class="btn btn-primary flex-1">
              {{ returnSubmitting ? '提交中...' : '确认退货' }}
            </button>
          </div>
        </div>
```

**Step 7: 关闭详情弹窗时重置退货表单**

在关闭弹窗的地方，确保退货表单也被重置。修改 modal-overlay 的 `@click.self`（line 117）：

将 `@click.self="showOrderDetailModal = false"` 改为 `@click.self="showOrderDetailModal = false; showReturnForm = false"`

同样修改关闭按钮（line 121）的 `@click`：

将 `@click="showOrderDetailModal = false"` 改为 `@click="showOrderDetailModal = false; showReturnForm = false"`

**Step 8: 验证编译**

```bash
cd /Users/lin/Desktop/erp-4/frontend && npx vite build --outDir ../backend/static 2>&1 | tail -5
```

---

### Task 3: 构建部署 + 验证

**Step 1: 前端构建**

```bash
cd /Users/lin/Desktop/erp-4/frontend && npx vite build --outDir ../backend/static
```

**Step 2: Docker 重建部署**

```bash
cd /Users/lin/Desktop/erp-4 && docker compose build erp && docker compose up -d erp
```

**Step 3: 验证场景**

在 8090 端口测试：

1. 销售页面 → 退货模式 → 搜索关联订单 → 应能正常加载订单列表（Bug 修复验证）
2. 财务订单明细 → 点击一个 CASH/CREDIT 订单 → 详情弹窗应显示「销售退货」按钮
3. 点击「销售退货」→ 展开退货表单 → 输入退货数量 → 确认退货 → 成功创建退货单
4. 已取消订单不应显示「销售退货」按钮
5. RETURN/CONSIGN_OUT 类型订单不应显示「销售退货」按钮

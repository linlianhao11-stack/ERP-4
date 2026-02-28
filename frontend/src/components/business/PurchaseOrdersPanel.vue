<template>
  <div>
    <div class="flex flex-wrap items-center gap-2 mb-3">
      <select v-model="purchaseStatusFilter" @change="loadPurchaseOrders" class="input text-sm" style="width:120px">
        <option value="">全部状态</option>
        <option value="pending_review">待审核</option>
        <option value="pending">待付款</option>
        <option value="paid">在途</option>
        <option value="partial">部分到货</option>
        <option value="completed">已完成</option>
        <option value="returned">已退货</option>
        <option value="rejected">已拒绝</option>
      </select>
      <select v-if="accountSets.length" v-model="purchaseAccountSetFilter" @change="loadPurchaseOrders" class="input text-sm" style="width:120px">
        <option value="">全部账套</option>
        <option v-for="s in accountSets" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
      <input type="date" v-model="purchaseDateStart" @change="loadPurchaseOrders" class="input text-sm" style="width:130px">
      <input type="date" v-model="purchaseDateEnd" @change="loadPurchaseOrders" class="input text-sm" style="width:130px">
      <input v-model="purchaseSearch" @input="debouncedLoadPurchaseOrders" class="input text-sm flex-1" placeholder="搜索单号/供应商..." style="min-width:120px">
      <button v-if="hasPermission('stock_edit')" @click="poNewProduct" class="btn btn-success btn-sm">新建商品</button>
      <button @click="openNewPO" class="btn btn-primary btn-sm" v-if="hasPermission('purchase')">新建采购单</button>
      <button @click="openPurchaseReceive" class="btn btn-success btn-sm" v-if="hasPermission('purchase_receive')">采购收货</button>
      <button @click="handleExportPurchaseOrders" class="btn btn-secondary btn-sm hidden md:inline-block">导出Excel</button>
    </div>

    <!-- Mobile cards -->
    <div class="md:hidden space-y-2">
      <div v-for="o in purchaseOrders" :key="o.id" class="card p-3" @click="viewPurchaseOrder(o.id)">
        <div class="flex justify-between items-start mb-1">
          <div class="font-medium text-sm font-mono">{{ o.po_no }}</div>
          <div class="text-lg font-bold text-[#0071e3]">¥{{ fmt(o.total_amount) }}</div>
        </div>
        <div class="flex justify-between items-center text-xs">
          <div class="text-[#86868b]">{{ o.supplier_name }}</div>
          <StatusBadge type="purchaseStatus" :status="o.status" />
        </div>
        <div class="text-xs text-[#86868b] mt-1">{{ fmtDate(o.created_at) }} · {{ o.creator_name }}</div>
      </div>
      <div v-if="!purchaseOrders.length" class="p-8 text-center text-[#86868b] text-sm">暂无采购订单</div>
    </div>

    <!-- Desktop table -->
    <div class="card hidden md:block">
      <div class="table-container">
        <table class="w-full text-sm">
          <thead class="bg-[#f5f5f7]">
            <tr>
              <th class="px-3 py-2 text-left">采购单号</th>
              <th class="px-3 py-2 text-left">供应商</th>
              <th class="px-3 py-2 text-right">总金额</th>
              <th class="px-3 py-2 text-center">状态</th>
              <th class="px-3 py-2 text-left">创建人</th>
              <th class="px-3 py-2 text-left">创建时间</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-for="o in purchaseOrders" :key="o.id" class="hover:bg-[#f5f5f7] cursor-pointer" @click="viewPurchaseOrder(o.id)">
              <td class="px-3 py-2 font-mono text-sm">{{ o.po_no }}</td>
              <td class="px-3 py-2">{{ o.supplier_name }}</td>
              <td class="px-3 py-2 text-right font-semibold">¥{{ fmt(o.total_amount) }}</td>
              <td class="px-3 py-2 text-center">
                <StatusBadge type="purchaseStatus" :status="o.status" />
              </td>
              <td class="px-3 py-2 text-[#6e6e73]">{{ o.creator_name }}</td>
              <td class="px-3 py-2 text-[#86868b] text-xs">{{ fmtDate(o.created_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!purchaseOrders.length" class="p-8 text-center text-[#86868b] text-sm">暂无采购订单</div>
    </div>

    <!-- New PO Modal -->
    <div v-if="showPOCreateModal" class="modal-overlay active" @click.self="showPOCreateModal = false">
      <div class="modal-content" style="max-width:700px">
        <div class="modal-header">
          <h3 class="modal-title">新建采购订单</h3>
          <button @click="showPOCreateModal = false" class="modal-close">&times;</button>
        </div>
        <div class="space-y-4 p-4">
          <div class="grid form-grid grid-cols-2 gap-3">
            <div class="relative">
              <label class="label">供应商 *</label>
              <input
                v-model="poSupplierSearch"
                @input="poSupplierDropdown = true"
                @focus="poSupplierDropdown = true"
                @blur="setTimeout(() => poSupplierDropdown = false, 200)"
                class="input"
                placeholder="输入供应商名称搜索..."
                autocomplete="off"
              >
              <div v-if="poSupplierDropdown && filteredPoSuppliers.length" class="absolute z-50 left-0 right-0 bg-white border rounded-lg shadow-lg max-h-48 overflow-y-auto mt-1">
                <div v-for="s in filteredPoSuppliers" :key="s.id" @mousedown.prevent="selectPoSupplier(s)" class="px-3 py-2 hover:bg-[#e8f4fd] cursor-pointer text-sm">
                  {{ s.name }}
                  <span v-if="s.contact_person" class="text-[#86868b] text-xs ml-1">({{ s.contact_person }})</span>
                </div>
              </div>
            </div>
            <div>
              <label class="label">目标仓库 *</label>
              <select v-model="poForm.target_warehouse_id" class="input" required>
                <option value="">选择仓库</option>
                <option v-for="w in warehouses.filter(x => !x.is_virtual)" :key="w.id" :value="w.id">{{ w.name }}</option>
              </select>
            </div>
          </div>
          <div>
            <label class="label">目标仓位</label>
            <select v-model="poForm.target_location_id" class="input" :disabled="!poForm.target_warehouse_id">
              <option value="">{{ poForm.target_warehouse_id ? '选择仓位（可选）' : '请先选择仓库' }}</option>
              <option v-for="loc in poTargetLocations" :key="loc.id" :value="loc.id">{{ loc.code }}{{ loc.name ? ' - ' + loc.name : '' }}</option>
            </select>
          </div>
          <div v-if="accountSets.length">
            <label class="label">财务账套</label>
            <select v-model="poForm.account_set_id" class="input">
              <option :value="null">不指定</option>
              <option v-for="s in accountSets" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
            <div v-if="poForm.account_set_id" class="text-xs text-[#86868b] mt-1">选择仓库后将自动带入关联账套，也可手动修改</div>
            <div v-else class="text-xs text-[#ff9500] mt-1">未选择财务账套，收货后将不会自动生成财务单据（应付单/入库单）</div>
          </div>

          <!-- Items -->
          <div class="border-t pt-3">
            <div class="flex justify-between items-center mb-2">
              <span class="font-semibold text-sm">商品明细</span>
              <button type="button" @click="poAddItem" class="btn btn-secondary btn-sm text-xs">+ 添加商品</button>
            </div>
            <div v-for="(item, idx) in poForm.items" :key="idx" class="p-3 bg-[#f5f5f7] rounded-lg mb-2">
              <div class="flex justify-between items-center mb-2">
                <span class="text-xs font-semibold text-[#86868b]">#{{ idx + 1 }}</span>
                <button type="button" @click="poRemoveItem(idx)" class="text-[#ff3b30] text-xs" v-if="poForm.items.length > 1">删除</button>
              </div>
              <div class="mb-2 relative">
                <label class="label text-xs">商品</label>
                <input
                  v-model="item._search"
                  @input="item._dropdownOpen = true"
                  @focus="item._dropdownOpen = true"
                  @blur="setTimeout(() => item._dropdownOpen = false, 200)"
                  class="input text-sm"
                  placeholder="输入SKU或商品名搜索..."
                  autocomplete="off"
                >
                <div v-if="item._dropdownOpen && poFilteredProducts(item._search).length" class="absolute z-50 left-0 right-0 bg-white border rounded-lg shadow-lg max-h-48 overflow-y-auto mt-1">
                  <div v-for="p in poFilteredProducts(item._search)" :key="p.id" @mousedown.prevent="poPickProduct(item, p)" class="px-3 py-2 hover:bg-[#e8f4fd] cursor-pointer text-sm">
                    <span class="font-mono text-[#86868b]">{{ p.sku }}</span> <span>{{ p.name }}</span>
                    <span v-if="p.brand" class="text-[#86868b] text-xs ml-1">[{{ p.brand }}]</span>
                  </div>
                </div>
              </div>
              <div class="grid grid-cols-3 gap-2 mb-2">
                <div>
                  <label class="label text-xs">含税单价</label>
                  <input v-model.number="item.tax_inclusive_price" type="number" step="0.01" class="input text-sm" @input="poCalcItem(item)">
                </div>
                <div>
                  <label class="label text-xs">税率</label>
                  <select v-model.number="item.tax_rate" class="input text-sm" @change="poCalcItem(item)">
                    <option :value="0.13">13%</option>
                    <option :value="0.09">9%</option>
                    <option :value="0.06">6%</option>
                    <option :value="0.03">3%</option>
                    <option :value="0">0%</option>
                  </select>
                </div>
                <div>
                  <label class="label text-xs">数量</label>
                  <input v-model.number="item.quantity" type="number" min="1" class="input text-sm" @input="poCalcItem(item)">
                </div>
              </div>
              <div class="flex justify-between text-xs text-[#86868b]">
                <span>未税单价: ¥{{ item.tax_exclusive_price.toFixed(2) }}</span>
                <span v-if="item.rebate_amount > 0" class="text-[#34c759]">返利: -¥{{ item.rebate_amount.toFixed(2) }}</span>
                <span class="font-semibold text-[#1d1d1f]">小计: ¥{{ (item.amount - (item.rebate_amount || 0)).toFixed(2) }}</span>
              </div>
            </div>
          </div>

          <!-- Rebate -->
          <div v-if="poForm.supplier_rebate_balance > 0" class="border-t pt-3">
            <label class="flex items-center cursor-pointer mb-2">
              <input type="checkbox" v-model="poForm.use_rebate" class="mr-2 w-4 h-4" @change="!poForm.use_rebate && poForm.items.forEach(i => i.rebate_amount = 0)">
              <span class="font-medium text-sm">使用返利</span>
              <span class="text-xs text-[#34c759] ml-2">可用: ¥{{ fmt(poForm.supplier_rebate_balance) }}</span>
            </label>
            <div v-if="poForm.use_rebate" class="space-y-2">
              <div v-for="(item, idx) in poForm.items.filter(i => i.product_id)" :key="idx" class="flex items-center gap-2 text-sm bg-[#f5f5f7] rounded p-2">
                <span class="flex-1 truncate">{{ item._search || '商品' + (idx + 1) }}</span>
                <span class="text-[#86868b]">¥{{ item.amount.toFixed(2) }}</span>
                <input v-model.number="item.rebate_amount" type="number" step="0.01" min="0" :max="item.amount" class="w-24 text-right border rounded px-2 py-1 text-sm" placeholder="返利">
              </div>
              <div class="flex justify-between text-sm mt-1">
                <span class="text-[#34c759]">返利总额: <b>¥{{ fmt(poForm.items.reduce((s, i) => s + (i.rebate_amount || 0), 0)) }}</b></span>
                <span v-if="poForm.items.reduce((s, i) => s + (i.rebate_amount || 0), 0) > poForm.supplier_rebate_balance" class="text-[#ff3b30] text-xs">超过可用余额!</span>
              </div>
            </div>
          </div>

          <!-- Credit -->
          <div v-if="poForm.supplier_credit_balance > 0" class="border-t pt-3">
            <label class="flex items-center cursor-pointer mb-2">
              <input type="checkbox" v-model="poForm.use_credit" class="mr-2 w-4 h-4">
              <span class="font-medium text-sm">使用在账资金</span>
              <span class="text-xs text-[#0071e3] ml-2">可用: ¥{{ fmt(poForm.supplier_credit_balance) }}</span>
            </label>
            <div v-if="poForm.use_credit" class="flex items-center gap-2">
              <label class="text-sm text-[#6e6e73]">抵扣金额:</label>
              <input v-model.number="poForm.credit_amount" type="number" step="0.01" min="0"
                :max="poForm.supplier_credit_balance" class="input text-sm w-40" placeholder="输入抵扣金额">
              <span v-if="poForm.credit_amount > poForm.supplier_credit_balance" class="text-[#ff3b30] text-xs">超过可用余额!</span>
            </div>
          </div>

          <!-- Total -->
          <div class="border-t pt-3 flex justify-between items-center">
            <div class="text-sm">
              含税总额: <span class="text-xl font-bold text-[#0071e3]">¥{{ poFinalAmount.toFixed(2) }}</span>
              <span v-if="(poForm.use_rebate && poRebateTotal > 0) || (poForm.use_credit && poForm.credit_amount > 0)" class="text-xs text-[#86868b] ml-2">
                (原价 ¥{{ poTotal.toFixed(2) }}
                <template v-if="poForm.use_rebate && poRebateTotal > 0"> - 返利 ¥{{ poRebateTotal.toFixed(2) }}</template>
                <template v-if="poForm.use_credit && poForm.credit_amount > 0"> - 在账 ¥{{ poForm.credit_amount.toFixed(2) }}</template>)
              </span>
            </div>
          </div>
          <div>
            <label class="label">备注</label>
            <input v-model="poForm.remark" class="input" placeholder="可选">
          </div>
          <div class="flex gap-3 pt-2">
            <button type="button" @click="showPOCreateModal = false" class="btn btn-secondary flex-1">取消</button>
            <button type="button" @click="savePurchaseOrder" class="btn btn-primary flex-1" :disabled="appStore.submitting">{{ appStore.submitting ? '提交中...' : '确认提交' }}</button>
          </div>
        </div>
      </div>
    </div>

    <!-- PO Detail Modal -->
    <div v-if="showPODetailModal && purchaseOrderDetail" class="modal-overlay active" @click.self="showPODetailModal = false">
      <div class="modal-content" style="max-width:700px">
        <div class="modal-header">
          <h3 class="modal-title">采购订单详情</h3>
          <button @click="showPODetailModal = false" class="modal-close">&times;</button>
        </div>
        <div class="space-y-4 p-4">
          <div class="grid grid-cols-2 gap-3 text-sm">
            <div><span class="text-[#86868b]">采购单号:</span> <span class="font-mono font-semibold">{{ purchaseOrderDetail.po_no }}</span></div>
            <div><span class="text-[#86868b]">状态:</span> <StatusBadge type="purchaseStatus" :status="purchaseOrderDetail.status" /></div>
            <div><span class="text-[#86868b]">供应商:</span> {{ purchaseOrderDetail.supplier_name }}</div>
            <div><span class="text-[#86868b]">总金额:</span> <span class="font-semibold text-[#0071e3]">¥{{ fmt(purchaseOrderDetail.total_amount) }}</span></div>
            <div v-if="purchaseOrderDetail.rebate_used > 0"><span class="text-[#86868b]">已使用返利:</span> <span class="text-[#34c759] font-semibold">¥{{ fmt(purchaseOrderDetail.rebate_used) }}</span></div>
            <div v-if="purchaseOrderDetail.credit_used > 0"><span class="text-[#86868b]">在账资金抵扣:</span> <span class="text-[#0071e3] font-semibold">¥{{ fmt(purchaseOrderDetail.credit_used) }}</span></div>
            <div><span class="text-[#86868b]">创建人:</span> {{ purchaseOrderDetail.creator_name }}</div>
            <div><span class="text-[#86868b]">创建时间:</span> {{ fmtDate(purchaseOrderDetail.created_at) }}</div>
            <div v-if="purchaseOrderDetail.reviewed_by_name"><span class="text-[#86868b]">审核人:</span> {{ purchaseOrderDetail.reviewed_by_name }} {{ fmtDate(purchaseOrderDetail.reviewed_at) }}</div>
            <div v-if="purchaseOrderDetail.paid_by_name"><span class="text-[#86868b]">付款确认:</span> {{ purchaseOrderDetail.paid_by_name }} {{ fmtDate(purchaseOrderDetail.paid_at) }}</div>
            <div v-if="purchaseOrderDetail.remark"><span class="text-[#86868b]">备注:</span> {{ purchaseOrderDetail.remark }}</div>
          </div>
          <!-- 退货信息 -->
          <div v-if="purchaseOrderDetail.return_amount > 0" class="bg-[#fff3e0] border border-[#ffcc80] rounded-lg p-3">
            <h4 class="font-semibold text-sm text-[#ff9f0a] mb-2">退货信息</h4>
            <div class="grid grid-cols-2 gap-2 text-sm">
              <div><span class="text-[#86868b]">退货金额:</span> <span class="font-semibold text-[#ff9f0a]">¥{{ fmt(purchaseOrderDetail.return_amount) }}</span></div>
              <div><span class="text-[#86868b]">退款状态:</span> <span :class="purchaseOrderDetail.is_refunded ? 'text-[#34c759]' : 'text-[#d70015]'">{{ purchaseOrderDetail.is_refunded ? '已退款' : '转为在账资金' }}</span></div>
              <div v-if="purchaseOrderDetail.return_tracking_no"><span class="text-[#86868b]">退货物流:</span> {{ purchaseOrderDetail.return_tracking_no }}</div>
              <div v-if="purchaseOrderDetail.returned_by_name"><span class="text-[#86868b]">处理人:</span> {{ purchaseOrderDetail.returned_by_name }} {{ fmtDate(purchaseOrderDetail.returned_at) }}</div>
            </div>
          </div>
          <div class="border-t pt-3">
            <h4 class="font-semibold text-sm mb-2">商品明细</h4>
            <div class="table-container">
              <table class="w-full text-xs">
                <thead class="bg-[#f5f5f7]">
                  <tr>
                    <th class="px-2 py-1 text-left">商品</th>
                    <th class="px-2 py-1 text-right">含税单价</th>
                    <th class="px-2 py-1 text-right">数量</th>
                    <th v-if="purchaseOrderDetail.rebate_used > 0" class="px-2 py-1 text-right">返利</th>
                    <th class="px-2 py-1 text-right">金额</th>
                    <th class="px-2 py-1 text-center">收货进度</th>
                    <th v-if="purchaseOrderDetail.return_amount > 0 || purchaseOrderDetail.status === 'completed'" class="px-2 py-1 text-center">退货</th>
                  </tr>
                </thead>
                <tbody class="divide-y">
                  <tr v-for="it in purchaseOrderDetail.items" :key="it.id">
                    <td class="px-2 py-1">
                      <div class="font-medium">{{ it.product_name }}</div>
                      <div class="text-[#86868b] font-mono">{{ it.product_sku }}</div>
                    </td>
                    <td class="px-2 py-1 text-right">¥{{ fmt(it.tax_inclusive_price) }}</td>
                    <td class="px-2 py-1 text-right">{{ it.quantity }}</td>
                    <td v-if="purchaseOrderDetail.rebate_used > 0" class="px-2 py-1 text-right text-[#34c759]">{{ it.rebate_amount > 0 ? '-¥' + fmt(it.rebate_amount) : '' }}</td>
                    <td class="px-2 py-1 text-right font-semibold">¥{{ fmt(it.amount) }}</td>
                    <td class="px-2 py-1 text-center">
                      <span :class="it.received_quantity >= it.quantity ? 'text-[#34c759]' : 'text-[#ff9f0a]'">{{ it.received_quantity }}/{{ it.quantity }}</span>
                    </td>
                    <td v-if="purchaseOrderDetail.return_amount > 0 || purchaseOrderDetail.status === 'completed'" class="px-2 py-1 text-center">
                      <span v-if="it.returned_quantity > 0" class="text-[#ff9f0a]">{{ it.returned_quantity }}</span>
                      <span v-else class="text-[#d2d2d7]">-</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div class="flex gap-3 pt-2 flex-wrap">
            <button v-if="purchaseOrderDetail.status === 'pending_review' && hasPermission('purchase_approve')" @click="handleApprovePO(purchaseOrderDetail.id)" class="btn flex-1" style="background:#0071e3;color:#fff">审核通过</button>
            <button v-if="purchaseOrderDetail.status === 'pending_review' && hasPermission('purchase_approve')" @click="handleRejectPO(purchaseOrderDetail.id)" class="btn flex-1" style="background:#ff3b30;color:#fff">拒绝</button>
            <button v-if="['paid','partial'].includes(purchaseOrderDetail.status) && hasPermission('purchase_receive')" @click="openReceiveFromDetail(purchaseOrderDetail.id)" class="btn btn-success flex-1">采购收货</button>
            <button v-if="purchaseOrderDetail.status === 'completed' && hasPermission('purchase')" @click="openReturnModal(purchaseOrderDetail)" class="btn flex-1" style="background:#ff9f0a;color:#fff">采购退货</button>
            <button @click="showPODetailModal = false" class="btn btn-secondary flex-1">关闭</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Purchase Receive Modal -->
    <div v-if="showReceiveModal" class="modal-overlay active" @click.self="showReceiveModal = false">
      <div class="modal-content" style="max-width:700px">
        <div class="modal-header">
          <h3 class="modal-title">采购收货</h3>
          <button @click="showReceiveModal = false" class="modal-close">&times;</button>
        </div>
        <div class="space-y-4 p-4">
          <div v-if="!receivablePOs.length" class="p-8 text-center text-[#86868b]">暂无可收货的采购订单</div>
          <div v-for="po in receivablePOs" :key="po.id" class="border rounded-lg p-3">
            <div class="flex justify-between items-center mb-2 cursor-pointer" @click="receiveForm.po_id === po.id ? receiveForm.po_id = null : initReceiveItems(po)">
              <div>
                <span class="font-mono font-semibold text-sm">{{ po.po_no }}</span>
                <span class="text-[#86868b] text-xs ml-2">{{ po.supplier_name }}</span>
              </div>
              <div class="flex items-center gap-2">
                <StatusBadge type="purchaseStatus" :status="po.status" />
                <span class="text-sm font-semibold">¥{{ fmt(po.total_amount) }}</span>
                <span class="text-[#86868b]">{{ receiveForm.po_id === po.id ? '&#9650;' : '&#9660;' }}</span>
              </div>
            </div>
            <div v-if="receiveForm.po_id === po.id" class="space-y-2 border-t pt-2">
              <div v-for="(item, idx) in receiveForm.items" :key="item.item_id" class="p-2 bg-[#f5f5f7] rounded">
                <div class="flex items-center gap-2 mb-1">
                  <label class="flex items-center text-sm">
                    <input type="checkbox" v-model="item.checked" class="mr-1">
                    {{ item.product_name }}
                  </label>
                  <span class="text-xs text-[#86868b] ml-auto">
                    待收:{{ item.pending_qty }}
                    <template v-if="item.checked && item.splits.length > 1">
                      | 已分配:<span :class="getSplitTotal(item) > item.pending_qty ? 'text-[#ff3b30] font-semibold' : 'text-[#34c759]'">{{ getSplitTotal(item) }}</span>
                    </template>
                  </span>
                </div>
                <div v-if="item.checked" class="space-y-2 mt-1">
                  <div v-for="(sp, si) in item.splits" :key="sp.id"
                    :class="['space-y-2', item.splits.length > 1 ? 'border border-[#b3d7f5] rounded p-2 bg-white' : '']">
                    <div class="flex items-center justify-between" v-if="item.splits.length > 1">
                      <span class="text-xs font-semibold text-[#0071e3]">分组 {{ si + 1 }}</span>
                      <button @click="removeSplit(item, si)" class="text-xs text-[#ff6961] hover:text-[#ff3b30]">删除</button>
                    </div>
                    <div class="grid grid-cols-3 gap-2">
                      <div>
                        <label class="text-xs text-[#86868b]">本次收货</label>
                        <input v-model.number="sp.receive_quantity" type="number" :max="item.pending_qty" min="1"
                          :class="['input text-sm', getSplitTotal(item) > item.pending_qty ? 'border-[#ff6961]' : '']">
                      </div>
                      <div>
                        <label class="text-xs text-[#86868b]">仓库</label>
                        <select v-model="sp.warehouse_id" @change="handleSplitWarehouseChange(item, sp)" class="input text-sm">
                          <option value="">选择</option>
                          <option v-for="w in warehouses.filter(x => !x.is_virtual)" :key="w.id" :value="w.id">{{ w.name }}</option>
                        </select>
                      </div>
                      <div>
                        <label class="text-xs text-[#86868b]">仓位</label>
                        <select v-model="sp.location_id" class="input text-sm" :disabled="!sp.warehouse_id">
                          <option value="">{{ sp.warehouse_id ? '选择' : '先选仓库' }}</option>
                          <option v-for="loc in getReceiveLocations(sp.warehouse_id)" :key="loc.id" :value="loc.id">{{ loc.code }}</option>
                        </select>
                      </div>
                    </div>
                    <div v-if="sp.sn_required" class="bg-[#fff8e1] border border-[#ffe082] rounded p-2">
                      <label class="text-xs font-semibold">
                        SN码 *
                        <span :class="parseSnCodes(sp.sn_input).length === Number(sp.receive_quantity || 0) ? 'text-[#34c759]' : 'text-[#ff3b30]'">
                          ({{ parseSnCodes(sp.sn_input).length }} / {{ sp.receive_quantity || 0 }})
                        </span>
                      </label>
                      <textarea v-model="sp.sn_input" class="input text-xs mt-1" rows="2" placeholder="每行一个SN码，或用逗号/空格分隔"></textarea>
                    </div>
                  </div>
                  <div class="flex items-center justify-between">
                    <button @click="addSplit(item)" class="text-xs text-[#0071e3] hover:text-[#0077ED]">+ 拆分到其他仓库</button>
                    <span v-if="item.splits.length > 1" class="text-xs" :class="getSplitRemaining(item) < 0 ? 'text-[#ff3b30]' : 'text-[#86868b]'">
                      剩余未分配: {{ getSplitRemaining(item) }}
                    </span>
                  </div>
                </div>
              </div>
              <div class="flex gap-3 pt-2">
                <button @click="showReceiveModal = false" class="btn btn-secondary flex-1">取消</button>
                <button @click="confirmReceive" class="btn btn-success flex-1" :disabled="appStore.submitting">{{ appStore.submitting ? '提交中...' : '确认收货入库' }}</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- New Product Modal -->
    <div v-if="showProductModal" class="modal-overlay active" @click.self="showProductModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="modal-title">新建商品</h3>
          <button @click="showProductModal = false" class="modal-close">&times;</button>
        </div>
        <form @submit.prevent="saveProduct" class="space-y-3 p-4">
          <div><label class="label">SKU *</label><input v-model="productForm.sku" class="input" required placeholder="商品SKU"></div>
          <div><label class="label">名称 *</label><input v-model="productForm.name" class="input" required placeholder="商品名称"></div>
          <div class="grid form-grid grid-cols-2 gap-3">
            <div><label class="label">品牌</label><input v-model="productForm.brand" class="input" placeholder="品牌"></div>
            <div><label class="label">分类</label><input v-model="productForm.category" class="input" placeholder="分类"></div>
          </div>
          <div class="grid form-grid grid-cols-2 gap-3">
            <div><label class="label">零售价</label><input v-model.number="productForm.retail_price" type="number" step="0.01" class="input"></div>
            <div><label class="label">成本价</label><input v-model.number="productForm.cost_price" type="number" step="0.01" class="input"></div>
          </div>
          <div class="flex gap-3 pt-3">
            <button type="button" @click="showProductModal = false" class="btn btn-secondary flex-1">取消</button>
            <button type="submit" class="btn btn-primary flex-1">保存</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Return Modal -->
    <div v-if="showReturnModal" class="modal-overlay active" @click.self="showReturnModal = false">
      <div class="modal-content" style="max-width:600px">
        <div class="modal-header">
          <h3 class="modal-title">采购退货 - {{ returnForm.po_no }}</h3>
          <button @click="showReturnModal = false" class="modal-close">&times;</button>
        </div>
        <div class="space-y-4 p-4">
          <div v-for="item in returnForm.items" :key="item.item_id" class="p-3 bg-[#f5f5f7] rounded-lg">
            <label class="flex items-center gap-2 mb-2">
              <input type="checkbox" v-model="item.checked" class="w-4 h-4">
              <span class="font-medium text-sm">{{ item.product_name }}</span>
              <span class="text-xs text-[#86868b] ml-auto">可退: {{ item.returnable_qty }}</span>
            </label>
            <div v-if="item.checked" class="flex items-center gap-3">
              <label class="text-xs text-[#86868b]">退货数量:</label>
              <input v-model.number="item.return_quantity" type="number" min="1" :max="item.returnable_qty" class="input text-sm w-24">
              <span class="text-xs text-[#86868b]">单价: ¥{{ fmt(item.unit_amount) }}</span>
              <span class="text-sm font-semibold text-[#ff9f0a] ml-auto">¥{{ (item.return_quantity * item.unit_amount).toFixed(2) }}</span>
            </div>
          </div>
          <div class="border-t pt-3 space-y-3">
            <label class="flex items-center gap-2">
              <input type="checkbox" v-model="returnForm.is_refunded" class="w-4 h-4">
              <span class="text-sm">供应商已退款</span>
            </label>
            <div v-if="!returnForm.is_refunded" class="text-xs text-[#0071e3] bg-[#e8f4fd] rounded p-2">
              未退款的金额将转为供应商"在账资金"，可在后续采购单中抵扣
            </div>
            <div>
              <label class="label text-xs">退货物流单号（选填）</label>
              <input v-model="returnForm.tracking_no" class="input text-sm" placeholder="退货物流单号">
            </div>
            <div class="flex justify-between items-center text-sm">
              <span>退货总金额:</span>
              <span class="text-xl font-bold text-[#ff9f0a]">¥{{ returnTotalAmount.toFixed(2) }}</span>
            </div>
          </div>
          <div class="flex gap-3 pt-2">
            <button @click="showReturnModal = false" class="btn btn-secondary flex-1">取消</button>
            <button @click="confirmReturn" class="btn flex-1" style="background:#ff9f0a;color:#fff" :disabled="appStore.submitting">{{ appStore.submitting ? '处理中...' : '确认退货' }}</button>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '../../stores/app'
import { useProductsStore } from '../../stores/products'
import { useWarehousesStore } from '../../stores/warehouses'
import { useFormat } from '../../composables/useFormat'
import { usePermission } from '../../composables/usePermission'
import {
  getSuppliers,
  getPurchaseOrders, getPurchaseOrder, createPurchaseOrder,
  exportPurchaseOrders as exportPurchaseOrdersApi, getReceivablePOs,
  approvePurchaseOrder, rejectPurchaseOrder,
  receivePurchaseOrder,
  returnPurchaseOrder
} from '../../api/purchase'
import { getAccountSets } from '../../api/accounting'
import { checkSnRequired } from '../../api/sn'
import { parseSnCodes } from '../../utils/helpers'
import api from '../../api/index'
import StatusBadge from '../common/StatusBadge.vue'

const emit = defineEmits(['data-changed'])

const appStore = useAppStore()
const productsStore = useProductsStore()
const warehousesStore = useWarehousesStore()
const { fmt, fmtDate } = useFormat()
const { hasPermission } = usePermission()
const products = computed(() => productsStore.products)
const warehouses = computed(() => warehousesStore.warehouses)

// Orders state
const purchaseOrders = ref([])
const purchaseStatusFilter = ref('')
const purchaseAccountSetFilter = ref('')
const purchaseDateStart = ref('')
const purchaseDateEnd = ref('')
const purchaseSearch = ref('')

// Account sets (for PO create dropdown)
const accountSets = ref([])

// Suppliers (for PO create dropdown)
const suppliers = ref([])

// Modal visibility
const showPOCreateModal = ref(false)
const showPODetailModal = ref(false)
const showReceiveModal = ref(false)
const showProductModal = ref(false)
const showReturnModal = ref(false)

// PO form
const poForm = reactive({
  supplier_id: '', target_warehouse_id: '', target_location_id: '',
  remark: '', items: [], use_rebate: false, supplier_rebate_balance: 0,
  use_credit: false, supplier_credit_balance: 0, credit_amount: 0,
  account_set_id: null
})
const poSupplierSearch = ref('')
const poSupplierDropdown = ref(false)

// PO detail
const purchaseOrderDetail = ref(null)

// Receive form
const receiveForm = reactive({ po_id: null, items: [] })
const receivablePOs = ref([])

// Product form
const productForm = reactive({
  sku: '', name: '', brand: '', category: '', retail_price: null, cost_price: null
})

// Return form
const returnForm = reactive({ po_id: null, po_no: '', items: [], is_refunded: false, tracking_no: '' })

// Computed
const filteredPoSuppliers = computed(() => {
  const q = poSupplierSearch.value.trim().toLowerCase()
  if (!q) return suppliers.value
  return suppliers.value.filter(s =>
    s.name.toLowerCase().includes(q) ||
    (s.contact_person && s.contact_person.toLowerCase().includes(q))
  )
})

const poTotal = computed(() => Math.round(poForm.items.reduce((s, i) => s + i.amount, 0) * 100) / 100)
const poRebateTotal = computed(() => Math.round(poForm.items.reduce((s, i) => s + (i.rebate_amount || 0), 0) * 100) / 100)
const poFinalAmount = computed(() => {
  let amount = poTotal.value
  if (poForm.use_rebate) amount -= poRebateTotal.value
  if (poForm.use_credit && poForm.credit_amount > 0) amount -= poForm.credit_amount
  return Math.max(0, amount)
})
const returnTotalAmount = computed(() => {
  return Math.round(returnForm.items
    .filter(i => i.checked && i.return_quantity > 0)
    .reduce((s, i) => s + i.return_quantity * i.unit_amount, 0) * 100) / 100
})

const poTargetLocations = computed(() => {
  if (!poForm.target_warehouse_id) return []
  return warehousesStore.getLocationsByWarehouse(poForm.target_warehouse_id)
})

const getReceiveLocations = (warehouseId) => {
  if (!warehouseId) return []
  return warehousesStore.getLocationsByWarehouse(warehouseId)
}

// Reset location and auto-fill account_set when warehouse changes
watch(() => poForm.target_warehouse_id, (whId) => {
  poForm.target_location_id = ''
  if (whId) {
    const wh = warehouses.value.find(w => w.id === parseInt(whId))
    if (wh?.account_set_id) poForm.account_set_id = wh.account_set_id
    else poForm.account_set_id = null
  }
})

// Data loading
let _poSearchTimer = null
const debouncedLoadPurchaseOrders = () => {
  clearTimeout(_poSearchTimer)
  _poSearchTimer = setTimeout(loadPurchaseOrders, 300)
}

const loadPurchaseOrders = async () => {
  try {
    const params = {}
    if (purchaseStatusFilter.value) params.status = purchaseStatusFilter.value
    if (purchaseDateStart.value) params.start_date = purchaseDateStart.value
    if (purchaseDateEnd.value) params.end_date = purchaseDateEnd.value
    if (purchaseSearch.value) params.search = purchaseSearch.value
    if (purchaseAccountSetFilter.value) params.account_set_id = purchaseAccountSetFilter.value
    const { data } = await getPurchaseOrders(params)
    purchaseOrders.value = data
  } catch (e) {
    console.error(e)
  }
}

const loadSuppliers = async () => {
  try {
    const { data } = await getSuppliers()
    suppliers.value = data
  } catch (e) {
    console.error(e)
  }
}

// Export
const handleExportPurchaseOrders = async () => {
  try {
    const params = {}
    if (purchaseStatusFilter.value) params.status = purchaseStatusFilter.value
    if (purchaseDateStart.value) params.start_date = purchaseDateStart.value
    if (purchaseDateEnd.value) params.end_date = purchaseDateEnd.value
    if (purchaseSearch.value) params.search = purchaseSearch.value
    if (purchaseAccountSetFilter.value) params.account_set_id = purchaseAccountSetFilter.value
    const response = await exportPurchaseOrdersApi(params)
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', '采购订单_' + new Date().toISOString().slice(0, 19).replace(/:/g, '') + '.csv')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    appStore.showToast('导出成功')
  } catch (e) {
    appStore.showToast('导出失败', 'error')
  }
}

// PO create
const selectPoSupplier = (s) => {
  poForm.supplier_id = s.id
  poSupplierSearch.value = s.name
  poSupplierDropdown.value = false
  poForm.supplier_rebate_balance = s.rebate_balance || 0
  poForm.use_rebate = false
  poForm.supplier_credit_balance = s.credit_balance || 0
  poForm.use_credit = false
  poForm.credit_amount = 0
}

const poFilteredProducts = (query) => {
  const q = (query || '').trim().toLowerCase()
  if (!q) return products.value.slice(0, 20)
  return products.value.filter(p =>
    p.sku.toLowerCase().includes(q) ||
    p.name.toLowerCase().includes(q) ||
    (p.brand && p.brand.toLowerCase().includes(q))
  ).slice(0, 20)
}

const poPickProduct = (item, p) => {
  item.product_id = p.id
  item._search = p.sku + ' - ' + p.name
  item._dropdownOpen = false
  item.tax_inclusive_price = p.cost_price || 0
  poCalcItem(item)
}

const poNewProduct = () => {
  Object.assign(productForm, { sku: '', name: '', brand: '', category: '', retail_price: null, cost_price: null })
  showProductModal.value = true
}

const saveProduct = async () => {
  if (productForm.retail_price == null || productForm.retail_price === '') {
    appStore.showToast('请输入零售价', 'error')
    return
  }
  if (productForm.cost_price == null || productForm.cost_price === '') {
    appStore.showToast('请输入成本价', 'error')
    return
  }
  try {
    await api.post('/products', productForm)
    appStore.showToast('保存成功')
    showProductModal.value = false
    productsStore.loadProducts()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  }
}

const openNewPO = () => {
  const defaultWh = warehouses.value.find(w => w.is_default)
  Object.assign(poForm, {
    supplier_id: '',
    target_warehouse_id: defaultWh?.id || '',
    target_location_id: '',
    remark: '',
    items: [],
    use_rebate: false,
    supplier_rebate_balance: 0,
    use_credit: false,
    supplier_credit_balance: 0,
    credit_amount: 0,
    account_set_id: defaultWh?.account_set_id || null
  })
  poSupplierSearch.value = ''
  poAddItem()
  showPOCreateModal.value = true
}

const poAddItem = () => {
  poForm.items.push({
    product_id: '', _search: '', _dropdownOpen: false,
    tax_inclusive_price: 0, tax_rate: 0.13, tax_exclusive_price: 0,
    quantity: 1, amount: 0, rebate_amount: 0
  })
}

const poRemoveItem = (idx) => {
  poForm.items.splice(idx, 1)
}

const poCalcItem = (item) => {
  item.tax_exclusive_price = item.tax_rate > 0
    ? Math.round(item.tax_inclusive_price / (1 + item.tax_rate) * 100) / 100
    : item.tax_inclusive_price
  item.amount = Math.round(item.tax_inclusive_price * item.quantity * 100) / 100
}

const savePurchaseOrder = async () => {
  if (!poForm.supplier_id) {
    appStore.showToast('请选择供应商', 'error')
    return
  }
  if (!poForm.target_warehouse_id) {
    appStore.showToast('请选择目标仓库', 'error')
    return
  }
  const validItems = poForm.items.filter(i => i.product_id && i.quantity > 0 && i.tax_inclusive_price > 0)
  if (!validItems.length) {
    appStore.showToast('请添加有效的商品明细', 'error')
    return
  }
  const totalRebate = poForm.use_rebate ? poForm.items.reduce((s, i) => s + (i.rebate_amount || 0), 0) : 0
  if (poForm.use_rebate && totalRebate > poForm.supplier_rebate_balance) {
    appStore.showToast('返利总额超过可用余额', 'error')
    return
  }
  const creditAmount = poForm.use_credit ? (poForm.credit_amount || 0) : 0
  if (poForm.use_credit && creditAmount > poForm.supplier_credit_balance) {
    appStore.showToast('在账资金抵扣超过可用余额', 'error')
    return
  }
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    const { data } = await createPurchaseOrder({
      supplier_id: parseInt(poForm.supplier_id),
      target_warehouse_id: parseInt(poForm.target_warehouse_id),
      target_location_id: poForm.target_location_id ? parseInt(poForm.target_location_id) : null,
      remark: poForm.remark || null,
      rebate_amount: totalRebate > 0 ? totalRebate : null,
      credit_amount: creditAmount > 0 ? creditAmount : null,
      account_set_id: poForm.account_set_id || null,
      items: validItems.map(i => ({
        product_id: parseInt(i.product_id),
        quantity: parseInt(i.quantity),
        tax_inclusive_price: i.tax_inclusive_price,
        tax_rate: Number(i.tax_rate),
        target_warehouse_id: null,
        target_location_id: null,
        rebate_amount: poForm.use_rebate && i.rebate_amount ? i.rebate_amount : null
      }))
    })
    appStore.showToast('采购订单创建成功: ' + data.po_no)
    showPOCreateModal.value = false
    loadPurchaseOrders()
    loadSuppliers()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '创建失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

// PO detail
const viewPurchaseOrder = async (id) => {
  try {
    const { data } = await getPurchaseOrder(id)
    purchaseOrderDetail.value = data
    showPODetailModal.value = true
  } catch (e) {
    appStore.showToast('加载详情失败', 'error')
  }
}

const handleApprovePO = async (id) => {
  const po = purchaseOrders.value.find(o => o.id === id) || purchaseOrderDetail.value
  if (!po) return
  if (!await appStore.customConfirm('审核通过', `确认通过采购单 ${po.po_no}？通过后将进入待付款状态。`)) return
  try {
    await approvePurchaseOrder(id)
    appStore.showToast('审核通过')
    loadPurchaseOrders()
    if (purchaseOrderDetail.value && purchaseOrderDetail.value.id === id) {
      viewPurchaseOrder(id)
    }
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '操作失败', 'error')
  }
}

const handleRejectPO = async (id) => {
  const po = purchaseOrders.value.find(o => o.id === id) || purchaseOrderDetail.value
  if (!po) return
  if (!await appStore.customConfirm('拒绝采购单', `确认拒绝采购单 ${po.po_no}？拒绝后该订单将完结。`)) return
  try {
    await rejectPurchaseOrder(id)
    appStore.showToast('已拒绝')
    loadPurchaseOrders()
    if (purchaseOrderDetail.value && purchaseOrderDetail.value.id === id) {
      viewPurchaseOrder(id)
    }
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '操作失败', 'error')
  }
}

// Receive
const openPurchaseReceive = () => {
  loadReceivablePOs()
  showReceiveModal.value = true
}

const openReceiveFromDetail = (poId) => {
  showPODetailModal.value = false
  openPurchaseReceive()
}

const loadReceivablePOs = async () => {
  try {
    const { data } = await getReceivablePOs()
    receivablePOs.value = data
  } catch (e) {
    console.error(e)
  }
}

let splitIdCounter = 0
const makeSplit = (opts = {}) => ({
  id: ++splitIdCounter,
  receive_quantity: opts.receive_quantity || 0,
  warehouse_id: opts.warehouse_id || '',
  location_id: opts.location_id || '',
  sn_required: false,
  sn_input: ''
})

const initReceiveItems = (po) => {
  receiveForm.po_id = po.id
  receiveForm.items = po.items.map(it => {
    const split = makeSplit({
      receive_quantity: it.pending_quantity,
      warehouse_id: it.target_warehouse_id || '',
      location_id: it.target_location_id || ''
    })
    return {
      item_id: it.id,
      product_id: it.product_id,
      product_name: it.product_name,
      pending_qty: it.pending_quantity,
      checked: true,
      splits: [split]
    }
  })
  receiveForm.items.forEach(item => {
    item.splits.forEach(sp => {
      if (sp.warehouse_id) handleSplitWarehouseChange(item, sp)
    })
  })
}

const getSplitTotal = (item) => item.splits.reduce((s, sp) => s + (Number(sp.receive_quantity) || 0), 0)
const getSplitRemaining = (item) => item.pending_qty - getSplitTotal(item)

const addSplit = (item) => {
  const remaining = getSplitRemaining(item)
  item.splits.push(makeSplit({ receive_quantity: remaining > 0 ? remaining : 0 }))
}

const removeSplit = (item, idx) => {
  if (item.splits.length <= 1) return
  item.splits.splice(idx, 1)
}

const handleSplitWarehouseChange = async (item, split) => {
  split.location_id = ''
  if (!split.warehouse_id) {
    split.sn_required = false
    split.sn_input = ''
    return
  }
  try {
    const { data } = await checkSnRequired({
      warehouse_id: split.warehouse_id,
      product_id: item.product_id
    })
    split.sn_required = data.required
    if (!data.required) {
      split.sn_input = ''
    }
  } catch (e) {
    split.sn_required = false
  }
}

const confirmReceive = async () => {
  if (!receiveForm.po_id) {
    appStore.showToast('请选择采购单', 'error')
    return
  }
  const checkedItems = receiveForm.items.filter(i => i.checked)
  if (!checkedItems.length) {
    appStore.showToast('请选择要收货的商品', 'error')
    return
  }
  const flatItems = []
  const allSnCodes = new Set()
  for (const item of checkedItems) {
    const total = getSplitTotal(item)
    if (total <= 0) {
      appStore.showToast(`${item.product_name} 收货数量须大于0`, 'error')
      return
    }
    if (total > item.pending_qty) {
      appStore.showToast(`${item.product_name} 收货总量(${total})超过待收数量(${item.pending_qty})`, 'error')
      return
    }
    for (let si = 0; si < item.splits.length; si++) {
      const sp = item.splits[si]
      const qty = Number(sp.receive_quantity) || 0
      if (qty <= 0) continue
      if (!sp.warehouse_id || !sp.location_id) {
        appStore.showToast(`${item.product_name}${item.splits.length > 1 ? ' 分组' + (si + 1) : ''} 缺少仓库或仓位`, 'error')
        return
      }
      if (sp.sn_required) {
        const snList = parseSnCodes(sp.sn_input)
        if (!snList.length) {
          appStore.showToast(`${item.product_name}${item.splits.length > 1 ? ' 分组' + (si + 1) : ''} 已启用SN管理，请填写SN码`, 'error')
          return
        }
        if (snList.length !== qty) {
          appStore.showToast(`${item.product_name}${item.splits.length > 1 ? ' 分组' + (si + 1) : ''} SN码数量(${snList.length})与收货数量(${qty})不匹配`, 'error')
          return
        }
        for (const sn of snList) {
          if (allSnCodes.has(sn)) {
            appStore.showToast(`SN码 ${sn} 重复，请检查`, 'error')
            return
          }
          allSnCodes.add(sn)
        }
      }
      flatItems.push({
        item_id: item.item_id,
        receive_quantity: qty,
        warehouse_id: parseInt(sp.warehouse_id),
        location_id: parseInt(sp.location_id),
        sn_codes: sp.sn_required ? parseSnCodes(sp.sn_input) : null
      })
    }
  }
  if (!flatItems.length) {
    appStore.showToast('请填写收货数量', 'error')
    return
  }
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    await receivePurchaseOrder(receiveForm.po_id, { items: flatItems })
    appStore.showToast('收货成功')
    showReceiveModal.value = false
    productsStore.loadProducts()
    loadPurchaseOrders()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '收货失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

// Return
const openReturnModal = (po) => {
  returnForm.po_id = po.id
  returnForm.po_no = po.po_no
  returnForm.is_refunded = false
  returnForm.tracking_no = ''
  returnForm.items = po.items
    .filter(it => it.returnable_quantity > 0)
    .map(it => ({
      item_id: it.id,
      product_name: `${it.product_sku} - ${it.product_name}`,
      returnable_qty: it.returnable_quantity,
      return_quantity: it.returnable_quantity,
      unit_amount: it.quantity > 0 ? it.amount / it.quantity : 0,
      checked: false
    }))
  showReturnModal.value = true
}

const confirmReturn = async () => {
  const checkedItems = returnForm.items.filter(i => i.checked && i.return_quantity > 0)
  if (!checkedItems.length) {
    appStore.showToast('请选择退货商品', 'error')
    return
  }
  for (const item of checkedItems) {
    if (item.return_quantity > item.returnable_qty) {
      appStore.showToast(`${item.product_name} 退货数量超过可退数量`, 'error')
      return
    }
  }
  if (!await appStore.customConfirm('确认退货', `确认退货 ${checkedItems.length} 项商品，退货金额 ¥${returnTotalAmount.value.toFixed(2)}？${returnForm.is_refunded ? '' : '未退款金额将转为供应商在账资金。'}`)) return
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    await returnPurchaseOrder(returnForm.po_id, {
      items: checkedItems.map(i => ({ item_id: i.item_id, return_quantity: i.return_quantity })),
      is_refunded: returnForm.is_refunded,
      tracking_no: returnForm.tracking_no || null
    })
    appStore.showToast('退货成功')
    showReturnModal.value = false
    showPODetailModal.value = false
    loadPurchaseOrders()
    loadSuppliers()
    emit('data-changed')
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '退货失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

defineExpose({ refresh: loadPurchaseOrders, viewPurchaseOrder, openPurchaseReceive })

onMounted(async () => {
  loadPurchaseOrders()
  loadSuppliers()
  productsStore.loadProducts()
  warehousesStore.loadWarehouses()
  warehousesStore.loadLocations()
  try {
    const { data } = await getAccountSets()
    accountSets.value = data
  } catch (e) { /* ignore */ }
})

onUnmounted(() => clearTimeout(_poSearchTimer))
</script>

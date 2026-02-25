<template>
  <div>
    <!-- Toolbar -->
    <div class="flex flex-wrap items-center gap-2 mb-2">
      <select v-model="stockWarehouseFilter" @change="loadProductsData" class="input text-sm" style="width:130px">
        <option value="">全部仓库</option>
        <option v-for="w in warehouses.filter(x => !x.is_virtual)" :key="w.id" :value="w.id">{{ w.name }}</option>
        <template v-if="showVirtualStock">
          <option v-for="vw in virtualWarehouses" :key="'v' + vw.id" :value="vw.id">{{ vw.name }}</option>
        </template>
      </select>
      <label class="flex items-center gap-1.5 text-xs text-[#86868b] cursor-pointer whitespace-nowrap select-none">
        <span class="toggle">
          <input type="checkbox" v-model="showVirtualStock" @change="onToggleVirtualStock">
          <span class="slider"></span>
        </span>
        寄售
      </label>
      <div class="flex-1"></div>
      <button @click="openPurchaseReceive" class="btn btn-success btn-sm" v-if="hasPermission('purchase_receive')">采购收货</button>
      <button @click="openRestockModal" class="btn btn-primary btn-sm" v-if="hasPermission('stock_edit')">入库</button>
      <button @click="openProductModal" class="btn btn-secondary btn-sm" v-if="hasPermission('stock_edit')">新增商品</button>
      <button @click="openImportModal" class="btn btn-secondary btn-sm hidden md:inline-block" v-if="hasPermission('stock_edit')">导入</button>
      <button @click="handleExportStock" class="btn btn-secondary btn-sm hidden md:inline-block">导出</button>
    </div>

    <!-- Search -->
    <div class="mb-3">
      <input v-model="productSearch" class="input text-sm" placeholder="搜索商品名称、SKU、品牌...">
    </div>

    <!-- Mobile card view -->
    <div class="md:hidden space-y-2">
      <template v-for="p in filteredProducts" :key="'m' + p.id">
        <div
          v-for="(s, idx) in (p.stocks?.length ? (showVirtualStock ? p.stocks : p.stocks.filter(x => !x.is_virtual)) : [])"
          :key="'m' + p.id + '-' + idx"
          class="card p-3"
          :class="{ 'bg-[#f3eef8]': s.is_virtual }"
        >
          <div class="flex justify-between items-start mb-1.5">
            <div class="flex-1 min-w-0 mr-2">
              <div class="font-medium text-sm truncate">{{ p.name }}</div>
              <div class="text-xs text-[#86868b] font-mono">
                {{ p.sku }}
                <span v-if="p.brand" class="text-[#86868b] ml-1">· {{ p.brand }}</span>
              </div>
            </div>
            <div class="text-right flex-shrink-0">
              <div class="text-lg font-bold" :class="s.is_virtual ? 'text-[#af52de]' : 'text-[#1d1d1f]'">{{ s.quantity }}</div>
              <div class="text-xs text-[#86868b]">库存</div>
              <div v-if="(s.reserved_qty || 0) > 0" class="text-xs text-[#ff9f0a]">预留 {{ s.reserved_qty }} / 可用 {{ s.available_qty ?? s.quantity }}</div>
            </div>
          </div>
          <div class="flex justify-between items-center">
            <div class="flex items-center gap-1.5 text-xs">
              <span :class="s.is_virtual ? 'badge badge-purple' : 'badge badge-blue'">{{ s.is_virtual ? '寄售' : (s.location_code || '-') }}</span>
              <span class="text-[#86868b]">{{ s.warehouse_name }}</span>
              <span v-if="!s.is_virtual" :class="getAgeClass(p.age_days)" class="ml-1">{{ p.age_days }}天</span>
            </div>
            <div class="flex items-center gap-2 text-xs flex-shrink-0">
              <template v-if="!s.is_virtual">
                <button @click="editProduct(p)" class="text-[#0071e3]">编辑</button>
                <button v-if="hasPermission('stock_edit')" @click="openTransferForStock(p, s)" class="text-[#34c759]">调拨</button>
              </template>
              <span v-else class="text-[#86868b]">只读</span>
            </div>
          </div>
        </div>
      </template>
      <div v-if="!hasStockProducts" class="p-8 text-center text-[#86868b] text-sm">暂无库存商品</div>
    </div>

    <!-- Desktop table view -->
    <div class="card hidden md:block">
      <div class="table-container">
        <table class="w-full text-sm">
          <thead class="bg-[#f5f5f7]">
            <tr>
              <th class="px-3 py-2 text-left w-24 cursor-pointer select-none hover:text-[#0071e3]" @click="toggleStockSort('brand')">
                品牌 <span v-if="stockSort.key === 'brand'" class="text-[#0071e3]">{{ stockSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th class="px-3 py-2 text-left cursor-pointer select-none hover:text-[#0071e3]" @click="toggleStockSort('name')">
                商品名称 <span v-if="stockSort.key === 'name'" class="text-[#0071e3]">{{ stockSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th class="px-3 py-2 text-left cursor-pointer select-none hover:text-[#0071e3]" @click="toggleStockSort('warehouse')">
                仓位 <span v-if="stockSort.key === 'warehouse'" class="text-[#0071e3]">{{ stockSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th class="px-3 py-2 text-right cursor-pointer select-none hover:text-[#0071e3]" @click="toggleStockSort('retail_price')">
                零售价 <span v-if="stockSort.key === 'retail_price'" class="text-[#0071e3]">{{ stockSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th v-if="hasPermission('finance')" class="px-3 py-2 text-right cursor-pointer select-none hover:text-[#0071e3]" @click="toggleStockSort('cost_price')">
                成本 <span v-if="stockSort.key === 'cost_price'" class="text-[#0071e3]">{{ stockSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th class="px-3 py-2 text-right cursor-pointer select-none hover:text-[#0071e3]" @click="toggleStockSort('quantity')">
                库存 <span v-if="stockSort.key === 'quantity'" class="text-[#0071e3]">{{ stockSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th class="px-3 py-2 text-right">预留</th>
              <th class="px-3 py-2 text-right">可用</th>
              <th class="px-3 py-2 text-center cursor-pointer select-none hover:text-[#0071e3]" @click="toggleStockSort('age')">
                库龄 <span v-if="stockSort.key === 'age'" class="text-[#0071e3]">{{ stockSort.order === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th class="px-3 py-2 text-center">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr
              v-for="(row, idx) in sortedStockRows"
              :key="row.p.id + '-' + idx"
              class="hover:bg-[#f5f5f7]"
              :class="{ 'bg-[#f3eef8]': row.s.is_virtual }"
            >
              <td class="px-3 py-2 text-[#6e6e73] text-xs">{{ row.p.brand || '-' }}</td>
              <td class="px-3 py-2">
                <div class="font-medium">{{ row.p.name }}</div>
                <div class="text-xs text-[#86868b] font-mono mt-0.5">{{ row.p.sku }}</div>
              </td>
              <td class="px-3 py-2">
                <span :class="row.s.is_virtual ? 'badge badge-purple' : 'badge badge-blue'">{{ row.s.is_virtual ? '寄售' : (row.s.location_code || '-') }}</span>
                <div class="text-xs text-[#86868b]">{{ row.s.warehouse_name }}</div>
              </td>
              <td class="px-3 py-2 text-right">{{ row.p.retail_price }}</td>
              <td v-if="hasPermission('finance')" class="px-3 py-2 text-right">{{ row.p.cost_price }}</td>
              <td class="px-3 py-2 text-right font-semibold" :class="{ 'text-[#af52de]': row.s.is_virtual }">{{ row.s.quantity }}</td>
              <td class="px-3 py-2 text-right" :class="(row.s.reserved_qty || 0) > 0 ? 'text-[#ff9f0a] font-semibold' : 'text-[#86868b]'">{{ row.s.reserved_qty || 0 }}</td>
              <td class="px-3 py-2 text-right" :class="(row.s.available_qty ?? row.s.quantity) < (row.s.reserved_qty || 0) ? 'text-[#ff3b30] font-semibold' : 'text-[#34c759] font-semibold'">{{ row.s.available_qty ?? row.s.quantity }}</td>
              <td class="px-3 py-2 text-center">
                <span :class="getAgeClass(row.p.age_days)">{{ row.p.age_days }}天</span>
              </td>
              <td class="px-3 py-2 text-center">
                <template v-if="!row.s.is_virtual">
                  <button @click="editProduct(row.p)" class="text-[#0071e3] text-xs mr-2">编辑</button>
                  <button v-if="hasPermission('stock_edit')" @click="openTransferForStock(row.p, row.s)" class="text-[#34c759] text-xs">调拨</button>
                </template>
                <span v-else class="text-xs text-[#86868b]">只读</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!hasStockProducts" class="p-8 text-center text-[#86868b] text-sm">暂无库存商品</div>
    </div>

    <!-- Product Form Modal -->
    <div v-if="modal.show && modal.type === 'product'" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <div class="p-4 border-b flex justify-between items-center">
          <h3 class="font-semibold">{{ modal.title }}</h3>
          <button @click="closeModal" class="text-[#86868b] text-xl">&times;</button>
        </div>
        <div class="p-4">
          <form @submit.prevent="saveProductHandler" class="space-y-3">
            <div>
              <label class="label">SKU *</label>
              <input v-model="productForm.sku" class="input" required :disabled="!!productForm.id">
            </div>
            <div>
              <label class="label">名称 *</label>
              <input v-model="productForm.name" class="input" required>
            </div>
            <div class="grid form-grid grid-cols-2 gap-3">
              <div>
                <label class="label">品牌</label>
                <input v-model="productForm.brand" class="input">
              </div>
              <div>
                <label class="label">分类</label>
                <input v-model="productForm.category" class="input">
              </div>
            </div>
            <div class="grid form-grid grid-cols-2 gap-3">
              <div>
                <label class="label">零售价</label>
                <input v-model.number="productForm.retail_price" type="number" step="0.01" class="input">
              </div>
              <div v-if="hasPermission('finance')">
                <label class="label">成本价</label>
                <input v-model.number="productForm.cost_price" type="number" step="0.01" class="input">
              </div>
            </div>
            <div class="flex gap-3 pt-3">
              <button type="button" @click="closeModal" class="btn btn-secondary flex-1">取消</button>
              <button type="submit" class="btn btn-primary flex-1">保存</button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- Restock Modal -->
    <div v-if="modal.show && modal.type === 'restock'" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <div class="p-4 border-b flex justify-between items-center">
          <h3 class="font-semibold">{{ modal.title }}</h3>
          <button @click="closeModal" class="text-[#86868b] text-xl">&times;</button>
        </div>
        <div class="p-4">
          <form @submit.prevent="saveRestockHandler" class="space-y-3">
            <div>
              <label class="label">仓库 *</label>
              <select v-model="restockForm.warehouse_id" @change="checkRestockSnRequiredHandler" class="input" required>
                <option value="">选择仓库</option>
                <option v-for="w in warehouses.filter(x => !x.is_virtual)" :key="w.id" :value="w.id">{{ w.name }}</option>
              </select>
            </div>
            <div>
              <label class="label">仓位 *</label>
              <select v-model="restockForm.location_id" class="input" required :disabled="!restockForm.warehouse_id">
                <option value="">{{ restockForm.warehouse_id ? '选择仓位' : '请先选择仓库' }}</option>
                <option v-for="loc in restockLocations" :key="loc.id" :value="loc.id">{{ loc.code }}{{ loc.name ? ' - ' + loc.name : '' }}</option>
              </select>
            </div>
            <div>
              <label class="label">商品 *</label>
              <select v-model="restockForm.product_id" @change="checkRestockSnRequiredHandler" class="input" required>
                <option value="">选择商品</option>
                <option v-for="p in products" :key="p.id" :value="p.id">{{ p.sku }} - {{ p.name }}</option>
              </select>
            </div>
            <div class="grid form-grid grid-cols-2 gap-3">
              <div>
                <label class="label">数量 *</label>
                <input v-model.number="restockForm.quantity" type="number" class="input" required min="1">
              </div>
              <div>
                <label class="label">入库成本(本批次)</label>
                <input v-model.number="restockForm.cost_price" type="number" step="0.01" class="input" placeholder="不填则用上次成本">
              </div>
            </div>
            <div>
              <label class="label">备注</label>
              <input v-model="restockForm.remark" class="input">
            </div>
            <div v-if="restockForm.sn_required" class="bg-[#fff8e1] border border-[#ffe082] rounded-lg p-3">
              <label class="label">
                SN码 *
                <span
                  class="font-normal text-xs"
                  :class="parseSnCodes(restockForm.sn_input).length === parseInt(restockForm.quantity || 0) ? 'text-[#34c759]' : 'text-[#ff3b30]'"
                >
                  (已输入 {{ parseSnCodes(restockForm.sn_input).length }} / 需要 {{ restockForm.quantity || 0 }})
                </span>
              </label>
              <textarea v-model="restockForm.sn_input" class="input text-sm" rows="3" placeholder="每行一个SN码，或用逗号/空格分隔"></textarea>
            </div>
            <div class="flex gap-3 pt-3">
              <button type="button" @click="closeModal" class="btn btn-secondary flex-1">取消</button>
              <button type="submit" class="btn btn-primary flex-1">确认入库</button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- Transfer Modal -->
    <div v-if="modal.show && modal.type === 'transfer'" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <div class="p-4 border-b flex justify-between items-center">
          <h3 class="font-semibold">{{ modal.title }}</h3>
          <button @click="closeModal" class="text-[#86868b] text-xl">&times;</button>
        </div>
        <div class="p-4">
          <form @submit.prevent="saveTransferHandler" class="space-y-4">
            <div class="p-4 bg-[#e8f4fd] border border-[#b3d7f5] rounded-lg">
              <div class="text-xs text-[#0071e3] font-semibold mb-1">调拨商品</div>
              <div class="font-medium text-[#1d1d1f]">{{ transferProductSearch }}</div>
            </div>
            <div class="grid form-grid grid-cols-2 gap-4">
              <!-- From -->
              <div class="p-4 bg-[#ffeaee] border-2 border-[#ffb3b3] rounded-lg">
                <div class="text-sm text-[#ff3b30] font-bold mb-3 flex items-center">
                  <svg class="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-11a1 1 0 10-2 0v3.586L7.707 9.293a1 1 0 00-1.414 1.414l3 3a1 1 0 001.414 0l3-3a1 1 0 00-1.414-1.414L11 10.586V7z" clip-rule="evenodd"/></svg>
                  调出
                </div>
                <div class="space-y-2 text-sm">
                  <div><span class="text-[#86868b]">仓库：</span><span class="font-medium text-[#1d1d1f]">{{ warehouses.find(w => w.id === transferForm.from_warehouse_id)?.name }}</span></div>
                  <div><span class="text-[#86868b]">仓位：</span><span class="font-medium text-[#1d1d1f]">{{ locations.find(l => l.id === transferForm.from_location_id)?.code }}</span></div>
                  <div class="pt-2 border-t border-[#ffb3b3]"><span class="text-[#86868b]">可用库存：</span><span class="text-lg font-bold text-[#ff3b30]">{{ transferSourceQty }}</span></div>
                </div>
              </div>
              <!-- To -->
              <div class="p-4 bg-[#e8f8ee] border-2 border-[#a8e6c1] rounded-lg">
                <div class="text-sm text-[#34c759] font-bold mb-3 flex items-center">
                  <svg class="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-11a1 1 0 10-2 0v3.586L7.707 9.293a1 1 0 00-1.414 1.414l3 3a1 1 0 001.414 0l3-3a1 1 0 00-1.414-1.414L11 10.586V7z" clip-rule="evenodd"/></svg>
                  调入
                </div>
                <div class="space-y-2">
                  <div>
                    <label class="block text-xs text-[#6e6e73] mb-1">目标仓库 *</label>
                    <select v-model="transferForm.to_warehouse_id" class="input" required>
                      <option value="">请选择</option>
                      <option v-for="w in warehouses.filter(x => !x.is_virtual)" :key="w.id" :value="w.id">{{ w.name }}</option>
                    </select>
                  </div>
                  <div>
                    <label class="block text-xs text-[#6e6e73] mb-1">目标仓位 *</label>
                    <select v-model="transferForm.to_location_id" class="input" required :disabled="!transferForm.to_warehouse_id">
                      <option value="">{{ transferForm.to_warehouse_id ? '请选择' : '请先选择仓库' }}</option>
                      <option v-for="loc in transferToLocations" :key="loc.id" :value="loc.id">{{ loc.code }}</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>
            <div>
              <label class="label">调拨数量 *</label>
              <input v-model.number="transferForm.quantity" type="number" class="input text-lg font-semibold" required min="1" :max="transferSourceQty || 999999" placeholder="输入数量">
            </div>
            <div>
              <label class="label">备注</label>
              <input v-model="transferForm.remark" class="input" placeholder="选填，可备注调拨原因">
            </div>
            <div class="flex gap-3 pt-2">
              <button type="button" @click="closeModal" class="btn btn-secondary flex-1">取消</button>
              <button type="submit" class="btn btn-primary flex-1 font-semibold">确认调拨</button>
            </div>
            <input type="hidden" v-model="transferForm.product_id" required>
            <input type="hidden" v-model="transferForm.from_warehouse_id" required>
            <input type="hidden" v-model="transferForm.from_location_id" required>
          </form>
        </div>
      </div>
    </div>

    <!-- Import Modal -->
    <div v-if="modal.show && modal.type === 'import'" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <div class="p-4 border-b flex justify-between items-center">
          <h3 class="font-semibold">{{ modal.title }}</h3>
          <button @click="closeModal" class="text-[#86868b] text-xl">&times;</button>
        </div>
        <div class="p-4">
          <div class="space-y-4">
            <div class="p-4 bg-[#e8f4fd] rounded-lg">
              <h4 class="font-semibold text-[#0071e3] mb-2">导入说明</h4>
              <ul class="text-sm text-[#0071e3] space-y-1">
                <li>支持 .xlsx 和 .xls 格式</li>
                <li>SKU为必填字段，用于匹配商品</li>
                <li>已存在的SKU将更新信息，新SKU将创建商品</li>
              </ul>
            </div>
            <div class="flex gap-3">
              <button type="button" @click="downloadTemplateHandler" class="btn btn-secondary flex-1 text-center">下载模板</button>
              <label class="btn btn-primary flex-1 text-center cursor-pointer">
                选择文件
                <input type="file" @change="previewImportHandler" accept=".xlsx,.xls" class="hidden">
              </label>
            </div>
            <div class="flex gap-3 pt-3">
              <button type="button" @click="closeModal" class="btn btn-secondary flex-1">关闭</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Import Preview Modal -->
    <div v-if="modal.show && modal.type === 'import_preview'" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <div class="p-4 border-b flex justify-between items-center">
          <h3 class="font-semibold">{{ modal.title }}</h3>
          <button @click="closeModal" class="text-[#86868b] text-xl">&times;</button>
        </div>
        <div class="p-4">
          <div class="space-y-4">
            <div class="p-3 rounded-lg" :class="importPreviewData.valid_count > 0 ? 'bg-[#e8f8ee] border border-[#a8e6c1]' : 'bg-[#fff8e1] border border-[#ffe082]'">
              <div class="flex justify-between items-center">
                <div><span class="font-semibold text-lg">共 {{ importPreviewData.total }} 条数据</span></div>
                <div class="text-sm">
                  <span class="text-[#34c759] font-semibold">{{ importPreviewData.valid_count }} 条有效</span>
                  <span class="mx-2">|</span>
                  <span class="text-[#86868b]">{{ importPreviewData.skip_count }} 条跳过</span>
                </div>
              </div>
            </div>
            <div class="max-h-96 overflow-y-auto border rounded-lg">
              <table class="w-full text-sm">
                <thead class="bg-[#f5f5f7] sticky top-0">
                  <tr>
                    <th class="px-2 py-2 text-left w-12">行</th>
                    <th class="px-2 py-2 text-left">SKU</th>
                    <th class="px-2 py-2 text-left">名称</th>
                    <th class="px-2 py-2 text-left">仓库</th>
                    <th class="px-2 py-2 text-left">仓位</th>
                    <th class="px-2 py-2 text-right">导入数量</th>
                    <th class="px-2 py-2 text-center">库存变化</th>
                    <th class="px-2 py-2 text-right">成本</th>
                    <th class="px-2 py-2 text-left">操作</th>
                  </tr>
                </thead>
                <tbody class="divide-y">
                  <tr v-for="item in importPreviewData.items" :key="item.row" :class="item.status === 'skip' ? 'bg-[#f5f5f7] text-[#86868b]' : ''">
                    <td class="px-2 py-1.5 text-[#86868b]">{{ item.row }}</td>
                    <td class="px-2 py-1.5 font-mono text-xs">{{ item.sku }}</td>
                    <td class="px-2 py-1.5 truncate max-w-32">{{ item.name }}</td>
                    <td class="px-2 py-1.5">
                      <span v-if="item.warehouse" class="text-xs">{{ item.warehouse }}</span>
                      <span v-else class="text-[#ff6961]">-</span>
                    </td>
                    <td class="px-2 py-1.5">
                      <span v-if="item.location" class="badge badge-blue text-xs">{{ item.location }}</span>
                      <span v-else class="text-[#ff6961]">-</span>
                    </td>
                    <td class="px-2 py-1.5 text-right font-semibold text-[#34c759]">+{{ item.quantity || 0 }}</td>
                    <td class="px-2 py-1.5 text-center">
                      <span v-if="item.current_stock > 0" class="text-xs">{{ item.current_stock }} → <span class="font-semibold text-[#0071e3]">{{ item.after_stock }}</span></span>
                      <span v-else-if="item.status === 'valid'" class="text-xs text-[#86868b]">0 → <span class="font-semibold">{{ item.after_stock }}</span></span>
                      <span v-else>-</span>
                    </td>
                    <td class="px-2 py-1.5 text-right">{{ item.cost_price ? '¥' + item.cost_price : '-' }}</td>
                    <td class="px-2 py-1.5">
                      <span v-if="item.current_stock > 0" class="badge badge-purple text-xs">叠加</span>
                      <span v-else-if="item.status === 'valid'" class="badge badge-green text-xs">新增</span>
                      <span v-else class="badge badge-gray text-xs">跳过</span>
                    </td>
                  </tr>
                </tbody>
              </table>
              <div v-if="!importPreviewData.items?.length" class="p-6 text-center text-[#86868b]">无数据</div>
            </div>
            <div v-if="importPreviewData.valid_count === 0" class="p-3 bg-[#fff8e1] border border-[#ffe082] rounded-lg text-[#ff9f0a] text-sm">
              没有有效的导入数据，请检查Excel文件是否正确填写了仓库、仓位和数量。
            </div>
            <div class="flex gap-3 pt-3">
              <button type="button" @click="cancelImportHandler" class="btn btn-secondary flex-1">取消</button>
              <button type="button" @click="confirmImportHandler" class="btn btn-primary flex-1" :disabled="importPreviewData.valid_count === 0">
                确认导入 ({{ importPreviewData.valid_count }}条)
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'
import { useProductsStore } from '../stores/products'
import { useWarehousesStore } from '../stores/warehouses'
import { useFormat } from '../composables/useFormat'
import { usePermission } from '../composables/usePermission'
import { exportStock as apiExportStock } from '../api/stock'
import { restock as apiRestock, transfer as apiTransfer } from '../api/stock'
import { getWarehouses } from '../api/warehouses'
import { getProducts, createProduct, updateProduct, getTemplate, previewImport, importProducts } from '../api/products'
import { checkSnRequired } from '../api/sn'
import { fuzzyMatchAny } from '../utils/helpers'
import { parseSnCodes } from '../utils/helpers'

const router = useRouter()
const appStore = useAppStore()
const productsStore = useProductsStore()
const warehousesStore = useWarehousesStore()
const { fmt, fmtDate, getAgeClass } = useFormat()
const { hasPermission } = usePermission()

// App store shortcuts
const modal = appStore.modal
const openModal = appStore.openModal
const closeModal = appStore.closeModal
const showToast = appStore.showToast

// Data from stores
const products = computed(() => productsStore.products)
const warehouses = computed(() => warehousesStore.warehouses)
const locations = computed(() => warehousesStore.locations)

// Local state
const stockWarehouseFilter = ref('')
const showVirtualStock = ref(false)
const virtualWarehouses = ref([])
const productSearch = ref('')

// Sort state
const stockSort = reactive({ key: '', order: '' })
const toggleStockSort = (key) => {
  if (stockSort.key === key) {
    if (stockSort.order === 'asc') stockSort.order = 'desc'
    else { stockSort.key = ''; stockSort.order = '' }
  } else {
    stockSort.key = key
    stockSort.order = 'asc'
  }
}

// Forms
const productForm = reactive({ id: null, sku: '', name: '', brand: '', category: '', retail_price: null, cost_price: null })
const restockForm = reactive({ warehouse_id: '', location_id: '', product_id: '', quantity: 1, cost_price: null, remark: '', sn_required: false, sn_input: '' })
const transferForm = reactive({ product_id: '', from_warehouse_id: '', from_location_id: '', to_warehouse_id: '', to_location_id: '', quantity: 1, remark: '' })
const transferProductSearch = ref('')
const transferSourceQty = ref(0)
const importFile = ref(null)
const importPreviewData = ref({ total: 0, valid_count: 0, skip_count: 0, items: [] })

// Computed
const filteredProducts = computed(() => {
  const kw = productSearch.value
  if (!kw) return products.value
  return products.value.filter(p => fuzzyMatchAny([p.sku, p.name, p.brand, p.category], kw))
})

const sortedStockRows = computed(() => {
  const rows = []
  filteredProducts.value.forEach(p => {
    if (!p.stocks || !p.stocks.length) return
    const stocks = showVirtualStock.value ? p.stocks : p.stocks.filter(x => !x.is_virtual)
    stocks.forEach(s => {
      rows.push({ p, s })
    })
  })
  if (!stockSort.key) return rows
  const k = stockSort.key
  const asc = stockSort.order === 'asc'
  rows.sort((a, b) => {
    let va, vb
    if (k === 'brand') { va = (a.p.brand || '').toLowerCase(); vb = (b.p.brand || '').toLowerCase() }
    else if (k === 'name') { va = (a.p.name || '').toLowerCase(); vb = (b.p.name || '').toLowerCase() }
    else if (k === 'warehouse') { va = (a.s.warehouse_name || '') + (a.s.location_code || ''); vb = (b.s.warehouse_name || '') + (b.s.location_code || '') }
    else if (k === 'retail_price') { va = Number(a.p.retail_price) || 0; vb = Number(b.p.retail_price) || 0 }
    else if (k === 'cost_price') { va = Number(a.p.cost_price) || 0; vb = Number(b.p.cost_price) || 0 }
    else if (k === 'quantity') { va = a.s.quantity || 0; vb = b.s.quantity || 0 }
    else if (k === 'age') { va = a.p.age_days || 0; vb = b.p.age_days || 0 }
    else return 0
    if (va < vb) return asc ? -1 : 1
    if (va > vb) return asc ? 1 : -1
    return 0
  })
  return rows
})

const hasStockProducts = computed(() =>
  filteredProducts.value.some(p => p.stocks && p.stocks.some(s => showVirtualStock.value || !s.is_virtual))
)

const restockLocations = computed(() => {
  if (!restockForm.warehouse_id) return []
  return warehousesStore.getLocationsByWarehouse(restockForm.warehouse_id)
})

const transferToLocations = computed(() => {
  if (!transferForm.to_warehouse_id) return []
  return warehousesStore.getLocationsByWarehouse(transferForm.to_warehouse_id)
})

// Watchers: reset location when warehouse changes
watch(() => restockForm.warehouse_id, () => { restockForm.location_id = '' })
watch(() => transferForm.to_warehouse_id, () => { transferForm.to_location_id = '' })

// Methods
const loadProductsData = () => {
  productsStore.loadProducts(stockWarehouseFilter.value || undefined)
}

const loadVirtualWarehouses = async () => {
  try {
    const { data } = await getWarehouses({ include_virtual: true })
    virtualWarehouses.value = data.filter(w => w.is_virtual)
  } catch (e) {
    console.error(e)
    appStore.showToast(e.response?.data?.detail || '加载数据失败', 'error')
  }
}

const onToggleVirtualStock = async () => {
  if (showVirtualStock.value && !virtualWarehouses.value.length) await loadVirtualWarehouses()
}

const openProductModal = () => {
  Object.assign(productForm, { id: null, sku: '', name: '', brand: '', category: '', retail_price: null, cost_price: null })
  openModal('product', '新增商品')
}

const editProduct = (p) => {
  Object.assign(productForm, {
    id: p.id, sku: p.sku, name: p.name, brand: p.brand,
    category: p.category, retail_price: p.retail_price, cost_price: p.cost_price
  })
  openModal('product', '编辑商品')
}

const saveProductHandler = async () => {
  if (!productForm.sku || !productForm.sku.trim()) {
    showToast('请输入商品SKU', 'error')
    return
  }
  if (!productForm.name || !productForm.name.trim()) {
    showToast('请输入商品名称', 'error')
    return
  }
  if (productForm.retail_price == null || productForm.retail_price === '') {
    showToast('请输入零售价', 'error')
    return
  }
  if (Number(productForm.retail_price) < 0) {
    showToast('零售价不能为负数', 'error')
    return
  }
  if (productForm.cost_price == null || productForm.cost_price === '') {
    showToast('请输入成本价', 'error')
    return
  }
  if (Number(productForm.cost_price) < 0) {
    showToast('成本价不能为负数', 'error')
    return
  }
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    if (productForm.id) await updateProduct(productForm.id, productForm)
    else await createProduct(productForm)
    showToast('保存成功')
    closeModal()
    loadProductsData()
  } catch (e) {
    showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

const openRestockModal = () => {
  Object.assign(restockForm, { warehouse_id: '', location_id: '', product_id: '', quantity: 1, cost_price: null, remark: '', sn_required: false, sn_input: '' })
  openModal('restock', '入库')
}

const checkRestockSnRequiredHandler = async () => {
  if (!restockForm.warehouse_id || !restockForm.product_id) {
    restockForm.sn_required = false
    restockForm.sn_input = ''
    return
  }
  try {
    const { data } = await checkSnRequired({ warehouse_id: restockForm.warehouse_id, product_id: restockForm.product_id })
    restockForm.sn_required = data.required
    if (!data.required) {
      restockForm.sn_input = ''
    }
  } catch (e) {
    restockForm.sn_required = false
  }
}

const saveRestockHandler = async () => {
  if (!restockForm.warehouse_id || !restockForm.location_id || !restockForm.product_id || !restockForm.quantity) {
    showToast('请填写完整信息', 'error')
    return
  }
  if (parseInt(restockForm.quantity) <= 0) {
    showToast('入库数量必须大于0', 'error')
    return
  }
  if (restockForm.cost_price != null && restockForm.cost_price !== '' && Number(restockForm.cost_price) < 0) {
    showToast('成本价不能为负数', 'error')
    return
  }
  if (appStore.submitting) return
  const snList = restockForm.sn_required ? parseSnCodes(restockForm.sn_input) : null
  if (restockForm.sn_required) {
    if (!snList || snList.length === 0) {
      showToast('该仓库+品牌已启用SN管理，请填写SN码', 'error')
      return
    }
    if (snList.length !== parseInt(restockForm.quantity)) {
      showToast(`SN码数量(${snList.length})与入库数量(${restockForm.quantity})不匹配`, 'error')
      return
    }
  }
  appStore.submitting = true
  try {
    await apiRestock({
      warehouse_id: parseInt(restockForm.warehouse_id),
      location_id: parseInt(restockForm.location_id),
      product_id: parseInt(restockForm.product_id),
      quantity: parseInt(restockForm.quantity),
      cost_price: restockForm.cost_price || null,
      remark: restockForm.remark || null,
      sn_codes: snList || null
    })
    showToast('入库成功')
    closeModal()
    loadProductsData()
  } catch (e) {
    showToast(e.response?.data?.detail || '入库失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

const openTransferForStock = (p, s) => {
  openModal('transfer', `调拨 - ${p.sku}`)
  transferForm.product_id = p.id
  transferForm.from_warehouse_id = s.warehouse_id
  transferForm.from_location_id = s.location_id
  transferForm.to_warehouse_id = ''
  transferForm.to_location_id = ''
  transferForm.quantity = 1
  transferForm.remark = ''
  transferProductSearch.value = `${p.sku} - ${p.name}`
  transferSourceQty.value = s.available_qty ?? (s.quantity - (s.reserved_qty || 0))
}

const saveTransferHandler = async () => {
  if (!transferForm.product_id || !transferForm.from_warehouse_id || !transferForm.from_location_id ||
      !transferForm.to_warehouse_id || !transferForm.to_location_id || !transferForm.quantity) {
    showToast('请填写完整信息', 'error')
    return
  }
  if (transferForm.from_warehouse_id === transferForm.to_warehouse_id &&
      transferForm.from_location_id === transferForm.to_location_id) {
    showToast('源和目标位置不能相同', 'error')
    return
  }
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    await apiTransfer({
      product_id: parseInt(transferForm.product_id),
      from_warehouse_id: parseInt(transferForm.from_warehouse_id),
      from_location_id: parseInt(transferForm.from_location_id),
      to_warehouse_id: parseInt(transferForm.to_warehouse_id),
      to_location_id: parseInt(transferForm.to_location_id),
      quantity: parseInt(transferForm.quantity),
      remark: transferForm.remark || null
    })
    showToast('调拨成功')
    closeModal()
    loadProductsData()
  } catch (e) {
    showToast(e.response?.data?.detail || '调拨失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

const openImportModal = () => {
  importFile.value = null
  importPreviewData.value = { total: 0, valid_count: 0, skip_count: 0, items: [] }
  openModal('import', '导入商品')
}

const downloadTemplateHandler = async () => {
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    const { data } = await getTemplate()
    const url = URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    a.download = 'import_template.xlsx'
    a.click()
    URL.revokeObjectURL(url)
    showToast('模板已下载')
  } catch (e) {
    showToast('下载失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

const previewImportHandler = async (e) => {
  const file = e.target.files[0]
  if (!file) return
  importFile.value = file
  const formData = new FormData()
  formData.append('file', file)
  try {
    const { data } = await previewImport(formData)
    importPreviewData.value = data
    modal.type = 'import_preview'
    modal.title = '导入预览 - ' + file.name
  } catch (ex) {
    showToast('解析文件失败', 'error')
  }
  e.target.value = ''
}

const confirmImportHandler = async () => {
  if (appStore.submitting) return
  if (!importFile.value) {
    showToast('请先选择文件', 'error')
    return
  }
  appStore.submitting = true
  try {
    const formData = new FormData()
    formData.append('file', importFile.value)
    const { data } = await importProducts(formData)
    showToast(data.message)
    closeModal()
    loadProductsData()
    warehousesStore.loadWarehouses()
    warehousesStore.loadLocations()
  } catch (ex) {
    showToast('导入失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

const cancelImportHandler = () => {
  importFile.value = null
  importPreviewData.value = { total: 0, valid_count: 0, skip_count: 0, items: [] }
  modal.type = 'import'
  modal.title = '导入商品'
}

const handleExportStock = async () => {
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    const params = {}
    if (stockWarehouseFilter.value) params.warehouse_id = stockWarehouseFilter.value
    const response = await apiExportStock(params)
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', '库存表_' + new Date().toISOString().slice(0, 19).replace(/:/g, '') + '.csv')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    showToast('导出成功')
  } catch (e) {
    showToast('导出失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

const openPurchaseReceive = () => {
  router.push({ path: '/purchase', query: { action: 'receive' } })
}
</script>

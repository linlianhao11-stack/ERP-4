<template>
  <div>
    <h2 class="text-lg font-bold mb-4">系统设置</h2>

    <!-- Tabs -->
    <div class="flex flex-wrap gap-2 mb-3 border-b pb-2">
      <span @click="settingsTab = 'general'" :class="['tab', settingsTab === 'general' ? 'active' : '']">常规设置</span>
      <span v-if="hasPermission('finance')" @click="settingsTab = 'finance'" :class="['tab', settingsTab === 'finance' ? 'active' : '']">财务设置</span>
      <span v-if="hasPermission('admin')" @click="settingsTab = 'logs'" :class="['tab', settingsTab === 'logs' ? 'active' : '']">系统日志</span>
      <span v-if="hasPermission('admin')" @click="settingsTab = 'permissions'" :class="['tab', settingsTab === 'permissions' ? 'active' : '']">权限管理</span>
    </div>

    <!-- General Tab -->
    <div v-if="settingsTab === 'general'" class="grid md:grid-cols-2 gap-5">
      <!-- Warehouses + Locations -->
      <div v-if="hasPermission('settings') || hasPermission('stock_edit')" class="card p-4 md:col-span-2">
        <h3 class="font-semibold mb-3 text-sm">仓库与仓位管理</h3>
        <div class="space-y-3 mb-3">
          <div v-for="w in warehouses.filter(x => !x.is_virtual)" :key="w.id" class="border rounded-lg overflow-hidden">
            <!-- Warehouse header -->
            <div class="flex justify-between items-center p-3 bg-[#f5f5f7] cursor-pointer" @click="toggleExpandWarehouse(w.id)">
              <div class="flex items-center gap-2">
                <span class="text-xs text-[#86868b]">{{ expandedWarehouse === w.id ? '▼' : '▶' }}</span>
                <span class="font-medium text-sm">{{ w.name }}</span>
                <span v-if="w.is_default" class="text-xs text-[#0071e3] bg-[#e8f4fd] px-1.5 py-0.5 rounded">(默认)</span>
                <span v-if="w.account_set_name" class="text-xs text-white bg-[#0071e3] px-1.5 py-0.5 rounded">{{ w.account_set_name }}</span>
                <span class="text-xs text-[#86868b]">{{ (w.locations || []).length }} 个仓位</span>
              </div>
              <div class="flex gap-2" @click.stop>
                <button v-if="!w.is_default" @click="handleSetDefaultWarehouse(w.id)" class="text-[#248a3d] text-xs">设为默认</button>
                <button @click="editWarehouse(w)" class="text-[#0071e3] text-xs">改名</button>
                <button v-if="!w.is_default" @click="handleDeleteWarehouse(w.id)" class="text-[#ff3b30] text-xs">删除</button>
              </div>
            </div>
            <!-- Locations list (expanded) -->
            <div v-if="expandedWarehouse === w.id" class="p-3 border-t bg-white">
              <div class="space-y-1.5 mb-3 max-h-48 overflow-y-auto">
                <div v-for="loc in (w.locations || [])" :key="loc.id" class="flex justify-between items-center px-3 py-1.5 bg-[#f5f5f7] rounded text-sm">
                  <span>{{ loc.code }} <span v-if="loc.name" class="text-xs text-[#86868b]">{{ loc.name }}</span></span>
                  <div>
                    <button @click="editLocation(loc, w.id)" class="text-[#0071e3] text-xs mr-2">编辑</button>
                    <button @click="handleDeleteLocation(loc.id)" class="text-[#ff3b30] text-xs">删除</button>
                  </div>
                </div>
                <div v-if="!(w.locations || []).length" class="text-[#86868b] text-center py-2 text-xs">暂无仓位</div>
              </div>
              <form @submit.prevent="handleCreateLocation(w.id)" class="flex gap-2">
                <input v-model="getLocationInput(w.id).code" class="input flex-1 text-sm" placeholder="仓位编号(如 A-01-02)">
                <input v-model="getLocationInput(w.id).name" class="input flex-1 text-sm" placeholder="名称(可选)">
                <button type="submit" class="btn btn-primary btn-sm">添加</button>
              </form>
            </div>
          </div>
        </div>
        <form @submit.prevent="handleCreateWarehouse" class="flex gap-2">
          <input v-model="newWarehouseName" class="input flex-1 text-sm" placeholder="新仓库名">
          <button type="submit" class="btn btn-primary btn-sm">添加仓库</button>
        </form>
      </div>

      <!-- Salespersons -->
      <div v-if="hasPermission('settings') || hasPermission('sales')" class="card p-4">
        <h3 class="font-semibold mb-3 text-sm">销售员管理</h3>
        <div class="space-y-2 mb-3 max-h-48 overflow-y-auto">
          <div v-for="s in salespersons" :key="s.id" class="flex justify-between items-center p-2 bg-[#f5f5f7] rounded text-sm">
            <span>{{ s.name }} <span v-if="s.phone" class="text-xs text-[#86868b]">{{ s.phone }}</span></span>
            <div>
              <button @click="editSalesperson(s)" class="text-[#0071e3] text-xs mr-2">编辑</button>
              <button @click="handleDeleteSalesperson(s.id)" class="text-[#ff3b30] text-xs">删除</button>
            </div>
          </div>
          <div v-if="!salespersons.length" class="text-[#86868b] text-center py-2 text-sm">暂无销售员</div>
        </div>
        <form @submit.prevent="handleCreateSalesperson" class="flex gap-2">
          <input v-model="newSalespersonName" class="input flex-1 text-sm" placeholder="姓名">
          <input v-model="newSalespersonPhone" class="input flex-1 text-sm" placeholder="电话(可选)">
          <button type="submit" class="btn btn-primary btn-sm">添加</button>
        </form>
      </div>

      <!-- Users (admin only) -->
      <div v-if="hasPermission('admin')" class="card p-4">
        <h3 class="font-semibold mb-3 text-sm">用户管理</h3>
        <div class="space-y-2 mb-3">
          <div v-for="u in users" :key="u.id" class="flex justify-between items-center p-2 bg-[#f5f5f7] rounded text-sm">
            <span>{{ u.display_name }} <span class="text-[#86868b] text-xs">@{{ u.username }}</span></span>
            <div>
              <button @click="editUser(u)" class="text-[#0071e3] text-xs mr-2">编辑</button>
              <button v-if="u.id !== authStore.user?.id" @click="handleToggleUser(u.id)" :class="u.is_active ? 'text-[#ff3b30]' : 'text-[#34c759]'" class="text-xs">{{ u.is_active ? '禁用' : '启用' }}</button>
            </div>
          </div>
        </div>
        <button @click="openUserForm()" class="btn btn-primary btn-sm">新增用户</button>
      </div>

      <!-- Change Password -->
      <div class="card p-4">
        <h3 class="font-semibold mb-3 text-sm">修改密码</h3>
        <form @submit.prevent="handleChangePassword" class="space-y-3">
          <div><label class="label">旧密码</label><input v-model="pwdForm.old_password" type="password" class="input w-full text-sm" placeholder="请输入当前密码"></div>
          <div><label class="label">新密码</label><input v-model="pwdForm.new_password" type="password" class="input w-full text-sm" placeholder="请输入新密码"></div>
          <div><label class="label">确认新密码</label><input v-model="pwdForm.confirm_password" type="password" class="input w-full text-sm" placeholder="再次输入新密码"></div>
          <button type="submit" class="btn btn-primary btn-sm">修改密码</button>
        </form>
      </div>

      <!-- Backup (admin only) -->
      <div v-if="hasPermission('admin')" class="card p-4">
        <h3 class="font-semibold mb-3 text-sm">数据库备份</h3>
        <div class="flex gap-2 mb-3">
          <button @click="handleCreateBackup" class="btn btn-primary btn-sm" :disabled="backupLoading">{{ backupLoading ? '备份中...' : '立即备份' }}</button>
          <button @click="loadBackups" class="btn btn-secondary btn-sm">刷新列表</button>
          <button @click="showRestoreModal = true" class="btn btn-sm" style="background:#16a34a;color:#fff" :disabled="restoreLoading">备份恢复</button>
        </div>
        <div class="space-y-1.5 max-h-48 overflow-y-auto">
          <div v-for="b in backups" :key="b.filename" class="flex justify-between items-center p-2 bg-[#f5f5f7] rounded text-xs">
            <div>
              <div class="font-medium">{{ b.filename }}</div>
              <div class="text-[#86868b]">{{ b.size_mb }} MB · {{ fmtDate(b.created_at) }}</div>
            </div>
            <div class="flex gap-2">
              <button @click="handleDownloadBackup(b.filename)" class="text-[#0071e3]">下载</button>
              <button @click="handleDeleteBackup(b.filename)" class="text-[#ff3b30]">删除</button>
            </div>
          </div>
          <div v-if="!backups.length" class="text-[#86868b] text-center py-2">暂无备份</div>
        </div>
        <div class="text-xs text-[#86868b] mt-2">自动备份：每天凌晨3点 · 保留30天</div>
      </div>

      <!-- SN Config -->
      <div v-if="hasPermission('settings') || hasPermission('admin')" class="card p-4">
        <h3 class="font-semibold mb-3 text-sm">SN码管理配置</h3>
        <div class="text-xs text-[#86868b] mb-3">配置需要SN码追踪的"仓库+品牌"组合，启用后入库必填SN码</div>
        <div class="space-y-2 mb-3 max-h-48 overflow-y-auto">
          <div v-for="c in snConfigs" :key="c.id" class="flex justify-between items-center p-2 bg-[#f5f5f7] rounded text-sm">
            <span>{{ c.warehouse_name }} <span class="text-[#0071e3] font-medium">{{ c.brand }}</span></span>
            <button @click="handleDeleteSnConfig(c.id)" class="text-[#ff3b30] text-xs">删除</button>
          </div>
          <div v-if="!snConfigs.length" class="text-[#86868b] text-center py-2 text-sm">暂无配置</div>
        </div>
        <div class="flex gap-2">
          <select v-model="newSnConfigWarehouse" class="input flex-1 text-sm">
            <option value="">选择仓库</option>
            <option v-for="w in warehouses.filter(x => !x.is_virtual)" :key="w.id" :value="w.id">{{ w.name }}</option>
          </select>
          <select v-model="newSnConfigBrand" class="input flex-1 text-sm">
            <option value="">选择品牌</option>
            <option v-for="b in productBrands" :key="b" :value="b">{{ b }}</option>
          </select>
          <button @click="handleCreateSnConfig" class="btn btn-primary btn-sm">添加</button>
        </div>
      </div>
    </div>

    <!-- Finance Tab -->
    <div v-if="settingsTab === 'finance'">
      <div class="grid md:grid-cols-2 gap-5">
        <!-- Payment Methods -->
        <div class="card p-4">
          <h3 class="font-semibold mb-3 text-sm">收款方式管理</h3>
          <div class="text-xs text-[#86868b] mb-3">管理收款时可选的付款方式，修改后全局生效</div>
          <div class="space-y-2 mb-3">
            <div v-for="m in paymentMethods" :key="m.id" class="flex justify-between items-center p-2 bg-[#f5f5f7] rounded text-sm">
              <div v-if="editingPayMethodId === m.id" class="flex items-center gap-2 flex-1">
                <input v-model="editingPayMethodName" class="input text-sm flex-1" @keyup.enter="saveEditPaymentMethod" @keyup.escape="cancelEditPaymentMethod">
                <button @click="saveEditPaymentMethod" class="text-[#248a3d] text-xs font-medium">保存</button>
                <button @click="cancelEditPaymentMethod" class="text-[#86868b] text-xs">取消</button>
              </div>
              <template v-else>
                <div>
                  <span class="font-medium">{{ m.name }}</span>
                  <span class="text-xs text-[#86868b] ml-1">({{ m.code }})</span>
                </div>
                <div>
                  <button @click="editPaymentMethod(m)" class="text-[#0071e3] text-xs mr-2">编辑</button>
                  <button @click="handleDeletePaymentMethod(m.id)" class="text-[#ff3b30] text-xs">删除</button>
                </div>
              </template>
            </div>
            <div v-if="!paymentMethods.length" class="text-[#86868b] text-center py-2 text-sm">暂无收款方式</div>
          </div>
          <form @submit.prevent="handleCreatePaymentMethod" class="flex gap-2">
            <input v-model="newPayMethodCode" class="input flex-1 text-sm" placeholder="编码(如 bank_abc)">
            <input v-model="newPayMethodName" class="input flex-1 text-sm" placeholder="显示名称">
            <button type="submit" class="btn btn-primary btn-sm">添加</button>
          </form>
        </div>
      </div>

      <!-- Disbursement Methods -->
      <div class="grid md:grid-cols-2 gap-5 mt-5">
        <div class="card p-4">
          <h3 class="font-semibold mb-3 text-sm">付款方式管理</h3>
          <div class="text-xs text-[#86868b] mb-3">管理向供应商付款时可选的付款方式，修改后全局生效</div>
          <div class="space-y-2 mb-3">
            <div v-for="m in disbursementMethods" :key="m.id" class="flex justify-between items-center p-2 bg-[#f5f5f7] rounded text-sm">
              <div v-if="editingDisbMethodId === m.id" class="flex items-center gap-2 flex-1">
                <input v-model="editingDisbMethodName" class="input text-sm flex-1" @keyup.enter="saveEditDisbursementMethod" @keyup.escape="cancelEditDisbursementMethod">
                <button @click="saveEditDisbursementMethod" class="text-[#248a3d] text-xs font-medium">保存</button>
                <button @click="cancelEditDisbursementMethod" class="text-[#86868b] text-xs">取消</button>
              </div>
              <template v-else>
                <div>
                  <span class="font-medium">{{ m.name }}</span>
                  <span class="text-xs text-[#86868b] ml-1">({{ m.code }})</span>
                </div>
                <div>
                  <button @click="editDisbursementMethod(m)" class="text-[#0071e3] text-xs mr-2">编辑</button>
                  <button @click="handleDeleteDisbursementMethod(m.id)" class="text-[#ff3b30] text-xs">删除</button>
                </div>
              </template>
            </div>
            <div v-if="!disbursementMethods.length" class="text-[#86868b] text-center py-2 text-sm">暂无付款方式</div>
          </div>
          <form @submit.prevent="handleCreateDisbursementMethod" class="flex gap-2">
            <input v-model="newDisbMethodCode" class="input flex-1 text-sm" placeholder="编码(如 bank_abc)">
            <input v-model="newDisbMethodName" class="input flex-1 text-sm" placeholder="显示名称">
            <button type="submit" class="btn btn-primary btn-sm">添加</button>
          </form>
        </div>
      </div>

    </div>

    <!-- Logs Tab -->
    <div v-if="settingsTab === 'logs'">
      <div class="card p-4">
        <div class="flex gap-2 mb-3 flex-wrap">
          <select v-model="opLogFilter" @change="loadOpLogs" class="input w-auto text-sm">
            <option value="">全部操作</option>
            <option value="ORDER_CREATE">创建订单</option>
            <option value="PAYMENT_CREATE">账期收款</option>
            <option value="PAYMENT_CONFIRM">确认收款</option>
            <option value="STOCK_RESTOCK">入库</option>
            <option value="PURCHASE_CREATE">采购下单</option>
            <option value="PURCHASE_PAY">采购付款</option>
            <option value="PURCHASE_RECEIVE">采购收货</option>
            <option value="STOCK_TRANSFER">库存调拨</option>
            <option value="STOCK_ADJUST">库存调整</option>
            <option value="USER_CREATE">创建用户</option>
            <option value="USER_TOGGLE">禁用/启用用户</option>
          </select>
          <button @click="loadOpLogs" class="btn btn-secondary btn-sm">刷新</button>
        </div>
        <div class="space-y-1 max-h-[70vh] overflow-y-auto">
          <div v-for="log in opLogs" :key="log.id" class="flex justify-between items-start p-2 bg-[#f5f5f7] rounded text-xs">
            <div>
              <span class="font-medium text-[#0071e3]">{{ log.operator_name }}</span>
              <span class="mx-1 text-[#86868b]">·</span>
              <span>{{ log.detail }}</span>
            </div>
            <div class="text-[#86868b] whitespace-nowrap ml-2">{{ fmtDate(log.created_at) }}</div>
          </div>
          <div v-if="!opLogs.length" class="text-[#86868b] text-center py-4">暂无操作日志</div>
        </div>
      </div>
    </div>

    <!-- Permissions Tab -->
    <div v-if="settingsTab === 'permissions'" class="flex gap-5" style="min-height: 60vh">
      <!-- Left: User list -->
      <div class="w-56 shrink-0">
        <div class="card p-3">
          <h3 class="font-semibold mb-3 text-sm">选择用户</h3>
          <div class="space-y-1 max-h-[60vh] overflow-y-auto">
            <div v-for="u in users" :key="u.id"
              @click="selectPermUser(u)"
              :class="['flex items-center justify-between p-2.5 rounded-lg cursor-pointer text-sm transition-colors',
                permSelectedUser?.id === u.id ? 'bg-[#0071e3] text-white' : 'hover:bg-[#f5f5f7]']">
              <div>
                <div class="font-medium">{{ u.display_name || u.username }}</div>
                <div :class="['text-xs', permSelectedUser?.id === u.id ? 'text-white/70' : 'text-[#86868b]']">@{{ u.username }}</div>
              </div>
              <span v-if="u.role === 'admin'"
                :class="['text-xs px-1.5 py-0.5 rounded',
                  permSelectedUser?.id === u.id ? 'bg-white/20 text-white' : 'bg-[#e8f4fd] text-[#0071e3]']">管理员</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Right: Permission cards -->
      <div class="flex-1 min-w-0">
        <div v-if="!permSelectedUser" class="card p-12 text-center text-[#86868b] text-sm">
          <div class="text-3xl mb-3 opacity-30">🔐</div>
          请从左侧选择一个用户来管理权限
        </div>

        <div v-else-if="permSelectedUser.role === 'admin'" class="card p-12 text-center">
          <div class="text-3xl mb-3 opacity-30">👑</div>
          <div class="text-[#0071e3] font-semibold mb-1">{{ permSelectedUser.display_name || permSelectedUser.username }}</div>
          <div class="text-[#86868b] text-sm">管理员拥有全部权限，无需单独配置</div>
        </div>

        <div v-else>
          <div class="flex items-center justify-between mb-3">
            <div class="text-sm text-[#86868b]">
              正在编辑 <span class="font-semibold text-[#1d1d1f]">{{ permSelectedUser.display_name || permSelectedUser.username }}</span> 的权限
            </div>
            <button @click="savePermissions" class="btn btn-primary btn-sm">保存权限</button>
          </div>
          <div class="grid md:grid-cols-2 gap-3">
            <div v-for="group in permissionGroups" :key="group.main" class="card p-3">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <component :is="iconMap[group.icon]" class="w-4 h-4 text-[#0071e3]" />
                  <span class="font-semibold text-sm">{{ group.label }}</span>
                </div>
                <button type="button" @click="toggleMainPerm(group)"
                  :class="['w-10 h-[22px] rounded-full transition-colors relative shrink-0',
                    permUserPerms.includes(group.main) ? 'bg-[#34c759]' : 'bg-[#d2d2d7]']">
                  <span :class="['absolute top-[3px] left-[3px] w-4 h-4 bg-white rounded-full shadow-sm transition-transform',
                    permUserPerms.includes(group.main) ? 'translate-x-[18px]' : '']"></span>
                </button>
              </div>
              <div v-if="group.children.length && permUserPerms.includes(group.main)" class="space-y-2 mt-3 pt-3 border-t border-[#e5e5ea]">
                <div v-for="child in group.children" :key="child.key" class="flex items-center justify-between pl-6">
                  <span class="text-sm text-[#6e6e73]">{{ child.name }}</span>
                  <button type="button" @click="toggleChildPerm(child.key)"
                    :class="['w-9 h-5 rounded-full transition-colors relative shrink-0',
                      permUserPerms.includes(child.key) ? 'bg-[#34c759]' : 'bg-[#d2d2d7]']">
                    <span :class="['absolute top-[2px] left-[2px] w-4 h-4 bg-white rounded-full shadow-sm transition-transform',
                      permUserPerms.includes(child.key) ? 'translate-x-4' : '']"></span>
                  </button>
                </div>
              </div>
              <div v-else-if="group.children.length" class="text-xs text-[#86868b] mt-3 pt-3 border-t border-[#e5e5ea]">
                开启主开关后可配置子权限
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Warehouse Modal -->
    <div v-if="showWarehouseModal" class="modal-overlay active" @click.self="showWarehouseModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="modal-title">{{ warehouseForm.id ? '仓库改名 - ' + warehouseForm.name : '新建仓库' }}</h3>
          <button @click="showWarehouseModal = false" class="modal-close">&times;</button>
        </div>
        <form @submit.prevent="saveWarehouse" class="space-y-3 p-4">
          <div><label class="label">仓库名称 *</label><input v-model="warehouseForm.name" class="input" required placeholder="请输入新名称"></div>
          <div><label class="flex items-center"><input type="checkbox" v-model="warehouseForm.is_default" class="mr-2">设为默认仓库</label></div>
          <div v-if="accountSets.length">
            <label class="label">关联账套</label>
            <select v-model="warehouseForm.account_set_id" class="input">
              <option :value="null">不关联</option>
              <option v-for="s in accountSets" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </div>
          <div class="flex gap-3 pt-3">
            <button type="button" @click="showWarehouseModal = false" class="btn btn-secondary flex-1">取消</button>
            <button type="submit" class="btn btn-primary flex-1">保存</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Location Modal -->
    <div v-if="showLocationModal" class="modal-overlay active" @click.self="showLocationModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="modal-title">编辑仓位 - {{ locationForm.code }}</h3>
          <button @click="showLocationModal = false" class="modal-close">&times;</button>
        </div>
        <form @submit.prevent="saveLocation" class="space-y-3 p-4">
          <div><label class="label">仓位编号 *</label><input v-model="locationForm.code" class="input" required placeholder="如 A-01-02"></div>
          <div><label class="label">仓位名称</label><input v-model="locationForm.name" class="input" placeholder="可选，如：主通道左侧"></div>
          <div class="flex gap-3 pt-3">
            <button type="button" @click="showLocationModal = false" class="btn btn-secondary flex-1">取消</button>
            <button type="submit" class="btn btn-primary flex-1">保存</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Salesperson Modal -->
    <div v-if="showSalespersonModal" class="modal-overlay active" @click.self="showSalespersonModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="modal-title">{{ salespersonForm.id ? '编辑销售员 - ' + salespersonForm.name : '新建销售员' }}</h3>
          <button @click="showSalespersonModal = false" class="modal-close">&times;</button>
        </div>
        <form @submit.prevent="saveSalesperson" class="space-y-3 p-4">
          <div><label class="label">姓名 *</label><input v-model="salespersonForm.name" class="input" required placeholder="销售员姓名"></div>
          <div><label class="label">电话</label><input v-model="salespersonForm.phone" class="input" placeholder="可选"></div>
          <div class="flex gap-3 pt-3">
            <button type="button" @click="showSalespersonModal = false" class="btn btn-secondary flex-1">取消</button>
            <button type="submit" class="btn btn-primary flex-1">保存</button>
          </div>
        </form>
      </div>
    </div>

    <!-- User Modal -->
    <div v-if="showUserModal" class="modal-overlay active" @click.self="showUserModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="modal-title">{{ userForm.id ? '编辑用户' : '新增用户' }}</h3>
          <button @click="showUserModal = false" class="modal-close">&times;</button>
        </div>
        <form @submit.prevent="saveUser" class="space-y-3 p-4">
          <div><label class="label">用户名 *</label><input v-model="userForm.username" class="input" required :disabled="!!userForm.id"></div>
          <div><label class="label">显示名称</label><input v-model="userForm.display_name" class="input"></div>
          <div><label class="label">密码 {{ userForm.id ? '(留空不修改)' : '*' }}</label><input v-model="userForm.password" type="password" class="input" :required="!userForm.id"></div>
          <div>
            <label class="label">角色</label>
            <select v-model="userForm.role" class="input">
              <option value="user">普通用户</option>
              <option value="admin">管理员</option>
            </select>
          </div>
          <div v-if="userForm.role === 'user'">
            <label class="label">权限</label>
            <div class="bg-[#f5f5f7] rounded-lg p-3 text-sm text-[#6e6e73]">
              <span v-if="userForm.permissions?.length">已配置 {{ userForm.permissions.length }} 项权限</span>
              <span v-else>暂未配置权限</span>
              <span class="mx-1">·</span>
              <button type="button" @click="showUserModal = false; settingsTab = 'permissions'; selectPermUser(users.find(u => u.id === userForm.id))"
                class="text-[#0071e3] hover:underline">前往权限管理</button>
            </div>
          </div>
          <div class="flex gap-3 pt-3">
            <button type="button" @click="showUserModal = false" class="btn btn-secondary flex-1">取消</button>
            <button type="submit" class="btn btn-primary flex-1">保存</button>
          </div>
        </form>
      </div>
    </div>
    <!-- Restore Modal -->
    <div v-if="showRestoreModal" class="modal-overlay active" @click.self="showRestoreModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3 class="modal-title">备份恢复</h3>
          <button @click="showRestoreModal = false" class="modal-close">&times;</button>
        </div>
        <div class="p-4 space-y-4">
          <div class="text-sm text-[#6e6e73]">上传 <span class="font-medium">.sql</span> 或 <span class="font-medium">.db</span> 备份文件来恢复数据库。恢复前会自动备份当前数据。</div>
          <div class="border-2 border-dashed border-[#d2d2d7] rounded-lg p-6 text-center cursor-pointer hover:border-[#0071e3] transition-colors" @click="$refs.restoreFileInput.click()" @dragover.prevent @drop.prevent="handleRestoreFileDrop">
            <div v-if="!restoreFile" class="text-[#86868b] text-sm">点击选择文件 或 拖拽文件到此处</div>
            <div v-else class="text-sm">
              <div class="font-medium text-[#6e6e73]">{{ restoreFile.name }}</div>
              <div class="text-[#86868b] mt-1">{{ (restoreFile.size / 1024 / 1024).toFixed(2) }} MB</div>
            </div>
          </div>
          <input ref="restoreFileInput" type="file" accept=".sql,.db" class="hidden" @change="handleRestoreFileSelect">
          <div class="bg-[#fff8e1] border border-[#ffe082] rounded p-3 text-xs text-[#ff9f0a]">注意：恢复操作将覆盖当前数据库，请确认备份文件正确。恢复后页面将自动刷新。</div>
          <div class="flex gap-3">
            <button @click="showRestoreModal = false" class="btn btn-secondary flex-1">取消</button>
            <button @click="handleUploadRestore" class="btn btn-primary flex-1" :disabled="!restoreFile || restoreLoading" style="background:#16a34a">{{ restoreLoading ? '恢复中...' : '确认恢复' }}</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useAppStore } from '../stores/app'
import { useWarehousesStore } from '../stores/warehouses'
import { useSettingsStore } from '../stores/settings'
import { useFormat } from '../composables/useFormat'
import { changePassword } from '../api/auth'
import {
  createWarehouse, updateWarehouse, deleteWarehouse as deleteWarehouseApi,
  createLocation, updateLocation, deleteLocation as deleteLocationApi
} from '../api/warehouses'
import {
  createUser, updateUser, toggleUser as toggleUserApi,
  createBackup as createBackupApi, downloadBackup as downloadBackupApi,
  deleteBackup as deleteBackupApi, restoreBackup as restoreBackupApi, uploadRestoreBackup,
  createPaymentMethod, updatePaymentMethod, deletePaymentMethod as deletePaymentMethodApi,
  createDisbursementMethod, updateDisbursementMethod, deleteDisbursementMethod as deleteDisbursementMethodApi
} from '../api/settings'
import { createSalesperson, updateSalesperson, deleteSalesperson as deleteSalespersonApi } from '../api/salespersons'
import { createSnConfig, deleteSnConfig as deleteSnConfigApi } from '../api/sn'
import { getAccountSets } from '../api/accounting'
import { getOpLogs } from '../api/settings'
import { allPermissions, permissionGroups, iconMap } from '../utils/constants'
import { usePermission } from '../composables/usePermission'

const authStore = useAuthStore()
const appStore = useAppStore()
const warehousesStore = useWarehousesStore()
const settingsStore = useSettingsStore()
const { fmt, fmtDate } = useFormat()
const { hasPermission } = usePermission()
const warehouses = computed(() => warehousesStore.warehouses)
const locations = computed(() => warehousesStore.locations)
const users = computed(() => settingsStore.users)
const salespersons = computed(() => settingsStore.salespersons)
const paymentMethods = computed(() => settingsStore.paymentMethods)
const disbursementMethods = computed(() => settingsStore.disbursementMethods)
const backups = computed(() => settingsStore.backups)
const opLogs = computed(() => settingsStore.opLogs)
const snConfigs = computed(() => settingsStore.snConfigs)
const productBrands = computed(() => settingsStore.productBrands)

// Account sets for warehouse association
const accountSets = ref([])

// Tab state
const settingsTab = ref('general')

// Password form
const pwdForm = reactive({ old_password: '', new_password: '', confirm_password: '' })

// Warehouse
const newWarehouseName = ref('')
const showWarehouseModal = ref(false)
const warehouseForm = reactive({ id: null, name: '', is_default: false, account_set_id: null })

// Location
const newLocationInputs = ref({})
const getLocationInput = (whId) => {
  if (!newLocationInputs.value[whId]) {
    newLocationInputs.value[whId] = { code: '', name: '' }
  }
  return newLocationInputs.value[whId]
}
const showLocationModal = ref(false)
const locationForm = reactive({ id: null, code: '', name: '' })
const expandedWarehouse = ref(null)

const toggleExpandWarehouse = (id) => {
  expandedWarehouse.value = expandedWarehouse.value === id ? null : id
}

// Salesperson
const newSalespersonName = ref('')
const newSalespersonPhone = ref('')
const showSalespersonModal = ref(false)
const salespersonForm = reactive({ id: null, name: '', phone: '' })

// User
const showUserModal = ref(false)
const userForm = reactive({ id: null, username: '', display_name: '', role: 'user', permissions: [], password: '' })

// Payment methods
const newPayMethodCode = ref('')
const newPayMethodName = ref('')
const editingPayMethodId = ref(null)
const editingPayMethodName = ref('')

// Disbursement methods
const newDisbMethodCode = ref('')
const newDisbMethodName = ref('')
const editingDisbMethodId = ref(null)
const editingDisbMethodName = ref('')

// SN config
const newSnConfigWarehouse = ref('')
const newSnConfigBrand = ref('')

// Company name

// Backup
const backupLoading = ref(false)
const restoreLoading = ref(false)
const showRestoreModal = ref(false)
const restoreFile = ref(null)

// Permissions management
const permSelectedUser = ref(null)
const permUserPerms = ref([])

// Op logs
const opLogFilter = ref('')

// === Password ===
const handleChangePassword = async () => {
  if (!pwdForm.old_password || !pwdForm.new_password) {
    appStore.showToast('请填写完整', 'error')
    return
  }
  if (pwdForm.new_password.length < 6) {
    appStore.showToast('新密码长度不能少于6位', 'error')
    return
  }
  if (pwdForm.new_password !== pwdForm.confirm_password) {
    appStore.showToast('两次输入的新密码不一致', 'error')
    return
  }
  try {
    await changePassword({ old_password: pwdForm.old_password, new_password: pwdForm.new_password })
    appStore.showToast('密码修改成功')
    Object.assign(pwdForm, { old_password: '', new_password: '', confirm_password: '' })
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '密码修改失败', 'error')
  }
}

// === Warehouses ===
const editWarehouse = (w) => {
  Object.assign(warehouseForm, { id: w.id, name: w.name, is_default: w.is_default, account_set_id: w.account_set_id || null })
  showWarehouseModal.value = true
}

const saveWarehouse = async () => {
  if (!warehouseForm.name || !warehouseForm.name.trim()) {
    appStore.showToast('请输入仓库名称', 'error')
    return
  }
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    await updateWarehouse(warehouseForm.id, { name: warehouseForm.name.trim(), is_default: warehouseForm.is_default, account_set_id: warehouseForm.account_set_id || null })
    appStore.showToast('保存成功')
    showWarehouseModal.value = false
    warehousesStore.loadWarehouses()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

const handleCreateWarehouse = async () => {
  if (!newWarehouseName.value) return
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    await createWarehouse({ name: newWarehouseName.value })
    appStore.showToast('创建成功')
    newWarehouseName.value = ''
    warehousesStore.loadWarehouses()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '创建失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

const handleDeleteWarehouse = async (id) => {
  if (!await appStore.customConfirm('删除确认', '确定删除该仓库？')) return
  try {
    await deleteWarehouseApi(id)
    appStore.showToast('已删除')
    warehousesStore.loadWarehouses()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '删除失败', 'error')
  }
}

const handleSetDefaultWarehouse = async (id) => {
  try {
    await updateWarehouse(id, { is_default: true })
    appStore.showToast('默认仓库已切换')
    warehousesStore.loadWarehouses()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '操作失败', 'error')
  }
}

// === Locations ===
const editLocation = (loc, warehouseId) => {
  Object.assign(locationForm, { id: loc.id, code: loc.code, name: loc.name || '' })
  showLocationModal.value = true
}

const saveLocation = async () => {
  if (!locationForm.code || !locationForm.code.trim()) {
    appStore.showToast('请输入仓位编号', 'error')
    return
  }
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    await updateLocation(locationForm.id, { code: locationForm.code.trim(), name: locationForm.name || null })
    appStore.showToast('保存成功')
    showLocationModal.value = false
    warehousesStore.loadWarehouses()
    warehousesStore.loadLocations()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

const handleCreateLocation = async (warehouseId) => {
  const input = getLocationInput(warehouseId)
  if (!input.code || !input.code.trim()) return
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    await createLocation({ warehouse_id: warehouseId, code: input.code.trim(), name: input.name.trim() || null })
    appStore.showToast('创建成功')
    input.code = ''
    input.name = ''
    warehousesStore.loadWarehouses()
    warehousesStore.loadLocations()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '创建失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

const handleDeleteLocation = async (id) => {
  if (!await appStore.customConfirm('删除确认', '确定删除该仓位？')) return
  try {
    await deleteLocationApi(id)
    appStore.showToast('已删除')
    warehousesStore.loadWarehouses()
    warehousesStore.loadLocations()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '删除失败', 'error')
  }
}

// === Salespersons ===
const editSalesperson = (s) => {
  Object.assign(salespersonForm, { id: s.id, name: s.name, phone: s.phone })
  showSalespersonModal.value = true
}

const saveSalesperson = async () => {
  if (!salespersonForm.name || !salespersonForm.name.trim()) {
    appStore.showToast('请输入销售员姓名', 'error')
    return
  }
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    await updateSalesperson(salespersonForm.id, { name: salespersonForm.name.trim(), phone: salespersonForm.phone || null })
    appStore.showToast('保存成功')
    showSalespersonModal.value = false
    settingsStore.loadSalespersons()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

const handleCreateSalesperson = async () => {
  if (!newSalespersonName.value || !newSalespersonName.value.trim()) return
  try {
    await createSalesperson({ name: newSalespersonName.value.trim(), phone: newSalespersonPhone.value.trim() || null })
    appStore.showToast('创建成功')
    newSalespersonName.value = ''
    newSalespersonPhone.value = ''
    settingsStore.loadSalespersons()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '创建失败', 'error')
  }
}

const handleDeleteSalesperson = async (id) => {
  if (!await appStore.customConfirm('删除确认', '确定删除该销售员？')) return
  try {
    await deleteSalespersonApi(id)
    appStore.showToast('已删除')
    settingsStore.loadSalespersons()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '删除失败', 'error')
  }
}

// === Users ===
const openUserForm = () => {
  Object.assign(userForm, { id: null, username: '', display_name: '', role: 'user', permissions: [], password: '' })
  showUserModal.value = true
}

const editUser = (u) => {
  Object.assign(userForm, {
    id: u.id, username: u.username, display_name: u.display_name,
    role: u.role, permissions: u.permissions || [], password: ''
  })
  showUserModal.value = true
}

const saveUser = async () => {
  if (appStore.submitting) return
  appStore.submitting = true
  try {
    if (userForm.id) {
      await updateUser(userForm.id, userForm)
    } else {
      await createUser(userForm)
    }
    appStore.showToast('保存成功')
    showUserModal.value = false
    settingsStore.loadUsers()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

const handleToggleUser = async (id) => {
  try {
    await toggleUserApi(id)
    settingsStore.loadUsers()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '操作失败', 'error')
  }
}

// === Backup ===
const loadBackups = () => settingsStore.loadBackups()

const handleCreateBackup = async () => {
  backupLoading.value = true
  try {
    await createBackupApi()
    appStore.showToast('备份成功')
    loadBackups()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '备份失败', 'error')
  } finally {
    backupLoading.value = false
  }
}

const handleDownloadBackup = async (filename) => {
  try {
    const { data } = await downloadBackupApi(filename)
    const url = URL.createObjectURL(new Blob([data]))
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    appStore.showToast('下载失败', 'error')
  }
}

const handleRestoreFileSelect = (e) => {
  restoreFile.value = e.target.files[0] || null
}

const handleRestoreFileDrop = (e) => {
  const file = e.dataTransfer.files[0]
  if (file) restoreFile.value = file
}

const handleUploadRestore = async () => {
  if (!restoreFile.value) return
  if (!await appStore.customConfirm('恢复确认', `确定使用 "${restoreFile.value.name}" 恢复数据库？此操作将覆盖当前数据，恢复前会自动备份。`)) return
  restoreLoading.value = true
  try {
    await uploadRestoreBackup(restoreFile.value)
    appStore.showToast('恢复成功，页面即将刷新')
    showRestoreModal.value = false
    setTimeout(() => location.reload(), 1000)
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '恢复失败', 'error')
  } finally {
    restoreLoading.value = false
  }
}

const handleDeleteBackup = async (filename) => {
  if (!await appStore.customConfirm('删除确认', '确定删除此备份？')) return
  try {
    await deleteBackupApi(filename)
    appStore.showToast('已删除')
    loadBackups()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '删除失败', 'error')
  }
}

// === Payment Methods ===
const editPaymentMethod = (m) => {
  editingPayMethodId.value = m.id
  editingPayMethodName.value = m.name
}

const saveEditPaymentMethod = async () => {
  if (!editingPayMethodName.value.trim()) {
    appStore.showToast('名称不能为空', 'error')
    return
  }
  try {
    await updatePaymentMethod(editingPayMethodId.value, { name: editingPayMethodName.value.trim() })
    appStore.showToast('修改成功')
    editingPayMethodId.value = null
    editingPayMethodName.value = ''
    settingsStore.loadPaymentMethods()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '修改失败', 'error')
  }
}

const cancelEditPaymentMethod = () => {
  editingPayMethodId.value = null
  editingPayMethodName.value = ''
}

const handleCreatePaymentMethod = async () => {
  if (!newPayMethodCode.value.trim() || !newPayMethodName.value.trim()) {
    appStore.showToast('请填写编码和名称', 'error')
    return
  }
  try {
    await createPaymentMethod({ code: newPayMethodCode.value.trim(), name: newPayMethodName.value.trim() })
    appStore.showToast('创建成功')
    newPayMethodCode.value = ''
    newPayMethodName.value = ''
    settingsStore.loadPaymentMethods()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '创建失败', 'error')
  }
}

const handleDeletePaymentMethod = async (id) => {
  if (!await appStore.customConfirm('删除确认', '确定删除该收款方式？')) return
  try {
    await deletePaymentMethodApi(id)
    appStore.showToast('已删除')
    settingsStore.loadPaymentMethods()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '删除失败', 'error')
  }
}

// === Disbursement Methods ===
const editDisbursementMethod = (m) => {
  editingDisbMethodId.value = m.id
  editingDisbMethodName.value = m.name
}

const saveEditDisbursementMethod = async () => {
  if (!editingDisbMethodName.value.trim()) {
    appStore.showToast('名称不能为空', 'error')
    return
  }
  try {
    await updateDisbursementMethod(editingDisbMethodId.value, { name: editingDisbMethodName.value.trim() })
    appStore.showToast('修改成功')
    editingDisbMethodId.value = null
    editingDisbMethodName.value = ''
    settingsStore.loadDisbursementMethods()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '修改失败', 'error')
  }
}

const cancelEditDisbursementMethod = () => {
  editingDisbMethodId.value = null
  editingDisbMethodName.value = ''
}

const handleCreateDisbursementMethod = async () => {
  if (!newDisbMethodCode.value.trim() || !newDisbMethodName.value.trim()) {
    appStore.showToast('编码和名称不能为空', 'error')
    return
  }
  try {
    await createDisbursementMethod({ code: newDisbMethodCode.value.trim(), name: newDisbMethodName.value.trim() })
    appStore.showToast('添加成功')
    newDisbMethodCode.value = ''
    newDisbMethodName.value = ''
    settingsStore.loadDisbursementMethods()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '添加失败', 'error')
  }
}

const handleDeleteDisbursementMethod = async (id) => {
  if (!await appStore.customConfirm('删除确认', '确定删除该付款方式？')) return
  try {
    await deleteDisbursementMethodApi(id)
    appStore.showToast('已删除')
    settingsStore.loadDisbursementMethods()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '删除失败', 'error')
  }
}

// === Company Name ===
// === SN Config ===
const handleCreateSnConfig = async () => {
  if (!newSnConfigWarehouse.value || !newSnConfigBrand.value) {
    appStore.showToast('请选择仓库和品牌', 'error')
    return
  }
  try {
    await createSnConfig({ warehouse_id: parseInt(newSnConfigWarehouse.value), brand: newSnConfigBrand.value })
    appStore.showToast('配置已添加')
    newSnConfigWarehouse.value = ''
    newSnConfigBrand.value = ''
    settingsStore.loadSnConfigs()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '添加失败', 'error')
  }
}

const handleDeleteSnConfig = async (id) => {
  if (!await appStore.customConfirm('删除确认', '确定删除该SN配置？')) return
  try {
    await deleteSnConfigApi(id)
    appStore.showToast('已删除')
    settingsStore.loadSnConfigs()
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '删除失败', 'error')
  }
}

// === Permissions Management ===
const selectPermUser = (u) => {
  if (!u) return
  permSelectedUser.value = u
  permUserPerms.value = [...(u.permissions || [])]
}

const toggleMainPerm = (group) => {
  const idx = permUserPerms.value.indexOf(group.main)
  if (idx >= 0) {
    // Turn off main → remove main + all children
    permUserPerms.value.splice(idx, 1)
    for (const child of group.children) {
      const ci = permUserPerms.value.indexOf(child.key)
      if (ci >= 0) permUserPerms.value.splice(ci, 1)
    }
  } else {
    permUserPerms.value.push(group.main)
  }
}

const toggleChildPerm = (key) => {
  const idx = permUserPerms.value.indexOf(key)
  if (idx >= 0) {
    permUserPerms.value.splice(idx, 1)
  } else {
    permUserPerms.value.push(key)
  }
}

const savePermissions = async () => {
  if (!permSelectedUser.value || appStore.submitting) return
  appStore.submitting = true
  try {
    await updateUser(permSelectedUser.value.id, { permissions: permUserPerms.value })
    appStore.showToast('权限已保存')
    await settingsStore.loadUsers()
    // Refresh selected user data
    const updated = users.value.find(u => u.id === permSelectedUser.value.id)
    if (updated) permSelectedUser.value = updated
  } catch (e) {
    appStore.showToast(e.response?.data?.detail || '保存失败', 'error')
  } finally {
    appStore.submitting = false
  }
}

// === Op Logs ===
const loadOpLogs = () => {
  const params = {}
  if (opLogFilter.value) params.action = opLogFilter.value
  settingsStore.loadOpLogs(params)
}

// === Mount ===
onMounted(async () => {
  warehousesStore.loadWarehouses()
  warehousesStore.loadLocations()
  settingsStore.loadSalespersons()
  settingsStore.loadSnConfigs()
  settingsStore.loadProductBrands()
  settingsStore.loadPaymentMethods()
  settingsStore.loadDisbursementMethods()
  if (hasPermission('admin')) {
    settingsStore.loadUsers()
    settingsStore.loadBackups()
  }
  try {
    const { data } = await getAccountSets()
    accountSets.value = data
  } catch (e) { /* ignore */ }
})
</script>

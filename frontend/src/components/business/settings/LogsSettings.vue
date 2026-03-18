<!--
  系统日志组件
  功能：操作日志列表展示、按操作类型筛选、刷新
  从 SettingsView.vue 系统日志标签页提取
-->
<template>
  <div class="card p-4">
    <!-- 筛选栏 -->
    <div class="flex gap-2 mb-3 flex-wrap">
      <select v-model="opLogFilter" @change="loadOpLogs" class="input w-auto text-sm">
        <option value="">全部操作</option>
        <optgroup label="认证安全">
          <option value="LOGIN_SUCCESS">登录成功</option>
          <option value="LOGIN_FAIL">登录失败</option>
          <option value="PASSWORD_CHANGE">修改密码</option>
        </optgroup>
        <optgroup label="用户管理">
          <option value="USER_CREATE">创建用户</option>
          <option value="USER_TOGGLE">禁用/启用用户</option>
          <option value="USER_ROLE_CHANGE">角色变更</option>
          <option value="USER_PERMISSION_CHANGE">权限变更</option>
        </optgroup>
        <optgroup label="订单">
          <option value="ORDER_CREATE">创建订单</option>
          <option value="ORDER_CANCEL">取消订单</option>
          <option value="ORDER_UPDATE_REMARK">修改备注</option>
        </optgroup>
        <optgroup label="代发货">
          <option value="DROPSHIP_CREATE">创建代发</option>
          <option value="DROPSHIP_SUBMIT">提交代发</option>
          <option value="DROPSHIP_SHIP">代发发货</option>
          <option value="DROPSHIP_COMPLETE">完成代发</option>
          <option value="DROPSHIP_CANCEL">取消代发</option>
          <option value="DROPSHIP_BATCH_PAY">批量支付</option>
        </optgroup>
        <optgroup label="采购">
          <option value="PURCHASE_CREATE">采购下单</option>
          <option value="PURCHASE_PAY">采购付款</option>
          <option value="PURCHASE_APPROVE">采购审核</option>
          <option value="PURCHASE_REJECT">采购拒绝</option>
          <option value="PURCHASE_CANCEL">采购取消</option>
          <option value="PURCHASE_RECEIVE">采购收货</option>
          <option value="PURCHASE_RETURN">采购退货</option>
        </optgroup>
        <optgroup label="库存">
          <option value="STOCK_RESTOCK">入库</option>
          <option value="STOCK_ADJUST">库存调整</option>
          <option value="STOCK_TRANSFER">库存调拨</option>
        </optgroup>
        <optgroup label="物流">
          <option value="SHIPMENT_CREATE">创建发货单</option>
          <option value="SHIPMENT_UPDATE">更新发货单</option>
          <option value="SHIPMENT_DELETE">删除发货单</option>
        </optgroup>
        <optgroup label="财务收款">
          <option value="PAYMENT_CREATE">账期收款</option>
          <option value="PAYMENT_CONFIRM">确认收款</option>
        </optgroup>
        <optgroup label="发票">
          <option value="INVOICE_CREATE">创建发票</option>
          <option value="INVOICE_UPDATE">更新发票</option>
          <option value="INVOICE_CONFIRM">确认发票</option>
          <option value="INVOICE_CANCEL">作废发票</option>
          <option value="INVOICE_UPLOAD_PDF">上传发票 PDF</option>
          <option value="INVOICE_DELETE_PDF">删除发票 PDF</option>
        </optgroup>
        <optgroup label="凭证">
          <option value="VOUCHER_CREATE">创建凭证</option>
          <option value="VOUCHER_UPDATE">更新凭证</option>
          <option value="VOUCHER_DELETE">删除凭证</option>
          <option value="VOUCHER_SUBMIT">提交凭证</option>
          <option value="VOUCHER_APPROVE">审核凭证</option>
          <option value="VOUCHER_REJECT">驳回凭证</option>
          <option value="VOUCHER_POST">过账</option>
          <option value="VOUCHER_UNPOST">反过账</option>
          <option value="VOUCHER_BATCH_SUBMIT">批量提交</option>
          <option value="VOUCHER_BATCH_APPROVE">批量审核</option>
          <option value="VOUCHER_BATCH_POST">批量过账</option>
        </optgroup>
        <optgroup label="客户/供应商">
          <option value="CUSTOMER_CREATE">新建客户</option>
          <option value="CUSTOMER_UPDATE">更新客户</option>
          <option value="CUSTOMER_DELETE">删除客户</option>
          <option value="SUPPLIER_CREATE">新建供应商</option>
          <option value="SUPPLIER_UPDATE">更新供应商</option>
          <option value="SUPPLIER_DELETE">删除供应商</option>
          <option value="SUPPLIER_IMPORT">导入供应商</option>
          <option value="CREDIT_REFUND">在账资金退款</option>
        </optgroup>
        <optgroup label="产品">
          <option value="PRODUCT_CREATE">新建产品</option>
          <option value="PRODUCT_UPDATE">更新产品</option>
          <option value="PRODUCT_DELETE">删除产品</option>
          <option value="PRODUCT_IMPORT">导入产品</option>
        </optgroup>
        <optgroup label="样机管理">
          <option value="DEMO_CREATE">新建样机</option>
          <option value="DEMO_UPDATE">更新样机</option>
          <option value="DEMO_DELETE">删除样机</option>
          <option value="DEMO_LOAN_CREATE">借出申请</option>
          <option value="DEMO_LOAN_APPROVE">审批借出</option>
          <option value="DEMO_LEND">执行借出</option>
          <option value="DEMO_RETURN">归还样机</option>
          <option value="DEMO_SELL">出售样机</option>
          <option value="DEMO_SCRAP">报废样机</option>
          <option value="DEMO_LOSS">报损样机</option>
        </optgroup>
        <optgroup label="配置管理">
          <option value="ACCOUNT_CREATE">新建科目</option>
          <option value="ACCOUNT_UPDATE">更新科目</option>
          <option value="ACCOUNT_DEACTIVATE">停用科目</option>
          <option value="DEPARTMENT_CREATE">新建部门</option>
          <option value="DEPARTMENT_UPDATE">更新部门</option>
          <option value="DEPARTMENT_DELETE">删除部门</option>
          <option value="WAREHOUSE_CREATE">新建仓库</option>
          <option value="WAREHOUSE_UPDATE">更新仓库</option>
          <option value="WAREHOUSE_DELETE">删除仓库</option>
          <option value="CONSIGNMENT_RETURN">寄售归还</option>
        </optgroup>
        <optgroup label="数据导出">
          <option value="PRODUCT_EXPORT">导出产品</option>
          <option value="STOCK_EXPORT">导出库存</option>
          <option value="ORDER_EXPORT">导出订单</option>
          <option value="PURCHASE_EXPORT">导出采购单</option>
          <option value="VOUCHER_EXPORT">导出凭证</option>
          <option value="LEDGER_EXPORT">导出账簿</option>
          <option value="REPORT_EXPORT">导出报表</option>
          <option value="DEMO_EXPORT">导出样机</option>
          <option value="AI_EXPORT">AI 导出</option>
        </optgroup>
        <optgroup label="系统">
          <option value="BACKUP_CREATE">创建备份</option>
          <option value="BACKUP_RESTORE">恢复备份</option>
          <option value="BACKUP_DOWNLOAD">下载备份</option>
          <option value="BACKUP_DELETE">删除备份</option>
        </optgroup>
      </select>
      <button @click="loadOpLogs" class="btn btn-secondary btn-sm">刷新</button>
    </div>
    <!-- 日志列表 -->
    <div class="space-y-1 max-h-[70vh] overflow-y-auto">
      <div v-for="log in opLogs" :key="log.id" class="flex justify-between items-start p-2 bg-elevated rounded text-xs">
        <div>
          <span class="font-medium text-primary">{{ log.operator_name }}</span>
          <span class="mx-1 text-muted">·</span>
          <span>{{ log.detail }}</span>
        </div>
        <div class="text-muted whitespace-nowrap ml-2">{{ fmtDate(log.created_at) }}</div>
      </div>
      <div v-if="!opLogs.length" class="text-muted text-center py-4">暂无操作日志</div>
    </div>
  </div>
</template>

<script setup>
/**
 * 系统操作日志
 * 包含：日志列表、按操作类型筛选、日期格式化
 */
import { ref, computed, onMounted } from 'vue'
import { useSettingsStore } from '../../../stores/settings'
import { useFormat } from '../../../composables/useFormat'

const settingsStore = useSettingsStore()
const { fmtDate } = useFormat()
const opLogs = computed(() => settingsStore.opLogs)

// 日志筛选条件
const opLogFilter = ref('')

// 加载操作日志
const loadOpLogs = () => {
  const params = {}
  if (opLogFilter.value) params.action = opLogFilter.value
  settingsStore.loadOpLogs(params)
}

// 组件挂载时自动加载日志
onMounted(() => {
  loadOpLogs()
})
</script>

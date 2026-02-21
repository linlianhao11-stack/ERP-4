<template>
  <div class="guide-page">
    <div class="guide-header">
      <h1 class="text-2xl font-bold mb-1">轻量级ERP系统 v4.8 使用手册</h1>
      <p class="text-[#86868b] text-sm">完整功能指南</p>
    </div>

    <!-- Table of Contents -->
    <div class="card p-4 mb-5">
      <h2 class="font-semibold mb-3 text-sm">目录</h2>
      <div class="grid grid-cols-2 md:grid-cols-5 gap-2">
        <button
          v-for="sec in sections"
          :key="sec.key"
          class="btn btn-sm text-left"
          :class="guideSection === sec.key ? 'btn-primary' : 'btn-secondary'"
          @click="guideSection = sec.key"
        >{{ sec.label }}</button>
      </div>
    </div>

    <!-- Overview -->
    <div v-if="guideSection === 'overview'" class="guide-section">
      <h2 class="text-lg font-bold mb-4">系统概述</h2>

      <h3 class="font-semibold mt-4 mb-2">系统简介</h3>
      <p class="text-sm text-[#6e6e73] mb-4">本系统是一套轻量级的企业资源管理系统（ERP），专为中小型贸易公司设计，支持多仓库管理、库存进销存、寄售业务、客户账期、财务管理等核心功能。</p>

      <h3 class="font-semibold mt-4 mb-2">核心功能模块</h3>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-[#f5f5f7]">模块</th><th class="px-3 py-2 text-left bg-[#f5f5f7]">功能说明</th><th class="px-3 py-2 text-left bg-[#f5f5f7]">适用人员</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2"><span class="badge badge-blue">首页</span></td><td class="px-3 py-2">查看销售概况、库存预警、待办事项等关键数据</td><td class="px-3 py-2">所有人员</td></tr>
            <tr><td class="px-3 py-2"><span class="badge badge-green">销售</span></td><td class="px-3 py-2">创建销售订单、退货单、寄售结算单等</td><td class="px-3 py-2">销售人员</td></tr>
            <tr><td class="px-3 py-2"><span class="badge badge-purple">库存</span></td><td class="px-3 py-2">查看库存、入库、调拨、导入导出库存数据</td><td class="px-3 py-2">仓管人员</td></tr>
            <tr><td class="px-3 py-2"><span class="badge badge-yellow">寄售</span></td><td class="px-3 py-2">管理寄售客户的库存、结算和退货</td><td class="px-3 py-2">销售/财务</td></tr>
            <tr><td class="px-3 py-2"><span class="badge badge-red">财务</span></td><td class="px-3 py-2">订单明细、收款记录、出入库日志、账款管理</td><td class="px-3 py-2">财务人员</td></tr>
            <tr><td class="px-3 py-2"><span class="badge badge-blue">客户</span></td><td class="px-3 py-2">客户信息管理、交易明细、欠款查询</td><td class="px-3 py-2">销售/财务</td></tr>
            <tr><td class="px-3 py-2"><span class="badge badge-purple">设置</span></td><td class="px-3 py-2">仓库管理、仓位管理、用户权限管理</td><td class="px-3 py-2">管理员</td></tr>
          </tbody>
        </table>
      </div>

      <h3 class="font-semibold mt-4 mb-2">订单类型说明</h3>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-[#f5f5f7]">类型</th><th class="px-3 py-2 text-left bg-[#f5f5f7]">说明</th><th class="px-3 py-2 text-left bg-[#f5f5f7]">库存影响</th><th class="px-3 py-2 text-left bg-[#f5f5f7]">账款影响</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2"><span class="badge badge-green">现款</span></td><td class="px-3 py-2">现金/即时付款的销售订单</td><td class="px-3 py-2">减少库存</td><td class="px-3 py-2">立即结清</td></tr>
            <tr><td class="px-3 py-2"><span class="badge badge-yellow">账期</span></td><td class="px-3 py-2">赊销订单，客户可延期付款</td><td class="px-3 py-2">减少库存</td><td class="px-3 py-2">形成应收账款</td></tr>
            <tr><td class="px-3 py-2"><span class="badge badge-purple">寄售调拨</span></td><td class="px-3 py-2">将库存调拨给客户寄售</td><td class="px-3 py-2">转入寄售仓</td><td class="px-3 py-2">无</td></tr>
            <tr><td class="px-3 py-2"><span class="badge badge-blue">寄售结算</span></td><td class="px-3 py-2">结算客户已售出的寄售商品</td><td class="px-3 py-2">无</td><td class="px-3 py-2">根据付款方式</td></tr>
            <tr><td class="px-3 py-2"><span class="badge badge-red">退货</span></td><td class="px-3 py-2">客户退回已购商品</td><td class="px-3 py-2">增加库存</td><td class="px-3 py-2">减少应收/退款</td></tr>
          </tbody>
        </table>
      </div>

      <h3 class="font-semibold mt-4 mb-2">权限说明</h3>
      <div class="overflow-x-auto">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-[#f5f5f7]">权限</th><th class="px-3 py-2 text-left bg-[#f5f5f7]">可访问的功能</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2">首页</td><td class="px-3 py-2">查看仪表盘数据统计</td></tr>
            <tr><td class="px-3 py-2">销售</td><td class="px-3 py-2">创建销售订单、寄售管理、客户管理</td></tr>
            <tr><td class="px-3 py-2">查看库存</td><td class="px-3 py-2">查看库存列表和库存详情</td></tr>
            <tr><td class="px-3 py-2">编辑库存</td><td class="px-3 py-2">入库、调拨、导入导出、商品管理</td></tr>
            <tr><td class="px-3 py-2">财务</td><td class="px-3 py-2">查看订单明细、收款、出入库日志</td></tr>
            <tr><td class="px-3 py-2">日志</td><td class="px-3 py-2">查看系统操作日志</td></tr>
            <tr><td class="px-3 py-2">管理员</td><td class="px-3 py-2">用户管理、系统设置</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Sales -->
    <div v-if="guideSection === 'sales'" class="guide-section">
      <h2 class="text-lg font-bold mb-4">销售管理</h2>

      <h3 class="font-semibold mt-4 mb-2">创建销售订单</h3>
      <div class="space-y-3 mb-4">
        <div v-for="(step, i) in salesSteps" :key="i" class="flex gap-3 items-start">
          <div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">{{ i + 1 }}</div>
          <div class="text-sm"><strong>{{ step.title }}</strong><br><span class="text-[#6e6e73]">{{ step.desc }}</span></div>
        </div>
      </div>

      <div class="bg-[#e8f4fd] border border-[#b3d7f5] rounded p-3 mb-4 text-sm text-[#0071e3]">
        <strong>使用在账资金</strong><br>
        如果客户有在账资金（如之前退货产生的余额），在确认订单时可以勾选「使用在账资金抵扣」，系统会自动抵扣。
      </div>

      <h3 class="font-semibold mt-4 mb-2">处理退货</h3>
      <div class="space-y-3 mb-4">
        <div v-for="(step, i) in returnSteps" :key="i" class="flex gap-3 items-start">
          <div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">{{ i + 1 }}</div>
          <div class="text-sm"><strong>{{ step.title }}</strong><br><span class="text-[#6e6e73]">{{ step.desc }}</span></div>
        </div>
      </div>

      <div class="bg-[#fff8e1] border border-[#ffe082] rounded p-3 mb-4 text-sm text-[#ff9f0a]">
        <strong>注意事项</strong><br>
        <ul class="list-disc list-inside mt-1 space-y-0.5">
          <li>退货数量不能超过原订单中该商品的数量</li>
          <li>退货会自动增加库存并记录入库日志</li>
          <li>如果原订单是账期订单，退货会减少应收账款</li>
        </ul>
      </div>

      <h3 class="font-semibold mt-4 mb-2">购物车操作</h3>
      <div class="overflow-x-auto">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-[#f5f5f7]">操作</th><th class="px-3 py-2 text-left bg-[#f5f5f7]">说明</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2">修改数量</td><td class="px-3 py-2">直接在数量输入框中修改，或使用 +/- 按钮</td></tr>
            <tr><td class="px-3 py-2">修改单价</td><td class="px-3 py-2">点击单价可直接编辑，支持折扣销售</td></tr>
            <tr><td class="px-3 py-2">删除商品</td><td class="px-3 py-2">点击商品行右侧的删除按钮</td></tr>
            <tr><td class="px-3 py-2">选择仓位</td><td class="px-3 py-2">先选仓库，再选仓位，系统显示可用库存</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Stock -->
    <div v-if="guideSection === 'stock'" class="guide-section">
      <h2 class="text-lg font-bold mb-4">库存管理</h2>

      <h3 class="font-semibold mt-4 mb-2">库存列表说明</h3>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-[#f5f5f7]">列</th><th class="px-3 py-2 text-left bg-[#f5f5f7]">说明</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2">SKU</td><td class="px-3 py-2">商品唯一编码</td></tr>
            <tr><td class="px-3 py-2">商品名称</td><td class="px-3 py-2">商品的名称描述</td></tr>
            <tr><td class="px-3 py-2">品牌/分类</td><td class="px-3 py-2">商品的品牌和分类信息</td></tr>
            <tr><td class="px-3 py-2">库存</td><td class="px-3 py-2">点击展开查看各仓位详细库存</td></tr>
            <tr><td class="px-3 py-2">加权成本</td><td class="px-3 py-2">按照加权平均法计算的单位成本</td></tr>
            <tr><td class="px-3 py-2">库龄</td><td class="px-3 py-2">库存的平均存放天数，颜色越红表示库龄越长</td></tr>
          </tbody>
        </table>
      </div>

      <h3 class="font-semibold mt-4 mb-2">入库操作</h3>
      <div class="space-y-3 mb-4">
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">1</div><div class="text-sm"><strong>选择仓库和仓位</strong><br><span class="text-[#6e6e73]">选择商品要入库的目标仓库和仓位</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">2</div><div class="text-sm"><strong>选择商品</strong><br><span class="text-[#6e6e73]">在搜索框中输入SKU或名称，选择要入库的商品</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">3</div><div class="text-sm"><strong>输入数量和成本</strong><br><span class="text-[#6e6e73]">输入入库数量和本批次的采购成本单价</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">4</div><div class="text-sm"><strong>确认入库</strong><br><span class="text-[#6e6e73]">点击确认完成入库，系统自动计算新的加权成本和库龄</span></div></div>
      </div>

      <div class="bg-[#e8f4fd] border border-[#b3d7f5] rounded p-3 mb-4 text-sm text-[#0071e3]">
        <strong>加权成本计算规则</strong><br>
        加权成本 = (原有库存 x 原成本 + 新入库数量 x 新成本) / 总库存数量<br>
        例如：原有10件成本50元，新入库5件成本60元<br>
        新加权成本 = (10x50 + 5x60) / 15 = 53.33元
      </div>

      <h3 class="font-semibold mt-4 mb-2">库存调拨</h3>
      <div class="space-y-3 mb-4">
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">1</div><div class="text-sm"><strong>选择商品</strong><br><span class="text-[#6e6e73]">选择要调拨的商品</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">2</div><div class="text-sm"><strong>选择源仓位</strong><br><span class="text-[#6e6e73]">选择商品当前所在的仓库和仓位</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">3</div><div class="text-sm"><strong>选择目标仓位</strong><br><span class="text-[#6e6e73]">选择要调入的目标仓库和仓位</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">4</div><div class="text-sm"><strong>输入调拨数量</strong><br><span class="text-[#6e6e73]">输入要调拨的数量，不能超过源仓位可用库存</span></div></div>
      </div>

      <h3 class="font-semibold mt-4 mb-2">导入库存</h3>
      <div class="space-y-3 mb-4">
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">1</div><div class="text-sm"><strong>下载模板</strong><br><span class="text-[#6e6e73]">点击「导入」按钮，在弹窗中点击「下载模板」获取标准导入模板</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">2</div><div class="text-sm"><strong>填写数据</strong><br><span class="text-[#6e6e73]">按模板格式填写商品信息和库存数据</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">3</div><div class="text-sm"><strong>上传文件</strong><br><span class="text-[#6e6e73]">点击「选择文件」上传填写好的Excel文件</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">4</div><div class="text-sm"><strong>预览确认</strong><br><span class="text-[#6e6e73]">系统会显示导入预览，检查数据无误后点击「确认导入」</span></div></div>
      </div>

      <div class="bg-[#fff8e1] border border-[#ffe082] rounded p-3 mb-4 text-sm text-[#ff9f0a]">
        <strong>导入注意事项</strong><br>
        <ul class="list-disc list-inside mt-1 space-y-0.5">
          <li>SKU相同的商品会自动合并库存，并重新计算加权成本</li>
          <li>仓库和仓位会自动创建（如果不存在）</li>
          <li>请确保Excel格式正确，必填字段不能为空</li>
        </ul>
      </div>

      <h3 class="font-semibold mt-4 mb-2">导出库存</h3>
      <p class="text-sm text-[#6e6e73]">点击「导出」按钮可将当前库存导出为CSV文件，可用于盘点或数据备份。支持按仓库筛选后导出。</p>
    </div>

    <!-- Purchase -->
    <div v-if="guideSection === 'purchase'" class="guide-section">
      <h2 class="text-lg font-bold mb-4">采购管理</h2>

      <h3 class="font-semibold mt-4 mb-2">页面标签</h3>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-[#f5f5f7]">标签</th><th class="px-3 py-2 text-left bg-[#f5f5f7]">功能</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2">采购订单</td><td class="px-3 py-2">查看所有采购订单，支持按状态/日期/关键词筛选</td></tr>
            <tr><td class="px-3 py-2">供应商管理</td><td class="px-3 py-2">供应商档案维护（名称、联系人、电话、税号等）</td></tr>
            <tr><td class="px-3 py-2">采购收货</td><td class="px-3 py-2">已付款的采购订单收货入库</td></tr>
          </tbody>
        </table>
      </div>

      <h3 class="font-semibold mt-4 mb-2">新建采购订单</h3>
      <div class="space-y-3 mb-4">
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">1</div><div class="text-sm"><strong>选择供应商</strong><br><span class="text-[#6e6e73]">输入供应商名称模糊搜索，从下拉列表选择</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">2</div><div class="text-sm"><strong>添加商品</strong><br><span class="text-[#6e6e73]">输入SKU/名称/品牌模糊搜索商品，选择后自动填充价格。如商品未建档，点击"新建商品"快速创建</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">3</div><div class="text-sm"><strong>填写数量和价格</strong><br><span class="text-[#6e6e73]">输入含税单价和数量，系统自动计算不含税单价和金额</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">4</div><div class="text-sm"><strong>提交订单</strong><br><span class="text-[#6e6e73]">确认信息后提交，订单状态为"待付款"</span></div></div>
      </div>

      <h3 class="font-semibold mt-4 mb-2">采购状态流转</h3>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-[#f5f5f7]">状态</th><th class="px-3 py-2 text-left bg-[#f5f5f7]">说明</th><th class="px-3 py-2 text-left bg-[#f5f5f7]">操作</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2">待付款</td><td class="px-3 py-2">采购订单已创建</td><td class="px-3 py-2">财务在应付管理中"确认"付款，或"取消"采购单</td></tr>
            <tr><td class="px-3 py-2">在途</td><td class="px-3 py-2">已确认付款</td><td class="px-3 py-2">仓库在采购收货中收货入库</td></tr>
            <tr><td class="px-3 py-2">部分到货</td><td class="px-3 py-2">已收部分商品</td><td class="px-3 py-2">继续收货</td></tr>
            <tr><td class="px-3 py-2">已完成</td><td class="px-3 py-2">全部商品收货完成</td><td class="px-3 py-2">-</td></tr>
            <tr><td class="px-3 py-2">已取消</td><td class="px-3 py-2">采购单被取消</td><td class="px-3 py-2">-</td></tr>
          </tbody>
        </table>
      </div>

      <div class="bg-[#e8f4fd] border border-[#b3d7f5] rounded p-3 text-sm text-[#0071e3]">
        <strong>注意事项</strong><br>
        <ul class="list-disc list-inside mt-1 space-y-0.5">
          <li>供应商和商品选择均支持模糊搜索，输入关键字即可快速定位</li>
          <li>采购收货会自动更新库存数量和加权平均成本</li>
          <li>只有待付款状态的采购单才能取消</li>
          <li>付款确认和取消操作在财务页面的应付管理中进行</li>
        </ul>
      </div>
    </div>

    <!-- Consignment -->
    <div v-if="guideSection === 'consignment'" class="guide-section">
      <h2 class="text-lg font-bold mb-4">寄售管理</h2>

      <h3 class="font-semibold mt-4 mb-2">什么是寄售？</h3>
      <p class="text-sm text-[#6e6e73] mb-4">寄售是指将商品放置在客户处代为销售，商品所有权仍属于公司，客户售出后再进行结算的销售模式。</p>

      <h3 class="font-semibold mt-4 mb-2">寄售概览数据</h3>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-[#f5f5f7]">数据</th><th class="px-3 py-2 text-left bg-[#f5f5f7]">说明</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2">寄售成本总值</td><td class="px-3 py-2">所有寄售商品的成本价值合计</td></tr>
            <tr><td class="px-3 py-2">寄售零售总值</td><td class="px-3 py-2">所有寄售商品按零售价计算的价值</td></tr>
            <tr><td class="px-3 py-2">待结算金额</td><td class="px-3 py-2">客户已售出但尚未付款的金额</td></tr>
            <tr><td class="px-3 py-2">寄售总数量</td><td class="px-3 py-2">寄售商品的总件数</td></tr>
          </tbody>
        </table>
      </div>

      <h3 class="font-semibold mt-4 mb-2">寄售调拨（发货给客户）</h3>
      <div class="space-y-3 mb-4">
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">1</div><div class="text-sm"><strong>进入销售页面</strong><br><span class="text-[#6e6e73]">选择订单类型为「寄售调拨」</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">2</div><div class="text-sm"><strong>选择客户</strong><br><span class="text-[#6e6e73]">选择要寄售的客户</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">3</div><div class="text-sm"><strong>添加商品</strong><br><span class="text-[#6e6e73]">添加要寄售的商品，选择出库仓位</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">4</div><div class="text-sm"><strong>提交订单</strong><br><span class="text-[#6e6e73]">确认后商品从仓库转入该客户的寄售库存</span></div></div>
      </div>

      <h3 class="font-semibold mt-4 mb-2">寄售结算</h3>
      <div class="space-y-3 mb-4">
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">1</div><div class="text-sm"><strong>进入销售页面</strong><br><span class="text-[#6e6e73]">选择订单类型为「寄售结算」，或从寄售详情点击「去结算」</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">2</div><div class="text-sm"><strong>选择客户</strong><br><span class="text-[#6e6e73]">选择要结算的寄售客户</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">3</div><div class="text-sm"><strong>选择结算商品</strong><br><span class="text-[#6e6e73]">选择已售出需要结算的商品和数量</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">4</div><div class="text-sm"><strong>提交结算</strong><br><span class="text-[#6e6e73]">确认后减少客户寄售库存，生成应收账款</span></div></div>
      </div>

      <h3 class="font-semibold mt-4 mb-2">寄售退货</h3>
      <p class="text-sm text-[#6e6e73]">将客户处未售出的寄售商品退回仓库：在寄售详情页面点击「寄售退货」，选择退货商品和入库仓位即可。</p>
    </div>

    <!-- Logistics -->
    <div v-if="guideSection === 'logistics'" class="guide-section">
      <h2 class="text-lg font-bold mb-4">物流管理</h2>

      <h3 class="font-semibold mt-4 mb-2">功能概述</h3>
      <p class="text-sm text-[#6e6e73] mb-4">物流管理页面自动关联所有销售订单，可为每个订单添加一个或多个快递单号，支持快递100实时物流查询和状态自动更新。</p>

      <h3 class="font-semibold mt-4 mb-2">物流状态</h3>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-[#f5f5f7]">状态</th><th class="px-3 py-2 text-left bg-[#f5f5f7]">说明</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2">待发货</td><td class="px-3 py-2">订单已创建但尚未填写快递信息</td></tr>
            <tr><td class="px-3 py-2">已发货</td><td class="px-3 py-2">已填写快递单号，等待揽收</td></tr>
            <tr><td class="px-3 py-2">在途</td><td class="px-3 py-2">快递已揽收，正在运输中</td></tr>
            <tr><td class="px-3 py-2">已签收</td><td class="px-3 py-2">收件人已签收</td></tr>
            <tr><td class="px-3 py-2">异常</td><td class="px-3 py-2">退回、超时或其他异常情况</td></tr>
          </tbody>
        </table>
      </div>

      <h3 class="font-semibold mt-4 mb-2">添加物流信息</h3>
      <div class="space-y-3 mb-4">
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">1</div><div class="text-sm"><strong>进入物流详情</strong><br><span class="text-[#6e6e73]">在物流列表中点击某个订单，进入物流详情页</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">2</div><div class="text-sm"><strong>添加物流单</strong><br><span class="text-[#6e6e73]">点击「+ 添加物流单」按钮，选择快递公司并填写快递单号</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">3</div><div class="text-sm"><strong>填写手机号（部分快递）</strong><br><span class="text-[#6e6e73]">顺丰、顺丰快运、中通等需要填写收/寄件人手机号后四位才能查询物流</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">4</div><div class="text-sm"><strong>保存</strong><br><span class="text-[#6e6e73]">点击「添加」完成，系统会自动查询并更新物流状态</span></div></div>
      </div>

      <h3 class="font-semibold mt-4 mb-2">常用操作</h3>
      <ul class="text-sm text-[#6e6e73] space-y-2 mb-4 list-disc list-inside">
        <li><strong>一个订单多个包裹</strong> - 可为同一订单添加多个物流单号，适合分包发货的场景</li>
        <li><strong>复制单号</strong> - 点击「复制」按钮可一键复制快递单号，方便发给客户</li>
        <li><strong>复制全部单号</strong> - 在物流详情中可一次性复制该订单下所有快递单号</li>
        <li><strong>编辑/删除</strong> - 在物流详情中可修改快递公司、单号，或删除错误的物流单</li>
        <li><strong>刷新物流</strong> - 点击刷新按钮可手动查询最新的物流轨迹</li>
      </ul>

      <h3 class="font-semibold mt-4 mb-2">筛选与搜索</h3>
      <ul class="text-sm text-[#6e6e73] space-y-2 mb-4 list-disc list-inside">
        <li><strong>状态筛选</strong> - 点击页面顶部的状态标签（全部/待发货/已发货/在途/已签收/异常）快速过滤</li>
        <li><strong>搜索</strong> - 支持按订单号、快递单号、客户名称搜索</li>
      </ul>

      <div class="bg-[#e8f4fd] border border-[#b3d7f5] rounded p-3 text-sm text-[#0071e3]">
        <strong>物流自动更新</strong><br>
        <ul class="list-disc list-inside mt-1 space-y-0.5">
          <li>系统对接快递100接口，添加快递单号后会自动查询物流轨迹</li>
          <li>物流状态会根据快递100的推送自动更新（揽收 -> 在途 -> 签收）</li>
          <li>如遇物流信息未更新，可手动点击刷新按钮查询最新状态</li>
        </ul>
      </div>
    </div>

    <!-- Finance -->
    <div v-if="guideSection === 'finance'" class="guide-section">
      <h2 class="text-lg font-bold mb-4">财务管理</h2>

      <h3 class="font-semibold mt-4 mb-2">页面标签</h3>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-[#f5f5f7]">标签</th><th class="px-3 py-2 text-left bg-[#f5f5f7]">功能</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2">订单明细</td><td class="px-3 py-2">查看所有订单详细信息，支持筛选/搜索/导出，收款按钮在导出Excel前</td></tr>
            <tr><td class="px-3 py-2">欠款明细</td><td class="px-3 py-2">未结清的账期订单，桌面端表格视图，点击查看订单详情</td></tr>
            <tr><td class="px-3 py-2">应收管理</td><td class="px-3 py-2">收款记录流水，桌面端表格视图，显示关联订单号，点击查看详情</td></tr>
            <tr><td class="px-3 py-2">应付管理</td><td class="px-3 py-2">采购应付款管理，支持确认付款/取消采购单，点击查看采购详情</td></tr>
            <tr><td class="px-3 py-2">出入库日志</td><td class="px-3 py-2">所有库存变动记录，支持按类型筛选</td></tr>
            <tr><td class="px-3 py-2">返利管理</td><td class="px-3 py-2">客户/供应商返利余额管理，充值、查看明细、订单抵扣</td></tr>
          </tbody>
        </table>
      </div>

      <h3 class="font-semibold mt-4 mb-2">收款操作</h3>
      <div class="space-y-3 mb-4">
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">1</div><div class="text-sm"><strong>进入订单明细</strong><br><span class="text-[#6e6e73]">在订单明细Tab中点击"收款"按钮</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">2</div><div class="text-sm"><strong>选择客户和订单</strong><br><span class="text-[#6e6e73]">选择客户后勾选要收款的订单，可以选择多个</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">3</div><div class="text-sm"><strong>输入收款金额</strong><br><span class="text-[#6e6e73]">输入本次收款金额，可以少于订单总额（部分收款）</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">4</div><div class="text-sm"><strong>选择收款方式</strong><br><span class="text-[#6e6e73]">选择现金、银行转账、微信、支付宝等</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">5</div><div class="text-sm"><strong>确认收款</strong><br><span class="text-[#6e6e73]">点击确认完成收款，系统自动更新订单状态</span></div></div>
      </div>

      <h3 class="font-semibold mt-4 mb-2">应付管理操作</h3>
      <div class="space-y-3 mb-4">
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">1</div><div class="text-sm"><strong>查看待付款</strong><br><span class="text-[#6e6e73]">应付管理Tab显示所有待付款和已取消的采购单</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">2</div><div class="text-sm"><strong>确认付款</strong><br><span class="text-[#6e6e73]">点击"确认"按钮确认已付款，采购单进入在途状态</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">3</div><div class="text-sm"><strong>取消采购单</strong><br><span class="text-[#6e6e73]">如采购出现问题，点击"取消"按钮取消该采购单</span></div></div>
      </div>

      <h3 class="font-semibold mt-4 mb-2">返利管理</h3>
      <div class="space-y-3 mb-4">
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">1</div><div class="text-sm"><strong>充值返利</strong><br><span class="text-[#6e6e73]">进入返利管理Tab，切换客户/供应商，点击"新增充值"或行内"充值"按钮，输入金额和备注</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">2</div><div class="text-sm"><strong>销售使用返利</strong><br><span class="text-[#6e6e73]">创建销售订单确认时，勾选"使用返利"，逐行输入每个商品的返利金额，系统自动减少订单总额</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">3</div><div class="text-sm"><strong>采购使用返利</strong><br><span class="text-[#6e6e73]">创建采购订单时，勾选"使用返利"，逐行输入返利金额，收货入库成本自动按返利后金额计算</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-[#0071e3] text-white flex items-center justify-center text-sm font-bold flex-shrink-0">4</div><div class="text-sm"><strong>查看明细</strong><br><span class="text-[#6e6e73]">点击"明细"按钮查看充值和使用的完整流水记录</span></div></div>
      </div>

      <div class="bg-[#e8f4fd] border border-[#b3d7f5] rounded p-3 mb-4 text-sm text-[#0071e3]">
        <strong>返利规则</strong><br>
        <ul class="list-disc list-inside mt-1 space-y-0.5">
          <li>返利精确到每个商品行，用户手动输入每行返利金额</li>
          <li>返利总额不能超过可用余额，每行返利不能超过行金额</li>
          <li>销售返利：降低订单行金额，影响毛利计算</li>
          <li>采购返利：降低入库成本（有效单价 = 返利后行金额 / 数量）</li>
          <li>使用返利的订单备注中会自动记录返利详情</li>
        </ul>
      </div>

      <div class="bg-[#e8f4fd] border border-[#b3d7f5] rounded p-3 text-sm text-[#0071e3]">
        <strong>收款规则</strong><br>
        <ul class="list-disc list-inside mt-1 space-y-0.5">
          <li>收款金额会按照订单顺序自动分配</li>
          <li>当某订单已付金额等于订单金额时，订单自动标记为「已结清」</li>
          <li>收款记录会永久保存</li>
          <li>订单详情中会显示每笔收款的具体付款方式和确认状态</li>
        </ul>
      </div>
    </div>

    <!-- Customers -->
    <div v-if="guideSection === 'customers'" class="guide-section">
      <h2 class="text-lg font-bold mb-4">客户管理</h2>

      <h3 class="font-semibold mt-4 mb-2">客户列表</h3>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-[#f5f5f7]">列</th><th class="px-3 py-2 text-left bg-[#f5f5f7]">说明</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2">客户名称</td><td class="px-3 py-2">客户的公司或个人名称</td></tr>
            <tr><td class="px-3 py-2">联系人</td><td class="px-3 py-2">主要联系人姓名</td></tr>
            <tr><td class="px-3 py-2">电话</td><td class="px-3 py-2">联系电话</td></tr>
            <tr><td class="px-3 py-2">地址</td><td class="px-3 py-2">客户地址</td></tr>
            <tr><td class="px-3 py-2">账户状态</td><td class="px-3 py-2">显示应收金额或在账余额</td></tr>
          </tbody>
        </table>
      </div>

      <h3 class="font-semibold mt-4 mb-2">新增客户</h3>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-[#f5f5f7]">字段</th><th class="px-3 py-2 text-left bg-[#f5f5f7]">是否必填</th><th class="px-3 py-2 text-left bg-[#f5f5f7]">说明</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2">客户名称</td><td class="px-3 py-2">必填</td><td class="px-3 py-2">客户的公司或个人名称</td></tr>
            <tr><td class="px-3 py-2">联系人</td><td class="px-3 py-2">选填</td><td class="px-3 py-2">主要联系人</td></tr>
            <tr><td class="px-3 py-2">电话</td><td class="px-3 py-2">选填</td><td class="px-3 py-2">联系电话</td></tr>
            <tr><td class="px-3 py-2">地址</td><td class="px-3 py-2">选填</td><td class="px-3 py-2">详细地址</td></tr>
          </tbody>
        </table>
      </div>

      <h3 class="font-semibold mt-4 mb-2">客户交易明细</h3>
      <p class="text-sm text-[#6e6e73] mb-2">点击客户名称可查看该客户的交易详情：</p>
      <ul class="text-sm text-[#6e6e73] space-y-2 list-disc list-inside">
        <li><strong>交易统计</strong> - 显示各类型订单的数量和金额汇总</li>
        <li><strong>类型筛选</strong> - 可按订单类型筛选查看（点击统计卡片快速筛选）</li>
        <li><strong>月份筛选</strong> - 可按月份筛选查看交易记录</li>
        <li><strong>订单详情</strong> - 点击订单号查看详情，左上角返回按钮可返回</li>
      </ul>
    </div>

    <!-- Settings -->
    <div v-if="guideSection === 'settings'" class="guide-section">
      <h2 class="text-lg font-bold mb-4">系统设置</h2>

      <h3 class="font-semibold mt-4 mb-2">仓库管理</h3>
      <ul class="text-sm text-[#6e6e73] space-y-2 mb-4 list-disc list-inside">
        <li><strong>新增仓库</strong> - 输入仓库名称后点击「创建」</li>
        <li><strong>编辑仓库</strong> - 点击仓库名称可修改名称</li>
        <li><strong>设为默认</strong> - 设置默认仓库，入库时自动选中</li>
        <li><strong>删除仓库</strong> - 只能删除没有库存的仓库</li>
      </ul>

      <h3 class="font-semibold mt-4 mb-2">仓位管理</h3>
      <ul class="text-sm text-[#6e6e73] space-y-2 mb-4 list-disc list-inside">
        <li><strong>新增仓位</strong> - 输入仓位编码（如 A-01、B-02）后点击「创建」</li>
        <li><strong>编辑仓位</strong> - 点击仓位可修改编码和名称</li>
        <li><strong>删除仓位</strong> - 只能删除没有库存的仓位</li>
      </ul>

      <div class="bg-[#e8f4fd] border border-[#b3d7f5] rounded p-3 mb-4 text-sm text-[#0071e3]">
        <strong>仓位编码建议</strong><br>
        建议使用有规律的编码方式，如：A-01、A-02（A区1号、2号货架）或 1F-A、1F-B（1楼A区、B区）
      </div>

      <h3 class="font-semibold mt-4 mb-2">用户管理</h3>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-[#f5f5f7]">字段</th><th class="px-3 py-2 text-left bg-[#f5f5f7]">说明</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2">用户名</td><td class="px-3 py-2">登录账号，创建后不可修改</td></tr>
            <tr><td class="px-3 py-2">显示名称</td><td class="px-3 py-2">系统中显示的名称</td></tr>
            <tr><td class="px-3 py-2">密码</td><td class="px-3 py-2">登录密码，建议使用复杂密码</td></tr>
            <tr><td class="px-3 py-2">角色</td><td class="px-3 py-2">admin（管理员）或 user（普通用户）</td></tr>
            <tr><td class="px-3 py-2">权限</td><td class="px-3 py-2">勾选该用户可以访问的功能模块</td></tr>
          </tbody>
        </table>
      </div>

      <div class="bg-[#fff8e1] border border-[#ffe082] rounded p-3 text-sm text-[#ff9f0a]">
        <strong>安全建议</strong><br>
        <ul class="list-disc list-inside mt-1 space-y-0.5">
          <li>定期更换密码，避免使用简单密码</li>
          <li>为不同岗位的员工分配最小必要权限</li>
          <li>员工离职后及时禁用其账号</li>
        </ul>
      </div>
    </div>

    <!-- FAQ -->
    <div v-if="guideSection === 'faq'" class="guide-section">
      <h2 class="text-lg font-bold mb-4">常见问题</h2>

      <div class="space-y-4">
        <div class="card p-4">
          <h4 class="font-semibold text-sm mb-1">Q: 忘记密码怎么办？</h4>
          <p class="text-sm text-[#6e6e73]">A: 请联系系统管理员重置密码。管理员可以在「设置 -> 用户管理」中编辑用户并设置新密码。</p>
        </div>
        <div class="card p-4">
          <h4 class="font-semibold text-sm mb-1">Q: 库存数量显示负数怎么办？</h4>
          <p class="text-sm text-[#6e6e73]">A: 正常情况下不应该出现负库存。请检查是否有重复出库的订单，联系管理员通过入库操作修正库存。</p>
        </div>
        <div class="card p-4">
          <h4 class="font-semibold text-sm mb-1">Q: 订单提交后发现错误怎么办？</h4>
          <p class="text-sm text-[#6e6e73]">A: 订单提交后不能直接修改。如果是数量错误，可以创建退货单退回部分商品；如果是价格错误，需要联系管理员在数据库层面修正。</p>
        </div>
        <div class="card p-4">
          <h4 class="font-semibold text-sm mb-1">Q: 导入Excel失败怎么办？</h4>
          <p class="text-sm text-[#6e6e73]">A: 请检查：1) 使用系统提供的模板格式；2) 必填字段都有填写；3) 数字字段格式正确；4) 文件是 .xlsx 格式。</p>
        </div>
        <div class="card p-4">
          <h4 class="font-semibold text-sm mb-1">Q: 如何备份数据？</h4>
          <p class="text-sm text-[#6e6e73]">A: 系统数据存储在 data/erp.db 文件中。建议定期复制该文件到安全位置，或使用「导出」功能导出重要数据。</p>
        </div>
        <div class="card p-4">
          <h4 class="font-semibold text-sm mb-1">Q: 如何获取初始账号？</h4>
          <p class="text-sm text-[#6e6e73]">A: 请联系系统管理员获取初始账号和密码。首次登录后请尽快修改默认密码！</p>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <div class="mt-8 pt-4 border-t border-[#d2d2d7] text-center text-xs text-[#86868b]">
      <p>轻量级ERP系统 v4.8 使用手册 | 如有疑问，请联系系统管理员</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const guideSection = ref('overview')

const sections = [
  { key: 'overview', label: '系统概述' },
  { key: 'sales', label: '销售管理' },
  { key: 'stock', label: '库存管理' },
  { key: 'purchase', label: '采购管理' },
  { key: 'consignment', label: '寄售管理' },
  { key: 'logistics', label: '物流管理' },
  { key: 'finance', label: '财务管理' },
  { key: 'customers', label: '客户管理' },
  { key: 'settings', label: '系统设置' },
  { key: 'faq', label: '常见问题' },
]

const salesSteps = [
  { title: '选择订单类型', desc: '在页面顶部选择：现款、账期、寄售调拨、寄售结算、退货' },
  { title: '选择客户（如需要）', desc: '账期、寄售类型订单必须选择客户' },
  { title: '添加商品到购物车', desc: '在商品列表中搜索商品，点击添加到右侧购物车，可修改数量和单价' },
  { title: '选择出库仓位', desc: '为每个商品选择出库的仓库和仓位，系统会显示该仓位的可用库存' },
  { title: '提交订单', desc: '点击「提交订单」按钮，确认订单信息后完成创建' },
]

const returnSteps = [
  { title: '选择退货类型', desc: '在订单类型中选择「退货」' },
  { title: '选择原始订单', desc: '在下拉框中搜索并选择要退货的原始销售订单' },
  { title: '选择退货商品', desc: '系统会自动加载原订单商品，选择需要退货的商品和数量' },
  { title: '选择退货入库仓位', desc: '选择退货商品要入库的仓库和仓位' },
  { title: '确认是否已退款', desc: '勾选「已退款给客户」表示已将款项退还；不勾选则款项转为客户在账资金' },
]
</script>

<template>
  <div class="guide-page">
    <div class="guide-header">
      <h1 class="text-2xl font-bold mb-1">轻量级ERP系统 v4.15 使用手册</h1>
      <p class="text-muted text-sm">完整功能指南 · 业财一体化</p>
    </div>

    <!-- Table of Contents -->
    <div class="card p-4 mb-5">
      <h2 class="font-semibold mb-3 text-sm">目录</h2>
      <div class="grid grid-cols-2 md:grid-cols-6 gap-2">
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
      <p class="text-sm text-secondary mb-4">本系统是一套轻量级的企业资源管理系统（ERP），专为中小型贸易/批发企业设计，覆盖销售、采购、库存、财务、会计、物流、寄售等核心业务流程，内置完整的业财一体化财务会计模块。</p>

      <h3 class="font-semibold mt-4 mb-2">核心功能模块</h3>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-elevated">模块</th><th class="px-3 py-2 text-left bg-elevated">功能说明</th><th class="px-3 py-2 text-left bg-elevated">适用人员</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2"><span class="badge badge-blue">首页</span></td><td class="px-3 py-2">销售概况、库存预警、畅销商品、经营概览</td><td class="px-3 py-2">所有人员</td></tr>
            <tr><td class="px-3 py-2"><span class="badge badge-green">销售</span></td><td class="px-3 py-2">现款/账期/寄售/退货订单、购物车开单</td><td class="px-3 py-2">销售人员</td></tr>
            <tr><td class="px-3 py-2"><span class="badge badge-purple">库存</span></td><td class="px-3 py-2">多仓库多仓位管理、入库/调拨/盘点、SN码管理、Excel导入导出</td><td class="px-3 py-2">仓管人员</td></tr>
            <tr><td class="px-3 py-2"><span class="badge badge-orange">采购</span></td><td class="px-3 py-2">采购订单全流程（下单→审核→付款→收货→退货）、供应商管理</td><td class="px-3 py-2">采购人员</td></tr>
            <tr><td class="px-3 py-2"><span class="badge badge-yellow">寄售</span></td><td class="px-3 py-2">寄售调拨、寄售结算、寄售退货</td><td class="px-3 py-2">销售/财务</td></tr>
            <tr><td class="px-3 py-2"><span class="badge badge-blue">物流</span></td><td class="px-3 py-2">多批次发货、快递100实时追踪、SN码绑定</td><td class="px-3 py-2">物流/销售</td></tr>
            <tr><td class="px-3 py-2"><span class="badge badge-red">财务</span></td><td class="px-3 py-2">收款管理、欠款明细、返利管理（客户/供应商双向）</td><td class="px-3 py-2">财务人员</td></tr>
            <tr><td class="px-3 py-2"><span class="badge badge-green">会计</span></td><td class="px-3 py-2">多账套、凭证管理、账簿查询、应收应付、发票、出入库单、期末处理、财务报表</td><td class="px-3 py-2">会计人员</td></tr>
            <tr><td class="px-3 py-2"><span class="badge badge-blue">客户</span></td><td class="px-3 py-2">客户档案、交易明细、余额/返利/欠款管理</td><td class="px-3 py-2">销售/财务</td></tr>
            <tr><td class="px-3 py-2"><span class="badge badge-purple">设置</span></td><td class="px-3 py-2">用户管理、权限配置、仓库仓位、收付款方式、备份管理</td><td class="px-3 py-2">管理员</td></tr>
          </tbody>
        </table>
      </div>

      <h3 class="font-semibold mt-4 mb-2">订单类型说明</h3>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-elevated">类型</th><th class="px-3 py-2 text-left bg-elevated">说明</th><th class="px-3 py-2 text-left bg-elevated">库存影响</th><th class="px-3 py-2 text-left bg-elevated">账款影响</th></tr></thead>
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
      <p class="text-sm text-secondary mb-2">系统角色分为 <strong>管理员</strong>（拥有全部权限）和 <strong>普通用户</strong>（按需分配），共 28 个细粒度权限，分 10 个权限组。管理员可在「设置 → 权限管理」中为每个用户独立配置。</p>
      <div class="overflow-x-auto">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-elevated">权限组</th><th class="px-3 py-2 text-left bg-elevated">可访问的功能</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2">首页</td><td class="px-3 py-2">查看仪表盘数据统计</td></tr>
            <tr><td class="px-3 py-2">销售管理</td><td class="px-3 py-2">创建销售订单、寄售管理</td></tr>
            <tr><td class="px-3 py-2">库存管理</td><td class="px-3 py-2">查看库存 + 库存操作（入库/调拨/盘点/商品管理）</td></tr>
            <tr><td class="px-3 py-2">采购管理</td><td class="px-3 py-2">采购下单 + 审核 + 付款 + 收货（四个子权限独立控制）</td></tr>
            <tr><td class="px-3 py-2">寄售管理</td><td class="px-3 py-2">寄售调拨、结算、退货</td></tr>
            <tr><td class="px-3 py-2">物流管理</td><td class="px-3 py-2">发货、物流追踪</td></tr>
            <tr><td class="px-3 py-2">财务管理</td><td class="px-3 py-2">收款管理 + 确认收款（子权限独立控制）</td></tr>
            <tr><td class="px-3 py-2">会计管理</td><td class="px-3 py-2">查看 + 录入 + 审核 + 过账 + 期末处理 + 应收（查看/编辑/确认）+ 应付（查看/编辑/确认）共 11 个子权限</td></tr>
            <tr><td class="px-3 py-2">客户管理</td><td class="px-3 py-2">客户档案维护、交易明细查询</td></tr>
            <tr><td class="px-3 py-2">系统设置</td><td class="px-3 py-2">系统配置 + 操作日志 + 系统管理（用户/备份/账套）</td></tr>
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
          <div class="w-7 h-7 rounded-full bg-primary text-white flex items-center justify-center text-sm font-bold flex-shrink-0">{{ i + 1 }}</div>
          <div class="text-sm"><strong>{{ step.title }}</strong><br><span class="text-secondary">{{ step.desc }}</span></div>
        </div>
      </div>

      <div class="bg-info-subtle border border-primary rounded p-3 mb-4 text-sm text-primary">
        <strong>使用在账资金</strong><br>
        如果客户有在账资金（如之前退货产生的余额），在确认订单时可以勾选「使用在账资金抵扣」，系统会自动抵扣。
      </div>

      <h3 class="font-semibold mt-4 mb-2">处理退货</h3>
      <div class="space-y-3 mb-4">
        <div v-for="(step, i) in returnSteps" :key="i" class="flex gap-3 items-start">
          <div class="w-7 h-7 rounded-full bg-primary text-white flex items-center justify-center text-sm font-bold flex-shrink-0">{{ i + 1 }}</div>
          <div class="text-sm"><strong>{{ step.title }}</strong><br><span class="text-secondary">{{ step.desc }}</span></div>
        </div>
      </div>

      <div class="bg-warning-subtle border border-warning rounded p-3 mb-4 text-sm text-warning">
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
          <thead><tr><th class="px-3 py-2 text-left bg-elevated">操作</th><th class="px-3 py-2 text-left bg-elevated">说明</th></tr></thead>
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
          <thead><tr><th class="px-3 py-2 text-left bg-elevated">列</th><th class="px-3 py-2 text-left bg-elevated">说明</th></tr></thead>
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
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-primary text-white flex items-center justify-center text-sm font-bold flex-shrink-0">1</div><div class="text-sm"><strong>选择仓库和仓位</strong><br><span class="text-secondary">选择商品要入库的目标仓库和仓位</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-primary text-white flex items-center justify-center text-sm font-bold flex-shrink-0">2</div><div class="text-sm"><strong>选择商品</strong><br><span class="text-secondary">在搜索框中输入SKU或名称，选择要入库的商品</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-primary text-white flex items-center justify-center text-sm font-bold flex-shrink-0">3</div><div class="text-sm"><strong>输入数量和成本</strong><br><span class="text-secondary">输入入库数量和本批次的采购成本单价</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-primary text-white flex items-center justify-center text-sm font-bold flex-shrink-0">4</div><div class="text-sm"><strong>确认入库</strong><br><span class="text-secondary">点击确认完成入库，系统自动计算新的加权成本和库龄</span></div></div>
      </div>

      <div class="bg-info-subtle border border-primary rounded p-3 mb-4 text-sm text-primary">
        <strong>加权成本计算规则</strong><br>
        加权成本 = (原有库存 x 原成本 + 新入库数量 x 新成本) / 总库存数量<br>
        例如：原有10件成本50元，新入库5件成本60元<br>
        新加权成本 = (10x50 + 5x60) / 15 = 53.33元
      </div>

      <h3 class="font-semibold mt-4 mb-2">库存调拨</h3>
      <div class="space-y-3 mb-4">
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-primary text-white flex items-center justify-center text-sm font-bold flex-shrink-0">1</div><div class="text-sm"><strong>选择商品</strong><br><span class="text-secondary">选择要调拨的商品</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-primary text-white flex items-center justify-center text-sm font-bold flex-shrink-0">2</div><div class="text-sm"><strong>选择源仓位</strong><br><span class="text-secondary">选择商品当前所在的仓库和仓位</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-primary text-white flex items-center justify-center text-sm font-bold flex-shrink-0">3</div><div class="text-sm"><strong>选择目标仓位</strong><br><span class="text-secondary">选择要调入的目标仓库和仓位</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-primary text-white flex items-center justify-center text-sm font-bold flex-shrink-0">4</div><div class="text-sm"><strong>输入调拨数量</strong><br><span class="text-secondary">输入要调拨的数量，不能超过源仓位可用库存</span></div></div>
      </div>

      <h3 class="font-semibold mt-4 mb-2">导入/导出</h3>
      <ul class="text-sm text-secondary space-y-2 mb-4 list-disc list-inside">
        <li><strong>导入商品</strong> — 点击「导入」→ 下载模板 → 填写数据 → 上传预览 → 确认导入。SKU 相同自动合并，仓库仓位自动创建</li>
        <li><strong>导出库存</strong> — 点击「导出」将当前库存导出为 CSV 文件，支持按仓库筛选</li>
      </ul>
    </div>

    <!-- Purchase -->
    <div v-if="guideSection === 'purchase'" class="guide-section">
      <h2 class="text-lg font-bold mb-4">采购管理</h2>

      <h3 class="font-semibold mt-4 mb-2">页面标签</h3>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-elevated">标签</th><th class="px-3 py-2 text-left bg-elevated">功能</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2">采购订单</td><td class="px-3 py-2">查看所有采购订单，支持按状态/日期/关键词筛选</td></tr>
            <tr><td class="px-3 py-2">供应商管理</td><td class="px-3 py-2">供应商档案维护（名称、联系人、电话、税号等）</td></tr>
            <tr><td class="px-3 py-2">采购收货</td><td class="px-3 py-2">已付款的采购订单收货入库</td></tr>
          </tbody>
        </table>
      </div>

      <h3 class="font-semibold mt-4 mb-2">采购状态流转</h3>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-elevated">状态</th><th class="px-3 py-2 text-left bg-elevated">说明</th><th class="px-3 py-2 text-left bg-elevated">操作</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2">待审核</td><td class="px-3 py-2">采购订单已创建</td><td class="px-3 py-2">有审核权限的人员审核通过或拒绝</td></tr>
            <tr><td class="px-3 py-2">待付款</td><td class="px-3 py-2">审核通过</td><td class="px-3 py-2">财务确认付款或取消</td></tr>
            <tr><td class="px-3 py-2">在途</td><td class="px-3 py-2">已确认付款</td><td class="px-3 py-2">仓库在采购收货中收货入库</td></tr>
            <tr><td class="px-3 py-2">部分到货</td><td class="px-3 py-2">已收部分商品</td><td class="px-3 py-2">继续收货</td></tr>
            <tr><td class="px-3 py-2">已完成</td><td class="px-3 py-2">全部商品收货完成</td><td class="px-3 py-2">—</td></tr>
          </tbody>
        </table>
      </div>

      <div class="bg-info-subtle border border-primary rounded p-3 text-sm text-primary">
        <strong>业财联动</strong><br>
        <ul class="list-disc list-inside mt-1 space-y-0.5">
          <li>采购付款自动生成应付单和付款单（会计模块）</li>
          <li>采购收货自动生成入库单和入库凭证（借：库存商品/进项税额，贷：应付账款）</li>
          <li>收货入库自动更新库存数量和加权平均成本</li>
          <li>使用供应商返利抵扣时，成本价按实际付款金额计算</li>
        </ul>
      </div>
    </div>

    <!-- Consignment -->
    <div v-if="guideSection === 'consignment'" class="guide-section">
      <h2 class="text-lg font-bold mb-4">寄售管理</h2>

      <h3 class="font-semibold mt-4 mb-2">什么是寄售？</h3>
      <p class="text-sm text-secondary mb-4">寄售是指将商品放置在客户处代为销售，商品所有权仍属于公司，客户售出后再进行结算的销售模式。</p>

      <h3 class="font-semibold mt-4 mb-2">寄售概览数据</h3>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-elevated">数据</th><th class="px-3 py-2 text-left bg-elevated">说明</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2">寄售成本总值</td><td class="px-3 py-2">所有寄售商品的成本价值合计</td></tr>
            <tr><td class="px-3 py-2">寄售零售总值</td><td class="px-3 py-2">所有寄售商品按零售价计算的价值</td></tr>
            <tr><td class="px-3 py-2">待结算金额</td><td class="px-3 py-2">客户已售出但尚未付款的金额</td></tr>
            <tr><td class="px-3 py-2">寄售总数量</td><td class="px-3 py-2">寄售商品的总件数</td></tr>
          </tbody>
        </table>
      </div>

      <h3 class="font-semibold mt-4 mb-2">寄售业务流程</h3>
      <ul class="text-sm text-secondary space-y-2 mb-4 list-disc list-inside">
        <li><strong>寄售调拨</strong> — 在销售页面选择「寄售调拨」类型，选择客户和商品，提交后库存从仓库转入客户的寄售仓</li>
        <li><strong>寄售结算</strong> — 在销售页面选择「寄售结算」，或从寄售详情点击「去结算」，选择已售出的商品和数量</li>
        <li><strong>寄售退货</strong> — 在寄售详情页面点击「寄售退货」，选择退货商品和入库仓位</li>
      </ul>
    </div>

    <!-- Logistics -->
    <div v-if="guideSection === 'logistics'" class="guide-section">
      <h2 class="text-lg font-bold mb-4">物流管理</h2>

      <h3 class="font-semibold mt-4 mb-2">功能概述</h3>
      <p class="text-sm text-secondary mb-4">物流管理页面自动关联所有销售订单，可为每个订单添加一个或多个快递单号，支持快递100实时物流查询和状态自动更新。</p>

      <h3 class="font-semibold mt-4 mb-2">物流状态</h3>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-elevated">状态</th><th class="px-3 py-2 text-left bg-elevated">说明</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2">待发货</td><td class="px-3 py-2">订单已创建但尚未填写快递信息</td></tr>
            <tr><td class="px-3 py-2">已发货</td><td class="px-3 py-2">已填写快递单号，等待揽收</td></tr>
            <tr><td class="px-3 py-2">在途</td><td class="px-3 py-2">快递已揽收，正在运输中</td></tr>
            <tr><td class="px-3 py-2">已签收</td><td class="px-3 py-2">收件人已签收</td></tr>
            <tr><td class="px-3 py-2">异常</td><td class="px-3 py-2">退回、超时或其他异常情况</td></tr>
          </tbody>
        </table>
      </div>

      <h3 class="font-semibold mt-4 mb-2">常用操作</h3>
      <ul class="text-sm text-secondary space-y-2 mb-4 list-disc list-inside">
        <li><strong>添加物流单</strong> — 进入物流详情 → 点击「+ 添加物流单」→ 选择快递公司 → 填写快递单号和手机号（顺丰等需要）→ 保存</li>
        <li><strong>一个订单多个包裹</strong> — 可为同一订单添加多个物流单号，适合分包发货</li>
        <li><strong>复制单号</strong> — 点击复制按钮可一键复制快递单号</li>
        <li><strong>刷新物流</strong> — 手动查询最新的物流轨迹</li>
        <li><strong>筛选搜索</strong> — 按状态标签过滤，或按订单号/快递单号/客户名称搜索</li>
      </ul>

      <div class="bg-info-subtle border border-primary rounded p-3 text-sm text-primary">
        <strong>物流自动更新</strong><br>
        系统对接快递100接口，添加快递单号后自动查询物流轨迹，状态根据快递100推送自动更新。
      </div>
    </div>

    <!-- Finance -->
    <div v-if="guideSection === 'finance'" class="guide-section">
      <h2 class="text-lg font-bold mb-4">财务管理</h2>

      <h3 class="font-semibold mt-4 mb-2">页面标签</h3>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-elevated">标签</th><th class="px-3 py-2 text-left bg-elevated">功能</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2">订单明细</td><td class="px-3 py-2">查看所有订单信息，支持筛选/搜索/导出/收款</td></tr>
            <tr><td class="px-3 py-2">欠款明细</td><td class="px-3 py-2">未结清的账期订单列表</td></tr>
            <tr><td class="px-3 py-2">应收管理</td><td class="px-3 py-2">收款记录流水，关联订单号</td></tr>
            <tr><td class="px-3 py-2">应付管理</td><td class="px-3 py-2">采购应付款，确认付款/取消采购单</td></tr>
            <tr><td class="px-3 py-2">出入库日志</td><td class="px-3 py-2">所有库存变动记录</td></tr>
            <tr><td class="px-3 py-2">返利管理</td><td class="px-3 py-2">客户/供应商返利余额管理</td></tr>
          </tbody>
        </table>
      </div>

      <h3 class="font-semibold mt-4 mb-2">收款操作</h3>
      <div class="space-y-3 mb-4">
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-primary text-white flex items-center justify-center text-sm font-bold flex-shrink-0">1</div><div class="text-sm"><strong>进入订单明细</strong><br><span class="text-secondary">点击「收款」按钮</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-primary text-white flex items-center justify-center text-sm font-bold flex-shrink-0">2</div><div class="text-sm"><strong>选择客户和订单</strong><br><span class="text-secondary">选择客户后勾选要收款的订单，可多选</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-primary text-white flex items-center justify-center text-sm font-bold flex-shrink-0">3</div><div class="text-sm"><strong>输入金额和方式</strong><br><span class="text-secondary">输入收款金额（可部分收款），选择收款方式</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-primary text-white flex items-center justify-center text-sm font-bold flex-shrink-0">4</div><div class="text-sm"><strong>确认收款</strong><br><span class="text-secondary">确认后系统自动更新订单状态，同时生成会计模块的应收单和收款单</span></div></div>
      </div>

      <h3 class="font-semibold mt-4 mb-2">返利管理</h3>
      <div class="bg-info-subtle border border-primary rounded p-3 text-sm text-primary">
        <strong>返利规则</strong><br>
        <ul class="list-disc list-inside mt-1 space-y-0.5">
          <li>返利精确到每个商品行，用户手动输入每行返利金额</li>
          <li>返利总额不能超过可用余额，每行返利不能超过行金额</li>
          <li>销售返利：降低订单行金额，影响毛利计算</li>
          <li>采购返利：降低入库成本（有效单价 = 返利后行金额 / 数量）</li>
        </ul>
      </div>
    </div>

    <!-- Accounting -->
    <div v-if="guideSection === 'accounting'" class="guide-section">
      <h2 class="text-lg font-bold mb-4">会计管理</h2>

      <p class="text-sm text-secondary mb-4">会计模块是系统的业财一体化核心，包含 10 个功能标签页，覆盖从日常记账到期末报表的完整会计循环。</p>

      <h3 class="font-semibold mt-4 mb-2">功能标签页</h3>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-elevated">标签</th><th class="px-3 py-2 text-left bg-elevated">功能说明</th><th class="px-3 py-2 text-left bg-elevated">所需权限</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2">凭证管理</td><td class="px-3 py-2">创建/编辑/审核/过账记账凭证，支持 PDF 套打</td><td class="px-3 py-2">查看/录入/审核/过账</td></tr>
            <tr><td class="px-3 py-2">科目管理</td><td class="px-3 py-2">查看和维护会计科目表（预置 32 个标准科目，支持 4 级）</td><td class="px-3 py-2">查看/录入</td></tr>
            <tr><td class="px-3 py-2">会计期间</td><td class="px-3 py-2">管理月度会计期间，支持按年批量初始化</td><td class="px-3 py-2">期末处理</td></tr>
            <tr><td class="px-3 py-2">账簿查询</td><td class="px-3 py-2">总分类账、明细分类账、科目余额表，支持 Excel 导出</td><td class="px-3 py-2">查看</td></tr>
            <tr><td class="px-3 py-2">应收管理</td><td class="px-3 py-2">应收单、收款单、收款退款单、应收核销，批量生成凭证</td><td class="px-3 py-2">应收查看/编辑/确认</td></tr>
            <tr><td class="px-3 py-2">应付管理</td><td class="px-3 py-2">应付单、付款单、付款退款单，批量生成凭证</td><td class="px-3 py-2">应付查看/编辑/确认</td></tr>
            <tr><td class="px-3 py-2">发票管理</td><td class="px-3 py-2">销项发票（从应收单推送）、进项发票，确认后自动生成凭证</td><td class="px-3 py-2">查看/录入/审核</td></tr>
            <tr><td class="px-3 py-2">出入库单</td><td class="px-3 py-2">销售出库单和采购入库单（业务自动生成），支持 PDF 套打</td><td class="px-3 py-2">查看</td></tr>
            <tr><td class="px-3 py-2">期末处理</td><td class="px-3 py-2">损益结转、结账检查、期末结账/反结账、年度结转</td><td class="px-3 py-2">期末处理</td></tr>
            <tr><td class="px-3 py-2">财务报表</td><td class="px-3 py-2">资产负债表、利润表、现金流量表，支持 Excel/PDF 导出</td><td class="px-3 py-2">查看</td></tr>
          </tbody>
        </table>
      </div>

      <h3 class="font-semibold mt-4 mb-2">凭证状态流转</h3>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-elevated">状态</th><th class="px-3 py-2 text-left bg-elevated">说明</th><th class="px-3 py-2 text-left bg-elevated">操作</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2">草稿</td><td class="px-3 py-2">凭证创建或退回后</td><td class="px-3 py-2">编辑、删除、提交</td></tr>
            <tr><td class="px-3 py-2">已提交</td><td class="px-3 py-2">等待审核</td><td class="px-3 py-2">审核通过、退回</td></tr>
            <tr><td class="px-3 py-2">已审核</td><td class="px-3 py-2">审核通过待过账</td><td class="px-3 py-2">过账</td></tr>
            <tr><td class="px-3 py-2">已过账</td><td class="px-3 py-2">正式入账</td><td class="px-3 py-2">反过账（需权限）</td></tr>
          </tbody>
        </table>
      </div>

      <h3 class="font-semibold mt-4 mb-2">科目体系</h3>
      <p class="text-sm text-secondary mb-2">系统预置 32 个标准会计科目，支持最多 4 级科目体系：</p>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-elevated">科目类别</th><th class="px-3 py-2 text-left bg-elevated">主要科目</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2">资产类</td><td class="px-3 py-2">银行存款(1002)、应收账款(1122)、库存商品(1405)、发出商品(1407)</td></tr>
            <tr><td class="px-3 py-2">负债类</td><td class="px-3 py-2">应付账款(2202)、预收账款(2203)、应交税费(2221)</td></tr>
            <tr><td class="px-3 py-2">权益类</td><td class="px-3 py-2">实收资本(4001)、本年利润(4103)、利润分配(4104)</td></tr>
            <tr><td class="px-3 py-2">损益类</td><td class="px-3 py-2">主营业务收入(6001)、主营业务成本(6401)、管理费用(6602)</td></tr>
          </tbody>
        </table>
      </div>

      <h3 class="font-semibold mt-4 mb-2">业财联动说明</h3>
      <div class="bg-info-subtle border border-primary rounded p-3 mb-4 text-sm text-primary">
        <strong>自动生成的单据和凭证</strong><br>
        <ul class="list-disc list-inside mt-1 space-y-0.5">
          <li><strong>销售发货</strong> → 自动生成销售出库单 + 出库凭证（借：发出商品，贷：库存商品）</li>
          <li><strong>采购收货</strong> → 自动生成入库单 + 入库凭证（借：库存商品/进项税额，贷：应付账款）</li>
          <li><strong>收款确认</strong> → 自动生成应收单和收款单</li>
          <li><strong>采购付款</strong> → 自动生成应付单和付款单</li>
          <li><strong>发票确认</strong> → 自动生成发票凭证（含收入/税额/成本分录）</li>
          <li><strong>期末批量生成</strong> → 一键为当期已确认的收款单/付款单生成记账凭证</li>
        </ul>
      </div>

      <h3 class="font-semibold mt-4 mb-2">期末处理流程</h3>
      <div class="space-y-3 mb-4">
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-primary text-white flex items-center justify-center text-sm font-bold flex-shrink-0">1</div><div class="text-sm"><strong>检查凭证</strong><br><span class="text-secondary">确保当期所有凭证已过账，所有收付款单据已确认</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-primary text-white flex items-center justify-center text-sm font-bold flex-shrink-0">2</div><div class="text-sm"><strong>批量生成凭证</strong><br><span class="text-secondary">在应收/应付标签页点击「批量生成凭证」，为已确认的单据自动生成记账凭证</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-primary text-white flex items-center justify-center text-sm font-bold flex-shrink-0">3</div><div class="text-sm"><strong>损益结转</strong><br><span class="text-secondary">点击「预览结转」查看本期损益，确认无误后执行结转（自动生成转字凭证）</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-primary text-white flex items-center justify-center text-sm font-bold flex-shrink-0">4</div><div class="text-sm"><strong>结账检查</strong><br><span class="text-secondary">系统自动检查 5 项：未过账凭证、未确认单据、借贷平衡等</span></div></div>
        <div class="flex gap-3 items-start"><div class="w-7 h-7 rounded-full bg-primary text-white flex items-center justify-center text-sm font-bold flex-shrink-0">5</div><div class="text-sm"><strong>期末结账</strong><br><span class="text-secondary">所有检查通过后执行结账，锁定当期数据</span></div></div>
      </div>

      <h3 class="font-semibold mt-4 mb-2">财务报表</h3>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-elevated">报表</th><th class="px-3 py-2 text-left bg-elevated">说明</th><th class="px-3 py-2 text-left bg-elevated">导出格式</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2">资产负债表</td><td class="px-3 py-2">反映企业某一时点的资产、负债和所有者权益</td><td class="px-3 py-2">Excel / PDF</td></tr>
            <tr><td class="px-3 py-2">利润表</td><td class="px-3 py-2">反映企业一定期间的收入、成本和利润（本期 + 本年累计）</td><td class="px-3 py-2">Excel / PDF</td></tr>
            <tr><td class="px-3 py-2">现金流量表</td><td class="px-3 py-2">反映企业现金流入和流出（简易直接法）</td><td class="px-3 py-2">Excel / PDF</td></tr>
          </tbody>
        </table>
      </div>

      <div class="bg-warning-subtle border border-warning rounded p-3 text-sm text-warning">
        <strong>注意事项</strong><br>
        <ul class="list-disc list-inside mt-1 space-y-0.5">
          <li>首次使用需要在「设置 → 账套管理」中创建账套，系统会自动初始化 32 个标准科目</li>
          <li>凭证的借贷金额必须平衡才能保存</li>
          <li>已过账的凭证需要先反过账才能修改</li>
          <li>结账后如需修改，需先反结账</li>
          <li>年末 12 月结账时建议先执行年度结转（本年利润 → 利润分配）</li>
        </ul>
      </div>
    </div>

    <!-- Customers -->
    <div v-if="guideSection === 'customers'" class="guide-section">
      <h2 class="text-lg font-bold mb-4">客户管理</h2>

      <h3 class="font-semibold mt-4 mb-2">客户列表</h3>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-elevated">列</th><th class="px-3 py-2 text-left bg-elevated">说明</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2">客户名称</td><td class="px-3 py-2">客户的公司或个人名称</td></tr>
            <tr><td class="px-3 py-2">联系人</td><td class="px-3 py-2">主要联系人姓名</td></tr>
            <tr><td class="px-3 py-2">电话</td><td class="px-3 py-2">联系电话</td></tr>
            <tr><td class="px-3 py-2">地址</td><td class="px-3 py-2">客户地址</td></tr>
            <tr><td class="px-3 py-2">账户状态</td><td class="px-3 py-2">显示应收金额或在账余额</td></tr>
          </tbody>
        </table>
      </div>

      <h3 class="font-semibold mt-4 mb-2">客户交易明细</h3>
      <p class="text-sm text-secondary mb-2">点击客户名称可查看该客户的交易详情：</p>
      <ul class="text-sm text-secondary space-y-2 list-disc list-inside">
        <li><strong>交易统计</strong> — 各类型订单的数量和金额汇总</li>
        <li><strong>类型筛选</strong> — 按订单类型筛选（点击统计卡片快速筛选）</li>
        <li><strong>月份筛选</strong> — 按月份查看交易记录</li>
        <li><strong>订单详情</strong> — 点击订单号查看完整详情</li>
      </ul>
    </div>

    <!-- Settings -->
    <div v-if="guideSection === 'settings'" class="guide-section">
      <h2 class="text-lg font-bold mb-4">系统设置</h2>

      <h3 class="font-semibold mt-4 mb-2">设置标签页</h3>
      <div class="overflow-x-auto mb-4">
        <table class="guide-table w-full text-sm">
          <thead><tr><th class="px-3 py-2 text-left bg-elevated">标签</th><th class="px-3 py-2 text-left bg-elevated">功能</th><th class="px-3 py-2 text-left bg-elevated">权限要求</th></tr></thead>
          <tbody class="divide-y">
            <tr><td class="px-3 py-2">仓库管理</td><td class="px-3 py-2">新增/编辑/删除仓库，设置默认仓库和关联账套</td><td class="px-3 py-2">系统设置</td></tr>
            <tr><td class="px-3 py-2">仓位管理</td><td class="px-3 py-2">按仓库管理仓位编码（如 A-01、B-02）</td><td class="px-3 py-2">系统设置</td></tr>
            <tr><td class="px-3 py-2">收款方式</td><td class="px-3 py-2">管理销售收款方式（现金、银行转账、微信等）</td><td class="px-3 py-2">系统设置</td></tr>
            <tr><td class="px-3 py-2">付款方式</td><td class="px-3 py-2">管理采购付款方式</td><td class="px-3 py-2">系统设置</td></tr>
            <tr><td class="px-3 py-2">销售员</td><td class="px-3 py-2">管理销售员列表</td><td class="px-3 py-2">系统设置</td></tr>
            <tr><td class="px-3 py-2">用户管理</td><td class="px-3 py-2">创建用户、修改密码、启用/禁用账号</td><td class="px-3 py-2">管理员</td></tr>
            <tr><td class="px-3 py-2">权限管理</td><td class="px-3 py-2">为每个用户配置细粒度权限（iOS 风格开关矩阵）</td><td class="px-3 py-2">管理员</td></tr>
            <tr><td class="px-3 py-2">操作日志</td><td class="px-3 py-2">查看系统操作审计日志</td><td class="px-3 py-2">日志权限</td></tr>
            <tr><td class="px-3 py-2">SN 码配置</td><td class="px-3 py-2">按仓库+品牌启用 SN 码管理</td><td class="px-3 py-2">系统设置</td></tr>
            <tr><td class="px-3 py-2">备份管理</td><td class="px-3 py-2">手动/自动备份、恢复、下载、删除</td><td class="px-3 py-2">管理员</td></tr>
          </tbody>
        </table>
      </div>

      <div class="bg-warning-subtle border border-warning rounded p-3 text-sm text-warning">
        <strong>安全建议</strong><br>
        <ul class="list-disc list-inside mt-1 space-y-0.5">
          <li>定期更换密码，避免使用简单密码</li>
          <li>为不同岗位的员工分配最小必要权限</li>
          <li>员工离职后及时禁用其账号</li>
          <li>定期检查备份是否正常执行</li>
        </ul>
      </div>
    </div>

    <!-- FAQ -->
    <div v-if="guideSection === 'faq'" class="guide-section">
      <h2 class="text-lg font-bold mb-4">常见问题</h2>

      <div class="space-y-4">
        <div class="card p-4">
          <h4 class="font-semibold text-sm mb-1">Q: 忘记密码怎么办？</h4>
          <p class="text-sm text-secondary">A: 请联系系统管理员重置密码。管理员可以在「设置 → 用户管理」中编辑用户并设置新密码。</p>
        </div>
        <div class="card p-4">
          <h4 class="font-semibold text-sm mb-1">Q: 库存数量显示负数怎么办？</h4>
          <p class="text-sm text-secondary">A: 正常情况下不应该出现负库存。请检查是否有重复出库的订单，联系管理员通过库存调整或入库操作修正。</p>
        </div>
        <div class="card p-4">
          <h4 class="font-semibold text-sm mb-1">Q: 订单提交后发现错误怎么办？</h4>
          <p class="text-sm text-secondary">A: 订单提交后不能直接修改。如果是数量错误，可以创建退货单退回部分商品；如果是价格错误，需要联系管理员在数据库层面修正。</p>
        </div>
        <div class="card p-4">
          <h4 class="font-semibold text-sm mb-1">Q: 导入Excel失败怎么办？</h4>
          <p class="text-sm text-secondary">A: 请检查：1) 使用系统提供的模板格式；2) 必填字段都有填写；3) 数字字段格式正确；4) 文件是 .xlsx 格式。</p>
        </div>
        <div class="card p-4">
          <h4 class="font-semibold text-sm mb-1">Q: 如何备份数据？</h4>
          <p class="text-sm text-secondary">A: 系统使用 PostgreSQL 数据库，支持自动和手动备份。在「设置 → 备份管理」中可以手动创建备份、下载备份文件或恢复历史备份。系统默认每日凌晨 3 点自动备份，保留 30 天。</p>
        </div>
        <div class="card p-4">
          <h4 class="font-semibold text-sm mb-1">Q: 如何获取初始账号？</h4>
          <p class="text-sm text-secondary">A: 请联系系统管理员获取初始账号和密码。首次登录后系统会强制要求修改密码。</p>
        </div>
        <div class="card p-4">
          <h4 class="font-semibold text-sm mb-1">Q: 凭证借贷不平衡怎么办？</h4>
          <p class="text-sm text-secondary">A: 系统要求凭证的借方合计和贷方合计必须相等才能保存。请检查每一行分录的金额是否正确。业务自动生成的凭证（出入库、发票确认等）会自动保证借贷平衡。</p>
        </div>
        <div class="card p-4">
          <h4 class="font-semibold text-sm mb-1">Q: 期末结账失败怎么办？</h4>
          <p class="text-sm text-secondary">A: 结账前系统会执行 5 项检查（未过账凭证、未确认单据等），任一项未通过都不能结账。请根据检查结果逐项处理后重试。</p>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <div class="mt-8 pt-4 border-t border-line-strong text-center text-xs text-muted">
      <p>轻量级ERP系统 v4.15 使用手册 | 如有疑问，请联系系统管理员</p>
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
  { key: 'accounting', label: '会计管理' },
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

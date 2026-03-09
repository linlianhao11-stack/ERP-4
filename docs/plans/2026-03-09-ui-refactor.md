# UI 重构设计文档

> 状态：**已完成**
> 创建：2026-03-09
> 预览文件：`/ui-preview.html`

---

## 一、设计方向

### 风格定位

**Modern Industrial** — 对比优先、密度可控、功能即装饰。

| 决定 | 选择 |
|------|------|
| 整体风格 | Modern Industrial，高对比黑白为底，单一亮色点缀 |
| 主色 | 蔚蓝 `oklch(0.55 0.20 250)` — 偏蓝不偏紫 |
| 中性色 | Zinc 冷灰，纯净无色温 |
| 侧边栏 | 白色/微灰底 + 1px 边框，当前项主色淡底高亮 |
| 暗色模式 | 同步实现，亮/暗双模式 |
| 色彩空间 | OKLCH，感知均匀 |
| 字体 | Inter + Geist Mono |
| 重构策略 | Token-First 分层渐进 |

### 色彩系统（OKLCH）

```css
/* === 亮色模式 === */

/* Primary — Steel Blue */
--primary:        oklch(0.55 0.20 250);   /* 蔚蓝 */
--primary-hover:  oklch(0.50 0.22 250);
--primary-active: oklch(0.45 0.24 250);
--primary-muted:  oklch(0.55 0.20 250 / 0.10);
--primary-ring:   oklch(0.55 0.20 250 / 0.25);

/* Semantic */
--success:      oklch(0.65 0.2 145);      /* 翠绿 */
--warning:      oklch(0.75 0.18 75);      /* 琥珀 */
--error:        oklch(0.60 0.25 25);      /* 赤红 */
--info:         oklch(0.60 0.18 250);     /* 信息蓝 */

/* Neutrals — Zinc */
--bg:              oklch(0.985 0 0);      /* ~#fafafa */
--surface:         oklch(1 0 0);          /* ~#fefefe */
--elevated:        oklch(0.97 0 0);       /* ~#f5f5f5 */
--sunken:          oklch(0.955 0 0);      /* ~#f0f0f0 */
--text:            oklch(0.13 0 0);       /* ~#0a0a0a */
--text-secondary:  oklch(0.45 0 0);       /* ~#6b6b6b */
--text-muted:      oklch(0.55 0 0);       /* ~#8b8b8b */
--border:          oklch(0.87 0 0);       /* ~#d9d9d9 */
--border-light:    oklch(0.92 0 0);       /* ~#eaeaea */

/* === 暗色模式 === */
--bg-dark:         oklch(0.10 0 0);       /* ~#0a0a0a */
--surface-dark:    oklch(0.15 0 0);       /* ~#1a1a1a */
--elevated-dark:   oklch(0.20 0 0);       /* ~#2a2a2a */
--text-dark:       oklch(0.93 0 0);       /* ~#ededed */
--border-dark:     oklch(0.25 0 0);       /* ~#333333 */
--primary-dark:    oklch(0.72 0.16 250);  /* 亮色蓝 */
```

### 字体方案

```css
--font-display: 'Inter', 'Geist', system-ui, 'PingFang SC', 'Microsoft YaHei', sans-serif;
--font-body:    'Inter', 'Geist', system-ui, 'PingFang SC', 'Microsoft YaHei', sans-serif;
--font-mono:    'Geist Mono', 'JetBrains Mono', 'SF Mono', monospace;
```

### 设计原则

1. **对比优先** — 黑白为底，单一亮色点缀，层级靠粗细和大小区分
2. **密度可控** — 紧凑分组 + 宽松分隔创造呼吸感
3. **功能即装饰** — 无无意义装饰，状态色/边框/阴影都有目的
4. **一致到底** — 同一语义只用一个颜色值，CSS 变量消灭硬编码
5. **无障碍为基线** — WCAG AA 合规，焦点可见、键盘可用、ARIA 完整

### 反模式清单

- ❌ 硬编码 hex 色值
- ❌ 毛玻璃堆砌（backdrop-blur 仅限遮罩层）
- ❌ 渐变文字、霓虹光效
- ❌ 弹跳/弹性动画（用指数缓出）
- ❌ 卡片嵌套卡片
- ❌ 纯黑 #000 或纯白 #fff
- ❌ `<div @click>` 代替 `<button>`
- ❌ 无 `for` 的 `<label>`

---

## 二、当前项目状况

| 指标 | 数值 |
|------|------|
| Vue 文件总数 | 72（12 视图 + 60 组件） |
| 硬编码色值 | ~1,074 处 `[#hex]` |
| CSS 变量使用 | 0 处 |
| 暗色模式 | 不支持 |
| Tailwind 主题配置 | 无（使用默认 + 任意值） |
| 设计 Token | 仅注释，未实现 |

---

## 三、仪表盘新增功能

### 待办事项面板

销售趋势图右侧新增待办事项面板，按权限动态显示：

| 待办项 | 所需权限 | 说明 |
|--------|----------|------|
| 待审核订单 | `sales` | 未审核的销售订单数 |
| 待发货 | `logistics` | 已审核未发货的订单数 |
| 待收货 | `purchase` | 已下单未到货的采购单数 |
| 待收款 | `finance` | 应收未收的账款笔数 |
| 低库存预警 | `stock_view` | 低于安全库存的商品数 |
| 待开票 | `accounting_view` | 需要开票的订单数 |

### 侧边栏红色角标

侧边栏菜单项的数字计数改为 iOS 风格红色圆形角标（红底白字），提高可读性。

---

## 四、实施计划

### 总览

```
P0 Token 基础设施        ← 最关键，后续全部依赖
P1 公共组件重写          ← 5 个核心组件迁移到 token
P2 全局色值批量替换      ← 1,074 处硬编码 → token class
P3 布局与视觉调整        ← 侧边栏/登录页/仪表盘
P4 暗色模式完善          ← 暗色 CSS 变量生效
P5 打磨收尾              ← 空状态/动效/响应式检查
```

---

### P0：Token 基础设施 ✅

**目标**：建立 CSS 变量 + Tailwind 4 主题配置，使所有色值通过 token 管理。

**产物**：
- `frontend/src/styles/base.css` — 重写，定义所有 CSS 变量（亮/暗双模式）
- `frontend/src/styles/theme.css` — Tailwind `@theme` 配置，将 CSS 变量映射为 Tailwind 类
- `frontend/src/App.vue` — 添加 `data-theme` 属性切换逻辑
- `frontend/src/stores/app.js` — 新增 `theme` 状态（light/dark），持久化到 localStorage

**具体任务**：
1. 重写 `base.css`：用 `:root` 和 `[data-theme="dark"]` 定义全部色彩 token
2. 创建 Tailwind 4 `@theme` 配置，映射 `--primary` → `text-primary`、`bg-primary` 等
3. 保留旧的硬编码 class 不动（P2 统一替换），确保 P0 完成后系统不受影响
4. 在 app store 中添加主题切换功能
5. 在 App.vue 根元素绑定 `data-theme`

**验证标准**：
- 所有 CSS 变量在浏览器 DevTools 可见
- `document.documentElement.dataset.theme = 'dark'` 可切换暗色变量
- 现有页面外观不变（因为还没替换硬编码值）

---

### P1：公共组件重写 ⬜

**目标**：5 个核心公共组件迁移到 token 系统，成为其余组件的参考实现。

**产物**：
- `AppModal.vue` — 用 CSS 变量替换所有 `[#hex]`
- `AppTable.vue` — 同上
- `AppTabs.vue` — 同上
- `StatusBadge.vue` — 同上
- `base.css` 中的 `.btn` / `.input` / `.badge` / `.modal` / `.tab` / `.toggle` 类 — 全部迁移到 CSS 变量

**具体任务**：
1. 重写 `base.css` 组件层：`.btn-primary { background: var(--primary) }` 替代 `#0071e3`
2. 重写 `AppModal.vue`：去掉所有 `[#hex]`，用 token class 或 CSS 变量
3. 重写 `AppTable.vue`
4. 重写 `AppTabs.vue`
5. 重写 `StatusBadge.vue`
6. 验证所有公共组件在亮/暗模式下正常显示

**验证标准**：
- 5 个公共组件零硬编码色值
- 切换主题后组件颜色正确变化
- 业务组件（引用公共组件的）不受影响

---

### P2：全局色值批量替换 ⬜

**目标**：将 72 个文件中 ~1,074 处 `[#hex]` 替换为 Tailwind token class。

**替换映射表**：

| 旧值 | 新 class | 语义 | CSS 变量 |
|------|----------|------|----------|
| `text-[#1d1d1f]` | `text-foreground` | 主文字 | `var(--text)` |
| `text-[#86868b]` | `text-muted` | 辅助文字 | `var(--text-muted)` |
| `text-[#6e6e73]` | `text-secondary` | 次要文字 | `var(--text-secondary)` |
| `bg-[#fbfbfd]` | `bg-canvas` | 页面背景 | `var(--bg)` |
| `bg-[#ffffff]` / `bg-white` | `bg-surface` | 面板背景 | `var(--surface)` |
| `bg-[#f5f5f7]` | `bg-elevated` | 浮起面 | `var(--elevated)` |
| `border-[#e8e8ed]` | `border-line` | 边框 | `var(--border)` |
| `border-[#d2d2d7]` | `border-line-strong` | 强边框 | `var(--border-strong)` |
| `text-[#0071e3]` / 主色相关 | `text-primary` | 主色文字 | `var(--primary)` |
| `bg-[#0071e3]` | `bg-primary` | 主色背景 | `var(--primary)` |
| `text-[#34c759]` | `text-success` | 成功色 | `var(--success)` |
| `text-[#ff3b30]` | `text-error` | 错误色 | `var(--error)` |
| `text-[#ff9f0a]` | `text-warning` | 警告色 | `var(--warning)` |

**执行方式**：
1. 编写替换脚本，按映射表批量替换（先 dry-run 验证）
2. 手动检查 5 个最复杂的文件（DashboardView, SalesView, FinanceView, AccountingView, SettingsView）
3. 逐文件验证，确保无遗漏

**验证标准**：
- `grep -r '\[#' frontend/src/` 返回 0 结果
- 所有页面视觉无变化（亮色模式下）

---

### P3：布局与视觉调整 ⬜

**目标**：按预览版调整侧边栏、登录页、仪表盘等关键页面的视觉风格。

**具体任务**：
1. **侧边栏** — 微灰底 + 分组标签 + 红色角标（iOS 风格）+ 底部用户信息
2. **顶部栏** — 面包屑 + 搜索按钮 + 通知按钮 + 亮/暗切换 toggle
3. **仪表盘** — KPI 卡片新样式 + 销售趋势曲线图 + 右侧待办事项面板（按权限显示）
4. **登录页** — 按预览版重新设计
5. **侧边栏导航** — 确认 10 项：首页/销售/库存/采购/寄售/物流/客户/财务/会计/设置

**验证标准**：
- 侧边栏、仪表盘、登录页与 `ui-preview.html` 一致
- 侧边栏角标红色圆形、待办面板按权限过滤

---

### P4：暗色模式完善 ⬜

**目标**：暗色模式全面可用。

**具体任务**：
1. 验证所有页面在暗色模式下的对比度（WCAG AA）
2. 修复暗色模式下的视觉问题（阴影、边框、hover 状态等）
3. 处理第三方组件（Chart.js 图表）的暗色适配
4. 移动端底部导航栏暗色适配
5. 持久化主题选择到 localStorage，刷新保持

**验证标准**：
- 12 个页面暗色模式无视觉异常
- 主题切换丝滑无闪烁
- 刷新页面保持上次选择的主题

---

### P5：打磨收尾 ⬜

**目标**：细节打磨，达到生产品质。

**具体任务**：
1. 空状态设计 — 各列表页的"暂无数据"状态
2. 动效 — 页面切换、弹窗出入、Toast 通知（指数缓出，禁止弹跳）
3. 响应式检查 — 移动端 768px 以下布局验证
4. 无障碍检查 — 焦点可见、ARIA 属性、键盘导航
5. 清理 — 删除旧的未使用 CSS class、注释掉的代码

**验证标准**：
- Lighthouse Accessibility 分数 ≥ 90
- 移动端可正常操作所有核心功能
- 无 console warning

---

## 五、进度追踪

| 阶段 | 状态 | 完成日期 | 备注 |
|------|------|----------|------|
| P0 Token 基础设施 | ✅ 完成 | 2026-03-09 | CSS 变量 + @theme + 主题切换 |
| P1 公共组件重写 | ✅ 完成 | 2026-03-09 | base.css 组件层全部迁移 CSS 变量 |
| P2 全局色值替换 | ✅ 完成 | 2026-03-09 | 1,370 处 [#hex] → token class |
| P3 布局与视觉调整 | ✅ 完成 | 2026-03-09 | 侧边栏角标 + 待办面板 + 主题切换 |
| P4 暗色模式完善 | ✅ 完成 | 2026-03-09 | 阴影 token + SVG 适配 + 底栏透明 |
| P5 打磨收尾 | ✅ 完成 | 2026-03-09 | focus-visible + reduced-motion + 清理 |

---

## 六、文件变更索引

> 每个阶段完成后在此记录实际变更的文件。

### P0 变更文件
- `frontend/src/styles/base.css` — 添加 `:root` / `[data-theme="dark"]` CSS 变量（60+ token），保留全部现有组件样式
- `frontend/src/styles/theme.css` — **新建**，Tailwind 4 `@theme` 配置，映射 CSS 变量为 Tailwind 类
- `frontend/src/stores/app.js` — 新增 `theme` / `setTheme` / `toggleTheme` / `initTheme`
- `frontend/src/App.vue` — `onMounted` 中调用 `appStore.initTheme()`
- `frontend/index.html` — `<head>` 中添加内联脚本防止主题闪烁（FOUC）
- `CLAUDE.md` — 主色修正为 Steel Blue `oklch(0.55 0.20 250)`

### P1 变更文件
- `frontend/src/styles/base.css` — 组件层全部改用 CSS 变量：`.btn-primary`/`.input`/`.badge`/`.modal`/`.tab`/`.toggle` 等
- `frontend/src/components/common/AppTable.vue` — `text-[#hex]` → token class
- `frontend/src/utils/constants.js` — `shipmentStatusBadges` 改为 badge class

### P2 变更文件
- **57 个 .vue 文件** — 批量替换 1,370 处 `[#hex]` → Tailwind token class（3 轮脚本执行）
- 替换后 `grep -r '\[#' frontend/src/` 返回 0 结果

### P3 变更文件
- `backend/app/routers/dashboard.py` — 新增 `GET /api/todo-counts` 端点（按权限返回各模块待办数量）
- `frontend/src/api/dashboard.js` — 新增 `getTodoCounts()` API 函数
- `frontend/src/stores/app.js` — 新增 `todoCounts` / `loadTodoCounts`
- `frontend/src/App.vue` — `loadEssentials()` 中调用 `loadTodoCounts()`
- `frontend/src/components/layout/Sidebar.vue` — iOS 风格红色角标 + 主题切换按钮
- `frontend/src/views/DashboardView.vue` — 新增待办事项面板（按权限过滤，红色计数标签）
- `frontend/src/styles/base.css` — 新增 `.sidebar-badge` 样式

### P4 变更文件
- `frontend/src/styles/base.css` — 新增 `--shadow-*` 阴影 token（亮/暗双模式），`--surface-translucent` token；组件层 box-shadow 全部改用 CSS 变量
- `frontend/src/components/layout/Sidebar.vue` — SVG logo `stroke="white"` → `stroke="currentColor"` + `text-canvas`
- `frontend/src/views/LoginView.vue` — 同上 SVG 修复

### P5 变更文件
- `frontend/src/styles/base.css` — 全局 `:focus-visible` 样式（主色 outline）；`prefers-reduced-motion` 媒体查询禁用动画

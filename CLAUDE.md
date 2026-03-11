# CLAUDE.md — ERP-4 项目指南

## 技术栈
- **后端**: FastAPI + Tortoise ORM + PostgreSQL 16
- **前端**: Vue 3 (Composition API) + Tailwind CSS 4 + Vite 7
- **图标**: lucide-vue-next
- **图表**: Chart.js 4.5
- **状态管理**: Pinia 3
- **路由**: Vue Router 4

## 开发规范
- **全程使用中文沟通**，包括代码注释、commit message 描述、文档更新等
- **所有代码开发必须使用 superpowers skill 流程**：brainstorming → writing-plans → subagent-driven-development / executing-plans → verification-before-completion → requesting-code-review
- Docker/容器管理统一通过 OrbStack，启动前先 `orb start`，不使用 Docker Desktop 或其他工具
- 前端代码在 `frontend/src/`，构建输出到 `backend/static/`
- 样式系统在 `frontend/src/styles/base.css`，使用 Tailwind `@layer` 组织
- 组件使用 Vue 3 `<script setup>` 语法
- API 模块在 `frontend/src/api/`，通过 Axios 实例统一管理
- Python 3.9 兼容需用 `from __future__ import annotations`

## 变更验证策略（节省 Token）
- **首选 `npm run build`** — 编译通过即可覆盖 90% 问题（语法、import、模板错误），大部分改动到此即可
- **用 `preview_snapshot` 代替 `preview_screenshot`** — snapshot 返回文本格式的可访问性树，token 消耗远小于截图，用于验证页面结构和内容
- **只在视觉/CSS 变更时才截图** — 如颜色、间距、布局调整，拍 1-2 张关键截图即可，不要逐页逐 tab 截图
- **用 `preview_inspect` 检查具体 CSS** — 比截全图更精准，用于验证特定样式属性
- **机械性改动跳过 preview** — 批量替换 class 名、重命名等，build 通过即可
- **`preview_console_logs` + `preview_logs`** — 检查运行时错误，比截图更高效
- **禁止**：逐页面、逐 tab 循环截图验证

## Design Context

### 用户画像
- **主要用户**: 中小贸易/零售企业的业务员、仓管员、财务人员、管理层
- **使用场景**: 日常高频操作（开单、入库、查账）+ 管理层数据查看
- **核心需求**: 操作层面追求效率和速度，数据层面追求专业和清晰
- **技术水平**: 参差不齐，需要低学习成本但不能牺牲信息密度

### 品牌个性
- **三个词**: 精准、克制、可靠
- **情感目标**: 让用户感到"工具可信赖、数据很清楚、操作很顺畅"
- **语气**: 简洁直接，不卖弄，不啰嗦，像一个靠谱的同事

### 美学方向
- **风格**: 现代工业风（Modern Industrial）
- **参考**: Vercel（极致黑白对比、留白、几何感）+ Linear（信息密度、紫色点缀、暗色优先）
- **反参考**: 不要传统 ERP 的灰蓝沉闷感，不要 SaaS 常见的圆润可爱风
- **主题**: 支持亮/暗双模式，用户手动切换
- **主色**: Steel Blue `oklch(0.55 0.20 250)` — 偏蓝不偏紫，清晰专业
- **字体**: Inter + Geist Mono，中文回退系统字体

### 色彩系统（OKLCH）
```
--color-primary:       oklch(0.55 0.20 250)    /* 蔚蓝 Steel Blue */
--color-primary-hover: oklch(0.50 0.22 250)    /* 深一档 */
--color-primary-muted: oklch(0.55 0.20 250 / 0.10) /* 轻底色 */

--color-success:       oklch(0.65 0.2 145)     /* 翠绿 */
--color-warning:       oklch(0.75 0.18 75)     /* 琥珀 */
--color-error:         oklch(0.60 0.25 25)     /* 赤红 */

/* 亮色模式中性色 */
--color-bg:            oklch(0.985 0 0)        /* 近白 ~#fafafa */
--color-surface:       oklch(1 0 0)            /* 纯面板 */
--color-elevated:      oklch(0.97 0 0)         /* 浮起面 */
--color-text:          oklch(0.13 0 0)         /* 近黑 ~#0a0a0a */
--color-text-secondary:oklch(0.55 0 0)         /* 辅助文字 */
--color-text-muted:    oklch(0.45 0 0)         /* 弱化文字 */
--color-border:        oklch(0.87 0 0)         /* 边框 */
--color-border-light:  oklch(0.92 0 0)         /* 轻边框 */

/* 暗色模式中性色 */
--color-bg-dark:            oklch(0.10 0 0)    /* 深底 ~#0a0a0a */
--color-surface-dark:       oklch(0.15 0 0)    /* 面板 */
--color-elevated-dark:      oklch(0.20 0 0)    /* 浮起面 */
--color-text-dark:          oklch(0.93 0 0)    /* 近白文字 */
--color-text-secondary-dark:oklch(0.60 0 0)    /* 辅助 */
--color-border-dark:        oklch(0.25 0 0)    /* 暗边框 */
```

### 字体方案
```
--font-display: 'Geist', 'Inter', system-ui, sans-serif   /* 标题/数字 */
--font-body:    'Geist', 'Inter', system-ui, sans-serif   /* 正文 */
--font-mono:    'Geist Mono', 'JetBrains Mono', monospace /* 代码/金额 */
```
- Geist 是 Vercel 开源字体，几何感强，现代工业风最佳匹配
- 中文回退到系统字体（macOS: PingFang SC / Windows: Microsoft YaHei）
- 金额数字用 tabular-nums + Geist Mono 保证对齐

### 设计原则
1. **对比优先**: 高对比度是工业风核心——黑白为底，单一亮色点缀，层级靠粗细和大小区分而非颜色堆砌
2. **密度可控**: 信息密度高但不拥挤——通过间距节奏（紧凑分组 + 宽松分隔）创造呼吸感
3. **功能即装饰**: 不加无意义的装饰——每个视觉元素都服务于功能，状态色、边框、阴影都有目的
4. **一致到底**: 同一语义只用一个颜色值——通过 CSS 变量 + Tailwind 主题配置消灭硬编码色值
5. **无障碍为基线**: WCAG AA 合规不是加分项，是底线——对比度、焦点可见、键盘可用、ARIA 完整

### 反模式清单（禁止出现）
- ❌ 硬编码 hex 色值（必须通过 CSS 变量或 Tailwind token）
- ❌ 毛玻璃堆砌（backdrop-blur 仅限遮罩层）
- ❌ 渐变文字、霓虹光效
- ❌ 弹跳/弹性动画（用指数缓出）
- ❌ 卡片嵌套卡片
- ❌ 3 层以上弹窗嵌套
- ❌ 灰色文字在彩色背景上
- ❌ 纯黑 #000 或纯白 #fff（必须微调色温）
- ❌ `<div @click>` 代替 `<button>`
- ❌ 无 `for` 的 `<label>`

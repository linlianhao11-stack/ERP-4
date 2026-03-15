# 分页组件 UI 重设计

## 问题

1. 分页控件在 `<table>` 外部，背景色（纯白 `--surface`）比表格区域（`--elevated`）更亮
2. 合计行与分页之间有多余的 `border-t` 黑色分割条，表头行间无此分割
3. 分页区高度（`py-3` + `btn-sm min-height:36px`）远超表格行高
4. 只有「上一页 / 下一页」，无页码快捷跳转

## 方案

### 结构：分页行移入 `<tfoot>`

```
<tfoot class="bg-elevated text-sm">
  <tr> 本页合计 … </tr>        ← 合计行（已有）
  <tr> 总条数 | 页码导航 </tr>  ← 新增分页行
</tfoot>
```

- 合计行与分页行共享 `bg-elevated` 背景，与表头一致
- 行间分割用普通 `border-bottom: 1px solid var(--border)`，和表体行一样
- 移除原本独立的 `<div>` 分页容器

### 页码算法：最多 5 个可见页码

```
总页数 ≤ 5：全部显示  [1] 2 3 4 5
总页数 > 5：
  当前页 ≤ 3：    [1] 2 3 … 20
  当前页 ≥ 末-2：  1 … 18 19 [20]
  其他：          1 … 4 [5] 6 … 20
```

省略号 `…` 不可点击，当前页高亮用 `bg-primary text-white` 圆角小色块。

### 分页行布局

```
| 共 120 条                ‹  1 … 4 [5] 6 … 20  ›               |
```

- 单个 `<td colspan="100">`
- 内部 flex：左侧总条数，中间页码组，右侧可选留空
- padding 与 th 一致：`10px 14px`

### 样式细节

| 元素 | 样式 |
|------|------|
| 分页行背景 | `bg-elevated`（同表头） |
| 行高/padding | `px-3.5 py-2.5`（与 th 的 `10px 14px` 一致） |
| 页码按钮 | `w-7 h-7 text-xs rounded-md` 内联方块 |
| 当前页 | `bg-primary text-white font-medium` |
| 非当前页 | `text-muted hover:bg-elevated hover:text-text` |
| ‹ › 箭头 | 同页码按钮大小，disabled 时 `opacity-30` |
| 省略号 | `text-muted cursor-default` 不可点击 |
| 总条数文字 | `text-xs text-muted` |

### `usePagination.js` 扩展

新增：
- `visiblePages` computed — 返回页码数组（数字或 `'…'`）
- `goToPage(n)` — 跳转到指定页

### 涉及文件

- `frontend/src/composables/usePagination.js` — 核心逻辑扩展
- `frontend/src/styles/base.css` — 可选：分页相关的基础样式
- 所有使用分页的业务组件（约 20 个 Tab/Panel）— 替换分页模板

### 暗色模式

无需额外处理 — `bg-elevated`、`--border`、`--text-muted` 已有暗色变量。

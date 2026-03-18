# AI Chat 多表格支持 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让 AI Chat 支持一次生成多条 SQL，分别执行并在前端渲染为多张独立带标题的表格。

**Architecture:** 后端在 system prompt 中新增 `multi_sql` 响应类型，R1 返回 `queries` 数组后逐条校验执行，收集结果交给 V3 统一分析。前端 AiMessage.vue 新增 `tables` 数组渲染，复用现有表格样式。向后兼容：单 SQL 场景完全不变。

**Tech Stack:** FastAPI + asyncpg + DeepSeek R1/V3 / Vue 3 + lucide-vue-next + openpyxl

---

### Task 1: 后端 — System Prompt 新增 multi_sql 响应类型

**Files:**
- Modify: `backend/app/ai/prompt_builder.py:48-82`

**Step 1: 在响应格式区域（第 49-60 行之间）追加第 4 种类型**

在第 59 行（`3. 不需要查数据库的问题`）之后，第 61 行（`**判断规则**`）之前，插入：

```python
4. 需要从多个角度查数据的综合问题（如日报、周报、经营分析）→ 生成多条 SQL:
{{"type": "multi_sql", "queries": [
  {{"title": "小节标题（中文）", "sql": "SELECT ..."}},
  {{"title": "另一个小节", "sql": "SELECT ..."}}
], "explanation": "简短说明（中文，不要带英文）"}}

multi_sql 使用规则：
- 仅当问题明确涉及 2 个以上不同维度（如销售+采购+库存）时才使用
- 每条 SQL 独立查询一个维度，用 title 标明该查询的主题
- 最多 10 条查询
- 每条 SQL 仍需遵守所有 SQL 生成规则（SELECT only、中文别名、LIMIT 等）
- 单一维度的问题（如"本月销售额"）仍然用普通 sql 类型，不要用 multi_sql
```

**Step 2: 验证语法**

Run: `cd /Users/lin/Desktop/erp-4/backend && python3 -c "from app.ai.prompt_builder import build_sql_prompt; print('OK')"`

注意：此命令可能因 SECRET_KEY 环境变量未设置而失败，这是正常的。改用：
Run: `cd /Users/lin/Desktop/erp-4/backend && python3 -c "from app.ai.prompt_builder import DEFAULT_SQL_SYSTEM_PROMPT; print('multi_sql' in DEFAULT_SQL_SYSTEM_PROMPT)"`
Expected: True

**Step 3: Commit**

```bash
git add backend/app/ai/prompt_builder.py
git commit -m "feat(ai): add multi_sql response type to SQL generation system prompt"
```

---

### Task 2: 后端 — ai_chat_service 新增 multi_sql 处理

**Files:**
- Modify: `backend/app/services/ai_chat_service.py:305-390`

**Step 1: 在 `resp_type == "text"` 分支之后（第 323 行 return 后），`resp_type != "sql"` 检查之前（第 325 行前），插入 multi_sql 分支**

```python
        if resp_type == "multi_sql":
            queries = r1_result.get("queries", [])
            if not queries or not isinstance(queries, list):
                yield {"event": "done", "data": {"type": "answer", "message_id": message_id, "analysis": r1_result.get("explanation", "未能生成查询")}}
                return

            queries = queries[:10]  # 最多 10 条
            tables = []
            all_sqls = []
            total_queries = len(queries)

            for qi, q in enumerate(queries):
                title = q.get("title", f"查询 {qi + 1}")
                raw_sql = q.get("sql", "")
                if not raw_sql:
                    continue

                is_safe, sanitized, reason = validate_sql(raw_sql, allowed_tables=allowed)
                if not is_safe:
                    logger.warning(f"multi_sql 第 {qi+1} 条校验失败: {reason}")
                    continue

                yield {"event": "progress", "data": {"stage": "executing", "message": f"正在查询: {title} ({qi+1}/{total_queries})..."}}

                try:
                    pool = await get_ai_pool(db_dsn)
                    async with pool.acquire() as conn:
                        async with conn.transaction(readonly=True):
                            rows = await conn.fetch(sanitized)
                            if len(rows) > 1000:
                                rows = rows[:1000]

                    if rows:
                        columns = list(rows[0].keys())
                        row_data = [[_serialize_value(r[c]) for c in columns] for r in rows]
                        tables.append({"title": title, "columns": columns, "rows": row_data, "row_count": len(rows)})
                        all_sqls.append(sanitized)
                    else:
                        tables.append({"title": title, "columns": [], "rows": [], "row_count": 0})
                        all_sqls.append(sanitized)
                except Exception as e:
                    logger.warning(f"multi_sql 第 {qi+1} 条执行失败: {e}")
                    continue

            if not tables:
                yield {"event": "error", "data": {"message": "所有查询均执行失败，请换个说法试试", "retryable": True, "error_type": "execution"}}
                return

            # 拼接所有表的摘要数据交给 V3 分析
            yield {"event": "progress", "data": {"stage": "analyzing", "message": "正在分析数据..."}}
            analysis_prompt = build_analysis_prompt(config.get("ai.prompt.analysis"))
            data_summary = f"用户问题: {message}\n\n查询了 {len(tables)} 组数据:\n"
            for t in tables:
                data_summary += f"\n### {t['title']} ({t['row_count']} 行)\n"
                if t['columns']:
                    data_summary += f"列: {t['columns']}\n"
                    for row in t['rows'][:10]:
                        data_summary += str(row) + "\n"

            v3_result = await call_deepseek(
                messages=[
                    {"role": "system", "content": analysis_prompt},
                    {"role": "user", "content": data_summary},
                ],
                api_key=api_key,
                base_url=config.get("base_url", DEFAULT_BASE_URL),
                model=config.get("model_analysis", DEFAULT_MODEL_ANALYSIS),
                temperature=0.7,
                max_tokens=2048,
                timeout=60.0,
            )

            analysis_text = "查询完成。"
            chart_config = None
            suggestions = None
            if v3_result:
                analysis_text = v3_result.get("analysis", "查询完成。")
                chart_config = v3_result.get("chart_config")
                suggestions = v3_result.get("suggestions")

            yield {"event": "done", "data": {
                "type": "answer",
                "message_id": message_id,
                "analysis": analysis_text,
                "tables": tables,
                "table_data": None,
                "chart_config": chart_config,
                "sqls": all_sqls,
                "sql": None,
                "row_count": sum(t["row_count"] for t in tables),
                "suggestions": suggestions,
            }}
            return
```

**重要**：需要确保 `get_ai_pool`、`_serialize_value`、`validate_sql`、`call_deepseek`、`build_analysis_prompt` 等函数在该位置都已可用（它们在文件顶部已经导入）。

**Step 2: 验证语法**

Run: `cd /Users/lin/Desktop/erp-4/backend && python3 -c "import ast; ast.parse(open('app/services/ai_chat_service.py').read()); print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add backend/app/services/ai_chat_service.py
git commit -m "feat(ai): handle multi_sql response type with per-query execution and unified analysis"
```

---

### Task 3: 前端 — AiMessage.vue 多表格渲染

**Files:**
- Modify: `frontend/src/components/business/AiMessage.vue`

**Step 1: 在模板中，单表格渲染块（第 42-64 行）之后，`<!-- 图表 -->` 注释之前，插入多表格渲染块**

```html
        <!-- 多表格（multi_sql 响应） -->
        <template v-else-if="msg.tables?.length">
          <div v-for="(t, ti) in msg.tables" :key="ti" class="mt-3 border rounded-lg overflow-hidden">
            <div class="px-3 py-2 bg-elevated border-b">
              <span class="font-semibold text-xs text-secondary">{{ t.title }}</span>
              <span class="text-[11px] text-muted ml-2">{{ t.row_count }} 行</span>
            </div>
            <div v-if="t.columns?.length" class="overflow-x-auto" :class="tableMaxH">
              <table class="w-full text-sm">
                <thead class="bg-elevated sticky top-0">
                  <tr>
                    <th v-for="col in t.columns" :key="col" class="px-2 py-2 text-left text-xs font-medium text-muted whitespace-nowrap">
                      {{ col }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, ri) in t.rows" :key="ri" class="border-t">
                    <td v-for="(cell, ci) in row" :key="ci" class="px-3 py-1.5 whitespace-nowrap" :class="isNumber(cell) ? 'tabular-nums font-mono text-right' : ''">
                      {{ formatCell(cell) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="px-3 py-3 text-xs text-muted text-center">暂无数据</div>
          </div>
        </template>
```

**Step 2: 修改 SQL 折叠区域（第 70-73 行），支持 sqls 数组**

将：
```html
        <details v-if="msg.sql" class="mt-3">
          <summary class="text-xs text-muted cursor-pointer">查看 SQL</summary>
          <pre class="mt-1 p-2 bg-elevated rounded text-xs font-mono overflow-x-auto">{{ msg.sql }}</pre>
        </details>
```

替换为：
```html
        <details v-if="msg.sql || msg.sqls?.length" class="mt-3">
          <summary class="text-xs text-muted cursor-pointer">查看 SQL</summary>
          <template v-if="msg.sqls?.length">
            <pre v-for="(s, si) in msg.sqls" :key="si" class="mt-1 p-2 bg-elevated rounded text-xs font-mono overflow-x-auto">{{ s }}</pre>
          </template>
          <pre v-else class="mt-1 p-2 bg-elevated rounded text-xs font-mono overflow-x-auto">{{ msg.sql }}</pre>
        </details>
```

**Step 3: 修改操作栏中复制/导出按钮的条件（第 76-88 行）**

将 `v-if="msg.table_data"` 改为 `v-if="msg.table_data || msg.tables?.length"`（共 2 处：复制按钮和导出菜单）。

**Step 4: 修改 `copyTable` 函数，支持多表格**

替换 `copyTable` 函数为：
```javascript
const copyTable = async () => {
  let tsv = ''
  if (props.msg.tables?.length) {
    tsv = props.msg.tables.map(t => {
      const header = t.columns.join('\t')
      const body = t.rows.map(r => r.map(c => c ?? '').join('\t')).join('\n')
      return `--- ${t.title} ---\n${header}\n${body}`
    }).join('\n\n')
  } else if (props.msg.table_data) {
    const { columns, rows } = props.msg.table_data
    tsv = [columns.join('\t'), ...rows.map(r => r.map(c => c ?? '').join('\t'))].join('\n')
  }
  if (!tsv) return
  try {
    await navigator.clipboard.writeText(tsv)
    appStore.showToast('已复制到剪贴板')
  } catch {
    appStore.showToast('复制失败', 'error')
  }
}
```

**Step 5: 修改 `exportCsv` 函数，支持多表格**

替换 `exportCsv` 函数为：
```javascript
const exportCsv = () => {
  const bom = '\uFEFF'
  let csv = bom
  if (props.msg.tables?.length) {
    csv += props.msg.tables.map(t => {
      const header = t.columns.join(',')
      const body = t.rows.map(r => r.map(c => `"${String(c ?? '').replace(/"/g, '""')}"`).join(',')).join('\n')
      return `${t.title}\n${header}\n${body}`
    }).join('\n\n')
  } else if (props.msg.table_data) {
    const { columns, rows } = props.msg.table_data
    csv += [columns.join(','), ...rows.map(r => r.map(c => `"${String(c ?? '').replace(/"/g, '""')}"`).join(','))].join('\n')
  }
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'AI查询结果.csv'
  a.click()
  URL.revokeObjectURL(url)
}
```

**Step 6: 验证构建**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npm run build`
Expected: 构建成功

**Step 7: Commit**

```bash
git add frontend/src/components/business/AiMessage.vue
git commit -m "feat(ai): render multi-table results with per-table title, copy and CSV export support"
```

---

### Task 4: 前端 — 数据过期处理 + Excel 多 sheet 导出

**Files:**
- Modify: `frontend/src/composables/useAiChat.js:80-86`
- Modify: `frontend/src/components/business/AiChatbot.vue:160-168`
- Modify: `backend/app/routers/ai_chat.py:114-149`
- Modify: `backend/app/schemas/ai.py:25-27`

**Step 1: useAiChat.js — 扩展 _hasTableData 判断**

在 `useAiChat.js` 第 80-86 行附近，找到存储消息时剥离 table_data 的逻辑：

```javascript
      const { table_data, chart_config, ...rest } = m
      return {
        ...rest,
        _hasTableData: !!table_data,
        _hasChartConfig: !!chart_config,
      }
```

替换为：
```javascript
      const { table_data, tables, chart_config, ...rest } = m
      return {
        ...rest,
        _hasTableData: !!table_data || !!tables?.length,
        _hasChartConfig: !!chart_config,
      }
```

**Step 2: AiChatbot.vue — 导出处理兼容多表格**

在 `handleExport` 函数中（约第 160-168 行），将：
```javascript
const handleExport = async (msg) => {
  if (!msg.table_data) return
  try {
    const { data } = await aiExport({ table_data: msg.table_data, title: 'AI查询结果' })
```

替换为：
```javascript
const handleExport = async (msg) => {
  if (!msg.table_data && !msg.tables?.length) return
  try {
    const payload = msg.tables?.length
      ? { tables: msg.tables, title: 'AI查询结果' }
      : { table_data: msg.table_data, title: 'AI查询结果' }
    const { data } = await aiExport(payload)
```

**Step 3: 后端 ExportRequest schema — 新增 tables 字段**

在 `backend/app/schemas/ai.py` 的 `ExportRequest` 类中，将：
```python
class ExportRequest(BaseModel):
    table_data: dict
    title: str = "AI查询结果"
```

替换为：
```python
class ExportRequest(BaseModel):
    table_data: Optional[dict] = None
    tables: Optional[list[dict]] = None
    title: str = "AI查询结果"
```

确保文件顶部已有 `from typing import Optional`。

**Step 4: 后端导出端点 — 支持多 sheet**

在 `backend/app/routers/ai_chat.py` 的 `ai_export` 函数中（第 115-149 行），替换函数体为：

```python
async def ai_export(body: ExportRequest, user: User = Depends(require_permission("ai_chat"))):
    """导出查询结果为 Excel（支持多表格多 sheet）"""
    import openpyxl

    wb = openpyxl.Workbook()

    if body.tables:
        # 多表格：每张表一个 sheet
        for ti, t in enumerate(body.tables):
            if ti == 0:
                ws = wb.active
            else:
                ws = wb.create_sheet()
            ws.title = (t.get("title", f"查询{ti+1}"))[:31]
            columns = t.get("columns", [])
            rows = t.get("rows", [])
            for col, name in enumerate(columns, 1):
                ws.cell(row=1, column=col, value=name)
            for row_idx, row in enumerate(rows, 2):
                for col_idx, val in enumerate(row, 1):
                    ws.cell(row=row_idx, column=col_idx, value=val)
    elif body.table_data:
        # 单表格：原有逻辑
        ws = wb.active
        ws.title = body.title[:31]
        table_data = body.table_data
        if "columns" not in table_data or "rows" not in table_data:
            raise HTTPException(status_code=400, detail="无效的表格数据")
        for col, name in enumerate(table_data["columns"], 1):
            ws.cell(row=1, column=col, value=name)
        for row_idx, row in enumerate(table_data["rows"], 2):
            for col_idx, val in enumerate(row, 1):
                ws.cell(row=row_idx, column=col_idx, value=val)
    else:
        raise HTTPException(status_code=400, detail="无效的表格数据")

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"{body.title}.xlsx"
    from urllib.parse import quote
    encoded_name = quote(filename)
    await log_operation(user, "AI_EXPORT", "SYSTEM", None, f"AI 对话导出 Excel: {body.title}")
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=\"export.xlsx\"; filename*=UTF-8''{encoded_name}"},
    )
```

**Step 5: 验证构建**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npm run build`
Expected: 构建成功

**Step 6: Commit**

```bash
git add frontend/src/composables/useAiChat.js frontend/src/components/business/AiChatbot.vue backend/app/routers/ai_chat.py backend/app/schemas/ai.py
git commit -m "feat(ai): multi-sheet Excel export and data expiry support for multi-table responses"
```

---

### Task 5: Docker 集成验证

**Step 1: 构建前端**

Run: `cd /Users/lin/Desktop/erp-4/frontend && npm run build`

**Step 2: 构建 Docker 并启动**

Run: `cd /Users/lin/Desktop/erp-4 && docker compose up --build -d`

**Step 3: 检查容器日志无启动错误**

Run: `docker compose logs erp --tail=20`
Expected: 无 ImportError 或 SyntaxError，`Application startup complete`

**Step 4: 验证 AI Chat 端点仍然正常**

Run: `curl -s http://localhost:8090/api/ai/status | python3 -m json.tool`
Expected: 返回 JSON（`available` 为 true 或 false 取决于 AI 配置）

**Step 5: Commit（如有修复）**

```bash
git add -A && git commit -m "fix: address issues found during Docker integration test"
```

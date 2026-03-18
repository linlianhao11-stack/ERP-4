# AI Chat 多表格支持

> **目标**: 让 AI Chat 在回答综合问题（日报、多维度分析）时，生成多条 SQL 分别执行，前端渲染多张独立表格，替代当前单 SQL 混合表格的混乱输出。

## 约束

- 向后兼容：单 SQL 场景（`type: "sql"`）不受影响
- 最多 10 条查询
- 不引入新依赖
- 复用现有 SQL 校验、执行、分析管线

## 改动清单

### 1. System Prompt 新增 multi_sql 响应类型

**文件**: `backend/app/ai/prompt_builder.py`

在响应格式部分新增第 4 种类型：

```json
{"type": "multi_sql", "queries": [
  {"title": "销售概况", "sql": "SELECT ..."},
  {"title": "采购概况", "sql": "SELECT ..."}
], "explanation": "简短说明（中文）"}
```

判断规则：当问题涉及多个维度（销售+采购+库存等），或要求"日报/周报/综合分析"时使用 `multi_sql`。最多 10 条。

### 2. 后端 multi_sql 处理

**文件**: `backend/app/services/ai_chat_service.py`

在 `resp_type` 分支新增 `multi_sql` 处理：

1. 从 `r1_result["queries"]` 取出 `[{title, sql}, ...]`，截断到 10 条
2. 逐条 `validate_sql`，跳过不安全的
3. 逐条执行，每条前发 SSE progress（"正在查询: 销售概况 (2/5)..."）
4. 收集结果到 `tables: [{title, columns, rows, row_count}, ...]`
5. 拼接所有表摘要数据，一次性交给 V3 分析
6. 单条执行失败：跳过该表，不阻塞其他表

响应格式：

```json
{
  "type": "answer",
  "message_id": "...",
  "analysis": "V3 分析文本",
  "tables": [
    {"title": "销售概况", "columns": [...], "rows": [...], "row_count": 10},
    {"title": "采购概况", "columns": [...], "rows": [...], "row_count": 5}
  ],
  "table_data": null,
  "chart_config": null,
  "sql": null,
  "sqls": ["SELECT ...", "SELECT ..."],
  "suggestions": [...]
}
```

### 3. 前端多表格渲染

**文件**: `frontend/src/components/business/AiMessage.vue`

在现有 `table_data` 渲染块之后，新增 `tables` 数组渲染：

- 每张表带标题栏（`bg-elevated font-semibold text-xs`）
- 表格样式复用现有单表格样式
- 底部行数统计
- 导出：多表格导出为一个 Excel，每张表一个 sheet
- 复制：合并所有表格为 TSV 文本，表之间用空行分隔
- SQL 折叠：显示所有 `sqls` 数组

### 4. 前端数据过期处理

**文件**: `frontend/src/composables/useAiChat.js`（如涉及）

`_hasTableData` 判断增加 `msg.tables?.length > 0` 条件，确保多表格消息也支持数据过期重查。

## 不做的事

- 不改单 SQL 场景的任何行为
- 不支持多图表（仍然只有一个 chart_config）
- 不支持 multi_sql 的自动纠错循环（单条失败跳过）
- 不改缓存逻辑（multi_sql 结果照常缓存）
- 不改预置查询（preset）的逻辑

# 可观测性改进设计

> **目标**: 为 ERP 系统增加请求日志、请求 ID 追踪、慢查询日志，提升运维排障能力。

## 约束

- 单机 Docker 部署，日志通过 `docker compose logs` 查看
- 不引入 Sentry 或外部日志采集系统
- 不添加新 Python 依赖
- 不改变现有 `get_logger()` 调用方式

## 改动清单

### 1. 请求日志中间件（AccessLogMiddleware）

**文件**: `main.py`

每个 API 请求记录一条结构化日志：
```json
{"time":"...","level":"INFO","module":"erp.access","method":"POST","path":"/api/orders","status":200,"duration_ms":45,"client":"192.168.1.5","request_id":"a3f8b2c1"}
```

规则：
- 跳过 `/health` 和 `/assets/` 请求
- 耗时 >1s → WARNING 级别
- 5xx 响应 → ERROR 级别
- 其余 → INFO 级别

### 2. 请求 ID 追踪（contextvars）

**文件**: `app/logger.py`

- 使用 `contextvars.ContextVar` 存储当前请求的 `request_id`
- `StructuredFormatter` 自动将 `request_id` 注入每条日志的 JSON 输出
- `AccessLogMiddleware` 在请求开始时生成 UUID 前 8 位并设置到 contextvar
- 现有代码的 `logger.info/error/warning` 调用无需修改

### 3. PostgreSQL 慢查询日志

**文件**: `docker-compose.yml`

```yaml
command: postgres -c log_min_duration_statement=500 -c log_statement=none
```

- 超过 500ms 的 SQL 自动记录
- 通过 `docker compose logs db | grep duration` 查看

## 不做的事

- 不接入 Sentry
- 不引入 Loki/ELK
- 不添加新依赖

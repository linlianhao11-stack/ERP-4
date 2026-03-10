# 轻量级 ERP 系统 v4.19.0

面向中小贸易/批发企业的全功能进销存管理系统，支持销售、采购、库存、财务、物流、寄售、会计等核心业务流程，含完整的业财一体化财务会计模块。

## 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 前端 | Vue 3 + Vue Router + Pinia | Vue 3.5 |
| UI | Tailwind CSS（OKLCH Token 设计系统） | v4 |
| 图表 | Chart.js | v4 |
| HTTP 客户端 | Axios | v1.13 |
| 构建工具 | Vite | v7 |
| 后端 | FastAPI + Uvicorn | FastAPI 0.109 |
| ORM | Tortoise ORM | v0.20 |
| 数据库 | PostgreSQL | v16 |
| 认证 | JWT (PyJWT) | — |
| 测试 | pytest + pytest-asyncio | — |
| 部署 | Docker + Docker Compose | — |

## 项目结构

```
erp-4/
├── docker-compose.yml          # 编排：PostgreSQL + 应用
├── Dockerfile                  # 多阶段构建（Node 构建前端 → Python 运行后端）
│
├── .env.example                # 环境变量模板
├── archive/                    # 历史遗留代码归档
│
├── backend/
│   ├── main.py                 # FastAPI 入口，lifespan 管理
│   ├── requirements.txt        # Python 依赖
│   ├── tests/                  # pytest 测试（84 个用例：认证/会计/账簿/应收应付/发票/出入库/期末/报表/业务流程集成测试）
│   ├── pytest.ini              # pytest 配置
│   ├── app/
│   │   ├── config.py           # 全局配置（环境变量 + 默认值）
│   │   ├── database.py         # Tortoise ORM 初始化
│   │   ├── logger.py           # 统一结构化 JSON 日志（级别可配置）
│   │   ├── exceptions.py       # 全局异常处理器
│   │   ├── migrations.py       # 启动时幂等初始化默认数据
│   │   ├── auth/               # JWT 签发 & 权限校验（含 token 版本机制）
│   │   ├── models/             # 数据模型（42 个）
│   │   ├── routers/            # API 路由（35 个模块，192 个端点，含通用 CRUD 工厂）
│   │   ├── schemas/            # Pydantic 请求/响应模型（23 个文件）
│   │   ├── services/           # 业务逻辑层（17 个服务）
│   │   └── utils/              # 工具函数（订单号生成、UTC 时间处理）
│   ├── backups/                # 数据库备份目录
│   └── static/                 # 前端构建产物（生产环境由后端托管）
│
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.js             # Vue 应用入口
        ├── App.vue             # 根组件
        ├── router/             # 路由定义
        ├── api/                # 后端 API 调用封装（20 个模块）
        ├── stores/             # Pinia 状态管理（10 个 store）
        ├── views/              # 页面视图（12 个）
        ├── components/         # 组件（layout / business / common）
        │   ├── layout/         # 布局组件（Sidebar, BottomNav, AppTabs）
        │   ├── business/       # 业务面板（FinanceOrdersPanel, PurchaseOrdersPanel 等）
        │   └── common/         # 通用组件（StatusBadge, FilterBar）
        ├── composables/        # 组合式函数（useApi、useFormat、usePagination、useStock 等 12 个）
        └── styles/             # 全局样式
```

## 功能模块

| 模块 | 路由 | 说明 |
|------|------|------|
| 仪表盘 | `/dashboard` | 销售统计、库存预警、经营概览、待办事项面板 |
| 销售管理 | `/sales` | 现款/账期/寄售调拨/寄售结算/退货订单 |
| 库存管理 | `/stock` | 入库、调拨、盘点调整、库存导出、SN 码管理 |
| 采购管理 | `/purchase` | 采购订单（创建→审核→付款→收货→退货）完整流程，供应商在账资金管理 |
| 寄售管理 | `/consignment` | 寄售调拨、寄售结算、寄售退货 |
| 物流管理 | `/logistics` | 发货确认、拆单发货、包裹商品明细、SN码记录、快递100对接 |
| 财务管理 | `/finance` | 收款、对账、欠款管理、返利管理（客户/供应商双向） |
| 会计管理 | `/accounting` | 10 个标签页：多账套、科目体系（32 预置科目）、会计期间、凭证管理（四级状态机）、账簿查询（总分类/明细/余额表）、应收管理（应收单/收款单/退款单/核销）、应付管理（应付单/付款单/退款单）、发票管理（销项/进项）、出入库单（销售出库/采购入库 + PDF 套打）、期末处理（损益结转/结账/年度结转）、财务报表（资产负债表/利润表/现金流量表 + Excel/PDF 导出） |
| 客户管理 | `/customers` | 客户信息、余额、返利、欠款、交易明细 |
| 系统设置 | `/settings` | 用户管理、权限管理、仓库/仓位、销售员、收款/付款方式、SN 码配置、备份管理 |

## 数据模型

核心模型共 44 个：

- **用户与权限**: User
- **商品**: Product, ProductBrand
- **仓储**: Warehouse, Location, WarehouseStock, StockLog
- **SN 管理**: SnConfig, SnCode
- **销售**: Customer, Salesperson, Order, OrderItem
- **采购**: Supplier, PurchaseOrder, PurchaseOrderItem, PurchaseReturn, PurchaseReturnItem
- **财务**: Payment, PaymentOrder, PaymentMethod, DisbursementMethod, RebateLog
- **会计基础**: AccountSet, ChartOfAccount, AccountingPeriod, Voucher, VoucherEntry
- **应收**: ReceivableBill, ReceiptBill, ReceiptRefundBill, ReceivableWriteOff
- **应付**: PayableBill, DisbursementBill, DisbursementRefundBill
- **发票**: Invoice, InvoiceItem
- **出入库单**: SalesDeliveryBill, SalesDeliveryItem, PurchaseReceiptBill, PurchaseReceiptItem
- **物流**: Shipment, ShipmentItem
- **系统**: OperationLog, SystemSetting

## 设计系统

**Modern Industrial** 风格 — 高对比黑白为底，单一亮色点缀。

| 项目 | 值 |
|------|-----|
| 主色 | Steel Blue `oklch(0.55 0.20 250)` |
| 色彩空间 | OKLCH（感知均匀） |
| 中性色 | Zinc 冷灰 |
| 字体 | Inter + Geist Mono |
| 主题 | 亮/暗双模式，手动切换，localStorage 持久化 |
| Token 数量 | 60+ CSS 变量 |
| 设计文档 | `docs/plans/2026-03-09-ui-refactor.md` |

样式文件结构：
- `frontend/src/styles/base.css` — CSS 变量定义（`:root` / `[data-theme="dark"]`）+ 全部组件样式
- `frontend/src/styles/theme.css` — Tailwind 4 `@theme` 配置，映射 CSS 变量为工具类

## 关键业务规则

### 采购成本价计算

采购收货时，商品的库存成本价 = **实际付款金额（已扣除返利抵扣）÷ 数量**。

例如：商品含税单价 100 元，采购 10 件，使用供应商返利抵扣 200 元，则实际付款 800 元，成本价 = 800 ÷ 10 = **80 元/件**。

> **设计原则**：成本价反映真实资金成本，返利抵扣视为已获得的折扣而非额外收入。这样计算出的毛利才能真实反映每笔交易的盈利情况。**请勿修改此逻辑。**
>
> 相关代码：`backend/app/routers/purchase_orders.py` → `receive_items` 函数中的 `cost_price` 计算。

## 环境变量

> 完整模板见项目根目录 `.env.example`

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `postgres://erp:erp@localhost:5432/erp` | PostgreSQL 连接串 |
| `POSTGRES_PASSWORD` | `erp123456` | PostgreSQL 密码（docker-compose 用） |
| `SECRET_KEY` | **必填，无默认值** | JWT 签名密钥，**必须在 .env 中设置** |
| `BACKUP_KEEP_DAYS` | `30` | 自动备份保留天数 |
| `BACKUP_HOUR` | `3` | 每日自动备份时间（24h） |
| `KD100_KEY` | （空） | 快递100 API Key |
| `KD100_CUSTOMER` | （空） | 快递100 Customer ID |
| `KD100_CALLBACK_URL` | （空） | 快递100回调地址 |
| `CORS_ORIGINS` | `*` | CORS 允许的源，逗号分隔 |
| `LOG_LEVEL` | `INFO` | 日志级别（DEBUG / INFO / WARNING / ERROR） |
| `DEBUG` | `false` | 开发模式（启用热重载） |

## 快速启动

### Docker 部署（推荐）

```bash
# 克隆项目
git clone <repo-url> erp-4 && cd erp-4

# 复制环境变量模板并修改
cp .env.example .env
# 编辑 .env，设置 SECRET_KEY 和 POSTGRES_PASSWORD
# 然后启动
docker compose up -d

# 访问 http://localhost:8090
# 默认管理员账号：admin（首次登录请联系管理员获取密码）
```

### 本地开发

**后端：**
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 需要本地 PostgreSQL 或设置 DATABASE_URL（密码与 docker-compose.yml 一致）
export DATABASE_URL=postgres://erp:erp123456@localhost:5432/erp
uvicorn main:app --host 0.0.0.0 --port 8090 --reload
```

**前端：**
```bash
cd frontend
npm install
npm run dev
# 开发服务器默认 http://localhost:5173，API 代理到 8090
```

**前端构建：**
```bash
cd frontend
npm run build
# 产物输出到 backend/static/（由 vite.config.js 配置）
```

## API 文档

启动后端后访问：
- Swagger UI: `http://localhost:8090/docs`
- ReDoc: `http://localhost:8090/redoc`

## 权限体系

系统采用基于权限列表的 RBAC 模型，用户角色为 `admin`（管理员，自动拥有全部权限）或 `user`（普通用户，按需分配）。

共 28 个权限码，分 10 个权限组：

| 权限组 | 权限标识 | 说明 |
|--------|---------|------|
| 首页 | `dashboard` | 仪表盘统计看板 |
| 销售管理 | `sales` | 销售开单（现款/账期/退货） |
| 库存管理 | `stock_view` | 查看库存列表和详情 |
| | `stock_edit` | 入库、调拨、盘点、商品管理 |
| 采购管理 | `purchase` | 采购下单 |
| | `purchase_approve` | 采购订单审核 |
| | `purchase_pay` | 采购付款确认 |
| | `purchase_receive` | 采购收货入库 |
| 寄售管理 | `consignment` | 寄售调拨/结算/退货 |
| 物流管理 | `logistics` | 物流发货、快递追踪 |
| 财务管理 | `finance` | 收款、对账、返利管理 |
| | `finance_confirm` | 确认收款 |
| 会计管理 | `accounting_view` | 会计查看（凭证/账簿/报表） |
| | `accounting_edit` | 会计录入（凭证/科目编辑） |
| | `accounting_approve` | 凭证审核 |
| | `accounting_post` | 凭证过账 |
| | `period_end` | 期末处理（结转/结账） |
| | `accounting_ar_view` | 应收查看 |
| | `accounting_ar_edit` | 应收编辑 |
| | `accounting_ar_confirm` | 应收确认 |
| | `accounting_ap_view` | 应付查看 |
| | `accounting_ap_edit` | 应付编辑 |
| | `accounting_ap_confirm` | 应付确认 |
| 客户管理 | `customer` | 客户信息维护 |
| 系统设置 | `settings` | 系统配置 |
| | `logs` | 操作日志查看 |
| | `admin` | 系统管理（用户/备份/账套） |

## 日志规范

系统使用结构化 JSON 日志（`app/logger.py`），输出到 stdout：

```json
{
  "time": "2026-02-12T03:00:00.000000Z",
  "level": "INFO",
  "module": "erp.backup",
  "message": "自动备份完成",
  "data": {"file": "erp_auto_20260212_030000.sql", "removed": 2}
}
```

使用方式：
```python
from app.logger import get_logger
logger = get_logger("模块名")
logger.info("操作成功", extra={"data": {"key": "value"}})
logger.error("操作失败", exc_info=e)
```

## 备份机制

- **自动备份**: 每日凌晨（`BACKUP_HOUR`）自动执行 `pg_dump`，保留 `BACKUP_KEEP_DAYS` 天
- **手动备份**: 管理员通过设置页面触发
- **备份管理**: 支持列表查看、下载、删除

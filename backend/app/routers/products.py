import io
from typing import Optional
from decimal import Decimal
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from tortoise import transactions
from tortoise.expressions import Q
from app.auth.dependencies import get_current_user, require_permission
from app.models import (
    User, Product, Warehouse, Location, WarehouseStock, StockLog, SnCode
)
from app.schemas.product import ProductCreate, ProductUpdate
from app.utils.time import now, to_naive, days_between
from app.services.operation_log_service import log_operation

router = APIRouter(prefix="/api/products", tags=["商品管理"])


@router.get("")
async def list_products(keyword: Optional[str] = None, category: Optional[str] = None,
                        warehouse_id: Optional[int] = None,
                        offset: int = 0, limit: int = 200,
                        user: User = Depends(get_current_user)):
    limit = min(limit, 1000)  # 安全上限
    query = Product.filter(is_active=True)
    if keyword:
        for word in keyword.split():
            query = query.filter(Q(sku__icontains=word) | Q(name__icontains=word) | Q(brand__icontains=word) | Q(category__icontains=word))
    if category:
        query = query.filter(category=category)
    total = await query.count()
    products = await query.order_by("-updated_at").offset(offset).limit(limit)

    # 批量查询所有库存（避免 N+1）
    product_ids = [p.id for p in products]
    stock_query = WarehouseStock.filter(product_id__in=product_ids) if product_ids else WarehouseStock.none()
    if warehouse_id:
        stock_query = stock_query.filter(warehouse_id=warehouse_id)
    all_stocks = await stock_query.select_related("warehouse", "location")

    stocks_by_product = {}
    for s in all_stocks:
        stocks_by_product.setdefault(s.product_id, []).append(s)

    result = []
    has_finance = user.role == "admin" or "finance" in (user.permissions or [])
    current_time = now()

    for p in products:
        stocks = stocks_by_product.get(p.id, [])
        total_qty = sum(s.quantity for s in stocks if not s.warehouse.is_virtual)

        oldest_date = None
        for s in stocks:
            if s.quantity > 0 and s.weighted_entry_date:
                s_date = to_naive(s.weighted_entry_date)
                if oldest_date is None or s_date < oldest_date:
                    oldest_date = s_date

        age_days = days_between(current_time, oldest_date) if oldest_date else 0

        stock_details = []
        for s in stocks:
            if s.quantity > 0:
                reserved = s.reserved_qty if hasattr(s, 'reserved_qty') else 0
                stock_details.append({
                    "warehouse_id": s.warehouse_id,
                    "warehouse_name": s.warehouse.name,
                    "location_id": s.location_id,
                    "location_code": s.location.code if s.location else None,
                    "quantity": s.quantity,
                    "reserved_qty": reserved,
                    "available_qty": s.quantity - reserved,
                    "is_virtual": s.warehouse.is_virtual
                })

        item = {
            "id": p.id, "sku": p.sku, "name": p.name, "brand": p.brand,
            "category": p.category, "retail_price": float(p.retail_price),
            "unit": p.unit, "total_stock": total_qty, "age_days": age_days,
            "stocks": stock_details
        }
        if has_finance:
            item["cost_price"] = float(p.cost_price)
        result.append(item)

    return {"items": result, "total": total}


@router.get("/categories/list")
async def list_categories(user: User = Depends(get_current_user)):
    products = await Product.filter(is_active=True, category__isnull=False).distinct().values_list("category", flat=True)
    return list(set(p for p in products if p))


@router.get("/export")
async def export_products(user: User = Depends(require_permission("stock_view"))):
    try:
        import pandas as pd
    except ImportError:
        raise HTTPException(status_code=500, detail="pandas未安装")

    products = await Product.filter(is_active=True)
    has_finance = user.role == "admin" or "finance" in (user.permissions or [])

    # 批量查询库存（避免 N+1）
    product_ids = [p.id for p in products]
    all_stocks = await WarehouseStock.filter(product_id__in=product_ids, quantity__gt=0).select_related("warehouse") if product_ids else []
    stocks_by_product = {}
    for s in all_stocks:
        stocks_by_product.setdefault(s.product_id, []).append(s)

    data = []
    for p in products:
        stocks = stocks_by_product.get(p.id, [])
        total_qty = sum(s.quantity for s in stocks if not s.warehouse.is_virtual)
        row = {
            "SKU": p.sku, "名称": p.name, "品牌": p.brand or "",
            "分类": p.category or "", "单位": p.unit,
            "零售价": float(p.retail_price), "库存": total_qty
        }
        if has_finance:
            row["成本价"] = float(p.cost_price)
        data.append(row)

    df = pd.DataFrame(data)
    output = io.BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=products.xlsx"}
    )


@router.get("/template")
async def download_template(user: User = Depends(require_permission("stock_edit"))):
    try:
        import pandas as pd
    except ImportError:
        raise HTTPException(status_code=500, detail="pandas未安装")

    df = pd.DataFrame({
        "SKU": ["SKU001", "SKU002"],
        "名称": ["示例商品1", "示例商品2"],
        "品牌": ["品牌A", "品牌B"],
        "分类": ["分类1", "分类1"],
        "单位": ["个", "件"],
        "零售价": [99.00, 150.00],
        "成本价": [50.00, 80.00],
        "仓库": ["实体仓库", "实体仓库"],
        "仓位": ["A-01", "A-02"],
        "数量": [10, 20],
        "备注": ["批次1", "批次2"]
    })
    output = io.BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=import_template.xlsx"}
    )


_EXCEL_MIME_TYPES = {
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel',
    'application/octet-stream',
}


def _validate_excel_file(file: UploadFile, content: bytes):
    """验证上传文件是否为合法的 Excel 文件"""
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="请上传Excel文件")
    if file.content_type and file.content_type not in _EXCEL_MIME_TYPES:
        raise HTTPException(status_code=400, detail="文件类型不正确，请上传Excel文件")
    if len(content) >= 4 and content[:4] != b'PK\x03\x04' and content[:8] != b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
        raise HTTPException(status_code=400, detail="文件内容格式不正确，请上传Excel文件")


@router.post("/import/preview")
async def preview_import(file: UploadFile = File(...), user: User = Depends(require_permission("stock_edit"))):
    try:
        import pandas as pd
    except ImportError:
        raise HTTPException(status_code=500, detail="pandas未安装")

    content = await file.read()
    _validate_excel_file(file, content)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件过大，最大支持10MB")
    df = pd.read_excel(io.BytesIO(content))

    required_cols = ["SKU", "名称"]
    for col in required_cols:
        if col not in df.columns:
            raise HTTPException(status_code=400, detail=f"缺少必要列: {col}")

    # 预先批量查询（避免循环内单条查询）
    all_skus = set()
    all_warehouse_names = set()
    all_location_codes = {}  # {warehouse_name: set(codes)}
    for idx, row in df.iterrows():
        sku = str(row.get("SKU", "")).strip() if pd.notna(row.get("SKU")) else ""
        if sku:
            all_skus.add(sku)
        wh_name = str(row.get("仓库", "")).strip() if pd.notna(row.get("仓库")) else ""
        loc_code = str(row.get("仓位", "")).strip() if pd.notna(row.get("仓位")) else ""
        if wh_name:
            all_warehouse_names.add(wh_name)
            if loc_code:
                all_location_codes.setdefault(wh_name, set()).add(loc_code)

    existing_products = await Product.filter(sku__in=list(all_skus)) if all_skus else []
    product_map = {p.sku: p for p in existing_products}

    existing_warehouses = await Warehouse.filter(name__in=list(all_warehouse_names)) if all_warehouse_names else []
    warehouse_map = {w.name: w for w in existing_warehouses}

    # 批量查询仓位
    location_map = {}  # {(warehouse_id, code): location}
    for wh_name, codes in all_location_codes.items():
        wh = warehouse_map.get(wh_name)
        if wh:
            locations = await Location.filter(warehouse_id=wh.id, code__in=list(codes))
            for loc in locations:
                location_map[(wh.id, loc.code)] = loc

    # 批量查询库存
    stock_map = {}  # {(warehouse_id, product_id, location_id): stock}
    if existing_products and existing_warehouses:
        product_ids = [p.id for p in existing_products]
        warehouse_ids = [w.id for w in existing_warehouses]
        stocks = await WarehouseStock.filter(
            product_id__in=product_ids, warehouse_id__in=warehouse_ids
        )
        for s in stocks:
            stock_map[(s.warehouse_id, s.product_id, s.location_id)] = s

    preview_items = []

    for idx, row in df.iterrows():
        sku = str(row["SKU"]).strip() if pd.notna(row.get("SKU")) else ""
        if not sku:
            continue
        name = str(row.get("名称", "")) if pd.notna(row.get("名称")) else ""
        brand = str(row.get("品牌", "")) if pd.notna(row.get("品牌")) else ""
        category_val = str(row.get("分类", "")) if pd.notna(row.get("分类")) else ""
        warehouse_name = str(row.get("仓库", "")).strip() if pd.notna(row.get("仓库")) else ""
        location_code = str(row.get("仓位", "")).strip() if pd.notna(row.get("仓位")) else ""
        quantity = int(row.get("数量", 0)) if pd.notna(row.get("数量")) and row.get("数量", 0) > 0 else 0
        retail_price = float(row.get("零售价", 0)) if pd.notna(row.get("零售价")) else 0
        cost_price = float(row.get("成本价", 0)) if pd.notna(row.get("成本价")) else 0
        remark = str(row.get("备注", "")) if pd.notna(row.get("备注")) else ""

        status = "valid"
        status_msg = ""
        current_stock = 0
        after_stock = 0

        if not warehouse_name or quantity <= 0:
            status = "skip"
            status_msg = "缺少仓库或数量"
        elif not location_code:
            status = "skip"
            status_msg = "缺少仓位"
        else:
            existing = product_map.get(sku)
            if existing:
                status_msg = "更新商品"
                wh = warehouse_map.get(warehouse_name)
                loc = location_map.get((wh.id, location_code)) if wh else None
                if wh and loc:
                    existing_stock = stock_map.get((wh.id, existing.id, loc.id))
                    if existing_stock and existing_stock.quantity > 0:
                        current_stock = existing_stock.quantity
                        after_stock = current_stock + quantity
                        status_msg = f"叠加库存 ({current_stock}→{after_stock})"
                    else:
                        after_stock = quantity
                else:
                    after_stock = quantity
            else:
                status_msg = "新建商品"
                after_stock = quantity

            wh = warehouse_map.get(warehouse_name)
            if not wh:
                status_msg += "，新建仓库"
            if wh:
                loc = location_map.get((wh.id, location_code))
            else:
                loc = None
            if not loc:
                status_msg += "，新建仓位"

        preview_items.append({
            "row": idx + 2, "sku": sku, "name": name, "brand": brand,
            "category": category_val, "warehouse": warehouse_name,
            "location": location_code, "quantity": quantity,
            "current_stock": current_stock, "after_stock": after_stock,
            "retail_price": retail_price, "cost_price": cost_price,
            "remark": remark, "status": status, "status_msg": status_msg
        })

    valid_count = len([i for i in preview_items if i["status"] == "valid"])
    skip_count = len([i for i in preview_items if i["status"] == "skip"])

    return {"total": len(preview_items), "valid_count": valid_count,
            "skip_count": skip_count, "items": preview_items}


@router.post("/import")
async def import_products(file: UploadFile = File(...), user: User = Depends(require_permission("stock_edit"))):
    try:
        import pandas as pd
    except ImportError:
        raise HTTPException(status_code=500, detail="pandas未安装")

    content = await file.read()
    _validate_excel_file(file, content)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件过大，最大支持10MB")
    df = pd.read_excel(io.BytesIO(content))

    required_cols = ["SKU", "名称"]
    for col in required_cols:
        if col not in df.columns:
            raise HTTPException(status_code=400, detail=f"缺少必要列: {col}")

    # Phase 1: Validate all rows first (no DB writes)
    rows_to_process = []
    errors = []
    skipped = 0

    for idx, row in df.iterrows():
        try:
            sku = str(row["SKU"]).strip()
            if not sku:
                continue
            warehouse_name = str(row.get("仓库", "")).strip() if pd.notna(row.get("仓库")) else None
            quantity = int(row.get("数量", 0)) if pd.notna(row.get("数量")) and row.get("数量", 0) > 0 else 0

            if not warehouse_name or quantity <= 0:
                skipped += 1
                errors.append(f"第{idx+2}行: {sku} - 缺少仓库或数量，已跳过")
                continue

            data = {
                "name": str(row.get("名称", "")),
                "brand": str(row.get("品牌", "")) if pd.notna(row.get("品牌")) else None,
                "category": str(row.get("分类", "")) if pd.notna(row.get("分类")) else None,
                "unit": str(row.get("单位", "个")) if pd.notna(row.get("单位")) else "个",
                "retail_price": float(row.get("零售价", 0)) if pd.notna(row.get("零售价")) else 0,
                "cost_price": float(row.get("成本价", 0)) if pd.notna(row.get("成本价")) else 0
            }

            location_code = str(row.get("仓位", "")).strip() if pd.notna(row.get("仓位")) else None
            if not location_code:
                errors.append(f"第{idx+2}行: {sku} - 未指定仓位，跳过")
                skipped += 1
                continue

            remark_text = str(row.get("备注", "Excel批量导入")) if pd.notna(row.get("备注")) else "Excel批量导入"

            rows_to_process.append({
                "idx": idx, "sku": sku, "data": data,
                "warehouse_name": warehouse_name, "location_code": location_code,
                "quantity": quantity, "remark": remark_text
            })
        except Exception as e:
            errors.append(f"第{idx+2}行验证错误: {str(e)}")

    # Phase 2: Process validated rows with savepoint per row (允许单行失败不影响其他行)
    created, updated, stocked = 0, 0, 0

    if rows_to_process:
        from tortoise import connections
        conn = connections.get("default")
        async with transactions.in_transaction():
            for row_info in rows_to_process:
                # 使用 savepoint 隔离每行，单行失败可回滚而不影响整个事务
                try:
                    await conn.execute_query("SAVEPOINT row_sp")

                    sku = row_info["sku"]
                    data = row_info["data"]
                    warehouse_name = row_info["warehouse_name"]
                    location_code = row_info["location_code"]
                    quantity = row_info["quantity"]
                    remark_text = row_info["remark"]
                    idx = row_info["idx"]

                    existing = await Product.filter(sku=sku).first()
                    if existing:
                        await Product.filter(id=existing.id).update(**data)
                        product = existing
                        updated += 1
                    else:
                        product = await Product.create(sku=sku, **data)
                        created += 1

                    warehouse = await Warehouse.filter(name=warehouse_name).first()
                    if not warehouse:
                        warehouse = await Warehouse.create(name=warehouse_name, is_virtual=False, is_default=False, is_active=True)

                    location = await Location.filter(warehouse_id=warehouse.id, code=location_code).first()
                    if not location:
                        location = await Location.create(warehouse_id=warehouse.id, code=location_code, name=location_code, is_active=True)

                    import_cost = Decimal(str(data["cost_price"])) if data["cost_price"] > 0 else Decimal(str(float(product.cost_price or 0)))

                    stock = await WarehouseStock.filter(
                        warehouse_id=warehouse.id, product_id=product.id, location_id=location.id).first()

                    if stock:
                        old_qty = stock.quantity
                        old_cost = float(stock.weighted_cost or 0)
                        old_date = to_naive(stock.weighted_entry_date) or now()
                        new_qty = old_qty + quantity
                        new_cost = ((old_qty * old_cost) + (quantity * float(import_cost))) / new_qty if new_qty > 0 else float(import_cost)
                        old_days = days_between(now(), old_date) if old_date else 0
                        new_days = (old_qty * old_days + quantity * 0) / new_qty if new_qty > 0 else 0
                        new_entry_date = now() - timedelta(days=new_days)
                        await WarehouseStock.filter(id=stock.id).update(
                            quantity=new_qty,
                            weighted_cost=Decimal(str(round(new_cost, 2))),
                            weighted_entry_date=new_entry_date
                        )
                    else:
                        await WarehouseStock.create(
                            warehouse_id=warehouse.id, product_id=product.id,
                            location_id=location.id, quantity=quantity,
                            weighted_cost=import_cost, weighted_entry_date=now()
                        )

                    updated_stock = await WarehouseStock.filter(
                        warehouse_id=warehouse.id, product_id=product.id, location_id=location.id).first()
                    before_qty = (updated_stock.quantity - quantity) if updated_stock else 0
                    after_qty = updated_stock.quantity if updated_stock else quantity
                    await StockLog.create(
                        product_id=product.id, warehouse_id=warehouse.id,
                        change_type="RESTOCK", quantity=quantity,
                        before_qty=before_qty, after_qty=after_qty,
                        remark=f"仓位:{location.code}, {remark_text}", creator=user
                    )
                    stocked += 1
                    await conn.execute_query("RELEASE SAVEPOINT row_sp")
                except Exception as e:
                    await conn.execute_query("ROLLBACK TO SAVEPOINT row_sp")
                    errors.append(f"第{row_info['idx']+2}行错误: {str(e)}")

    msg_parts = []
    if created > 0: msg_parts.append(f"新建商品{created}条")
    if updated > 0: msg_parts.append(f"更新商品{updated}条")
    if stocked > 0: msg_parts.append(f"入库{stocked}条")
    if skipped > 0: msg_parts.append(f"跳过{skipped}条")

    result = {"message": f"导入完成: {', '.join(msg_parts) if msg_parts else '无数据处理'}"}
    if errors:
        result["errors"] = errors[:20]
        result["message"] += f"（共{len(errors)}条错误/警告）"
        result["total_errors"] = len(errors)
    return result


@router.get("/{product_id}")
async def get_product(product_id: int, user: User = Depends(get_current_user)):
    p = await Product.filter(id=product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="商品不存在")
    has_finance = user.role == "admin" or "finance" in (user.permissions or [])
    stocks = await WarehouseStock.filter(product_id=p.id, warehouse__is_virtual=False).select_related("warehouse")
    result = {
        "id": p.id, "sku": p.sku, "name": p.name, "brand": p.brand, "category": p.category,
        "retail_price": float(p.retail_price), "unit": p.unit,
        "stocks": [{"warehouse_id": s.warehouse_id, "warehouse_name": s.warehouse.name, "quantity": s.quantity} for s in stocks]
    }
    if has_finance:
        result["cost_price"] = float(p.cost_price)
    return result


@router.post("")
async def create_product(data: ProductCreate, user: User = Depends(require_permission("stock_edit"))):
    if await Product.filter(sku=data.sku).exists():
        raise HTTPException(status_code=400, detail="SKU已存在")
    p = await Product.create(**data.model_dump())
    return {"id": p.id, "message": "创建成功"}


@router.put("/{product_id}")
async def update_product(product_id: int, data: ProductUpdate, user: User = Depends(require_permission("stock_edit"))):
    p = await Product.filter(id=product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="商品不存在")
    update_data = data.model_dump(exclude_unset=True)
    if update_data:
        await Product.filter(id=product_id).update(**update_data)
    return {"message": "更新成功"}


@router.delete("/{product_id}")
async def delete_product(product_id: int, user: User = Depends(require_permission("stock_edit"))):
    p = await Product.filter(id=product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="商品不存在")
    p.is_active = False
    await p.save()
    return {"message": "删除成功"}

"""通用查询辅助函数"""
from fastapi import HTTPException
from tortoise.queryset import Q


async def paginated_query(model, filters=None, keyword=None, keyword_fields=None,
                          order_by="-created_at", offset=0, limit=200):
    """
    通用分页 + 关键词搜索查询。

    Args:
        model: Tortoise ORM 模型类
        filters: dict 或 Q 对象，基础过滤条件
        keyword: 搜索关键词（支持空格分隔多词 AND 匹配）
        keyword_fields: 关键词搜索的字段列表，如 ["name", "phone"]
        order_by: 排序字段，默认 "-created_at"
        offset: 偏移量
        limit: 每页条数（上限 1000）

    Returns:
        (items, total) 元组
    """
    offset = max(0, offset)
    limit = max(1, min(limit, 1000))

    if isinstance(filters, Q):
        query = model.filter(filters)
    elif filters:
        query = model.filter(**filters)
    else:
        query = model.all()

    if keyword and keyword_fields:
        for word in keyword.split():
            word_q = Q()
            for field in keyword_fields:
                word_q |= Q(**{f"{field}__icontains": word})
            query = query.filter(word_q)

    total = await query.count()
    items = await query.order_by(order_by).offset(offset).limit(limit)
    return items, total


async def get_or_404(model, entity_name="资源", **filters):
    """
    查询单条记录，不存在时抛出 404。

    Args:
        model: Tortoise ORM 模型类
        entity_name: 实体名称，用于错误消息
        **filters: 查询条件

    Returns:
        模型实例
    """
    obj = await model.filter(**filters).first()
    if not obj:
        raise HTTPException(status_code=404, detail=f"{entity_name}不存在")
    return obj


async def soft_delete(model, entity_name="资源", **filters):
    """
    软删除：查找记录并设置 is_active=False。

    Args:
        model: Tortoise ORM 模型类
        entity_name: 实体名称，用于错误消息
        **filters: 查询条件

    Returns:
        被软删除的模型实例
    """
    obj = await get_or_404(model, entity_name, **filters)
    obj.is_active = False
    await obj.save()
    return obj

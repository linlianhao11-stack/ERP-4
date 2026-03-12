"""AI 模块健康检查脚本 — python -m app.ai.health_check"""
from __future__ import annotations
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


async def main():
    from app.database import init_db, close_db
    from tortoise import connections

    print("=" * 50)
    print("ERP AI 模块健康检查")
    print("=" * 50)

    await init_db()
    conn = connections.get("default")
    errors = []

    # 1. 检查只读用户
    print("\n[1/4] 检查 AI 只读用户...")
    result = await conn.execute_query_dict("SELECT 1 FROM pg_roles WHERE rolname = 'erp_ai_readonly'")
    if result:
        print("  ✓ erp_ai_readonly 用户存在")
    else:
        errors.append("erp_ai_readonly 用户不存在")
        print("  ✗ erp_ai_readonly 用户不存在")

    # 2. 检查语义视图
    print("\n[2/4] 检查语义视图...")
    views = ["vw_sales_detail", "vw_sales_summary", "vw_purchase_detail",
             "vw_inventory_status", "vw_inventory_turnover", "vw_receivables", "vw_payables"]
    for v in views:
        try:
            await conn.execute_query(f"SELECT 1 FROM {v} LIMIT 0")
            print(f"  ✓ {v}")
        except Exception as e:
            errors.append(f"视图 {v} 异常: {e}")
            print(f"  ✗ {v}: {e}")

    # 3. 检查 API Key 配置
    print("\n[3/4] 检查 DeepSeek 配置...")
    from app.models import SystemSetting
    key_setting = await SystemSetting.filter(key="ai.deepseek.api_key").first()
    if key_setting and key_setting.value:
        print("  ✓ DeepSeek API Key 已配置")
    else:
        errors.append("DeepSeek API Key 未配置")
        print("  ✗ DeepSeek API Key 未配置")

    # 4. 检查 Few-shot 示例
    print("\n[4/4] 检查 Few-shot 示例...")
    shots_setting = await SystemSetting.filter(key="ai.few_shots").first()
    if shots_setting and shots_setting.value:
        import json
        shots = json.loads(shots_setting.value)
        print(f"  ✓ {len(shots)} 个示例")
        # 验证示例 SQL 是否可执行
        from app.ai.sql_validator import validate_sql
        for shot in shots:
            ok, _, reason = validate_sql(shot.get("sql", ""))
            if not ok:
                print(f"  ⚠ 示例 SQL 校验失败: {shot.get('question', '')[:30]}... — {reason}")
    else:
        print("  ○ 未配置自定义示例（使用默认）")

    await close_db()

    print("\n" + "=" * 50)
    if errors:
        print(f"发现 {len(errors)} 个问题:")
        for e in errors:
            print(f"  ✗ {e}")
    else:
        print("所有检查通过 ✓")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())

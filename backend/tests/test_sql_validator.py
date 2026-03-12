"""SQL 校验器测试 — 覆盖正常 SQL 和各类攻击向量"""
from __future__ import annotations
import pytest
from app.ai.sql_validator import validate_sql

# ===== 合法 SQL =====

class TestValidSQL:
    def test_simple_select(self):
        ok, sql, reason = validate_sql("SELECT * FROM vw_sales_detail")
        assert ok
        assert "LIMIT" in sql.upper()

    def test_select_with_where(self):
        ok, sql, _ = validate_sql(
            "SELECT customer_name, SUM(amount) FROM vw_sales_detail "
            "WHERE order_date >= '2024-01-01' GROUP BY customer_name"
        )
        assert ok

    def test_select_with_join(self):
        ok, sql, _ = validate_sql(
            "SELECT a.name, b.quantity FROM products a "
            "JOIN warehouse_stocks b ON a.id = b.product_id"
        )
        assert ok

    def test_select_with_subquery(self):
        ok, sql, _ = validate_sql(
            "SELECT * FROM vw_sales_detail WHERE customer_name IN "
            "(SELECT name FROM customers WHERE id > 5)"
        )
        assert ok

    def test_limit_preserved(self):
        ok, sql, _ = validate_sql("SELECT * FROM products LIMIT 50")
        assert ok
        assert "LIMIT 50" in sql.upper() or "LIMIT 50" in sql

    def test_limit_capped_at_1000(self):
        ok, sql, _ = validate_sql("SELECT * FROM products LIMIT 5000")
        assert ok
        assert "1000" in sql

    def test_auto_limit_added(self):
        ok, sql, _ = validate_sql("SELECT * FROM products")
        assert ok
        assert "LIMIT" in sql.upper()

    def test_count_query(self):
        ok, sql, _ = validate_sql("SELECT COUNT(*) FROM vw_sales_summary")
        assert ok

    def test_case_when(self):
        ok, sql, _ = validate_sql(
            "SELECT CASE WHEN amount > 1000 THEN 'high' ELSE 'low' END FROM vw_sales_detail"
        )
        assert ok

    def test_cte_query(self):
        ok, sql, _ = validate_sql(
            "WITH top_customers AS (SELECT customer_name, SUM(amount) AS total "
            "FROM vw_sales_detail GROUP BY customer_name ORDER BY total DESC LIMIT 10) "
            "SELECT * FROM top_customers"
        )
        assert ok

# ===== DML/DDL 攻击 =====

class TestDMLDDLAttacks:
    def test_insert(self):
        ok, _, reason = validate_sql("INSERT INTO users (username) VALUES ('hacker')")
        assert not ok
        assert reason

    def test_update(self):
        ok, _, reason = validate_sql("UPDATE users SET role = 'admin' WHERE id = 1")
        assert not ok

    def test_delete(self):
        ok, _, reason = validate_sql("DELETE FROM orders WHERE id > 0")
        assert not ok

    def test_drop_table(self):
        ok, _, reason = validate_sql("DROP TABLE users")
        assert not ok

    def test_alter_table(self):
        ok, _, reason = validate_sql("ALTER TABLE users ADD COLUMN hack TEXT")
        assert not ok

    def test_truncate(self):
        ok, _, reason = validate_sql("TRUNCATE TABLE orders")
        assert not ok

    def test_create_table(self):
        ok, _, reason = validate_sql("CREATE TABLE evil (id INT)")
        assert not ok

# ===== 注入攻击 =====

class TestInjectionAttacks:
    def test_semicolon_multi_statement(self):
        ok, _, reason = validate_sql(
            "SELECT 1; DROP TABLE users"
        )
        assert not ok

    def test_select_into(self):
        ok, _, reason = validate_sql(
            "SELECT * INTO new_table FROM products"
        )
        assert not ok

    def test_union_select_users(self):
        """UNION 访问敏感表"""
        ok, _, reason = validate_sql(
            "SELECT name FROM products UNION SELECT password_hash FROM users"
        )
        assert not ok

    def test_subquery_access_users(self):
        """子查询访问敏感表"""
        ok, _, reason = validate_sql(
            "SELECT * FROM products WHERE name IN (SELECT username FROM users)"
        )
        assert not ok

    def test_access_system_settings(self):
        ok, _, reason = validate_sql("SELECT * FROM system_settings")
        assert not ok

# ===== 边界情况 =====

class TestEdgeCases:
    def test_empty_string(self):
        ok, _, reason = validate_sql("")
        assert not ok

    def test_nonsense(self):
        ok, _, reason = validate_sql("this is not sql at all")
        assert not ok

    def test_comment_only(self):
        ok, _, reason = validate_sql("-- just a comment")
        assert not ok

    def test_whitespace_only(self):
        ok, _, reason = validate_sql("   \n\t  ")
        assert not ok

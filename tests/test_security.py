"""SQL 安全校验测试 — 验证 validate_sql() 的安全策略行为.

测试覆盖：
- 只读模式：仅 SELECT 允许
- 写模式：INSERT/UPDATE/DELETE 允许，但破坏性操作仍被禁止
- 多语句拒绝
- 危险函数拦截（LOAD_FILE、INTO OUTFILE、INTO DUMPFILE）
- 权限提升拦截（GRANT、REVOKE）
"""

import pytest


def test_select_allowed_in_readonly():
    """只读模式下 SELECT 查询应该通过校验."""
    from server import validate_sql
    result = validate_sql("SELECT * FROM users", allow_write=False)
    assert result == "SELECT * FROM users"


def test_select_with_where_allowed_in_readonly():
    """带 WHERE 子句的 SELECT 也应该通过."""
    from server import validate_sql
    result = validate_sql(
        "SELECT id, name FROM products WHERE price > 100", allow_write=False
    )
    assert result == "SELECT id, name FROM products WHERE price > 100"


def test_insert_blocked_in_readonly():
    """只读模式下 INSERT 应被拦截."""
    from server import validate_sql
    with pytest.raises(ValueError, match="只读模式"):
        validate_sql("INSERT INTO users (name) VALUES ('alice')", allow_write=False)


def test_update_blocked_in_readonly():
    """只读模式下 UPDATE 应被拦截."""
    from server import validate_sql
    with pytest.raises(ValueError, match="只读模式"):
        validate_sql("UPDATE users SET name = 'bob' WHERE id = 1", allow_write=False)


def test_delete_blocked_in_readonly():
    """只读模式下 DELETE 应被拦截."""
    from server import validate_sql
    with pytest.raises(ValueError, match="只读模式"):
        validate_sql("DELETE FROM users WHERE id = 1", allow_write=False)


def test_drop_blocked_in_readonly():
    """只读模式下 DROP 应被拦截."""
    from server import validate_sql
    with pytest.raises(ValueError, match="只读模式"):
        validate_sql("DROP TABLE users", allow_write=False)


def test_alter_blocked_in_readonly():
    """只读模式下 ALTER 应被拦截."""
    from server import validate_sql
    with pytest.raises(ValueError, match="只读模式"):
        validate_sql("ALTER TABLE users ADD COLUMN age INT", allow_write=False)


def test_create_blocked_in_readonly():
    """只读模式下 CREATE 应被拦截."""
    from server import validate_sql
    with pytest.raises(ValueError, match="只读模式"):
        validate_sql("CREATE TABLE test (id INT)", allow_write=False)


def test_truncate_blocked_in_readonly():
    """只读模式下 TRUNCATE 应被拦截."""
    from server import validate_sql
    with pytest.raises(ValueError, match="只读模式"):
        validate_sql("TRUNCATE TABLE users", allow_write=False)


def test_insert_allowed_in_write_mode():
    """写模式下 INSERT 应通过校验."""
    from server import validate_sql
    result = validate_sql(
        "INSERT INTO users (name) VALUES ('alice')", allow_write=True
    )
    assert result == "INSERT INTO users (name) VALUES ('alice')"


def test_update_allowed_in_write_mode():
    """写模式下 UPDATE 应通过校验."""
    from server import validate_sql
    result = validate_sql(
        "UPDATE users SET name = 'bob' WHERE id = 1", allow_write=True
    )
    assert result == "UPDATE users SET name = 'bob' WHERE id = 1"


def test_delete_allowed_in_write_mode():
    """写模式下 DELETE 应通过校验."""
    from server import validate_sql
    result = validate_sql(
        "DELETE FROM users WHERE id = 1", allow_write=True
    )
    assert result == "DELETE FROM users WHERE id = 1"


def test_multi_statement_blocked():
    """多语句查询（分号分隔）应始终被拒绝."""
    from server import validate_sql
    with pytest.raises(ValueError, match="多语句"):
        validate_sql("SELECT 1; DROP TABLE users", allow_write=False)


def test_multi_statement_blocked_in_write_mode():
    """写模式下多语句查询也应被拒绝."""
    from server import validate_sql
    with pytest.raises(ValueError, match="多语句"):
        validate_sql("INSERT INTO a (x) VALUES (1); DELETE FROM b", allow_write=True)


def test_load_file_blocked():
    """LOAD_FILE() 应在所有模式下被禁止 — 文件系统访问风险."""
    from server import validate_sql
    with pytest.raises(ValueError, match="危险"):
        validate_sql("SELECT LOAD_FILE('/etc/passwd')", allow_write=False)


def test_load_file_blocked_in_write_mode():
    """写模式下 LOAD_FILE() 也应被禁止."""
    from server import validate_sql
    with pytest.raises(ValueError, match="危险"):
        validate_sql("SELECT LOAD_FILE('/etc/passwd')", allow_write=True)


def test_into_outfile_blocked():
    """INTO OUTFILE 应在所有模式下被禁止 — 文件写入风险."""
    from server import validate_sql
    with pytest.raises(ValueError, match="危险"):
        validate_sql("SELECT * INTO OUTFILE '/tmp/data' FROM users", allow_write=False)


def test_into_outfile_blocked_in_write_mode():
    """写模式下 INTO OUTFILE 也应被禁止."""
    from server import validate_sql
    with pytest.raises(ValueError, match="危险"):
        validate_sql(
            "SELECT * INTO OUTFILE '/tmp/data' FROM users", allow_write=True
        )


def test_into_dumpfile_blocked():
    """INTO DUMPFILE 应在所有模式下被禁止."""
    from server import validate_sql
    with pytest.raises(ValueError, match="危险"):
        validate_sql("SELECT * INTO DUMPFILE '/tmp/data' FROM users", allow_write=True)


def test_drop_blocked_in_write_mode():
    """写模式下 DROP 仍应被禁止 — 破坏性结构操作."""
    from server import validate_sql
    with pytest.raises(ValueError, match="破坏性结构"):
        validate_sql("DROP TABLE users", allow_write=True)


def test_alter_blocked_in_write_mode():
    """写模式下 ALTER 仍应被禁止 — 结构变更风险."""
    from server import validate_sql
    with pytest.raises(ValueError, match="破坏性结构"):
        validate_sql("ALTER TABLE users ADD COLUMN age INT", allow_write=True)


def test_create_table_blocked_in_write_mode():
    """写模式下 CREATE TABLE 仍应被禁止 — 结构变更."""
    from server import validate_sql
    with pytest.raises(ValueError, match="破坏性结构"):
        validate_sql("CREATE TABLE test (id INT)", allow_write=True)


def test_grant_blocked():
    """GRANT 应在所有模式下被禁止 — 权限提升风险."""
    from server import validate_sql
    with pytest.raises(ValueError, match="破坏性结构"):
        validate_sql("GRANT ALL ON *.* TO 'hacker'@'%'", allow_write=True)


def test_revoke_blocked():
    """REVOKE 应在所有模式下被禁止 — 权限风险."""
    from server import validate_sql
    with pytest.raises(ValueError, match="破坏性结构"):
        validate_sql("REVOKE ALL ON *.* FROM 'admin'@'localhost'", allow_write=True)


def test_empty_sql_blocked():
    """空 SQL 应被拒绝."""
    from server import validate_sql
    with pytest.raises(ValueError, match="为空"):
        validate_sql("", allow_write=False)


def test_trailing_semicolon_allowed():
    """尾部分号应被允许（无害）."""
    from server import validate_sql
    result = validate_sql("SELECT 1;", allow_write=False)
    assert result == "SELECT 1;"

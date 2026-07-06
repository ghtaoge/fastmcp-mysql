"""MCP 工具函数测试 — 使用 mock 数据库连接验证工具行为.

这些测试验证 list_tables、describe_table、query 和 get_db_info 的行为，
无需真实 MySQL 连接。aiomysql 连接池被 mock 以返回可控的测试数据。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_pool():
    """Mock aiomysql 连接池，避免测试需要真实 MySQL 服务器.

    mock 池返回一个连接，其游标产生可预测的测试数据。
    """
    mock_cursor = AsyncMock()

    # 默认：fetchone 返回 None，fetchall 返回空列表
    mock_cursor.fetchone = AsyncMock(return_value=None)
    mock_cursor.fetchall = AsyncMock(return_value=[])
    mock_cursor.fetchmany = AsyncMock(return_value=[])
    mock_cursor.description = None

    # cursor() 返回异步上下文管理器
    mock_cursor_ctx_mgr = AsyncMock()
    mock_cursor_ctx_mgr.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor_ctx_mgr.__aexit__ = AsyncMock(return_value=False)

    mock_conn = AsyncMock()
    mock_conn.cursor = MagicMock(return_value=mock_cursor_ctx_mgr)

    # Pool.acquire() 返回异步上下文管理器
    mock_ctx_mgr = AsyncMock()
    mock_ctx_mgr.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_ctx_mgr.__aexit__ = AsyncMock(return_value=False)

    mock_pool_obj = MagicMock()
    mock_pool_obj.acquire = MagicMock(return_value=mock_ctx_mgr)
    mock_pool_obj.__aenter__ = AsyncMock(return_value=mock_pool_obj)
    mock_pool_obj.__aexit__ = AsyncMock(return_value=False)

    with patch("server._pool", mock_pool_obj):
        yield mock_pool_obj, mock_conn, mock_cursor


@pytest.mark.asyncio
async def test_list_tables(mock_pool):
    """list_tables 应返回格式化的表信息."""
    _, mock_conn, mock_cursor = mock_pool

    # 模拟 SHOW TABLE STATUS 结果
    mock_cursor.description = [
        ("Name", None), ("Rows", None), ("Comment", None),
    ]
    mock_cursor.fetchall = AsyncMock(
        return_value=[
            ("users", 150, "用户表"),
            ("orders", 2000, "订单表"),
        ]
    )

    from server import list_tables
    result = await list_tables()

    assert "users" in result
    assert "orders" in result


@pytest.mark.asyncio
async def test_list_tables_empty(mock_pool):
    """list_tables 在无表时应返回提示信息."""
    _, mock_conn, mock_cursor = mock_pool

    mock_cursor.description = [("Name", None)]
    mock_cursor.fetchall = AsyncMock(return_value=[])

    from server import list_tables
    result = await list_tables()

    assert "未找到" in result


@pytest.mark.asyncio
async def test_describe_table(mock_pool):
    """describe_table 应返回列和索引信息."""
    _, mock_conn, mock_cursor = mock_pool

    # 第一次调用：SHOW FULL COLUMNS
    # 第二次调用：SHOW INDEX
    columns_result = [
        ("id", "int", "NO", "PRI", None, "auto_increment", "主键"),
        ("name", "varchar(100)", "YES", "", None, "", "用户名"),
    ]
    index_result = [
        ("users", "PRIMARY", "id", "BTREE"),
    ]

    call_count = [0]
    desc_for_columns = [
        ("Field", None), ("Type", None), ("Null", None), ("Key", None),
        ("Default", None), ("Extra", None), ("Comment", None),
    ]
    desc_for_indexes = [
        ("Table", None), ("Key_name", None), ("Column_name", None), ("Index_type", None),
    ]

    async def fetchall_side_effect():
        call_count[0] += 1
        if call_count[0] == 1:
            mock_cursor.description = desc_for_columns
            return columns_result
        else:
            mock_cursor.description = desc_for_indexes
            return index_result

    mock_cursor.fetchall = AsyncMock(side_effect=fetchall_side_effect)

    from server import describe_table
    result = await describe_table("users")

    assert "id" in result
    assert "name" in result
    assert "varchar" in result


@pytest.mark.asyncio
async def test_query_select(mock_pool):
    """query 应执行 SELECT 并返回格式化结果."""
    _, mock_conn, mock_cursor = mock_pool

    mock_cursor.description = [("id", None), ("name", None)]
    mock_cursor.fetchmany = AsyncMock(
        return_value=[(1, "Alice"), (2, "Bob")]
    )
    mock_cursor.fetchone = AsyncMock(return_value=None)  # 无更多行

    from server import query
    result = await query("SELECT id, name FROM users LIMIT 10")

    assert "id" in result
    assert "name" in result
    assert "Alice" in result
    assert "Bob" in result


@pytest.mark.asyncio
async def test_query_truncation(mock_pool):
    """query 应在超出 limit 时显示截断提示."""
    _, mock_conn, mock_cursor = mock_pool

    mock_cursor.description = [("id", None)]
    # fetchmany 返回行，fetchone 返回一行表示有更多数据
    mock_cursor.fetchmany = AsyncMock(return_value=[(1,), (2,), (3,), (4,), (5,)])
    mock_cursor.fetchone = AsyncMock(return_value=(6,))

    from server import query
    result = await query("SELECT id FROM big_table", limit=5)

    # 应包含截断提示
    assert "截断" in result


@pytest.mark.asyncio
async def test_query_empty_result(mock_pool):
    """query 应优雅处理空结果集."""
    _, mock_conn, mock_cursor = mock_pool

    mock_cursor.description = [("id", None)]
    mock_cursor.fetchmany = AsyncMock(return_value=[])
    mock_cursor.fetchone = AsyncMock(return_value=None)

    from server import query
    result = await query("SELECT id FROM empty_table")

    assert "无数据" in result


@pytest.mark.asyncio
async def test_query_blocked_sql(mock_pool):
    """query 应拦截不安全的 SQL 并抛出错误."""
    from server import query
    with pytest.raises(ValueError, match="只读模式"):
        await query("DROP TABLE users")


@pytest.mark.asyncio
async def test_get_db_info(mock_pool):
    """get_db_info 应返回数据库元信息."""
    _, mock_conn, mock_cursor = mock_pool

    # 多次 fetchone/fetchall 调用模拟不同查询
    mock_cursor.fetchone = AsyncMock(
        side_effect=[
            ("8.0.32",),  # VERSION()
            ("test_db",),  # DATABASE()
        ]
    )
    mock_cursor.fetchall = AsyncMock(
        side_effect=[
            [("character_set_client", "utf8mb4")],  # 字符集变量
            [("users", 150), ("orders", 2000)],       # 表状态
        ]
    )

    from server import get_db_info
    result = await get_db_info()

    assert "8.0.32" in result
    assert "test_db" in result

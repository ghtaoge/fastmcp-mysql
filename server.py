"""FastMCP MySQL Server — 基于 MCP 协议的 MySQL 数据库访问服务.

本服务提供四个 MCP 工具，用于与 MySQL 数据库交互：
- list_tables: 列出当前数据库中的所有表
- describe_table: 查看指定表的详细结构（列、索引、注释）
- query: 执行 SQL 查询（默认只允许 SELECT，可配置开启写操作）
- get_db_info: 获取数据库元信息（版本、字符集、表数量等）

安全策略：
- 默认只读模式（仅允许 SELECT 查询）
- 可通过 MYSQL_ALLOW_WRITE=true 环境变量开启写操作
- SQL 注入防护：关键词拦截、多语句拒绝
- 危险操作（DROP、ALTER、GRANT、LOAD_FILE、INTO OUTFILE）始终被禁止
- 错误信息绝不泄露连接凭证（host、端口、密码）

使用方式：
- 通过环境变量配置 MySQL 连接信息（参见 .env.example）
- 以 stdio 模式运行：python server.py
- 集成到 Claude Code、Cursor、VS Code 等 MCP 客户端
"""

import os
import re
from typing import Any

import aiomysql
from dotenv import load_dotenv
from fastmcp import FastMCP

# 从 .env 文件加载环境变量（如果存在）
# 真实凭证只应存在于 .env 文件中，绝不在 .env.example 中
load_dotenv()

# ---------------------------------------------------------------------------
# 配置 — 所有值来自环境变量，零硬编码
# ---------------------------------------------------------------------------

MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER: str = os.getenv("MYSQL_USER", "")
MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "")
MYSQL_ALLOW_WRITE: bool = os.getenv("MYSQL_ALLOW_WRITE", "false").lower() in (
    "true",
    "1",
    "yes",
)

# ---------------------------------------------------------------------------
# SQL 安全校验 — query 工具的安全网关
# ---------------------------------------------------------------------------

# 始终被禁止的关键词 — 无论是否开启写模式，这些操作过于危险
# 涉及结构性变更或权限提升风险
BLOCKED_ALWAYS: set[str] = {
    "DROP",
    "ALTER",
    "CREATE",
    "GRANT",
    "REVOKE",
    "TRUNCATE",
    "RENAME",
}

# 只读模式下被禁止的关键词 — 数据修改操作
BLOCKED_READONLY: set[str] = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "REPLACE",
    "CALL",
    "LOAD",
}

# 始终被禁止的危险 SQL 函数/子句 — 文件系统访问风险
DANGEROUS_PATTERNS: list[str] = [
    r"\bLOAD_FILE\s*\(",      # 读取服务器文件
    r"\bINTO\s+OUTFILE\b",    # 写入服务器文件
    r"\bINTO\s+DUMPFILE\b",   # 写入服务器文件（二进制）
]


def validate_sql(sql: str, allow_write: bool) -> str:
    """校验 SQL 查询是否符合安全策略.

    本函数为 query 工具的安全网关：
    - 只读模式：仅允许 SELECT 查询
    - 写模式：允许 INSERT/UPDATE/DELETE，但 DROP/ALTER/CREATE/GRANT 仍然被禁止
    - 多语句查询（分号分隔）始终被禁止
    - 危险操作（LOAD_FILE、INTO OUTFILE、INTO DUMPFILE）始终被禁止

    Args:
        sql: 待校验的 SQL 查询字符串.
        allow_write: 是否允许写操作（INSERT/UPDATE/DELETE）.

    Returns:
        通过校验的 SQL 字符串（原样返回）.

    Raises:
        ValueError: SQL 违反安全策略时抛出，错误信息不暴露数据库凭证.
    """
    # 去除首尾空白，统一处理
    cleaned: str = sql.strip()

    # 拒绝空查询
    if not cleaned:
        raise ValueError("SQL 查询为空")

    # 拒绝多语句查询 — 防止注入隐藏的第二条命令
    # 示例攻击："SELECT 1; DROP TABLE users"
    # 尾部分号无害，去除后再检查
    if ";" in cleaned.rstrip(";"):
        raise ValueError(
            "出于安全原因，多语句查询不被允许（检测到分号分隔的多条语句）"
        )

    # 检查危险函数/子句 — 始终被禁止
    # 这些可以读取或写入 MySQL 服务器的文件系统
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cleaned, re.IGNORECASE):
            raise ValueError(
                "查询包含危险操作（涉及文件系统访问），该操作始终被禁止"
            )

    # 提取第一个关键词以确定 SQL 类型
    first_word: str = cleaned.split()[0].upper() if cleaned.split() else ""

    # 只读模式：仅允许 SELECT
    if not allow_write and first_word != "SELECT":
        if first_word in BLOCKED_READONLY or first_word in BLOCKED_ALWAYS:
            raise ValueError(
                f"'{first_word}' 操作在只读模式下不被允许。"
                "设置 MYSQL_ALLOW_WRITE=true 可开启写操作。"
            )
        # 未知关键词也在只读模式下被禁止
        raise ValueError(f"'{first_word}' 操作在只读模式下不被允许")

    # 写模式：仍然禁止破坏性结构/权限操作
    if allow_write and first_word in BLOCKED_ALWAYS:
        raise ValueError(
            f"'{first_word}' 是破坏性结构操作，始终被禁止"
        )

    return cleaned


# ---------------------------------------------------------------------------
# FastMCP 服务实例
# ---------------------------------------------------------------------------

mcp: FastMCP = FastMCP(
    "mysql",
    instructions=(
        "MySQL 数据库访问服务。"
        "使用 list_tables 查看可用表，describe_table 查看表结构，"
        "query 执行 SQL（默认仅 SELECT），get_db_info 获取数据库元信息。"
        "默认只允许 SELECT 查询 — 设置 MYSQL_ALLOW_WRITE 可开启写操作。"
    ),
)


# ---------------------------------------------------------------------------
# 数据库连接池管理
# ---------------------------------------------------------------------------

# 全局连接池 — 首次使用时创建，服务关闭时释放
# 使用懒初始化模式避免在导入时就连接数据库（环境变量可能尚未设置）
_pool: aiomysql.Pool | None = None


async def get_pool() -> aiomysql.Pool:
    """获取或创建 MySQL 连接池.

    使用懒初始化：首次调用时创建连接池，后续调用返回同一实例。
    连接参数仅来自环境变量 — 绝不硬编码。

    Returns:
        aiomysql 连接池实例.

    Raises:
        RuntimeError: 如果缺少必需的环境变量（MYSQL_USER、MYSQL_PASSWORD、
            MYSQL_DATABASE）。错误信息故意不暴露任何连接细节以确保安全。
    """
    global _pool
    if _pool is not None:
        return _pool

    # 在尝试连接之前验证必需配置
    # 这可以避免令人困惑的"连接被拒绝"错误
    missing: list[str] = []
    if not MYSQL_USER:
        missing.append("MYSQL_USER")
    if not MYSQL_PASSWORD:
        missing.append("MYSQL_PASSWORD")
    if not MYSQL_DATABASE:
        missing.append("MYSQL_DATABASE")
    if missing:
        raise RuntimeError(
            f"缺少必需的环境变量：{', '.join(missing)}。"
            "请检查 .env 文件或 MCP 客户端配置。"
        )

    _pool = await aiomysql.create_pool(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        db=MYSQL_DATABASE,
        minsize=1,         # 最小连接数
        maxsize=5,         # 最大连接数
        pool_recycle=1800, # 30 分钟后回收连接
        autocommit=True,   # 自动提交（不管理事务）
    )
    return _pool


async def close_pool() -> None:
    """优雅关闭 MySQL 连接池.

    在服务关闭时调用以释放所有数据库连接。
    安全处理连接池未初始化的情况。
    """
    global _pool
    if _pool is not None:
        _pool.close()
        await _pool.wait_closed()
        _pool = None


def _format_rows(description: tuple | None, rows: list[tuple]) -> str:
    """将查询结果格式化为可读的文本表格.

    Args:
        description: cursor.description 提供的列元数据（列名）.
        rows: 查询返回的行数据元组列表.

    Returns:
        包含列标题和行数据的格式化字符串，或表示无结果的提示信息.
    """
    if not description:
        return "查询已执行成功（无表格结果）"

    columns: list[str] = [col[0] for col in description]

    if not rows:
        return f"列：{', '.join(columns)}\n无数据行返回。"

    # 构建简单文本表格：标题行 + 数据行
    lines: list[str] = [f"列：{', '.join(columns)}"]
    lines.append("-" * 40)
    for row in rows:
        line: str = " | ".join(
            str(val) if val is not None else "NULL" for val in row
        )
        lines.append(line)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MCP 工具：list_tables — 列出数据库中的所有表
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
async def list_tables() -> str:
    """列出当前 MySQL 数据库中的所有表，包含行数估算和表注释.

    返回格式化的表名、估算行数和表注释列表。
    在运行具体查询之前，适合先使用此工具探索数据库结构。
    """
    pool: aiomysql.Pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SHOW TABLE STATUS")
            rows: list[tuple] = await cur.fetchall()
            description: tuple = cur.description

    if not rows:
        return "数据库中未找到任何表。"

    # SHOW TABLE STATUS 返回多列；我们提取 Name、Rows、Comment
    columns: list[str] = [col[0] for col in description]
    name_idx: int = columns.index("Name")
    rows_idx: int = columns.index("Rows")
    comment_idx: int = columns.index("Comment")

    lines: list[str] = ["数据库中的表："]
    lines.append("-" * 60)
    for row in rows:
        name: str = row[name_idx]
        row_count: Any = row[rows_idx]
        comment: str = row[comment_idx] or ""
        lines.append(f"  {name}  (~{row_count} 行)  {comment}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MCP 工具：describe_table — 查看表的详细结构
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
async def describe_table(table_name: str) -> str:
    """查看指定 MySQL 表的详细结构信息.

    返回列定义（名称、类型、是否可空、默认值、注释）和
    索引信息（名称、列、类型）。

    Args:
        table_name: 要查看的表名.
    """
    pool: aiomysql.Pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            # 获取列详情
            await cur.execute(f"SHOW FULL COLUMNS FROM `{table_name}`")
            columns: list[tuple] = await cur.fetchall()
            col_desc: tuple = cur.description

            # 获取索引详情
            await cur.execute(f"SHOW INDEX FROM `{table_name}`")
            indexes: list[tuple] = await cur.fetchall()
            idx_desc: tuple = cur.description

    # 格式化列信息
    col_names: list[str] = [c[0] for c in col_desc]
    field_idx: int = col_names.index("Field")
    type_idx: int = col_names.index("Type")
    null_idx: int = col_names.index("Null")
    key_idx: int = col_names.index("Key")
    default_idx: int = col_names.index("Default")
    extra_idx: int = col_names.index("Extra")
    comment_idx: int = (
        col_names.index("Comment") if "Comment" in col_names else -1
    )

    lines: list[str] = [f"表：{table_name}", "", "列："]
    for col in columns:
        line: str = (
            f"  {col[field_idx]} ({col[type_idx]}) "
            f"可空: {col[null_idx]} 键: {col[key_idx]} "
            f"默认: {col[default_idx]} 额外: {col[extra_idx]}"
        )
        if comment_idx >= 0 and col[comment_idx]:
            line += f" 注释: {col[comment_idx]}"
        lines.append(line)

    # 格式化索引信息
    if indexes:
        idx_names: list[str] = [i[0] for i in idx_desc]
        lines.extend(["", "索引："])
        for idx in indexes:
            idx_name: str = idx[idx_names.index("Key_name")]
            idx_col: str = idx[idx_names.index("Column_name")]
            idx_type: str = idx[idx_names.index("Index_type")]
            lines.append(f"  {idx_name} 列: {idx_col} 类型: ({idx_type})")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MCP 工具：query — 执行 SQL 查询（带安全校验）
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={"readOnlyHint": True},
)
async def query(sql: str, limit: int = 100) -> str:
    """在连接的 MySQL 数据库上执行 SQL 查询.

    默认仅允许 SELECT 查询。设置环境变量 MYSQL_ALLOW_WRITE=true
    可开启 INSERT、UPDATE、DELETE 操作。

    结果最多返回 `limit` 行，防止数据量过大导致 MCP 客户端卡顿。
    如有更多行可用，将附加截断提示。

    执行前会进行安全校验：
    - 只读模式：仅允许 SELECT
    - 多语句查询始终被禁止
    - 危险操作（DROP、ALTER、LOAD_FILE、INTO OUTFILE）始终被禁止

    Args:
        sql: 要执行的 SQL 查询.
        limit: 最多返回的行数（默认 100）.
    """
    # 执行前校验 SQL 安全性
    validated: str = validate_sql(sql, allow_write=MYSQL_ALLOW_WRITE)

    pool: aiomysql.Pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(validated)
            description: tuple | None = cur.description
            rows: list[tuple] = await cur.fetchmany(limit)

            # 检查是否有更多行超出 limit
            has_more: bool = False
            extra: tuple | None = await cur.fetchone()
            if extra:
                has_more = True

    result: str = _format_rows(description, rows)

    if has_more:
        result += (
            f"\n\n⚠ 结果已在 {limit} 行处截断。"
            "请减小 limit 参数或添加 WHERE 条件缩小查询范围。"
        )

    return result


# ---------------------------------------------------------------------------
# MCP 工具：get_db_info — 获取数据库元信息
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
async def get_db_info() -> str:
    """获取连接的 MySQL 数据库的元信息.

    返回：MySQL 版本、当前数据库名、字符集设置、
    表总数和估算总行数。
    """
    pool: aiomysql.Pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            # MySQL 版本
            await cur.execute("SELECT VERSION()")
            version_row: tuple | None = await cur.fetchone()

            # 当前数据库名
            await cur.execute("SELECT DATABASE()")
            db_name_row: tuple | None = await cur.fetchone()

            # 字符集设置
            await cur.execute(
                "SHOW VARIABLES WHERE Variable_name IN "
                "('character_set_client', 'character_set_connection', "
                "'character_set_database', 'character_set_results', "
                "'character_set_server')"
            )
            charset_rows: list[tuple] = await cur.fetchall()

            # 表数量和总行数估算
            await cur.execute("SHOW TABLE STATUS")
            table_rows: list[tuple] = await cur.fetchall()
            table_desc: tuple = cur.description

    # 格式化版本信息
    version: str = version_row[0] if version_row else "未知"
    db_name: str = db_name_row[0] if db_name_row else "未知"

    lines: list[str] = [
        f"MySQL 版本：{version}",
        f"当前数据库：{db_name}",
        "",
        "字符集设置：",
    ]

    # 格式化字符集信息
    for cs_row in charset_rows:
        lines.append(f"  {cs_row[0]}: {cs_row[1]}")

    # 格式化表统计
    if table_rows and table_desc:
        col_names: list[str] = [c[0] for c in table_desc]
        rows_idx: int = col_names.index("Rows")
        total_rows: int = sum(row[rows_idx] for row in table_rows)
        lines.append("")
        lines.append(f"表总数：{len(table_rows)}")
        lines.append(f"估算总行数：{total_rows}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 服务入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()  # 默认使用 STDIO 传输模式

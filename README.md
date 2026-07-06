# FastMCP MySQL

基于 [FastMCP](https://gofastmcp.com/) 构建的 MySQL [MCP（模型上下文协议）](https://modelcontextprotocol.io/) 服务。

**默认只读模式** — 仅允许 SELECT 查询。设置 `MYSQL_ALLOW_WRITE=true` 可开启 INSERT、UPDATE、DELETE 操作。危险操作（DROP、ALTER、LOAD_FILE、INTO OUTFILE）始终被禁止。

## 工具列表

| 工具 | 说明 |
|------|------|
| `list_tables` | 列出所有表名、行数估算和表注释 |
| `describe_table` | 查看表的列定义、类型、键、索引和注释 |
| `query` | 执行 SQL 查询（默认只允许 SELECT，可配置开启写操作） |
| `get_db_info` | 获取 MySQL 版本、字符集、表总数、行数估算 |

## 安装

```bash
git clone https://github.com/dongweitao/fastmcp-mysql.git
cd fastmcp-mysql
pip install -r requirements.txt
```

## 配置

所有配置通过环境变量传入 — **绝不硬编码密码**。

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `MYSQL_HOST` | MySQL 主机地址 | `localhost` |
| `MYSQL_PORT` | MySQL 端口 | `3306` |
| `MYSQL_USER` | 用户名 | *（必填）* |
| `MYSQL_PASSWORD` | 密码 | *（必填）* |
| `MYSQL_DATABASE` | 数据库名 | *（必填）* |
| `MYSQL_ALLOW_WRITE` | 是否允许写操作 | `false` |

创建 `.env` 文件（参考 `.env.example` 模板），或通过 MCP 客户端配置传入环境变量。

## MCP 客户端配置

### Claude Code

在 Claude Code 的 MCP 配置文件中添加：

```json
{
  "mcpServers": {
    "mysql": {
      "command": "python",
      "args": ["server.py"],
      "env": {
        "MYSQL_HOST": "localhost",
        "MYSQL_PORT": "3306",
        "MYSQL_USER": "your_user",
        "MYSQL_PASSWORD": "your_password",
        "MYSQL_DATABASE": "your_database"
      }
    }
  }
}
```

### Cursor

在 `~/.cursor/mcp.json` 中添加（同上格式，`args` 需填 server.py 的完整路径）：

```json
{
  "mcpServers": {
    "mysql": {
      "command": "python",
      "args": ["path/to/fastmcp-mysql/server.py"],
      "env": {
        "MYSQL_HOST": "localhost",
        "MYSQL_PORT": "3306",
        "MYSQL_USER": "your_user",
        "MYSQL_PASSWORD": "your_password",
        "MYSQL_DATABASE": "your_database"
      }
    }
  }
}
```

### VS Code（Claude 扩展）

在 VS Code 的 `settings.json` 中添加：

```json
{
  "claude.mcpServers": {
    "mysql": {
      "command": "python",
      "args": ["server.py"],
      "env": {
        "MYSQL_HOST": "localhost",
        "MYSQL_PORT": "3306",
        "MYSQL_USER": "your_user",
        "MYSQL_PASSWORD": "your_password",
        "MYSQL_DATABASE": "your_database"
      }
    }
  }
}
```

## 安全策略

- **默认只读**：仅 SELECT 查询通过验证
- **写模式**：设置 `MYSQL_ALLOW_WRITE=true` 后允许 INSERT/UPDATE/DELETE
- **始终禁止**：DROP、ALTER、CREATE、GRANT、TRUNCATE、LOAD_FILE、INTO OUTFILE、INTO DUMPFILE
- **多语句拒绝**：分号分隔的多条 SQL 始终被禁止
- **结果截断**：默认最多返回 100 行（可通过 `limit` 参数调整）
- **无凭证泄露**：错误信息绝不暴露主机、端口或密码

## 使用示例

配置完成后，向 AI 助手提问：

- *"数据库里有哪些表？"* → 调用 `list_tables`
- *"查看 users 表的结构"* → 调用 `describe_table`
- *"上个月有多少订单？"* → 调用 `query` 执行 SELECT
- *"MySQL 是什么版本？"* → 调用 `get_db_info`

## 常见问题

### Q: 连接失败怎么办？

检查以下环境变量是否正确配置：
- `MYSQL_USER`、`MYSQL_PASSWORD`、`MYSQL_DATABASE` 是否填写
- MySQL 服务是否正在运行
- 网络是否可达（防火墙/端口）

错误信息不会暴露具体连接参数，请自行核对 `.env` 文件或 MCP 客户端配置。

### Q: 如何开启写操作？

将 `MYSQL_ALLOW_WRITE` 设为 `true`、`1` 或 `yes`。**注意**：开启后 INSERT/UPDATE/DELETE 将被允许执行，请确保数据库用户拥有适当权限。DROP/ALTER/CREATE 等结构性操作仍然被禁止。

### Q: 为什么 DROP/ALTER 即使开启写模式也被禁止？

这些操作会导致不可逆的结构变更（删表、改表结构），风险远大于数据增删改。如需执行这些操作，请直接使用 MySQL 客户端工具。

### Q: 查询结果被截断怎么办？

`query` 工具的 `limit` 参数默认为 100。你可以：
- 调用时指定更小的 limit（如 `limit=20`）
- 在 SQL 中添加 WHERE 条件缩小结果范围
- 在 SQL 中使用 LIMIT 子句

## 运行测试

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

测试使用 mock 数据库连接，不需要真实 MySQL 服务。

## 许可证

MIT — 详见 [LICENSE](LICENSE)。

## 贡献指南

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

English documentation: [README.en.md](README.en.md)

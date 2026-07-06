# FastMCP MySQL

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for MySQL database access, built with [FastMCP](https://gofastmcp.com/).

**Read-only by default** — only SELECT queries are allowed. Set `MYSQL_ALLOW_WRITE=true` to enable INSERT, UPDATE, and DELETE operations. Dangerous operations (DROP, ALTER, LOAD_FILE, INTO OUTFILE) are always blocked.

## Tools

| Tool | Description |
|------|-------------|
| `list_tables` | List all tables with row counts and comments |
| `describe_table` | Show column types, keys, indexes, and comments for a table |
| `query` | Execute SQL queries (SELECT by default, write configurable) |
| `get_db_info` | Get MySQL version, charset, table count, and row estimates |

## Installation

```bash
git clone https://github.com/dongweitao/fastmcp-mysql.git
cd fastmcp-mysql
pip install -r requirements.txt
```

## Configuration

All settings are provided via environment variables — **never hardcode credentials**.

| Variable | Description | Default |
|----------|-------------|---------|
| `MYSQL_HOST` | MySQL server host | `localhost` |
| `MYSQL_PORT` | MySQL server port | `3306` |
| `MYSQL_USER` | MySQL username | *(required)* |
| `MYSQL_PASSWORD` | MySQL password | *(required)* |
| `MYSQL_DATABASE` | Database name | *(required)* |
| `MYSQL_ALLOW_WRITE` | Allow INSERT/UPDATE/DELETE | `false` |

Create a `.env` file (see `.env.example` for a template) or pass variables through your MCP client configuration.

## MCP Client Setup

### Claude Code

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

### Cursor (`~/.cursor/mcp.json`)

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

### VS Code (Claude Extension)

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

## Security

- **Read-only by default**: only SELECT queries pass validation
- **Write mode**: set `MYSQL_ALLOW_WRITE=true` for INSERT/UPDATE/DELETE
- **Always blocked**: DROP, ALTER, CREATE, GRANT, TRUNCATE, LOAD_FILE, INTO OUTFILE
- **Multi-statement rejection**: semicolon-separated queries are always blocked
- **Result truncation**: queries return at most 100 rows by default (configurable via `limit` parameter)
- **No credential leakage**: error messages never expose host, port, or password

## Usage Examples

- *"What tables are in the database?"* → calls `list_tables`
- *"Describe the users table"* → calls `describe_table`
- *"How many orders were placed last month?"* → calls `query`
- *"What version of MySQL is running?"* → calls `get_db_info`

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

Tests use mocked database connections — no real MySQL server required.

## License

MIT — see [LICENSE](LICENSE) for details.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

中文说明请参阅 [README.md](README.md)。

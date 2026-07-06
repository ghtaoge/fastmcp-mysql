# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-06

### Added

- 初始版本发布
- MCP 工具：`list_tables`、`describe_table`、`query`、`get_db_info`
- 默认只读模式，通过 `MYSQL_ALLOW_WRITE=true` 可配置开启写操作
- SQL 注入防护：关键词拦截、多语句拒绝、危险操作始终禁止
- 基于 aiomysql 的异步 MySQL 连接池
- 错误信息脱敏处理，绝不泄露连接凭证
- 中英文双 README 文档

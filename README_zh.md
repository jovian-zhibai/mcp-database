# mcp-database

[![PyPI](https://img.shields.io/pypi/v/mcp-database)](https://pypi.org/project/mcp-database/)
[![CI](https://github.com/jovian-zhibai/mcp-database/actions/workflows/ci.yml/badge.svg)](https://github.com/jovian-zhibai/mcp-database/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-compatible-orange)](https://modelcontextprotocol.io)

**多数据库 MCP 服务器 —— 让 Claude 直接查询、探索和管理你的 SQLite、PostgreSQL、MySQL 数据库。**

[English](README.md) | 中文

## 为什么需要 mcp-database？

| 你的问题 | mcp-database 的解决方案 |
|---------|----------------------|
| 想在 Claude Code 里直接查数据库 | 一个 MCP 服务器，支持多种数据库 |
| 现有的数据库 MCP 要么是 JS 要么是 Go | 纯 Python，基于官方 `mcp` SDK |
| 担心 Claude 误操作数据 | 默认只读模式，写入需要显式开启 |
| 不熟悉数据库结构 | 内置表结构探索、列信息、关键词搜索 |

## 快速开始

```bash
# 安装
pip install mcp-database

# 连接 SQLite 数据库
MCP_DATABASE_URL=sqlite:///path/to/your.db mcp-database
```

### 接入 Claude Code

```bash
# 一行命令接入
claude mcp add mcp-database -- mcp-database

# 指定数据库文件
claude mcp add mcp-database -e MCP_DATABASE_URL=sqlite:///path/to/db.sqlite -- mcp-database
```

### 接入 Claude Desktop

在 `claude_desktop_config.json` 中添加：

```json
{
  "mcpServers": {
    "database": {
      "command": "mcp-database",
      "env": {
        "MCP_DATABASE_URL": "sqlite:///path/to/your.db"
      }
    }
  }
}
```

## 支持的数据库

| 数据库 | 状态 | 安装方式 |
|--------|------|----------|
| **SQLite** | 内置 | `pip install mcp-database` |
| **PostgreSQL** | 可选 | `pip install 'mcp-database[postgres]'` |
| **MySQL** | 可选 | `pip install 'mcp-database[mysql]'` |
| **全部** | 可选 | `pip install 'mcp-database[all]'` |

## 配置方式

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `MCP_DATABASE_URL` | `sqlite:///:memory:` | 数据库连接地址 |
| `MCP_DATABASE_TYPE` | `sqlite` | 数据库类型：`sqlite`、`postgresql`、`mysql` |
| `MCP_DATABASE_READ_ONLY` | `true` | 是否启用只读模式 |
| `MCP_MAX_ROWS` | `100` | 单次查询最大返回行数 |
| `MCP_DATABASE_CONFIG` | — | 指向多连接 JSON 配置文件的路径 |

### 多数据库连接

要同时连接多个数据库，创建一个 JSON 配置文件：

```json
{
  "connections": {
    "prod": {"url": "postgres://user:pass@host:5432/db", "read_only": true},
    "staging": {"url": "postgres://user:pass@host:5432/staging", "read_only": true},
    "local": {"url": "sqlite:///dev.db", "read_only": false}
  },
  "settings": {
    "max_rows": 100,
    "allow_writes": false
  }
}
```

设置 `MCP_DATABASE_CONFIG` 环境变量指向此文件。所有工具都接受可选的 `connection_name` 参数（默认为 `"default"`）。

### 连接地址格式

```bash
# SQLite
MCP_DATABASE_URL=sqlite:///path/to/db.sqlite
MCP_DATABASE_URL=sqlite:///:memory:

# PostgreSQL
MCP_DATABASE_URL=postgres://user:password@localhost:5432/mydb
MCP_DATABASE_TYPE=postgresql

# MySQL
MCP_DATABASE_URL=mysql://user:password@localhost:3306/mydb
MCP_DATABASE_TYPE=mysql
```

## 可用工具

接入后，Claude 可以使用以下工具：

| 工具名 | 说明 |
|--------|------|
| `list_databases` | 列出所有已配置的数据库连接 |
| `list_tables` | 列出数据库中的所有表 |
| `get_table_info` | 获取表的详细信息（列名、类型、行数） |
| `get_schema` | 获取完整的数据库建表语句 |
| `query` | 执行只读 SQL 查询（SELECT、SHOW、DESCRIBE） |
| `execute` | 执行写入语句（INSERT、UPDATE、DELETE）—— 需手动开启 |
| `sample_rows` | 获取表中的示例数据 |
| `search_tables` | 按关键词搜索表名和列名 |
| `schema_diff` | 比较两个数据库连接之间的表结构差异 |
| `check_health` | 获取数据库健康指标（表数量、行数、延迟） |
| `generate_er_diagram` | 从数据库结构生成 Mermaid ER 图 |
| `explain_query` | 解释 SELECT 查询的执行计划 |

## 使用示例

你可以这样问 Claude：

- "我的数据库里有哪些表？"
- "看一下 users 表的结构"
- "查询金额最大的 10 笔订单"
- "找一下所有跟 email 相关的字段"
- "看看 products 表里长什么样"
- "比较 staging 和生产环境的表结构"
- "为我的数据库生成 ER 图"
- "我的表有多大？"

## 安全设计

- **默认只读** —— 查询操作不会修改任何数据
- **写入需授权** —— 必须设置 `allow_writes=True` 和 `MCP_DATABASE_READ_ONLY=false`
- **语句检测** —— 写入工具会拒绝 SELECT 语句（应该用 `query`）
- **行数限制** —— 可配置最大返回行数，防止意外拉取全表

## 开发

```bash
# 克隆仓库用于开发
git clone https://github.com/jovian-zhibai/mcp-database.git
cd mcp-database
pip install -e ".[dev]"

# 运行测试
pytest

# 使用 Inspector 调试
mcp dev src/mcp_database/server.py
```

## 项目结构

```
src/mcp_database/
  __init__.py          # 版本信息
  server.py            # MCP 服务器主入口（8 个工具）
  config.py            # 配置加载（环境变量、URL 解析）
  adapters/
    base.py            # 适配器基类（DatabaseAdapter）
    sqlite.py          # SQLite 适配器
    postgres.py        # PostgreSQL 适配器
    mysql.py           # MySQL 适配器
tests/
  test_sqlite_adapter.py  # SQLite 适配器测试（17 个用例）
```

## 许可证

MIT — 详见 [LICENSE](LICENSE)。

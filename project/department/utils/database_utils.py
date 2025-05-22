"""
SQLite数据库工具模块 - 基于AutoGen 0.5.6的数据库操作工具

本模块提供了SQLite数据库的基本操作功能，包括：
- 创建和管理数据库连接
- 创建和管理数据库表
- 执行SQL查询（SELECT、INSERT、UPDATE、DELETE等）
- 提供数据库元数据查询功能（表结构、索引等）
- 支持事务处理和错误恢复

所有功能都设计为兼容AutoGen 0.5.6的工具格式，可以直接用于智能体工具调用。
"""

import os
import json
import sqlite3
import datetime
import logging
import pathlib
from contextlib import closing
from typing import Dict, Any, Optional, List, Union, Tuple
from typing_extensions import Annotated

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 尝试导入AutoGen相关模块
try:
    from autogen_core.tools import FunctionTool
except ImportError:
    try:
        from autogen.agentchat.contrib.tools import FunctionTool
    except ImportError:
        logger.warning("未找到AutoGen模块，工具将无法作为FunctionTool使用")
        # 定义一个空的FunctionTool类，以便代码可以继续运行
        class FunctionTool:
            def __init__(self, func, **kwargs):
                self.func = func
                self.kwargs = kwargs

# =====================================================================
# 数据库配置和连接管理
# =====================================================================

# 默认数据库路径
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "database", "ai_company.db")

def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    获取SQLite数据库连接。

    参数:
        db_path: 数据库文件路径，如果为None则使用默认路径

    返回:
        sqlite3.Connection: 数据库连接对象
    """
    db_path = db_path or DEFAULT_DB_PATH

    # 确保数据库目录存在
    db_dir = os.path.dirname(db_path)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)

    # 创建连接
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # 使查询结果可以通过列名访问

    # 启用外键约束
    conn.execute("PRAGMA foreign_keys = ON")

    return conn

def create_tables_if_not_exist(db_path: Optional[str] = None, table_definitions: Optional[List[str]] = None) -> None:
    """
    创建数据库表（如果不存在）。

    参数:
        db_path: 数据库文件路径，如果为None则使用默认路径
        table_definitions: 表定义SQL语句列表，如果为None则不创建任何表
    """
    if not table_definitions:
        logger.info("未提供表定义，不创建任何表")
        return

    conn = get_db_connection(db_path)

    try:
        # 执行每个表定义语句
        for table_sql in table_definitions:
            conn.execute(table_sql)

        # 提交事务
        conn.commit()
        logger.info(f"成功创建 {len(table_definitions)} 个数据库表")

    except sqlite3.Error as e:
        logger.error(f"创建数据库表时出错: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

# =====================================================================
# 基本数据库操作函数
# =====================================================================

def execute_query(
    query: str,
    params: Optional[Union[Tuple, Dict[str, Any]]] = None,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    执行SQL查询并返回结果。

    参数:
        query: SQL查询语句
        params: 查询参数，可以是元组或字典
        db_path: 数据库文件路径，如果为None则使用默认路径

    返回:
        查询结果列表，每个元素是一个字典
    """
    conn = get_db_connection(db_path)
    results = []

    try:
        with closing(conn.cursor()) as cursor:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            # 如果是SELECT查询，获取结果
            if query.strip().upper().startswith("SELECT"):
                # 获取列名
                columns = [col[0] for col in cursor.description]

                # 将结果转换为字典列表
                for row in cursor.fetchall():
                    results.append(dict(zip(columns, row)))
            else:
                # 对于非SELECT查询，返回受影响的行数
                conn.commit()
                results = [{"affected_rows": cursor.rowcount}]

    except sqlite3.Error as e:
        logger.error(f"执行查询时出错: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

    return results

def execute_script(
    script: str,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    执行SQL脚本（多个SQL语句）。

    参数:
        script: SQL脚本，包含多个SQL语句
        db_path: 数据库文件路径，如果为None则使用默认路径

    返回:
        执行结果信息
    """
    conn = get_db_connection(db_path)

    try:
        conn.executescript(script)
        conn.commit()
        return {
            "status": "success",
            "message": "SQL脚本执行成功"
        }
    except sqlite3.Error as e:
        logger.error(f"执行SQL脚本时出错: {e}")
        conn.rollback()
        return {
            "status": "error",
            "message": f"SQL脚本执行失败: {str(e)}"
        }
    finally:
        conn.close()

# =====================================================================
# AutoGen工具函数 - 用于数据库操作的工具函数
# =====================================================================

def execute_sql(
    query: Annotated[str, "SQL查询语句，支持SELECT、INSERT、UPDATE、DELETE等"],
    params: Annotated[Optional[List[Any]], "查询参数，用于替换查询中的占位符"] = None,
    db_path: Annotated[Optional[str], "数据库文件路径，如果不提供则使用默认路径"] = None
) -> Dict[str, Any]:
    """
    执行SQL查询并返回结果。

    此工具支持所有类型的SQL查询，包括SELECT、INSERT、UPDATE、DELETE等。
    对于SELECT查询，返回查询结果；对于其他类型的查询，返回受影响的行数。

    参数:
        query: SQL查询语句
        params: 查询参数列表，用于替换查询中的占位符
        db_path: 数据库文件路径，如果不提供则使用默认路径

    返回:
        包含查询结果或执行状态的字典
    """
    try:
        # 将参数转换为元组（如果提供）
        params_tuple = tuple(params) if params else None

        # 执行查询
        results = execute_query(query, params_tuple, db_path)

        return {
            "status": "success",
            "timestamp": datetime.datetime.now().isoformat(),
            "query": query,
            "results": results
        }
    except Exception as e:
        logger.error(f"执行查询时出错: {e}")
        return {
            "status": "error",
            "timestamp": datetime.datetime.now().isoformat(),
            "query": query,
            "error": str(e)
        }

def execute_sql_script(
    script: Annotated[str, "SQL脚本，包含多个SQL语句"],
    db_path: Annotated[Optional[str], "数据库文件路径，如果不提供则使用默认路径"] = None
) -> Dict[str, Any]:
    """
    执行SQL脚本（多个SQL语句）。

    此工具允许执行包含多个SQL语句的脚本，适用于批量操作或复杂的数据库更新。

    参数:
        script: SQL脚本，包含多个SQL语句
        db_path: 数据库文件路径，如果不提供则使用默认路径

    返回:
        包含执行结果的字典
    """
    try:
        result = execute_script(script, db_path)

        return {
            "status": result["status"],
            "timestamp": datetime.datetime.now().isoformat(),
            "message": result["message"]
        }
    except Exception as e:
        logger.error(f"执行SQL脚本时出错: {e}")
        return {
            "status": "error",
            "timestamp": datetime.datetime.now().isoformat(),
            "error": str(e)
        }

def get_schema_info(
    db_path: Annotated[Optional[str], "数据库文件路径，如果不提供则使用默认路径"] = None
) -> Dict[str, Any]:
    """
    获取数据库架构信息，包括表、视图、索引等。

    此工具返回数据库中所有表的列表及其结构信息。

    参数:
        db_path: 数据库文件路径，如果不提供则使用默认路径

    返回:
        包含数据库架构信息的字典
    """
    try:
        # 查询sqlite_master表获取所有表
        tables_result = execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
            None,
            db_path
        )

        # 提取表名
        tables = [row["name"] for row in tables_result]

        # 获取每个表的结构信息
        schema_info = {}
        for table in tables:
            # 跳过SQLite内部表
            if table.startswith('sqlite_'):
                continue

            # 获取表结构
            columns_result = execute_query(f"PRAGMA table_info({table})", None, db_path)
            schema_info[table] = columns_result

        return {
            "status": "success",
            "timestamp": datetime.datetime.now().isoformat(),
            "tables": tables,
            "schema": schema_info
        }
    except Exception as e:
        logger.error(f"获取数据库架构信息时出错: {e}")
        return {
            "status": "error",
            "timestamp": datetime.datetime.now().isoformat(),
            "error": str(e)
        }

# =====================================================================
# 工具实例创建区域 - 在此处创建您的工具实例
# =====================================================================

# 创建工具实例
try:
    # SQL执行工具
    execute_sql_tool = FunctionTool(
        func=execute_sql,
        name="ExecuteSQL",
        description="执行SQL查询并返回结果，支持SELECT、INSERT、UPDATE、DELETE等"
    )

    # SQL脚本执行工具
    execute_sql_script_tool = FunctionTool(
        func=execute_sql_script,
        name="ExecuteSQLScript",
        description="执行包含多个SQL语句的脚本，适用于批量操作或复杂的数据库更新"
    )

    # 数据库架构信息工具
    get_schema_info_tool = FunctionTool(
        func=get_schema_info,
        name="GetSchemaInfo",
        description="获取数据库架构信息，包括表、视图、索引等"
    )

    logger.info("SQLite数据库工具创建成功")

    # 将所有工具实例添加到工具列表中
    tool_list = [
        execute_sql_tool,
        execute_sql_script_tool,
        get_schema_info_tool
    ]

except (AttributeError, TypeError, NameError) as e:
    logger.warning(f"创建工具实例时出错: {e}")
    tool_list = []

# =====================================================================
# 测试代码区域 - 用于直接测试工具功能
# =====================================================================

if __name__ == "__main__":
    print("\n=== SQLite数据库工具测试模式 ===")

    # 创建测试表
    print("\n1. 创建测试表:")
    test_table_sql = [
        '''
        CREATE TABLE IF NOT EXISTS test_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE,
            age INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    ]
    create_tables_if_not_exist(table_definitions=test_table_sql)

    # 测试插入数据
    print("\n2. 插入测试数据:")
    insert_sql = "INSERT INTO test_users (name, email, age) VALUES ('测试用户', 'test@example.com', 30)"
    test_result = execute_sql(insert_sql)
    print(json.dumps(test_result, indent=2, ensure_ascii=False))

    # 测试查询数据
    print("\n3. 查询测试数据:")
    select_sql = "SELECT * FROM test_users"
    test_result = execute_sql(select_sql)
    print(json.dumps(test_result, indent=2, ensure_ascii=False))

    # 测试获取数据库架构信息
    print("\n4. 获取数据库架构信息:")
    test_result = get_schema_info()
    print(json.dumps(test_result, indent=2, ensure_ascii=False))

    # 工具列表信息
    print("\n可用工具列表:")
    for i, tool in enumerate(tool_list, 1):
        if hasattr(tool, 'name') and hasattr(tool, 'description'):
            print(f"{i}. {tool.name}: {tool.description}")
        else:
            print(f"{i}. 未知工具: {tool}")

    print("\n=== 测试完成 ===")

# =====================================================================
# 导出区域 - 导出工具函数和工具列表
# =====================================================================

__all__ = [
    # 数据库连接和表管理
    "get_db_connection",
    "create_tables_if_not_exist",
    "execute_query",
    "execute_script",

    # 工具函数
    "execute_sql",
    "execute_sql_script",
    "get_schema_info",

    # 工具实例
    "execute_sql_tool",
    "execute_sql_script_tool",
    "get_schema_info_tool",

    # 工具列表
    "tool_list"
]
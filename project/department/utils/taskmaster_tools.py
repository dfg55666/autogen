"""
TaskMaster工具模块 - 基于AutoGen 0.5.6的任务管理工具

本模块提供了一组用于任务管理的工具，基于claude-task-master-main项目的功能，
但使用Python实现并与AutoGen 0.5.6集成。

主要功能:
- 初始化项目
- 解析PRD文档生成任务
- 列出所有任务
- 更新任务状态
- 生成任务文件
- 分析任务复杂度
- 管理任务依赖关系
"""

import os
import json
import re
import shutil
import time
from typing import Dict, Optional, List, Tuple
from typing_extensions import Annotated
import datetime

# 尝试导入AutoGen相关模块
try:
    from autogen_core.tools import FunctionTool
except ImportError:
    print("警告: 未找到AutoGen模块，工具将无法作为FunctionTool使用")
    # 定义一个空的FunctionTool类，以便代码可以继续运行
    class FunctionTool:
        def __init__(self, func, **kwargs):
            self.func = func
            self.kwargs = kwargs

# 默认配置
DEFAULT_CONFIG = {
    "models": {
        "main": {
            "provider": "anthropic",
            "modelId": "claude-3-7-sonnet-20250219",
            "maxTokens": 100000,
            "temperature": 0.2
        },
        "research": {
            "provider": "perplexity",
            "modelId": "sonar-pro",
            "maxTokens": 8700,
            "temperature": 0.1
        },
        "fallback": {
            "provider": "anthropic",
            "modelId": "claude-3-7-sonnet-20250219",
            "maxTokens": 120000,
            "temperature": 0.2
        }
    },
    "global": {
        "logLevel": "info",
        "debug": False,
        "defaultSubtasks": 5,
        "defaultPriority": "medium",
        "projectName": "Taskmaster",
    },
    "team": {
        "members": [],
        "groups": [],
        "roles": {
            "admin": {
                "description": "管理员，可以执行所有操作",
                "permissions": ["read", "write", "delete", "assign"]
            },
            "manager": {
                "description": "项目经理，可以分配任务和更改状态",
                "permissions": ["read", "write", "assign"]
            },
            "developer": {
                "description": "开发人员，可以更新自己的任务",
                "permissions": ["read", "write_own"]
            },
            "viewer": {
                "description": "查看者，只能查看任务",
                "permissions": ["read"]
            }
        }
    }
}

# 默认任务模板
DEFAULT_TEMPLATES = {
    "default": {
        "title": "新任务",
        "description": "任务描述",
        "status": "pending",
        "priority": "medium",
        "dependencies": [],
        "subtasks": [],
        "tags": []
    },
    "feature": {
        "title": "实现新功能",
        "description": "实现新的功能模块",
        "status": "pending",
        "priority": "medium",
        "dependencies": [],
        "subtasks": [
            {
                "title": "需求分析",
                "description": "分析功能需求",
                "status": "pending"
            },
            {
                "title": "设计方案",
                "description": "设计功能实现方案",
                "status": "pending"
            },
            {
                "title": "编写代码",
                "description": "实现功能代码",
                "status": "pending"
            },
            {
                "title": "编写测试",
                "description": "编写单元测试",
                "status": "pending"
            },
            {
                "title": "文档编写",
                "description": "编写功能文档",
                "status": "pending"
            }
        ],
        "tags": ["feature"]
    },
    "bug": {
        "title": "修复Bug",
        "description": "修复系统Bug",
        "status": "pending",
        "priority": "high",
        "dependencies": [],
        "subtasks": [
            {
                "title": "复现问题",
                "description": "复现并确认Bug",
                "status": "pending"
            },
            {
                "title": "分析原因",
                "description": "分析Bug产生的原因",
                "status": "pending"
            },
            {
                "title": "修复Bug",
                "description": "编写修复代码",
                "status": "pending"
            },
            {
                "title": "编写测试",
                "description": "编写测试确保Bug不再出现",
                "status": "pending"
            }
        ],
        "tags": ["bug"]
    },
    "refactor": {
        "title": "重构代码",
        "description": "重构现有代码",
        "status": "pending",
        "priority": "medium",
        "dependencies": [],
        "subtasks": [
            {
                "title": "分析现有代码",
                "description": "分析现有代码的问题",
                "status": "pending"
            },
            {
                "title": "设计重构方案",
                "description": "设计代码重构方案",
                "status": "pending"
            },
            {
                "title": "实施重构",
                "description": "实施代码重构",
                "status": "pending"
            },
            {
                "title": "验证功能",
                "description": "验证重构后的功能正常",
                "status": "pending"
            }
        ],
        "tags": ["refactor"]
    },
    "docs": {
        "title": "编写文档",
        "description": "编写项目文档",
        "status": "pending",
        "priority": "low",
        "dependencies": [],
        "subtasks": [
            {
                "title": "收集信息",
                "description": "收集需要记录的信息",
                "status": "pending"
            },
            {
                "title": "编写文档",
                "description": "编写文档内容",
                "status": "pending"
            },
            {
                "title": "审核文档",
                "description": "审核文档内容",
                "status": "pending"
            }
        ],
        "tags": ["documentation"]
    }
}

# 任务状态常量
TASK_STATUS = ["pending", "in_progress", "done", "deferred"]

# 任务优先级常量
TASK_PRIORITY = ["high", "medium", "low"]

# 工具函数

def find_tasks_json_path(project_root: Optional[str] = None) -> str:
    """
    查找tasks.json文件的路径

    Args:
        project_root: 项目根目录，如果为None则使用当前目录

    Returns:
        tasks.json文件的绝对路径

    Raises:
        FileNotFoundError: 如果找不到tasks.json文件
    """
    if project_root is None:
        project_root = os.getcwd()

    # 首先检查直接路径
    direct_path = os.path.join(project_root, "tasks.json")
    if os.path.isfile(direct_path):
        return os.path.abspath(direct_path)

    # 然后检查.taskmaster目录
    taskmaster_path = os.path.join(project_root, ".taskmaster", "tasks.json")
    if os.path.isfile(taskmaster_path):
        return os.path.abspath(taskmaster_path)

    raise FileNotFoundError(f"无法在{project_root}或其.taskmaster子目录中找到tasks.json文件")

def load_tasks(tasks_path: str) -> Dict:
    """
    加载tasks.json文件

    Args:
        tasks_path: tasks.json文件的路径

    Returns:
        任务数据字典
    """
    try:
        with open(tasks_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 使用安全的JSON解析
        success, result, error = safe_json_loads(content)
        if success:
            # 验证基本结构
            if "tasks" not in result:
                result["tasks"] = []
            if "metadata" not in result:
                result["metadata"] = {"created": datetime.datetime.now().isoformat()}
            return result
        else:
            print(f"警告: JSON解析错误 - {error}")
            # 记录错误
            log_json_error(tasks_path, error, content)

            # 尝试修复并重新解析
            print("尝试修复JSON格式...")
            cleaned_content = clean_json_string(content)
            try:
                result = json.loads(cleaned_content)
                # 验证基本结构
                if "tasks" not in result:
                    result["tasks"] = []
                if "metadata" not in result:
                    result["metadata"] = {"created": datetime.datetime.now().isoformat()}
                return result
            except Exception as e:
                # 如果仍然失败，返回空的任务数据结构
                print(f"修复失败: {str(e)}，返回空任务数据")
                return {"tasks": [], "metadata": {"created": datetime.datetime.now().isoformat()}}
    except json.JSONDecodeError as e:
        # 记录错误
        log_json_error(tasks_path, str(e))
        # 如果文件为空或格式不正确，返回空的任务数据结构
        return {"tasks": [], "metadata": {"created": datetime.datetime.now().isoformat()}}
    except FileNotFoundError:
        raise FileNotFoundError(f"找不到任务文件: {tasks_path}")
    except Exception as e:
        # 捕获其他可能的异常
        print(f"加载任务时出错: {str(e)}")
        return {"tasks": [], "metadata": {"created": datetime.datetime.now().isoformat()}}

def save_tasks(tasks_data: Dict, tasks_path: str) -> None:
    """
    保存任务数据到tasks.json文件

    Args:
        tasks_data: 任务数据字典
        tasks_path: 保存路径
    """
    # 确保目录存在
    os.makedirs(os.path.dirname(tasks_path), exist_ok=True)

    with open(tasks_path, 'w', encoding='utf-8') as f:
        json.dump(tasks_data, f, indent=2, ensure_ascii=False)

# 核心功能函数

def list_templates(
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    列出所有可用的任务模板

    显示系统预定义的模板和用户自定义的模板
    """
    if project_root is None:
        project_root = os.getcwd()

    # 获取系统预定义模板
    system_templates = DEFAULT_TEMPLATES.keys()

    # 获取用户自定义模板
    user_templates = []
    templates_path = os.path.join(project_root, ".taskmaster", "templates.json")
    if os.path.isfile(templates_path):
        try:
            with open(templates_path, 'r', encoding='utf-8') as f:
                user_templates_data = json.load(f)
                user_templates = user_templates_data.keys()
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    # 生成报告
    report = ["可用的任务模板:"]

    # 系统预定义模板
    report.append("\n系统预定义模板:")
    for template_name in system_templates:
        template = DEFAULT_TEMPLATES[template_name]
        subtasks_count = len(template.get("subtasks", []))
        tags = ", ".join(template.get("tags", [])) or "无"
        report.append(f"  - {template_name}: {template['title']} (优先级: {template['priority']}, 子任务: {subtasks_count}, 标签: {tags})")

    # 用户自定义模板
    if user_templates:
        report.append("\n用户自定义模板:")
        try:
            with open(templates_path, 'r', encoding='utf-8') as f:
                user_templates_data = json.load(f)
                for template_name in user_templates:
                    template = user_templates_data[template_name]
                    subtasks_count = len(template.get("subtasks", []))
                    tags = ", ".join(template.get("tags", [])) or "无"
                    report.append(f"  - {template_name}: {template['title']} (优先级: {template['priority']}, 子任务: {subtasks_count}, 标签: {tags})")
        except (json.JSONDecodeError, FileNotFoundError):
            report.append("  无法读取用户自定义模板")
    else:
        report.append("\n没有用户自定义模板")

    return "\n".join(report)

def get_template(
    template_name: Annotated[str, "模板名称"],
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> Dict:
    """
    获取指定名称的任务模板

    如果找不到指定模板，返回默认模板
    """
    if project_root is None:
        project_root = os.getcwd()

    # 首先检查系统预定义模板
    if template_name in DEFAULT_TEMPLATES:
        return DEFAULT_TEMPLATES[template_name].copy()

    # 然后检查用户自定义模板
    templates_path = os.path.join(project_root, ".taskmaster", "templates.json")
    if os.path.isfile(templates_path):
        try:
            with open(templates_path, 'r', encoding='utf-8') as f:
                user_templates = json.load(f)
                if template_name in user_templates:
                    return user_templates[template_name].copy()
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    # 如果找不到指定模板，返回默认模板
    return DEFAULT_TEMPLATES["default"].copy()

def save_template(
    template_name: Annotated[str, "模板名称"],
    template_data: Annotated[Dict, "模板数据"],
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    保存用户自定义模板

    如果模板已存在，则覆盖
    """
    if project_root is None:
        project_root = os.getcwd()

    # 检查模板名称是否为系统预定义模板
    if template_name in DEFAULT_TEMPLATES:
        return f"错误: 不能覆盖系统预定义模板 '{template_name}'"

    # 确保模板数据包含必要的字段
    required_fields = ["title", "description", "status", "priority"]
    for field in required_fields:
        if field not in template_data:
            return f"错误: 模板数据缺少必要字段 '{field}'"

    # 确保目录存在
    templates_dir = os.path.join(project_root, ".taskmaster")
    os.makedirs(templates_dir, exist_ok=True)

    # 读取现有模板
    templates_path = os.path.join(templates_dir, "templates.json")
    templates = {}
    if os.path.isfile(templates_path):
        try:
            with open(templates_path, 'r', encoding='utf-8') as f:
                templates = json.load(f)
        except json.JSONDecodeError:
            pass

    # 添加或更新模板
    templates[template_name] = template_data

    # 保存模板
    with open(templates_path, 'w', encoding='utf-8') as f:
        json.dump(templates, f, indent=2, ensure_ascii=False)

    return f"模板 '{template_name}' 已保存"

def delete_template(
    template_name: Annotated[str, "模板名称"],
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    删除用户自定义模板

    不能删除系统预定义模板
    """
    if project_root is None:
        project_root = os.getcwd()

    # 检查模板名称是否为系统预定义模板
    if template_name in DEFAULT_TEMPLATES:
        return f"错误: 不能删除系统预定义模板 '{template_name}'"

    # 读取现有模板
    templates_path = os.path.join(project_root, ".taskmaster", "templates.json")
    if not os.path.isfile(templates_path):
        return f"错误: 找不到用户自定义模板 '{template_name}'"

    try:
        with open(templates_path, 'r', encoding='utf-8') as f:
            templates = json.load(f)
    except json.JSONDecodeError:
        return f"错误: 无法读取模板文件"

    # 检查模板是否存在
    if template_name not in templates:
        return f"错误: 找不到用户自定义模板 '{template_name}'"

    # 删除模板
    del templates[template_name]

    # 保存模板
    with open(templates_path, 'w', encoding='utf-8') as f:
        json.dump(templates, f, indent=2, ensure_ascii=False)

    return f"模板 '{template_name}' 已删除"

def add_task(
    title: Annotated[str, "任务标题"],
    description: Annotated[str, "任务描述"],
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None,
    dependencies: Annotated[List[str], "依赖任务ID列表"] = None,
    priority: Annotated[str, "任务优先级 (high, medium, low)"] = None,
    template: Annotated[str, "使用的模板名称"] = "default",
    tags: Annotated[List[str], "任务标签列表"] = None,
    status: Annotated[str, "任务状态 (pending, in_progress, done, deferred)"] = "pending"
) -> str:
    """
    添加新任务

    根据提供的信息创建新任务，可以指定使用的模板
    """
    if project_root is None:
        project_root = os.getcwd()

    # 验证优先级
    if priority is not None and priority not in TASK_PRIORITY:
        return f"错误: 无效的优先级 '{priority}'。有效优先级: {', '.join(TASK_PRIORITY)}"

    # 验证状态
    if status not in TASK_STATUS:
        return f"错误: 无效的状态 '{status}'。有效状态: {', '.join(TASK_STATUS)}"

    # 获取模板
    template_data = get_template(template, project_root)

    try:
        tasks_path = find_tasks_json_path(project_root)
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError as e:
        return f"错误: {str(e)}"

    # 验证依赖
    if dependencies is None:
        dependencies = []

    tasks = tasks_data.get("tasks", [])
    task_ids = [task.get("id") for task in tasks]

    invalid_deps = [dep_id for dep_id in dependencies if dep_id not in task_ids]
    if invalid_deps:
        return f"错误: 以下依赖任务不存在: {', '.join(invalid_deps)}"

    # 生成新任务ID
    new_task_id = f"task_{len(tasks) + 1:03d}"

    # 创建新任务
    new_task = {
        "id": new_task_id,
        "title": title,
        "description": description,
        "status": status,
        "priority": priority if priority is not None else template_data.get("priority", "medium"),
        "dependencies": dependencies,
        "subtasks": [],
        "tags": tags if tags is not None else template_data.get("tags", [])
    }

    # 如果模板中有子任务，添加到新任务中
    if "subtasks" in template_data and template_data["subtasks"]:
        for i, subtask_template in enumerate(template_data["subtasks"]):
            subtask_id = f"{new_task_id}_sub_{i + 1:03d}"
            subtask = {
                "id": subtask_id,
                "title": subtask_template.get("title", ""),
                "description": subtask_template.get("description", ""),
                "status": "pending"
            }
            new_task["subtasks"].append(subtask)

    # 添加新任务
    tasks_data["tasks"].append(new_task)

    # 保存更新后的任务
    save_tasks(tasks_data, tasks_path)

    # 生成报告
    subtasks_count = len(new_task.get("subtasks", []))
    if subtasks_count > 0:
        return f"已添加新任务 '{new_task_id}'，标题为 '{title}'，包含 {subtasks_count} 个子任务"
    else:
        return f"已添加新任务 '{new_task_id}'，标题为 '{title}'"

def add_team_member(
    username: Annotated[str, "用户名"],
    role: Annotated[str, "角色名称，例如：产品经理、开发工程师、UI设计师、测试工程师等，支持自定义"],
    description: Annotated[str, "成员描述"] = "",
    group_id: Annotated[str, "所属组ID，如果不指定则不分配到组"] = None,
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    添加团队成员

    向项目添加新的团队成员，并分配角色、描述和通讯地址
    每个成员至少有一个个人专属的通讯文件，如果分配到组中，还会有组群聊通讯文件
    """
    if project_root is None:
        project_root = os.getcwd()

    # 读取配置文件
    config_path = os.path.join(project_root, ".taskmasterconfig")
    if not os.path.isfile(config_path):
        return f"错误: 找不到配置文件。请先初始化项目。"

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError:
        return f"错误: 无法解析配置文件。"

    # 确保配置中有team字段
    if "team" not in config:
        config["team"] = {
            "members": [],
            "groups": [],
            "roles": DEFAULT_CONFIG["team"]["roles"]
        }

    # 检查用户是否已存在
    for member in config["team"].get("members", []):
        if member.get("username") == username:
            return f"错误: 用户 '{username}' 已存在。"

    # 创建个人消息目录
    personal_chat_dir = os.path.join(project_root, "ProjectTask", "GroupChat", "Personal")
    os.makedirs(personal_chat_dir, exist_ok=True)

    # 设置个人消息文件路径
    personal_message_file = os.path.join("ProjectTask", "GroupChat", "Personal", f"{username}.txt")

    # 创建个人消息文件
    with open(os.path.join(project_root, personal_message_file), 'w', encoding='utf-8') as f:
        f.write(f"# {username} 的个人通讯文件\n创建时间: {datetime.datetime.now().isoformat()}\n\n")

    # 初始化通讯地址列表
    communication_files = [
        {
            "type": "personal",
            "file_path": personal_message_file,
            "description": "个人专属通讯文件"
        }
    ]

    # 如果指定了组ID，检查组是否存在并添加到组中
    is_group_leader = False
    parent_group_id = None

    if group_id:
        group_found = False
        group_name = ""

        for group in config["team"].get("groups", []):
            if group.get("id") == group_id:
                group_found = True
                group_name = group.get("name", "")

                # 检查该组是否已有组长
                if "leader" in group and group["leader"]:
                    # 如果组已有组长，则新成员为普通成员
                    if "members" not in group:
                        group["members"] = []
                    group["members"].append(username)
                else:
                    # 如果组没有组长，则新成员为组长
                    group["leader"] = username
                    if "members" not in group:
                        group["members"] = []
                    group["members"].append(username)
                    is_group_leader = True

                # 获取父组ID
                parent_group_id = group.get("parent_id")

                # 获取组的群聊文件路径
                group_chat_file = None
                for g in config["team"].get("groups", []):
                    if g.get("id") == group_id:
                        group_chat_file = g.get("chat_file")
                        break

                if not group_chat_file:
                    # 如果找不到群聊文件，创建一个新的
                    # 构建完整的组路径名称
                    full_path = group_name
                    parent_id = group.get("parent_id")

                    # 递归查找父组路径
                    while parent_id:
                        for g in config["team"].get("groups", []):
                            if g.get("id") == parent_id:
                                parent_name = g.get("name", "")
                                full_path = f"{parent_name}-{full_path}"
                                parent_id = g.get("parent_id")
                                break
                        else:
                            parent_id = None

                    # 创建群组目录和群聊文件
                    groups_dir = os.path.join(project_root, "ProjectTask", "GroupChat", "Groups")

                    # 将路径名称转换为文件系统路径
                    group_path_parts = full_path.split("-")
                    current_path = groups_dir

                    # 创建层级目录结构
                    for i, part in enumerate(group_path_parts):
                        current_path = os.path.join(current_path, part)
                        os.makedirs(current_path, exist_ok=True)

                    # 创建群聊文件
                    group_chat_file = os.path.join("ProjectTask", "GroupChat", "Groups", *group_path_parts, "group_chat.txt")
                    full_group_chat_path = os.path.join(project_root, group_chat_file)

                    if not os.path.exists(full_group_chat_path):
                        with open(full_group_chat_path, 'w', encoding='utf-8') as f:
                            f.write(f"# {full_path} 群聊\n创建时间: {datetime.datetime.now().isoformat()}\n\n")

                    # 更新组的群聊文件路径
                    group["chat_file"] = group_chat_file

                # 添加到通讯地址列表
                communication_files.append({
                    "type": "group_chat",
                    "group_id": group_id,
                    "file_path": group_chat_file,
                    "description": f"{group_name} 组群聊"
                })

                break

        if not group_found:
            return f"错误: 找不到ID为 '{group_id}' 的组。"

        # 如果是组长且父组存在，添加父组群聊通讯文件
        if is_group_leader and parent_group_id:
            parent_group_name = ""
            for group in config["team"].get("groups", []):
                if group.get("id") == parent_group_id:
                    parent_group_name = group.get("name", "")
                    break

            # 获取父组的群聊文件路径
            parent_group_chat_file = None
            for g in config["team"].get("groups", []):
                if g.get("id") == parent_group_id:
                    parent_group_chat_file = g.get("chat_file")
                    break

            if not parent_group_chat_file:
                # 如果找不到父组群聊文件，创建一个新的
                # 构建完整的父组路径名称
                full_path = parent_group_name
                parent_id = None

                # 查找父组的父组ID
                for g in config["team"].get("groups", []):
                    if g.get("id") == parent_group_id:
                        parent_id = g.get("parent_id")
                        break

                # 递归查找父组路径
                while parent_id:
                    for g in config["team"].get("groups", []):
                        if g.get("id") == parent_id:
                            parent_name = g.get("name", "")
                            full_path = f"{parent_name}-{full_path}"
                            parent_id = g.get("parent_id")
                            break
                    else:
                        parent_id = None

                # 创建群组目录和群聊文件
                groups_dir = os.path.join(project_root, "ProjectTask", "GroupChat", "Groups")

                # 将路径名称转换为文件系统路径
                group_path_parts = full_path.split("-")
                current_path = groups_dir

                # 创建层级目录结构
                for i, part in enumerate(group_path_parts):
                    current_path = os.path.join(current_path, part)
                    os.makedirs(current_path, exist_ok=True)

                # 创建群聊文件
                parent_group_chat_file = os.path.join("ProjectTask", "GroupChat", "Groups", *group_path_parts, "group_chat.txt")
                full_parent_group_chat_path = os.path.join(project_root, parent_group_chat_file)

                if not os.path.exists(full_parent_group_chat_path):
                    with open(full_parent_group_chat_path, 'w', encoding='utf-8') as f:
                        f.write(f"# {full_path} 群聊\n创建时间: {datetime.datetime.now().isoformat()}\n\n")

                # 更新父组的群聊文件路径
                for g in config["team"].get("groups", []):
                    if g.get("id") == parent_group_id:
                        g["chat_file"] = parent_group_chat_file
                        break

            # 添加到通讯地址列表
            communication_files.append({
                "type": "parent_group_chat",
                "group_id": parent_group_id,
                "file_path": parent_group_chat_file,
                "description": f"{parent_group_name} 父组群聊"
            })

    # 添加新成员
    new_member = {
        "username": username,
        "role": role,
        "description": description,
        "communication_files": communication_files,
        "is_group_leader": is_group_leader,
        "group_id": group_id,
        "added_at": datetime.datetime.now().isoformat()
    }

    config["team"]["members"].append(new_member)

    # 保存配置
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    result = f"已添加团队成员 '{username}' 并分配角色 '{role}'"

    if group_id:
        result += f"，已添加到组 '{group_id}'"
        if is_group_leader:
            result += f" 并设为组长"

    result += f"\n通讯地址:"
    for comm_file in communication_files:
        result += f"\n- {comm_file['description']}: {comm_file['file_path']}"

    return result

def remove_team_member(
    username: Annotated[str, "用户名"],
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    移除团队成员

    从项目中移除团队成员，同时处理其通讯文件和组成员关系
    """
    if project_root is None:
        project_root = os.getcwd()

    # 读取配置文件
    config_path = os.path.join(project_root, ".taskmasterconfig")
    if not os.path.isfile(config_path):
        return f"错误: 找不到配置文件。请先初始化项目。"

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError:
        return f"错误: 无法解析配置文件。"

    # 确保配置中有team字段
    if "team" not in config or "members" not in config["team"]:
        return f"错误: 项目中没有团队成员。"

    # 查找用户
    members = config["team"]["members"]
    found = False
    removed_member = None
    communication_files = []

    for i, member in enumerate(members):
        if member.get("username") == username:
            removed_member = member
            # 获取所有通讯文件
            if "communication_files" in member:
                communication_files = member["communication_files"]
            del members[i]
            found = True
            break

    if not found:
        return f"错误: 找不到用户 '{username}'。"

    # 检查用户是否是任何组的组长
    is_leader = False
    leader_groups = []

    if "groups" in config["team"]:
        for group in config["team"]["groups"]:
            if group.get("leader") == username:
                is_leader = True
                leader_groups.append(group.get("name", group.get("id", "")))

    if is_leader:
        # 恢复删除的成员
        members.append(removed_member)
        return f"错误: 用户 '{username}' 是以下组的组长，不能移除: {', '.join(leader_groups)}。请先更换组长或删除这些组。"

    # 从所有组中移除该成员
    if "groups" in config["team"]:
        for group in config["team"]["groups"]:
            if username in group.get("members", []):
                group["members"].remove(username)

    # 保存配置
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    # 处理通讯文件（归档个人通讯文件，保留群聊文件）
    archived_files = []

    # 创建归档目录
    archive_dir = os.path.join(project_root, "ProjectTask", "GroupChat", "Archive", "Personal")
    os.makedirs(archive_dir, exist_ok=True)

    for comm_file in communication_files:
        file_path = comm_file.get("file_path", "")
        file_type = comm_file.get("type", "")

        # 只归档个人通讯文件，群聊文件保留
        if file_type == "personal" and file_path:
            full_file_path = os.path.join(project_root, file_path)
            if os.path.isfile(full_file_path):
                # 归档文件
                archive_file_name = f"{username}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.txt"
                archive_path = os.path.join(archive_dir, archive_file_name)

                try:
                    # 复制到归档
                    shutil.copy2(full_file_path, archive_path)
                    # 删除原文件
                    os.remove(full_file_path)
                    archived_files.append(file_path)
                except Exception as e:
                    return f"已移除团队成员 '{username}'，但处理通讯文件时出错: {str(e)}"

    if archived_files:
        return f"已移除团队成员 '{username}'，并归档了以下通讯文件: {', '.join(archived_files)}"
    else:
        return f"已移除团队成员 '{username}'"

def list_team_members(
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None,
    group_id: Annotated[str, "按组ID筛选成员"] = None
) -> str:
    """
    列出团队成员

    显示项目中的所有团队成员及其角色、描述和通讯地址
    可以按组ID筛选成员
    """
    if project_root is None:
        project_root = os.getcwd()

    # 读取配置文件
    config_path = os.path.join(project_root, ".taskmasterconfig")
    if not os.path.isfile(config_path):
        return f"错误: 找不到配置文件。请先初始化项目。"

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError:
        return f"错误: 无法解析配置文件。"

    # 确保配置中有team字段
    if "team" not in config or "members" not in config["team"]:
        return f"项目中没有团队成员。"

    members = config["team"]["members"]

    if not members:
        return f"项目中没有团队成员。"

    # 如果指定了组ID，筛选该组的成员
    if group_id:
        # 先检查组是否存在
        group_found = False
        group_name = ""

        for group in config["team"].get("groups", []):
            if group.get("id") == group_id:
                group_found = True
                group_name = group.get("name", "")
                break

        if not group_found:
            return f"错误: 找不到ID为 '{group_id}' 的组。"

        # 筛选该组的成员
        filtered_members = []
        for member in members:
            # 检查成员是否属于该组
            if member.get("group_id") == group_id:
                filtered_members.append(member)
            # 或者检查成员的通讯文件中是否包含该组的群聊
            elif "communication_files" in member:
                for comm_file in member["communication_files"]:
                    if comm_file.get("type") in ["group_chat", "parent_group_chat"] and comm_file.get("group_id") == group_id:
                        filtered_members.append(member)
                        break

        if not filtered_members:
            return f"组 '{group_name}' (ID: {group_id}) 中没有成员。"

        members = filtered_members
        report = [f"组 '{group_name}' (ID: {group_id}) 的成员:"]
    else:
        report = ["团队成员:"]

    # 生成报告
    for member in members:
        username = member.get("username", "")
        role = member.get("role", "")
        description = member.get("description", "")
        is_group_leader = member.get("is_group_leader", False)
        member_group_id = member.get("group_id", "")

        # 获取成员所属组的名称
        group_name = ""
        if member_group_id:
            for group in config["team"].get("groups", []):
                if group.get("id") == member_group_id:
                    group_name = group.get("name", "")
                    break

        # 构建成员信息
        if is_group_leader and group_name:
            member_info = f"  - {username} ({role}) [组长: {group_name}]"
        elif group_name:
            member_info = f"  - {username} ({role}) [组员: {group_name}]"
        else:
            member_info = f"  - {username} ({role})"

        if description:
            member_info += f" 描述: {description}"

        report.append(member_info)

        # 添加通讯地址信息
        if "communication_files" in member:
            report.append(f"    通讯地址:")
            for comm_file in member["communication_files"]:
                report.append(f"    - {comm_file.get('description', '')}: {comm_file.get('file_path', '')}")

    return "\n".join(report)

def create_group(
    group_name: Annotated[str, "组名称"],
    leader_username: Annotated[str, "组长用户名"],
    description: Annotated[str, "组描述"] = "",
    parent_group_id: Annotated[Optional[str], "父组ID，如果为None则为顶级组"] = None,
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    创建团队组

    创建一个新的团队组，指定组长和可选的父组
    群组按层级组织，使用"上上级-上级-组名"的命名方式
    """
    if project_root is None:
        project_root = os.getcwd()

    # 读取配置文件
    config_path = os.path.join(project_root, ".taskmasterconfig")
    if not os.path.isfile(config_path):
        return f"错误: 找不到配置文件。请先初始化项目。"

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError:
        return f"错误: 无法解析配置文件。"

    # 确保配置中有team字段和groups字段
    if "team" not in config:
        config["team"] = {
            "members": [],
            "groups": [],
            "roles": DEFAULT_CONFIG["team"]["roles"]
        }
    elif "groups" not in config["team"]:
        config["team"]["groups"] = []

    # 检查组长是否存在
    leader_exists = False
    for member in config["team"].get("members", []):
        if member.get("username") == leader_username:
            leader_exists = True
            break

    if not leader_exists:
        return f"错误: 找不到组长用户 '{leader_username}'。请先添加该用户。"

    # 检查父组是否存在（如果指定了父组）
    parent_group = None
    parent_full_path = ""
    parent_name = ""

    if parent_group_id:
        parent_exists = False
        for group in config["team"].get("groups", []):
            if group.get("id") == parent_group_id:
                parent_exists = True
                parent_group = group
                parent_name = group.get("name", "")
                parent_full_path = group.get("full_path", parent_name)
                break

        if not parent_exists:
            return f"错误: 找不到父组 '{parent_group_id}'。"

    # 生成新组ID
    groups = config["team"].get("groups", [])
    new_group_id = f"group_{len(groups) + 1:03d}"

    # 构建完整的组路径名称（使用"上上级-上级-组名"的命名方式）
    if parent_group_id:
        full_path = f"{parent_full_path}-{group_name}"
    else:
        full_path = group_name

    # 创建群组目录和群聊文件
    groups_dir = os.path.join(project_root, "ProjectTask", "GroupChat", "Groups")

    # 将路径名称转换为文件系统路径（替换-为目录分隔符）
    group_path_parts = full_path.split("-")
    current_path = groups_dir

    # 创建层级目录结构
    for i, part in enumerate(group_path_parts):
        current_path = os.path.join(current_path, part)
        os.makedirs(current_path, exist_ok=True)

        # 如果是最后一级，创建群聊文件
        if i == len(group_path_parts) - 1:
            group_chat_file = os.path.join(current_path, "group_chat.txt")
            if not os.path.exists(group_chat_file):
                with open(group_chat_file, 'w', encoding='utf-8') as f:
                    f.write(f"# {full_path} 群聊\n创建时间: {datetime.datetime.now().isoformat()}\n\n")

    # 计算群聊文件的相对路径
    group_chat_rel_path = os.path.join("ProjectTask", "GroupChat", "Groups", *group_path_parts, "group_chat.txt")

    # 创建新组
    new_group = {
        "id": new_group_id,
        "name": group_name,
        "description": description,
        "leader": leader_username,
        "parent_id": parent_group_id,
        "full_path": full_path,
        "chat_file": group_chat_rel_path,
        "members": [leader_username],  # 组长自动成为组成员
        "created_at": datetime.datetime.now().isoformat()
    }

    # 添加新组
    groups.append(new_group)
    config["team"]["groups"] = groups

    # 更新组长的通讯文件列表
    for member in config["team"].get("members", []):
        if member.get("username") == leader_username:
            if "communication_files" not in member:
                member["communication_files"] = []

            # 添加组群聊通讯文件
            group_chat_entry = {
                "type": "group_chat",
                "group_id": new_group_id,
                "file_path": group_chat_rel_path,
                "description": f"{full_path} 组群聊"
            }

            # 检查是否已存在相同的通讯文件
            exists = False
            for comm_file in member["communication_files"]:
                if comm_file.get("file_path") == group_chat_rel_path:
                    exists = True
                    break

            if not exists:
                member["communication_files"].append(group_chat_entry)

            # 如果是子组的组长，添加父组群聊通讯文件
            if parent_group_id and parent_group:
                parent_chat_file = parent_group.get("chat_file")
                if parent_chat_file:
                    parent_chat_entry = {
                        "type": "parent_group_chat",
                        "group_id": parent_group_id,
                        "file_path": parent_chat_file,
                        "description": f"{parent_full_path} 父组群聊"
                    }

                    # 检查是否已存在相同的通讯文件
                    exists = False
                    for comm_file in member["communication_files"]:
                        if comm_file.get("file_path") == parent_chat_file:
                            exists = True
                            break

                    if not exists:
                        member["communication_files"].append(parent_chat_entry)

            # 标记为组长
            member["is_group_leader"] = True
            member["group_id"] = new_group_id
            break

    # 保存配置
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    result = f"已创建组 '{group_name}' (ID: {new_group_id})，组长为 '{leader_username}'"
    if parent_group_id:
        result += f"，父组为 '{parent_group_id}'"
    result += f"\n组路径: {full_path}"
    result += f"\n群聊文件: {group_chat_rel_path}"

    return result

def add_member_to_group(
    username: Annotated[str, "用户名"],
    group_id: Annotated[str, "组ID，例如group_001"],
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    将成员添加到组

    将指定用户添加到指定组
    """
    if project_root is None:
        project_root = os.getcwd()

    # 读取配置文件
    config_path = os.path.join(project_root, ".taskmasterconfig")
    if not os.path.isfile(config_path):
        return f"错误: 找不到配置文件。请先初始化项目。"

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError:
        return f"错误: 无法解析配置文件。"

    # 确保配置中有team字段和groups字段
    if "team" not in config or "groups" not in config["team"]:
        return f"错误: 项目中没有团队组。"

    # 检查用户是否存在
    user_exists = False
    for member in config["team"].get("members", []):
        if member.get("username") == username:
            user_exists = True
            break

    if not user_exists:
        return f"错误: 找不到用户 '{username}'。"

    # 查找组
    group_found = False
    group_name = ""

    for group in config["team"]["groups"]:
        if group.get("id") == group_id:
            group_name = group.get("name", "")

            # 检查用户是否已在组中
            if username in group.get("members", []):
                return f"用户 '{username}' 已经是组 '{group_name}' 的成员。"

            # 添加用户到组
            if "members" not in group:
                group["members"] = []

            group["members"].append(username)
            group_found = True
            break

    if not group_found:
        return f"错误: 找不到ID为 '{group_id}' 的组。"

    # 保存配置
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    return f"已将用户 '{username}' 添加到组 '{group_name}' (ID: {group_id})"

def remove_member_from_group(
    username: Annotated[str, "用户名"],
    group_id: Annotated[str, "组ID，例如group_001"],
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    从组中移除成员

    将指定用户从指定组中移除
    """
    if project_root is None:
        project_root = os.getcwd()

    # 读取配置文件
    config_path = os.path.join(project_root, ".taskmasterconfig")
    if not os.path.isfile(config_path):
        return f"错误: 找不到配置文件。请先初始化项目。"

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError:
        return f"错误: 无法解析配置文件。"

    # 确保配置中有team字段和groups字段
    if "team" not in config or "groups" not in config["team"]:
        return f"错误: 项目中没有团队组。"

    # 查找组
    group_found = False
    group_name = ""
    is_leader = False

    for group in config["team"]["groups"]:
        if group.get("id") == group_id:
            group_name = group.get("name", "")

            # 检查用户是否是组长
            if group.get("leader") == username:
                is_leader = True
                return f"错误: 用户 '{username}' 是组 '{group_name}' 的组长，不能移除。请先更换组长或删除组。"

            # 检查用户是否在组中
            if username not in group.get("members", []):
                return f"用户 '{username}' 不是组 '{group_name}' 的成员。"

            # 从组中移除用户
            group["members"].remove(username)
            group_found = True
            break

    if not group_found:
        return f"错误: 找不到ID为 '{group_id}' 的组。"

    # 保存配置
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    return f"已将用户 '{username}' 从组 '{group_name}' (ID: {group_id}) 中移除"

def list_groups(
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None,
    show_members: Annotated[bool, "是否显示组成员"] = True
) -> str:
    """
    列出所有团队组

    显示项目中的所有团队组及其组长、成员等信息
    """
    if project_root is None:
        project_root = os.getcwd()

    # 读取配置文件
    config_path = os.path.join(project_root, ".taskmasterconfig")
    if not os.path.isfile(config_path):
        return f"错误: 找不到配置文件。请先初始化项目。"

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError:
        return f"错误: 无法解析配置文件。"

    # 确保配置中有team字段和groups字段
    if "team" not in config or "groups" not in config["team"]:
        return f"项目中没有团队组。"

    groups = config["team"]["groups"]

    if not groups:
        return f"项目中没有团队组。"

    # 构建组层次结构
    group_dict = {group["id"]: group for group in groups}
    top_level_groups = [group for group in groups if not group.get("parent_id")]

    # 生成报告
    report = ["团队组:"]

    # 递归生成组层次结构报告
    def add_group_to_report(group, level=0):
        indent = "  " * level
        group_id = group["id"]
        group_name = group["name"]
        leader = group["leader"]
        description = group.get("description", "")

        # 基本组信息
        group_info = f"{indent}- {group_name} (ID: {group_id}, 组长: {leader})"
        if description:
            group_info += f" - {description}"
        report.append(group_info)

        # 组成员信息
        if show_members and "members" in group and group["members"]:
            members = group["members"]
            report.append(f"{indent}  成员: {', '.join(members)}")

        # 递归处理子组
        children = [g for g in groups if g.get("parent_id") == group_id]
        for child in children:
            add_group_to_report(child, level + 1)

    # 处理所有顶级组
    for group in top_level_groups:
        add_group_to_report(group)

    return "\n".join(report)

def delete_group(
    group_id: Annotated[str, "组ID，例如group_001"],
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    删除团队组

    删除指定的团队组，如果有子组，则子组的parent_id将被设为None
    """
    if project_root is None:
        project_root = os.getcwd()

    # 读取配置文件
    config_path = os.path.join(project_root, ".taskmasterconfig")
    if not os.path.isfile(config_path):
        return f"错误: 找不到配置文件。请先初始化项目。"

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError:
        return f"错误: 无法解析配置文件。"

    # 确保配置中有team字段和groups字段
    if "team" not in config or "groups" not in config["team"]:
        return f"错误: 项目中没有团队组。"

    # 查找组
    groups = config["team"]["groups"]
    group_found = False
    group_name = ""
    group_index = -1

    for i, group in enumerate(groups):
        if group.get("id") == group_id:
            group_name = group.get("name", "")
            group_index = i
            group_found = True
            break

    if not group_found:
        return f"错误: 找不到ID为 '{group_id}' 的组。"

    # 删除组
    deleted_group = groups.pop(group_index)

    # 更新子组的parent_id
    for group in groups:
        if group.get("parent_id") == group_id:
            group["parent_id"] = None

    # 保存配置
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    return f"已删除组 '{group_name}' (ID: {group_id})"

def send_message(
    to_username: Annotated[str, "接收消息的用户名"],
    message: Annotated[str, "消息内容"],
    message_type: Annotated[str, "消息类型 (task_assigned, task_status_changed, direct_message, system_notification)"] = "direct_message",
    from_username: Annotated[str, "发送消息的用户名，默认为system"] = "system",
    comm_type: Annotated[str, "通讯类型 (personal, group_chat, parent_group_chat)"] = "personal",
    group_id: Annotated[str, "组ID，当comm_type为group_chat或parent_group_chat时必须提供"] = None,
    wait_for_reply: Annotated[bool, "是否等待回复"] = False,
    reply_timeout: Annotated[int, "等待回复的超时时间（秒），0表示无限等待"] = 0,
    reply_check_interval: Annotated[float, "检查回复的间隔时间（秒）"] = 1.0,
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    发送消息

    向指定用户或群组发送消息，消息将保存在相应的通讯文件中
    支持等待回复功能：
    - wait_for_reply=True: 等待接收者回复后才返回
    - reply_timeout=0: 无限等待回复，直到有回复为止
    - reply_timeout>0: 在指定的超时时间内等待回复，超时后返回
    """
    if project_root is None:
        project_root = os.getcwd()

    # 读取配置文件
    config_path = os.path.join(project_root, ".taskmasterconfig")
    if not os.path.isfile(config_path):
        return f"错误: 找不到配置文件。请先初始化项目。"

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError:
        return f"错误: 无法解析配置文件。"

    # 确保配置中有team字段
    if "team" not in config or "members" not in config["team"]:
        return f"错误: 项目中没有团队成员。"

    # 构建消息
    timestamp = datetime.datetime.now().isoformat()
    message_line = f"[{timestamp}]|{from_username}|{message_type}|unread|{message}\n"

    # 根据通讯类型处理
    if comm_type == "personal":
        # 查找接收者
        receiver = None
        for member in config["team"]["members"]:
            if member.get("username") == to_username:
                receiver = member
                break

        if not receiver:
            return f"错误: 找不到用户 '{to_username}'。"

        # 获取接收者的个人通讯文件路径
        personal_file_path = None
        if "communication_files" in receiver:
            for comm_file in receiver["communication_files"]:
                if comm_file.get("type") == "personal":
                    personal_file_path = comm_file.get("file_path")
                    break

        if not personal_file_path:
            return f"错误: 用户 '{to_username}' 没有个人通讯文件。"

        # 构建完整的消息文件路径
        full_message_file_path = os.path.join(project_root, personal_file_path)

        # 写入消息
        try:
            with open(full_message_file_path, 'a', encoding='utf-8') as f:
                f.write(message_line)
        except Exception as e:
            return f"错误: 无法写入消息文件: {str(e)}"

        # 如果不需要等待回复，直接返回
        if not wait_for_reply:
            return f"已向用户 '{to_username}' 发送个人消息"

        # 等待回复
        result = f"已向用户 '{to_username}' 发送个人消息"

        # 记录当前消息数量
        initial_message_count = 0
        try:
            with open(full_message_file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()

            # 计算当前消息数量
            for line in file_content.splitlines():
                if line.strip() and not line.startswith('#'):
                    initial_message_count += 1
        except Exception:
            return result + f"\n警告: 无法读取消息文件，无法等待回复"

        # 设置开始等待的时间
        start_time = time.time()

        # 等待回复
        while True:
            # 检查是否有新消息
            current_message_count = 0
            latest_message = ""

            try:
                with open(full_message_file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()

                # 计算当前消息数量并获取最新消息
                lines = []
                for line in file_content.splitlines():
                    if line.strip() and not line.startswith('#'):
                        lines.append(line)
                        current_message_count += 1

                # 获取最新消息
                if lines and current_message_count > initial_message_count:
                    latest_message = lines[-1]
            except Exception:
                pass  # 忽略读取错误，继续等待

            # 如果有新消息，表示有回复
            if current_message_count > initial_message_count:
                # 解析最新消息
                try:
                    parts = latest_message.strip().split('|', 4)
                    if len(parts) >= 5:
                        timestamp, sender, msg_type, read_status, content = parts
                        # 确保不是自己发的消息
                        if sender != from_username:
                            result += f"\n收到回复: [{timestamp}] {sender}: {content}"
                            break
                except Exception:
                    result += f"\n收到回复，但无法解析"
                    break

            # 检查是否超时
            if reply_timeout > 0 and (time.time() - start_time) > reply_timeout:
                result += f"\n等待回复超时"
                break

            # 等待一段时间再检查
            time.sleep(reply_check_interval)

        return result

    elif comm_type in ["group_chat", "parent_group_chat"]:
        if not group_id:
            return f"错误: 发送群组消息时必须提供group_id参数。"

        # 查找组
        group_found = False
        group_name = ""

        for group in config["team"].get("groups", []):
            if group.get("id") == group_id:
                group_found = True
                group_name = group.get("name", "")
                break

        if not group_found:
            return f"错误: 找不到ID为 '{group_id}' 的组。"

        # 获取群聊文件路径
        group_chat_file = None
        for group in config["team"].get("groups", []):
            if group.get("id") == group_id:
                group_chat_file = group.get("chat_file")
                break

        if not group_chat_file:
            return f"错误: 找不到组 '{group_id}' 的群聊文件。"

        full_group_chat_path = os.path.join(project_root, group_chat_file)

        # 确保群聊文件存在
        if not os.path.exists(full_group_chat_path):
            # 确保目录存在
            os.makedirs(os.path.dirname(full_group_chat_path), exist_ok=True)
            # 创建群聊文件
            with open(full_group_chat_path, 'w', encoding='utf-8') as f:
                f.write(f"# {group_name} 群聊\n创建时间: {datetime.datetime.now().isoformat()}\n\n")

        # 写入消息
        try:
            with open(full_group_chat_path, 'a', encoding='utf-8') as f:
                f.write(message_line)
        except Exception as e:
            return f"错误: 无法写入群聊文件: {str(e)}"

        # 如果不需要等待回复，直接返回
        if not wait_for_reply:
            return f"已向组 '{group_name}' (ID: {group_id}) 发送群聊消息"

        # 等待回复
        result = f"已向组 '{group_name}' (ID: {group_id}) 发送群聊消息"

        # 记录当前消息数量
        initial_message_count = 0
        try:
            with open(full_group_chat_path, 'r', encoding='utf-8') as f:
                file_content = f.read()

            # 计算当前消息数量
            for line in file_content.splitlines():
                if line.strip() and not line.startswith('#'):
                    initial_message_count += 1
        except Exception:
            return result + f"\n警告: 无法读取群聊文件，无法等待回复"

        # 设置开始等待的时间
        start_time = time.time()

        # 等待回复
        while True:
            # 检查是否有新消息
            current_message_count = 0
            latest_message = ""

            try:
                with open(full_group_chat_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()

                # 计算当前消息数量并获取最新消息
                lines = []
                for line in file_content.splitlines():
                    if line.strip() and not line.startswith('#'):
                        lines.append(line)
                        current_message_count += 1

                # 获取最新消息
                if lines and current_message_count > initial_message_count:
                    latest_message = lines[-1]
            except Exception:
                pass  # 忽略读取错误，继续等待

            # 如果有新消息，表示有回复
            if current_message_count > initial_message_count:
                # 解析最新消息
                try:
                    parts = latest_message.strip().split('|', 4)
                    if len(parts) >= 5:
                        timestamp, sender, msg_type, read_status, content = parts
                        # 确保不是自己发的消息
                        if sender != from_username:
                            result += f"\n收到回复: [{timestamp}] {sender}: {content}"
                            break
                except Exception:
                    result += f"\n收到回复，但无法解析"
                    break

            # 检查是否超时
            if reply_timeout > 0 and (time.time() - start_time) > reply_timeout:
                result += f"\n等待回复超时"
                break

            # 等待一段时间再检查
            time.sleep(reply_check_interval)

        return result

    else:
        return f"错误: 无效的通讯类型 '{comm_type}'。有效类型: personal, group_chat, parent_group_chat"

def get_messages(
    username: Annotated[str, "用户名"],
    unread_only: Annotated[bool, "是否只获取未读消息"] = False,
    comm_type: Annotated[str, "通讯类型 (personal, group_chat, parent_group_chat, all)"] = "personal",
    group_id: Annotated[str, "组ID，当comm_type为group_chat或parent_group_chat时必须提供"] = None,
    wait_mode: Annotated[str, "等待模式 (no_wait, timeout, infinite)"] = "no_wait",
    timeout_seconds: Annotated[int, "超时时间（秒），仅在wait_mode为timeout时有效"] = 60,
    check_interval: Annotated[float, "检查间隔（秒）"] = 1.0,
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    获取消息

    获取指定用户的个人消息或群组消息，可以选择只获取未读消息
    支持三种等待模式：
    - no_wait: 不等待，立即返回当前消息
    - timeout: 在指定的超时时间内等待新消息，超时后返回
    - infinite: 无限等待，直到有新消息出现才返回
    """
    if project_root is None:
        project_root = os.getcwd()

    # 读取配置文件
    config_path = os.path.join(project_root, ".taskmasterconfig")
    if not os.path.isfile(config_path):
        return f"错误: 找不到配置文件。请先初始化项目。"

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError:
        return f"错误: 无法解析配置文件。"

    # 确保配置中有team字段
    if "team" not in config or "members" not in config["team"]:
        return f"错误: 项目中没有团队成员。"

    # 查找用户
    user = None
    for member in config["team"]["members"]:
        if member.get("username") == username:
            user = member
            break

    if not user:
        return f"错误: 找不到用户 '{username}'。"

    # 获取要读取的消息文件列表
    message_files = []

    if comm_type == "all":
        # 获取用户的所有通讯文件
        if "communication_files" in user:
            for comm_file in user["communication_files"]:
                message_files.append({
                    "path": comm_file.get("file_path", ""),
                    "type": comm_file.get("type", ""),
                    "description": comm_file.get("description", ""),
                    "group_id": comm_file.get("group_id", "")
                })
    elif comm_type == "personal":
        # 获取用户的个人通讯文件
        if "communication_files" in user:
            for comm_file in user["communication_files"]:
                if comm_file.get("type") == "personal":
                    message_files.append({
                        "path": comm_file.get("file_path", ""),
                        "type": "personal",
                        "description": "个人消息",
                        "group_id": None
                    })
                    break
    elif comm_type in ["group_chat", "parent_group_chat"]:
        if not group_id:
            return f"错误: 获取群组消息时必须提供group_id参数。"

        # 查找组
        group_found = False
        group_name = ""

        for group in config["team"].get("groups", []):
            if group.get("id") == group_id:
                group_found = True
                group_name = group.get("name", "")
                break

        if not group_found:
            return f"错误: 找不到ID为 '{group_id}' 的组。"

        # 构建群聊文件路径
        group_chat_file = os.path.join(".taskmaster", "group_chats", f"group_{group_id}.txt")

        message_files.append({
            "path": group_chat_file,
            "type": comm_type,
            "description": f"{group_name} 群聊",
            "group_id": group_id
        })
    else:
        return f"错误: 无效的通讯类型 '{comm_type}'。有效类型: personal, group_chat, parent_group_chat, all"

    if not message_files:
        return f"用户 '{username}' 没有可用的通讯文件。"

    # 验证等待模式
    if wait_mode not in ["no_wait", "timeout", "infinite"]:
        return f"错误: 无效的等待模式 '{wait_mode}'。有效模式: no_wait, timeout, infinite"

    # 如果使用等待模式，记录初始消息数量
    if wait_mode in ["timeout", "infinite"]:
        # 获取初始消息数量
        initial_message_count = 0
        initial_unread_count = 0

        for file_info in message_files:
            file_path = file_info["path"]
            if not file_path:
                continue

            full_file_path = os.path.join(project_root, file_path)
            if not os.path.isfile(full_file_path):
                continue

            try:
                with open(full_file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()

                # 计算消息数量
                for line in file_content.splitlines():
                    if line.strip() and not line.startswith('#'):
                        initial_message_count += 1
                        # 检查是否为未读消息
                        parts = line.strip().split('|', 4)
                        if len(parts) >= 4 and parts[3] == "unread":
                            initial_unread_count += 1
            except Exception:
                pass  # 忽略读取错误，继续检查其他文件

        # 设置开始等待的时间
        start_time = time.time()

        # 等待新消息
        while True:
            # 检查是否有新消息
            current_message_count = 0
            current_unread_count = 0

            for file_info in message_files:
                file_path = file_info["path"]
                if not file_path:
                    continue

                full_file_path = os.path.join(project_root, file_path)
                if not os.path.isfile(full_file_path):
                    continue

                try:
                    with open(full_file_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()

                    # 计算当前消息数量
                    for line in file_content.splitlines():
                        if line.strip() and not line.startswith('#'):
                            current_message_count += 1
                            # 检查是否为未读消息
                            parts = line.strip().split('|', 4)
                            if len(parts) >= 4 and parts[3] == "unread":
                                current_unread_count += 1
                except Exception:
                    pass  # 忽略读取错误，继续检查其他文件

            # 检查是否有新消息
            has_new_messages = current_message_count > initial_message_count
            has_new_unread = current_unread_count > initial_unread_count

            # 如果有新消息或新的未读消息，退出等待
            if has_new_messages or (unread_only and has_new_unread):
                break

            # 检查是否超时
            if wait_mode == "timeout" and (time.time() - start_time) > timeout_seconds:
                break

            # 等待一段时间再检查
            time.sleep(check_interval)

    # 读取所有消息文件并解析消息
    all_parsed_messages = []

    for file_info in message_files:
        file_path = file_info["path"]
        file_type = file_info["type"]
        file_description = file_info["description"]

        if not file_path:
            continue

        full_file_path = os.path.join(project_root, file_path)

        # 检查文件是否存在
        if not os.path.isfile(full_file_path):
            continue

        # 读取消息
        try:
            with open(full_file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()

            # 跳过文件头部的注释和空行
            lines = []
            for line in file_content.splitlines():
                if line.strip() and not line.startswith('#'):
                    lines.append(line)

            if not lines:
                continue

            # 解析消息
            for message in lines:
                parts = message.strip().split('|', 4)
                if len(parts) < 5:
                    continue  # 跳过格式不正确的消息

                timestamp, sender, message_type, read_status, content = parts

                # 如果只获取未读消息，跳过已读消息
                if unread_only and read_status != "unread":
                    continue

                # 格式化时间戳
                try:
                    dt = datetime.datetime.fromisoformat(timestamp.strip('[]'))
                    formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    formatted_time = timestamp.strip('[]')

                # 添加解析后的消息
                all_parsed_messages.append({
                    "timestamp": formatted_time,
                    "sender": sender,
                    "type": message_type,
                    "read_status": read_status,
                    "content": content,
                    "file_type": file_type,
                    "file_description": file_description
                })

        except Exception as e:
            return f"错误: 无法读取消息文件 {file_path}: {str(e)}"

    # 按时间戳排序
    all_parsed_messages.sort(key=lambda x: x["timestamp"])

    if not all_parsed_messages:
        if unread_only:
            return f"用户 '{username}' 没有未读消息。"
        else:
            return f"用户 '{username}' 没有消息。"

    # 生成报告
    if comm_type == "all":
        if unread_only:
            report = [f"用户 '{username}' 的所有未读消息:"]
        else:
            report = [f"用户 '{username}' 的所有消息:"]
    elif comm_type == "personal":
        if unread_only:
            report = [f"用户 '{username}' 的未读个人消息:"]
        else:
            report = [f"用户 '{username}' 的个人消息:"]
    else:
        group_name = ""
        for file_info in message_files:
            if file_info["type"] == comm_type:
                group_name = file_info["description"]
                break

        if unread_only:
            report = [f"{group_name}的未读消息:"]
        else:
            report = [f"{group_name}的所有消息:"]

    for i, msg in enumerate(all_parsed_messages, 1):
        source_info = f"[{msg['file_description']}]" if comm_type == "all" else ""
        report.append(f"{i}. [{msg['timestamp']}] {source_info} 来自: {msg['sender']}, 类型: {msg['type']}, 状态: {msg['read_status']}")
        report.append(f"   内容: {msg['content']}")
        report.append("")

    return "\n".join(report)

def mark_message_read(
    username: Annotated[str, "用户名"],
    message_index: Annotated[int, "消息索引，从1开始"] = 0,  # 0表示标记所有消息为已读
    comm_type: Annotated[str, "通讯类型 (personal, group_chat, parent_group_chat)"] = "personal",
    group_id: Annotated[str, "组ID，当comm_type为group_chat或parent_group_chat时必须提供"] = None,
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    标记消息为已读

    标记指定用户的个人消息或群组消息为已读，可以指定消息索引或标记所有消息
    """
    if project_root is None:
        project_root = os.getcwd()

    # 读取配置文件
    config_path = os.path.join(project_root, ".taskmasterconfig")
    if not os.path.isfile(config_path):
        return f"错误: 找不到配置文件。请先初始化项目。"

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError:
        return f"错误: 无法解析配置文件。"

    # 确保配置中有team字段
    if "team" not in config or "members" not in config["team"]:
        return f"错误: 项目中没有团队成员。"

    # 获取要标记的消息文件路径
    message_file_path = None
    file_description = ""

    if comm_type == "personal":
        # 查找用户
        user = None
        for member in config["team"]["members"]:
            if member.get("username") == username:
                user = member
                break

        if not user:
            return f"错误: 找不到用户 '{username}'。"

        # 获取用户的个人通讯文件路径
        if "communication_files" in user:
            for comm_file in user["communication_files"]:
                if comm_file.get("type") == "personal":
                    message_file_path = comm_file.get("file_path")
                    file_description = "个人消息"
                    break

        if not message_file_path:
            return f"错误: 用户 '{username}' 没有个人通讯文件。"

    elif comm_type in ["group_chat", "parent_group_chat"]:
        if not group_id:
            return f"错误: 标记群组消息时必须提供group_id参数。"

        # 查找组
        group_found = False
        group_name = ""

        for group in config["team"].get("groups", []):
            if group.get("id") == group_id:
                group_found = True
                group_name = group.get("name", "")
                break

        if not group_found:
            return f"错误: 找不到ID为 '{group_id}' 的组。"

        # 构建群聊文件路径
        message_file_path = os.path.join(".taskmaster", "group_chats", f"group_{group_id}.txt")
        file_description = f"{group_name} 群聊"

    else:
        return f"错误: 无效的通讯类型 '{comm_type}'。有效类型: personal, group_chat, parent_group_chat"

    # 构建完整的消息文件路径
    full_message_file_path = os.path.join(project_root, message_file_path)

    # 检查消息文件是否存在
    if not os.path.isfile(full_message_file_path):
        if comm_type == "personal":
            return f"用户 '{username}' 没有消息。"
        else:
            return f"{file_description}没有消息。"

    # 读取消息
    try:
        with open(full_message_file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
    except Exception as e:
        return f"错误: 无法读取消息文件: {str(e)}"

    # 跳过文件头部的注释和空行
    lines = []
    for line in file_content.splitlines():
        if line.strip() and not line.startswith('#'):
            lines.append(line)

    if not lines:
        if comm_type == "personal":
            return f"用户 '{username}' 没有消息。"
        else:
            return f"{file_description}没有消息。"

    # 标记消息为已读
    unread_count = 0
    marked_count = 0
    updated_lines = []

    # 处理文件头部的注释和空行
    for line in file_content.splitlines():
        if not line.strip() or line.startswith('#'):
            updated_lines.append(line)
            continue

        parts = line.strip().split('|', 4)
        if len(parts) < 5:
            updated_lines.append(line)  # 保留格式不正确的行
            continue

        timestamp, sender, message_type, read_status, content = parts

        # 统计未读消息
        if read_status == "unread":
            unread_count += 1

            # 标记指定索引的消息或所有消息
            if message_index == 0 or message_index == unread_count:
                parts[3] = "read"
                updated_lines.append('|'.join(parts))
                marked_count += 1
            else:
                updated_lines.append(line)
        else:
            updated_lines.append(line)

    # 如果没有未读消息
    if unread_count == 0:
        if comm_type == "personal":
            return f"用户 '{username}' 没有未读消息。"
        else:
            return f"{file_description}没有未读消息。"

    # 如果指定的消息索引超出范围
    if message_index > unread_count:
        if comm_type == "personal":
            return f"错误: 消息索引 {message_index} 超出范围，用户 '{username}' 只有 {unread_count} 条未读消息。"
        else:
            return f"错误: 消息索引 {message_index} 超出范围，{file_description}只有 {unread_count} 条未读消息。"

    # 写入更新后的消息
    try:
        with open(full_message_file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(updated_lines))
    except Exception as e:
        return f"错误: 无法写入消息文件: {str(e)}"

    # 返回结果
    if message_index == 0:
        if comm_type == "personal":
            return f"已将用户 '{username}' 的所有 {marked_count} 条未读消息标记为已读。"
        else:
            return f"已将{file_description}的所有 {marked_count} 条未读消息标记为已读。"
    else:
        if comm_type == "personal":
            return f"已将用户 '{username}' 的第 {message_index} 条未读消息标记为已读。"
        else:
            return f"已将{file_description}的第 {message_index} 条未读消息标记为已读。"

def assign_task(
    task_id: Annotated[str, "任务ID，例如task_001"],
    username: Annotated[str, "要分配给的用户名"],
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    分配任务

    将任务分配给特定的团队成员
    """
    if project_root is None:
        project_root = os.getcwd()

    # 读取配置文件
    config_path = os.path.join(project_root, ".taskmasterconfig")
    if not os.path.isfile(config_path):
        return f"错误: 找不到配置文件。请先初始化项目。"

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError:
        return f"错误: 无法解析配置文件。"

    # 确保配置中有team字段
    if "team" not in config or "members" not in config["team"]:
        return f"错误: 项目中没有团队成员。"

    # 检查用户是否存在
    members = config["team"]["members"]
    user_exists = False

    for member in members:
        if member.get("username") == username:
            user_exists = True
            break

    if not user_exists:
        return f"错误: 找不到用户 '{username}'。"

    # 读取任务
    try:
        tasks_path = find_tasks_json_path(project_root)
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError as e:
        return f"错误: {str(e)}"

    # 查找任务
    found = False
    old_assignee = ""

    for task in tasks_data.get("tasks", []):
        if task.get("id") == task_id:
            old_assignee = task.get("assignee", "")
            task["assignee"] = username
            found = True
            break

        # 检查子任务
        if "subtasks" in task:
            for subtask in task["subtasks"]:
                if subtask.get("id") == task_id:
                    old_assignee = subtask.get("assignee", "")
                    subtask["assignee"] = username
                    found = True
                    break
            if found:
                break

    if not found:
        return f"错误: 找不到ID为 '{task_id}' 的任务"

    # 添加历史记录
    if old_assignee:
        add_task_history(
            task_id=task_id,
            action="任务分配",
            details=f"任务从 '{old_assignee}' 重新分配给 '{username}'",
            project_root=project_root
        )
    else:
        add_task_history(
            task_id=task_id,
            action="任务分配",
            details=f"任务分配给 '{username}'",
            project_root=project_root
        )

    # 保存更新后的任务
    save_tasks(tasks_data, tasks_path)

    # 获取任务标题
    task_title = ""
    for task in tasks_data.get("tasks", []):
        if task.get("id") == task_id:
            task_title = task.get("title", "")
            break

        # 检查子任务
        if "subtasks" in task:
            for subtask in task["subtasks"]:
                if subtask.get("id") == task_id:
                    task_title = subtask.get("title", "")
                    break
            if task_title:
                break

    # 发送通知消息
    task_info = f"任务 '{task_id}'"
    if task_title:
        task_info += f" ({task_title})"

    if old_assignee:
        message = f"{task_info} 已从 '{old_assignee}' 重新分配给你。"
        send_message(username, message, "task_assigned", project_root)
        result = f"任务 '{task_id}' 已从 '{old_assignee}' 重新分配给 '{username}'"
    else:
        message = f"{task_info} 已分配给你。"
        send_message(username, message, "task_assigned", project_root)
        result = f"任务 '{task_id}' 已分配给 '{username}'"

    return result

def initialize_project(
    project_name: Annotated[str, "项目名称"],
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None,
    description: Annotated[str, "项目描述"] = "",
    author: Annotated[str, "作者名称"] = ""
) -> str:
    """
    初始化一个新的TaskMaster项目

    创建必要的目录结构和配置文件，包括tasks.json和配置文件
    所有文件都存储在项目根目录的ProjectTask文件夹中
    """
    if project_root is None:
        project_root = os.getcwd()

    # 创建ProjectTask目录及其子目录
    project_task_dir = os.path.join(project_root, "ProjectTask")
    os.makedirs(project_task_dir, exist_ok=True)

    # 创建配置目录
    config_dir = os.path.join(project_task_dir, "config")
    os.makedirs(config_dir, exist_ok=True)

    # 创建通讯目录结构
    group_chat_dir = os.path.join(project_task_dir, "GroupChat")
    os.makedirs(group_chat_dir, exist_ok=True)

    # 创建个人通讯目录
    personal_chat_dir = os.path.join(group_chat_dir, "Personal")
    os.makedirs(personal_chat_dir, exist_ok=True)

    # 创建群组通讯目录
    groups_chat_dir = os.path.join(group_chat_dir, "Groups")
    os.makedirs(groups_chat_dir, exist_ok=True)

    # 创建归档目录（用于存储已离职成员或已解散群组的通讯记录）
    archive_dir = os.path.join(group_chat_dir, "Archive")
    os.makedirs(archive_dir, exist_ok=True)
    os.makedirs(os.path.join(archive_dir, "Personal"), exist_ok=True)
    os.makedirs(os.path.join(archive_dir, "Groups"), exist_ok=True)

    # 创建开发文档目录
    documents_dir = os.path.join(project_task_dir, "Documents")
    os.makedirs(documents_dir, exist_ok=True)
    os.makedirs(os.path.join(documents_dir, "Requirements"), exist_ok=True)
    os.makedirs(os.path.join(documents_dir, "Design"), exist_ok=True)
    os.makedirs(os.path.join(documents_dir, "API"), exist_ok=True)
    os.makedirs(os.path.join(documents_dir, "UserGuides"), exist_ok=True)
    os.makedirs(os.path.join(documents_dir, "Technical"), exist_ok=True)

    # 创建报告目录
    reports_dir = os.path.join(project_task_dir, "Reports")
    os.makedirs(reports_dir, exist_ok=True)

    # 创建导出目录
    exports_dir = os.path.join(project_task_dir, "Exports")
    os.makedirs(exports_dir, exist_ok=True)

    # 创建空的tasks.json
    tasks_path = os.path.join(config_dir, "tasks.json")
    tasks_data = {
        "tasks": [],
        "metadata": {
            "created": datetime.datetime.now().isoformat(),
            "project_name": project_name,
            "description": description,
            "author": author
        }
    }
    with open(tasks_path, 'w', encoding='utf-8') as f:
        json.dump(tasks_data, f, indent=2, ensure_ascii=False)

    # 创建team.json文件
    team_path = os.path.join(config_dir, "team.json")
    team_data = {
        "members": [],
        "groups": [],
        "roles": DEFAULT_CONFIG["team"]["roles"]
    }
    with open(team_path, 'w', encoding='utf-8') as f:
        json.dump(team_data, f, indent=2, ensure_ascii=False)

    # 创建配置文件
    config = DEFAULT_CONFIG.copy()
    config["global"]["projectName"] = project_name
    config_path = os.path.join(config_dir, "config.json")
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    # 创建README文件，说明目录结构
    readme_path = os.path.join(project_task_dir, "README.md")
    readme_content = f"""# {project_name} - TaskMaster项目

{description}

## 目录结构

- **config/**: 配置文件目录
  - tasks.json: 任务数据
  - team.json: 团队成员数据
  - config.json: 项目配置

- **GroupChat/**: 通讯文件目录
  - Personal/: 个人通讯文件
  - Groups/: 群组通讯文件（按层级组织，使用"上上级-上级-组名"的命名方式）
  - Archive/: 归档的通讯文件（存储已离职成员或已解散群组的通讯记录）

- **Documents/**: 开发文档目录
  - Requirements/: 需求文档
  - Design/: 设计文档
  - API/: API文档
  - UserGuides/: 用户指南
  - Technical/: 技术文档

- **Reports/**: 报告和统计数据

- **Exports/**: 导出的任务数据

## 创建时间

{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)

    # 创建兼容性链接文件，确保旧代码仍然可以工作
    compat_dir = os.path.join(project_root, ".taskmaster")
    os.makedirs(compat_dir, exist_ok=True)

    # 创建兼容性配置文件
    compat_config = {
        "project_task_dir": project_task_dir,
        "config_dir": config_dir,
        "tasks_path": tasks_path,
        "team_path": team_path
    }
    compat_config_path = os.path.join(project_root, ".taskmasterconfig")
    with open(compat_config_path, 'w', encoding='utf-8') as f:
        json.dump(compat_config, f, indent=2, ensure_ascii=False)

    return f"项目 '{project_name}' 已成功初始化于 {project_root}，项目文件存储在 'ProjectTask' 目录中"

def parse_prd(
    prd_file_path: Annotated[str, "PRD文档的路径"],
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None,
    num_tasks: Annotated[int, "要生成的最大任务数量，默认为0（不限制）"] = 0
) -> str:
    """
    解析PRD文档并生成任务

    读取PRD文档内容，分析并生成一系列任务，保存到tasks.json
    支持多种格式的PRD文件，包括Markdown、纯文本、HTML等
    能够识别前端开发中的HTML、CSS、JavaScript等关键组件
    """
    if project_root is None:
        project_root = os.getcwd()

    # 检查文件是否存在
    if not os.path.exists(prd_file_path):
        return f"错误: 找不到PRD文件 {prd_file_path}"

    # 获取文件扩展名
    file_ext = os.path.splitext(prd_file_path)[1].lower()

    # 读取PRD文件
    try:
        with open(prd_file_path, 'r', encoding='utf-8') as f:
            prd_content = f.read()
    except UnicodeDecodeError:
        # 尝试其他编码
        try:
            with open(prd_file_path, 'r', encoding='gbk') as f:
                prd_content = f.read()
        except:
            return f"错误: 无法读取PRD文件 {prd_file_path}，请检查文件编码"
    except FileNotFoundError:
        return f"错误: 找不到PRD文件 {prd_file_path}"
    except Exception as e:
        return f"错误: 读取PRD文件时出错: {str(e)}"

    # 查找tasks.json路径
    try:
        tasks_path = find_tasks_json_path(project_root)
    except FileNotFoundError:
        # 如果找不到，尝试初始化项目
        taskmaster_dir = os.path.join(project_root, ".taskmaster")
        os.makedirs(taskmaster_dir, exist_ok=True)
        tasks_path = os.path.join(taskmaster_dir, "tasks.json")

    # 加载现有任务或创建新的任务数据
    try:
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError:
        tasks_data = {"tasks": [], "metadata": {"created": datetime.datetime.now().isoformat()}}

    # 获取现有任务列表
    existing_tasks = tasks_data.get("tasks", [])

    # 根据文件类型进行预处理
    if file_ext in ['.md', '.markdown']:
        # Markdown文件处理
        tasks = extract_tasks_from_markdown(prd_content, existing_tasks, num_tasks)
    elif file_ext in ['.html', '.htm']:
        # HTML文件处理
        tasks = extract_tasks_from_html(prd_content, existing_tasks, num_tasks)
    else:
        # 默认文本处理
        tasks = extract_tasks_from_text(prd_content, existing_tasks, num_tasks)

    # 添加到现有任务
    tasks_data["tasks"].extend(tasks)

    # 保存任务
    save_tasks(tasks_data, tasks_path)

    return f"已从PRD生成 {len(tasks)} 个任务并保存到 {tasks_path}"

def extract_tasks_from_markdown(content: str, num_tasks: int = 0) -> list:
    """从Markdown内容中提取任务"""
    tasks = []

    # 分析Markdown标题和列表
    lines = content.split('\n')
    current_section = ""
    section_content = []

    # 提取Markdown结构
    for line in lines:
        # 检查是否是标题行
        if line.strip().startswith('#'):
            # 如果有之前的章节，处理它
            if current_section and section_content:
                section_tasks = process_section(current_section, section_content, tasks)
                tasks.extend(section_tasks)
                section_content = []

            # 提取新章节标题
            current_section = line.strip().lstrip('#').strip()
            continue

        # 将行添加到当前章节
        section_content.append(line)

    # 处理最后一个章节
    if current_section and section_content:
        section_tasks = process_section(current_section, section_content, tasks)
        tasks.extend(section_tasks)

    # 检查是否有前端开发相关内容
    frontend_tasks = extract_frontend_tasks(content, tasks)
    tasks.extend(frontend_tasks)

    # 限制任务数量
    if num_tasks > 0 and len(tasks) > num_tasks:
        tasks = tasks[:num_tasks]

    return tasks

def extract_tasks_from_html(content: str, num_tasks: int = 0) -> list:
    """从HTML内容中提取任务"""
    tasks = []

    # 尝试提取HTML结构中的任务
    # 查找HTML、CSS、JavaScript相关内容
    html_pattern = re.compile(r'<html.*?>|<body.*?>|<div.*?>|<section.*?>', re.IGNORECASE)
    css_pattern = re.compile(r'<style.*?>|\.css|#[a-zA-Z][-_a-zA-Z0-9]*', re.IGNORECASE)
    js_pattern = re.compile(r'<script.*?>|function\s+[a-zA-Z]|addEventListener|querySelector', re.IGNORECASE)

    # 检测HTML组件
    if html_pattern.search(content):
        tasks.append({
            "id": f"task_{len(tasks) + 1:03d}",
            "title": "实现HTML页面结构",
            "description": "创建网页的基本HTML结构，包括必要的元素和布局",
            "status": "pending",
            "priority": "high",
            "dependencies": [],
            "subtasks": [],
            "tags": ["HTML", "前端"]
        })

    # 检测CSS样式
    if css_pattern.search(content):
        tasks.append({
            "id": f"task_{len(tasks) + 1:03d}",
            "title": "开发CSS样式",
            "description": "为网页元素创建样式，实现设计要求的视觉效果",
            "status": "pending",
            "priority": "medium",
            "dependencies": [],
            "subtasks": [],
            "tags": ["CSS", "样式", "前端"]
        })

    # 检测JavaScript功能
    if js_pattern.search(content):
        tasks.append({
            "id": f"task_{len(tasks) + 1:03d}",
            "title": "实现JavaScript交互功能",
            "description": "开发网页的交互功能，处理用户事件和数据操作",
            "status": "pending",
            "priority": "high",
            "dependencies": [],
            "subtasks": [],
            "tags": ["JavaScript", "交互", "前端"]
        })

    # 提取HTML文档中的文本内容
    text_content = re.sub(r'<[^>]*>', ' ', content)
    text_tasks = extract_tasks_from_text(text_content, 0)  # 不限制数量，后面会统一处理
    tasks.extend(text_tasks)

    # 限制任务数量
    if num_tasks > 0 and len(tasks) > num_tasks:
        tasks = tasks[:num_tasks]

    return tasks

def extract_tasks_from_text(content: str, num_tasks: int = 0) -> list:
    """从纯文本内容中提取任务"""
    potential_tasks = []
    lines = content.split('\n')

    # 1. 检查数字列表项和符号列表项
    for i, line in enumerate(lines):
        # 检查数字列表项（如"1. 实现用户登录功能"）
        numbered_match = re.match(r'^\s*\d+\.\s*(.*)', line.strip())
        if numbered_match:
            task_title = numbered_match.group(1).strip()
            if task_title:
                potential_tasks.append({
                    "id": f"task_{len(potential_tasks) + 1:03d}",
                    "title": task_title,
                    "description": task_title,
                    "status": "pending",
                    "priority": "medium",
                    "dependencies": [],
                    "subtasks": []
                })
                continue

        # 检查符号列表项（如"- 实现用户登录功能"或"* 实现用户登录功能"）
        symbol_match = re.match(r'^\s*[-*•]\s*(.*)', line.strip())
        if symbol_match:
            task_title = symbol_match.group(1).strip()
            if task_title:
                potential_tasks.append({
                    "id": f"task_{len(potential_tasks) + 1:03d}",
                    "title": task_title,
                    "description": task_title,
                    "status": "pending",
                    "priority": "medium",
                    "dependencies": [],
                    "subtasks": []
                })
                continue

        # 2. 检查以动词开头的短句
        if re.match(r'^[A-Z实现创建开发设计构建添加修改更新].*[^。？！.?!]$', line.strip()):
            potential_tasks.append({
                "id": f"task_{len(potential_tasks) + 1:03d}",
                "title": line.strip(),
                "description": line.strip(),
                "status": "pending",
                "priority": "medium",
                "dependencies": [],
                "subtasks": []
            })

    # 检查前端开发相关内容
    frontend_tasks = extract_frontend_tasks(content)
    potential_tasks.extend(frontend_tasks)

    # 限制任务数量
    if num_tasks > 0 and len(potential_tasks) > num_tasks:
        potential_tasks = potential_tasks[:num_tasks]

    return potential_tasks

def process_section(section_title: str, section_lines: list) -> list:
    """处理Markdown文档的一个章节，提取任务"""
    tasks = []

    # 合并章节内容
    section_content = '\n'.join(section_lines)

    # 查找列表项
    list_items = re.findall(r'^\s*[-*•]\s*(.*?)$|^\s*\d+\.\s*(.*?)$', section_content, re.MULTILINE)

    for item in list_items:
        # 列表项可能在第一个或第二个捕获组中
        task_title = item[0] if item[0] else item[1]
        if task_title:
            tasks.append({
                "id": f"task_{len(tasks) + 1:03d}",
                "title": task_title,
                "description": f"{task_title} (来自章节: {section_title})",
                "status": "pending",
                "priority": "medium",
                "dependencies": [],
                "subtasks": []
            })

    return tasks

def extract_frontend_tasks(content: str) -> list:
    """提取前端开发相关的任务"""
    tasks = []

    # 前端开发关键词和对应的任务
    frontend_categories = [
        {
            "keywords": ["html", "标签", "元素", "dom", "文档结构", "语义化"],
            "task": {
                "title": "实现HTML页面结构",
                "description": "创建网页的基本HTML结构，包括必要的元素和语义化标签",
                "tags": ["HTML", "前端"]
            }
        },
        {
            "keywords": ["css", "样式", "布局", "响应式", "flexbox", "grid", "动画", "媒体查询", "sass", "less"],
            "task": {
                "title": "开发CSS样式",
                "description": "为网页元素创建样式，实现响应式布局和视觉效果",
                "tags": ["CSS", "样式", "前端"]
            }
        },
        {
            "keywords": ["javascript", "js", "交互", "事件", "函数", "api", "ajax", "fetch", "异步", "promise"],
            "task": {
                "title": "实现JavaScript交互功能",
                "description": "开发网页的交互功能，处理用户事件和数据操作",
                "tags": ["JavaScript", "交互", "前端"]
            }
        },
        {
            "keywords": ["react", "vue", "angular", "框架", "组件", "状态管理", "redux", "vuex", "hooks"],
            "task": {
                "title": "集成前端框架",
                "description": "使用现代前端框架构建应用，实现组件化开发和状态管理",
                "tags": ["框架", "前端"]
            }
        },
        {
            "keywords": ["ui", "界面", "用户体验", "ux", "设计", "原型", "交互设计", "可用性", "可访问性"],
            "task": {
                "title": "设计用户界面",
                "description": "创建用户友好的界面设计，提升用户体验和可用性",
                "tags": ["UI", "设计", "前端"]
            }
        },
        {
            "keywords": ["测试", "单元测试", "集成测试", "e2e", "jest", "cypress", "测试用例"],
            "task": {
                "title": "前端测试",
                "description": "编写并执行前端测试，确保功能正常和代码质量",
                "tags": ["测试", "前端"]
            }
        },
        {
            "keywords": ["性能", "优化", "加载速度", "懒加载", "代码分割", "缓存", "bundle", "webpack"],
            "task": {
                "title": "前端性能优化",
                "description": "优化前端代码和资源，提高应用性能和加载速度",
                "tags": ["性能", "优化", "前端"]
            }
        },
        {
            "keywords": ["移动端", "适配", "触摸", "手势", "pwa", "app", "移动优先"],
            "task": {
                "title": "移动端适配",
                "description": "确保应用在移动设备上的良好体验，实现响应式设计",
                "tags": ["移动端", "前端"]
            }
        }
    ]

    # 检查内容中是否包含前端开发关键词
    for category in frontend_categories:
        for keyword in category["keywords"]:
            if re.search(r'\b' + keyword + r'\b', content.lower()):
                # 检查是否已经添加了这个类别的任务
                if not any(task["title"] == category["task"]["title"] for task in tasks):
                    task_data = {
                        "id": f"task_{len(tasks) + 1:03d}",
                        "title": category["task"]["title"],
                        "description": category["task"]["description"],
                        "status": "pending",
                        "priority": "medium",
                        "dependencies": [],
                        "subtasks": [],
                        "tags": category["task"]["tags"]
                    }
                    tasks.append(task_data)
                break  # 找到一个关键词就跳出内部循环

    # 如果检测到多个前端任务，设置适当的依赖关系
    if len(tasks) > 1:
        # 查找HTML任务
        html_task = next((task for task in tasks if "HTML" in task.get("tags", [])), None)
        # 查找CSS任务
        css_task = next((task for task in tasks if "CSS" in task.get("tags", [])), None)
        # 查找JavaScript任务
        js_task = next((task for task in tasks if "JavaScript" in task.get("tags", [])), None)
        # 查找框架任务
        framework_task = next((task for task in tasks if "框架" in task.get("tags", [])), None)

        # 设置依赖关系
        if html_task and css_task:
            css_task["dependencies"].append(html_task["id"])
        if html_task and js_task:
            js_task["dependencies"].append(html_task["id"])
        if framework_task:
            if html_task:
                framework_task["dependencies"].append(html_task["id"])
            if css_task:
                framework_task["dependencies"].append(css_task["id"])
            if js_task:
                framework_task["dependencies"].append(js_task["id"])

    return tasks
def extract_tasks_from_markdown(content: str, existing_tasks: list, num_tasks: int = 0) -> list:
    """从Markdown内容中提取任务"""
    tasks = []

    # 分析Markdown标题和列表
    lines = content.split('\n')
    current_section = ""
    section_content = []

    # 提取Markdown结构
    for line in lines:
        # 检查是否是标题行
        if line.strip().startswith('#'):
            # 如果有之前的章节，处理它
            if current_section and section_content:
                section_tasks = process_section(current_section, section_content, existing_tasks)
                tasks.extend(section_tasks)
                section_content = []

            # 提取新章节标题
            current_section = line.strip().lstrip('#').strip()
            continue

        # 将行添加到当前章节
        section_content.append(line)

    # 处理最后一个章节
    if current_section and section_content:
        section_tasks = process_section(current_section, section_content, existing_tasks)
        tasks.extend(section_tasks)

    # 检查是否有前端开发相关内容
    frontend_tasks = extract_frontend_tasks(content, existing_tasks)
    tasks.extend(frontend_tasks)

    # 限制任务数量
    if num_tasks > 0 and len(tasks) > num_tasks:
        tasks = tasks[:num_tasks]

    return tasks

def extract_tasks_from_html(content: str, existing_tasks: list, num_tasks: int = 0) -> list:
    """从HTML内容中提取任务"""
    tasks = []

    # 尝试提取HTML结构中的任务
    # 查找HTML、CSS、JavaScript相关内容
    html_pattern = re.compile(r'<html.*?>|<body.*?>|<div.*?>|<section.*?>', re.IGNORECASE)
    css_pattern = re.compile(r'<style.*?>|\.css|#[a-zA-Z][-_a-zA-Z0-9]*', re.IGNORECASE)
    js_pattern = re.compile(r'<script.*?>|function\s+[a-zA-Z]|addEventListener|querySelector', re.IGNORECASE)

    # 检测HTML组件
    if html_pattern.search(content):
        if not any(task["title"].startswith("实现HTML页面结构") for task in existing_tasks + tasks):
            tasks.append({
                "id": f"task_{len(existing_tasks + tasks) + 1:03d}",
                "title": "实现HTML页面结构",
                "description": "创建网页的基本HTML结构，包括必要的元素和布局",
                "status": "pending",
                "priority": "high",
                "dependencies": [],
                "subtasks": [],
                "tags": ["HTML", "前端"]
            })

    # 检测CSS样式
    if css_pattern.search(content):
        if not any(task["title"].startswith("开发CSS样式") for task in existing_tasks + tasks):
            tasks.append({
                "id": f"task_{len(existing_tasks + tasks) + 1:03d}",
                "title": "开发CSS样式",
                "description": "为网页元素创建样式，实现设计要求的视觉效果",
                "status": "pending",
                "priority": "medium",
                "dependencies": [],
                "subtasks": [],
                "tags": ["CSS", "样式", "前端"]
            })

    # 检测JavaScript功能
    if js_pattern.search(content):
        if not any(task["title"].startswith("实现JavaScript交互功能") for task in existing_tasks + tasks):
            tasks.append({
                "id": f"task_{len(existing_tasks + tasks) + 1:03d}",
                "title": "实现JavaScript交互功能",
                "description": "开发网页的交互功能，处理用户事件和数据操作",
                "status": "pending",
                "priority": "high",
                "dependencies": [],
                "subtasks": [],
                "tags": ["JavaScript", "交互", "前端"]
            })

    # 提取HTML文档中的文本内容
    text_content = re.sub(r'<[^>]*>', ' ', content)
    text_tasks = extract_tasks_from_text(text_content, existing_tasks)  # 不限制数量，后面会统一处理
    tasks.extend(text_tasks)

    # 限制任务数量
    if num_tasks > 0 and len(tasks) > num_tasks:
        tasks = tasks[:num_tasks]

    return tasks

def extract_tasks_from_text(content: str, existing_tasks: list, num_tasks: int = 0) -> list:
    """从纯文本内容中提取任务"""
    potential_tasks = []
    lines = content.split('\n')

    # 1. 检查数字列表项和符号列表项
    for i, line in enumerate(lines):
        # 检查数字列表项（如"1. 实现用户登录功能"）
        numbered_match = re.match(r'^\s*\d+\.\s*(.*)', line.strip())
        if numbered_match:
            task_title = numbered_match.group(1).strip()
            if task_title:
                potential_tasks.append({
                    "id": f"task_{len(existing_tasks + potential_tasks) + 1:03d}",
                    "title": task_title,
                    "description": task_title,
                    "status": "pending",
                    "priority": "medium",
                    "dependencies": [],
                    "subtasks": []
                })
                continue

        # 检查符号列表项（如"- 实现用户登录功能"或"* 实现用户登录功能"）
        symbol_match = re.match(r'^\s*[-*•]\s*(.*)', line.strip())
        if symbol_match:
            task_title = symbol_match.group(1).strip()
            if task_title:
                potential_tasks.append({
                    "id": f"task_{len(existing_tasks + potential_tasks) + 1:03d}",
                    "title": task_title,
                    "description": task_title,
                    "status": "pending",
                    "priority": "medium",
                    "dependencies": [],
                    "subtasks": []
                })
                continue

        # 2. 检查以动词开头的短句
        if re.match(r'^[A-Z实现创建开发设计构建添加修改更新].*[^。？！.?!]$', line.strip()):
            potential_tasks.append({
                "id": f"task_{len(existing_tasks + potential_tasks) + 1:03d}",
                "title": line.strip(),
                "description": line.strip(),
                "status": "pending",
                "priority": "medium",
                "dependencies": [],
                "subtasks": []
            })

    # 检查前端开发相关内容
    frontend_tasks = extract_frontend_tasks(content, existing_tasks)
    potential_tasks.extend(frontend_tasks)

    # 限制任务数量
    if num_tasks > 0 and len(potential_tasks) > num_tasks:
        potential_tasks = potential_tasks[:num_tasks]

    return potential_tasks

def process_section(section_title: str, section_lines: list, existing_tasks: list) -> list:
    """处理Markdown文档的一个章节，提取任务"""
    tasks = []

    # 合并章节内容
    section_content = '\n'.join(section_lines)

    # 查找列表项
    list_items = re.findall(r'^\s*[-*•]\s*(.*?)$|^\s*\d+\.\s*(.*?)$', section_content, re.MULTILINE)

    for item in list_items:
        # 列表项可能在第一个或第二个捕获组中
        task_title = item[0] if item[0] else item[1]
        if task_title:
            tasks.append({
                "id": f"task_{len(existing_tasks + tasks) + 1:03d}",
                "title": task_title,
                "description": f"{task_title} (来自章节: {section_title})",
                "status": "pending",
                "priority": "medium",
                "dependencies": [],
                "subtasks": []
            })

    return tasks

def extract_frontend_tasks(content: str, existing_tasks: list) -> list:
    """提取前端开发相关的任务"""
    tasks = []

    # 前端开发关键词
    frontend_keywords = {
        "HTML": ["html", "标签", "元素", "dom", "文档结构"],
        "CSS": ["css", "样式", "布局", "响应式", "flexbox", "grid", "动画"],
        "JavaScript": ["javascript", "js", "交互", "事件", "函数", "api", "ajax", "fetch"],
        "框架": ["react", "vue", "angular", "框架", "组件"],
        "UI": ["ui", "界面", "用户体验", "ux", "设计", "原型"]
    }

    # 检查内容中是否包含前端开发关键词
    for category, keywords in frontend_keywords.items():
        for keyword in keywords:
            if re.search(r'\b' + keyword + r'\b', content.lower()):
                # 根据类别创建相应的任务
                if category == "HTML" and not any(task["title"].startswith("实现HTML") for task in existing_tasks + tasks):
                    tasks.append({
                        "id": f"task_{len(existing_tasks + tasks) + 1:03d}",
                        "title": "实现HTML页面结构",
                        "description": "创建网页的基本HTML结构，包括必要的元素和布局",
                        "status": "pending",
                        "priority": "high",
                        "dependencies": [],
                        "subtasks": [],
                        "tags": ["HTML", "前端"]
                    })
                elif category == "CSS" and not any(task["title"].startswith("开发CSS") for task in existing_tasks + tasks):
                    tasks.append({
                        "id": f"task_{len(existing_tasks + tasks) + 1:03d}",
                        "title": "开发CSS样式",
                        "description": "为网页元素创建样式，实现设计要求的视觉效果",
                        "status": "pending",
                        "priority": "medium",
                        "dependencies": [],
                        "subtasks": [],
                        "tags": ["CSS", "样式", "前端"]
                    })
                elif category == "JavaScript" and not any(task["title"].startswith("实现JavaScript交互功能") for task in existing_tasks + tasks):
                    tasks.append({
                        "id": f"task_{len(existing_tasks + tasks) + 1:03d}",
                        "title": "实现JavaScript交互功能",
                        "description": "开发网页的交互功能，处理用户事件和数据操作",
                        "status": "pending",
                        "priority": "high",
                        "dependencies": [],
                        "subtasks": [],
                        "tags": ["JavaScript", "交互", "前端"]
                    })
                elif category == "框架" and not any(task["title"].startswith("集成前端框架") for task in existing_tasks + tasks):
                    tasks.append({
                        "id": f"task_{len(existing_tasks + tasks) + 1:03d}",
                        "title": "集成前端框架",
                        "description": "使用现代前端框架构建应用，实现组件化开发",
                        "status": "pending",
                        "priority": "high",
                        "dependencies": [],
                        "subtasks": [],
                        "tags": ["框架", "前端"]
                    })
                elif category == "UI" and not any(task["title"].startswith("设计用户界面") for task in existing_tasks + tasks):
                    tasks.append({
                        "id": f"task_{len(existing_tasks + tasks) + 1:03d}",
                        "title": "设计用户界面",
                        "description": "创建用户友好的界面设计，提升用户体验",
                        "status": "pending",
                        "priority": "medium",
                        "dependencies": [],
                        "subtasks": [],
                        "tags": ["UI", "设计", "前端"]
                    })
                break  # 找到一个关键词就跳出内部循环

    return tasks

def clean_json_string(json_str: str) -> str:
    """
    清理JSON字符串，修复常见的格式问题

    处理以下问题：
    1. 多余的逗号
    2. 缺少引号的键
    3. 单引号替换为双引号
    4. 未闭合的括号
    """
    # 移除注释
    json_str = re.sub(r'//.*?$|/\*.*?\*/', '', json_str, flags=re.MULTILINE | re.DOTALL)

    # 替换单引号为双引号
    json_str = re.sub(r'(?<!\\)\'', '"', json_str)

    # 修复键没有引号的问题
    json_str = re.sub(r'([{,])\s*([a-zA-Z0-9_]+)\s*:', r'\1"\2":', json_str)

    # 修复多余的逗号
    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)

    # 检查并修复未闭合的括号
    open_braces = json_str.count('{')
    close_braces = json_str.count('}')
    open_brackets = json_str.count('[')
    close_brackets = json_str.count(']')

    # 添加缺少的闭合括号
    if open_braces > close_braces:
        json_str += '}' * (open_braces - close_braces)
    if open_brackets > close_brackets:
        json_str += ']' * (open_brackets - close_brackets)

    return json_str

def validate_json_structure(json_obj: dict, schema: dict) -> Tuple[bool, List[str]]:
    """
    验证JSON对象是否符合指定的结构

    Args:
        json_obj: 要验证的JSON对象
        schema: 期望的结构模式

    Returns:
        (is_valid, errors): 是否有效及错误信息
    """
    errors = []

    # 检查必需字段
    for key, value in schema.items():
        if key not in json_obj:
            errors.append(f"缺少必需字段: {key}")
        elif isinstance(value, dict) and isinstance(json_obj[key], dict):
            # 递归验证嵌套结构
            is_valid, nested_errors = validate_json_structure(json_obj[key], value)
            if not is_valid:
                errors.extend([f"{key}.{err}" for err in nested_errors])
        elif isinstance(value, list) and isinstance(json_obj[key], list):
            # 验证列表中的每个元素
            if value and json_obj[key]:  # 如果模式列表和数据列表都不为空
                schema_item = value[0]  # 使用列表中的第一个元素作为模式
                for i, item in enumerate(json_obj[key]):
                    if isinstance(schema_item, dict) and isinstance(item, dict):
                        is_valid, nested_errors = validate_json_structure(item, schema_item)
                        if not is_valid:
                            errors.extend([f"{key}[{i}].{err}" for err in nested_errors])

    return len(errors) == 0, errors

def safe_json_loads(json_str: str) -> Tuple[bool, Optional[dict], Optional[str]]:
    """
    安全地解析JSON字符串，处理可能的格式错误

    Args:
        json_str: JSON字符串

    Returns:
        (success, result, error): 成功标志、解析结果或错误信息
    """
    try:
        # 尝试直接解析
        result = json.loads(json_str)
        return True, result, None
    except json.JSONDecodeError as e:
        try:
            # 尝试清理并重新解析
            cleaned_json = clean_json_string(json_str)
            result = json.loads(cleaned_json)
            return True, result, None
        except json.JSONDecodeError as e2:
            # 如果仍然失败，返回错误
            return False, None, f"JSON解析错误: {str(e2)}"

# 核心功能函数

def list_tasks(
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None,
    status: Annotated[Optional[str], "筛选特定状态的任务 (pending, in_progress, done, deferred)"] = None,
    with_subtasks: Annotated[bool, "是否包含子任务"] = False
) -> str:
    """
    列出所有任务

    显示任务ID、状态和标题，可选择按状态筛选
    """
    if project_root is None:
        project_root = os.getcwd()

    try:
        tasks_path = find_tasks_json_path(project_root)
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError as e:
        return f"错误: {str(e)}"

    tasks = tasks_data.get("tasks", [])

    if status:
        if status not in TASK_STATUS:
            return f"错误: 无效的状态 '{status}'。有效状态: {', '.join(TASK_STATUS)}"
        tasks = [task for task in tasks if task.get("status") == status]

    if not tasks:
        return "没有找到任务。"

    # 格式化输出
    result = []
    for task in tasks:
        task_id = task.get("id", "unknown")
        task_status = task.get("status", "pending")
        task_title = task.get("title", "无标题")
        task_priority = task.get("priority", "medium")

        result.append(f"[{task_id}] [{task_status}] [{task_priority}] {task_title}")

        if with_subtasks and "subtasks" in task and task["subtasks"]:
            for subtask in task["subtasks"]:
                subtask_id = subtask.get("id", "unknown")
                subtask_status = subtask.get("status", "pending")
                subtask_title = subtask.get("title", "无标题")

                result.append(f"  └─ [{subtask_id}] [{subtask_status}] {subtask_title}")

    return "\n".join(result)

def add_task_tag(
    task_id: Annotated[str, "任务ID，例如task_001"],
    tag: Annotated[str, "要添加的标签"],
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    为任务添加标签

    向指定任务添加一个标签
    """
    if project_root is None:
        project_root = os.getcwd()

    try:
        tasks_path = find_tasks_json_path(project_root)
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError as e:
        return f"错误: {str(e)}"

    # 查找任务
    found = False
    for task in tasks_data.get("tasks", []):
        if task.get("id") == task_id:
            # 确保任务有tags字段
            if "tags" not in task:
                task["tags"] = []

            # 检查标签是否已存在
            if tag in task["tags"]:
                return f"任务 '{task_id}' 已有标签 '{tag}'"

            # 添加标签
            task["tags"].append(tag)
            found = True
            break

        # 检查子任务
        if "subtasks" in task:
            for subtask in task["subtasks"]:
                if subtask.get("id") == task_id:
                    # 确保子任务有tags字段
                    if "tags" not in subtask:
                        subtask["tags"] = []

                    # 检查标签是否已存在
                    if tag in subtask["tags"]:
                        return f"子任务 '{task_id}' 已有标签 '{tag}'"

                    # 添加标签
                    subtask["tags"].append(tag)
                    found = True
                    break
            if found:
                break

    if not found:
        return f"错误: 找不到ID为 '{task_id}' 的任务"

    # 保存更新后的任务
    save_tasks(tasks_data, tasks_path)

    return f"已为任务 '{task_id}' 添加标签 '{tag}'"

def remove_task_tag(
    task_id: Annotated[str, "任务ID，例如task_001"],
    tag: Annotated[str, "要移除的标签"],
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    从任务中移除标签

    从指定任务中移除一个标签
    """
    if project_root is None:
        project_root = os.getcwd()

    try:
        tasks_path = find_tasks_json_path(project_root)
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError as e:
        return f"错误: {str(e)}"

    # 查找任务
    found = False
    tag_removed = False

    for task in tasks_data.get("tasks", []):
        if task.get("id") == task_id:
            # 确保任务有tags字段
            if "tags" not in task or tag not in task["tags"]:
                return f"任务 '{task_id}' 没有标签 '{tag}'"

            # 移除标签
            task["tags"].remove(tag)
            found = True
            tag_removed = True
            break

        # 检查子任务
        if "subtasks" in task:
            for subtask in task["subtasks"]:
                if subtask.get("id") == task_id:
                    # 确保子任务有tags字段
                    if "tags" not in subtask or tag not in subtask["tags"]:
                        return f"子任务 '{task_id}' 没有标签 '{tag}'"

                    # 移除标签
                    subtask["tags"].remove(tag)
                    found = True
                    tag_removed = True
                    break
            if found:
                break

    if not found:
        return f"错误: 找不到ID为 '{task_id}' 的任务"

    if not tag_removed:
        return f"任务 '{task_id}' 没有标签 '{tag}'"

    # 保存更新后的任务
    save_tasks(tasks_data, tasks_path)

    return f"已从任务 '{task_id}' 移除标签 '{tag}'"

def list_task_tags(
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    列出所有任务标签

    显示项目中使用的所有标签及其使用次数
    """
    if project_root is None:
        project_root = os.getcwd()

    try:
        tasks_path = find_tasks_json_path(project_root)
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError as e:
        return f"错误: {str(e)}"

    # 收集所有标签
    tag_counts = {}

    for task in tasks_data.get("tasks", []):
        # 收集主任务标签
        for tag in task.get("tags", []):
            if tag in tag_counts:
                tag_counts[tag] += 1
            else:
                tag_counts[tag] = 1

        # 收集子任务标签
        for subtask in task.get("subtasks", []):
            for tag in subtask.get("tags", []):
                if tag in tag_counts:
                    tag_counts[tag] += 1
                else:
                    tag_counts[tag] = 1

    # 生成报告
    if not tag_counts:
        return "项目中没有使用任何标签。"

    # 按使用次数排序
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)

    report = ["项目中使用的标签:"]
    for tag, count in sorted_tags:
        report.append(f"  - {tag}: {count} 个任务")

    return "\n".join(report)

def search_tasks(
    keyword: Annotated[str, "搜索关键词"],
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None,
    search_title: Annotated[bool, "是否搜索标题"] = True,
    search_description: Annotated[bool, "是否搜索描述"] = True,
    search_tags: Annotated[bool, "是否搜索标签"] = True,
    status: Annotated[Optional[str], "筛选特定状态的任务"] = None
) -> str:
    """
    搜索任务

    按关键词搜索任务，可以指定搜索范围和状态筛选
    """
    if project_root is None:
        project_root = os.getcwd()

    # 验证状态
    if status is not None and status not in TASK_STATUS:
        return f"错误: 无效的状态 '{status}'。有效状态: {', '.join(TASK_STATUS)}"

    try:
        tasks_path = find_tasks_json_path(project_root)
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError as e:
        return f"错误: {str(e)}"

    # 搜索任务
    matching_tasks = []
    matching_subtasks = []

    for task in tasks_data.get("tasks", []):
        # 如果指定了状态筛选，跳过不匹配的任务
        if status is not None and task.get("status") != status:
            continue

        # 检查主任务是否匹配
        task_matches = False
        match_reason = ""

        # 搜索标题
        if search_title and keyword.lower() in task.get("title", "").lower():
            task_matches = True
            match_reason = "标题"

        # 搜索描述
        if not task_matches and search_description and keyword.lower() in task.get("description", "").lower():
            task_matches = True
            match_reason = "描述"

        # 搜索标签
        if not task_matches and search_tags:
            for tag in task.get("tags", []):
                if keyword.lower() in tag.lower():
                    task_matches = True
                    match_reason = f"标签 '{tag}'"
                    break

        # 如果任务匹配，添加到结果中
        if task_matches:
            task_copy = task.copy()
            task_copy["match_reason"] = match_reason
            matching_tasks.append(task_copy)

        # 检查子任务
        for subtask in task.get("subtasks", []):
            # 如果指定了状态筛选，跳过不匹配的子任务
            if status is not None and subtask.get("status") != status:
                continue

            # 检查子任务是否匹配
            subtask_matches = False
            subtask_match_reason = ""

            # 搜索标题
            if search_title and keyword.lower() in subtask.get("title", "").lower():
                subtask_matches = True
                subtask_match_reason = "标题"

            # 搜索描述
            if not subtask_matches and search_description and keyword.lower() in subtask.get("description", "").lower():
                subtask_matches = True
                subtask_match_reason = "描述"

            # 搜索标签
            if not subtask_matches and search_tags:
                for tag in subtask.get("tags", []):
                    if keyword.lower() in tag.lower():
                        subtask_matches = True
                        subtask_match_reason = f"标签 '{tag}'"
                        break

            # 如果子任务匹配，添加到结果中
            if subtask_matches:
                subtask_copy = subtask.copy()
                subtask_copy["parent_id"] = task.get("id")
                subtask_copy["match_reason"] = subtask_match_reason
                matching_subtasks.append(subtask_copy)

    # 生成报告
    if not matching_tasks and not matching_subtasks:
        if status is not None:
            return f"没有找到状态为 '{status}' 且包含关键词 '{keyword}' 的任务。"
        else:
            return f"没有找到包含关键词 '{keyword}' 的任务。"

    report = [f"搜索关键词 '{keyword}' 的结果:"]

    # 主任务
    if matching_tasks:
        report.append("\n主任务:")
        for task in matching_tasks:
            task_id = task.get("id", "unknown")
            task_status = task.get("status", "pending")
            task_priority = task.get("priority", "medium")
            task_title = task.get("title", "无标题")
            match_reason = task.get("match_reason", "")

            report.append(f"  - [{task_id}] [{task_status}] [{task_priority}] {task_title} (匹配: {match_reason})")

    # 子任务
    if matching_subtasks:
        report.append("\n子任务:")
        for subtask in matching_subtasks:
            subtask_id = subtask.get("id", "unknown")
            subtask_status = subtask.get("status", "pending")
            subtask_title = subtask.get("title", "无标题")
            parent_id = subtask.get("parent_id", "unknown")
            match_reason = subtask.get("match_reason", "")

            report.append(f"  - [{subtask_id}] [{subtask_status}] {subtask_title} (父任务: {parent_id}, 匹配: {match_reason})")

    return "\n".join(report)

def find_tasks_by_tag(
    tag: Annotated[str, "要查找的标签"],
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    按标签查找任务

    查找具有指定标签的所有任务
    """
    if project_root is None:
        project_root = os.getcwd()

    try:
        tasks_path = find_tasks_json_path(project_root)
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError as e:
        return f"错误: {str(e)}"

    # 查找具有指定标签的任务
    matching_tasks = []
    matching_subtasks = []

    for task in tasks_data.get("tasks", []):
        # 检查主任务
        if "tags" in task and tag in task["tags"]:
            matching_tasks.append(task)

        # 检查子任务
        for subtask in task.get("subtasks", []):
            if "tags" in subtask and tag in subtask["tags"]:
                # 保存子任务和父任务ID
                subtask["parent_id"] = task.get("id")
                matching_subtasks.append(subtask)

    # 生成报告
    if not matching_tasks and not matching_subtasks:
        return f"没有找到具有标签 '{tag}' 的任务。"

    report = [f"具有标签 '{tag}' 的任务:"]

    # 主任务
    if matching_tasks:
        report.append("\n主任务:")
        for task in matching_tasks:
            task_id = task.get("id", "unknown")
            task_status = task.get("status", "pending")
            task_priority = task.get("priority", "medium")
            task_title = task.get("title", "无标题")

            report.append(f"  - [{task_id}] [{task_status}] [{task_priority}] {task_title}")

    # 子任务
    if matching_subtasks:
        report.append("\n子任务:")
        for subtask in matching_subtasks:
            subtask_id = subtask.get("id", "unknown")
            subtask_status = subtask.get("status", "pending")
            subtask_title = subtask.get("title", "无标题")
            parent_id = subtask.get("parent_id", "unknown")

            report.append(f"  - [{subtask_id}] [{subtask_status}] {subtask_title} (父任务: {parent_id})")

    return "\n".join(report)

def set_task_priority(
    task_id: Annotated[str, "任务ID，例如task_001"],
    priority: Annotated[str, "新优先级 (high, medium, low)"],
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    设置任务优先级

    更新指定任务的优先级
    """
    if project_root is None:
        project_root = os.getcwd()

    if priority not in TASK_PRIORITY:
        return f"错误: 无效的优先级 '{priority}'。有效优先级: {', '.join(TASK_PRIORITY)}"

    try:
        tasks_path = find_tasks_json_path(project_root)
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError as e:
        return f"错误: {str(e)}"

    # 查找任务
    found = False
    old_priority = ""
    for task in tasks_data.get("tasks", []):
        if task.get("id") == task_id:
            old_priority = task.get("priority", "medium")
            task["priority"] = priority
            found = True
            break

        # 检查子任务
        if "subtasks" in task:
            for subtask in task["subtasks"]:
                if subtask.get("id") == task_id:
                    old_priority = subtask.get("priority", "medium")
                    subtask["priority"] = priority
                    found = True
                    break
            if found:
                break

    if not found:
        return f"错误: 找不到ID为 '{task_id}' 的任务"

    # 添加历史记录
    add_task_history(
        task_id=task_id,
        action="优先级变更",
        details=f"优先级从 '{old_priority}' 变更为 '{priority}'",
        project_root=project_root
    )

    # 保存更新后的任务
    save_tasks(tasks_data, tasks_path)

    return f"任务 '{task_id}' 的优先级已从 '{old_priority}' 更新为 '{priority}'"

def add_task_history(
    task_id: Annotated[str, "任务ID，例如task_001"],
    action: Annotated[str, "执行的操作"],details: Annotated[str, "操作详情"],
    project_root: Annotated[str,"项目根目录，默认为当前目录"] = None
) -> None:
    """
    添加任务历史记录

    记录任务的状态变更、优先级变更等操作
    """
    if project_root is None:
        project_root = os.getcwd()

    try:
        tasks_path = find_tasks_json_path(project_root)
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError:
        return

    # 查找任务
    found = False
    for task in tasks_data.get("tasks", []):
        if task.get("id") == task_id:
            # 确保任务有history字段
            if "history" not in task:
                task["history"] = []

            # 添加历史记录
            history_entry = {
                "timestamp": datetime.datetime.now().isoformat(),
                "action": action,
                "details": details
            }

            task["history"].append(history_entry)
            found = True
            break

        # 检查子任务
        if "subtasks" in task:
            for subtask in task["subtasks"]:
                if subtask.get("id") == task_id:
                    # 确保子任务有history字段
                    if "history" not in subtask:
                        subtask["history"] = []

                    # 添加历史记录
                    history_entry = {
                        "timestamp": datetime.datetime.now().isoformat(),
                        "action": action,
                        "details": details
                    }

                    subtask["history"].append(history_entry)
                    found = True
                    break
            if found:
                break

    if found:
        # 保存更新后的任务
        save_tasks(tasks_data, tasks_path)

def get_task_history(
    task_id: Annotated[str, "任务ID，例如task_001"],
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    获取任务历史记录

    显示任务的历史操作记录
    """
    if project_root is None:
        project_root = os.getcwd()

    try:
        tasks_path = find_tasks_json_path(project_root)
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError as e:
        return f"错误: {str(e)}"

    # 查找任务
    found = False
    history = []
    task_title = ""

    for task in tasks_data.get("tasks", []):
        if task.get("id") == task_id:
            task_title = task.get("title", "无标题")
            history = task.get("history", [])
            found = True
            break

        # 检查子任务
        if "subtasks" in task:
            for subtask in task["subtasks"]:
                if subtask.get("id") == task_id:
                    task_title = subtask.get("title", "无标题")
                    history = subtask.get("history", [])
                    found = True
                    break
            if found:
                break

    if not found:
        return f"错误: 找不到ID为 '{task_id}' 的任务"

    if not history:
        return f"任务 '{task_id}' ({task_title}) 没有历史记录"

    # 生成报告
    report = [f"任务 '{task_id}' ({task_title}) 的历史记录:"]

    # 按时间排序
    sorted_history = sorted(history, key=lambda x: x.get("timestamp", ""), reverse=True)

    for i, entry in enumerate(sorted_history):
        timestamp = entry.get("timestamp", "")
        action = entry.get("action", "")
        details = entry.get("details", "")

        # 格式化时间戳
        try:
            dt = datetime.datetime.fromisoformat(timestamp)
            formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            formatted_time = timestamp

        report.append(f"{i+1}. [{formatted_time}] {action}: {details}")

    return "\n".join(report)

def set_task_status(
    task_id: Annotated[str, "任务ID，例如task_001"],
    status: Annotated[str, "新状态 (pending, in_progress, done, deferred)"],
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    设置任务状态

    更新指定任务的状态
    """
    if project_root is None:
        project_root = os.getcwd()

    if status not in TASK_STATUS:
        return f"错误: 无效的状态 '{status}'。有效状态: {', '.join(TASK_STATUS)}"

    try:
        tasks_path = find_tasks_json_path(project_root)
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError as e:
        return f"错误: {str(e)}"

    # 查找任务
    found = False
    old_status = ""
    for task in tasks_data.get("tasks", []):
        if task.get("id") == task_id:
            old_status = task.get("status", "pending")
            task["status"] = status
            found = True
            break

        # 检查子任务
        if "subtasks" in task:
            for subtask in task["subtasks"]:
                if subtask.get("id") == task_id:
                    old_status = subtask.get("status", "pending")
                    subtask["status"] = status
                    found = True
                    break
            if found:
                break

    if not found:
        return f"错误: 找不到ID为 '{task_id}' 的任务"

    # 添加历史记录
    add_task_history(
        task_id=task_id,
        action="状态变更",
        details=f"状态从 '{old_status}' 变更为 '{status}'",
        project_root=project_root
    )

    # 保存更新后的任务
    save_tasks(tasks_data, tasks_path)

    # 获取任务标题和分配者
    task_title = ""
    assignee = ""
    for task in tasks_data.get("tasks", []):
        if task.get("id") == task_id:
            task_title = task.get("title", "")
            assignee = task.get("assignee", "")
            break

        # 检查子任务
        if "subtasks" in task:
            for subtask in task["subtasks"]:
                if subtask.get("id") == task_id:
                    task_title = subtask.get("title", "")
                    assignee = subtask.get("assignee", "")
                    break
            if task_title:
                break

    # 如果任务有分配者，发送通知消息
    if assignee:
        task_info = f"任务 '{task_id}'"
        if task_title:
            task_info += f" ({task_title})"

        message = f"{task_info} 的状态已从 '{old_status}' 更新为 '{status}'。"
        send_message(assignee, message, "task_status_changed", project_root)

    return f"任务 '{task_id}' 的状态已从 '{old_status}' 更新为 '{status}'"

def show_task(
    task_id: Annotated[str, "任务ID，例如task_001"],
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    显示特定任务的详细信息

    包括任务描述、状态、优先级、依赖关系和子任务
    """
    if project_root is None:
        project_root = os.getcwd()

    try:
        tasks_path = find_tasks_json_path(project_root)
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError as e:
        return f"错误: {str(e)}"

    # 查找任务
    task_info = None
    is_subtask = False
    parent_id = None

    for task in tasks_data.get("tasks", []):
        if task.get("id") == task_id:
            task_info = task
            break

        # 检查子任务
        if "subtasks" in task:
            for subtask in task["subtasks"]:
                if subtask.get("id") == task_id:
                    task_info = subtask
                    is_subtask = True
                    parent_id = task.get("id")
                    break
            if task_info:
                break

    if not task_info:
        return f"错误: 找不到ID为 '{task_id}' 的任务"

    # 格式化输出
    result = []
    result.append(f"任务ID: {task_info.get('id')}")
    if is_subtask:
        result.append(f"父任务: {parent_id}")
    result.append(f"标题: {task_info.get('title', '无标题')}")
    result.append(f"状态: {task_info.get('status', 'pending')}")
    result.append(f"优先级: {task_info.get('priority', 'medium')}")
    result.append(f"描述: {task_info.get('description', '无描述')}")

    if not is_subtask:
        # 显示依赖关系
        dependencies = task_info.get("dependencies", [])
        if dependencies:
            result.append("依赖任务:")
            for dep in dependencies:
                result.append(f"  - {dep}")
        else:
            result.append("依赖任务: 无")

        # 显示子任务
        subtasks = task_info.get("subtasks", [])
        if subtasks:
            result.append("子任务:")
            for subtask in subtasks:
                subtask_id = subtask.get("id", "unknown")
                subtask_status = subtask.get("status", "pending")
                subtask_title = subtask.get("title", "无标题")
                result.append(f"  - [{subtask_id}] [{subtask_status}] {subtask_title}")
        else:
            result.append("子任务: 无")

    return "\n".join(result)

def next_task(
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    确定下一个要处理的任务

    基于依赖关系和状态，推荐下一个应该处理的任务
    """
    if project_root is None:
        project_root = os.getcwd()

    try:
        tasks_path = find_tasks_json_path(project_root)
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError as e:
        return f"错误: {str(e)}"

    tasks = tasks_data.get("tasks", [])

    # 找出所有未完成的任务
    pending_tasks = [task for task in tasks if task.get("status") not in ["done", "deferred"]]

    if not pending_tasks:
        return "没有待处理的任务。所有任务都已完成或延期。"

    # 找出没有未完成依赖的任务
    available_tasks = []
    for task in pending_tasks:
        dependencies = task.get("dependencies", [])
        has_pending_deps = False

        for dep_id in dependencies:
            # 查找依赖任务
            for dep_task in tasks:
                if dep_task.get("id") == dep_id and dep_task.get("status") != "done":
                    has_pending_deps = True
                    break

            if has_pending_deps:
                break

        if not has_pending_deps:
            available_tasks.append(task)

    if not available_tasks:
        return "没有可立即处理的任务。所有未完成任务都有未满足的依赖。"

    # 按优先级排序
    priority_map = {"high": 3, "medium": 2, "low": 1}
    available_tasks.sort(key=lambda t: priority_map.get(t.get("priority", "medium"), 0), reverse=True)

    next_task = available_tasks[0]

    return f"""下一个推荐任务:
[{next_task.get('id')}] [{next_task.get('status', 'pending')}] [{next_task.get('priority', 'medium')}] {next_task.get('title', '无标题')}
描述: {next_task.get('description', '无描述')}"""

def generate_task_files(
    output_dir: Annotated[str, "输出目录，默认为当前目录下的tasks文件夹"] = None,
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None,
    format: Annotated[str, "输出格式 (txt, md, json)"] = "txt"
) -> str:
    """
    生成任务文件

    为每个任务创建单独的文件，便于参考或AI编码工作流
    """
    if project_root is None:
        project_root = os.getcwd()

    if output_dir is None:
        output_dir = os.path.join(project_root, "tasks")

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    if format not in ["txt", "md", "json"]:
        return f"错误: 无效的格式 '{format}'。有效格式: txt, md, json"

    try:
        tasks_path = find_tasks_json_path(project_root)
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError as e:
        return f"错误: {str(e)}"

    tasks = tasks_data.get("tasks", [])

    if not tasks:
        return "没有找到任务，无法生成任务文件。"

    # 生成任务文件
    generated_files = []

    for task in tasks:
        task_id = task.get("id", "unknown")

        if format == "txt":
            file_path = os.path.join(output_dir, f"{task_id}.txt")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"任务ID: {task_id}\n")
                f.write(f"标题: {task.get('title', '无标题')}\n")
                f.write(f"状态: {task.get('status', 'pending')}\n")
                f.write(f"优先级: {task.get('priority', 'medium')}\n")
                f.write(f"描述: {task.get('description', '无描述')}\n\n")

                # 依赖关系
                dependencies = task.get("dependencies", [])
                if dependencies:
                    f.write("依赖任务:\n")
                    for dep in dependencies:
                        f.write(f"  - {dep}\n")
                else:
                    f.write("依赖任务: 无\n")

                # 子任务
                subtasks = task.get("subtasks", [])
                if subtasks:
                    f.write("\n子任务:\n")
                    for subtask in subtasks:
                        subtask_id = subtask.get("id", "unknown")
                        subtask_status = subtask.get("status", "pending")
                        subtask_title = subtask.get("title", "无标题")
                        f.write(f"  - [{subtask_id}] [{subtask_status}] {subtask_title}\n")
                        f.write(f"    描述: {subtask.get('description', '无描述')}\n")

        elif format == "md":
            file_path = os.path.join(output_dir, f"{task_id}.md")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"# 任务: {task.get('title', '无标题')}\n\n")
                f.write(f"**ID:** {task_id}  \n")
                f.write(f"**状态:** {task.get('status', 'pending')}  \n")
                f.write(f"**优先级:** {task.get('priority', 'medium')}  \n\n")
                f.write(f"## 描述\n\n{task.get('description', '无描述')}\n\n")

                # 依赖关系
                dependencies = task.get("dependencies", [])
                f.write("## 依赖任务\n\n")
                if dependencies:
                    for dep in dependencies:
                        f.write(f"- {dep}\n")
                else:
                    f.write("无依赖任务\n")

                # 子任务
                subtasks = task.get("subtasks", [])
                f.write("\n## 子任务\n\n")
                if subtasks:
                    for subtask in subtasks:
                        subtask_id = subtask.get("id", "unknown")
                        subtask_status = subtask.get("status", "pending")
                        subtask_title = subtask.get("title", "无标题")
                        f.write(f"### [{subtask_id}] {subtask_title}\n\n")
                        f.write(f"**状态:** {subtask_status}  \n")
                        f.write(f"**描述:** {subtask.get('description', '无描述')}  \n\n")
                else:
                    f.write("无子任务\n")

        elif format == "json":
            file_path = os.path.join(output_dir, f"{task_id}.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(task, f, indent=2, ensure_ascii=False)

        generated_files.append(file_path)

    return f"已生成 {len(generated_files)} 个任务文件到 {output_dir} 目录"

def add_dependency(
    task_id: Annotated[str, "任务ID，例如task_001"],
    dependency_id: Annotated[str, "依赖任务ID，例如task_002"],
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    添加任务依赖关系

    将一个任务添加为另一个任务的依赖
    """
    if project_root is None:
        project_root = os.getcwd()

    try:
        tasks_path = find_tasks_json_path(project_root)
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError as e:
        return f"错误: {str(e)}"

    tasks = tasks_data.get("tasks", [])

    # 检查任务是否存在
    task_exists = False
    dependency_exists = False

    for task in tasks:
        if task.get("id") == task_id:
            task_exists = True
        if task.get("id") == dependency_id:
            dependency_exists = True

        if task_exists and dependency_exists:
            break

    if not task_exists:
        return f"错误: 找不到ID为 '{task_id}' 的任务"

    if not dependency_exists:
        return f"错误: 找不到ID为 '{dependency_id}' 的依赖任务"

    # 检查循环依赖
    def has_dependency_path(from_id, to_id, visited=None):
        if visited is None:
            visited = set()

        if from_id in visited:
            return False

        visited.add(from_id)

        if from_id == to_id:
            return True

        for task in tasks:
            if task.get("id") == from_id:
                for dep_id in task.get("dependencies", []):
                    if has_dependency_path(dep_id, to_id, visited):
                        return True

        return False

    # 检查添加新依赖是否会导致循环
    if has_dependency_path(dependency_id, task_id):
        return f"错误: 添加此依赖将导致循环依赖"

    # 添加依赖
    for task in tasks:
        if task.get("id") == task_id:
            dependencies = task.get("dependencies", [])
            if dependency_id in dependencies:
                return f"任务 '{task_id}' 已经依赖于 '{dependency_id}'"

            dependencies.append(dependency_id)
            task["dependencies"] = dependencies
            break

    # 保存更新后的任务
    save_tasks(tasks_data, tasks_path)

    return f"已将任务 '{dependency_id}' 添加为 '{task_id}' 的依赖"

def remove_dependency(
    task_id: Annotated[str, "任务ID，例如task_001"],
    dependency_id: Annotated[str, "要移除的依赖任务ID，例如task_002"],
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    移除任务依赖关系

    从一个任务中移除依赖
    """
    if project_root is None:
        project_root = os.getcwd()

    try:
        tasks_path = find_tasks_json_path(project_root)
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError as e:
        return f"错误: {str(e)}"

    tasks = tasks_data.get("tasks", [])

    # 查找任务
    found = False
    dependency_removed = False

    for task in tasks:
        if task.get("id") == task_id:
            found = True
            dependencies = task.get("dependencies", [])

            if dependency_id in dependencies:
                dependencies.remove(dependency_id)
                task["dependencies"] = dependencies
                dependency_removed = True

            break

    if not found:
        return f"错误: 找不到ID为 '{task_id}' 的任务"

    if not dependency_removed:
        return f"任务 '{task_id}' 不依赖于 '{dependency_id}'"

    # 保存更新后的任务
    save_tasks(tasks_data, tasks_path)

    return f"已从任务 '{task_id}' 中移除依赖 '{dependency_id}'"

def validate_dependencies(
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    验证任务依赖关系

    检查所有任务的依赖关系是否有效，包括检测循环依赖和不存在的依赖
    """
    if project_root is None:
        project_root = os.getcwd()

    try:
        tasks_path = find_tasks_json_path(project_root)
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError as e:
        return f"错误: {str(e)}"

    tasks = tasks_data.get("tasks", [])

    if not tasks:
        return "没有找到任务，无法验证依赖关系。"

    # 收集所有任务ID
    task_ids = set(task.get("id") for task in tasks)

    # 检查无效依赖
    invalid_dependencies = []
    for task in tasks:
        task_id = task.get("id")
        dependencies = task.get("dependencies", [])

        for dep_id in dependencies:
            if dep_id not in task_ids:
                invalid_dependencies.append((task_id, dep_id))

    # 检查循环依赖
    circular_dependencies = []

    def has_circular_dependency(from_id, to_id, visited=None, path=None):
        if visited is None:
            visited = set()
        if path is None:
            path = []

        if from_id in visited:
            return False

        visited.add(from_id)
        path.append(from_id)

        if from_id == to_id:
            return True

        for task in tasks:
            if task.get("id") == from_id:
                for dep_id in task.get("dependencies", []):
                    if has_circular_dependency(dep_id, to_id, visited, path[:]):
                        return True

        return False

    for task in tasks:
        has_circular_dependency(task.get("id"))

    # 生成报告
    report = []

    if not invalid_dependencies and not circular_dependencies:
        report.append("所有任务依赖关系有效，没有发现问题。")
    else:
        if invalid_dependencies:
            report.append("发现无效依赖关系:")
            for task_id, dep_id in invalid_dependencies:
                report.append(f"  - 任务 '{task_id}' 依赖于不存在的任务 '{dep_id}'")

        if circular_dependencies:
            report.append("发现循环依赖关系:")
            for cycle in circular_dependencies:
                report.append(f"  - 循环: {' -> '.join(cycle)}")

    return "\n".join(report)

def fix_dependencies(
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None,
    auto_fix: Annotated[bool, "是否自动修复问题"] = False
) -> str:
    """
    修复任务依赖关系

    修复无效的依赖关系，包括移除不存在的依赖和打破循环依赖
    """
    if project_root is None:
        project_root = os.getcwd()

    try:
        tasks_path = find_tasks_json_path(project_root)
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError as e:
        return f"错误: {str(e)}"

    tasks = tasks_data.get("tasks", [])

    if not tasks:
        return "没有找到任务，无法修复依赖关系。"

    # 收集所有任务ID
    task_ids = set(task.get("id") for task in tasks)

    # 修复无效依赖
    fixed_invalid = []
    for task in tasks:
        task_id = task.get("id")
        dependencies = task.get("dependencies", [])

        valid_dependencies = [dep_id for dep_id in dependencies if dep_id in task_ids]
        if len(valid_dependencies) != len(dependencies):
            fixed_invalid.append((task_id, set(dependencies) - set(valid_dependencies)))
            if auto_fix:
                task["dependencies"] = valid_dependencies

    # 检测并修复循环依赖

    def detect_cycles():
        # 构建依赖图
        graph = {}
        for task in tasks:
            task_id = task.get("id")
            graph[task_id] = task.get("dependencies", [])

        # 使用Tarjan算法检测循环
        index_counter = [0]
        index = {}
        lowlink = {}
        onstack = set()
        stack = []
        cycles = []

        def strongconnect(node):
            index[node] = index_counter[0]
            lowlink[node] = index_counter[0]
            index_counter[0] += 1
            stack.append(node)
            onstack.add(node)

            for successor in graph.get(node, []):
                if successor not in index:
                    strongconnect(successor)
                    lowlink[node] = min(lowlink[node], lowlink[successor])
                elif successor in onstack:
                    lowlink[node] = min(lowlink[node], index[successor])

            if lowlink[node] == index[node]:
                cycle = []
                while True:
                    successor = stack.pop()
                    onstack.remove(successor)
                    cycle.append(successor)
                    if successor == node:
                        break

                if len(cycle) > 1:
                    cycles.append(cycle)

        for node in graph:
            if node not in index:
                strongconnect(node)

        return cycles

    cycles = detect_cycles()

    # 修复循环依赖
    fixed_circular = []
    if auto_fix and cycles:
        for cycle in cycles:
            # 打破循环的简单策略：移除最后一个任务对第一个任务的依赖
            last_task_id = cycle[-1]
            first_task_id = cycle[0]

            for task in tasks:
                if task.get("id") == last_task_id:
                    if first_task_id in task.get("dependencies", []):
                        task["dependencies"].remove(first_task_id)
                        fixed_circular.append((last_task_id, first_task_id))
                    break

    # 如果自动修复，保存更新后的任务
    if auto_fix and (fixed_invalid or fixed_circular):
        save_tasks(tasks_data, tasks_path)

    # 生成报告
    report = []

    if not fixed_invalid and not cycles:
        report.append("所有任务依赖关系有效，没有需要修复的问题。")
    else:
        if fixed_invalid:
            report.append("发现无效依赖关系:")
            for task_id, invalid_deps in fixed_invalid:
                deps_str = ", ".join(f"'{dep}'" for dep in invalid_deps)
                if auto_fix:
                    report.append(f"  - 已修复: 从任务 '{task_id}' 中移除了不存在的依赖 {deps_str}")
                else:
                    report.append(f"  - 建议: 从任务 '{task_id}' 中移除不存在的依赖 {deps_str}")

        if cycles:  # 使用cycles变量替代circular_dependencies
            report.append("发现循环依赖关系:")
            for i, cycle in enumerate(cycles):
                cycle_str = " -> ".join(cycle)
                if auto_fix and i < len(fixed_circular):
                    task_id, dep_id = fixed_circular[i]
                    report.append(f"  - 已修复: 打破循环 '{cycle_str}' 通过移除 '{task_id}' 对 '{dep_id}' 的依赖")
                else:
                    report.append(f"  - 建议: 打破循环 '{cycle_str}'")

    if auto_fix:
        if fixed_invalid or fixed_circular:
            report.append("\n已自动修复所有问题并保存更改。")
        else:
            report.append("\n没有进行任何修改。")
    else:
        if fixed_invalid or cycles:
            report.append("\n使用 fix_dependencies(project_root, auto_fix=True) 自动修复这些问题。")

    return "\n".join(report)

def add_subtask(
    parent_task_id: Annotated[str, "父任务ID，例如task_001"],
    title: Annotated[str, "子任务标题"],
    description: Annotated[str, "子任务描述"] = "",
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    添加子任务

    向指定任务添加一个子任务
    """
    if project_root is None:
        project_root = os.getcwd()

    try:
        tasks_path = find_tasks_json_path(project_root)
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError as e:
        return f"错误: {str(e)}"

    tasks = tasks_data.get("tasks", [])

    # 查找父任务
    parent_task = None
    for task in tasks:
        if task.get("id") == parent_task_id:
            parent_task = task
            break

    if not parent_task:
        return f"错误: 找不到ID为 '{parent_task_id}' 的父任务"

    # 创建子任务
    subtasks = parent_task.get("subtasks", [])

    # 生成子任务ID
    subtask_id = f"{parent_task_id}_sub_{len(subtasks) + 1:03d}"

    new_subtask = {
        "id": subtask_id,
        "title": title,
        "description": description,
        "status": "pending"
    }

    subtasks.append(new_subtask)
    parent_task["subtasks"] = subtasks

    # 保存更新后的任务
    save_tasks(tasks_data, tasks_path)

    return f"已向任务 '{parent_task_id}' 添加子任务 '{subtask_id}'"
def clean_json_string(json_str: str) -> str:
    """
    清理JSON字符串，修复常见的格式问题

    处理以下问题：
    1. 多余的逗号
    2. 缺少引号的键
    3. 单引号替换为双引号
    4. 未闭合的括号
    5. 特殊字符处理
    6. 缺少值的键
    """
    if not json_str:
        return "{}"

    # 移除注释
    json_str = re.sub(r'//.*?$|/\*.*?\*/', '', json_str, flags=re.MULTILINE | re.DOTALL)

    # 移除可能导致问题的控制字符
    json_str = ''.join(ch for ch in json_str if ch >= ' ' or ch in '\n\r\t')

    # 替换单引号为双引号（但不替换转义的单引号）
    json_str = re.sub(r'(?<!\\)\'', '"', json_str)

    # 修复键没有引号的问题
    json_str = re.sub(r'([{,])\s*([a-zA-Z0-9_]+)\s*:', r'\1"\2":', json_str)

    # 修复多余的逗号
    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)

    # 修复缺少值的键（将null作为默认值）
    json_str = re.sub(r'("[\w\s]+"\s*:)\s*([,}])', r'\1null\2', json_str)

    # 修复错误的布尔值和null值（小写）
    json_str = re.sub(r':\s*True\b', r':true', json_str)
    json_str = re.sub(r':\s*False\b', r':false', json_str)
    json_str = re.sub(r':\s*None\b', r':null', json_str)

    # 检查并修复未闭合的括号
    open_braces = json_str.count('{')
    close_braces = json_str.count('}')
    open_brackets = json_str.count('[')
    close_brackets = json_str.count(']')

    # 添加缺少的闭合括号
    if open_braces > close_braces:
        json_str += '}' * (open_braces - close_braces)
    if open_brackets > close_brackets:
        json_str += ']' * (open_brackets - close_brackets)

    # 确保JSON字符串至少是一个有效的对象
    if not json_str.strip().startswith('{') and not json_str.strip().startswith('['):
        json_str = '{' + json_str + '}'

    return json_str

def safe_json_loads(json_str: str) -> tuple:
    """
    安全地解析JSON字符串，处理可能的格式错误

    Args:
        json_str: JSON字符串

    Returns:
        (success, result, error): 成功标志、解析结果或错误信息
    """
    if not json_str or json_str.strip() == "":
        return False, None, "JSON字符串为空"

    try:
        # 尝试直接解析
        result = json.loads(json_str)
        return True, result, None
    except json.JSONDecodeError as e:
        # 记录原始错误
        original_error = str(e)
        try:
            # 尝试清理并重新解析
            cleaned_json = clean_json_string(json_str)
            result = json.loads(cleaned_json)
            return True, result, None
        except json.JSONDecodeError as e2:
            # 如果仍然失败，返回详细错误信息
            return False, None, f"JSON解析错误: {original_error}\n清理后仍然失败: {str(e2)}"
        except Exception as e3:
            # 捕获其他可能的异常
            return False, None, f"JSON处理错误: {str(e3)}"

def validate_json_structure(json_obj: dict, schema: dict, path: str = "") -> tuple:
    """
    验证JSON对象是否符合指定的结构

    Args:
        json_obj: 要验证的JSON对象
        schema: 期望的结构模式
        path: 当前路径（用于错误报告）

    Returns:
        (is_valid, errors): 是否有效及错误信息
    """
    if json_obj is None:
        return False, ["JSON对象为空"]

    errors = []

    # 检查类型
    if not isinstance(json_obj, type(schema)):
        return False, [f"{path}: 类型不匹配，期望 {type(schema).__name__}，实际 {type(json_obj).__name__}"]

    # 处理字典
    if isinstance(schema, dict):
        # 检查必需字段
        for key, value in schema.items():
            if key not in json_obj:
                errors.append(f"{path}.{key}: 缺少必需字段")
            elif isinstance(value, (dict, list)):
                # 递归验证嵌套结构
                current_path = f"{path}.{key}" if path else key
                is_valid, nested_errors = validate_json_structure(json_obj[key], value, current_path)
                if not is_valid:
                    errors.extend(nested_errors)

    # 处理列表
    elif isinstance(schema, list) and schema:  # 非空列表
        schema_item = schema[0]  # 使用列表中的第一个元素作为模式
        for i, item in enumerate(json_obj):
            current_path = f"{path}[{i}]"
            is_valid, nested_errors = validate_json_structure(item, schema_item, current_path)
            if not is_valid:
                errors.extend(nested_errors)

    return len(errors) == 0, errors

def extract_json_from_text(text: str) -> str:
    """
    从文本中提取JSON字符串

    处理可能包含在Markdown代码块或其他文本中的JSON

    Args:
        text: 可能包含JSON的文本

    Returns:
        提取的JSON字符串，如果没有找到则返回原文本
    """
    # 尝试从Markdown代码块中提取JSON
    json_block_pattern = re.compile(r'```(?:json)?\s*([\s\S]*?)\s*```')
    match = json_block_pattern.search(text)
    if match:
        return match.group(1)

    # 尝试查找JSON对象或数组
    json_pattern = re.compile(r'(\{[\s\S]*\}|\[[\s\S]*\])')
    match = json_pattern.search(text)
    if match:
        return match.group(1)

    # 如果没有找到明确的JSON，返回原文本
    return text

def log_json_error(file_path: str, error_message: str, json_content: str = None):
    """
    记录JSON解析错误到日志文件

    Args:
        file_path: 发生错误的文件路径
        error_message: 错误信息
        json_content: 导致错误的JSON内容（可选）
    """
    log_dir = os.path.join(os.path.dirname(os.path.dirname(file_path)), "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "json_errors.log")

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] 错误: {file_path}\n")
        f.write(f"错误信息: {error_message}\n")
        if json_content:
            f.write("JSON内容片段:\n")
            # 只记录前200个字符，避免日志文件过大
            f.write(f"{json_content[:200]}...\n" if len(json_content) > 200 else f"{json_content}\n")
        f.write("-" * 80 + "\n")

def remove_subtask(
    parent_task_id: Annotated[str, "父任务ID，例如task_001"],
    subtask_id: Annotated[str, "子任务ID，例如task_001_sub_001"],
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    移除子任务

    从指定任务中移除一个子任务
    """
    if project_root is None:
        project_root = os.getcwd()

    try:
        tasks_path = find_tasks_json_path(project_root)
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError as e:
        return f"错误: {str(e)}"

    tasks = tasks_data.get("tasks", [])

    # 查找父任务
    parent_task = None
    for task in tasks:
        if task.get("id") == parent_task_id:
            parent_task = task
            break

    if not parent_task:
        return f"错误: 找不到ID为 '{parent_task_id}' 的父任务"

    # 查找并移除子任务
    subtasks = parent_task.get("subtasks", [])
    found = False

    for i, subtask in enumerate(subtasks):
        if subtask.get("id") == subtask_id:
            del subtasks[i]
            found = True
            break

    if not found:
        return f"错误: 在任务 '{parent_task_id}' 中找不到ID为 '{subtask_id}' 的子任务"

    parent_task["subtasks"] = subtasks

    # 保存更新后的任务
    save_tasks(tasks_data, tasks_path)

    return f"已从任务 '{parent_task_id}' 中移除子任务 '{subtask_id}'"

def analyze_task_complexity(
    task_id: Annotated[str, "任务ID，例如task_001"],
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    分析任务复杂度

    分析任务的复杂度，提供建议的子任务数量和估计工作量
    """
    if project_root is None:
        project_root = os.getcwd()

    try:
        tasks_path = find_tasks_json_path(project_root)
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError as e:
        return f"错误: {str(e)}"

    # 查找任务
    task_info = None
    for task in tasks_data.get("tasks", []):
        if task.get("id") == task_id:
            task_info = task
            break

        # 检查子任务
        if "subtasks" in task:
            for subtask in task["subtasks"]:
                if subtask.get("id") == task_id:
                    task_info = subtask
                    break
            if task_info:
                break

    if not task_info:
        return f"错误: 找不到ID为 '{task_id}' 的任务"

    # 获取任务信息
    title = task_info.get("title", "")
    description = task_info.get("description", "")
    priority = task_info.get("priority", "medium")
    status = task_info.get("status", "pending")
    dependencies = task_info.get("dependencies", [])
    subtasks = task_info.get("subtasks", [])
    tags = task_info.get("tags", [])

    # 计算复杂度分数
    complexity_score = 0

    # 基于描述长度
    if description:
        words = description.split()
        if len(words) > 200:
            complexity_score += 5
        elif len(words) > 100:
            complexity_score += 3
        elif len(words) > 50:
            complexity_score += 2
        else:
            complexity_score += 1

    # 基于优先级
    if priority == "high":
        complexity_score += 3
    elif priority == "medium":
        complexity_score += 2
    else:
        complexity_score += 1

    # 基于依赖关系
    complexity_score += len(dependencies)

    # 基于标签
    complexity_tags = ["复杂", "困难", "挑战", "高级", "架构", "设计", "研究", "优化", "重构"]
    for tag in tags:
        if any(ct in tag.lower() for ct in complexity_tags):
            complexity_score += 2

    # 基于现有子任务
    if subtasks:
        complexity_score += min(len(subtasks), 5)

    # 确定复杂度级别
    if complexity_score >= 15:
        complexity_level = "非常高"
        suggested_subtasks = 8
        estimated_hours = "40-60"
    elif complexity_score >= 10:
        complexity_level = "高"
        suggested_subtasks = 6
        estimated_hours = "20-40"
    elif complexity_score >= 7:
        complexity_level = "中等"
        suggested_subtasks = 4
        estimated_hours = "10-20"
    elif complexity_score >= 4:
        complexity_level = "低"
        suggested_subtasks = 3
        estimated_hours = "5-10"
    else:
        complexity_level = "非常低"
        suggested_subtasks = 2
        estimated_hours = "1-5"

    # 保存复杂度分析结果
    task_info["complexity"] = {
        "score": complexity_score,
        "level": complexity_level,
        "suggested_subtasks": suggested_subtasks,
        "estimated_hours": estimated_hours,
        "analyzed_at": datetime.datetime.now().isoformat()
    }

    # 保存更新后的任务
    save_tasks(tasks_data, tasks_path)

    # 生成报告
    report = [f"任务 '{task_id}' ({title}) 的复杂度分析:"]
    report.append(f"复杂度分数: {complexity_score}")
    report.append(f"复杂度级别: {complexity_level}")
    report.append(f"建议子任务数量: {suggested_subtasks}")
    report.append(f"估计工作时间: {estimated_hours} 小时")

    # 提供建议
    report.append("\n建议:")

    if complexity_level in ["高", "非常高"]:
        report.append("- 将任务分解为更小的子任务")
        report.append("- 考虑分配多人协作完成")
        report.append("- 设置明确的里程碑和检查点")
        report.append("- 提前识别风险和依赖")

    if len(dependencies) > 0:
        report.append("- 确保所有依赖任务都已完成或正在进行中")

    if len(subtasks) < suggested_subtasks:
        report.append(f"- 考虑添加更多子任务（当前 {len(subtasks)}，建议 {suggested_subtasks}）")

    if "测试" not in " ".join(tags).lower():
        report.append("- 添加测试相关的子任务")

    if "文档" not in " ".join(tags).lower():
        report.append("- 添加文档相关的子任务")

    return "\n".join(report)

def expand_task(
    task_id: Annotated[str, "任务ID，例如task_001"],
    num_subtasks: Annotated[int, "要生成的子任务数量，默认为0（使用建议数量）"] = 0,
    project_root: Annotated[str, "项目根目录，默认为当前目录"] = None
) -> str:
    """
    扩展任务

    将一个任务扩展为多个子任务，可以指定子任务数量或使用建议数量
    """
    if project_root is None:
        project_root = os.getcwd()

    try:
        tasks_path = find_tasks_json_path(project_root)
        tasks_data = load_tasks(tasks_path)
    except FileNotFoundError as e:
        return f"错误: {str(e)}"

    tasks = tasks_data.get("tasks", [])

    # 查找任务
    task_info = None
    for task in tasks:
        if task.get("id") == task_id:
            task_info = task
            break

    if not task_info:
        return f"错误: 找不到ID为 '{task_id}' 的任务"

    # 获取任务信息
    title = task_info.get("title", "")
    description = task_info.get("description", "")

    # 如果任务已经有子任务，询问是否要清除
    existing_subtasks = task_info.get("subtasks", [])
    if existing_subtasks:
        return f"任务 '{task_id}' 已有 {len(existing_subtasks)} 个子任务。请先使用 remove_subtask 移除现有子任务，或使用 add_subtask 添加更多子任务。"

# 创建TaskMaster工具列表
taskmaster_tools = [
    # 项目管理
    FunctionTool(
        initialize_project,
        name="initialize_project",
        description="初始化一个新的TaskMaster项目，创建必要的目录结构和配置文件"
    ),

    # PRD解析
    FunctionTool(
        parse_prd,
        name="parse_prd",
        description="解析PRD文档并生成任务列表，支持多种格式的PRD文件"
    ),

    # 任务管理
    FunctionTool(
        list_tasks,
        name="list_tasks",
        description="列出所有任务，可按状态筛选"
    ),

    FunctionTool(
        set_task_status,
        name="set_task_status",
        description="设置任务状态，可选状态: pending, in_progress, done, deferred"
    ),

    FunctionTool(
        show_task,
        name="show_task",
        description="显示特定任务的详细信息，包括子任务和依赖关系"
    ),

    FunctionTool(
        next_task,
        name="next_task",
        description="确定下一个要处理的任务，基于优先级和依赖关系"
    ),

    FunctionTool(
        generate_task_files,
        name="generate_task_files",
        description="为每个任务生成单独的文件，便于参考或AI编码工作流"
    ),

    # 任务依赖管理
    FunctionTool(
        add_dependency,
        name="add_dependency",
        description="添加任务依赖关系，将一个任务添加为另一个任务的依赖"
    ),

    FunctionTool(
        remove_dependency,
        name="remove_dependency",
        description="移除任务依赖关系"
    ),

    # 子任务管理
    FunctionTool(
        add_subtask,
        name="add_subtask",
        description="向指定任务添加一个子任务"
    ),

    FunctionTool(
        remove_subtask,
        name="remove_subtask",
        description="从指定任务中移除一个子任务"
    ),

    # 任务分析
    FunctionTool(
        analyze_task_complexity,
        name="analyze_task_complexity",
        description="分析任务复杂度，提供建议的子任务数量和估计工作量"
    ),

    # 任务管理
    FunctionTool(
        add_task,
        name="add_task",
        description="添加新任务，可以指定使用的模板"
    ),

    FunctionTool(
        set_task_priority,
        name="set_task_priority",
        description="设置任务优先级，可选优先级: high, medium, low"
    ),

    # 任务标签管理
    FunctionTool(
        add_task_tag,
        name="add_task_tag",
        description="为任务添加标签"
    ),

    FunctionTool(
        remove_task_tag,
        name="remove_task_tag",
        description="从任务中移除标签"
    ),

    FunctionTool(
        list_task_tags,
        name="list_task_tags",
        description="列出所有任务标签及其使用次数"
    ),

    FunctionTool(
        find_tasks_by_tag,
        name="find_tasks_by_tag",
        description="按标签查找任务"
    ),

    # 任务搜索
    FunctionTool(
        search_tasks,
        name="search_tasks",
        description="搜索任务，可按关键词、状态、优先级等条件搜索"
    ),

    # 任务历史
    FunctionTool(
        get_task_history,
        name="get_task_history",
        description="获取任务历史记录，显示任务的变更历史"
    ),

    # 模板管理
    FunctionTool(
        list_templates,
        name="list_templates",
        description="列出所有可用的任务模板，包括系统预定义模板和用户自定义模板"
    ),

    FunctionTool(
        save_template,
        name="save_template",
        description="保存用户自定义模板"
    ),

    FunctionTool(
        delete_template,
        name="delete_template",
        description="删除用户自定义模板"
    ),

    # 团队管理
    FunctionTool(
        add_team_member,
        name="add_team_member",
        description="添加团队成员，并分配角色和描述"
    ),

    FunctionTool(
        remove_team_member,
        name="remove_team_member",
        description="移除团队成员"
    ),

    FunctionTool(
        list_team_members,
        name="list_team_members",
        description="列出所有团队成员及其角色、描述和消息文件路径"
    ),

    FunctionTool(
        assign_task,
        name="assign_task",
        description="将任务分配给特定的团队成员"
    ),

    # 团队分组管理
    FunctionTool(
        create_group,
        name="create_group",
        description="创建团队组，指定组长和可选的父组"
    ),

    FunctionTool(
        add_member_to_group,
        name="add_member_to_group",
        description="将成员添加到组"
    ),

    FunctionTool(
        remove_member_from_group,
        name="remove_member_from_group",
        description="从组中移除成员"
    ),

    FunctionTool(
        list_groups,
        name="list_groups",
        description="列出所有团队组及其组长、成员等信息"
    ),

    FunctionTool(
        delete_group,
        name="delete_group",
        description="删除团队组"
    ),

    # 消息通信
    FunctionTool(
        send_message,
        name="send_message",
        description="向指定用户或群组发送消息，消息将保存在相应的通讯文件中"
    ),

    FunctionTool(
        get_messages,
        name="get_messages",
        description="获取指定用户的个人消息或群组消息，可以选择只获取未读消息"
    ),

    FunctionTool(
        mark_message_read,
        name="mark_message_read",
        description="标记指定用户的个人消息或群组消息为已读，可以指定消息索引或标记所有消息"
    )
]
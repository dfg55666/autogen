"""
AutoGen工具模板 - 基于AutoGen 0.5.6的通用工具模板

本模板提供了创建AutoGen工具的基本结构，可以作为开发新工具的起点。
只需复制此文件，重命名，并添加您的具体工具功能即可。

主要特点:
- 兼容AutoGen 0.5.6的FunctionTool格式
- 包含完整的类型注解和文档字符串
- 提供错误处理和日志记录
- 支持直接测试工具功能
"""

import os
import json
import datetime
from typing import Dict, Any, Optional, List, Union
from typing_extensions import Annotated

# 尝试导入AutoGen相关模块
try:
    from autogen_core.tools import FunctionTool
except ImportError:
    try:
        from autogen.agentchat.contrib.tools import FunctionTool
    except ImportError:
        print("警告: 未找到AutoGen模块，工具将无法作为FunctionTool使用")
        # 定义一个空的FunctionTool类，以便代码可以继续运行
        class FunctionTool:
            def __init__(self, func, **kwargs):
                self.func = func
                self.kwargs = kwargs

# =====================================================================
# 工具函数定义区域 - 在此处添加您的工具函数
# =====================================================================

def example_tool(
    param1: Annotated[str, "第一个参数的说明，会显示在工具文档中"],
    param2: Annotated[int, "第二个参数的说明，会显示在工具文档中"] = 42,
    optional_param: Annotated[Optional[str], "可选参数的说明，如果不提供则使用默认值"] = None
) -> Dict[str, Any]:
    """
    示例工具函数，展示如何创建一个基本的工具。
    
    此函数演示了如何定义参数、添加文档字符串和返回结果。
    在实际开发中，请替换为您的实际工具功能。
    
    参数:
        param1: 第一个参数的详细说明
        param2: 第二个参数的详细说明，默认值为42
        optional_param: 可选参数的详细说明，默认为None
        
    返回:
        包含操作结果的字典
    """
    print(f"示例工具被调用，参数: param1={param1}, param2={param2}, optional_param={optional_param}")
    
    # 这里是工具的实际逻辑
    result = {
        "status": "success",
        "timestamp": datetime.datetime.now().isoformat(),
        "params": {
            "param1": param1,
            "param2": param2,
            "optional_param": optional_param
        },
        "result": f"处理了 {param1} 和 {param2}"
    }
    
    return result

# =====================================================================
# 工具实例创建区域 - 在此处创建您的工具实例
# =====================================================================

# 创建工具实例
try:
    example_tool_instance = FunctionTool(
        func=example_tool,
        name="ExampleTool",  # 工具名称，遵循OpenAI命名规范（字母数字下划线，不超过64字符）
        description="示例工具，展示如何创建一个基本的AutoGen工具"
    )
    print("工具 'ExampleTool' 创建成功。")
    
    # 将所有工具实例添加到工具列表中
    tool_list = [
        example_tool_instance,
        # 在此处添加更多工具实例
    ]
    
except (AttributeError, TypeError, NameError) as e:
    print(f"警告: 创建工具实例时出错: {e}")
    example_tool_instance = None
    tool_list = []

# =====================================================================
# 测试代码区域 - 用于直接测试工具功能
# =====================================================================

if __name__ == "__main__":
    print("\n=== 工具测试模式 ===")
    
    # 测试示例工具
    print("\n测试示例工具:")
    test_result = example_tool(
        param1="测试字符串",
        param2=100,
        optional_param="可选值"
    )
    
    # 美化输出结果
    print("\n工具执行结果:")
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
    # 工具函数
    "example_tool",
    
    # 工具实例
    "example_tool_instance",
    
    # 工具列表
    "tool_list"
]

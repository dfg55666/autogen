#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JSON解析器 - 用于处理和修复AI助手生成的JSON格式工具调用

这个模块提供了一组函数，用于解析、验证和修复AI助手生成的JSON格式工具调用，
特别是处理可能存在的格式错误和不完整的JSON。

主要功能:
1. JSON提取与修复 - 从文本中提取JSON并修复常见格式错误
2. 工具调用解析 - 解析AI助手生成的工具调用JSON
3. 工具调用执行 - 执行工具调用并处理结果
4. 结果格式化 - 将工具调用结果格式化为易于理解的文本

使用方式:
- 基本JSON解析: extract_json_from_text, fix_json_string, parse_json_safely
- 工具调用处理: extract_tool_calls, validate_tool_call, prepare_function_call, process_tool_calls_json
- 完整工具调用流程: process_and_execute_tool_calls
"""

# 标准库导入
import json
import re
from typing import Dict, List, Tuple, Optional

# 第三方库导入 (在使用时动态导入，避免启动时依赖错误)
# from autogen_agentchat.agents import AssistantAgent
# from autogen_core import FunctionCall, CancellationToken
# from autogen_agentchat.messages import TextMessage
# from autogen_core.tools import StaticWorkbench

def extract_json_from_text(text: str) -> str:
    """
    从文本中提取JSON对象

    Args:
        text: 包含JSON的文本

    Returns:
        提取的JSON字符串
    """
    # 清理文本，移除可能的标记
    clean_text = text.replace("IGNORE_WHEN_COPYING_START", "").replace("IGNORE_WHEN_COPYING_END", "")

    # 尝试找到完整的JSON对象
    json_match = re.search(r'(\{[\s\S]*\})', clean_text)
    if json_match:
        return json_match.group(1)

    return clean_text

def fix_json_string(json_str: str) -> str:
    """
    修复常见的JSON格式错误

    Args:
        json_str: 可能包含错误的JSON字符串

    Returns:
        修复后的JSON字符串
    """
    # 修复尾随逗号
    fixed_json = re.sub(r',\s*}', '}', json_str)
    fixed_json = re.sub(r',\s*]', ']', fixed_json)

    # 修复未引用的键
    fixed_json = re.sub(r'([{,]\s*)(\w+)(\s*:)', r'\1"\2"\3', fixed_json)

    # 修复单引号
    if "'" in fixed_json and '"' not in fixed_json:
        fixed_json = fixed_json.replace("'", '"')

    # 修复转义字符
    fixed_json = fixed_json.replace("\\\n", "\\n")
    fixed_json = re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', r'\\\\', fixed_json)

    # 修复括号不匹配
    open_braces = fixed_json.count('{')
    close_braces = fixed_json.count('}')
    if open_braces > close_braces:
        fixed_json += '}' * (open_braces - close_braces)

    return fixed_json

def parse_json_safely(json_str: str) -> Tuple[Dict, bool, str]:
    """
    安全地解析JSON字符串，处理可能的错误

    Args:
        json_str: JSON字符串

    Returns:
        元组 (解析结果, 是否成功, 错误消息)
    """
    try:
        # 尝试直接解析
        result = json.loads(json_str)
        return result, True, ""
    except json.JSONDecodeError as e:
        # 尝试修复并重新解析
        try:
            fixed_json = fix_json_string(json_str)
            result = json.loads(fixed_json)
            return result, True, f"已修复JSON格式问题: {str(e)}"
        except json.JSONDecodeError as e2:
            # 如果修复后仍然失败，返回错误
            return {}, False, f"JSON解析失败: {str(e2)}"

def extract_tool_calls(text: str) -> Tuple[List[Dict], bool, str]:
    """
    从文本中提取工具调用

    Args:
        text: 包含工具调用的文本

    Returns:
        元组 (工具调用列表, 是否成功, 错误消息)
    """
    # 提取JSON
    json_str = extract_json_from_text(text)

    # 解析JSON
    parsed_json, success, error_message = parse_json_safely(json_str)

    if not success:
        # 尝试使用正则表达式直接提取工具调用
        extracted_tool_calls = []
        tool_matches = re.finditer(
            r'"type"\s*:\s*"function"\s*,\s*"function"\s*:\s*\{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*(\{[\s\S]*?\})\s*\}',
            text
        )

        for match in tool_matches:
            try:
                tool_name = match.group(1)
                arguments_str = match.group(2)

                # 尝试解析参数
                try:
                    arguments = json.loads(arguments_str)
                except json.JSONDecodeError:
                    # 修复参数并重新解析
                    fixed_args = fix_json_string(arguments_str)
                    try:
                        arguments = json.loads(fixed_args)
                    except json.JSONDecodeError:
                        # 如果仍然失败，使用原始字符串
                        arguments = {"raw_arguments": arguments_str}

                extracted_tool_calls.append({
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": arguments
                    }
                })
            except Exception as e:
                error_message += f"\n提取工具调用时出错: {str(e)}"

        if extracted_tool_calls:
            return extracted_tool_calls, True, f"使用正则表达式提取了 {len(extracted_tool_calls)} 个工具调用。{error_message}"

        return [], False, error_message

    # 从解析的JSON中提取工具调用
    if "tool_calls" in parsed_json and isinstance(parsed_json["tool_calls"], list):
        return parsed_json["tool_calls"], True, error_message

    return [], False, "JSON中未找到有效的工具调用"

def validate_tool_call(tool_call: Dict) -> Tuple[bool, str]:
    """
    验证工具调用格式是否正确

    Args:
        tool_call: 工具调用字典

    Returns:
        元组 (是否有效, 错误消息)
    """
    # 检查类型
    if "type" not in tool_call or tool_call["type"] != "function":
        return False, "工具调用类型必须为'function'"

    # 检查函数
    if "function" not in tool_call or not isinstance(tool_call["function"], dict):
        return False, "工具调用必须包含'function'对象"

    function_data = tool_call["function"]

    # 检查函数名称
    if "name" not in function_data or not function_data["name"]:
        return False, "函数必须包含有效的'name'"

    # 检查参数
    if "arguments" not in function_data:
        return False, "函数必须包含'arguments'"

    # 如果参数是字符串，尝试解析为JSON
    if isinstance(function_data["arguments"], str):
        try:
            json.loads(function_data["arguments"])
        except json.JSONDecodeError:
            return False, "函数参数必须是有效的JSON字符串"

    return True, ""

def prepare_function_call(tool_call: Dict) -> Dict:
    """
    准备函数调用，确保格式正确

    Args:
        tool_call: 工具调用字典

    Returns:
        准备好的函数调用字典
    """
    # 验证工具调用
    is_valid, error_message = validate_tool_call(tool_call)
    if not is_valid:
        raise ValueError(f"无效的工具调用: {error_message}")

    function_data = tool_call["function"]

    # 确保参数是JSON字符串
    arguments = function_data["arguments"]
    if isinstance(arguments, dict):
        arguments_str = json.dumps(arguments)
    else:
        # 如果已经是字符串，确保是有效的JSON
        try:
            json.loads(arguments)
            arguments_str = arguments
        except json.JSONDecodeError:
            # 尝试修复
            fixed_args = fix_json_string(arguments)
            try:
                json.loads(fixed_args)
                arguments_str = fixed_args
            except json.JSONDecodeError:
                # 如果仍然失败，包装为原始参数
                arguments_str = json.dumps({"raw_arguments": arguments})

    return {
        "name": function_data["name"],
        "arguments": arguments_str
    }

def process_tool_calls_json(content: str) -> Tuple[List[Dict], bool, str]:
    """
    处理包含工具调用的JSON内容

    Args:
        content: 包含工具调用的文本

    Returns:
        元组 (处理后的函数调用列表, 是否成功, 错误消息)
    """
    # 提取工具调用
    tool_calls, success, error_message = extract_tool_calls(content)

    if not success or not tool_calls:
        return [], success, error_message

    # 准备函数调用
    function_calls = []
    for i, tool_call in enumerate(tool_calls):
        try:
            function_call = prepare_function_call(tool_call)
            function_calls.append(function_call)
        except ValueError as e:
            error_message += f"\n工具调用 {i+1} 无效: {str(e)}"

    return function_calls, bool(function_calls), error_message

async def _create_function_calls(function_calls_data):
    """
    根据函数调用数据创建FunctionCall对象列表

    Args:
        function_calls_data: 函数调用数据列表

    Returns:
        元组 (FunctionCall对象列表, 是否成功, 错误消息)
    """
    # 动态导入，避免启动时依赖错误
    from autogen_core import FunctionCall

    function_calls = []
    try:
        for i, function_call_data in enumerate(function_calls_data):
            try:
                function_call = FunctionCall(
                    id=f"tool_{i}",
                    name=function_call_data["name"],
                    arguments=function_call_data["arguments"]
                )
                function_calls.append(function_call)
                print(f"[系统] 工具 {i+1}: {function_call_data['name']}")
            except Exception as e:
                error_msg = f"创建FunctionCall对象失败: {e}"
                print(f"[错误] {error_msg}")
                return [], False, error_msg

        return function_calls, True, ""
    except Exception as e:
        error_msg = f"创建函数调用对象时出错: {e}"
        print(f"[错误] {error_msg}")
        return [], False, error_msg


async def _execute_function_calls(function_calls, workbench, agent_name, cancellation_token):
    """
    执行函数调用并返回结果

    Args:
        function_calls: FunctionCall对象列表
        workbench: 工具工作台
        agent_name: 代理名称
        cancellation_token: 取消令牌

    Returns:
        元组 (执行结果列表, 是否成功, 错误消息)
    """
    # 动态导入，避免启动时依赖错误
    from autogen_agentchat.agents import AssistantAgent

    all_results = []
    try:
        for i, function_call in enumerate(function_calls):
            try:
                print(f"[系统] 执行工具调用 {i+1}/{len(function_calls)}: {function_call.name}")

                # 使用AssistantAgent._execute_tool_call方法执行工具调用
                result_tuple = await AssistantAgent._execute_tool_call(
                    tool_call=function_call,
                    workbench=workbench,
                    handoff_tools=[],
                    agent_name=agent_name,
                    cancellation_token=cancellation_token
                )

                result = result_tuple[1]  # 获取执行结果

                # 添加到结果列表
                all_results.append({
                    "index": i+1,
                    "name": function_call.name,
                    "arguments": function_call.arguments,
                    "success": not result.is_error,
                    "content": result.content
                })

                status = "成功" if not result.is_error else "失败"
                print(f"[系统] 工具调用 {i+1} 执行{status}")

                # 显示文件操作信息
                if function_call.name == "write_file" and not result.is_error:
                    try:
                        args = json.loads(function_call.arguments)
                        print(f"[系统] 已创建/修改文件: {args.get('file_path', '未知文件')}")
                    except:
                        pass
                elif function_call.name == "read_file" and not result.is_error:
                    try:
                        args = json.loads(function_call.arguments)
                        print(f"[系统] 已读取文件: {args.get('file_path', '未知文件')}")
                    except:
                        pass
            except Exception as e:
                print(f"[错误] 执行工具调用 {i+1} 时出错: {e}")
                all_results.append({
                    "index": i+1,
                    "name": function_call.name,
                    "arguments": function_call.arguments,
                    "success": False,
                    "content": f"执行失败: {str(e)}"
                })

        return all_results, True, ""
    except Exception as e:
        error_msg = f"执行函数调用时出错: {e}"
        print(f"[错误] {error_msg}")
        return all_results, False, error_msg


def _format_tool_results(all_results, json_error_message=""):
    """
    格式化工具执行结果为易于理解的文本

    Args:
        all_results: 工具执行结果列表
        json_error_message: JSON解析过程中的错误信息

    Returns:
        格式化后的结果文本
    """
    result_content = ""
    try:
        # 如果有JSON解析错误，添加到结果开头
        if json_error_message:
            result_content += f"⚠️ JSON解析警告: {json_error_message}\n\n"
            result_content += "请在下次工具调用时注意JSON格式，确保符合标准格式。\n\n"

        if len(all_results) == 1:
            result = all_results[0]
            status = "成功" if result["success"] else "失败"

            # 为命令行工具提供更详细的输出格式
            if result['name'] in ['execute_command', 'launch-process']:
                result_content += f"工具 {result['name']} 执行{status}:\n\n"
                result_content += f"{result['content']}"
            else:
                # 其他工具保持原有格式
                result_content += f"工具 {result['name']} 执行{status}:\n\n"
                # 添加参数信息
                try:
                    args = json.loads(result["arguments"])
                    args_str = "\n".join([f"  {k}: {v}" for k, v in args.items()])
                    result_content += f"参数:\n{args_str}\n\n"
                except:
                    pass

                result_content += f"结果:\n{result['content']}"
        else:
            result_content += f"所有工具调用的执行结果 (共 {len(all_results)} 次调用):\n\n"
            for result in all_results:
                status = "成功" if result["success"] else "失败"
                result_content += f"=== 工具: {result['name']} (调用 {result['index']}/{len(all_results)}) ===\n"
                result_content += f"状态: {status}\n"

                # 添加参数信息
                try:
                    args = json.loads(result["arguments"])
                    args_str = "\n".join([f"  {k}: {v}" for k, v in args.items()])
                    result_content += f"参数:\n{args_str}\n\n"
                except:
                    pass

                # 为命令行工具保持原始格式，其他工具添加额外格式
                if result['name'] in ['execute_command', 'launch-process']:
                    result_content += f"结果:\n{result['content']}\n\n"
                else:
                    result_content += f"结果:\n{result['content']}\n\n"

        return result_content
    except Exception as e:
        print(f"[错误] 格式化工具结果时出错: {e}")
        return f"格式化工具结果时出错: {e}\n\n原始结果: {all_results}"


async def process_and_execute_tool_calls(content, workbench, agent_name, cancellation_token):
    """
    处理并执行AI助手回复中的工具调用。

    此函数执行以下步骤:
    1. 解析工具调用JSON
    2. 创建FunctionCall对象
    3. 执行工具调用
    4. 格式化结果
    5. 返回结果内容

    Args:
        content: AI助手的回复内容
        workbench: 工具工作台
        agent_name: 代理名称
        cancellation_token: 取消令牌

    Returns:
        元组 (结果内容, 是否成功, 错误消息)
        - 如果成功，结果内容为格式化后的工具执行结果
        - 如果失败，结果内容为原始内容或错误信息
    """

    if not isinstance(content, str) or "tool_calls" not in content:
        return content, True, ""

    print("\n[系统] 解析工具调用...")
    try:
        # 步骤1: 解析工具调用JSON
        function_calls_data, success, error_message = process_tool_calls_json(content)

        # 保存JSON解析错误信息，即使解析成功也可能有警告
        json_error_message = error_message if error_message else ""

        if not success or not function_calls_data:
            print(f"[错误] 工具调用解析失败: {error_message}")
            return content, False, error_message

        print(f"[系统] 成功解析 {len(function_calls_data)} 个工具调用")
        if json_error_message:
            print(f"[警告] JSON解析有问题: {json_error_message}")

        # 步骤2: 创建FunctionCall对象
        function_calls, success, error_message = await _create_function_calls(function_calls_data)
        if not success or not function_calls:
            print(f"[错误] 创建FunctionCall对象失败: {error_message}")
            return content, False, error_message

        # 步骤3: 执行工具调用
        all_results, success, error_message = await _execute_function_calls(
            function_calls, workbench, agent_name, cancellation_token
        )
        if not success:
            print(f"[警告] 执行工具调用时出现问题: {error_message}")
            # 继续处理，因为可能有部分工具调用成功了

        # 步骤4: 格式化结果，包含JSON解析错误信息
        result_content = _format_tool_results(all_results, json_error_message)

        # 返回格式化后的结果内容
        return result_content, True, ""

    except Exception as e:
        error_msg = f"处理工具调用时出错: {e}"
        print(f"[错误] {error_msg}")
        return content, False, error_msg

# 导出主要函数
__all__ = [
    # 基本JSON解析函数
    'extract_json_from_text',
    'fix_json_string',
    'parse_json_safely',

    # 工具调用处理函数
    'extract_tool_calls',
    'validate_tool_call',
    'prepare_function_call',
    'process_tool_calls_json',

    # 工具调用执行函数
    'process_and_execute_tool_calls',

    # 辅助函数 (内部使用)
    '_create_function_calls',
    '_execute_function_calls',
    '_format_tool_results'
]

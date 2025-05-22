# AutoGen 0.5.6 版本自定义工具开发核心指南

本文档提供 AutoGen 0.5.6 版本中自定义工具开发的清晰、简洁的指南，重点介绍 `FunctionTool` 和 `AssistantAgent` 的使用，以及处理第三方模型工具调用的方法。

## 1. 核心概念：FunctionTool 与 Schema

* **BaseTool**: `autogen_core.tools.BaseTool` 是所有工具的抽象基类。
* **FunctionTool**: `autogen_core.tools.FunctionTool` 是创建工具的主要方式，它包装 Python 函数，使其可由代理执行。它利用 Python 的类型注解和文档字符串自动生成工具的 Schema。
* **工具 Schema**: 一个 JSON 结构，描述工具的名称（Name）、描述（Description）和参数（Parameters）。LLM 使用 Schema 来理解工具的功能、何时调用以及如何传递参数。一个定义良好的 Schema 至关重要。
    * **自动生成**: `FunctionTool` 从 Python 函数的名称、文档字符串（作为描述）和类型提示（作为参数）自动生成 Schema。
    * **重要提示**: 不建议使用 `dict`作为工具参数，因为 AutoGen 无法从中自动生成详细的 Schema。应使用显式的、类型化的参数或 Pydantic 模型。

## 2. 使用 FunctionTool 开发自定义工具

1. **编写 Python 函数**:
    * **文档字符串 (Docstrings)**: 必须清晰描述函数的目标、功能和用例，这将成为 Schema 中的工具描述。
    * **类型注解 (Type Annotations)**: 所有参数和返回值都必须有类型注解，用于生成 Schema 中的参数类型和属性。没有默认值的参数被标记为必需。
    * **`typing_extensions.Annotated`**: 可用于为单个参数提供更详细的描述或格式信息。

2. **包装函数为 FunctionTool**:
    ```python
    from autogen_core.tools import FunctionTool
    
    my_tool = FunctionTool(my_python_function, description="可选的覆盖描述")
    ```
    如果将原始 Python 函数直接传递给 `AssistantAgent` 的 `tools` 列表，`AssistantAgent` 通常会自动完成此包装。

3. **检查自动生成的 Schema**:
    ```python
    print(my_tool.schema)
    ```
    检查 Schema 以确保其准确反映工具的预期接口。

**示例：天气查询工具**
```python
import random
from typing_extensions import Annotated
from autogen_core.tools import FunctionTool
from autogen_core import CancellationToken # 导入 CancellationToken

async def get_current_weather(
    location: Annotated[str, "需要查询天气的城市，例如：北京"],
    unit: Annotated[str, "温度单位，可以是 'celsius' 或 'fahrenheit'"] = "celsius"
) -> str:
    """获取指定城市的当前天气信息。"""
    if unit not in ["celsius", "fahrenheit"]:
        return "错误的单位。请使用 'celsius' 或 'fahrenheit'。"
    temperature = random.randint(-10 if unit == "celsius" else 14, 35 if unit == "celsius" else 95)
    condition = random.choice(["晴朗", "多云", "小雨", "雷阵雨"])
    return f"{location} 当前天气：{condition}，温度 {temperature}°{unit.capitalize()}。"

weather_tool = FunctionTool(func=get_current_weather)
# print(weather_tool.schema) # 检查 Schema
```

## 3. 将自定义工具与 AssistantAgent 集成

* **`tools` 参数**: 在初始化 `AssistantAgent` 时，通过 `tools` 参数传递 Python 函数或 `FunctionTool` 实例列表。
    ```python
    from autogen_agentchat.agents import AssistantAgent
    # 假设 model_client 已配置
    # agent = AssistantAgent(name="MyToolUser", model_client=model_client, tools=[get_current_weather, another_tool])
    ```
* **工具调用生命周期**:
    1. LLM 根据对话历史和工具 Schema 决定使用哪个工具。
    2. LLM 生成包含工具名称和参数的工具调用请求。
    3. `AssistantAgent` 接收请求，找到对应工具并执行。
* **`ToolCallSummaryMessage`**: 当 `reflect_on_tool_use=False` (默认情况之一) 时，工具输出作为字符串在 `ToolCallSummaryMessage` 中返回。
* **`reflect_on_tool_use`**: 若为 `True`，代理会在工具执行后进行一次额外的 LLM 调用，以更自然语言的形式总结或反思工具结果。

## 4. 手动工具调用执行与第三方模型 (AutoGen 0.5.6)

当使用第三方模型（如 Ollama）或需要更精细控制工具调用时，可以手动解析模型输出并执行。

* **期望的工具调用 JSON 格式**:
    ```json
    {
      "tool_calls": [
        {
          "type": "function",
          "function": {
            "name": "工具名称",
            "arguments": {
              "参数1": "值1",
              "参数2": "值2"
            }
          }
        }
      ]
    }
    ```
    确保第三方模型输出符合此格式，或编写转换逻辑。

* **使用 `AssistantAgent._execute_tool_call`**:
    1. **创建 `StaticWorkbench`**: 包含所有可用工具。
        ```python
        from autogen_core.tools import StaticWorkbench
        # tools = [weather_tool, ...] # 工具列表
        # workbench = StaticWorkbench(tools)
        ```
    2. **解析模型输出**: 从模型响应中提取工具调用信息。清理可能存在的额外标记（如 Ollama 输出中的 `IGNORE_WHEN_COPYING_START`）。
    3. **创建 `FunctionCall` 对象**:
        ```python
        import json
        from autogen_core import FunctionCall
        # 假设 tool_call_data 是从模型输出解析得到的单个工具调用
        # function_data = tool_call_data["function"]
        # tool_name = function_data["name"]
        # arguments_str = json.dumps(function_data["arguments"]) #确保参数是字符串
        #
        # function_call = FunctionCall(
        #     id="tool_some_id", # 为调用生成唯一ID
        #     name=tool_name,
        #     arguments=arguments_str
        # )
        ```
    4. **执行工具调用**:
        ```python
        # from autogen_core import CancellationToken
        # cancellation_token = CancellationToken()
        #
        # # 假设 assistant_agent 是一个 AssistantAgent 实例
        # result_tuple = await assistant_agent._execute_tool_call(
        #     tool_call=function_call,
        #     workbench=workbench,
        #     handoff_tools=[], # 通常为空，除非有特殊切换逻辑
        #     agent_name="ExecutingAgentName",
        #     cancellation_token=cancellation_token
        # )
        # original_call, execution_result = result_tuple
        # print(f"工具执行结果: {execution_result.content}")
        # print(f"是否出错: {execution_result.is_error}")
        ```

* **自定义工具解析器**: 对于复杂的模型输出，可以编写自定义解析函数，将原始模型输出转换为 `FunctionCall` 对象列表。
    ```python
    def parse_my_model_tool_calls(model_output: str) -> list[FunctionCall]:
        function_calls = []
        try:
            # 清理和解析 model_output...
            # 示例：假设模型直接输出符合AutoGen期望的JSON数组的字符串
            clean_output = model_output.replace("IGNORE_WHEN_COPYING_START", "").replace("IGNORE_WHEN_COPYING_END", "")
            data = json.loads(clean_output)

            if "tool_calls" in data and isinstance(data["tool_calls"], list):
                for i, tc_data in enumerate(data["tool_calls"]):
                    if tc_data.get("type") == "function" and "function" in tc_data:
                        func_data = tc_data["function"]
                        args_str = json.dumps(func_data.get("arguments", {}))
                        function_calls.append(
                            FunctionCall(id=f"call_{i}", name=func_data["name"], arguments=args_str)
                        )
        except Exception as e:
            print(f"解析工具调用出错: {e}")
        return function_calls
    ```

## 5. 高级注意事项与最佳实践

* **输入处理**: `FunctionTool` 根据 Schema 处理参数反序列化。类型提示至关重要。
* **输出结果**: 返回清晰、简洁的结果。若输出复杂，考虑 `reflect_on_tool_use=True`。
* **错误处理**: 在工具函数内部使用 `try-except` 块捕获预期错误，并返回有意义的错误消息。这使得代理系统更具弹性。
* **常见错误**:
    * **Schema 不匹配**: 改进工具描述或参数定义。
    * **工具未被调用**: 优化工具名称和描述。
    * **工具执行内部错误**: 在工具函数内实现 `try-except`。
* **设计**: 编写通用、清晰的工具。
* **依赖管理**: 通过 `requirements.txt` 或虚拟环境管理工具的外部 Python 包依赖。
* **安全**: 安全处理 API 密钥（环境变量、密钥管理器），注意速率限制。对执行代码或修改文件的工具要考虑沙箱。
* **幂等性**: 如果适用，设计幂等工具（多次调用相同输入产生相同结果）。

## 6. 结论与后续步骤

本指南涵盖了 AutoGen 0.5.6 中自定义工具开发的基础和手动执行方法。为实现更高级功能，可探索：
* **工作台 (Workbenches)**: 如 `StaticWorkbench`，用于管理工具集合。
* **有状态工具 (Stateful Tools)**: 通过子类化 `BaseTool` 实现。
* **内置工具 (Built-in Tools)**: 查阅 `autogen_ext.tools` 模块。

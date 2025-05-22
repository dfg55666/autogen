"""
Browserless工具模板 - 基于AutoGen 0.5.6的Browserless API工具模板

本模板提供了创建基于Browserless API的AutoGen工具的基本结构，
可以作为开发新的浏览器自动化工具的起点。

主要特点:
- 兼容AutoGen 0.5.6的FunctionTool格式
- 封装了Browserless API的调用逻辑
- 支持执行JavaScript脚本并获取结果
- 包含完整的错误处理和日志记录
"""

import os
import json
import requests
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
# 配置区域 - Browserless API配置
# =====================================================================

# 从环境变量或直接在此处设置您的 API Token
# 强烈建议从环境变量读取 TOKEN，而不是硬编码
TOKEN = os.environ.get("BROWSERLESS_TOKEN", "")
if not TOKEN:
    print("警告: BROWSERLESS_TOKEN 环境变量未设置。请设置有效的Token。")

# Browserless API端点
BROWSERLESS_FUNCTION_URL = f"https://production-sfo.browserless.io/function?token={TOKEN}"

# =====================================================================
# 核心功能区域 - Browserless API调用函数
# =====================================================================

def run_js_on_browserless(
    js_script: str,
    target_url: str,
    wait_for_selector: Optional[str] = None,
    timeout_ms: int = 60000
) -> Dict[str, Any]:
    """
    使用Browserless API在指定URL上执行JavaScript脚本。
    
    参数:
        js_script: 要执行的JavaScript脚本内容
        target_url: 要访问的目标URL
        wait_for_selector: 可选的CSS选择器，等待该元素出现后再执行脚本
        timeout_ms: 超时时间（毫秒）
        
    返回:
        包含执行结果的字典
    """
    if not TOKEN:
        return {
            "status": "failure",
            "error": "Browserless API Token未配置",
            "details": "请设置BROWSERLESS_TOKEN环境变量或在脚本中提供有效的Token"
        }
    
    headers = {
        "Content-Type": "application/javascript"
    }
    
    # 构建Browserless脚本
    browserless_script = f"""
    export default async function ({{ page }}) {{
      let operationStatus = "failure";
      let errorMessage = null;
      let pageTitle = null;
      let detailsMessage = "Script execution initiated.";
      let extractedData = null;
      
      try {{
        // 导航到目标URL
        detailsMessage = `Navigating to target URL: {target_url}`;
        await page.goto("{target_url}", {{ waitUntil: 'networkidle0', timeout: {timeout_ms} }});
        pageTitle = await page.title();
        detailsMessage = `Navigation successful. Page title: ${{pageTitle}}`;
        
        // 如果提供了选择器，等待该元素出现
        {f'await page.waitForSelector("{wait_for_selector}", {{ timeout: {timeout_ms} }});' if wait_for_selector else ''}
        {f'detailsMessage = `Selector "{wait_for_selector}" found.`;' if wait_for_selector else ''}
        
        // 执行提供的JavaScript脚本
        detailsMessage = "Executing JavaScript...";
        extractedData = await page.evaluate(() => {{
          {js_script}
        }});
        
        if (extractedData !== null && extractedData !== undefined) {{
          operationStatus = "success";
          detailsMessage = "JavaScript execution successful.";
        }} else {{
          operationStatus = "partial_success";
          detailsMessage = "JavaScript executed but returned no data.";
          errorMessage = "No data returned by script.";
        }}
        
      }} catch (e) {{
        console.error("Error during script execution:", e.name, e.message, e.stack);
        errorMessage = e.name + ": " + e.message;
        operationStatus = "failure";
        detailsMessage = "An error occurred during script execution: " + errorMessage;
        try {{
          pageTitle = await page.title();
        }} catch(_) {{}}
      }}
      
      return {{
        data: {{
          status: operationStatus,
          pageTitle: pageTitle,
          details: detailsMessage,
          result: extractedData,
          error: errorMessage
        }},
        type: "application/json",
      }};
    }}
    """
    
    try:
        response = requests.post(BROWSERLESS_FUNCTION_URL, headers=headers, data=browserless_script.encode('utf-8'), timeout=120)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        return { "data": { "status": "failure", "details": "Request to browserless.io timed out.", "error": "Timeout" } }
    except requests.exceptions.RequestException as e:
        raw_response_text = None
        status_code = "N/A"
        if hasattr(e, 'response') and e.response is not None:
            raw_response_text = e.response.text
            status_code = e.response.status_code
        return { "data": { "status": "failure", "details": f"Error communicating with browserless.io (HTTP {status_code}): {str(e)}", "error": raw_response_text or str(e) } }
    except ValueError as e:
        raw_response_text = response.text if 'response' in locals() and hasattr(response, 'text') else 'N/A'
        return { "data": { "status": "failure", "details": f"Failed to parse JSON response from browserless.io: {str(e)}", "error": raw_response_text } }

# =====================================================================
# 工具函数定义区域 - 在此处添加您的工具函数
# =====================================================================

def example_browserless_tool(
    target_url: Annotated[str, "要访问的网页URL，例如: 'https://example.com'"],
    js_code: Annotated[str, "要在页面上执行的JavaScript代码，应该返回一个值"] = "return document.title;",
    wait_for_element: Annotated[Optional[str], "可选的CSS选择器，等待该元素出现后再执行脚本"] = None
) -> Dict[str, Any]:
    """
    示例Browserless工具，在指定URL上执行JavaScript代码并返回结果。
    
    此函数演示了如何使用Browserless API创建一个基本的浏览器自动化工具。
    在实际开发中，请替换为您的实际工具功能。
    
    参数:
        target_url: 要访问的网页URL
        js_code: 要在页面上执行的JavaScript代码
        wait_for_element: 可选的CSS选择器，等待该元素出现后再执行脚本
        
    返回:
        包含操作结果的字典
    """
    print(f"示例Browserless工具被调用:")
    print(f"  目标URL: {target_url}")
    print(f"  等待元素: {wait_for_element if wait_for_element else '无'}")
    print(f"  JavaScript代码: {js_code[:100]}..." if len(js_code) > 100 else f"  JavaScript代码: {js_code}")
    
    # 调用Browserless API
    result = run_js_on_browserless(
        js_script=js_code,
        target_url=target_url,
        wait_for_selector=wait_for_element
    )
    
    # 处理结果
    if result and 'data' in result and isinstance(result['data'], dict):
        print(f"  执行状态: {result['data'].get('status')}")
        if result['data'].get('status') == 'success':
            print(f"  页面标题: {result['data'].get('pageTitle')}")
            print(f"  执行结果: {str(result['data'].get('result'))[:100]}..." if len(str(result['data'].get('result'))) > 100 else f"  执行结果: {result['data'].get('result')}")
            return {
                "status": "success",
                "page_title": result['data'].get('pageTitle'),
                "result": result['data'].get('result')
            }
        else:
            print(f"  错误: {result['data'].get('error')}")
            return {
                "status": "failure",
                "error": result['data'].get('error'),
                "details": result['data'].get('details')
            }
    else:
        print(f"  错误: 无效的响应格式")
        return {
            "status": "failure",
            "error": "无效的响应格式",
            "raw_response": result
        }

# =====================================================================
# 工具实例创建区域 - 在此处创建您的工具实例
# =====================================================================

# 创建工具实例
try:
    example_browserless_tool_instance = FunctionTool(
        func=example_browserless_tool,
        name="ExampleBrowserlessTool",
        description="示例Browserless工具，在指定URL上执行JavaScript代码并返回结果"
    )
    print("工具 'ExampleBrowserlessTool' 创建成功。")
    
    # 将所有工具实例添加到工具列表中
    browserless_tool_list = [
        example_browserless_tool_instance,
        # 在此处添加更多工具实例
    ]
    
except (AttributeError, TypeError, NameError) as e:
    print(f"警告: 创建工具实例时出错: {e}")
    example_browserless_tool_instance = None
    browserless_tool_list = []

# =====================================================================
# 测试代码区域 - 用于直接测试工具功能
# =====================================================================

if __name__ == "__main__":
    print("\n=== Browserless工具测试模式 ===")
    
    # 检查TOKEN是否有效
    if not TOKEN:
        print("错误: 无效的Browserless API Token。请设置BROWSERLESS_TOKEN环境变量。测试中止。")
    else:
        # 测试示例工具
        print("\n测试示例Browserless工具:")
        test_result = example_browserless_tool(
            target_url="https://example.com",
            js_code="return { title: document.title, content: document.body.textContent.substring(0, 200) };"
        )
        
        # 美化输出结果
        print("\n工具执行结果:")
        print(json.dumps(test_result, indent=2, ensure_ascii=False))
    
    print("\n=== 测试完成 ===")

# =====================================================================
# 导出区域 - 导出工具函数和工具列表
# =====================================================================

__all__ = [
    # 核心函数
    "run_js_on_browserless",
    
    # 工具函数
    "example_browserless_tool",
    
    # 工具实例
    "example_browserless_tool_instance",
    
    # 工具列表
    "browserless_tool_list"
]

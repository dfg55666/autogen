"""
Browserless API 工具模块 - 基于 AutoGen 0.5.6 的浏览器自动化工具

本模块提供了一组用于浏览器自动化的工具，基于 Browserless 的 BrowserQL API，
并与 AutoGen 0.5.6 集成。

主要功能:
- 导航到网页
- 点击元素
- 输入文本
- 获取页面内容
- 截图
- 等待元素出现
- 执行 JavaScript

使用方法:
```python
from department.utils.browserless_tools import get_browserless_tools

# 获取所有工具
tools = get_browserless_tools(api_key="your-api-key")

# 在 AssistantAgent 中使用
assistant = AssistantAgent(
    name="browser_assistant",
    llm_config={"config_list": [{"model": "gpt-3.5-turbo"}]},
    tools=tools
)
```
"""

import os
import json
import base64
import asyncio
import aiohttp
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from typing_extensions import Annotated
import urllib.parse

# 尝试导入JSON解析器
try:
    from department.utils.json_parser import process_tool_calls_json
    JSON_PARSER_AVAILABLE = True
except ImportError:
    JSON_PARSER_AVAILABLE = False
    print("警告: 未找到JSON解析器模块，将使用基本JSON解析")

# 获取当前模块的路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Browserless工具目录
BROWSERLESS_TOOLS_DIR = os.path.join(CURRENT_DIR, "Browserless")

# 尝试导入 AutoGen 相关模块
AUTOGEN_AVAILABLE = False
try:
    from autogen_core.tools import FunctionTool
    from autogen_core import CancellationToken
    AUTOGEN_AVAILABLE = True
except ImportError:
    print("警告: 未找到 AutoGen 模块，工具将无法作为 FunctionTool 使用")
    # 定义一个空的 FunctionTool 类，以便代码可以继续运行
    class FunctionTool:
        def __init__(self, func, **kwargs):
            self.func = func
            self.kwargs = kwargs

class BrowserlessClient:
    """Browserless API 客户端类"""

    def __init__(self, api_key: str, endpoint: str = "https://chrome.browserless.io", use_graphql: bool = False):
        """
        初始化 Browserless 客户端

        Args:
            api_key: Browserless API 密钥
            endpoint: Browserless API 端点，默认为官方端点
            use_graphql: 是否使用 GraphQL API (BrowserQL)，默认为 False
        """
        self.api_key = api_key
        self.endpoint = endpoint
        self.use_graphql = use_graphql
        self.session = None
        self.ws = None  # WebSocket 连接，用于 GraphQL API
        self.connected = False

    async def connect(self):
        """连接到 Browserless API"""
        if self.connected:
            return

        if not self.session:
            connector = aiohttp.TCPConnector(ssl=False)  # 禁用 SSL 验证以便于调试
            self.session = aiohttp.ClientSession(connector=connector)

        # 如果使用 GraphQL API，则建立 WebSocket 连接
        if self.use_graphql:
            try:
                # 构建 WebSocket URL
                ws_url = self.endpoint

                # 根据端点类型转换协议
                if ws_url.startswith("https://"):
                    ws_url = ws_url.replace("https://", "wss://")
                elif ws_url.startswith("http://"):
                    ws_url = ws_url.replace("http://", "ws://")

                # 添加路径和令牌
                ws_url = f"{ws_url}/bql?token={self.api_key}"

                print(f"尝试连接到 BrowserQL WebSocket URL: {ws_url}")

                self.ws = await self.session.ws_connect(ws_url)
                print("已连接到 BrowserQL WebSocket API")
            except Exception as e:
                print(f"连接到 BrowserQL 失败: {e}")
                print("将使用 HTTP API 作为备选")
                self.use_graphql = False

        self.connected = True
        print(f"已连接到 Browserless API (使用 {'GraphQL' if self.use_graphql else 'HTTP'} API)")
        return {"success": True, "message": f"已成功连接到 Browserless API (使用 {'GraphQL' if self.use_graphql else 'HTTP'} API)"}

    async def disconnect(self):
        """断开与 Browserless API 的连接"""
        if self.ws:
            await self.ws.close()
            self.ws = None

        if self.session:
            await self.session.close()
            self.session = None

        self.connected = False
        print("已断开与 Browserless API 的连接")
        return {"success": True, "message": "已成功断开与 Browserless API 的连接"}

    async def execute_query(self, query: str, variables: Dict = None) -> Dict:
        """
        执行 GraphQL 查询

        Args:
            query: GraphQL 查询字符串
            variables: 查询变量

        Returns:
            Dict: 查询结果
        """
        if not self.use_graphql:
            return {"error": "GraphQL API 未启用，请使用 use_graphql=True 初始化客户端"}

        if not self.connected or not self.ws:
            await self.connect()
            if not self.use_graphql:
                return {"error": "无法连接到 GraphQL API，已自动切换到 HTTP API"}

        # 构建 GraphQL 请求
        request = {
            "query": query,
            "variables": variables or {}
        }

        # 发送请求
        await self.ws.send_json(request)

        # 接收响应
        response = await self.ws.receive_json()

        # 检查错误
        if "errors" in response:
            errors = response["errors"]
            error_message = errors[0].get("message", "未知错误")
            print(f"GraphQL 查询错误: {error_message}")
            return {"error": error_message}

        return response.get("data", {})

    async def get_content(self, url: str, wait_for: int = 1000, timeout: int = 30000) -> Dict:
        """
        获取网页内容

        Args:
            url: 要访问的网页 URL
            wait_for: 等待时间（毫秒）
            timeout: 超时时间（毫秒）

        Returns:
            Dict: 包含 HTML 内容的字典
        """
        if not self.connected:
            await self.connect()

        content_url = f"{self.endpoint}/content?token={self.api_key}"

        try:
            async with self.session.post(
                content_url,
                json={
                    "url": url,
                    "waitFor": wait_for
                },
                timeout=timeout / 1000  # 转换为秒
            ) as response:
                if response.status == 200:
                    html_content = await response.text()
                    return {"html": html_content, "status": response.status}
                else:
                    error_text = await response.text()
                    return {"error": error_text, "status": response.status}
        except Exception as e:
            return {"error": str(e)}

    async def take_screenshot(self, url: str, selector: str = None, type: str = "png",
                             full_page: bool = True, quality: int = None, timeout: int = 30000) -> Dict:
        """
        截取网页截图

        Args:
            url: 要截图的网页 URL
            selector: 要截图的元素选择器 (可选)
            type: 截图类型 ('png' 或 'jpeg')
            full_page: 是否截取整个页面
            quality: 图片质量 (1-100)，仅对 JPEG 有效
            timeout: 超时时间（毫秒）

        Returns:
            Dict: 包含 Base64 编码的截图数据的字典
        """
        if not self.connected:
            await self.connect()

        screenshot_url = f"{self.endpoint}/screenshot?token={self.api_key}"

        options = {
            "type": type,
            "fullPage": full_page
        }

        # 仅当类型为 jpeg 且 quality 不为 None 时添加 quality 参数
        if type.lower() == "jpeg" and quality is not None:
            options["quality"] = quality

        if selector:
            options["selector"] = selector

        try:
            async with self.session.post(
                screenshot_url,
                json={
                    "url": url,
                    "options": options
                },
                timeout=timeout / 1000  # 转换为秒
            ) as response:
                if response.status == 200:
                    screenshot_data = await response.read()
                    # 将二进制数据转换为 Base64
                    base64_data = base64.b64encode(screenshot_data).decode('utf-8')
                    return {"data": base64_data, "type": type, "status": response.status}
                else:
                    error_text = await response.text()
                    return {"error": error_text, "status": response.status}
        except Exception as e:
            return {"error": str(e)}

    async def execute_function(self, code: str, context: Dict = None, timeout: int = 30000) -> Dict:
        """
        执行自定义函数

        Args:
            code: 要执行的 JavaScript 函数代码
            context: 函数上下文
            timeout: 超时时间（毫秒）

        Returns:
            Dict: 包含函数执行结果的字典
        """
        if not self.connected:
            await self.connect()

        function_url = f"{self.endpoint}/function?token={self.api_key}"

        try:
            async with self.session.post(
                function_url,
                json={
                    "code": code,
                    "context": context or {}
                },
                timeout=timeout / 1000  # 转换为秒
            ) as response:
                if response.status == 200:
                    try:
                        result = await response.json()
                        return {"result": result, "status": response.status}
                    except:
                        # 如果无法解析为 JSON，则返回文本
                        text_result = await response.text()
                        return {"result": text_result, "status": response.status}
                else:
                    error_text = await response.text()
                    return {"error": error_text, "status": response.status}
        except Exception as e:
            return {"error": str(e)}

    async def load_script(self, script_path: str, timeout: int = 30000) -> Dict:
        """
        加载并执行JavaScript脚本文件

        Args:
            script_path: 脚本文件路径（相对于Browserless工具目录）
            timeout: 超时时间（毫秒）

        Returns:
            Dict: 包含脚本执行结果的字典
        """
        if not self.connected:
            await self.connect()

        # 构建完整的脚本路径
        full_path = os.path.join(BROWSERLESS_TOOLS_DIR, script_path)

        # 检查文件是否存在
        if not os.path.exists(full_path):
            return {"error": f"脚本文件不存在: {script_path}"}

        # 读取脚本内容
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                script_content = f.read()
        except Exception as e:
            return {"error": f"读取脚本文件失败: {str(e)}"}

        # 执行脚本
        return await self.execute_function(script_content, timeout=timeout)

    async def load_tool_module(self, module_name: str = "loader") -> Dict:
        """
        加载工具模块

        Args:
            module_name: 模块名称，默认为"loader"

        Returns:
            Dict: 包含加载结果的字典
        """
        # 构建模块路径
        module_path = f"{module_name}.js"

        # 加载模块
        result = await self.load_script(module_path)

        if "error" in result:
            return result

        # 如果是加载器模块，尝试执行loadAllTools函数
        if module_name == "loader":
            load_code = """
            module.exports = async ({ page }) => {
                try {
                    // 执行loadAllTools函数
                    const loadResult = loadAllTools();
                    return loadResult;
                } catch (error) {
                    return { error: error.message };
                }
            };
            """

            return await self.execute_function(load_code)

        return {"success": True, "message": f"已加载模块: {module_name}"}

# 单例客户端
_client_instance = None

def get_client(api_key: str, endpoint: str = "https://chrome.browserless.io", use_graphql: bool = False) -> BrowserlessClient:
    """
    获取或创建 Browserless 客户端实例

    Args:
        api_key: Browserless API 密钥
        endpoint: Browserless API 端点
        use_graphql: 是否使用 GraphQL API (BrowserQL)，默认为 False

    Returns:
        BrowserlessClient: 客户端实例
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = BrowserlessClient(api_key, endpoint, use_graphql)
    elif _client_instance.api_key != api_key or _client_instance.endpoint != endpoint or _client_instance.use_graphql != use_graphql:
        # 如果参数变化，则创建新的实例
        if _client_instance.connected:
            # 确保旧实例断开连接
            import asyncio
            asyncio.create_task(_client_instance.disconnect())
        _client_instance = BrowserlessClient(api_key, endpoint, use_graphql)
    return _client_instance

# 核心操作函数
async def goto(
    url: Annotated[str, "要访问的网页 URL"],
    api_key: Annotated[str, "Browserless API 密钥"],
    wait_until: Annotated[str, "等待页面加载的条件，可选值: 'load', 'domcontentloaded', 'networkidle0', 'networkidle2'"] = "load",
    timeout: Annotated[Optional[int], "超时时间（毫秒）"] = 30000,
    endpoint: Annotated[str, "Browserless API 端点"] = "https://chrome.browserless.io",
    use_graphql: Annotated[bool, "是否使用 GraphQL API"] = False
) -> Dict:
    """
    跳转到指定网址

    使用 Browserless API 导航到指定的网页 URL，并等待页面加载完成。

    Args:
        url: 要访问的网页 URL（必须是完整的 URL，包含 http:// 或 https://）
        api_key: Browserless API 密钥
        wait_until: 等待页面加载的条件，可选值: 'load', 'domcontentloaded', 'networkidle0', 'networkidle2'
        timeout: 超时时间（毫秒），默认为 30000 毫秒（30 秒）
        endpoint: Browserless API 端点
        use_graphql: 是否使用 GraphQL API，默认为 False

    Returns:
        Dict: 包含状态码和其他响应信息的字典

    示例:
        ```python
        result = await goto(
            url="https://example.com",
            api_key="your-api-key",
            wait_until="load"
        )
        print(result)  # {'status': 200, 'url': 'https://example.com/'}
        ```
    """
    client = get_client(api_key, endpoint, use_graphql)

    if client.use_graphql:
        # 使用 GraphQL API
        query = """
        mutation Goto($url: String!, $waitUntil: WaitUntilGoto, $timeout: Float) {
          goto(url: $url, waitUntil: $waitUntil, timeout: $timeout) {
            status
            url
          }
        }
        """

        variables = {
            "url": url,
            "waitUntil": wait_until,
            "timeout": timeout
        }

        try:
            result = await client.execute_query(query, variables)
            goto_result = result.get("goto", {})
            if goto_result:
                return goto_result
            elif "error" in result:
                # 如果 GraphQL 查询失败，尝试使用 HTTP API
                print(f"GraphQL 查询失败: {result['error']}，尝试使用 HTTP API")
                client.use_graphql = False
            else:
                return {"status": 200, "url": url}  # 假设成功
        except Exception as e:
            print(f"GraphQL 查询异常: {e}，尝试使用 HTTP API")
            client.use_graphql = False

    # 使用 HTTP API
    # 构建 goto 选项
    goto_options = {"waitUntil": wait_until}

    # 使用 content API 导航到 URL 并获取内容
    content_url = f"{endpoint}/content?token={api_key}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                content_url,
                json={
                    "url": url,
                    "gotoOptions": goto_options,
                    "waitFor": 1000  # 等待 1 秒确保页面加载
                },
                timeout=timeout / 1000  # 转换为秒
            ) as response:
                if response.status == 200:
                    return {"status": response.status, "url": url}
                else:
                    error_text = await response.text()
                    return {"error": error_text, "status": response.status}
    except Exception as e:
        return {"error": str(e)}

async def click(
    selector: Annotated[str, "要点击的元素选择器，支持CSS选择器、JavaScript表达式或Browserless深度查询"],
    api_key: Annotated[str, "Browserless API 密钥"],
    scroll: Annotated[bool, "是否在点击前滚动到元素位置"] = True,
    visible: Annotated[bool, "是否只在元素可见时点击"] = False,
    wait: Annotated[bool, "是否等待元素出现"] = True,
    timeout: Annotated[Optional[int], "超时时间（毫秒）"] = 30000,
    endpoint: Annotated[str, "Browserless API 端点"] = "https://chrome.browserless.io",
    use_graphql: Annotated[bool, "是否使用 GraphQL API"] = False
) -> Dict:
    """
    点击页面上的元素

    等待元素出现，滚动到元素位置，然后使用原生事件点击元素。

    Args:
        selector: 要点击的元素选择器，支持以下格式：
                 - CSS 选择器: "button"
                 - JavaScript 表达式: "document.querySelector('button')"
                 - Browserless 深度查询: "< button" (以 < 开头)
                 - 深度查询示例: "< https://example.com/* button.active" (在 iframe 中查找)
        api_key: Browserless API 密钥
        scroll: 是否在点击前滚动到元素位置，默认为 True
        visible: 是否只在元素可见时点击，默认为 False
        wait: 是否等待元素出现，默认为 True
        timeout: 超时时间（毫秒），默认为 30000 毫秒（30 秒）
        endpoint: Browserless API 端点

    Returns:
        Dict: 包含点击操作结果的字典，包括操作耗时

    示例:
        ```python
        # 点击页面上的第一个链接
        result = await click(
            selector="a",
            api_key="your-api-key"
        )
        print(result)  # {'time': 123} (耗时毫秒数)
        ```
    """
    client = get_client(api_key, endpoint, use_graphql)

    if client.use_graphql:
        # 使用 GraphQL API
        query = """
        mutation Click($selector: String!, $scroll: Boolean, $visible: Boolean, $wait: Boolean, $timeout: Float) {
          click(selector: $selector, scroll: $scroll, visible: $visible, wait: $wait, timeout: $timeout) {
            time
          }
        }
        """

        variables = {
            "selector": selector,
            "scroll": scroll,
            "visible": visible,
            "wait": wait,
            "timeout": timeout
        }

        try:
            result = await client.execute_query(query, variables)
            if "error" in result:
                # 如果 GraphQL 查询失败，尝试使用 HTTP API
                print(f"GraphQL 查询失败: {result['error']}，尝试使用 HTTP API")
                client.use_graphql = False
            else:
                return result.get("click", {})
        except Exception as e:
            print(f"GraphQL 查询异常: {e}，尝试使用 HTTP API")
            client.use_graphql = False

    # 使用 HTTP API (通过 function API 执行点击操作)
    code = f"""
    module.exports = async ({{ page }}) => {{
        try {{
            const element = await page.$("{selector}");
            if (!element) return {{ error: "未找到元素" }};

            if ({str(scroll).lower()}) {{
                await element.scrollIntoView();
            }}

            const options = {{
                visible: {str(visible).lower()},
                waitFor: {str(wait).lower()},
                timeout: {timeout}
            }};

            await element.click(options);
            return {{ success: true }};
        }} catch (error) {{
            return {{ error: error.message }};
        }}
    }};
    """

    result = await client.execute_function(code=code)
    if "result" in result and isinstance(result["result"], dict):
        if "error" in result["result"]:
            return {"error": result["result"]["error"]}
        else:
            return {"success": True}
    else:
        return {"error": "点击操作失败"}

async def type_text(
    selector: Annotated[str, "要输入文本的元素选择器"],
    text: Annotated[str, "要输入的文本"],
    api_key: Annotated[str, "Browserless API 密钥"],
    delay: Annotated[int, "每个字符之间的延迟（毫秒）"] = 10,
    timeout: Annotated[Optional[int], "超时时间（毫秒）"] = 30000,
    endpoint: Annotated[str, "Browserless API 端点"] = "https://chrome.browserless.io",
    use_graphql: Annotated[bool, "是否使用 GraphQL API"] = False
) -> Dict:
    """
    在页面元素中输入文本

    通过滚动到元素位置，点击元素，然后为每个字符发送按键事件来输入文本。

    Args:
        selector: 要输入文本的元素选择器
        text: 要输入的文本内容
        api_key: Browserless API 密钥
        delay: 每个字符之间的延迟（毫秒），默认为 10 毫秒
        timeout: 超时时间（毫秒），默认为 30000 毫秒（30 秒）
        endpoint: Browserless API 端点

    Returns:
        Dict: 包含输入操作结果的字典，包括操作耗时

    示例:
        ```python
        # 在搜索框中输入文本
        result = await type_text(
            selector="input[type='text']",
            text="Hello, World!",
            api_key="your-api-key"
        )
        print(result)  # {'time': 456} (耗时毫秒数)
        ```
    """
    client = get_client(api_key, endpoint, use_graphql)

    if client.use_graphql:
        # 使用 GraphQL API
        query = """
        mutation Type($selector: String!, $text: String!, $delay: Float, $timeout: Float) {
          type(selector: $selector, text: $text, delay: $delay, timeout: $timeout) {
            time
          }
        }
        """

        variables = {
            "selector": selector,
            "text": text,
            "delay": delay,
            "timeout": timeout
        }

        try:
            result = await client.execute_query(query, variables)
            if "error" in result:
                # 如果 GraphQL 查询失败，尝试使用 HTTP API
                print(f"GraphQL 查询失败: {result['error']}，尝试使用 HTTP API")
                client.use_graphql = False
            else:
                return result.get("type", {})
        except Exception as e:
            print(f"GraphQL 查询异常: {e}，尝试使用 HTTP API")
            client.use_graphql = False

    # 使用 HTTP API (通过 function API 执行输入操作)
    code = f"""
    module.exports = async ({{ page }}) => {{
        try {{
            const element = await page.$("{selector}");
            if (!element) return {{ error: "未找到元素" }};

            // 点击元素以确保焦点
            await element.click();

            // 输入文本
            await element.type("{text}", {{ delay: {delay} }});

            return {{ success: true }};
        }} catch (error) {{
            return {{ error: error.message }};
        }}
    }};
    """

    result = await client.execute_function(code=code)
    if "result" in result and isinstance(result["result"], dict):
        if "error" in result["result"]:
            return {"error": result["result"]["error"]}
        else:
            return {"success": True}
    else:
        return {"error": "输入操作失败"}

async def get_html(
    api_key: Annotated[str, "Browserless API 密钥"],
    url: Annotated[Optional[str], "要获取HTML的网页URL，如果不提供则获取当前页面"] = None,
    selector: Annotated[Optional[str], "要获取HTML的元素选择器，如果不提供则获取整个页面"] = None,
    endpoint: Annotated[str, "Browserless API 端点"] = "https://chrome.browserless.io",
    use_graphql: Annotated[bool, "是否使用 GraphQL API"] = False
) -> Dict:
    """
    获取页面或元素的HTML内容

    使用 Browserless API 获取指定页面或元素的HTML内容。

    Args:
        api_key: Browserless API 密钥
        url: 要获取HTML的网页URL，如果不提供则获取当前页面
        selector: 要获取HTML的元素选择器，如果不提供则获取整个页面
        endpoint: Browserless API 端点

    Returns:
        Dict: 包含HTML内容的字典
    """
    client = get_client(api_key, endpoint, use_graphql)

    if url:
        if client.use_graphql:
            # 使用 GraphQL API 获取页面内容
            query = """
            mutation GetContent($url: String!, $waitFor: Float) {
              content(url: $url, waitFor: $waitFor) {
                html
              }
            }
            """

            variables = {
                "url": url,
                "waitFor": 1000
            }

            try:
                result = await client.execute_query(query, variables)
                if "error" in result:
                    # 如果 GraphQL 查询失败，尝试使用 HTTP API
                    print(f"GraphQL 查询失败: {result['error']}，尝试使用 HTTP API")
                    client.use_graphql = False
                elif "content" in result and "html" in result["content"]:
                    return {"html": result["content"]["html"]}
            except Exception as e:
                print(f"GraphQL 查询异常: {e}，尝试使用 HTTP API")
                client.use_graphql = False

        # 使用 HTTP API 获取页面内容
        content_url = f"{endpoint}/content?token={api_key}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    content_url,
                    json={
                        "url": url,
                        "waitFor": 1000
                    },
                    timeout=30  # 30秒超时
                ) as response:
                    if response.status == 200:
                        html_content = await response.text()
                        return {"html": html_content, "status": response.status}
                    else:
                        error_text = await response.text()
                        return {"error": error_text, "status": response.status}
        except Exception as e:
            return {"error": str(e)}

    elif selector:
        # 如果提供了选择器，则使用 function API 获取元素内容
        code = f"""
        module.exports = async ({{ page }}) => {{
            try {{
                const element = await page.$('{selector}');
                if (!element) return {{ error: '未找到元素' }};
                const html = await page.evaluate(el => el.outerHTML, element);
                return {{ html }};
            }} catch (error) {{
                return {{ error: error.message }};
            }}
        }}
        """
        result = await client.execute_function(code=code)
        if "result" in result and isinstance(result["result"], dict) and "html" in result["result"]:
            return {"html": result["result"]["html"]}
        else:
            return {"error": "获取元素HTML失败"}
    else:
        # 如果既没有提供URL也没有提供选择器，则返回错误
        return {"error": "必须提供url或selector参数"}

async def take_screenshot(
    api_key: Annotated[str, "Browserless API 密钥"],
    url: Annotated[str, "要截图的网页URL"] = "about:blank",
    selector: Annotated[Optional[str], "要截图的元素选择器，如果不提供则截取整个页面"] = None,
    type: Annotated[str, "截图类型，可选值: 'jpeg', 'png'"] = "png",
    quality: Annotated[Optional[int], "图片质量（1-100），仅对JPEG有效"] = None,
    full_page: Annotated[bool, "是否截取整个页面"] = True,
    omitBackground: Annotated[bool, "是否省略背景"] = False,
    endpoint: Annotated[str, "Browserless API 端点"] = "https://chrome.browserless.io",
    use_graphql: Annotated[bool, "是否使用 GraphQL API"] = False
) -> Dict:
    """
    截取页面或元素的屏幕截图

    使用 Browserless API 截取指定页面或元素的屏幕截图。

    Args:
        api_key: Browserless API 密钥
        url: 要截图的网页URL，必须提供有效的URL
        selector: 要截图的元素选择器，如果不提供则截取整个页面
        type: 截图类型，可选值: 'jpeg', 'png'，默认为 'png'
        quality: 图片质量（1-100），仅对 JPEG 有效
        full_page: 是否截取整个页面，默认为 True
        omitBackground: 是否省略背景使截图透明，默认为 False
        endpoint: Browserless API 端点

    Returns:
        Dict: 包含 Base64 编码的截图数据的字典，格式为 {'data': '...', 'type': 'png'}

    示例:
        ```python
        # 截取整个页面的截图
        result = await take_screenshot(
            url="https://example.com",
            api_key="your-api-key"
        )

        # 保存截图到文件
        if "data" in result:
            import base64
            with open("screenshot.png", "wb") as f:
                f.write(base64.b64decode(result["data"]))
        ```
    """
    client = get_client(api_key, endpoint, use_graphql)

    if client.use_graphql:
        # 使用 GraphQL API 获取截图
        query = """
        mutation Screenshot($url: String!, $options: ScreenshotOptions) {
          screenshot(url: $url, options: $options) {
            data
            type
          }
        }
        """

        # 构建截图选项
        options = {
            "type": type,
            "fullPage": full_page,
            "omitBackground": omitBackground
        }

        # 仅当类型为 jpeg 且 quality 不为 None 时添加 quality 参数
        if type.lower() == "jpeg" and quality is not None:
            options["quality"] = quality

        # 如果提供了选择器，添加到选项中
        if selector:
            options["selector"] = selector

        variables = {
            "url": url,
            "options": options
        }

        try:
            result = await client.execute_query(query, variables)
            if "error" in result:
                # 如果 GraphQL 查询失败，尝试使用 HTTP API
                print(f"GraphQL 查询失败: {result['error']}，尝试使用 HTTP API")
                client.use_graphql = False
            elif "screenshot" in result and "data" in result["screenshot"]:
                return {
                    "data": result["screenshot"]["data"],
                    "type": result["screenshot"]["type"],
                    "status": 200
                }
        except Exception as e:
            print(f"GraphQL 查询异常: {e}，尝试使用 HTTP API")
            client.use_graphql = False

    # 使用 HTTP API 获取页面截图
    screenshot_url = f"{endpoint}/screenshot?token={api_key}"

    options = {
        "type": type,
        "fullPage": full_page,
        "omitBackground": omitBackground
    }

    # 仅当类型为 jpeg 且 quality 不为 None 时添加 quality 参数
    if type.lower() == "jpeg" and quality is not None:
        options["quality"] = quality

    # 如果提供了选择器，添加到选项中
    if selector:
        options["selector"] = selector

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                screenshot_url,
                json={
                    "url": url,
                    "options": options
                },
                timeout=30  # 30秒超时
            ) as response:
                if response.status == 200:
                    screenshot_data = await response.read()
                    # 将二进制数据转换为 Base64
                    base64_data = base64.b64encode(screenshot_data).decode('utf-8')
                    return {"data": base64_data, "type": type, "status": response.status}
                else:
                    error_text = await response.text()
                    return {"error": error_text, "status": response.status}
    except Exception as e:
        return {"error": str(e)}

async def wait_for_selector(
    selector: Annotated[str, "要等待的元素选择器"],
    api_key: Annotated[str, "Browserless API 密钥"],
    visible: Annotated[bool, "是否等待元素可见"] = False,
    hidden: Annotated[bool, "是否等待元素隐藏"] = False,
    timeout: Annotated[Optional[int], "超时时间（毫秒）"] = 30000,
    endpoint: Annotated[str, "Browserless API 端点"] = "https://chrome.browserless.io"
) -> Dict:
    """
    等待页面上的元素出现或消失

    使用 Browserless API 等待页面上的指定元素出现或消失。

    Args:
        selector: 要等待的元素选择器
        api_key: Browserless API 密钥
        visible: 是否等待元素可见
        hidden: 是否等待元素隐藏
        timeout: 超时时间（毫秒）
        endpoint: Browserless API 端点

    Returns:
        Dict: 包含等待操作结果的字典
    """
    client = get_client(api_key, endpoint)

    query = """
    mutation WaitForSelector($selector: String!, $visible: Boolean, $hidden: Boolean, $timeout: Float) {
      waitForSelector(selector: $selector, visible: $visible, hidden: $hidden, timeout: $timeout) {
        time
      }
    }
    """

    variables = {
        "selector": selector,
        "visible": visible,
        "hidden": hidden,
        "timeout": timeout
    }

    try:
        result = await client.execute_query(query, variables)
        return result.get("waitForSelector", {})
    except Exception as e:
        return {"error": str(e)}

async def evaluate_javascript(
    script: Annotated[str, "要执行的JavaScript代码"],
    api_key: Annotated[str, "Browserless API 密钥"],
    args: Annotated[Optional[List[Any]], "传递给脚本的参数"] = None,
    endpoint: Annotated[str, "Browserless API 端点"] = "https://chrome.browserless.io"
) -> Dict:
    """
    在页面上执行 JavaScript 代码

    在浏览器的页面环境中执行 JavaScript 代码，可以返回任何可序列化的值。

    Args:
        script: 要执行的 JavaScript 代码，这段代码会被包装在一个异步函数中，
               因此可以使用 await 和其他异步概念，也可以使用 return 返回值
        api_key: Browserless API 密钥
        args: 传递给脚本的参数列表
        endpoint: Browserless API 端点

    Returns:
        Dict: 包含脚本执行结果的字典，格式为 {'result': 执行结果}

    示例:
        ```python
        # 执行简单的 JavaScript 代码
        result = await evaluate_javascript(
            script="return document.title",
            api_key="your-api-key"
        )
        print(result)  # {'result': '页面标题'}

        # 执行复杂的 JavaScript 代码
        result = await evaluate_javascript(
            script="return { url: window.location.href, title: document.title, links: Array.from(document.querySelectorAll('a')).map(a => ({ text: a.textContent, href: a.href })) }",
            api_key="your-api-key"
        )
        ```
    """
    client = get_client(api_key, endpoint)

    query = """
    mutation Evaluate($script: String!, $args: [JSON]) {
      evaluate(script: $script, args: $args) {
        result
      }
    }
    """

    variables = {
        "script": script,
        "args": args or []
    }

    try:
        result = await client.execute_query(query, variables)
        return result.get("evaluate", {})
    except Exception as e:
        return {"error": str(e)}

# 工具列表将在下面定义

async def connect_browser(
    api_key: Annotated[str, "Browserless API 密钥"],
    endpoint: Annotated[str, "Browserless API 端点"] = "https://chrome.browserless.io"
) -> Dict:
    """
    连接到 Browserless WebSocket API

    建立与 Browserless WebSocket API 的连接。

    Args:
        api_key: Browserless API 密钥
        endpoint: Browserless API 端点

    Returns:
        Dict: 包含连接状态的字典
    """
    client = get_client(api_key, endpoint)

    try:
        await client.connect()
        return {"success": True, "message": "已成功连接到 Browserless API"}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def disconnect_browser(
    api_key: Annotated[str, "Browserless API 密钥"],
    endpoint: Annotated[str, "Browserless API 端点"] = "https://chrome.browserless.io"
) -> Dict:
    """
    断开与 Browserless WebSocket API 的连接

    关闭与 Browserless WebSocket API 的连接。

    Args:
        api_key: Browserless API 密钥
        endpoint: Browserless API 端点

    Returns:
        Dict: 包含断开连接状态的字典
    """
    client = get_client(api_key, endpoint)

    try:
        await client.disconnect()
        return {"success": True, "message": "已成功断开与 Browserless API 的连接"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# 高级工具函数

async def load_browser_tools(
    api_key: Annotated[str, "Browserless API 密钥"],
    endpoint: Annotated[str, "Browserless API 端点"] = "https://chrome.browserless.io"
) -> Dict:
    """
    加载浏览器工具模块

    加载并初始化所有自定义JavaScript工具模块，包括HTML解析器、搜索助手和页面交互助手。

    Args:
        api_key: Browserless API 密钥
        endpoint: Browserless API 端点

    Returns:
        Dict: 包含加载结果的字典
    """
    client = get_client(api_key, endpoint)

    try:
        # 确保已连接
        if not client.connected:
            await client.connect()

        # 加载工具模块
        result = await client.load_tool_module("loader")

        if "error" in result:
            return {"success": False, "error": f"加载工具模块失败: {result['error']}"}

        return {"success": True, "message": "已成功加载浏览器工具模块", "details": result}
    except Exception as e:
        return {"success": False, "error": str(e)}





async def extract_page_metadata(
    api_key: Annotated[str, "Browserless API 密钥"],
    endpoint: Annotated[str, "Browserless API 端点"] = "https://chrome.browserless.io"
) -> Dict:
    """
    提取当前页面的元数据

    提取当前页面的元数据，包括标题、描述、关键词、规范URL、Open Graph元数据和Twitter卡片元数据。

    Args:
        api_key: Browserless API 密钥
        endpoint: Browserless API 端点

    Returns:
        Dict: 包含页面元数据的字典
    """
    client = get_client(api_key, endpoint)

    try:
        # 确保已连接
        if not client.connected:
            await client.connect()

        # 执行提取函数
        code = """
        module.exports = async ({ page }) => {
            try {
                // 检查extractPageMetadata函数是否可用
                if (typeof extractPageMetadata !== 'function') {
                    // 如果函数不可用，尝试加载工具模块
                    if (typeof loadAllTools === 'function') {
                        loadAllTools();
                    } else {
                        return { error: "未找到extractPageMetadata函数，请先加载工具模块" };
                    }
                }

                // 执行提取
                const metadata = extractPageMetadata();
                return metadata;
            } catch (error) {
                return { error: error.message };
            }
        };
        """

        result = await client.execute_function(code)

        if "error" in result:
            return {"success": False, "error": f"提取页面元数据失败: {result['error']}"}

        if "result" in result and isinstance(result["result"], dict):
            if "error" in result["result"]:
                return {"success": False, "error": result["result"]["error"]}
            else:
                return {"success": True, "metadata": result["result"]}

        return {"success": False, "error": "提取页面元数据失败，返回格式不正确"}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def extract_page_summary(
    api_key: Annotated[str, "Browserless API 密钥"],
    endpoint: Annotated[str, "Browserless API 端点"] = "https://chrome.browserless.io"
) -> Dict:
    """
    提取当前页面的摘要信息

    提取当前页面的摘要信息，包括标题、描述、主要内容、图片和链接等。

    Args:
        api_key: Browserless API 密钥
        endpoint: Browserless API 端点

    Returns:
        Dict: 包含页面摘要的字典
    """
    client = get_client(api_key, endpoint)

    try:
        # 确保已连接
        if not client.connected:
            await client.connect()

        # 执行提取函数
        code = """
        module.exports = async ({ page }) => {
            try {
                // 检查extractPageSummary函数是否可用
                if (typeof extractPageSummary !== 'function') {
                    // 如果函数不可用，尝试加载工具模块
                    if (typeof loadAllTools === 'function') {
                        loadAllTools();
                    } else {
                        return { error: "未找到extractPageSummary函数，请先加载工具模块" };
                    }
                }

                // 执行提取
                const summary = extractPageSummary();
                return { summary };
            } catch (error) {
                return { error: error.message };
            }
        };
        """

        result = await client.execute_function(code)

        if "error" in result:
            return {"success": False, "error": f"提取页面摘要失败: {result['error']}"}

        if "result" in result and isinstance(result["result"], dict):
            if "error" in result["result"]:
                return {"success": False, "error": result["result"]["error"]}
            elif "summary" in result["result"]:
                return {"success": True, "summary": result["result"]["summary"]}

        return {"success": False, "error": "提取页面摘要失败，返回格式不正确"}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def analyze_webpage(
    api_key: Annotated[str, "Browserless API 密钥"],
    endpoint: Annotated[str, "Browserless API 端点"] = "https://chrome.browserless.io"
) -> Dict:
    """
    分析当前网页内容

    分析当前网页内容，提取关键信息并确定页面类型。

    Args:
        api_key: Browserless API 密钥
        endpoint: Browserless API 端点

    Returns:
        Dict: 包含网页分析结果的字典
    """
    client = get_client(api_key, endpoint)

    try:
        # 确保已连接
        if not client.connected:
            await client.connect()

        # 执行分析函数
        code = """
        module.exports = async ({ page }) => {
            try {
                // 检查analyzeWebpage函数是否可用
                if (typeof analyzeWebpage !== 'function') {
                    // 如果函数不可用，尝试加载工具模块
                    if (typeof loadAllTools === 'function') {
                        loadAllTools();
                    } else {
                        return { error: "未找到analyzeWebpage函数，请先加载工具模块" };
                    }
                }

                // 执行分析
                const analysis = analyzeWebpage();
                return { analysis };
            } catch (error) {
                return { error: error.message };
            }
        };
        """

        result = await client.execute_function(code)

        if "error" in result:
            return {"success": False, "error": f"分析网页失败: {result['error']}"}

        if "result" in result and isinstance(result["result"], dict):
            if "error" in result["result"]:
                return {"success": False, "error": result["result"]["error"]}
            elif "analysis" in result["result"]:
                return {"success": True, "analysis": result["result"]["analysis"]}

        return {"success": False, "error": "分析网页失败，返回格式不正确"}
    except Exception as e:
        return {"success": False, "error": str(e)}





# 更新工具列表，添加连接和断开连接的工具
def get_browserless_tools(api_key: str, endpoint: str = "https://chrome.browserless.io", use_graphql: bool = False) -> List[FunctionTool]:
    """
    获取 Browserless 工具列表

    Args:
        api_key: Browserless API 密钥
        endpoint: Browserless API 端点
        use_graphql: 是否使用 GraphQL API (BrowserQL)，默认为 False

    Returns:
        List[FunctionTool]: FunctionTool 列表
    """
    if not AUTOGEN_AVAILABLE:
        print("警告: AutoGen 模块不可用，无法创建 FunctionTool 实例")
        return []

    # 创建工具列表
    tools = [
        FunctionTool(
            func=connect_browser,
            name="browserless_connect",
            description="连接到 Browserless API，在使用其他工具前必须先调用此工具"
        ),
        FunctionTool(
            func=goto,
            name="browserless_goto",
            description=f"跳转到指定网址并等待页面加载，支持多种加载条件 (使用 {'GraphQL' if use_graphql else 'HTTP'} API)"
        ),
        FunctionTool(
            func=click,
            name="browserless_click",
            description=f"点击页面上的元素，支持CSS选择器、JavaScript表达式或深度查询 (使用 {'GraphQL' if use_graphql else 'HTTP'} API)"
        ),
        FunctionTool(
            func=type_text,
            name="browserless_type",
            description=f"在页面元素中输入文本，可控制输入速度 (使用 {'GraphQL' if use_graphql else 'HTTP'} API)"
        ),
        FunctionTool(
            func=get_html,
            name="browserless_html",
            description=f"获取页面或指定元素的HTML内容 (使用 {'GraphQL' if use_graphql else 'HTTP'} API)"
        ),
        FunctionTool(
            func=take_screenshot,
            name="browserless_screenshot",
            description=f"截取页面或元素的屏幕截图，支持PNG和JPEG格式 (使用 {'GraphQL' if use_graphql else 'HTTP'} API)"
        ),
        FunctionTool(
            func=wait_for_selector,
            name="browserless_wait_for_selector",
            description="等待页面上的元素出现或消失，可设置可见性条件"
        ),
        FunctionTool(
            func=evaluate_javascript,
            name="browserless_evaluate",
            description="在页面上执行JavaScript代码，可返回执行结果"
        ),
        FunctionTool(
            func=disconnect_browser,
            name="browserless_disconnect",
            description="断开与 Browserless API 的连接，使用完毕后应调用此工具"
        ),
        # 添加高级工具
        FunctionTool(
            func=load_browser_tools,
            name="browserless_load_tools",
            description="加载浏览器工具模块，包括HTML解析器、搜索助手和页面交互助手"
        ),

        FunctionTool(
            func=extract_page_metadata,
            name="browserless_extract_metadata",
            description="提取当前页面的元数据，包括标题、描述、关键词等"
        ),
        # 添加新的工具
        FunctionTool(
            func=extract_page_summary,
            name="browserless_extract_summary",
            description="提取当前页面的摘要信息，包括标题、描述、主要内容、图片和链接等"
        ),
        FunctionTool(
            func=analyze_webpage,
            name="browserless_analyze_webpage",
            description="分析当前网页内容，提取关键信息并确定页面类型"
        ),

    ]

    # 搜索功能已被移除

    return tools



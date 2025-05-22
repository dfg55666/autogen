"""
CDP调试器工具模块 - 基于AutoGen的Chrome DevTools Protocol调试工具

本模块提供了一组用于连接到CDP浏览器并进行网站分析和解密的工具，
融合了AI_JS_DEBUGGER-main项目的功能，并与AutoGen集成。

主要功能:
- 连接到CDP浏览器 (使用Playwright)
- 设置JavaScript断点
- 设置XHR请求断点 (支持调用栈回溯)
- AI驱动的自动单步调试
- 生成解密分析报告 (AI辅助)

与AutoGen集成:
- 所有功能都通过FunctionTool包装 (如果AutoGen可用)
- 支持异步操作
- 提供详细的错误处理和日志记录
"""

import os
import sys
import json
import asyncio
import tempfile
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from typing_extensions import Annotated
import uuid
import jsbeautifier # 用于格式化代码片段

# 尝试导入AutoGen相关模块
AUTOGEN_AVAILABLE = False
try:
    from autogen_core.tools import FunctionTool
    from autogen_core import CancellationToken # 虽然未使用，但保持完整性
    AUTOGEN_AVAILABLE = True
except ImportError:
    print("警告: 未找到AutoGen核心模块，工具将无法作为FunctionTool使用。请尝试 `pip install autogen-core`")
    class FunctionTool: # type: ignore
        def __init__(self, func, **kwargs):
            self.func = func
            self.kwargs = kwargs
            print(f"FunctionTool mock created for {func.__name__}")

# 尝试导入Playwright相关模块
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import async_playwright, Page, BrowserContext, Browser as PlaywrightBrowser, CDPSession
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    print("警告: 未找到playwright模块，请安装: pip install playwright && playwright install")

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("cdp_debugger")

# 全局会话状态 (注意：在并发AutoGen Agent场景下，全局变量可能需要更复杂的会话管理)
class BrowserSession:
    def __init__(self, playwright_instance, browser: PlaywrightBrowser, context: BrowserContext, page: Page, cdp_client: CDPSession, cdp_port: int):
        self._playwright_instance = playwright_instance
        self.browser = browser
        self.context = context
        self.page = page
        self.client = cdp_client # This is the CDPSession
        self.cdp_port = cdp_port
        self.debug_session_file: Optional[str] = None
        self.script_source_cache: Dict[str, str] = {}
        self.xhr_backtrace_tasks: List[asyncio.Task] = [] # 用于管理XHR回溯任务

    async def close(self):
        logger.info("开始关闭浏览器会话...")
        for task in self.xhr_backtrace_tasks:
            if not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=1.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    logger.debug("XHR回溯任务取消/超时。")
                except Exception as e:
                    logger.error(f"关闭XHR回溯任务时出错: {e}")
        self.xhr_backtrace_tasks.clear()

        if self.client and self.client.is_connected():
            try:
                # 尝试优雅地分离CDP会话
                await self.client.detach()
                logger.info("CDP会话已分离。")
            except Exception as e:
                logger.warning(f"分离CDP会话时出错: {e}")

        # Playwright会自动处理CDP会话的关闭，当页面或上下文关闭时
        if self.page and not self.page.is_closed():
            try:
                await self.page.close()
                logger.info("页面已关闭。")
            except Exception as e:
                logger.warning(f"关闭页面时出错: {e}")

        if self.context: # Playwright的context没有is_closed()，依赖browser.is_connected()
            try:
                await self.context.close()
                logger.info("浏览器上下文已关闭。")
            except Exception as e:
                logger.warning(f"关闭浏览器上下文时出错: {e}")

        if self.browser and self.browser.is_connected():
            try:
                await self.browser.close()
                logger.info("浏览器实例已关闭。")
            except Exception as e:
                logger.warning(f"关闭浏览器实例时出错: {e}")

        if self._playwright_instance:
            try:
                await self._playwright_instance.stop()
                logger.info("Playwright实例已停止。")
            except Exception as e:
                logger.warning(f"停止Playwright实例时出错: {e}")

        self.script_source_cache.clear()
        logger.info("浏览器会话关闭完成。")

_browser_session: Optional[BrowserSession] = None

# 结果目录
RESULT_DIR = Path("cdp_debugger_results") # 使用Path对象
LOG_DIR = RESULT_DIR / "logs"
REPORT_DIR = RESULT_DIR / "reports"

# 确保结果目录存在
LOG_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# --- 提示词模板 (与原项目保持一致或按需修改) ---
# (从您的原始文件中复制)
DEBUG_INSTRUCTION_PROMPT = '''
任务：根据JavaScript调试信息分析加密相关代码并决定最优调试策略。

分析重点：
1. 加密函数识别：
   - 函数名包含encrypt/decrypt/AES/RSA/DES/MD5/SHA/Hash/Crypto/签名/code等关键词
   - JavaScript特有加密：btoa/atob(Base64)、TextEncoder/TextDecoder、crypto.subtle等Web API
   - 位运算加密：XOR(^)、位移(<<,>>)、按位与(&)、按位或(|)等操作
2. 可疑函数调用：
   - 网络请求相关：fetch/XMLHttpRequest/axios/$.ajax/sendData*/getToken*/getSign*/request*
   - 数据处理相关：JSON.parse/stringify、URLSearchParams、FormData操作
3. 加密库识别：
   - 主流库：CryptoJS/WebCrypto/forge/jsencrypt/crypto-js/sjcl/noble-*
   - 自定义库：检测_加密函数命名模式、特定算法实现特征
4. 数据转换操作：
   - 编码转换：Base64/HEX/UTF-8/encodeURIComponent/escape
   - 字符串操作：toString/fromCharCode/charCodeAt/padStart/padEnd/split/join
   - 数组操作：TypedArray(Uint8Array等)、Array.from、map/reduce用于字节处理
5. 混淆代码识别：
   - 动态执行：eval/Function构造函数/setTimeout+字符串/new Function()
   - 字符串拼接：大量的字符串拼接、字符编码转换、数组join操作
   - 控制流扁平化：大型switch-case结构、状态机模式、大量条件判断
   - 变量混淆：单字符变量、数字变量名、无意义变量名
6. 可疑参数：IV/key/salt/mode/padding/secret/token/sign/signature等加密参数

精确决策规则：
- 【step_into】发现首次出现的加密相关函数调用时，进入该函数内部
- 【step_over】已经处于加密函数内部时，对非核心操作进行单步跳过
- 【step_into】遇到eval、Function构造函数、动态执行代码时，尝试进入查看实际执行内容
- 【step_out】深入3层以上的内部库函数实现或重复的循环操作时，跳出当前函数
- 【step_out】连续3次在相同位置或相似上下文中执行或"作用域中未找到相关变量"时，避免调试陷入循环
- 【step_over】遇到大量混淆代码或控制流扁平化结构时，优先跳过复杂逻辑直到返回有意义结果
输出格式：仅返回单一JSON对象，三个字段中只有一个为true
{
  "step_into": false,
  "step_over": false,
  "step_out": false
}
'''

DEBUGGER_ANALYZE_PROMPT = '''
这是我的JavaScript调试信息，请帮我分析：

1. 加解密方法识别：
   - 识别所有加密/解密函数及其调用链
   - 分析加密算法类型（对称/非对称/哈希等）
   - 识别自定义加密算法和混淆技术

2. 密钥提取：
   - 提取所有加密密钥、IV、salt等参数
   - 分析密钥生成/派生逻辑
   - 识别密钥存储位置（本地存储/Cookie/内存）

3. 关键代码分析：
   - 提取核心加解密逻辑，简化并注释
   - 分析混淆代码的实际功能
   - 识别动态执行代码（eval/Function）的实际内容

4. 编写mitmproxy脚本：
   - 实现请求/响应数据的解密和加密
   - 处理特殊头部和参数
   - 确保脚本简洁高效

请保持分析简洁，不需要加固建议，专注于核心加解密逻辑和mitmproxy脚本实现。
'''
SYSTEM_ROLE_PROMPT = '''
你是一个专业的JavaScript代码分析专家，擅长分析加密算法和网络请求
'''

# --- 辅助函数 (使用AutoGen的AI) ---
async def get_llm_debug_instruction(debug_info_json_str: str, model_name: str = "default_model") -> str:
    """
    使用简单的规则来决定下一步调试指令。
    在实际使用中，这个函数会被AutoGen的AI替代。
    """
    # 简单的规则逻辑
    await asyncio.sleep(0.1)  # 模拟处理时间
    logger.info(f"调试决策: 收到调试信息，长度 {len(debug_info_json_str)}")

    # 基于关键词的简单决策
    if "encrypt" in debug_info_json_str.lower() or "decrypt" in debug_info_json_str.lower():
         return json.dumps({"step_into": True, "step_over": False, "step_out": False})
    if "callStack" in debug_info_json_str and len(json.loads(debug_info_json_str).get("callStack", [])) > 3:
         return json.dumps({"step_into": False, "step_over": False, "step_out": True})
    return json.dumps({"step_into": False, "step_over": True, "step_out": False})


async def get_llm_analysis_report(session_content: str, model_name: str = "default_model") -> str:
    """
    生成一个简单的分析报告。
    在实际使用中，这个函数会被AutoGen的AI替代。
    """
    await asyncio.sleep(0.1)  # 模拟处理时间
    logger.info(f"分析报告: 收到会话内容，长度 {len(session_content)}")

    # 提取一些基本信息
    step_count = session_content.count("步骤")
    has_encryption = "encrypt" in session_content.lower() or "decrypt" in session_content.lower()
    has_network = "xhr" in session_content.lower() or "fetch" in session_content.lower()

    return f"""
# 调试会话分析报告

## 概述
- 调试步骤数: 约 {step_count} 步
- 包含加密相关代码: {'是' if has_encryption else '否'}
- 包含网络请求: {'是' if has_network else '否'}

## 建议
- 检查调试日志中的变量值和调用栈
- 关注可能的加密函数和网络请求处理

**(这是一个自动生成的简单报告)**
"""

# --- CDP核心逻辑函数 (移植并适配自原项目) ---
async def _get_script_source(session: BrowserSession, script_id: str) -> str:
    if script_id in session.script_source_cache:
        return session.script_source_cache[script_id]
    try:
        response = await session.client.send("Debugger.getScriptSource", {"scriptId": script_id})
        source = response.get("scriptSource", "")
        if len(session.script_source_cache) > 100: # 简单缓存大小限制
            session.script_source_cache.popitem()
        session.script_source_cache[script_id] = source
        return source
    except Exception as e:
        logger.error(f"获取脚本源代码(ID: {script_id})出错: {e}")
        return ""

def _should_skip_property(name: str, value_obj: dict) -> bool:
    # (从原项目 debug_processor.py 移植)
    if value_obj is None: return True
    if not name: return True
    if name == "this" or name.startsWith('$'): return True # Note: startsWith is JS, use startswith for Python
    description = value_obj.get("description", "")
    if description in ("Window", "global", "VueComponent", "HTMLDivElement", "HTMLElement", "options"): return True
    if description == "Object" and value_obj.get("className") == "Object" and value_obj.get("subtype") == "object":
        preview = value_obj.get("preview", {})
        properties = preview.get("properties", [])
        return len(properties) > 5 # Only skip if it's a generic object with many properties
    if value_obj.get("type") == "function": return True
    if "Vue" in description or "Window" in description: return True # Be careful with "Window" if you need global vars
    if value_obj.get("value") is None and "description" not in value_obj: return True # Skip if value is None and no description
    if name in {"constructor", "prototype", "$super", "__proto__", "window", "document", "location", "navigator", "history", "performance", "console"}: return True
    return False

async def _get_object_properties(session: BrowserSession, object_id: str, max_depth=1, current_depth=0, max_props=10) -> Any:
    # (简化版，从原项目 debug_processor.py 移植和修改)
    if current_depth > max_depth:
        return "[对象嵌套过深]"
    try:
        props_resp = await session.client.send("Runtime.getProperties", {
            "objectId": object_id,
            "ownProperties": True, # Get own properties
            "accessorPropertiesOnly": False,
            "generatePreview": True
        })

        result_props = {}
        prop_count = 0
        for prop in props_resp.get("result", []):
            if prop_count >= max_props:
                result_props["_truncated"] = f"[显示前{max_props}个属性]"
                break

            name = prop.get("name")
            value_obj = prop.get("value")

            if not name or _should_skip_property(name, value_obj): # type: ignore
                continue

            prop_count +=1
            if "value" in value_obj: # Primitive types or simple descriptions
                result_props[name] = value_obj["value"]
            elif "objectId" in value_obj:
                obj_type = value_obj.get("type")
                obj_subtype = value_obj.get("subtype")
                obj_desc = value_obj.get("description", "[对象]")

                if obj_type == "object" and obj_subtype == "array":
                    # For arrays, try to get a preview or length
                    preview = value_obj.get("preview")
                    if preview and "properties" in preview and len(preview["properties"]) < 5: # show small arrays
                         arr_values = [_p.get('value', _p.get('description', '?')) for _p in preview['properties']]
                         result_props[name] = arr_values
                    else:
                        result_props[name] = f"[数组: {obj_desc}]"

                elif current_depth < max_depth: # Recurse for non-array objects
                    result_props[name] = await _get_object_properties(session, value_obj["objectId"], max_depth, current_depth + 1, max_props=5)
                else:
                    result_props[name] = obj_desc # Max depth reached, just show description
            else:
                result_props[name] = value_obj.get("description", "[未知类型]")
        return result_props
    except Exception as e:
        logger.warning(f"获取对象属性(ID: {object_id})出错: {e}")
        return {"错误": str(e)}


async def _process_debugger_paused(session: BrowserSession, pause_event: Dict) -> Dict:
    # (从原项目 debug_processor.py 移植并适配)
    call_frames = pause_event.get("callFrames", [])
    if not call_frames:
        return {"error": "无法获取调用帧信息"}

    top_frame = call_frames[0]
    location = top_frame["location"]
    script_id = location["scriptId"]
    line_number = location["lineNumber"]
    column_number = location.get("columnNumber", 0)
    function_name = top_frame.get("functionName") or "<anonymous>"

    script_source = await _get_script_source(session, script_id)
    script_url = top_frame.get("url", "unknown_url") # URL is usually in the frame

    # 获取代码片段 (美化)
    code_snippet_raw = ""
    if script_source:
        lines = script_source.splitlines()
        start_line_idx = max(0, line_number - 2)
        end_line_idx = min(len(lines), line_number + 3)
        snippet_lines = []
        for i in range(start_line_idx, end_line_idx):
            prefix = "➤ " if i == line_number else "  "
            snippet_lines.append(f"{prefix}{i + 1:4}: {lines[i]}")
        code_snippet_raw = "\n".join(snippet_lines)

    try:
        # 尝试美化整个脚本或重要片段，这里简化为只美化片段
        beautified_snippet = jsbeautifier.beautify(code_snippet_raw) # May not be ideal for snippets with markers
    except:
        beautified_snippet = code_snippet_raw # Fallback

    # 获取调用栈
    formatted_call_stack = []
    for i, frame_data in enumerate(call_frames[:5]): # Limit call stack depth
        fn_name = frame_data.get("functionName") or "<anonymous>"
        loc = frame_data["location"]
        s_url = frame_data.get("url", "unknown_script")
        ln = loc["lineNumber"]
        cn = loc.get("columnNumber", 0)
        formatted_call_stack.append(f"{i}: {fn_name} at {Path(s_url).name}:{ln}:{cn}")

    # 获取作用域变量 (仅顶层作用域，简化版)
    scope_variables = {}
    if top_frame.get("scopeChain"):
        for scope in top_frame["scopeChain"]:
            # We are interested in 'local' and 'closure', sometimes 'block'
            # Skip 'global' as it's too large
            scope_type = scope.get("type")
            if scope_type in ["local", "closure", "block"]:
                object_id = scope["object"].get("objectId")
                if object_id:
                    try:
                        props = await _get_object_properties(session, object_id, max_depth=0) # shallow
                        if props:
                           scope_variables[f"{scope_type}_{scope.get('name','')}"] = props
                    except Exception as e:
                        logger.warning(f"获取 {scope_type} 作用域变量失败: {e}")


    debug_info = {
        "pausedReason": pause_event.get("reason"),
        "scriptUrl": script_url,
        "functionName": function_name,
        "location": {"lineNumber": line_number, "columnNumber": column_number},
        "codeSnippet": beautified_snippet,
        "callStack": formatted_call_stack,
        "scopeVariables": scope_variables,
        "hitBreakpoints": pause_event.get("hitBreakpoints", [])
    }
    return debug_info


async def _set_breakpoint_internal(session: BrowserSession, script_url_or_regex: str, line: int, column: int = 0, is_regex: bool = False) -> str:
    await session.client.send("Debugger.enable")
    params = {
        "lineNumber": line,
        "columnNumber": column
    }
    if is_regex:
        params["urlRegex"] = script_url_or_regex
    else:
        params["url"] = script_url_or_regex

    result = await session.client.send("Debugger.setBreakpointByUrl", params)
    breakpoint_id = result.get("breakpointId", "unknown")
    actual_locations = result.get("locations", [])
    logger.info(f"已在 {script_url_or_regex}:{line}:{column} 设置断点，ID: {breakpoint_id}, 实际位置: {actual_locations}")
    return breakpoint_id

async def _set_xhr_breakpoint_internal(session: BrowserSession, url_pattern: str = "*"):
    # Playwright's CDP session might not directly support DOMDebugger or Debugger.setXHRBreakpoint
    # We need to use Network request interception or events if direct XHR breakpoints are tricky
    # For now, using the event-based approach for XHR.
    # A true XHR breakpoint pauses *before* the JS that initiated it finishes.
    # This is more like a request listener.
    # The original `set_xhr_breakpoint` was for `pyppeteer`. Playwright handles this differently.
    # Typically, you'd use page.route() for interception or listen to network events.
    # The `set_xhr_new_breakpoint_logic` is more aligned with what we want for tracing.
    await session.client.send("Network.enable") # Ensure network domain is enabled
    # This CDP command might not be directly available or work as expected with Playwright's session management.
    # Consider `page.route()` for intercepting/modifying, or `set_xhr_new_breakpoint_logic` for tracing.
    try:
        await session.client.send("Fetch.enable", {"patterns": [{"urlPattern": url_pattern or "*"}]})
        logger.info(f"已启用Fetch拦截，URL模式: {url_pattern or '*'}. JS将会在匹配的请求处暂停。")
        # Note: This requires handling Fetch.requestPaused events
    except Exception as e:
        logger.warning(f"尝试设置Fetch拦截失败 (备选XHR断点): {e}. 将依赖Network事件。")

    logger.info(f"已设置XHR监听 (通过Network事件)，URL模式: {url_pattern or '所有请求'}")
    return f"已设置XHR监听，URL模式: {url_pattern or '所有请求'}"


async def _set_xhr_new_breakpoint_logic(session: BrowserSession, url_pattern: str, js_ready_event: asyncio.Event):
    logger.info(f"XHR回溯: 开始监听网络请求, URL模式: '{url_pattern or '*'}'")

    # This handler will be called when a request is about to be sent
    async def on_request_paused(event: Dict):
        request_id = event["requestId"]
        request_data = event.get("request", {})
        request_url = request_data.get("url", "")

        # Check if the URL matches the pattern
        if not url_pattern or url_pattern in request_url:
            logger.info(f"XHR回溯: 捕获到匹配的Fetch请求: {request_url} (ID: {request_id})")

            # At this point, JS is paused. We can get the call stack.
            call_frames = event.get("networkStageInfo", {}).get("callFrames") # Playwright might provide this differently
                                                                          # Or we might need to explicitly call Debugger.getStackTrace

            # If callFrames are not directly in Fetch.requestPaused, we might need an alternative
            # For instance, if Fetch.requestPaused gives a source location, use that.
            # Or, after Fetch.enable, any JS execution related to it might hit a general Debugger.pause
            # This part is tricky and Playwright-specific for Fetch domain.

            # Let's assume we need to get the call stack via Debugger.pause and Debugger.paused
            # This means we need a way to trigger Debugger.pause when Fetch.requestPaused happens,
            # or rely on an existing breakpoint.
            # The original AI_JS_DEBUGGER used DOMDebugger.setXHRBreakpoint which is more direct.

            # Simpler approach: when Fetch.requestPaused happens, we are already paused.
            # We need to get the call stack from the Debugger domain.
            # The `event` from `Fetch.requestPaused` *is* the pause event, essentially.
            # However, the call stack might not be readily available in the Fetch event.
            # A common pattern is to use Fetch.enable to pause, then when `Fetch.requestPaused` fires,
            # you get `sourceLocation` if available or you might need to inspect `window.event.target.stack` if it's a UI event.
            # For pure XHRs, the call stack leading to it is what we need.

            # Let's try to get the stack trace from the debugger
            try:
                # Ensure debugger is enabled
                await session.client.send("Debugger.enable")

                # Get current call stack (since Fetch.requestPaused means we are paused)
                # This is a bit of a guess; the exact way to get the stack might differ.
                # Playwright's internal debugger might already have this.
                # We might need to listen to Debugger.paused *after* Fetch.enable.

                # For simplicity, let's assume the top useful frame can be found by:
                # 1. Listening to Debugger.scriptParsed to get all script IDs and URLs.
                # 2. When Fetch.requestPaused, try to find a relevant script.
                # This is becoming very complex to replicate accurately without pyppeteer's specific XHR breakpoint.

                # Reverting to a more robust, event-driven Debugger.paused approach
                # similar to the original project for the XHR tracing part.
                # This means the Fetch.enable above is a bit of a red herring for *tracing*.
                # For tracing, we'll use a general Debugger.pause on XHR.

                # The following logic is adapted from original project's set_xhr_new_breakpoint
                # It assumes *some* breakpoint (could be a generic one) was hit due to XHR.

                # Let's make this function listen for Debugger.paused after enabling network monitoring.
                # This requires the caller (start_debug_session) to actually trigger actions on the page.

                # This function will now be a listener for Debugger.paused, and it will check if the pause
                # reason is related to an XHR/Fetch.
                # This is a conceptual shift from the original `set_xhr_new_breakpoint` which set a specific type of breakpoint.
                # With Playwright, we might need to be more creative.

                # A more direct Playwright way for XHR tracing using routing:
                # await page.route(url_pattern or "**/*", handle_route)
                # async def handle_route(route):
                #   logger.info(f"Intercepted {route.request.method} to {route.request.url}")
                #   await session.client.send("Debugger.pause") # Pause JS
                #   # Now wait for Debugger.paused event to get stack
                #   # ... (logic with asyncio.Future as in original)
                #   await route.continue_() # or route.fulfill(), route.abort()

                # For now, let's keep the original idea of *reacting* to a pause event
                # if it's related to XHR. This function will be registered as a Debugger.paused handler.
                # This means the XHR breakpoint itself is more "virtual".

                # THE CURRENT `set_xhr_new_breakpoint_logic` IS MORE OF A TEMPLATE
                # A robust implementation with Playwright would likely involve `page.route`
                # combined with `Debugger.pause` and then handling `Debugger.paused`.

                # Fallback: if this function is called, we assume a relevant pause happened.
                # This part will be simplified and assume `pause_event` is passed in.

                # This function (`_set_xhr_new_breakpoint_logic`) is becoming problematic
                # in its current form. The original relied on `DOMDebugger.setXHRBreakpoint`.
                # Let's simplify the XHR mode:
                # 1. User says "listen to XHR for /api/data".
                # 2. We don't set a *specific* XHR breakpoint.
                # 3. Instead, `start_debug_session` will, on *any* pause, check if the
                #    current context (e.g., network activity, top of call stack) relates to that XHR.
                # This is less direct.

                # Let's try to implement the spirit of the original:
                # On *any* pause, if the reason is XHR/Fetch, then try to set a JS breakpoint.
                # This means this function should be a Debugger.paused handler.
                # For now, this function is simplified. The complex XHR backtracing is hard with Playwright's CDP session alone
                # without deeper integration with page routing.

                # A simplified XHR "notification" for now.
                logger.info(f"XHR回溯: 监听到 {url_pattern} 相关的活动。请手动检查调用栈。")
                if not js_ready_event.is_set():
                    js_ready_event.set()

            except Exception as e_xhr_proc:
                logger.error(f"XHR回溯: 处理暂停事件时出错: {e_xhr_proc}")
            finally:
                # Ensure execution is resumed if we paused it,
                # but in a Fetch.requestPaused context, we use Fetch.continueRequest etc.
                # This is where direct CDP control gets complex with Playwright's abstractions.
                pass # Resume logic needs to be context-aware (Debugger.resume vs Fetch.continueRequest)
        else: # URL does not match
            try:
                if event.get("resourceType", "").lower() in ["fetch", "xhr"]: # For Fetch domain
                     await session.client.send("Fetch.continueRequest", {"requestId": request_id})
            except Exception: # Ignore if not a fetch event or continue fails
                pass


    # If using Fetch.enable, this is how you'd listen:
    # session.client.on("Fetch.requestPaused", on_request_paused)
    # logger.info(f"XHR回溯: Fetch.requestPaused 监听器已注册 for '{url_pattern or '*'}'")
    # This task would then need to be managed (e.g., awaited or cancelled)

    # For a simpler model, we'll assume that `start_debug_session` will handle pauses,
    # and if `url_pattern` is set, it will be extra vigilant about XHR-like calls.
    # The `js_ready_event` will be set by `start_debug_session` when it deems an XHR-related pause has occurred.
    # This makes `_set_xhr_new_breakpoint_logic` more of a conceptual placeholder for now.
    # This function will not be directly called as a standalone task in this revision
    # due to the complexity of replicating the original behavior with Playwright's CDP.
    # Instead, the XHR "mode" will be a flag in `start_debug_session_async`.
    pass # Placeholder


async def _start_debug_session_internal(
    session: BrowserSession,
    max_steps: int = 20,
    timeout_per_step: int = 20, # Timeout for waiting for a single pause event
    model_name: str = "default_model",
    target_xhr_url_pattern: Optional[str] = None # For XHR mode
):
    session_id = uuid.uuid4().hex[:8]
    session.debug_session_file = LOG_DIR / f"debug_session_{session_id}.txt"
    logger.info(f"开始调试会话 (ID: {session_id}), 日志: {session.debug_session_file}")

    debug_results = []
    debug_step_count = 0

    # Ensure Debugger is enabled
    await session.client.send("Debugger.enable")
    if target_xhr_url_pattern:
        await session.client.send("Network.enable") # For observing network requests
        logger.info(f"XHR模式启用: 监控包含 '{target_xhr_url_pattern}' 的网络请求。")

    # --- Pause event handling ---
    pause_event_future: Optional[asyncio.Future] = None

    async def on_debugger_paused(event_data: Dict):
        nonlocal pause_event_future
        if pause_event_future and not pause_event_future.done():
            logger.debug(f"Debugger.paused event received: {event_data.get('reason')}")
            pause_event_future.set_result(event_data)
        else:
            logger.warning("Debugger.paused event received but no active future to notify.")

    session.client.on("Debugger.paused", on_debugger_paused)
    # --- End Pause event handling ---

    try:
        for step in range(max_steps):
            logger.info(f"调试步骤 {step + 1}/{max_steps}")
            debug_step_count = step + 1

            pause_event_future = asyncio.Future() # type: ignore

            # If this is the first step after an XHR breakpoint was "set",
            # the user needs to trigger the XHR on the page.
            if step == 0 and target_xhr_url_pattern:
                logger.info("XHR模式: 请在网页上执行操作以触发匹配的XHR请求。")

            try:
                logger.debug(f"等待断点触发 (超时: {timeout_per_step}s)...")
                current_pause_event = await asyncio.wait_for(pause_event_future, timeout=timeout_per_step)
            except asyncio.TimeoutError:
                logger.warning("等待断点超时，调试会话结束。")
                break

            logger.info(f"断点已触发! 原因: {current_pause_event.get('reason')}")

            # Process the pause event
            processed_info = await _process_debugger_paused(session, current_pause_event)
            debug_results.append(processed_info)

            # Log to file
            with open(session.debug_session_file, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*20} 步骤 {debug_step_count} {'='*20}\n")
                f.write(json.dumps(processed_info, ensure_ascii=False, indent=2))

            # Get next instruction from LLM
            instruction_json_str = await get_llm_debug_instruction(json.dumps(processed_info), model_name)

            next_action = "Debugger.stepOver" # Default
            try:
                instruction_data = json.loads(instruction_json_str)
                if instruction_data.get("step_into"): next_action = "Debugger.stepInto"
                elif instruction_data.get("step_out"): next_action = "Debugger.stepOut"
                elif instruction_data.get("step_over"): next_action = "Debugger.stepOver"
                else: logger.warning(f"LLM返回无效指令JSON: {instruction_json_str}, 默认 step_over")
            except json.JSONDecodeError:
                logger.warning(f"LLM返回的指令非JSON格式: {instruction_json_str}, 默认 step_over")

            logger.info(f"LLM 指令: {next_action.split('.')[-1]}")

            if next_action == "Debugger.resume": # Should not happen with current prompt
                logger.info("恢复执行...")
                await session.client.send("Debugger.resume")
                break # Resume ends this kind of step-by-step debugging
            else:
                await session.client.send(next_action)

        logger.info(f"调试会话完成 {debug_step_count} 步。")

    except asyncio.CancelledError:
        logger.info("调试会话被取消。")
        raise
    except Exception as e:
        logger.error(f"调试会话主循环发生错误: {e}", exc_info=True)
        # Try to resume if paused to prevent browser freeze
        try: await session.client.send("Debugger.resume")
        except: pass
    finally:
        session.client.off("Debugger.paused", on_debugger_paused) # Clean up listener
        logger.debug("Debugger.paused 监听器已移除。")

    return {
        "sessionId": session_id,
        "sessionFile": str(session.debug_session_file), # Ensure string for JSON
        "stepCount": debug_step_count,
        "results": debug_results # Might be large, consider summarizing if returning to LLM
    }

# --- AutoGen Tool Functions (Async with Sync Wrappers) ---

async def initialize_browser_async(
    url: Annotated[str, "要访问的URL"],
    headless_ignored: Annotated[bool, "此参数会被忽略，强制使用有头模式进行调试"] = False,
    browser_type: Annotated[str, "浏览器类型，支持chromium、firefox和webkit"] = "chromium",
    cdp_port: Annotated[int, "CDP调试端口"] = 9222, # Common default
    cookies_file: Annotated[Optional[str], "Cookie文件路径，JSON格式"] = None
) -> Dict[str, Any]:
    global _browser_session
    if _browser_session and _browser_session.browser.is_connected():
        logger.warning("浏览器已初始化。如需重置，请先调用 close_browser。")
        # Optionally, navigate to the new URL in existing browser
        try:
            await _browser_session.page.goto(url, timeout=15000)
            return {
                "success": True,
                "message": f"浏览器已存在, 已导航到新URL: {url}",
                "cdp_port": _browser_session.cdp_port
            }
        except Exception as e_goto:
            return {
                "success": False,
                "error": f"浏览器已存在, 但导航到新URL失败: {e_goto}"
            }

    if not PLAYWRIGHT_AVAILABLE:
        return {"success": False, "error": "Playwright模块未找到，请执行: pip install playwright && playwright install"}

    try:
        logger.info(f"初始化浏览器 ({browser_type})，CDP端口: {cdp_port}, 目标URL: {url}")
        pw_instance = await async_playwright().start()

        browser_args = [
            f'--remote-debugging-port={cdp_port}',
            '--no-sandbox', # Often needed in Docker/CI
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-blink-features=AutomationControlled' # Attempt to look less like automation
        ]

        if browser_type.lower() == "firefox":
            browser_instance = await pw_instance.firefox.launch(headless=False, args=browser_args)
        elif browser_type.lower() == "webkit":
            # WebKit has limited CDP support, primarily for Safari Web Inspector.
            # Full JS debugging capabilities might be restricted.
            logger.warning("WebKit的CDP支持可能受限，推荐使用Chromium进行高级调试。")
            browser_instance = await pw_instance.webkit.launch(headless=False, args=browser_args)
        else: # Default to chromium
            browser_instance = await pw_instance.chromium.launch(headless=False, args=browser_args)

        context = await browser_instance.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36" # Example user agent
        )

        cookies_imported_count = 0
        if cookies_file and Path(cookies_file).exists():
            try:
                with open(cookies_file, 'r', encoding='utf-8') as f:
                    cookie_data = json.load(f)

                # 处理不同格式的Cookie文件
                if isinstance(cookie_data, dict) and "cookies" in cookie_data and isinstance(cookie_data["cookies"], list):
                    # Chrome扩展导出的格式：{"url": "...", "cookies": [...]}
                    loaded_cookies = cookie_data["cookies"]
                    logger.info(f"检测到Chrome扩展格式的Cookie文件，包含 {len(loaded_cookies)} 个Cookie")
                elif isinstance(cookie_data, list):
                    # 直接的Cookie数组
                    loaded_cookies = cookie_data
                    logger.info(f"检测到数组格式的Cookie文件，包含 {len(loaded_cookies)} 个Cookie")
                else:
                    logger.warning("Cookie文件格式不正确，应为JSON数组或包含cookies数组的对象")
                    loaded_cookies = []

                # Adapt cookies to Playwright format if necessary (common issue)
                # Playwright expects 'expires' to be Unix timestamp in seconds.
                # Cookie Editor often exports 'expirationDate'.
                adapted_cookies = []
                for c in loaded_cookies:
                    # 确保c是字典
                    if not isinstance(c, dict):
                        logger.warning(f"跳过非字典格式的Cookie: {c}")
                        continue

                    # 处理expirationDate
                    if 'expirationDate' in c and 'expires' not in c:
                        c['expires'] = int(c['expirationDate'])

                    # 处理sameSite值，确保它是Playwright支持的格式（Strict、Lax或None）
                    sameSite = c.get('sameSite', 'Lax')
                    if sameSite not in ['Strict', 'Lax', 'None']:
                        # 将其他值映射到Playwright支持的值
                        if isinstance(sameSite, str):
                            if sameSite.lower() == 'unspecified':
                                sameSite = 'Lax'  # 默认为Lax
                            elif sameSite.lower() == 'no_restriction':
                                sameSite = 'None'
                            else:
                                sameSite = 'Lax'  # 默认为Lax
                        else:
                            sameSite = 'Lax'  # 默认为Lax

                    # Ensure essential fields, provide defaults if missing
                    c_adapted = {
                        'name': c.get('name',''),
                        'value': c.get('value',''),
                        'domain': c.get('domain'),
                        'path': c.get('path', '/'),
                        'expires': c.get('expires', -1), # -1 for session cookie
                        'httpOnly': c.get('httpOnly', False),
                        'secure': c.get('secure', False),
                        'sameSite': sameSite
                    }

                    if not c_adapted['domain']: # Domain is required
                        logger.warning(f"Cookie '{c_adapted['name']}' 缺少domain, 跳过。")
                        continue

                    adapted_cookies.append(c_adapted)

                if adapted_cookies:
                    await context.add_cookies(adapted_cookies)
                    cookies_imported_count = len(adapted_cookies)
                    logger.info(f"成功从 {cookies_file} 导入 {cookies_imported_count} 个Cookie。")
                else:
                    logger.warning(f"没有从 {cookies_file} 导入任何有效的Cookie。")
            except Exception as e_cookie:
                logger.error(f"导入Cookie文件 {cookies_file} 失败: {e_cookie}", exc_info=True)

        page = await context.new_page()
        cdp_session = await context.new_cdp_session(page) # Attach to the page

        await page.goto(url, timeout=30000, wait_until="domcontentloaded") # wait_until can be 'load', 'domcontentloaded', 'networkidle'

        _browser_session = BrowserSession(pw_instance, browser_instance, context, page, cdp_session, cdp_port)

        return {
            "success": True,
            "message": f"浏览器 ({browser_type}) 已初始化并导航到 {url}. CDP端口: {cdp_port}. Cookie导入数量: {cookies_imported_count}.",
            "cdp_port": cdp_port
        }

    except Exception as e:
        logger.error(f"初始化浏览器失败: {e}", exc_info=True)
        if _browser_session: # Attempt cleanup if partially initialized
            await _browser_session.close()
            _browser_session = None
        return {"success": False, "error": str(e)}

def initialize_browser(
    url: Annotated[str, "要访问的URL"],
    headless_ignored: Annotated[bool, "此参数会被忽略，强制使用有头模式进行调试"] = False,
    browser_type: Annotated[str, "浏览器类型，支持chromium、firefox和webkit"] = "chromium",
    cdp_port: Annotated[int, "CDP调试端口"] = 9222,
    cookies_file: Annotated[Optional[str], "Cookie文件路径，JSON格式"] = None
) -> str:
    result = asyncio.run(initialize_browser_async(url, headless_ignored, browser_type, cdp_port, cookies_file))
    return result.get("message") if result.get("success") else f"失败: {result.get('error')}"


async def set_js_breakpoint_async(
    script_url_or_regex: Annotated[str, "JavaScript文件的完整URL或用于匹配URL的正则表达式"],
    line: Annotated[int, "断点行号 (0-based)"],
    column: Annotated[int, "断点列号 (0-based, 可选)"] = 0,
    is_regex: Annotated[bool, "指明script_url_or_regex是否为正则表达式"] = False
) -> Dict[str, Any]:
    if not _browser_session:
        return {"success": False, "error": "浏览器未初始化。"}
    try:
        breakpoint_id = await _set_breakpoint_internal(_browser_session, script_url_or_regex, line, column, is_regex)
        return {
            "success": True,
            "message": f"JS断点已设置 (ID: {breakpoint_id})",
            "breakpoint_id": breakpoint_id
        }
    except Exception as e:
        logger.error(f"设置JS断点失败: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

def set_js_breakpoint(
    script_url_or_regex: Annotated[str, "JavaScript文件的完整URL或用于匹配URL的正则表达式"],
    line: Annotated[int, "断点行号 (0-based)"],
    column: Annotated[int, "断点列号 (0-based, 可选)"] = 0,
    is_regex: Annotated[bool, "指明script_url_or_regex是否为正则表达式"] = False
) -> str:
    result = asyncio.run(set_js_breakpoint_async(script_url_or_regex, line, column, is_regex))
    return result.get("message") if result.get("success") else f"失败: {result.get('error')}"


async def set_xhr_breakpoint_tool_async( # Renamed to avoid conflict with internal
    url_pattern: Annotated[str, "URL模式 (字符串片段或通配符*), 为空则监听所有XHR/Fetch请求"] = "",
    enable_tracing_mode: Annotated[bool, "是否启用XHR追踪模式 (AI将在相关暂停时介入)"] = True
) -> Dict[str, Any]:
    # This tool now mainly signals the `start_debug_session_async` to operate in an XHR-aware mode.
    # The actual "breakpoint" is conceptual; the debugger will look for pauses related to this pattern.
    if not _browser_session:
        return {"success": False, "error": "浏览器未初始化。"}
    try:
        # No specific CDP command for a "tracing XHR breakpoint" like pyppeteer's DOMDebugger.
        # We just enable network monitoring. The start_debug_session will use this url_pattern.
        await _browser_session.client.send("Network.enable")
        message = f"XHR/Fetch监听模式已配置。URL模式: '{url_pattern or '所有请求'}'."
        if enable_tracing_mode:
            message += " AI将在相关网络活动暂停时尝试介入。请在调用 `start_debug_session` 时指明此URL模式。"
            # Store this pattern in session if start_debug_session needs to pick it up automatically
            # For now, it's an argument to start_debug_session.
        return {"success": True, "message": message}
    except Exception as e:
        logger.error(f"配置XHR/Fetch监听模式失败: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

def set_xhr_breakpoint_tool(
    url_pattern: Annotated[str, "URL模式 (字符串片段或通配符*), 为空则监听所有XHR/Fetch请求"] = "",
    enable_tracing_mode: Annotated[bool, "是否启用XHR追踪模式 (AI将在相关暂停时介入)"] = True
) -> str:
    result = asyncio.run(set_xhr_breakpoint_tool_async(url_pattern, enable_tracing_mode))
    return result.get("message") if result.get("success") else f"失败: {result.get('error')}"


async def start_debug_session_async(
    max_steps: Annotated[int, "最大调试步骤数"] = 10,
    timeout_per_step: Annotated[int, "每一步等待断点触发的超时时间 (秒)"] = 20,
    target_xhr_url_pattern: Annotated[Optional[str], "如果为XHR调试模式, 提供要关注的XHR URL片段或模式"] = None
) -> Dict[str, Any]:
    if not _browser_session:
        return {"success": False, "error": "浏览器未初始化。"}
    try:
        result = await _start_debug_session_internal(
            _browser_session, max_steps, timeout_per_step, "default_model", target_xhr_url_pattern
        )
        return {
            "success": True,
            "message": f"调试会话 (ID: {result['sessionId']}) 完成 {result['stepCount']} 步. 日志: {result['sessionFile']}",
            "session_id": result["sessionId"],
            "session_file": result["sessionFile"],
            "step_count": result["stepCount"]
            # "results" field can be very large, so not returning it here by default
        }
    except Exception as e:
        logger.error(f"启动调试会话失败: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

def start_debug_session_tool(
    max_steps: Annotated[int, "最大调试步骤数"] = 10,
    timeout_per_step: Annotated[int, "每一步等待断点触发的超时时间 (秒)"] = 20,
    target_xhr_url_pattern: Annotated[Optional[str], "如果为XHR调试模式, 提供要关注的XHR URL片段或模式"] = None
) -> str:
    result = asyncio.run(start_debug_session_async(max_steps, timeout_per_step, target_xhr_url_pattern))
    return result.get("message") if result.get("success") else f"失败: {result.get('error')}"


async def analyze_debug_session_async(
    session_file: Annotated[str, "调试会话日志文件路径 (通常由start_debug_session返回)"]
) -> Dict[str, Any]:
    session_file_path = Path(session_file)
    if not session_file_path.exists():
        return {"success": False, "error": f"调试会话文件不存在: {session_file}"}

    try:
        with open(session_file_path, "r", encoding="utf-8") as f:
            session_content = f.read()

        if not session_content.strip():
             return {"success": False, "error": f"调试会话文件为空: {session_file}"}

        logger.info(f"开始分析调试会话文件: {session_file}")
        ai_report_content = await get_llm_analysis_report(session_content, "default_model")

        report_file_path = REPORT_DIR / f"{session_file_path.stem}_report.md"
        with open(report_file_path, "w", encoding="utf-8") as f:
            f.write(f"# JavaScript 加密分析报告\n\n")
            f.write(f"## 源日志文件\n`{session_file}`\n\n")
            f.write(f"## 分析结果\n")
            f.write(ai_report_content)

        logger.info(f"分析报告已生成: {report_file_path}")
        return {
            "success": True,
            "message": f"分析报告已生成: {report_file_path}",
            "report_file": str(report_file_path)
        }
    except Exception as e:
        logger.error(f"分析调试会话失败: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

def analyze_debug_session_tool(
    session_file: Annotated[str, "调试会话日志文件路径"]
) -> str:
    result = asyncio.run(analyze_debug_session_async(session_file))
    return result.get("message") if result.get("success") else f"失败: {result.get('error')}"


async def close_browser_async() -> Dict[str, Any]:
    global _browser_session
    if not _browser_session:
        return {"success": True, "message": "浏览器未初始化或已关闭。"}
    try:
        await _browser_session.close()
        _browser_session = None
        logger.info("浏览器已成功关闭。")
        return {"success": True, "message": "浏览器已关闭。"}
    except Exception as e:
        logger.error(f"关闭浏览器失败: {e}", exc_info=True)
        _browser_session = None # Ensure it's cleared even on error
        return {"success": False, "error": str(e)}

def close_browser() -> str:
    result = asyncio.run(close_browser_async())
    return result.get("message") if result.get("success") else f"失败: {result.get('error')}"


# --- 页面交互函数 ---
async def click_element_async(
    selector: Annotated[str, "CSS选择器，用于定位要点击的元素"],
    wait_for_navigation: Annotated[bool, "是否等待页面导航完成"] = False,
    timeout_ms: Annotated[int, "超时时间（毫秒）"] = 5000
) -> Dict[str, Any]:
    """
    点击页面上的元素。

    Args:
        selector: CSS选择器，用于定位要点击的元素
        wait_for_navigation: 是否等待页面导航完成
        timeout_ms: 超时时间（毫秒）

    Returns:
        包含点击结果的字典
    """
    if not _browser_session:
        return {"success": False, "error": "浏览器未初始化。"}

    try:
        # 等待元素可见
        logger.info(f"等待元素可见: {selector}")
        await _browser_session.page.wait_for_selector(selector, state="visible", timeout=timeout_ms)

        # 点击元素
        logger.info(f"点击元素: {selector}")
        if wait_for_navigation:
            async with _browser_session.page.expect_navigation(timeout=timeout_ms):
                await _browser_session.page.click(selector)
        else:
            await _browser_session.page.click(selector)

        return {
            "success": True,
            "message": f"已点击元素: {selector}"
        }
    except Exception as e:
        logger.error(f"点击元素失败: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

def click_element(
    selector: Annotated[str, "CSS选择器，用于定位要点击的元素"],
    wait_for_navigation: Annotated[bool, "是否等待页面导航完成"] = False,
    timeout_ms: Annotated[int, "超时时间（毫秒）"] = 5000
) -> str:
    """
    点击页面上的元素。

    Args:
        selector: CSS选择器，用于定位要点击的元素
        wait_for_navigation: 是否等待页面导航完成
        timeout_ms: 超时时间（毫秒）

    Returns:
        点击结果消息
    """
    result = asyncio.run(click_element_async(selector, wait_for_navigation, timeout_ms))
    return result.get("message") if result.get("success") else f"失败: {result.get('error')}"

async def type_text_async(
    selector: Annotated[str, "CSS选择器，用于定位要输入文本的元素"],
    text: Annotated[str, "要输入的文本"],
    delay_ms: Annotated[int, "每个字符之间的延迟（毫秒）"] = 10,
    timeout_ms: Annotated[int, "超时时间（毫秒）"] = 5000
) -> Dict[str, Any]:
    """
    在页面上的元素中输入文本。

    Args:
        selector: CSS选择器，用于定位要输入文本的元素
        text: 要输入的文本
        delay_ms: 每个字符之间的延迟（毫秒）
        timeout_ms: 超时时间（毫秒）

    Returns:
        包含输入结果的字典
    """
    if not _browser_session:
        return {"success": False, "error": "浏览器未初始化。"}

    try:
        # 等待元素可见
        logger.info(f"等待元素可见: {selector}")
        await _browser_session.page.wait_for_selector(selector, state="visible", timeout=timeout_ms)

        # 清空现有内容
        await _browser_session.page.fill(selector, "")

        # 输入文本
        logger.info(f"输入文本: {text[:30]}...")
        await _browser_session.page.type(selector, text, delay=delay_ms)

        return {
            "success": True,
            "message": f"已在元素 {selector} 中输入文本"
        }
    except Exception as e:
        logger.error(f"输入文本失败: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

def type_text(
    selector: Annotated[str, "CSS选择器，用于定位要输入文本的元素"],
    text: Annotated[str, "要输入的文本"],
    delay_ms: Annotated[int, "每个字符之间的延迟（毫秒）"] = 10,
    timeout_ms: Annotated[int, "超时时间（毫秒）"] = 5000
) -> str:
    """
    在页面上的元素中输入文本。

    Args:
        selector: CSS选择器，用于定位要输入文本的元素
        text: 要输入的文本
        delay_ms: 每个字符之间的延迟（毫秒）
        timeout_ms: 超时时间（毫秒）

    Returns:
        输入结果消息
    """
    result = asyncio.run(type_text_async(selector, text, delay_ms, timeout_ms))
    return result.get("message") if result.get("success") else f"失败: {result.get('error')}"

async def wait_for_element_async(
    selector: Annotated[str, "CSS选择器，用于定位要等待的元素"],
    state: Annotated[str, "要等待的元素状态，可选值：visible、hidden、attached、detached"] = "visible",
    timeout_ms: Annotated[int, "超时时间（毫秒）"] = 30000
) -> Dict[str, Any]:
    """
    等待页面上的元素达到指定状态。

    Args:
        selector: CSS选择器，用于定位要等待的元素
        state: 要等待的元素状态，可选值：visible、hidden、attached、detached
        timeout_ms: 超时时间（毫秒）

    Returns:
        包含等待结果的字典
    """
    if not _browser_session:
        return {"success": False, "error": "浏览器未初始化。"}

    try:
        # 等待元素达到指定状态
        logger.info(f"等待元素 {selector} 达到状态: {state}")
        await _browser_session.page.wait_for_selector(selector, state=state, timeout=timeout_ms)

        return {
            "success": True,
            "message": f"元素 {selector} 已达到状态: {state}"
        }
    except Exception as e:
        logger.error(f"等待元素失败: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

def wait_for_element(
    selector: Annotated[str, "CSS选择器，用于定位要等待的元素"],
    state: Annotated[str, "要等待的元素状态，可选值：visible、hidden、attached、detached"] = "visible",
    timeout_ms: Annotated[int, "超时时间（毫秒）"] = 30000
) -> str:
    """
    等待页面上的元素达到指定状态。

    Args:
        selector: CSS选择器，用于定位要等待的元素
        state: 要等待的元素状态，可选值：visible、hidden、attached、detached
        timeout_ms: 超时时间（毫秒）

    Returns:
        等待结果消息
    """
    result = asyncio.run(wait_for_element_async(selector, state, timeout_ms))
    return result.get("message") if result.get("success") else f"失败: {result.get('error')}"

async def execute_js_async(
    script: Annotated[str, "要执行的JavaScript代码"],
    arg: Annotated[Optional[Any], "传递给脚本的参数"] = None
) -> Dict[str, Any]:
    """
    在页面上执行JavaScript代码。

    Args:
        script: 要执行的JavaScript代码
        arg: 传递给脚本的参数

    Returns:
        包含执行结果的字典
    """
    if not _browser_session:
        return {"success": False, "error": "浏览器未初始化。"}

    try:
        # 执行JavaScript代码
        logger.info(f"执行JavaScript代码: {script[:50]}...")
        result = await _browser_session.page.evaluate(script, arg)

        return {
            "success": True,
            "message": "JavaScript代码执行成功",
            "result": result
        }
    except Exception as e:
        logger.error(f"执行JavaScript代码失败: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

def execute_js(
    script: Annotated[str, "要执行的JavaScript代码"],
    arg: Annotated[Optional[Any], "传递给脚本的参数"] = None
) -> str:
    """
    在页面上执行JavaScript代码。

    Args:
        script: 要执行的JavaScript代码
        arg: 传递给脚本的参数

    Returns:
        执行结果消息
    """
    result = asyncio.run(execute_js_async(script, arg))
    if result.get("success"):
        js_result = result.get("result")
        if js_result is None:
            return "JavaScript代码执行成功，无返回值"
        elif isinstance(js_result, (dict, list)):
            return f"JavaScript代码执行成功，返回值: {json.dumps(js_result, ensure_ascii=False)}"
        else:
            return f"JavaScript代码执行成功，返回值: {js_result}"
    else:
        return f"失败: {result.get('error')}"

# --- AutoGen FunctionTool Definitions ---
cdp_debugger_tools = []
if AUTOGEN_AVAILABLE and PLAYWRIGHT_AVAILABLE:
    tool_initialize_browser = FunctionTool(
        func=initialize_browser, # Use the sync wrapper
        name="initialize_browser",
        description="初始化浏览器并导航到指定URL。支持chromium, firefox, webkit。可加载Cookie文件。"
    )
    tool_set_js_breakpoint = FunctionTool(
        func=set_js_breakpoint,
        name="set_js_breakpoint",
        description="在指定的JavaScript文件URL(或正则)和行号处设置断点。"
    )
    tool_set_xhr_breakpoint = FunctionTool(
        func=set_xhr_breakpoint_tool,
        name="set_xhr_breakpoint",
        description="设置XHR/Fetch请求断点，监听网络请求。"
    )
    tool_start_debug_session = FunctionTool(
        func=start_debug_session_tool,
        name="start_debug_session",
        description="启动JavaScript调试会话，自动分析JavaScript代码。"
    )
    tool_analyze_debug_session = FunctionTool(
        func=analyze_debug_session_tool,
        name="analyze_debug_session",
        description="分析调试会话，识别加密算法和关键参数。"
    )
    tool_close_browser = FunctionTool(
        func=close_browser,
        name="close_browser",
        description="关闭浏览器。"
    )
    # 添加页面交互工具
    tool_click_element = FunctionTool(
        func=click_element,
        name="click_element",
        description="点击页面上的元素。"
    )
    tool_type_text = FunctionTool(
        func=type_text,
        name="type_text",
        description="在页面上的元素中输入文本。"
    )
    tool_wait_for_element = FunctionTool(
        func=wait_for_element,
        name="wait_for_element",
        description="等待页面上的元素达到指定状态。"
    )
    tool_execute_js = FunctionTool(
        func=execute_js,
        name="execute_js",
        description="在页面上执行JavaScript代码。"
    )
    cdp_debugger_tools = [
        tool_initialize_browser,
        tool_set_js_breakpoint,
        tool_set_xhr_breakpoint,
        tool_start_debug_session,
        tool_analyze_debug_session,
        tool_close_browser,
        tool_click_element,
        tool_type_text,
        tool_wait_for_element,
        tool_execute_js
    ]
    logger.info(f"CDP调试器AutoGen工具已创建: {len(cdp_debugger_tools)}个")
else:
    if not AUTOGEN_AVAILABLE:
        logger.warning("AutoGen核心模块未找到，无法创建FunctionTool实例。")
    if not PLAYWRIGHT_AVAILABLE:
        logger.warning("Playwright模块未找到，CDP调试功能不可用。")

__all__ = [
    # Sync tool functions for AutoGen
    "initialize_browser",
    "set_js_breakpoint",
    "set_xhr_breakpoint_tool",
    "start_debug_session_tool",
    "analyze_debug_session_tool",
    "close_browser",
    # 页面交互函数
    "click_element",
    "type_text",
    "wait_for_element",
    "execute_js",
    # Async functions (for direct use if needed)
    "initialize_browser_async",
    "set_js_breakpoint_async",
    "set_xhr_breakpoint_tool_async",
    "start_debug_session_async",
    "analyze_debug_session_async",
    "close_browser_async",
    "click_element_async",
    "type_text_async",
    "wait_for_element_async",
    "execute_js_async",
    # Tool list for AutoGen
    "cdp_debugger_tools"
]

# Example usage (for testing, not part of the module normally)
async def _main_test():
    if not PLAYWRIGHT_AVAILABLE:
        print("Playwright not available, skipping test.")
        return

    test_url = "https://www.example.com" # Replace with a site that has JS
    # test_url = "file:///path/to/your/local/test.html" # For local testing

    init_result = await initialize_browser_async(url=test_url, cdp_port=9223)
    print(f"Initialize result: {init_result}")

    if not init_result.get("success"):
        return

    # Example: Set a JS breakpoint (you'll need a real script URL and line)
    # js_bp_result = await set_js_breakpoint_async(script_url_or_regex="main.js", line=10) # Fictional
    # print(f"Set JS breakpoint result: {js_bp_result}")

    # Example: Configure XHR monitoring
    xhr_config_result = await set_xhr_breakpoint_tool_async(url_pattern="/api/", enable_tracing_mode=True)
    print(f"Configure XHR monitoring result: {xhr_config_result}")

    print("\n请手动在浏览器中执行操作以触发断点或XHR请求...\n")
    # Start debug session
    # If you set a JS breakpoint, interact with the page to hit it.
    # If XHR mode, interact to trigger the XHR.
    debug_session_result = await start_debug_session_async(max_steps=5, target_xhr_url_pattern="/api/")
    print(f"Debug session result: {debug_session_result}")

    if debug_session_result.get("success") and debug_session_result.get("session_file"):
        session_file = debug_session_result["session_file"]
        print(f"\nAnalyzing debug session file: {session_file}")
        analysis_result = await analyze_debug_session_async(session_file=session_file)
        print(f"Analysis result: {analysis_result}")

    close_result = await close_browser_async()
    print(f"Close browser result: {close_result}")

if __name__ == "__main__":
    # This allows running the test directly: python your_script_name.py
    # Ensure you have an event loop running if you call this from a sync context
    # or use asyncio.run()
    # For example, to run from command line:
    # import asyncio
    # asyncio.run(_main_test())
    pass # Keep __main__ clean for module import
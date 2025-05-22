# xuanxue_tool.py
import requests
import os
import json
from typing import Dict, Any, Optional
from typing_extensions import Annotated

# --- 从原始 xuanxue.py 复制过来的核心逻辑 ---
# 从环境变量或直接在此处设置您的 API Token
# 强烈建议从环境变量读取 TOKEN，而不是硬编码
TOKEN = os.environ.get("BROWSERLESS_TOKEN", "SE1vtS5vBiqQ7Y139313afb589cbab4cfb241ca363")
if not TOKEN:
    print("警告: BROWSERLESS_TOKEN 环境变量未设置。将使用脚本中的默认TOKEN。")
    # 如果没有环境变量，并且你想提供一个默认值（不推荐用于生产）
    if TOKEN == "SE1vtS5vBiqQ7Y139313afb589cbab4cfb241ca363": # 检查是否还是占位符
        print("错误: 请设置有效的 browserless.io API Token 作为 BROWSERLESS_TOKEN 环境变量或直接修改脚本。")
        # 在实际工具中，这里应该抛出异常或返回错误，阻止工具在没有有效TOKEN时运行
        # raise ValueError("请设置您的 browserless.io API Token")


BROWSERLESS_FUNCTION_URL = f"https://production-sfo.browserless.io/function?token={TOKEN}"
SCRIPT1_FILENAME = "startliuyao.js"
SCRIPT2_FILENAME = "extractliuyao.js"

# 获取当前脚本所在的目录，以确保能正确找到JS文件
# JS文件位于Browserless文件夹中
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BROWSERLESS_DIR = os.path.join(SCRIPT_DIR, "Browserless")
SCRIPT1_FILE_PATH = os.path.join(BROWSERLESS_DIR, SCRIPT1_FILENAME)
SCRIPT2_FILE_PATH = os.path.join(BROWSERLESS_DIR, SCRIPT2_FILENAME)

def run_two_step_js_on_browserless(
    js_script1_string_literal: str,
    js_script2_string_literal: str,
    initial_target_url: str,
    expected_navigation_url: str,
    log_friendly_script1_call_description: str,
    actual_script1_call_code: str
) -> Dict[str, Any]:
    """
    使用 browserless.io 执行两步 JavaScript 操作：
    1. 在初始URL执行第一个脚本并等待导航。
    2. 在导航后的新URL执行第二个脚本并提取数据。
    """
    # 为了测试，我们暂时允许使用默认TOKEN
    if not TOKEN: # 再次检查Token有效性
        return { "data": { "status": "failure", "pageTitle": None, "details": "Browserless API Token 未配置。", "error": "Configuration Error" } }

    headers = {
        "Content-Type": "application/javascript"
    }

    # 注意：在实际的 FunctionTool 中，文件路径 SCRIPT1_FILE_PATH 和 SCRIPT2_FILE_PATH
    # 需要在 browserless_script 字符串模板中正确引用，或者将JS内容直接注入。
    # 这里我们保持原样，因为JS文件名在JS代码字符串中是作为注释/日志存在的。
    browserless_script = f"""
    export default async function ({{ page }}) {{
      let operationStatus = "failure";
      let errorMessage = null;
      let pageTitle = null;
      let detailsMessage = "Multi-step script execution initiated.";
      let extractedData = null;
      let currentPageURL = "";

      try {{
        // --- Part 1: Initial page and first script ---
        detailsMessage = `Navigating to initial target URL: {initial_target_url}`;
        await page.goto("{initial_target_url}", {{ waitUntil: 'networkidle0', timeout: 60000 }});
        pageTitle = await page.title();
        detailsMessage = `Initial navigation successful. Page title: ${{pageTitle}}`;

        detailsMessage = "Injecting first script content..."; // SCRIPT1_FILE_PATH is a placeholder here for logging
        await page.evaluate({js_script1_string_literal});
        detailsMessage = "First script content injected globally.";

        detailsMessage = `Calling function from first script: {log_friendly_script1_call_description}...`;

        const navigationPromise = page.waitForNavigation({{
            waitUntil: 'networkidle0',
            timeout: 60000,
            url: (navUrl) => navUrl.startsWith("{expected_navigation_url}") // Use startsWith for flexibility with query params
        }});

        await page.evaluate(() => {{
          {actual_script1_call_code}
        }});
        detailsMessage = "Action from first script initiated, awaiting navigation...";

        await navigationPromise;
        pageTitle = await page.title();
        currentPageURL = page.url();
        detailsMessage = `Navigation to results page successful. New page title: ${{pageTitle}}. URL: ${{currentPageURL}}`;

        if (!currentPageURL.startsWith("{expected_navigation_url}")) {{
            console.warn(`Expected navigation to start with {expected_navigation_url} but landed on ${{currentPageURL}}`);
            // Potentially an issue, but proceed with extraction attempt
        }}

        // --- Part 2: Results page and second script ---
        detailsMessage = "Injecting second script content on results page..."; // SCRIPT2_FILE_PATH is a placeholder here
        await page.evaluate({js_script2_string_literal});
        detailsMessage = "Second script content injected globally.";

        detailsMessage = "Calling function from second script to extract data...";
        extractedData = await page.evaluate(() => {{
          if (typeof extractAndFormatYaoData === 'function') {{
            return extractAndFormatYaoData();
          }} else {{
            throw new ReferenceError('extractAndFormatYaoData function is not defined after injecting second script.');
          }}
        }});

        if (extractedData !== null && extractedData !== undefined && Object.keys(extractedData).length > 0) {{
            operationStatus = "success";
            detailsMessage = "Data extraction from results page successful.";
        }} else {{
            operationStatus = "partial_success"; // Or failure depending on strictness
            detailsMessage = "Data extraction script (extractAndFormatYaoData) ran, but returned no data or empty data.";
            errorMessage = "No data or empty data returned by extraction script.";
        }}

      }} catch (e) {{
        console.error("Error during browserless script execution:", e.name, e.message, e.stack);
        errorMessage = e.name + ": " + e.message;
        operationStatus = "failure";
        detailsMessage = "An error occurred during script execution: " + errorMessage;
        try {{
            pageTitle = await page.title();
            currentPageURL = page.url();
        }} catch(_) {{}}
      }}

      return {{
        data: {{
          status: operationStatus,
          pageTitle: pageTitle,
          finalURL: currentPageURL,
          details: detailsMessage,
          extractedHexagramData: extractedData,
          error: errorMessage
        }},
        type: "application/json",
      }};
    }}
    """
    try:
        response = requests.post(BROWSERLESS_FUNCTION_URL, headers=headers, data=browserless_script.encode('utf-8'), timeout=120)
        response.raise_for_status()
        return response.json() # This should be the outer structure, containing a 'data' key
    except requests.exceptions.Timeout:
        return { "data": { "status": "failure", "pageTitle": None, "finalURL": None, "details": "Request to browserless.io timed out.", "error": "Timeout" } }
    except requests.exceptions.SSLError as e:
        return { "data": { "status": "failure", "pageTitle": None, "finalURL": None, "details": f"SSL Error communicating with browserless.io: {str(e)}", "error": str(e) } }
    except requests.exceptions.RequestException as e:
        raw_response_text = None
        status_code = "N/A"
        if hasattr(e, 'response') and e.response is not None:
            raw_response_text = e.response.text
            status_code = e.response.status_code
        return { "data": { "status": "failure", "pageTitle": None, "finalURL": None, "details": f"Error communicating with browserless.io (HTTP {status_code}): {str(e)}", "error": raw_response_text or str(e) } }
    except ValueError as e: # JSONDecodeError inherits from ValueError
        raw_response_text = response.text if 'response' in locals() and hasattr(response, 'text') else 'N/A'
        return { "data": { "status": "failure", "pageTitle": None, "finalURL": None, "details": f"Failed to parse JSON response from browserless.io: {str(e)}", "error": raw_response_text } }

# --- END of xuanxue.py core logic ---


# --- AutoGen FunctionTool Wrapper ---
def perform_liu_yao_divination(
    divination_question: Annotated[str, "请输入占卜的具体问题，例如：'今日财运如何？'或'此项目能否成功？'"],
    divination_number: Annotated[str, "请输入用于起卦的三个数字，通常由用户提供，例如：'688' 或 '123'"],
    custom_time: Annotated[Optional[str], "可选的自定义占卜时间，格式为 'YYYY-MM-DD HH:MM:SS'。如果留空或提供空字符串，则使用当前时间。"] = None
) -> Dict[str, Any]:
    """
    在线进行六爻起卦并返回排盘结果。
    此工具通过调用 browserless.io 服务，在远程浏览器中执行预设的JavaScript脚本与易痴会网站 (pp.yishihui.net) 进行交互。
    它会模拟用户填写起卦表单、提交，然后在结果页面提取生成的卦象数据。
    返回一个包含操作状态、最终页面标题、详情、提取到的卦象数据（如果成功）以及任何错误的字典。
    """
    print(f"准备执行六爻起卦工具...")
    print(f"  占卜问题: {divination_question}")
    print(f"  起卦数字: {divination_number}")
    print(f"  自定义时间: {custom_time if custom_time else '使用当前时间'}")

    # 为了测试，我们暂时允许使用默认TOKEN
    if not TOKEN: # Final check
        error_msg = "Browserless API Token 未配置。请配置有效的 Token。"
        print(f"错误: {error_msg}")
        return {"status": "failure", "error": error_msg, "details": "Tool configuration error."}

    # 1. 检查并加载 JavaScript 文件内容
    print(f"  检查脚本文件路径: {SCRIPT1_FILE_PATH}, {SCRIPT2_FILE_PATH}")
    if not os.path.exists(SCRIPT1_FILE_PATH):
        error_msg = f"错误: 第一个关键JS文件 '{SCRIPT1_FILENAME}' 在路径 '{SCRIPT1_FILE_PATH}' 未找到。请确保该文件位于Browserless文件夹中。"
        print(error_msg)
        return {"status": "failure", "error": error_msg, "details": "Tool dependency missing."}
    if not os.path.exists(SCRIPT2_FILE_PATH):
        error_msg = f"错误: 第二个关键JS文件 '{SCRIPT2_FILENAME}' 在路径 '{SCRIPT2_FILE_PATH}' 未找到。请确保该文件位于Browserless文件夹中。"
        print(error_msg)
        return {"status": "failure", "error": error_msg, "details": "Tool dependency missing."}

    print(f"  正在加载JS脚本内容...")
    try:
        with open(SCRIPT1_FILE_PATH, 'r', encoding='utf-8') as f:
            script1_raw_content = f.read()
        # 将整个JS文件内容作为字符串传递给 page.evaluate()
        # JSON-stringifying the script content ensures it's a valid JS string literal
        script1_for_global_injection = json.dumps(script1_raw_content)

        with open(SCRIPT2_FILE_PATH, 'r', encoding='utf-8') as f:
            script2_raw_content = f.read()
        script2_for_global_injection = json.dumps(script2_raw_content)
        print(f"  JS脚本加载成功。")
    except Exception as e:
        error_msg = f"读取JS脚本文件时出错: {e}"
        print(error_msg)
        return {"status": "failure", "error": error_msg, "details": "Failed to load JS dependencies."}

    # 2. 定义网站和脚本调用参数
    initial_target_url = "https://pp.yishihui.net/"
    # 易痴会的排盘结果URL似乎是固定的，或者至少前缀固定
    expected_navigation_url_prefix = "https://pp.yishihui.net/?action=paipanresult&module=yjhapp"

    # 构造第一个脚本中实际调用的JavaScript代码
    # 注意对输入参数进行JS转义通常是个好主意，但这里 autoFillLiuYaoForm 内部可能已处理或不需要
    # 为简单起见，这里直接嵌入。更安全的方式是确保这些字符串是合法的JS字符串常量。
    escaped_question = json.dumps(divination_question)[1:-1] # Basic escaping for JS string
    escaped_number = json.dumps(divination_number)[1:-1]

    script1_actual_call_code = f'autoFillLiuYaoForm("{escaped_question}", "{escaped_number}"'
    if custom_time and custom_time.strip() != "":
        escaped_custom_time = json.dumps(custom_time.strip())[1:-1]
        script1_actual_call_code += f', "{escaped_custom_time}"'
    script1_actual_call_code += ');'

    script1_log_description = f'autoFillLiuYaoForm with question: "{divination_question}", number: "{divination_number}"'
    if custom_time and custom_time.strip() != "":
        script1_log_description += f', time: "{custom_time.strip()}"'

    print(f"  准备调用 browserless.io 服务...")
    print(f"    初始URL: {initial_target_url}")
    print(f"    预期导航URL前缀: {expected_navigation_url_prefix}")
    print(f"    第一个脚本调用描述: {script1_log_description}")
    print(f"    第一个脚本实际执行: {script1_actual_call_code}")

    # 3. 调用核心 browserless 执行函数
    browserless_result_outer = run_two_step_js_on_browserless(
        js_script1_string_literal=script1_for_global_injection,
        js_script2_string_literal=script2_for_global_injection,
        initial_target_url=initial_target_url,
        expected_navigation_url=expected_navigation_url_prefix, # Pass prefix
        log_friendly_script1_call_description=script1_log_description,
        actual_script1_call_code=script1_actual_call_code
    )

    print(f"  Browserless.io 调用完成。")

    # 4. 处理并返回结果
    # run_two_step_js_on_browserless 已经返回了包含 'data' 键的字典
    if browserless_result_outer and 'data' in browserless_result_outer and isinstance(browserless_result_outer['data'], dict):
        final_result_data = browserless_result_outer['data']
        print(f"  工具执行状态: {final_result_data.get('status')}")
        if final_result_data.get('status') == 'success' or final_result_data.get('status') == 'partial_success':
            # 直接将格式化好的卦象数据作为结果返回给AI使用
            # 不需要额外处理，JS已经格式化好了卦象
            print(f"  提取到的数据 (部分预览): {str(final_result_data.get('extractedHexagramData'))[:200]}...")

            # 如果extractedHexagramData是字符串，直接返回
            if isinstance(final_result_data.get('extractedHexagramData'), str):
                return {
                    "status": "success",
                    "result": final_result_data.get('extractedHexagramData'),
                    "details": final_result_data.get('details', "卦象提取成功")
                }
            # 如果是其他格式，保持原样返回
            else:
                return final_result_data
        elif final_result_data.get('error'):
            print(f"  错误信息: {final_result_data.get('error')}")
        return final_result_data
    else:
        error_msg = "从browserless.io执行返回的原始结果结构无效或缺少'data'字段。"
        print(f"  错误: {error_msg}")
        print(f"  原始返回: {browserless_result_outer}")
        return {
            "status": "failure",
            "error": error_msg,
            "details": "Invalid response structure from core execution function.",
            "raw_result_from_core_function": browserless_result_outer
        }

# --- AutoGen FunctionTool 实例创建 ---
try:
    from autogen_core.tools import FunctionTool

    # 创建一个包装函数，确保直接返回格式化好的卦象字符串给AI
    def liu_yao_divination_wrapper(
        divination_question: Annotated[str, "请输入占卜的具体问题，例如：'今日财运如何？'或'此项目能否成功？'"],
        divination_number: Annotated[str, "请输入用于起卦的三个数字，通常由用户提供，例如：'688' 或 '123'"],
        custom_time: Annotated[Optional[str], "可选的自定义占卜时间，格式为 'YYYY-MM-DD HH:MM:SS'。如果留空或提供空字符串，则使用当前时间。"] = None
    ):
        """包装函数，确保直接返回格式化好的卦象字符串给AI"""
        result = perform_liu_yao_divination(
            divination_question=divination_question,
            divination_number=divination_number,
            custom_time=custom_time
        )

        # 如果有直接的result字段（字符串格式的卦象），直接返回
        if result.get('status') == 'success' and 'result' in result and isinstance(result['result'], str):
            return result['result']

        # 如果有extractedHexagramData字段且为字符串，直接返回
        elif result.get('status') in ['success', 'partial_success'] and 'extractedHexagramData' in result:
            if isinstance(result['extractedHexagramData'], str):
                return result['extractedHexagramData']
            else:
                # 如果是其他格式，尝试转换为字符串
                try:
                    return json.dumps(result['extractedHexagramData'], ensure_ascii=False)
                except:
                    pass

        # 其他情况返回完整结果
        return result

    liu_yao_divination_tool = FunctionTool(
        func=liu_yao_divination_wrapper,  # 使用包装函数
        name="OnlineLiuYaoDivination", # 遵循 OpenAI 命名建议 (字母数字下划线，不超过64字符)
        description="通过在线排盘网站(易痴会)进行六爻起卦，并返回格式化好的卦象详情。需要提供占卜问题和起卦数字。结果直接可用于分析，无需额外处理。"
    )
    print("AutoGen FunctionTool 'OnlineLiuYaoDivination' 创建成功。")

    # 你可以将此工具添加到 Agent 的工具列表中:
    # agent = AssistantAgent("my_agent", tools=[liu_yao_divination_tool, ...])

except ImportError:
    print("警告: 未找到 AutoGen 模块，无法创建 FunctionTool 实例。请确保已安装 autogen-core。")
    liu_yao_divination_tool = None # Or some other placeholder if needed
except Exception as e:
    print(f"创建 FunctionTool 实例时发生错误: {e}")
    liu_yao_divination_tool = None

# --- 导入六爻团队分析工具 ---
try:
    # 从xuanxue包中导入六爻团队分析函数
    from utils.xuanxue import liuyao_team_analysis

    # 创建六爻团队分析工具
    liuyao_team_tool = FunctionTool(
        func=liuyao_team_analysis,
        name="LiuYaoTeamAnalysis",
        description="运行六爻团队分析，让两位六爻专家对给定的卦象进行讨论和分析，得出更全面的结论。"
    )
    print("AutoGen FunctionTool 'LiuYaoTeamAnalysis' 创建成功。")
except ImportError:
    print("警告: 未找到 utils.xuanxue 模块或 AutoGen 模块，无法创建 FunctionTool 实例。")
    liuyao_team_tool = None
except Exception as e:
    print(f"创建 FunctionTool 实例时发生错误: {e}")
    liuyao_team_tool = None


if __name__ == "__main__":
    print("\n=== 测试六爻起卦工具函数 (不通过AutoGen Agent) ===")

    # 检查TOKEN是否有效，如果无效则不进行测试
    # 为了测试，我们暂时允许使用默认TOKEN
    if not TOKEN:
        print("错误: 无效的 Browserless API Token。请设置 BROWSERLESS_TOKEN 环境变量或更新脚本中的 TOKEN。测试中止。")
    elif not os.path.exists(SCRIPT1_FILE_PATH) or not os.path.exists(SCRIPT2_FILE_PATH):
        print(f"错误: 必须的JS脚本文件 ({SCRIPT1_FILENAME} 或 {SCRIPT2_FILENAME}) 未在期望的路径找到。测试中止。")
        print(f"请确保 '{SCRIPT1_FILENAME}' 和 '{SCRIPT2_FILENAME}' 位于Browserless文件夹中。")
        print(f"当前脚本目录: {SCRIPT_DIR}")
        print(f"Browserless文件夹路径: {BROWSERLESS_DIR}")
        print(f"期望的JS文件路径: {SCRIPT1_FILE_PATH}, {SCRIPT2_FILE_PATH}")
    else:
        print("模拟调用 'perform_liu_yao_divination' 函数:")
        test_question = "今日运势如何？"
        test_number = "789"
        # test_custom_time = "2024-05-10 10:30:00"
        test_custom_time = None

        print(f"\n调用参数:")
        print(f"  问题: {test_question}")
        print(f"  数字: {test_number}")
        print(f"  时间: {test_custom_time if test_custom_time else '当前时间'}")

        result = perform_liu_yao_divination(
            divination_question=test_question,
            divination_number=test_number,
            custom_time=test_custom_time
        )

        print("\n--- 工具函数执行结果 ---")
        # 使用 json.dumps 美化输出字典
        print(json.dumps(result, indent=2, ensure_ascii=False))

        if result and result.get('status') == 'success':
            print("\n--- 提取到的卦象数据 ---")
            # 检查result中是否有直接的result字段（我们新添加的格式）
            if 'result' in result and isinstance(result['result'], str):
                # 直接打印格式化好的卦象字符串
                print(result['result'])
            else:
                # 兼容原有格式
                extracted_data = result.get('extractedHexagramData')
                if isinstance(extracted_data, dict): # 假设提取的数据是字典
                    print(json.dumps(extracted_data, indent=2, ensure_ascii=False))
                else: # 如果是字符串或其他
                    print(extracted_data)
        elif result and result.get('status') == 'partial_success':
            print("\n--- 提取操作部分成功 ---")
            print("脚本可能已执行，但未提取到预期数据或数据为空。请检查 'details' 和 'extractedHexagramData'。")
            # 检查result中是否有直接的result字段
            if 'result' in result and result['result']:
                print("提取到的数据:")
                print(result['result'])
            else:
                extracted_data = result.get('extractedHexagramData')
                if extracted_data:
                    print("提取到的数据 (可能不完整或为空):")
                    print(json.dumps(extracted_data, indent=2, ensure_ascii=False) if isinstance(extracted_data, dict) else extracted_data)
        else:
            print("\n--- 执行失败或未提取到数据 ---")
            print(f"状态: {result.get('status')}")
            print(f"错误: {result.get('error')}")
            print(f"详情: {result.get('details')}")

        print("\n=== 测试完成 ===")

        # 测试六爻团队分析工具
        print("\n=== 测试六爻团队分析工具 (不通过AutoGen Agent) ===")
        print("注意: 此测试需要Ollama服务运行，并且有aistudio004-006模型")
        test_team = input("是否测试六爻团队分析工具? (y/n): ")
        if test_team.lower() == 'y':
            # 使用上面生成的卦象数据进行测试
            if 'result' in result and isinstance(result['result'], str):
                test_hexagram_data = result['result']
            elif 'extractedHexagramData' in result and isinstance(result['extractedHexagramData'], str):
                test_hexagram_data = result['extractedHexagramData']
            else:
                # 使用默认卦象数据
                test_hexagram_data = """
占事：aiagents团队帮我起卦决策买基金可以吗
占类：男 - 财运/生意 起卦方式：单数起卦
公历：2025-5-15 13:11 (四月十八 星期四)
节气：立夏05月05日13:57~芒种06月05日17:56
干支：乙巳 辛巳 甲申 辛未 (旬空 午未)
卦身：卯 世身：未
神煞：驿马—寅　 咸池—酉　 贵人—丑未　 　展开
六神　 泽火革(坎宫)
　　 泽山咸(兑宫)
玄武　 官鬼丁未土▅　▅　　　　 官鬼丁未土▅　▅应
白虎　 父母丁酉金▅▅▅　　　　 父母丁酉金▅▅▅
螣蛇　 兄弟丁亥水▅▅▅世　　　 兄弟丁亥水▅▅▅
勾陈　 兄弟己亥水▅▅▅（↑ 伏神：妻财戊午火）　　 父母丙申金▅▅▅世
朱雀　 官鬼己丑土▅　▅　　　　 妻财丙午火▅　▅
青龙　 子孙己卯木▅▅▅应〇　　 官鬼丙辰土▅　▅
"""

            test_topic = input("输入讨论主题 (默认为'分析讨论'): ") or "分析讨论"

            print(f"\n开始六爻团队分析...")
            print(f"  讨论主题: {test_topic}")
            print(f"  使用卦象数据长度: {len(test_hexagram_data)} 字符")

            try:
                # 导入六爻团队分析函数
                from utils.xuanxue import liuyao_team_analysis

                team_result = liuyao_team_analysis(
                    hexagram_data=test_hexagram_data,
                    discussion_topic=test_topic,
                    min_discussion_turns=3,  # 测试时使用较小的值
                    max_total_messages=10    # 测试时使用较小的值
                )

                print("\n--- 六爻团队分析结果 ---")
                print(team_result)
            except ImportError:
                print("错误: 无法导入六爻团队分析模块。请确保utils/xuanxue目录已正确设置。")
            except Exception as e:
                print(f"运行六爻团队分析时出错: {e}")
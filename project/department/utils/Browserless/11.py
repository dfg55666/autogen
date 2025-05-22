import requests
import os
import json # 导入json模块

# 从环境变量或直接在此处设置您的 API Token
TOKEN = "SE1vtS5vBiqQ7Y139313afb589cbab4cfb241ca363" # 使用您提供的Token
if not TOKEN:
    raise ValueError("请设置您的 browserless.io API Token")

BROWSERLESS_FUNCTION_URL = f"https://production-sfo.browserless.io/function?token={TOKEN}"
# Script filenames
SCRIPT1_FILE_PATH = "startliuyao.js"
SCRIPT2_FILE_PATH = "extractliuyao.js" # Corrected filename based on user's upload log

def run_two_step_js_on_browserless(
    js_script1_string_literal,
    js_script2_string_literal,
    initial_target_url,
    expected_navigation_url,
    log_friendly_script1_call_description,
    actual_script1_call_code
):
    """
    使用 browserless.io 执行两步 JavaScript 操作：
    1. 在初始URL执行第一个脚本并等待导航。
    2. 在导航后的新URL执行第二个脚本并提取数据。
    """
    headers = {
        "Content-Type": "application/javascript"
    }

    browserless_script = f"""
    export default async function ({{ page }}) {{
      let operationStatus = "failure";
      let errorMessage = null;
      let pageTitle = null;
      let detailsMessage = "Multi-step script execution initiated.";
      let extractedData = null;

      try {{
        // --- Part 1: Initial page and first script (e.g., startliuyao.js) ---
        detailsMessage = `Navigating to initial target URL: {initial_target_url}`;
        await page.goto("{initial_target_url}", {{ waitUntil: 'networkidle0', timeout: 60000 }});
        pageTitle = await page.title();
        detailsMessage = `Initial navigation successful. Page title: ${{pageTitle}}`;

        detailsMessage = "Injecting first script ({SCRIPT1_FILE_PATH})...";
        await page.evaluate({js_script1_string_literal}); // Defines functions from script1 globally
        detailsMessage = "First script injected globally.";

        detailsMessage = `Calling function from first script: {log_friendly_script1_call_description}...`;

        // Start listening for navigation BEFORE performing the action that triggers it.
        const navigationPromise = page.waitForNavigation({{
            waitUntil: 'networkidle0',
            timeout: 60000,
            url: "{expected_navigation_url}" // Wait for specific URL
        }});

        // Perform the action defined in actual_script1_call_code (e.g., calling autoFillLiuYaoForm)
        await page.evaluate(() => {{
          {actual_script1_call_code}
        }});
        detailsMessage = "Action from first script initiated, awaiting navigation...";

        await navigationPromise; // Wait for the navigation to complete.
        pageTitle = await page.title(); // Get title of the new (result) page.
        detailsMessage = `Navigation to results page successful. New page title: ${{pageTitle}}`;
        const currentPageURL = page.url();
        if (currentPageURL !== "{expected_navigation_url}") {{
            console.warn(`Expected navigation to {expected_navigation_url} but landed on ${{currentPageURL}}`);
            // Continue anyway, but this might indicate an issue.
        }}


        // --- Part 2: Results page and second script (e.g., extractliuyao.js) ---
        detailsMessage = "Injecting second script ({SCRIPT2_FILE_PATH}) on results page...";
        await page.evaluate({js_script2_string_literal}); // Defines functions from script2 globally
        detailsMessage = "Second script injected globally.";

        detailsMessage = "Calling function from second script to extract data...";
        // The function name 'extractAndFormatYaoData' is hardcoded based on extractliuyao.js
        extractedData = await page.evaluate(() => {{
          if (typeof extractAndFormatYaoData === 'function') {{
            return extractAndFormatYaoData();
          }} else {{
            throw new ReferenceError('extractAndFormatYaoData function is not defined on the page after injecting second script.');
          }}
        }});

        if (extractedData !== null && extractedData !== undefined) {{ // Check if data is actually returned
            operationStatus = "success";
            detailsMessage = "Data extraction from results page seems successful.";
        }} else {{
            // If extractAndFormatYaoData returns null/undefined or doesn't return, this branch is taken.
            operationStatus = "failure"; // Or a partial success status
            detailsMessage = "Data extraction script (extractAndFormatYaoData) ran, but returned no data or an issue occurred.";
            errorMessage = "No data explicitly returned by extraction script, or script error prevented return.";
        }}

      }} catch (e) {{
        console.error("Error during browserless script execution:", e.name, e.message, e.stack);
        errorMessage = e.name + ": " + e.message;
        operationStatus = "failure";
        detailsMessage = "An error occurred during script execution: " + errorMessage;
        try {{ pageTitle = await page.title(); }} catch(_) {{}} // Try to get current page title if possible
      }}

      return {{
        data: {{
          status: operationStatus,
          pageTitle: pageTitle,
          details: detailsMessage,
          extractedHexagramData: extractedData,
          error: errorMessage
        }},
        type: "application/json",
      }};
    }}
    """
    try:
        response = requests.post(BROWSERLESS_FUNCTION_URL, headers=headers, data=browserless_script.encode('utf-8'), timeout=120) # Increased timeout for 2 steps
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print("请求 browserless.io 时发生超时错误。")
        return { "data": { "status": "failure", "pageTitle": None, "details": "Request to browserless.io timed out.", "error": "Timeout" } }
    except requests.exceptions.SSLError as e:
        print(f"请求 browserless.io 时发生 SSL 错误: {e}")
        return { "data": { "status": "failure", "pageTitle": None, "details": f"SSL Error communicating with browserless.io: {str(e)}", "error": str(e) } }
    except requests.exceptions.RequestException as e:
        print(f"请求 browserless.io 时发生错误: {e}")
        error_details = f"RequestException: {str(e)}"
        raw_response_text = None
        if hasattr(e, 'response') and e.response is not None:
            print(f"响应状态码: {e.response.status_code}")
            print(f"响应内容: {e.response.text}")
            raw_response_text = e.response.text
        return { "data": { "status": "failure", "pageTitle": None, "details": f"Error communicating with browserless.io: {error_details}", "error": raw_response_text or error_details } }
    except ValueError as e:
        print(f"解析 JSON 响应时发生错误: {e}")
        raw_response_text = response.text if 'response' in locals() and hasattr(response, 'text') else 'N/A'
        print(f"原始响应文本: {raw_response_text}")
        return { "data": { "status": "failure", "pageTitle": None, "details": "Failed to parse JSON response from browserless.io.", "error": raw_response_text } }

if __name__ == "__main__":
    # Check for script1
    if not os.path.exists(SCRIPT1_FILE_PATH):
        print(f"错误: 第一个JS文件 '{SCRIPT1_FILE_PATH}' 未找到。")
        exit()
    # Check for script2
    if not os.path.exists(SCRIPT2_FILE_PATH):
        print(f"错误: 第二个JS文件 '{SCRIPT2_FILE_PATH}' 未找到。")
        exit()

    with open(SCRIPT1_FILE_PATH, 'r', encoding='utf-8') as f:
        script1_raw_content = f.read()
    script1_for_global_injection = json.dumps(script1_raw_content)

    with open(SCRIPT2_FILE_PATH, 'r', encoding='utf-8') as f:
        script2_raw_content = f.read()
    script2_for_global_injection = json.dumps(script2_raw_content)

    INITIAL_TARGET_URL = "https://pp.yishihui.net/"
    EXPECTED_NAVIGATION_URL = "https://pp.yishihui.net/?action=paipanresult&module=yjhapp" # User provided URL

    # Parameters for the first script (startliuyao.js)
    divination_question = "今日整体运势如何"
    divination_number = "688"
    custom_time = "" # Empty for current time

    script1_actual_call_code = f'autoFillLiuYaoForm("{divination_question}", "{divination_number}"'
    if custom_time and custom_time.strip() != "":
        script1_actual_call_code += f', "{custom_time.strip()}"'
    script1_actual_call_code += ');'
    script1_log_description = f'autoFillLiuYaoForm with question and number'

    print(f"准备在 {INITIAL_TARGET_URL} 上执行第一个 JavaScript...")
    print(f"将调用的JS函数 (实际代码): {script1_actual_call_code}")
    print(f"完成后期望导航到: {EXPECTED_NAVIGATION_URL}")
    print(f"然后在目标页面执行第二个脚本 ({SCRIPT2_FILE_PATH}) 中的 extractAndFormatYaoData().")


    result = run_two_step_js_on_browserless(
        script1_for_global_injection,
        script2_for_global_injection,
        INITIAL_TARGET_URL,
        EXPECTED_NAVIGATION_URL,
        script1_log_description,
        script1_actual_call_code
    )

    print("\n--- browserless.io 执行结果 ---")
    if result and 'data' in result and result['data'] is not None:
        data = result['data']
        print(f"总状态: {data.get('status')}")
        if data.get('pageTitle'):
            print(f"最终页面标题: {data.get('pageTitle')}")
        print(f"执行详情: {data.get('details')}")

        if data.get('extractedHexagramData'):
            print("\n--- 提取到的卦象数据 ---")
            print(data.get('extractedHexagramData'))
        elif data.get('status') == 'success':
             print("\n--- 提取到的卦象数据 ---")
             print("提取脚本已执行，但未返回明确数据。")


        if data.get('status') == 'failure' and data.get('error'):
            error_message = data.get('error')
            details_message = data.get('details', "")
            if error_message and str(error_message) not in details_message:
                print(f"错误信息 (原始): {error_message}")
    else:
        print("未能从 browserless.io 获取有效结果或结果格式不正确。")
        if result:
             print("原始结果:", result)
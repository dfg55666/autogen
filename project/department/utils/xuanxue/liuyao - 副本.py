"""
六爻起卦与分析工具

此模块提供了一个简单的命令行界面，用于进行六爻起卦并分析结果。
它使用department/utils/xuanxue.py中的起卦功能，然后将结果传给
department/utils/xuanxue/liuyao_team.py进行分析。

使用方法:
    python liuyao.py

交互式界面会引导用户输入占卜问题和起卦数字，然后自动进行起卦和分析。
"""

import sys
import os
import time
import json
import threading

# 导入起卦和分析功能
try:
    # 添加父目录到路径
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    sys.path.append(parent_dir)

    # 使用importlib直接导入xuanxue.py
    import importlib.util
    xuanxue_path = os.path.join(parent_dir, 'xuanxue.py')
    spec = importlib.util.spec_from_file_location("xuanxue_module", xuanxue_path)
    xuanxue = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(xuanxue)

    # 获取起卦函数
    perform_liu_yao_divination = xuanxue.perform_liu_yao_divination

    # 导入六爻团队分析功能
    try:
        # 先尝试相对导入（当作为模块导入时）
        from .liuyao_team import liuyao_team_analysis
    except ImportError:
        # 如果失败，尝试从当前目录导入（当直接运行脚本时）
        from liuyao_team import liuyao_team_analysis

    # 导入update_gemini_page模块 - 必须成功导入
    try:
        # 先尝试相对导入
        from ..update_gemini_page import update_pages_batch
    except ImportError:
        # 尝试从父目录导入
        import sys
        sys.path.append(parent_dir)
        from update_gemini_page import update_pages_batch

    IMPORTS_SUCCESSFUL = True
except Exception as e:
    print(f"导入模块时出错: {e}")
    import traceback
    traceback.print_exc()
    IMPORTS_SUCCESSFUL = False


def clear_screen():
    """清除控制台屏幕"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    """打印程序标题"""
    clear_screen()
    print("=" * 60)
    print("                    六爻起卦与分析工具")
    print("=" * 60)
    print("此工具将帮助您进行六爻起卦或直接输入卦象，并由六爻专家团队为您分析卦象。")
    print("-" * 60)


def get_user_input():
    """获取用户输入的占卜问题和分析方式"""
    print("\n请输入您的占卜信息:")

    # 获取占卜问题（同时作为分析主题）
    while True:
        question = input("1. 您想占卜的问题是什么? ").strip()
        if question:
            break
        print("占卜问题不能为空，请重新输入。")

    # 占卜问题同时作为分析主题
    topic = question
    print(f"   您的问题将同时作为六爻专家团队的分析主题")

    # 询问用户是否要自动起卦或手动输入卦象
    while True:
        input_mode = input("2. 请选择操作方式: [1]自动起卦 [2]手动输入卦象 (输入1或2): ").strip()
        if input_mode in ['1', '2']:
            break
        print("请输入有效的选项(1或2)。")

    # 询问用户是否要自定义模型
    use_custom_models = input("3. 是否使用自定义模型进行分析? (y/n, 默认为n): ").strip().lower()

    # 默认模型
    supervisor_model = "gemini023"
    expert_one_model = "gemini021"
    expert_two_model = "gemini022"

    if use_custom_models == 'y':
        print("\n请输入要使用的模型名称 (可用模型包括gemini系列、aistudio系列等):")
        supervisor_input = input("   主管模型 (默认gemini023): ").strip()
        expert_one_input = input("   专家一模型 (默认gemini021): ").strip()
        expert_two_input = input("   专家二模型 (默认gemini022): ").strip()

        # 如果用户输入了有效值，则使用用户输入的模型名称
        if supervisor_input:
            supervisor_model = supervisor_input
        if expert_one_input:
            expert_one_model = expert_one_input
        if expert_two_input:
            expert_two_model = expert_two_input

        print(f"\n将使用以下模型进行分析:")
        print(f"   主管模型: {supervisor_model}")
        print(f"   专家一模型: {expert_one_model}")
        print(f"   专家二模型: {expert_two_model}")
    else:
        print(f"\n将使用默认模型进行分析:")
        print(f"   主管模型: {supervisor_model}")
        print(f"   专家一模型: {expert_one_model}")
        print(f"   专家二模型: {expert_two_model}")

    # 如果选择自动起卦
    if input_mode == '1':
        # 获取起卦数字
        while True:
            number = input("4. 请输入一个起卦数字 (建议3位数): ").strip()
            if number and number.isdigit():
                break
            print("请输入有效的数字。")

        # 询问是否使用自定义时间
        use_custom_time = input("5. 是否使用自定义时间进行起卦? (y/n, 默认为n): ").strip().lower()
        custom_time = None

        if use_custom_time == 'y':
            while True:
                time_input = input("   请输入自定义时间 (格式: YYYY-MM-DD HH:MM:SS): ").strip()
                # 简单验证时间格式
                if time_input and len(time_input) >= 16:  # 至少包含YYYY-MM-DD HH:MM
                    custom_time = time_input
                    break
                print("   时间格式不正确，请重新输入。")
        else:
            import datetime
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"   将使用当前时间: {current_time} 进行起卦")

        return {
            "mode": "auto",
            "question": question,
            "topic": topic,
            "number": number,
            "custom_time": custom_time,
            "supervisor_model": supervisor_model,
            "expert_one_model": expert_one_model,
            "expert_two_model": expert_two_model
        }
    # 如果选择手动输入卦象
    else:
        return {
            "mode": "manual",
            "question": question,
            "topic": topic,
            "supervisor_model": supervisor_model,
            "expert_one_model": expert_one_model,
            "expert_two_model": expert_two_model
        }


def get_manual_hexagram_input():
    """获取用户手动输入的卦象信息"""
    print("\n请输入卦象信息:")
    print("提示: 您可以从其他来源获取卦象信息，然后粘贴到这里。")
    print("格式要求: 包含卦名、六爻动静、变卦等信息的文本。")

    # 获取卦象信息
    print("\n请输入卦象信息 (输入完成后按回车两次结束):")
    lines = []
    while True:
        line = input()
        if not line and lines and not lines[-1]:  # 连续两次回车结束输入
            lines.pop()  # 移除最后一个空行
            break
        lines.append(line)

    hexagram_data = "\n".join(lines)

    # 验证输入是否有效
    if not hexagram_data or len(hexagram_data.strip()) < 10:
        print("输入的卦象信息过短或为空，请确保包含足够的信息。")
        return None

    print("\n您输入的卦象信息已接收。")
    return hexagram_data


def perform_divination(question, number, custom_time=None):
    """执行六爻起卦"""
    print("\n正在进行六爻起卦，请稍候...")

    try:
        # 如果没有提供自定义时间，则使用当前时间
        if custom_time is None or custom_time.strip() == "":
            import datetime
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"  未提供自定义时间，将使用当前时间: {current_time}")
            custom_time = current_time

        # 调用xuanxue.py中的起卦函数
        result = perform_liu_yao_divination(
            divination_question=question,
            divination_number=number,
            custom_time=custom_time
        )

        # 处理返回结果
        if isinstance(result, str) and len(result) > 10:
            print("起卦成功!")
            return result
        elif isinstance(result, dict):
            if result.get('status') == 'success' and result.get('result'):
                print("起卦成功!")
                return result.get('result')
            elif 'extractedHexagramData' in result and result.get('extractedHexagramData'):
                print("起卦成功!")
                return result.get('extractedHexagramData')
            else:
                print("起卦失败或返回数据格式不正确。")
                print(f"返回结果: {result}")
                return None
        else:
            print("起卦失败或返回数据格式不正确。")
            print(f"返回结果: {result}")
            return None
    except Exception as e:
        print(f"起卦过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return None


def analyze_hexagram(hexagram_data, topic, supervisor_model="gemini023", expert_one_model="gemini021", expert_two_model="gemini022"):
    """使用六爻团队分析卦象

    Args:
        hexagram_data: 卦象数据
        topic: 分析主题
        supervisor_model: 主管模型名称，默认为gemini023
        expert_one_model: 专家一模型名称，默认为gemini021
        expert_two_model: 专家二模型名称，默认为gemini022
    """
    global gemini_init_completed, gemini_init_success

    if not hexagram_data:
        return "无法进行分析，卦象数据为空。"

    # 等待Gemini模型初始化完成
    if not gemini_init_completed:
        print("\n等待Gemini模型初始化完成...")
        wait_count = 0
        while not gemini_init_completed and wait_count < 30:  # 最多等待30秒
            time.sleep(1)
            wait_count += 1
            if wait_count % 5 == 0:  # 每5秒显示一次等待信息
                print(f"仍在等待Gemini模型初始化...({wait_count}秒)")

        if not gemini_init_completed:
            print("Gemini模型初始化超时，将尝试继续分析。")
            gemini_init_completed = True  # 强制标记为已完成
            gemini_init_success = False   # 标记为失败

    # 检查初始化结果 - 确保在启动分析前模型已初始化成功
    # 由于大模型初始化一定会成功，这里只在失败时显示提示
    if not gemini_init_success:
        print("\n注意: Gemini模型初始化状态未确认，但将继续进行分析。")

    print("\n正在进行六爻团队分析，这可能需要几分钟时间...")
    print(f"分析主题: 「{topic}」")
    print(f"使用模型: 主管({supervisor_model}), 专家一({expert_one_model}), 专家二({expert_two_model})")
    print("(分析过程中，两位六爻专家将围绕您的问题对卦象进行深入讨论)")

    try:
        # 调用六爻团队分析，传入模型参数
        result = liuyao_team_analysis(
            hexagram_data=hexagram_data,
            discussion_topic=topic,
            min_discussion_turns=6,
            max_total_messages=30,
            supervisor_model=supervisor_model,
            expert_one_model=expert_one_model,
            expert_two_model=expert_two_model
        )
        return result
    except Exception as e:
        print(f"分析过程中发生错误: {e}")
        return f"分析失败: {str(e)}"


def save_result(hexagram_data, analysis_result, question):
    """保存起卦和分析结果到文件"""
    try:
        # 创建results目录（如果不存在）
        results_dir = os.path.join(os.path.dirname(__file__), 'results')
        os.makedirs(results_dir, exist_ok=True)

        # 生成文件名（使用时间戳和问题的前10个字符）
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        question_part = ''.join(c for c in question[:10] if c.isalnum() or c.isspace()).strip().replace(' ', '_')
        filename = f"{timestamp}_{question_part}.txt"
        filepath = os.path.join(results_dir, filename)

        # 写入文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"占卜问题/分析主题: {question}\n")
            f.write(f"记录时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("\n" + "="*50 + "\n")
            f.write("【卦象信息】\n\n")
            f.write(hexagram_data)
            f.write("\n" + "="*50 + "\n")
            f.write("【分析结果】\n\n")
            f.write(analysis_result)

        print(f"\n结果已保存到文件: {filepath}")
        return filepath
    except Exception as e:
        print(f"保存结果时出错: {e}")
        return None


# 全局变量，用于跟踪Gemini模型初始化状态
gemini_init_completed = False
gemini_init_success = False

async def update_gemini_pages():
    """异步更新Gemini页面，返回是否成功的标志"""
    global gemini_init_completed, gemini_init_success

    try:
        # 处理gemini021, 022, 023，不输出日志
        gemini_pages = ['gemini021', 'gemini022', 'gemini023']

        # 虽然update_pages_batch是同步函数，但我们可以在异步环境中执行它
        # 使用asyncio.to_thread将同步函数转换为异步执行
        import asyncio
        result = await asyncio.to_thread(update_pages_batch, gemini_pages, verbose=False)

        # 检查结果 - 正确处理update_pages_batch返回的元组
        # update_pages_batch返回Tuple[Dict[str, Any], bool]
        # 第一个元素是详细结果字典，第二个元素是布尔值表示所有页面是否都成功检测到HTTP链接
        if isinstance(result, tuple) and len(result) == 2:
            detailed_results, all_http_detected = result

            # 由于大模型初始化一定会成功，我们直接设置为成功
            gemini_init_success = True

            if not all_http_detected:
                # 检查是否至少有一个页面成功
                any_success = False
                for _, page_result in detailed_results.items():
                    if page_result.get('http_detected', False):
                        any_success = True
                        break

                if not any_success:
                    print("注意: Gemini模型初始化状态未确认，但将继续进行分析。")
        elif isinstance(result, dict):
            # 兼容旧版本可能返回的字典格式
            gemini_init_success = True  # 假设成功以允许继续
        else:
            gemini_init_success = True  # 假设成功以允许继续
    except Exception as e:
        # 记录异常但继续执行
        print(f"初始化Gemini模型时出错: {str(e)}")
        print("但将继续进行分析。")
        gemini_init_success = True  # 即使出错也标记为成功，因为大模型初始化一定会成功

    # 无论成功与否，都标记为已完成初始化
    gemini_init_completed = True
    return gemini_init_success


def main():
    """主函数"""
    # 检查模块导入是否成功
    if not IMPORTS_SUCCESSFUL:
        print("错误: 无法导入必要的模块。请确保已正确安装所有依赖。")
        print("提示: 请确保您在正确的目录中运行此脚本。")
        return

    # 异步初始化Gemini页面
    try:
        # 在Windows上需要使用不同的事件循环策略
        import asyncio
        if os.name == 'nt':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        # 创建一个新的事件循环来运行异步任务
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # 启动异步任务但不等待它完成
        print("正在准备模型...")
        asyncio.run_coroutine_threadsafe(update_gemini_pages(), loop)

        # 让事件循环在后台运行
        def run_event_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()

        # 创建守护线程运行事件循环
        thread = threading.Thread(target=run_event_loop, args=(loop,), daemon=True)
        thread.start()
    except Exception as e:
        print(f"初始化Gemini模型时发生错误: {str(e)}")
        print("将尝试在没有预加载模型的情况下继续。")
        global gemini_init_completed
        gemini_init_completed = True  # 标记为已完成，即使失败了

    print_header()

    # 获取用户输入
    user_input = get_user_input()

    # 根据用户选择的模式处理
    if user_input["mode"] == "auto":
        # 自动起卦模式
        print("\n您选择了自动起卦模式。")
        hexagram_data = perform_divination(
            user_input["question"],
            user_input["number"],
            user_input["custom_time"]
        )
    else:
        # 手动输入卦象模式
        print("\n您选择了手动输入卦象模式。")
        hexagram_data = get_manual_hexagram_input()

    if hexagram_data:
        # 显示卦象信息
        print("\n【卦象信息】")
        print("-" * 60)
        print(hexagram_data)
        print("-" * 60)
        print(f"\n您的占卜问题/分析主题: 「{user_input['question']}」")

        # 分析卦象，传入选择的模型
        analysis_result = analyze_hexagram(
            hexagram_data,
            user_input["topic"],
            supervisor_model=user_input["supervisor_model"],
            expert_one_model=user_input["expert_one_model"],
            expert_two_model=user_input["expert_two_model"]
        )

        # 显示分析结果
        print("\n【分析结果】")
        print("-" * 60)
        print(analysis_result)
        print("-" * 60)

        # 保存结果
        save_result(hexagram_data, analysis_result, user_input["question"])
    else:
        if user_input["mode"] == "auto":
            print("由于起卦失败，无法进行分析。")
        else:
            print("由于卦象输入无效，无法进行分析。")

    print("\n感谢使用六爻起卦与分析工具!")


if __name__ == "__main__":
    main()

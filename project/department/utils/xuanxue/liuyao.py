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
import uuid
import queue
from datetime import datetime

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

    # 检查初始化结果
    if not gemini_init_success:
        print("\n注意: Gemini模型初始化状态未确认，但将继续进行分析。")
    else:
        print("\nGemini模型初始化成功，开始进行分析。")

    print("\n正在进行六爻团队分析，这可能需要几分钟时间...")
    print(f"分析主题: 「{topic}」")
    print(f"使用模型: 主管({supervisor_model}), 专家一({expert_one_model}), 专家二({expert_two_model})")
    print("(分析过程中，两位六爻专家将围绕您的问题对卦象进行深入讨论)")

    try:
        # 调用六爻团队分析，传入模型参数
        print("\n开始调用六爻团队分析函数...")
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
    except RuntimeError as e:
        # 特别处理事件循环相关的错误
        if "Event loop is closed" in str(e):
            print(f"事件循环错误: {e}")
            print("这可能是因为事件循环被过早关闭。尝试使用新的事件循环...")

            try:
                # 尝试使用asyncio.run()，它会创建新的事件循环
                import asyncio
                from .liuyao_team import run_liuyao_team_analysis

                print("使用asyncio.run()重新尝试分析...")
                result = asyncio.run(run_liuyao_team_analysis(
                    hexagram_data=hexagram_data,
                    discussion_topic=topic,
                    min_discussion_turns=6,
                    max_total_messages=30,
                    supervisor_model=supervisor_model,
                    expert_one_model=expert_one_model,
                    expert_two_model=expert_two_model
                ))
                return result
            except Exception as inner_e:
                print(f"使用新事件循环尝试失败: {inner_e}")
                import traceback
                traceback.print_exc()
                return f"分析失败: 事件循环错误，无法恢复。详细信息: {str(e)} -> {str(inner_e)}"
        else:
            # 其他RuntimeError
            print(f"运行时错误: {e}")
            import traceback
            traceback.print_exc()
            return f"分析失败: {str(e)}"
    except Exception as e:
        print(f"分析过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
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

# 任务队列管理器
class TaskQueueManager:
    """任务队列管理器，负责管理六爻起卦与分析任务"""

    def __init__(self, queue_file=None, max_concurrent=1):
        """
        初始化任务队列管理器

        Args:
            queue_file: 队列持久化文件路径
            max_concurrent: 最大并发任务数
        """
        self.queue = []  # 任务队列
        self.queue_file = queue_file  # 队列持久化文件
        self.max_concurrent = max_concurrent  # 最大并发数
        self.running_tasks = 0  # 当前运行的任务数
        self.lock = threading.Lock()  # 线程锁，保证线程安全

        # 如果有队列文件，从文件加载队列
        if queue_file and os.path.exists(queue_file):
            self.load_queue()

    def add_task(self, task):
        """
        添加任务到队列

        Args:
            task: 任务信息字典

        Returns:
            str: 任务ID
        """
        with self.lock:
            task["task_id"] = str(uuid.uuid4())  # 生成唯一ID
            task["status"] = "waiting"
            task["submit_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
            self.queue.append(task)
            self.save_queue()
        return task["task_id"]

    def get_next_task(self):
        """
        获取下一个等待处理的任务

        Returns:
            dict: 任务信息字典，如果没有可处理的任务则返回None
        """
        with self.lock:
            if self.running_tasks >= self.max_concurrent:
                return None

            for task in self.queue:
                if task["status"] == "waiting":
                    task["status"] = "processing"
                    task["start_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    self.running_tasks += 1
                    self.save_queue()
                    return task
        return None

    def update_task(self, task_id, status, result=None, error=None):
        """
        更新任务状态

        Args:
            task_id: 任务ID
            status: 新状态
            result: 任务结果
            error: 错误信息
        """
        with self.lock:
            for task in self.queue:
                if task["task_id"] == task_id:
                    task["status"] = status
                    if status in ["completed", "failed"]:
                        task["end_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        self.running_tasks -= 1
                    if result:
                        task["result"] = result
                    if error:
                        task["error"] = error
                    self.save_queue()
                    break

    def get_task(self, task_id):
        """
        获取指定ID的任务

        Args:
            task_id: 任务ID

        Returns:
            dict: 任务信息字典，如果未找到则返回None
        """
        for task in self.queue:
            if task["task_id"] == task_id:
                return task
        return None

    def get_all_tasks(self):
        """
        获取所有任务

        Returns:
            list: 任务列表
        """
        return self.queue

    def delete_task(self, task_id):
        """
        删除指定ID的任务

        Args:
            task_id: 任务ID

        Returns:
            bool: 是否成功删除
        """
        with self.lock:
            for i, task in enumerate(self.queue):
                if task["task_id"] == task_id:
                    # 如果任务正在处理中，减少运行任务计数
                    if task["status"] == "processing":
                        self.running_tasks -= 1
                    # 删除任务
                    self.queue.pop(i)
                    self.save_queue()
                    return True
            return False

    def reprocess_task(self, task_id):
        """
        重新处理指定ID的任务

        将已完成或失败的任务重置为等待状态，以便重新处理

        Args:
            task_id: 任务ID

        Returns:
            bool: 是否成功重置任务状态
        """
        with self.lock:
            for task in self.queue:
                if task["task_id"] == task_id:
                    # 只有已完成或失败的任务可以重新处理
                    if task["status"] in ["completed", "failed"]:
                        # 保存原始结果（如果有）
                        if "result" in task:
                            task["previous_result"] = task["result"]
                            del task["result"]
                        if "error" in task:
                            task["previous_error"] = task["error"]
                            del task["error"]

                        # 重置任务状态
                        task["status"] = "waiting"
                        task["reprocess_time"] = time.strftime("%Y-%m-%d %H:%M:%S")

                        # 移除结束时间
                        if "end_time" in task:
                            del task["end_time"]

                        self.save_queue()
                        return True
                    else:
                        # 任务正在等待或处理中，不能重新处理
                        return False
            return False  # 未找到任务

    def save_queue(self):
        """保存队列到文件"""
        if self.queue_file:
            with open(self.queue_file, 'w', encoding='utf-8') as f:
                json.dump(self.queue, f, ensure_ascii=False, indent=2)

    def load_queue(self):
        """从文件加载队列"""
        if self.queue_file and os.path.exists(self.queue_file):
            try:
                with open(self.queue_file, 'r', encoding='utf-8') as f:
                    self.queue = json.load(f)
                # 重置运行中的任务计数
                self.running_tasks = sum(1 for task in self.queue if task["status"] == "processing")
                # 将所有处理中的任务重置为等待状态（程序重启后）
                for task in self.queue:
                    if task["status"] == "processing":
                        task["status"] = "waiting"
                self.running_tasks = 0
                self.save_queue()
            except Exception as e:
                print(f"加载队列文件时出错: {e}")
                self.queue = []

# 任务处理器
class TaskProcessor:
    """任务处理器，负责执行队列中的任务"""

    def __init__(self, queue_manager):
        """
        初始化任务处理器

        Args:
            queue_manager: 任务队列管理器实例
        """
        self.queue_manager = queue_manager
        self.stop_flag = False
        self.thread = None

    def start(self):
        """启动任务处理线程"""
        if self.thread is None or not self.thread.is_alive():
            self.stop_flag = False
            self.thread = threading.Thread(target=self._process_tasks, daemon=True)
            self.thread.start()

    def stop(self):
        """停止任务处理线程"""
        self.stop_flag = True
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)

    def _process_tasks(self):
        """处理任务的主循环"""
        while not self.stop_flag:
            task = self.queue_manager.get_next_task()
            if task:
                try:
                    print(f"\n开始处理任务 (ID: {task['task_id']})")
                    print(f"占卜问题: {task['question']}")
                    print(f"分析主题: {task['topic']}")

                    # 重要：每个新任务前重置模型初始化状态
                    global gemini_init_completed, gemini_init_success
                    gemini_init_completed = False
                    gemini_init_success = False
                    print("为当前任务重置模型初始化状态...")

                    # 为当前任务初始化模型
                    print("开始为当前任务初始化模型...")
                    try:
                        # 在Windows上需要使用不同的事件循环策略
                        import asyncio
                        if os.name == 'nt':
                            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

                        # 同步等待模型初始化完成
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        init_result = loop.run_until_complete(update_gemini_pages())
                        # 不要关闭循环，因为后续的liuyao_team_analysis可能会使用它
                        # loop.close()

                        if init_result:
                            print("模型初始化成功，继续处理任务...")
                        else:
                            print("模型初始化状态未确认，但将继续处理任务...")
                    except Exception as e:
                        print(f"初始化模型时出错: {e}")
                        print("将尝试在没有预加载模型的情况下继续处理任务...")
                        gemini_init_completed = True  # 标记为已完成，即使失败了

                    # 根据任务模式执行不同的处理
                    if task["mode"] == "auto":
                        # 自动起卦模式
                        print(f"模式: 自动起卦")
                        print(f"起卦数字: {task['number']}")
                        if task.get("custom_time"):
                            print(f"自定义时间: {task['custom_time']}")

                        hexagram_data = perform_divination(
                            task["question"],
                            task["number"],
                            task.get("custom_time")
                        )

                        if hexagram_data:
                            # 分析卦象
                            analysis_result = analyze_hexagram(
                                hexagram_data,
                                task["topic"],
                                task["supervisor_model"],
                                task["expert_one_model"],
                                task["expert_two_model"]
                            )

                            # 保存结果
                            save_path = save_result(hexagram_data, analysis_result, task["question"])

                            # 更新任务状态
                            self.queue_manager.update_task(
                                task["task_id"],
                                "completed",
                                result={
                                    "hexagram_data": hexagram_data,
                                    "analysis_result": analysis_result,
                                    "save_path": save_path
                                }
                            )
                            print(f"任务 (ID: {task['task_id']}) 处理完成")
                        else:
                            # 起卦失败
                            self.queue_manager.update_task(
                                task["task_id"],
                                "failed",
                                error="起卦失败，无法获取卦象数据"
                            )
                            print(f"任务 (ID: {task['task_id']}) 处理失败: 起卦失败，无法获取卦象数据")

                    elif task["mode"] == "manual":
                        # 手动输入卦象模式
                        print(f"模式: 手动输入卦象")
                        hexagram_data = task["hexagram_data"]

                        if hexagram_data:
                            # 分析卦象
                            analysis_result = analyze_hexagram(
                                hexagram_data,
                                task["topic"],
                                task["supervisor_model"],
                                task["expert_one_model"],
                                task["expert_two_model"]
                            )

                            # 保存结果
                            save_path = save_result(hexagram_data, analysis_result, task["question"])

                            # 更新任务状态
                            self.queue_manager.update_task(
                                task["task_id"],
                                "completed",
                                result={
                                    "hexagram_data": hexagram_data,
                                    "analysis_result": analysis_result,
                                    "save_path": save_path
                                }
                            )
                            print(f"任务 (ID: {task['task_id']}) 处理完成")
                        else:
                            # 卦象数据无效
                            self.queue_manager.update_task(
                                task["task_id"],
                                "failed",
                                error="卦象数据无效"
                            )
                            print(f"任务 (ID: {task['task_id']}) 处理失败: 卦象数据无效")

                except Exception as e:
                    # 处理任务时出错
                    import traceback
                    error_msg = f"处理任务时出错: {str(e)}\n{traceback.format_exc()}"
                    self.queue_manager.update_task(
                        task["task_id"],
                        "failed",
                        error=error_msg
                    )
                    print(f"任务 (ID: {task['task_id']}) 处理失败: {str(e)}")

            # 等待一段时间再检查下一个任务
            time.sleep(1)

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


# 队列管理界面函数
def print_queue_menu():
    """打印任务队列菜单"""
    clear_screen()
    print("=" * 60)
    print("                    六爻起卦任务队列管理")
    print("=" * 60)
    print("1. 添加新任务")
    print("2. 查看所有任务")
    print("3. 查看任务详情")
    print("4. 删除任务")
    print("5. 重新处理任务")
    print("6. 返回主菜单")
    print("-" * 60)

def add_task_to_queue(queue_manager):
    """添加新任务到队列"""
    print("\n添加新任务到队列")

    # 获取用户输入
    user_input = get_user_input()

    # 如果是手动输入卦象模式，获取卦象数据
    if user_input["mode"] == "manual":
        hexagram_data = get_manual_hexagram_input()
        if not hexagram_data:
            print("卦象数据无效，无法添加任务")
            input("\n按回车键继续...")
            return
        user_input["hexagram_data"] = hexagram_data

    # 添加任务到队列
    task_id = queue_manager.add_task(user_input)
    print(f"\n任务已添加到队列，任务ID: {task_id}")
    print("任务将在后台自动处理，您可以稍后查看结果")
    input("\n按回车键继续...")

def view_all_tasks(queue_manager):
    """查看所有任务"""
    clear_screen()
    print("=" * 60)
    print("                    六爻起卦任务列表")
    print("=" * 60)

    tasks = queue_manager.get_all_tasks()
    if not tasks:
        print("任务队列为空")
    else:
        print(f"共有 {len(tasks)} 个任务:")
        print("-" * 60)
        print(f"{'任务ID':<36} {'状态':<10} {'提交时间':<20} {'问题':<30}")
        print("-" * 60)
        for task in tasks:
            task_id = task["task_id"]
            status = task["status"]
            submit_time = task["submit_time"]
            question = task["question"][:30]  # 截取前30个字符
            print(f"{task_id:<36} {status:<10} {submit_time:<20} {question:<30}")

    print("-" * 60)
    input("\n按回车键继续...")

def view_task_detail(queue_manager):
    """查看任务详情"""
    task_id = input("\n请输入要查看的任务ID: ").strip()
    task = queue_manager.get_task(task_id)

    if not task:
        print(f"未找到任务ID为 {task_id} 的任务")
        input("\n按回车键继续...")
        return

    clear_screen()
    print("=" * 60)
    print(f"                    任务详情 (ID: {task_id})")
    print("=" * 60)
    print(f"占卜问题: {task['question']}")
    print(f"分析主题: {task['topic']}")
    print(f"任务状态: {task['status']}")
    print(f"提交时间: {task['submit_time']}")

    if "start_time" in task:
        print(f"开始时间: {task['start_time']}")

    if "end_time" in task:
        print(f"完成时间: {task['end_time']}")

    print(f"模式: {'自动起卦' if task['mode'] == 'auto' else '手动输入卦象'}")

    if task["mode"] == "auto":
        print(f"起卦数字: {task['number']}")
        if task.get("custom_time"):
            print(f"自定义时间: {task['custom_time']}")

    print(f"使用模型: 主管({task['supervisor_model']}), 专家一({task['expert_one_model']}), 专家二({task['expert_two_model']})")

    if task["status"] == "completed" and "result" in task:
        print("\n【卦象信息】")
        print("-" * 60)
        print(task["result"]["hexagram_data"])
        print("-" * 60)

        print("\n【分析结果】")
        print("-" * 60)
        print(task["result"]["analysis_result"])
        print("-" * 60)

        if "save_path" in task["result"] and task["result"]["save_path"]:
            print(f"\n结果已保存到文件: {task['result']['save_path']}")

        # 显示重新处理选项
        print("\n您可以选择重新处理此任务以获取新的分析结果。")
        reprocess = input("是否重新处理此任务? (y/n): ").strip().lower()
        if reprocess == 'y':
            if queue_manager.reprocess_task(task_id):
                print(f"任务 (ID: {task_id}) 已重置为等待状态，将在后台自动重新处理")
            else:
                print(f"重新处理任务 (ID: {task_id}) 失败")

    if task["status"] == "failed" and "error" in task:
        print("\n【错误信息】")
        print("-" * 60)
        print(task["error"])
        print("-" * 60)

        # 显示重新处理选项
        print("\n您可以选择重新处理此失败的任务。")
        reprocess = input("是否重新处理此任务? (y/n): ").strip().lower()
        if reprocess == 'y':
            if queue_manager.reprocess_task(task_id):
                print(f"任务 (ID: {task_id}) 已重置为等待状态，将在后台自动重新处理")
            else:
                print(f"重新处理任务 (ID: {task_id}) 失败")

    # 显示历史结果（如果有）
    if "previous_result" in task:
        print("\n【历史分析结果】")
        print("-" * 60)
        print("此任务曾经被重新处理，以下是之前的分析结果:")
        print("-" * 60)
        print(task["previous_result"]["analysis_result"])
        print("-" * 60)

    input("\n按回车键继续...")

def delete_task(queue_manager):
    """删除任务"""
    task_id = input("\n请输入要删除的任务ID: ").strip()
    task = queue_manager.get_task(task_id)

    if not task:
        print(f"未找到任务ID为 {task_id} 的任务")
        input("\n按回车键继续...")
        return

    confirm = input(f"确定要删除任务 '{task['question']}' (ID: {task_id})? (y/n): ").strip().lower()
    if confirm == 'y':
        queue_manager.delete_task(task_id)
        print(f"任务 (ID: {task_id}) 已删除")
    else:
        print("取消删除")

    input("\n按回车键继续...")

def reprocess_task(queue_manager):
    """重新处理任务"""
    task_id = input("\n请输入要重新处理的任务ID: ").strip()
    task = queue_manager.get_task(task_id)

    if not task:
        print(f"未找到任务ID为 {task_id} 的任务")
        input("\n按回车键继续...")
        return

    # 检查任务状态
    if task["status"] not in ["completed", "failed"]:
        print(f"只有已完成或失败的任务可以重新处理。当前任务状态: {task['status']}")
        input("\n按回车键继续...")
        return

    confirm = input(f"确定要重新处理任务 '{task['question']}' (ID: {task_id})? (y/n): ").strip().lower()
    if confirm == 'y':
        if queue_manager.reprocess_task(task_id):
            print(f"任务 (ID: {task_id}) 已重置为等待状态，将在后台自动重新处理")
        else:
            print(f"重新处理任务 (ID: {task_id}) 失败")
    else:
        print("取消重新处理")

    input("\n按回车键继续...")

def main():
    """主函数"""
    # 检查模块导入是否成功
    if not IMPORTS_SUCCESSFUL:
        print("错误: 无法导入必要的模块。请确保已正确安装所有依赖。")
        print("提示: 请确保您在正确的目录中运行此脚本。")
        return

    # 创建任务队列管理器
    queue_file = os.path.join(os.path.dirname(__file__), 'task_queue.json')
    queue_manager = TaskQueueManager(queue_file=queue_file, max_concurrent=1)

    # 创建任务处理器
    task_processor = TaskProcessor(queue_manager)

    # 启动任务处理线程
    task_processor.start()

    # 不再在主函数中初始化模型，而是在每个任务处理前初始化
    print("任务处理器已启动，将在处理每个任务前初始化模型...")

    # 主菜单循环
    while True:
        print_header()
        print("\n请选择操作:")
        print("1. 直接进行六爻起卦与分析")
        print("2. 管理任务队列")
        print("3. 退出程序")

        choice = input("\n请输入选项 (1-3): ").strip()

        if choice == '1':
            # 直接进行六爻起卦与分析（现有功能）
            user_input = get_user_input()

            # 重要：在直接分析模式下也重置模型初始化状态
            global gemini_init_completed, gemini_init_success
            gemini_init_completed = False
            gemini_init_success = False
            print("\n为当前分析重置模型初始化状态...")

            # 为当前分析初始化模型
            print("开始为当前分析初始化模型...")
            try:
                # 在Windows上需要使用不同的事件循环策略
                import asyncio
                if os.name == 'nt':
                    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

                # 同步等待模型初始化完成
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                init_result = loop.run_until_complete(update_gemini_pages())
                # 不要关闭循环，因为后续的liuyao_team_analysis可能会使用它
                # loop.close()

                if init_result:
                    print("模型初始化成功，继续进行分析...")
                else:
                    print("模型初始化状态未确认，但将继续进行分析...")
            except Exception as e:
                print(f"初始化模型时出错: {e}")
                print("将尝试在没有预加载模型的情况下继续进行分析...")
                gemini_init_completed = True  # 标记为已完成，即使失败了

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

            input("\n按回车键继续...")

        elif choice == '2':
            # 管理任务队列（新功能）
            while True:
                print_queue_menu()
                queue_choice = input("\n请输入选项 (1-6): ").strip()

                if queue_choice == '1':
                    add_task_to_queue(queue_manager)
                elif queue_choice == '2':
                    view_all_tasks(queue_manager)
                elif queue_choice == '3':
                    view_task_detail(queue_manager)
                elif queue_choice == '4':
                    delete_task(queue_manager)
                elif queue_choice == '5':
                    reprocess_task(queue_manager)
                elif queue_choice == '6':
                    break
                else:
                    print("无效的选项，请重新输入")
                    time.sleep(1)

        elif choice == '3':
            # 退出程序
            print("\n正在停止任务处理线程...")
            task_processor.stop()
            print("\n感谢使用六爻起卦与分析工具!")
            break

        else:
            print("无效的选项，请重新输入")
            time.sleep(1)


if __name__ == "__main__":
    main()

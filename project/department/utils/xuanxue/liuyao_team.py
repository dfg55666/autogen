"""
六爻团队模块 - 基于AutoGen 0.5.6的六爻卦象分析团队

本模块提供了一个由两位六爻专家组成的团队，可以对给定的卦象进行深入分析和讨论。
专家们会从不同角度解读卦象，并进行辩论以得出更全面的结论。
讨论结束后，LLM主管会对整个对话进行总结，提供关键见解和结论。

主要功能:
- 接受传入的卦象参数
- 设置由两位六爻专家和一个主管组成的团队
- 运行专家之间的讨论
- 由LLM主管对讨论进行总结
- 返回讨论的摘要结果和主管总结
"""

import asyncio
import os
from typing import Optional

# 尝试导入AutoGen模块
try:
    # 导入AutoGen 0.5.7模块
    from autogen_agentchat.agents import AssistantAgent
    from autogen_agentchat.teams import SelectorGroupChat
    from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
    from autogen_agentchat.base import OrTerminationCondition
    from autogen_ext.models.ollama import OllamaChatCompletionClient
    from autogen_agentchat.messages import TextMessage
    from autogen_core import CancellationToken
    from typing_extensions import Annotated
    AUTOGEN_IMPORTS_SUCCESSFUL = True
except ImportError as e:
    print(f"警告: 无法导入AutoGen模块，六爻团队分析功能将不可用。错误: {e}")
    print("请确保已安装AutoGen 0.5.7及相关依赖。")
    AUTOGEN_IMPORTS_SUCCESSFUL = False

# 导入六爻起卦工具（如果可用）
try:
    # 尝试导入六爻起卦工具
    import sys
    import os

    # 添加父目录到sys.path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)

    # 尝试导入
    try:
        from xuanxue import liu_yao_divination_tool
        HAS_DIVINATION_TOOL = True
    except ImportError:
        HAS_DIVINATION_TOOL = False
except Exception:
    HAS_DIVINATION_TOOL = False

# --- 默认配置信息 ---
SUPERVISOR_MODEL_NAME = "gemini023"  # Supervisor LLM
DEFAULT_LIUYAO_EXPERT_ONE_MODEL_NAME = "gemini021"
DEFAULT_LIUYAO_EXPERT_TWO_MODEL_NAME = "gemini022"
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_DISCUSSION_TOPIC = "分析讨论"

# 终止信号Agent发出的特定短语，以及它的名字
TERMINATOR_AGENT_NAME = "Discussion_Summary_Terminator_Agent"
TERMINATION_PHRASE_FROM_TERMINATOR = "ACTION_CONCLUDE_DISCUSSION_NOW"

DEFAULT_MIN_DISCUSSION_TURNS = 6  # 主管在至少这么多轮Agent有效发言后才能考虑结束
DEFAULT_MAX_TOTAL_MESSAGES = 30  # 总消息上限，防止无限循环

# --- 定义模型信息 ---
model_info_for_ollama = {
    "context_length": 1048576,
    "structured_output": True,
    "vision": False,
    "function_calling": True,
    "json_output": True,
    "family": "custom_ollama_models"
}


def create_ollama_client(model_name: str, model_info: dict) -> OllamaChatCompletionClient:
    return OllamaChatCompletionClient(
        model=model_name,
        base_url=OLLAMA_BASE_URL,
        model_info=model_info,
        keep_alive=True,  # 保持会话活跃，让Ollama维护历史
        config={
            "num_ctx": 1048576,  # 上下文窗口大小设置为最大值
            "num_keep": 1048576,  # 服务器端保留尽可能多的上下文（实际上相当于无限）
        }
    )


# 不再需要自定义的TerminationSignalAgent类，将使用标准的AssistantAgent


async def run_liuyao_team_analysis(
    hexagram_data: str,
    discussion_topic: str = DEFAULT_DISCUSSION_TOPIC,
    min_discussion_turns: int = DEFAULT_MIN_DISCUSSION_TURNS,
    max_total_messages: int = DEFAULT_MAX_TOTAL_MESSAGES,
    supervisor_model: str = SUPERVISOR_MODEL_NAME,
    expert_one_model: str = DEFAULT_LIUYAO_EXPERT_ONE_MODEL_NAME,
    expert_two_model: str = DEFAULT_LIUYAO_EXPERT_TWO_MODEL_NAME
) -> str:
    """
    运行六爻团队分析，让两位六爻专家对给定的卦象进行讨论和分析。

    此函数创建一个由两位六爻专家组成的团队，在主管的协调下对卦象进行深入分析和讨论。
    专家们会从不同角度解读卦象，并进行辩论以得出更全面的结论。
    讨论结束后，终止Agent会使用主管模型对整个对话进行总结，提供关键见解和结论。

    Args:
        hexagram_data: 六爻卦象数据，包含完整的卦象信息
        discussion_topic: 讨论主题，默认为"分析讨论"
        min_discussion_turns: 最少讨论轮数，默认为6轮
        max_total_messages: 最大消息数量，默认为30条
        supervisor_model: 主管模型名称，默认为gemini023
        expert_one_model: 专家一模型名称，默认为gemini021
        expert_two_model: 专家二模型名称，默认为gemini022

    Returns:
        包含专家讨论摘要和主管总结的结果
    """
    # --- 配置信息 ---
    SUPERVISOR_MODEL_NAME = supervisor_model
    DEFAULT_LIUYAO_EXPERT_ONE_MODEL_NAME = expert_one_model
    DEFAULT_LIUYAO_EXPERT_TWO_MODEL_NAME = expert_two_model
    DISCUSSION_TOPIC = discussion_topic
    LIUYAO_INFO = hexagram_data

    MIN_DISCUSSION_TURNS_BEFORE_TERMINATION = min_discussion_turns
    MAX_TOTAL_MESSAGES = max_total_messages

    # --- 创建Ollama客户端 ---
    try:
        supervisor_llm_client = create_ollama_client(SUPERVISOR_MODEL_NAME, model_info_for_ollama)
        first_liuyao_expert_client = create_ollama_client(DEFAULT_LIUYAO_EXPERT_ONE_MODEL_NAME, model_info_for_ollama)
        second_liuyao_expert_client = create_ollama_client(DEFAULT_LIUYAO_EXPERT_TWO_MODEL_NAME, model_info_for_ollama)
    except Exception as e:
        return f"初始化Ollama客户端时出错: {e}"

    # --- System message template for Liuyao Experts ---
    liuyao_expert_system_message_template = """
你是一位资深的六爻占卜专家，名为"{expert_name}"。
你将与其他六爻专家一起，共同分析以下提供的六爻卦象信息，研讨的主题是："{discussion_topic}"。

目前的卦象信息如下：
--- 卦象开始 ---
{liuyao_data}
--- 卦象结束 ---

你的核心任务是：
1.  请你根据提供的六爻卦象，仔细观察世爻、应爻以及其他爻的状态，分析它们之间的生克冲合关系。
2.  结合卦中的动爻、变爻，以及太岁、月建、日辰对各爻的影响。
3.  请考虑十二长生在分析中的应用，判断爻的旺衰。
4.  讨论此卦对于 "{discussion_topic}" 这一事项的吉凶、发展趋势、注意事项等。
5.  请详细说明你的推断依据，引用卦爻信息（如某爻发动、某爻逢空、某爻受日月生扶克制等）来支持你的观点。

【重要】辩论与交流指南：
6.  你必须与其他专家进行深入辩论，不要轻易认同对方的观点。积极寻找不同的解读角度，提出质疑和反对意见。
7.  当其他专家发表观点时，请仔细分析其论点中的薄弱环节，指出其可能忽略的卦象细节或解读偏差。
8.  提出你自己独特的解读视角，即使这与传统解读或其他专家的观点相左。六爻预测本就存在多种解读可能。
9.  当你认为对方的解读有误时，明确指出问题所在，并提供你认为更合理的解释，引用卦象中的具体证据。
10. 辩论应当聚焦于卦象解读的专业性，而非简单的个人观点对立。每次发言都应当有理有据。
11. 在辩论过程中保持专业尊重，但不要回避分歧，真理越辩越明。

请充分阐述你的观点，直到项目经理（主管）指示讨论结束。
请使用中文进行分析和回复。
"""

    # --- 定义参与的Agent ---
    tools = [liu_yao_divination_tool] if HAS_DIVINATION_TOOL else []

    liuyao_expert_one_agent = AssistantAgent(
        name="Liuyao_Expert_One",
        model_client=first_liuyao_expert_client,
        system_message=liuyao_expert_system_message_template.format(
            expert_name="易玄子",
            discussion_topic=DISCUSSION_TOPIC,
            liuyao_data=LIUYAO_INFO
        ),
        description="六爻专家一（易玄子），负责从整体格局和关键爻入手分析卦象。",
        tools=tools,
    )
    liuyao_expert_one_agent.description_for_llm = "易玄子 (Liuyao_Expert_One): 六爻专家，侧重于卦的整体解读、世应关系及动变影响。"

    liuyao_expert_two_agent = AssistantAgent(
        name="Liuyao_Expert_Two",
        model_client=second_liuyao_expert_client,
        system_message=liuyao_expert_system_message_template.format(
            expert_name="道源真人",
            discussion_topic=DISCUSSION_TOPIC,
            liuyao_data=LIUYAO_INFO
        ),
        description="六爻专家二（道源真人），负责深入分析日月组合、神煞及细节对卦象的影响。",
        tools=tools,
    )
    liuyao_expert_two_agent.description_for_llm = "道源真人 (Liuyao_Expert_Two): 六爻专家，侧重于日月组合、神煞、空亡、十二长生等细节对卦象的具体影响。"

    # 创建终止信号Agent实例（同时负责总结）
    # 准备终止Agent的系统消息
    terminator_system_message = f"""
你是一位六爻占卜讨论的主管总结专家，负责对专家讨论进行全面、客观的总结，并发出讨论结束信号。

你的任务是：
1. 仔细阅读两位六爻专家（易玄子和道源真人）的讨论内容
2. 提取讨论中的关键观点、分析和结论
3. 识别专家们达成共识的部分和存在分歧的部分
4. 综合不同观点，形成全面的总结
5. 提供对卦象关键信息的简明解读
6. 总结卦象对"{DISCUSSION_TOPIC}"这一主题的指导意义

卦象信息：
{LIUYAO_INFO}

请以中文撰写一个结构清晰、内容全面的总结，帮助咨询者理解六爻专家的分析结果。
在总结的最后，请添加"结论"部分，简明扼要地给出最终建议。

【重要】在你的回复最后，必须添加这个特定的结束标识："{TERMINATION_PHRASE_FROM_TERMINATOR}"
这个标识将告诉系统讨论已经结束。请确保它出现在你回复的最后一行。
"""

    # 使用AssistantAgent创建终止Agent
    terminator_agent = AssistantAgent(
        name=TERMINATOR_AGENT_NAME,
        model_client=supervisor_llm_client,
        system_message=terminator_system_message,
        description="六爻讨论总结专家，负责对专家讨论进行全面总结，提供关键见解和结论，然后发出结束信号。"
    )
    # 设置description_for_llm属性，用于在选择器提示中显示
    terminator_agent.description_for_llm = f"{TERMINATOR_AGENT_NAME}: 当项目经理（主管）决定结束讨论时会选择我，我会使用主管的模型对专家讨论进行全面总结，提供关键见解和结论，然后发出结束信号。"

    participants = [liuyao_expert_one_agent, liuyao_expert_two_agent, terminator_agent]

    # --- 为主管（Selector）定义选择器提示 ---
    participant_descriptions_for_prompt_list = []
    for agent in participants:
        desc = agent.description_for_llm if hasattr(agent, 'description_for_llm') else agent.description
        participant_descriptions_for_prompt_list.append(f"- {agent.name} ({desc})")
    participant_descriptions_for_prompt = "\n".join(participant_descriptions_for_prompt_list)

    selector_prompt = (
        f"你是一位六爻占卜讨论的项目经理，负责协调专家之间的讨论，确保讨论深入且全面。\n\n"
        f"参与者:\n{participant_descriptions_for_prompt}\n\n"
        f"你的任务是选择下一位发言者。每次只能选择一位参与者。\n\n"
        f"讨论主题: {DISCUSSION_TOPIC}\n\n"
        f"选择规则:\n"
        f"1. 在讨论初期，应该让两位专家轮流发言，确保他们都有机会表达自己的观点。\n"
        f"2. 当讨论进行到至少 {MIN_DISCUSSION_TURNS_BEFORE_TERMINATION} 轮有效专家发言后，如果你认为讨论已经充分且全面，可以选择 '{TERMINATOR_AGENT_NAME}' 来总结讨论并结束对话。该Agent会使用你的模型对专家讨论进行全面总结，提供关键见解和结论。\n"
        f"3. 如果讨论不够深入或专家间存在明显分歧，应继续让专家发言，直到达成更一致的结论。\n"
        f"4. 优先选择能够对前一位专家的观点提出质疑或补充的专家，以促进辩论深度。\n\n"
        f"在未达到最少轮数或辩论不充分时，请继续选择 'Liuyao_Expert_One' 或 'Liuyao_Expert_Two' 发言，引导他们深入质疑对方的观点并提出不同的解读角度。\n\n"
        "请仔细阅读以下的对话历史（注意专家发言的次数和讨论的深度，以判断是否达到最少交流轮数并决定何时结束）：\n"
        "--- 对话历史开始 ---\n"
        "{history}"
        "\n--- 对话历史结束 ---\n\n"
        f"你的任务是根据当前的对话进展、专家角色、讨论的充分性（尤其是在满足最少 {MIN_DISCUSSION_TURNS_BEFORE_TERMINATION} 轮有效专家发言后），来决定下一位最适合的发言者。\n"
        f"你的回答必须且只能是其中一位参与者的英文名称 (例如 'Liuyao_Expert_One', 'Liuyao_Expert_Two', 或 '{TERMINATOR_AGENT_NAME}')。"
    )

    # --- 创建并组合终止条件 ---
    supervisor_decided_termination = TextMentionTermination(
        text=TERMINATION_PHRASE_FROM_TERMINATOR,
        sources=[TERMINATOR_AGENT_NAME]
    )
    max_messages_fallback_termination = MaxMessageTermination(max_messages=MAX_TOTAL_MESSAGES)
    combined_termination_condition = OrTerminationCondition(supervisor_decided_termination, max_messages_fallback_termination)

    # --- 创建SelectorGroupChat ---
    team = SelectorGroupChat(
        participants=participants,
        model_client=supervisor_llm_client,
        selector_prompt=selector_prompt,
        termination_condition=combined_termination_condition,
        allow_repeated_speaker=False,
        model_client_streaming=False
    )

    # --- 准备初始消息 ---
    initial_message_content = (
        f"请两位六爻专家根据以下卦象信息，就主题「{DISCUSSION_TOPIC}」进行深入分析和讨论。\n\n"
        "请注意：\n"
        "1. 分析时要引用卦象中的具体信息作为依据\n"
        "2. 要从不同角度解读卦象，不要轻易认同对方观点\n"
        "3. 当发现对方解读有误或片面时，要明确指出并提供更合理的解释\n"
        "4. 讨论应当聚焦于卦象的专业解读，而非简单的个人观点对立\n\n"
        f"卦象信息：\n{LIUYAO_INFO}\n\n"
        "请开始讨论。"
    )

    initial_task_message = TextMessage(source="Project_Manager_Bot", content=initial_message_content)

    # --- 运行群聊 ---
    task_result = await team.run(task=[initial_task_message], cancellation_token=CancellationToken())

    # --- 处理结果 ---
    result_summary = "六爻专家讨论结果摘要：\n\n"

    if task_result and task_result.messages:
        # 计算实际专家发言次数
        actual_expert_turns = 0
        for msg in task_result.messages:
            if msg.source in [liuyao_expert_one_agent.name, liuyao_expert_two_agent.name]:
                actual_expert_turns += 1

        # 添加专家发言摘要
        for i, msg in enumerate(task_result.messages):
            if hasattr(msg, 'content'):
                role_name_map = {
                    liuyao_expert_one_agent.name: "易玄子",
                    liuyao_expert_two_agent.name: "道源真人",
                    terminator_agent.name: "终止信号Agent",
                    "Project_Manager_Bot": "项目经理机器人"
                }
                display_source = role_name_map.get(msg.source, msg.source)

                # 跳过初始消息
                if msg.source == "Project_Manager_Bot":
                    continue

                # 处理终止Agent的消息（包含总结）
                if msg.source == terminator_agent.name:
                    # 提取总结内容（去掉终止短语）
                    content = msg.content
                    if TERMINATION_PHRASE_FROM_TERMINATOR in content:
                        # 保留总结部分，去掉终止短语
                        content = content.replace(TERMINATION_PHRASE_FROM_TERMINATOR, "").strip()
                    result_summary += f"【总结】:\n{content}\n\n"
                    continue

                # 添加专家发言
                result_summary += f"【{display_source}】: {msg.content}\n\n"

        result_summary += f"专家发言轮数: {actual_expert_turns}\n"
    else:
        result_summary += "讨论未能正常进行或没有消息交换。"

    # 关闭Ollama客户端
    await supervisor_llm_client.close()
    await first_liuyao_expert_client.close()
    await second_liuyao_expert_client.close()

    return result_summary


def liuyao_team_analysis(
    hexagram_data: str,
    discussion_topic: str = DEFAULT_DISCUSSION_TOPIC,
    min_discussion_turns: int = DEFAULT_MIN_DISCUSSION_TURNS,
    max_total_messages: int = DEFAULT_MAX_TOTAL_MESSAGES,
    supervisor_model: str = SUPERVISOR_MODEL_NAME,
    expert_one_model: str = DEFAULT_LIUYAO_EXPERT_ONE_MODEL_NAME,
    expert_two_model: str = DEFAULT_LIUYAO_EXPERT_TWO_MODEL_NAME
) -> str:
    """
    运行六爻团队分析，让两位六爻专家对给定的卦象进行讨论和分析。

    此工具创建一个由两位六爻专家组成的团队，在主管的协调下对卦象进行深入分析和讨论。
    专家们会从不同角度解读卦象，并进行辩论以得出更全面的结论。
    讨论结束后，终止Agent会使用主管模型对整个对话进行总结，提供关键见解和结论。

    Args:
        hexagram_data: 六爻卦象数据，包含完整的卦象信息
        discussion_topic: 讨论主题，默认为"分析讨论"
        min_discussion_turns: 最少讨论轮数，默认为6轮
        max_total_messages: 最大消息数量，默认为30条
        supervisor_model: 主管模型名称，默认为gemini023
        expert_one_model: 专家一模型名称，默认为gemini021
        expert_two_model: 专家二模型名称，默认为gemini022

    Returns:
        包含专家讨论摘要和主管总结的结果
    """
    # 检查AutoGen模块是否成功导入
    if not globals().get('AUTOGEN_IMPORTS_SUCCESSFUL', False):
        return "错误: 无法导入AutoGen模块，六爻团队分析功能不可用。请确保已安装AutoGen 0.5.6及相关依赖。"

    # 使用asyncio运行异步函数
    try:
        # 尝试获取当前事件循环
        try:
            loop = asyncio.get_event_loop()
            # 检查循环是否已关闭
            if loop.is_closed():
                print("当前事件循环已关闭，创建新的事件循环...")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            # 如果没有当前事件循环，创建一个新的
            print("没有当前事件循环，创建新的事件循环...")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        print(f"使用事件循环: {id(loop)} 运行六爻团队分析...")

        # 尝试在当前事件循环上运行
        result = loop.run_until_complete(
            run_liuyao_team_analysis(
                hexagram_data=hexagram_data,
                discussion_topic=discussion_topic,
                min_discussion_turns=min_discussion_turns,
                max_total_messages=max_total_messages,
                supervisor_model=supervisor_model,
                expert_one_model=expert_one_model,
                expert_two_model=expert_two_model
            )
        )
    except RuntimeError as e:
        # 如果事件循环已经在运行，使用ThreadPoolExecutor运行在新线程中
        if "This event loop is already running" in str(e):
            # 创建一个Future来存储结果
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    lambda: asyncio.run(
                        run_liuyao_team_analysis(
                            hexagram_data=hexagram_data,
                            discussion_topic=discussion_topic,
                            min_discussion_turns=min_discussion_turns,
                            max_total_messages=max_total_messages,
                            supervisor_model=supervisor_model,
                            expert_one_model=expert_one_model,
                            expert_two_model=expert_two_model
                        )
                    )
                )
                result = future.result()
        else:
            # 其他RuntimeError
            result = f"运行六爻团队分析时出错: {str(e)}"
    except Exception as e:
        # 处理其他异常
        result = f"运行六爻团队分析时出错: {str(e)}"

    return result


# 模块只能被导入使用，不支持直接运行
if __name__ == "__main__":
    print("错误: liuyao_team.py 只能作为模块导入使用，不支持直接运行。")
    print("请在您的代码中导入并使用 liuyao_team_analysis 函数。")
    print("示例:")
    print("  from utils.xuanxue.liuyao_team import liuyao_team_analysis")
    print("  result = liuyao_team_analysis(hexagram_data='卦象数据', discussion_topic='分析主题')")
    print("  print(result)")
# -*- coding: utf-8 -*-
"""
塔罗团队模块 - 基于AutoGen的塔罗牌阵分析团队

本模块提供了一个由两位塔罗专家组成的团队，可以对给定的牌阵进行深入分析和讨论。
专家们会从不同角度解读牌阵，并进行辩论以得出更全面的结论。
讨论结束后，LLM主管会对整个对话进行总结，提供关键见解和结论。

主要功能:
- 接受传入的塔罗牌阵参数
- 设置由两位塔罗专家和一个主管组成的团队
- 运行专家之间的讨论
- 由LLM主管对讨论进行总结
- 返回讨论的摘要结果和主管总结
"""

import asyncio
import os
from typing import Sequence, Optional

from autogen_agentchat.agents import AssistantAgent, BaseChatAgent
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.base import OrTerminationCondition, Response
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_agentchat.messages import TextMessage, BaseChatMessage
from autogen_core import CancellationToken
from typing_extensions import Annotated

# 导入塔罗解读工具（如果可用）
try:
    # 尝试导入塔罗解读工具
    import sys
    import os

    # 添加父目录到sys.path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)

    # 尝试导入
    try:
        from xuanxue import tarot_reading_tool # 修改：导入塔罗工具
        HAS_READING_TOOL = True
    except ImportError:
        HAS_READING_TOOL = False
except Exception:
    HAS_READING_TOOL = False

# --- 默认配置信息 ---
SUPERVISOR_MODEL_NAME = "aistudio010"  # Supervisor LLM
DEFAULT_TAROT_EXPERT_ONE_MODEL_NAME = "aistudio008" # 修改：塔罗专家模型
DEFAULT_TAROT_EXPERT_TWO_MODEL_NAME = "aistudio009" # 修改：塔罗专家模型
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_DISCUSSION_TOPIC = "分析讨论" # 默认为“分析讨论”，可根据实际情况修改为更具体的塔罗解读主题

# 终止信号Agent发出的特定短语，以及它的名字
TERMINATOR_AGENT_NAME = "Discussion_Summary_Terminator_Agent"
TERMINATION_PHRASE_FROM_TERMINATOR = "ACTION_CONCLUDE_DISCUSSION_NOW"

DEFAULT_MIN_DISCUSSION_TURNS = 6  # 主管在至少这么多轮Agent有效发言后才能考虑结束
DEFAULT_MAX_TOTAL_MESSAGES = 30  # 总消息上限，防止无限循环

# --- 定义模型信息 ---
model_info_for_ollama = {
    "context_length": 1048576,
    "structured_output": True,
    "vision": False, # 假设当前模型不直接处理图像，牌面信息以文本描述传入
    "function_calling": True,
    "json_output": True,
    "family": "custom_ollama_models"
}


def create_ollama_client(model_name: str, model_info: dict) -> OllamaChatCompletionClient:
    return OllamaChatCompletionClient(
        model=model_name,
        base_url=OLLAMA_BASE_URL,
        model_info=model_info,
    )


# --- 定义总结和终止信号Agent ---
class TerminationSignalAgent(BaseChatAgent):
    def __init__(self, name: str = TERMINATOR_AGENT_NAME,
                 termination_phrase: str = TERMINATION_PHRASE_FROM_TERMINATOR,
                 description: Optional[str] = None,
                 tarot_spread_data: str = "", # 修改：塔罗牌阵数据
                 discussion_topic: str = DEFAULT_DISCUSSION_TOPIC):
        super().__init__(
            name=name,
            description=description or "一个用于总结讨论并发出结束信号的特殊Agent。"
        )
        self.termination_phrase = termination_phrase
        self.tarot_spread_data = tarot_spread_data # 修改
        self.discussion_topic = discussion_topic
        self.description_for_llm = f"{name}: 当项目经理（主管）决定结束讨论时会选择我，我会使用主管的模型对专家讨论进行全面总结，提供关键见解和结论，然后发出结束信号。"
        self.model_client = None  # 将在外部设置

    async def on_messages(self, messages: Sequence[BaseChatMessage], cancellation_token: Optional[CancellationToken] = None) -> Response:
        # 提取专家讨论内容
        expert_messages = []
        expert_names = ["Tarot_Expert_One", "Tarot_Expert_Two"] # 修改：塔罗专家名称

        for msg in messages:
            if hasattr(msg, 'source') and msg.source in expert_names and hasattr(msg, 'content'):
                role_name_map = {
                    "Tarot_Expert_One": "神秘学者", # 修改：塔罗专家角色名
                    "Tarot_Expert_Two": "洞察者"  # 修改：塔罗专家角色名
                }
                display_source = role_name_map.get(msg.source, msg.source)
                expert_messages.append(f"【{display_source}】: {msg.content}")

        # 准备总结提示词
        summary_prompt = f"""
你是一位塔罗解读讨论的主管总结专家，负责对专家讨论进行全面、客观的总结。

你的任务是：
1.  仔细阅读两位塔罗专家（神秘学者和洞察者）的讨论内容。
2.  提取讨论中的关键观点、对牌面和牌阵的分析、以及最终的结论。
3.  识别专家们在解读牌义、牌阵结构、象征意义等方面达成共识的部分和存在分歧的部分。
4.  综合不同观点，形成对塔罗牌阵的全面总结。
5.  提供对牌阵关键信息（如核心牌、挑战牌、结果牌等）的简明解读。
6.  总结牌阵对于“{self.discussion_topic}”这一主题的指导意义、潜在启示和行动建议。
7.  总结时，请特别关注专家们对于牌阵中象征意义、潜在挑战、以及未来可能性的不同解读，并尝试整合这些观点，给出一个既包含共识也点明分歧的全面概述。

塔罗牌阵信息：
{self.tarot_spread_data}

专家讨论内容：
{chr(10).join(expert_messages)}

请以中文撰写一个结构清晰、内容全面的总结，帮助咨询者理解塔罗专家的分析结果。
在总结的最后，请添加“结论”部分，简明扼要地给出最终建议或对未来的展望。
"""

        # 使用模型生成总结
        if self.model_client:
            try:
                # 创建一个临时消息列表，只包含总结提示
                temp_messages = [TextMessage(source="Summary_Request", content=summary_prompt)]

                # 调用模型生成总结
                response = await self.model_client.complete(
                    messages=temp_messages,
                    cancellation_token=cancellation_token
                )

                # 获取总结内容
                summary_content = response.message.content if hasattr(response, 'message') and hasattr(response.message, 'content') else "未能生成总结。"

                # 添加终止短语
                final_content = f"## 主管总结\n\n{summary_content}\n\n{self.termination_phrase}"

            except Exception as e:
                # 如果生成总结失败，仍然返回终止短语
                final_content = f"生成总结时出错: {str(e)}\n\n{self.termination_phrase}"
        else:
            # 如果没有模型客户端，只返回终止短语
            final_content = f"未配置模型客户端，无法生成总结。\n\n{self.termination_phrase}"

        # 返回包含总结和终止短语的消息
        response_message = TextMessage(source=self.name, content=final_content)
        return Response(chat_message=response_message)

    async def on_reset(self, cancellation_token: Optional[CancellationToken] = None) -> None:
        pass

    @property
    def produced_message_types(self) -> Sequence[type[BaseChatMessage]]:
        return [TextMessage]


async def run_tarot_team_analysis( # 修改：函数名
    tarot_spread_data: str, # 修改：参数名
    discussion_topic: str = DEFAULT_DISCUSSION_TOPIC,
    min_discussion_turns: int = DEFAULT_MIN_DISCUSSION_TURNS,
    max_total_messages: int = DEFAULT_MAX_TOTAL_MESSAGES,
    supervisor_model: str = SUPERVISOR_MODEL_NAME,
    expert_one_model: str = DEFAULT_TAROT_EXPERT_ONE_MODEL_NAME, # 修改
    expert_two_model: str = DEFAULT_TAROT_EXPERT_TWO_MODEL_NAME # 修改
) -> str:
    """
    运行塔罗团队分析，让两位塔罗专家对给定的牌阵进行讨论和分析。

    此函数创建一个由两位塔罗专家组成的团队，在主管的协调下对牌阵进行深入分析和讨论。
    专家们会从不同角度解读牌阵，并进行辩论以得出更全面的结论。
    讨论结束后，终止Agent会使用主管模型对整个对话进行总结，提供关键见解和结论。

    Args:
        tarot_spread_data: 塔罗牌阵数据，包含完整的牌阵信息 (例如：牌名、位置、是否逆位等)
        discussion_topic: 讨论主题，默认为"分析讨论"
        min_discussion_turns: 最少讨论轮数，默认为6轮
        max_total_messages: 最大消息数量，默认为30条
        supervisor_model: 主管模型名称
        expert_one_model: 专家一模型名称
        expert_two_model: 专家二模型名称

    Returns:
        包含专家讨论摘要和主管总结的结果
    """
    # --- 配置信息 ---
    SUPERVISOR_MODEL_NAME_LOCAL = supervisor_model
    DEFAULT_TAROT_EXPERT_ONE_MODEL_NAME_LOCAL = expert_one_model
    DEFAULT_TAROT_EXPERT_TWO_MODEL_NAME_LOCAL = expert_two_model
    DISCUSSION_TOPIC_LOCAL = discussion_topic
    TAROT_SPREAD_INFO_LOCAL = tarot_spread_data # 修改

    MIN_DISCUSSION_TURNS_BEFORE_TERMINATION_LOCAL = min_discussion_turns
    MAX_TOTAL_MESSAGES_LOCAL = max_total_messages

    # --- 创建Ollama客户端 ---
    try:
        supervisor_llm_client = create_ollama_client(SUPERVISOR_MODEL_NAME_LOCAL, model_info_for_ollama)
        first_tarot_expert_client = create_ollama_client(DEFAULT_TAROT_EXPERT_ONE_MODEL_NAME_LOCAL, model_info_for_ollama) # 修改
        second_tarot_expert_client = create_ollama_client(DEFAULT_TAROT_EXPERT_TWO_MODEL_NAME_LOCAL, model_info_for_ollama) # 修改
    except Exception as e:
        return f"初始化Ollama客户端时出错: {e}"

    # --- System message template for Tarot Experts --- # 修改
    tarot_expert_system_message_template = """
你是一位资深的塔罗解读专家，名为“{expert_name}”。
你将与其他塔罗专家一起，共同分析以下提供的塔罗牌阵信息，研讨的主题是：“{discussion_topic}”。

当前的塔罗牌阵信息如下（可能包含牌名、位置、正逆位等）：
--- 牌阵信息开始 ---
{tarot_spread_data}
--- 牌阵信息结束 ---

你的核心任务是进行深度、多维度的牌阵解读，并与其他专家进行富有洞察力的辩论：

**一、个体牌面深度挖掘：**
1.  **精准定位与释义：** 仔细审视每一张牌在其牌阵中的具体位置（例如：现状、挑战、根基、未来等）。结合该位置的传统含义与牌面本身的核心象征（图像、符号、颜色、数字、元素），提供一个精确且富有层次的初步解读。
2.  **正逆位的细致辨析：** 对于逆位牌，避免简单化为“不好”或“相反”。深入探讨其能量是如何被阻塞、内化、延迟、需要反思，或者以一种非传统、更隐晦的方式在运作。逆位牌往往指向内在的功课或被忽略的面向。
3.  **象征体系的运用：** 运用你对塔罗象征体系（如卡巴拉、占星、神话原型、色彩心理学等）的理解，揭示牌面更深层的含义。例如，某张牌上的特定符号可能与某个古老传说或心理原型相关联。

**二、牌阵整体与互动分析：**
4.  **能量流向与叙事构建：** 分析整个牌阵的能量是如何流动的？是顺畅、受阻还是冲突？牌阵整体在讲述一个怎样的“故事”？识别故事的起点、发展、高潮、转折点以及可能的结局趋势。
5.  **元素互动与平衡：** 评估牌阵中风、火、水、土元素的分布情况。是否存在某个元素过强或过弱？元素之间的生克制化关系（例如，火元素的热情是否被水元素的情感所调和或熄灭？）对当前议题有何影响？
6.  **数字序列与模式：** 关注小阿尔卡那牌的数字序列（例如，从2到3到4的进展）或重复出现的数字。这些数字模式可能揭示了发展的阶段、能量的强调或需要特别关注的课题。
7.  **牌组优势与缺失：** 大阿尔卡那牌的出现比例是否显著？哪个小阿尔卡那牌组（权杖、圣杯、宝剑、星币）占据主导？这反映了问题的核心领域或能量焦点。是否有某个牌组明显缺失，暗示了被忽略的面向？
8.  **宫廷牌的角色扮演与人际互动：** 如果出现宫廷牌，它们代表了哪些具体的人物、人格特质、或者求问者需要扮演的角色？多张宫廷牌之间是否存在互动关系（如对望、背离、权力结构）？
9.  **关键牌识别与串联：** 识别牌阵中的指示牌（Significator, 如有）、核心牌（Crux）、挑战牌、辅助牌、结果牌等关键位置的牌。这些牌如何相互作用，共同揭示问题的核心？

**三、结合议题的实际应用与指导：**
10. **聚焦议题“{discussion_topic}”：** 始终将你的分析与求问者提出的具体议题紧密联系。牌阵的每一个发现如何回应了这个议题？它揭示了哪些与议题相关的现状、潜在影响、未来趋势、内在/外在的挑战与机遇？
11. **提供可行动的洞见：** 基于牌阵分析，提出具体、有建设性的思考方向或行动建议。这些建议应当是启发性的，帮助求问者更好地理解自身处境并做出明智选择。

############ 核心修改开始 ############
**四、深度辩论与多维视角碰撞：**
12. **主动质疑与挑战：** 当其他专家发表观点时，你的任务是进行批判性思考。**不要轻易认同，主动寻找其解读中可能存在的盲点、片面性或过度简化之处。** 例如，对方是否忽略了某张牌的逆位细节？是否对牌阵的某个象征有更深或不同的理解？
13. **挖掘不同解读层次：** 即便对同一张牌，也尝试从不同层面（例如：心理层面、灵性层面、现实层面、人际关系层面）提出你的独特见解，即使这与传统解读或其他专家的观点形成对比。
14. **引用依据，深入辩驳：** 当你提出不同意见或质疑时，必须引用牌阵中的具体信息（牌名、位置、图像细节、元素互动、数字关联等）以及相关的塔罗理论知识来支持你的论点。清晰阐述为什么你认为另一种解读更合理或更全面。
15. **探求象征的丰富性：** 塔罗的象征是多义的。鼓励从不同的象征学派（如荣格心理学原型、神话学、炼金术符号等）或不同的塔罗体系（如伟特、透特、马赛等，如果你的知识库支持）角度丰富解读，挑战单一的字面意义。
16. **识别并整合矛盾信息：** 牌阵中常常出现看似矛盾的信息。你的任务不是回避这些矛盾，而是深入探讨它们为何同时存在，它们可能揭示了求问者内心的何种张力、外界环境的复杂性，或是需要整合的对立面。
17. **推动讨论向深层发展：** 如果讨论停留在表面，主动提出更具挑战性的问题，引导对话触及牌阵更本质、更核心的启示。例如：“这张‘塔’的出现，仅仅是外部的突变，还是也暗示了某种内在结构的崩塌与重建的必要性？”
############ 核心修改结束 ############

请充分阐述你的观点，直到项目经理（主管）指示讨论结束。
请使用中文进行分析和回复。
"""

    # --- 定义参与的Agent ---
    tools = [tarot_reading_tool] if HAS_READING_TOOL else [] # 修改

    tarot_expert_one_agent = AssistantAgent( # 修改
        name="Tarot_Expert_One", # 修改
        model_client=first_tarot_expert_client,
        system_message=tarot_expert_system_message_template.format(
            expert_name="神秘学者", # 修改
            discussion_topic=DISCUSSION_TOPIC_LOCAL,
            tarot_spread_data=TAROT_SPREAD_INFO_LOCAL # 修改
        ),
        description="塔罗专家一（神秘学者），侧重于牌阵的整体结构、象征意义和能量流动分析。", # 修改
        tools=tools,
    )
    tarot_expert_one_agent.description_for_llm = "神秘学者 (Tarot_Expert_One): 塔罗专家，精通塔罗牌的象征体系、神话原型以及牌阵的深层叙事解读。" # 修改

    tarot_expert_two_agent = AssistantAgent( # 修改
        name="Tarot_Expert_Two", # 修改
        model_client=second_tarot_expert_client,
        system_message=tarot_expert_system_message_template.format(
            expert_name="洞察者", # 修改
            discussion_topic=DISCUSSION_TOPIC_LOCAL,
            tarot_spread_data=TAROT_SPREAD_INFO_LOCAL # 修改
        ),
        description="塔罗专家二（洞察者），侧重于单张牌的细节解读、牌与牌之间的具体互动关系以及实际应用指导。", # 修改
        tools=tools,
    )
    tarot_expert_two_agent.description_for_llm = "洞察者 (Tarot_Expert_Two): 塔罗专家，擅长从牌面细节、元素互动、数字命理角度进行分析，并提供实际可行的建议。" # 修改

    # 创建终止信号Agent实例（同时负责总结）
    terminator_agent = TerminationSignalAgent(
        tarot_spread_data=TAROT_SPREAD_INFO_LOCAL, # 修改
        discussion_topic=DISCUSSION_TOPIC_LOCAL
    )
    # 设置终止Agent使用主管的模型客户端进行总结
    terminator_agent.model_client = supervisor_llm_client

    participants = [tarot_expert_one_agent, tarot_expert_two_agent, terminator_agent] # 修改

    # --- 为主管（Selector）定义选择器提示 ---
    participant_descriptions_for_prompt_list = []
    for agent in participants:
        desc = agent.description_for_llm if hasattr(agent, 'description_for_llm') else agent.description
        participant_descriptions_for_prompt_list.append(f"- {agent.name} ({desc})")
    participant_descriptions_for_prompt = "\n".join(participant_descriptions_for_prompt_list)

    selector_prompt = (
        f"你是一位塔罗解读讨论的项目经理，负责协调专家之间的讨论，确保讨论深入、全面，并能为求问者提供有价值的洞见。\n\n"
        f"参与者:\n{participant_descriptions_for_prompt}\n\n"
        f"你的任务是选择下一位发言者。每次只能选择一位参与者。\n\n"
        f"讨论主题: {DISCUSSION_TOPIC_LOCAL}\n\n"
        f"当前塔罗牌阵信息（供你参考，专家已知晓）：\n{TAROT_SPREAD_INFO_LOCAL}\n\n" # 新增：让主管也看到牌阵信息，有助于判断讨论深度

        f"选择规则:\n"
        f"1. **促进深度辩论是首要目标。** 在讨论初期，让两位专家（神秘学者、洞察者）轮流发言，确保他们都能对牌阵的各个方面（如整体象征、个体牌义、元素数字互动、牌阵叙事等）给出初步但深入的分析。鼓励他们从一开始就展现各自的专长和不同视角。\n"
        f"2. 当讨论进行到至少 {MIN_DISCUSSION_TURNS_BEFORE_TERMINATION_LOCAL} 轮**富有实质内容的专家发言**后（不仅仅是简单同意或重复），并且你判断以下条件满足时，才考虑选择 '{TERMINATOR_AGENT_NAME}' 进行总结：\n"
        f"   a. 牌阵中的关键牌（如指示牌、核心牌、挑战牌、结果牌）都得到了多角度的深入解读。\n"
        f"   b. 专家们对牌阵的整体能量、主要矛盾点、以及潜在的故事线都进行了充分的探讨和辩论。\n"
        f"   c. 对于求问者的议题“{DISCUSSION_TOPIC_LOCAL}”，牌阵所能提供的核心洞见、挑战、机遇和建议已经比较清晰，或者不同观点间的张力已得到充分展现。\n"
        f"3. **如果讨论深度不足，必须继续引导专家深入：**\n"
        f"   a. 若专家意见趋同过早，或解读停留在表面关键词，应选择能提出**不同意见、质疑现有结论、或从全新角度（例如，不同的象征体系、更细微的牌面细节、被忽略的牌间互动）**进行解读的专家。\n"
        f"   b. 明确指示专家**互相质疑和挑战**对方的论点，要求他们为自己的解读提供更充分的牌阵内部证据。\n"
        f"   c. 引导专家探讨牌阵中可能存在的**内在矛盾或被忽略的细节**。例如：'洞察者，神秘学者认为这张牌代表A，但你从元素角度看，它是否也暗示了B这种可能性？请详细阐述。'\n"
        f"4. **优先选择能够推动对话向更深层次发展的发言者。** 这可能意味着选择一位专家去回应或反驳前一位专家的特定观点，或者引入一个新的分析维度（如数字命理、宫廷牌的深层含义等）。\n"
        f"5. 确保专家不仅解读牌面，更要**时刻紧扣“{DISCUSSION_TOPIC_LOCAL}”这一核心议题**，将分析结果转化为对求问者有实际指导意义的洞见和建议。\n\n"
        f"在未达到最少轮数或辩论深度不足时，请继续选择 'Tarot_Expert_One' 或 'Tarot_Expert_Two' 发言。你的选择应旨在**激发更激烈的思想碰撞、挖掘更深层的象征意义、并最终形成对牌阵更全面、更多元的理解。**\n\n"
        "请仔细阅读以下的对话历史（关注专家发言的次数、每一次发言的分析深度、是否进行了有效的相互质疑与补充、是否深入挖掘了牌阵细节与象征、以及讨论是否围绕核心议题展开），来决定下一位最适合的发言者。\n"
        "--- 对话历史开始 ---\n"
        "{history}"
        "\n--- 对话历史结束 ---\n\n"
        f"你的任务是根据当前的对话进展、专家角色、讨论的深度与广度（尤其是在满足最少 {MIN_DISCUSSION_TURNS_BEFORE_TERMINATION_LOCAL} 轮有效专家发言后），来决定下一位最适合的发言者，以期获得最富有洞察力的塔罗解读。\n"
        f"你的回答必须且只能是其中一位参与者的英文名称 (例如 'Tarot_Expert_One', 'Tarot_Expert_Two', 或 '{TERMINATOR_AGENT_NAME}')。"
    )

    # --- 创建并组合终止条件 ---
    supervisor_decided_termination = TextMentionTermination(
        text=TERMINATION_PHRASE_FROM_TERMINATOR,
        sources=[TERMINATOR_AGENT_NAME]
    )
    max_messages_fallback_termination = MaxMessageTermination(max_messages=MAX_TOTAL_MESSAGES_LOCAL)
    combined_termination_condition = OrTerminationCondition(supervisor_decided_termination, max_messages_fallback_termination)

    # --- 创建SelectorGroupChat ---
    team = SelectorGroupChat(
        participants=participants,
        model_client=supervisor_llm_client,
        selector_prompt=selector_prompt,
        termination_condition=combined_termination_condition,
        allow_repeated_speaker=False, # 通常设置为False，但在某些辩论场景下，主管可以决定是否重复选择同一专家以深入追问
        model_client_streaming=False
    )

    # --- 准备初始消息 ---
    initial_message_content = (
        f"请两位塔罗专家根据以下牌阵信息，就主题「{DISCUSSION_TOPIC_LOCAL}」进行深入分析和讨论。\n\n"
        "请注意：\n"
        "1. 分析时要引用牌阵中的具体信息作为依据（如牌名、位置、元素、数字、符号等）。\n"
        "2. 要从不同角度解读牌阵（象征意义、心理层面、实际影响等），不要轻易认同对方观点，鼓励建设性质疑。\n"
        "3. 当发现对方解读有遗漏、片面或不同见解时，要明确指出并提供更合理、更深入的解释，并阐述理由。\n"
        "4. 讨论应当聚焦于牌阵的专业解读，探索牌阵揭示的深层智慧，而非简单的个人观点对立。\n\n"
        f"塔罗牌阵信息：\n{TAROT_SPREAD_INFO_LOCAL}\n\n"
        "请开始讨论。"
    )

    initial_task_message = TextMessage(source="Project_Manager_Bot", content=initial_message_content)

    # --- 运行群聊 ---
    task_result = await team.run(task=[initial_task_message], cancellation_token=CancellationToken())

    # --- 处理结果 ---
    result_summary = "塔罗专家讨论结果摘要：\n\n" # 修改

    if task_result and task_result.messages:
        # 计算实际专家发言次数
        actual_expert_turns = 0
        for msg in task_result.messages:
            if msg.source in [tarot_expert_one_agent.name, tarot_expert_two_agent.name]: # 修改
                actual_expert_turns += 1

        # 添加专家发言摘要
        for i, msg in enumerate(task_result.messages):
            if hasattr(msg, 'content'):
                role_name_map = {
                    tarot_expert_one_agent.name: "神秘学者", # 修改
                    tarot_expert_two_agent.name: "洞察者",   # 修改
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
                    result_summary += f"{content}\n\n"
                    continue

                # 添加专家发言
                result_summary += f"【{display_source}】: {msg.content}\n\n"

        result_summary += f"专家发言轮数: {actual_expert_turns}\n"
    else:
        result_summary += "讨论未能正常进行或没有消息交换。"

    # 关闭Ollama客户端
    await supervisor_llm_client.close()
    await first_tarot_expert_client.close() # 修改
    await second_tarot_expert_client.close() # 修改

    return result_summary


def tarot_team_analysis( # 修改：函数名
    tarot_spread_data: Annotated[str, "塔罗牌阵数据，包含牌名、位置、是否正逆位等详细信息"], # 修改
    discussion_topic: Annotated[str, "讨论主题，例如'分析爱情运势'或'事业发展路径'等"] = DEFAULT_DISCUSSION_TOPIC, # 修改
    min_discussion_turns: Annotated[int, "最少讨论轮数，默认为6轮"] = DEFAULT_MIN_DISCUSSION_TURNS,
    max_total_messages: Annotated[int, "最大消息数量，默认为30条"] = DEFAULT_MAX_TOTAL_MESSAGES
) -> str:
    """
    运行塔罗团队分析，让两位塔罗专家对给定的牌阵进行讨论和分析。

    此工具创建一个由两位塔罗专家组成的团队，在主管的协调下对牌阵进行深入分析和讨论。
    专家们会从不同角度解读牌阵，并进行辩论以得出更全面的结论。
    讨论结束后，终止Agent会使用主管模型对整个对话进行总结，提供关键见解和结论。

    Args:
        tarot_spread_data: 塔罗牌阵数据
        discussion_topic: 讨论主题
        min_discussion_turns: 最少讨论轮数
        max_total_messages: 最大消息数量

    Returns:
        包含专家讨论摘要和主管总结的结果
    """
    # 使用asyncio运行异步函数
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError: # pragma: no cover
        # This is to handle the case where there is no current event loop.
        # This can happen if the function is called from a thread that is not the main thread.
        # If running in a new thread or environment without a default event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    result = loop.run_until_complete(
        run_tarot_team_analysis( # 修改
            tarot_spread_data=tarot_spread_data, # 修改
            discussion_topic=discussion_topic,
            min_discussion_turns=min_discussion_turns,
            max_total_messages=max_total_messages
        )
    )
    return result


# 模块只能被导入使用，不支持直接运行
if __name__ == "__main__": # pragma: no cover
    print("错误: tarot_team.py 只能作为模块导入使用，不支持直接运行。") # 修改
    print("请在您的代码中导入并使用 tarot_team_analysis 函数。") # 修改
    print("示例:")
    print("  from your_module_path.tarot_team import tarot_team_analysis") # 修改
    print("  example_spread = '''牌阵：凯尔特十字")
    print("  1. 当前状况：权杖十 (逆位)")
    print("  2. 眼前的阻碍：宝剑三")
    print("  3. 目标/最佳结果：圣杯王后")
    print("  4. 根基：星币骑士")
    print("  5. 近期过去：愚人")
    print("  6. 近期未来：命运之轮")
    print("  7. 你自身：圣杯侍从 (逆位)")
    print("  8. 环境：宝剑七 (逆位)")
    print("  9. 指引/课题：女祭司")
    print("  10. 最终可能：太阳'''")
    print("  result = tarot_team_analysis(tarot_spread_data=example_spread, discussion_topic='分析当前事业发展的挑战与机遇')") # 修改
    print("  print(result)")

    # # 更详细的测试示例 (取消注释以运行)
    # async def main_async_test():
    #     sample_tarot_spread = """
    #     牌阵类型: 凯尔特十字
    #     问题: 我目前的工作前景如何？

    #     1.  现状 (Present Position): 权杖十 (Ten of Wands) - 正位
    #         描述: 一个人背负着沉重的十根权杖，艰难前行。
    #     2.  直接挑战 (Immediate Challenge): 宝剑侍从 (Page of Swords) - 逆位
    #         描述: 年轻人显得鲁莽，言语可能伤人，缺乏计划。
    #     3.  遥远过去/根基 (Distant Past / Foundation): 星币七 (Seven of Pentacles) - 正位
    #         描述: 一个人在花园中审视自己的劳动成果，思考下一步。
    #     4.  近期过去 (Recent Past): 圣杯二 (Two of Cups) - 正位
    #         描述: 两人交换杯子，象征合作与情感连接。
    #     5.  目标或最佳结果 (Best Outcome / Crown): 皇帝 (The Emperor) - 正位
    #         描述: 威严的统治者坐在宝座上，象征权威、结构和控制。
    #     6.  近期未来 (Immediate Future): 权杖三 (Three of Wands) - 正位
    #         描述: 一个人站在悬崖边，眺望远方，等待船只归来，象征计划和远见。
    #     7.  求问者心态 (Querent's Attitude): 隐士 (The Hermit) - 逆位
    #         描述: 隐士提灯独行，逆位可能表示孤立或逃避。
    #     8.  外部环境 (External Environment): 星星 (The Star) - 正位
    #         描述: 女子在星空下将水倒入池中和土地，象征希望、灵感和治愈。
    #     9.  希望与恐惧 (Hopes and Fears): 月亮 (The Moon) - 逆位
    #         描述: 月亮照耀下的奇异景象，逆位可能表示困惑解除或真相浮现。
    #     10. 最终结果 (Final Outcome): 星币王后 (Queen of Pentacles) - 正位
    #         描述: 富有、务实的女性，手持星币，象征滋养、实际和富足。
    #     """
    #     topic = "分析我目前的工作前景，并提供发展建议"
        
    #     print(f"正在运行塔罗团队分析，主题：{topic}...")
    #     # 注意：实际运行时，需要确保Ollama服务正在运行，并且配置的模型可用
    #     # 这里假设模型名称是有效的，如果不是，请修改为实际可用的模型名
    #     # result_text = await run_tarot_team_analysis(
    #     #     tarot_spread_data=sample_tarot_spread,
    #     #     discussion_topic=topic,
    #     #     min_discussion_turns=2, # 测试时可以减少轮数
    #     #     max_total_messages=15, # 测试时可以减少消息数
    #     #     supervisor_model="aistudio010", # 替换为你的Ollama模型
    #     #     expert_one_model="aistudio008", # 替换为你的Ollama模型
    #     #     expert_two_model="aistudio009"  # 替换为你的Ollama模型
    #     # )
    #     # print("\n--- 塔罗团队分析结果 ---")
    #     # print(result_text)
    #     # print("\n--- 分析结束 ---")
    #     print("请取消上面实际调用 run_tarot_team_analysis 的注释，并确保Ollama服务和模型配置正确以进行测试。")

    # if os.name == 'nt': # Windows
    #      asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    # # asyncio.run(main_async_test()) # 取消注释以运行异步测试代码

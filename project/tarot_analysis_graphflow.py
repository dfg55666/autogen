#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
test_graphflow_tarot.py - 测试 GraphFlow 条件控制循环功能（塔罗分析版）

这个脚本使用 Volces API 和 Ollama Gemini 测试 GraphFlow 的条件控制循环功能，
创建一个塔罗分析工作流：
1. 占卜师进行初步解读。
2. 两名英文分析师并行评审。
3. 总结节点用中文汇总英文分析师意见，决定是否需要修改或完成解读。
4. 编辑节点与用户确认最终解读。
5. 结束节点生成中文总结报告。
"""

import asyncio
import logging
import traceback # 用于打印详细错误信息
import os
from typing_extensions import Annotated

# 直接导入已安装的模块
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import DiGraphBuilder, GraphFlow
from autogen_ext.models.openai import OpenAIChatCompletionClient # autogen_ext.models.openai 已经迁移到 autogen.runtime.openai
# from autogen.runtime.openai import OpenAIChatCompletionClient # 假设已更新到新版
from autogen_core.tools import FunctionTool

# 配置日志 - 设置为警告级别，减少输出
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# ModelScope API 配置
MODELSCOPE_CONFIG = {
    "api_key": "e0026259-3528-49d4-8715-d7e9472ee047",
    "base_url": "https://api-inference.modelscope.cn/v1/",
    "model": "deepseek-ai/DeepSeek-V3-0324"
    # ModelScope API 不支持stream参数
}

# 不再使用固定任务，改为从人类获取输入

def create_modelscope_client(model: str) -> OpenAIChatCompletionClient:
    """
    创建 ModelScope API 客户端
    """
    model_info = {
        "name": model, "family": "openai", "prompt_token_cost": 0.0,
        "completion_token_cost": 0.0, "max_tokens": 32768, "vision": False,
        "function_calling": True, "json_output": True, "structured_output": True,
        "multiple_system_messages": True
    }
    return OpenAIChatCompletionClient(
        model=model, api_key=MODELSCOPE_CONFIG["api_key"], base_url=MODELSCOPE_CONFIG["base_url"],
        model_info=model_info, headers={"Content-Type": "application/json", "Authorization": f"Bearer {MODELSCOPE_CONFIG['api_key']}"}
        # ModelScope API 不支持stream参数
    )

# 不再使用Gemini客户端，全部使用ModelScope
def create_modelscope_client_for_all() -> OpenAIChatCompletionClient:
    """
    创建 ModelScope API 客户端，用于所有智能体
    """
    return create_modelscope_client(MODELSCOPE_CONFIG["model"])

async def test_agent_interaction() -> None:
    """
    测试智能体交互的并行执行，实现完整的循环反馈机制。
    """
    print("\n开始执行塔罗分析智能体交互测试...")

    if not os.path.exists("output"):
        os.makedirs("output")
        print("创建output目录成功")
    try:
        print("正在创建ModelScope API客户端...")
        modelscope_client = create_modelscope_client(MODELSCOPE_CONFIG["model"])
        print("ModelScope API客户端创建成功！")
    except Exception as e:
        print(f"创建ModelScope API客户端时出错: {e}. 将使用备选OpenAI客户端。")
        modelscope_client = OpenAIChatCompletionClient(model="gpt-3.5-turbo", api_key="sk-dummy-key", base_url="https://api.openai.com/v1/") # 确保有备选

    # 创建工具
    async def write_document(
        file_path: Annotated[str, "要写入的文件路径"],
        content: Annotated[str, "要写入文件的内容"]
    ) -> str:
        """将内容写入指定路径的文件。"""
        try:
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"成功写入文件: {file_path}"
        except Exception as e:
            return f"写入文件出错: {str(e)}"

    async def get_human_input(
        prompt: Annotated[str, "向人类显示的提示信息"]
    ) -> str:
        """获取人类用户的输入。"""
        try:
            print(f"\n【人类输入请求】: {prompt}")
            print("请输入您的回答 (直接回车默认为'是'):")
            user_input = input()
            if not user_input.strip(): # 如果用户直接回车
                user_input = "是"
            print(f"收到人类输入: {user_input}")
            return user_input
        except Exception as e:
            return f"获取人类输入时出错: {str(e)}"

    write_document_tool = FunctionTool(
        func=write_document,
        name="write_document",
        description="将内容写入指定路径的文件。参数file_path是文件路径，content是要写入的内容。例如，要将总结写入output/塔罗分析总结.md，可以调用write_document(file_path='output/塔罗分析总结.md', content='总结内容...')"
    )

    human_input_tool = FunctionTool(
        func=get_human_input,
        name="get_human_input",
        description="获取人类用户的输入。参数prompt是向人类显示的提示信息。例如，要询问人类是否对塔罗解读满意，可以调用get_human_input(prompt='您对这个塔罗解读满意吗？请回答\"是\"或\"否\"')"
    )

    # 所有智能体都使用ModelScope客户端
    modelscope_llm = modelscope_client  # 使用ModelScope客户端

    # 创建智能体
    # writer 更名为 LeadTarotReader (占卜师) - 使用ModelScope模型，输出中文
    writer = AssistantAgent(
        name="LeadTarotReader_CN", # 智能体在图中的名字
        model_client=modelscope_llm,
        tools=[human_input_tool],  # 添加人类输入工具
        reflect_on_tool_use=True,  # 开启工具调用反思
        tool_call_summary_format="{result}",  # 使用简单的结果格式
        system_message="""你是塔罗占卜师。你的任务是从人类获取占卜请求，进行初步的牌面解读，或根据反馈修改已有的解读。

工作流程：
1. 初次收到任务时：使用get_human_input工具询问人类想要解答的问题，提示语为："请输入您想要通过塔罗牌解答的问题："
2. 获取到人类输入后：进行初步的牌面解读，包括定义牌阵和抽出初始牌，确保解读包含对每张牌的初步看法。
3. 收到总结节点的修改建议时：根据建议修改你的解读，使其更加深入和准确。
4. 收到编辑的"仍需调整"反馈时：这意味着人类用户对解读不满意，你需要进一步完善和丰富你的解读。

重要规则：
- 必须先使用get_human_input工具获取人类的占卜请求，再进行解读。
- 无论是初次解读、根据总结节点修改，还是根据编辑反馈调整，你的回复末尾都必须添加标记"需要分析"（单独占一行）。
- 这个标记确保你的解读会被发送给分析师进行评审。
- 输出语言：中文。
"""
    )

    # reviewer1 更名为 SymbolismAnalyst_EN - 使用ModelScope模型，纯英文提示词和输出
    reviewer1 = AssistantAgent(
        name="SymbolismAnalyst_EN",
        model_client=modelscope_llm,
        system_message="""You are Tarot Analyst A.
Your role is to meticulously analyze the provided tarot reading, focusing on the traditional symbolism, numerology, and elemental dignities of each card presented.
Provide a concise analysis for each card based on these aspects.
Conclude your entire response with one of the following two phrases, on a new line, and nothing else after it:
- "Needs Refinement: [briefly explain why, e.g., "symbolism interpretation needs more depth for card X"]"
- "Interpretation Valid: [briefly confirm, e.g., "symbolism accurately represented"]"

IMPORTANT:
1.  For the first round of review, if the interpretation has any room for improvement, you MUST use "Needs Refinement: [reason]".
2.  For the second round of review (if applicable), if the writer has addressed previous concerns and the interpretation is solid from your perspective, use "Interpretation Valid: [reason]".
3.  Your entire output must be in English.
"""
    )

    # reviewer2 更名为 IntuitiveAnalyst_EN - 使用ModelScope模型，纯英文提示词和输出
    reviewer2 = AssistantAgent(
        name="IntuitiveAnalyst_EN",
        model_client=modelscope_llm,
        system_message="""You are Tarot Analyst B.
Your role is to analyze the provided tarot reading from an intuitive and psychological perspective.
Consider the archetypes, the narrative told by the cards, and potential emotional or subconscious messages.
Provide a concise analysis for each card based on these aspects.
Conclude your entire response with one of the following two phrases, on a new line, and nothing else after it:
- "Needs Refinement: [briefly explain why, e.g., "intuitive connection for card Y feels underdeveloped"]"
- "Interpretation Valid: [briefly confirm, e.g., "intuitive insights are clear and resonant"]"

IMPORTANT:
1.  For the first round of review, if the interpretation has any room for improvement, you MUST use "Needs Refinement: [reason]".
2.  For the second round of review (if applicable), if the writer has addressed previous concerns and the interpretation is solid from your perspective, use "Interpretation Valid: [reason]".
3.  Your entire output must be in English.
"""
    )



    async def get_human_input(
        prompt: Annotated[str, "向人类显示的提示信息"]
    ) -> str:
        """获取人类用户的输入。"""
        try:
            print(f"\n【人类输入请求】: {prompt}")
            print("请输入您的回答 (直接回车默认为'是'):")
            user_input = input()
            if not user_input.strip(): # 如果用户直接回车
                user_input = "是"
            print(f"收到人类输入: {user_input}")
            return user_input
        except Exception as e:
            return f"获取人类输入时出错: {str(e)}"

    write_document_tool = FunctionTool(
        func=write_document,
        name="write_document",
        description="将内容写入指定路径的文件。参数file_path是文件路径，content是要写入的内容。例如，要将总结写入output/塔罗分析总结.md，可以调用write_document(file_path='output/塔罗分析总结.md', content='总结内容...')"
    )

    human_input_tool = FunctionTool(
        func=get_human_input,
        name="get_human_input",
        description="获取人类用户的输入。参数prompt是向人类显示的提示信息。例如，要询问人类是否对塔罗解读满意，可以调用get_human_input(prompt='您对这个塔罗解读满意吗？请回答“是”或“否”')"
    )

    # summary_node 更名为 AnalysisSynthesizer_CN - 使用ModelScope模型，接收英文输入，输出中文
    summary_node = AssistantAgent(
        name="AnalysisSynthesizer_CN",
        model_client=modelscope_llm,
        system_message="""你是塔罗分析总结专家。你的任务是仔细阅读两位英文分析师（SymbolismAnalyst_EN 和 IntuitiveAnalyst_EN）的评审意见，并用中文进行总结和决策。

工作流程：
1.  仔细阅读两位分析师的英文分析。注意他们各自的结论是 "Needs Refinement: ..." 还是 "Interpretation Valid: ..."。
2.  用中文总结两位分析师的主要观点和具体建议（如果有）。
3.  做出决策：
    - 如果两位分析师的结论都明确包含 "Interpretation Valid"，那么你的回复最后一行必须是 "解读完成"（单独一行）。
    - 如果任何一位分析师的结论包含 "Needs Refinement"，你应该综合他们的修改意见（即使另一位认为有效），然后在你的回复最后一行必须是 "需要修改"（单独一行）。

回复格式：
1.  [中文] 对SymbolismAnalyst_EN意见的总结：...
2.  [中文] 对IntuitiveAnalyst_EN意见的总结：...
3.  [中文] 综合建议给占卜师：... (如果需要修改)
4.  最后一行必须是 "需要修改" 或 "解读完成" (这两个是你的中文决策关键词)。

重要规则：
- 你的输出必须完全是中文。
- 你的中文决策关键词（"需要修改" 或 "解读完成"）必须单独放在最后一行，它将决定流程的走向。
- 即使分析师的理由很短，你也需要做出明确的总结和决策。
"""
    )

    # editor 更名为 FinalReviewer_CN - 使用ModelScope模型，处理中文内容
    editor = AssistantAgent(
        name="FinalReviewer_CN",
        model_client=modelscope_llm,
        tools=[human_input_tool],
        reflect_on_tool_use=True,
        system_message="""你是资深塔罗解读编辑，负责对占卜师完成的最终解读（由总结节点确认“解读完成”）进行审核，并根据人类用户的意见决定是否可以交付。

审核流程：
1.  用中文简要分析占卜师提交的最终解读（1-2句话即可）。
2.  立即使用get_human_input工具询问人类用户是否满意最终解读。
   例如：询问“这是关于[占卜主题]的塔罗解读。您认为这个解读是否清晰且令人满意？请回答‘是’或‘否’（直接回车默认为'是'）”
3.  根据人类用户的回答决定审核结论。

审核结论规则：
- 如果人类用户回答包含"是"或为空，你必须用中文回复"同意交付"（单独一行）。
- 如果人类用户回答包含"否"，你必须用中文回复"仍需调整"（单独一行）。

重要：
1.  确保你的回复简短，并且最后一行必须是"同意交付"或"仍需调整"。
2.  当你收到人类输入后，你必须立即给出审核结论，不要再次调用工具。
3.  你的输出语言为中文。
"""
    )

    # end_node 更名为 ReportGenerator_CN - 使用ModelScope模型，输出中文总结
    end_node = AssistantAgent(
        name="ReportGenerator_CN",
        model_client=modelscope_llm,
        tools=[write_document_tool],
        system_message="""你是结束节点。请用中文总结整个塔罗分析过程。
报告内容应包括：
1.  初始占卜请求。
2.  分析和修改的轮数。
3.  关键反馈路径和决策点（例如，分析师的意见，总结节点的判断，编辑的确认）。
4.  每位智能体（占卜师、英文分析师、中文总结节点、编辑）的主要贡献。
5.  塔罗解读内容是如何从初稿演变到最终稿的。
6.  多智能体协作（特别是跨语言协作）的效果评估。
7.  对流程的任何优化建议。

总结应全面深入，语言为中文。
完成总结后，你必须使用write_document工具将总结内容保存到文件中。

使用工具的具体步骤：
1. 首先完成你的中文总结报告。
2. 然后调用write_document工具，传入以下参数：
   - file_path: "output/塔罗分析总结.md"
   - content: 你的完整中文总结内容
这是非常重要的任务，你必须确保调用工具保存文件。
"""
    )

    from autogen_agentchat.agents import MessageFilterAgent, MessageFilterConfig, PerSourceFilter

    # 创建过滤器配置
    # 分析师过滤器：接收占卜师的最新消息，以及另一位分析师的最新消息（如果需要他们互相参考，但当前设计是独立分析后汇总）
    # 这里我们假设分析师仅需看到占卜师的最新稿件。如果需要看到彼此，可以调整。
    analyst_filter_config = MessageFilterConfig(
        per_source=[
            PerSourceFilter(source=writer.name, position="last", count=1) # 看占卜师的最新稿
        ]
    )
    # 如果分析师需要看到对方的最新意见（可能导致死锁或复杂依赖，需小心设计）
    # analyst_filter_config_peer_aware = MessageFilterConfig(
    #     per_source=[
    #         PerSourceFilter(source=writer.name, position="last", count=1),
    #         PerSourceFilter(source=reviewer1.name, position="last", count=1), # reviewer2看reviewer1
    #         PerSourceFilter(source=reviewer2.name, position="last", count=1)  # reviewer1看reviewer2
    #     ]
    # )


    # 总结节点过滤器配置 - 接收两位分析师的最新消息
    summary_filter = MessageFilterConfig(
        per_source=[
            PerSourceFilter(source=reviewer1.name, position="last", count=1),
            PerSourceFilter(source=reviewer2.name, position="last", count=1)
        ]
    )

    # 编辑节点过滤器：接收总结节点的最新消息
    editor_filter = MessageFilterConfig(
        per_source=[PerSourceFilter(source=summary_node.name, position="last", count=1)]
    )

    # 使用过滤器包装智能体
    # 注意：这里使用 .name 属性来确保 MessageFilterAgent 能正确识别 source
    filtered_reviewer1 = MessageFilterAgent(name=reviewer1.name, wrapped_agent=reviewer1, filter=analyst_filter_config)
    filtered_reviewer2 = MessageFilterAgent(name=reviewer2.name, wrapped_agent=reviewer2, filter=analyst_filter_config)
    filtered_summary_node = MessageFilterAgent(name=summary_node.name, wrapped_agent=summary_node, filter=summary_filter)
    filtered_editor = MessageFilterAgent(name=editor.name, wrapped_agent=editor, filter=editor_filter)

    builder = DiGraphBuilder()
    builder.add_node(writer, activation="any") # writer是LeadTarotReader_CN
    builder.add_node(filtered_reviewer1) # SymbolismAnalyst_EN
    builder.add_node(filtered_reviewer2) # IntuitiveAnalyst_EN
    builder.add_node(filtered_summary_node, activation="all") # AnalysisSynthesizer_CN，等待两位分析师
    builder.add_node(filtered_editor) # FinalReviewer_CN
    builder.add_node(end_node) # ReportGenerator_CN
    builder.set_entry_point(writer)

    # 定义条件函数
    writer_needs_analysis = lambda msg: "需要分析" in msg.to_model_text() # 中文
    # 分析师的英文关键词由总结节点处理，总结节点输出中文关键词
    summary_needs_revision_cn = lambda msg: "需要修改" in msg.to_model_text() # 中文
    summary_interpretation_complete_cn = lambda msg: "解读完成" in msg.to_model_text() # 中文
    editor_approve_cn = lambda msg: "同意交付" in msg.to_model_text() # 中文
    editor_revision_cn = lambda msg: "仍需调整" in msg.to_model_text() # 中文

    # 流程图：
    # 占卜师 -> 分析师 (当占卜师完成初步解读并标记"需要分析")
    builder.add_edge(writer, filtered_reviewer1, condition=writer_needs_analysis)
    builder.add_edge(writer, filtered_reviewer2, condition=writer_needs_analysis)

    # 分析师 -> 总结节点 (无条件，两位分析师的英文反馈都会发送给总结节点)
    builder.add_edge(filtered_reviewer1, filtered_summary_node)
    builder.add_edge(filtered_reviewer2, filtered_summary_node)

    # 总结节点 -> 占卜师 (当总结节点用中文判断"需要修改")
    builder.add_edge(filtered_summary_node, writer, condition=summary_needs_revision_cn)

    # 总结节点 -> 编辑 (当总结节点用中文判断"解读完成")
    builder.add_edge(filtered_summary_node, filtered_editor, condition=summary_interpretation_complete_cn)

    # 编辑 -> 占卜师 (当编辑根据用户反馈用中文判断"仍需调整")
    builder.add_edge(filtered_editor, writer, condition=editor_revision_cn)

    # 编辑 -> 结束节点 (当编辑根据用户反馈用中文判断"同意交付")
    builder.add_edge(filtered_editor, end_node, condition=editor_approve_cn)

    print("\n正在构建塔罗分析GraphFlow图...")
    graph = builder.build()
    print("图构建完成！")

    print("\n正在创建GraphFlow团队...")
    team = GraphFlow(participants=builder.get_participants(), graph=graph, max_turns=20) # 减少轮数以防死循环
    print("GraphFlow团队创建成功！")

    print("\n=== 塔罗分析自动化系统 ===")
    print(f"1. 占卜师(模型: {MODELSCOPE_CONFIG['model']})将根据预设塔罗任务进行初步解读。")
    print(f"2. 初步解读发送给两位英文分析师(模型: {MODELSCOPE_CONFIG['model']})并行评审。")
    print(f"3. 英文分析师的评审意见发送给中文总结节点(模型: {MODELSCOPE_CONFIG['model']})。")
    print("4. 总结节点汇总英文意见并用中文做出决策：")
    print("   - 如果需要修改：发回占卜师继续修改。")
    print("   - 如果解读完成：发送给中文编辑进行最终审核。")
    print(f"5. 编辑(模型: {MODELSCOPE_CONFIG['model']})会询问人类用户对解读的意见。")
    print("6. 如果人类用户认为仍需调整，内容会发回占卜师修改。")
    print("7. 如果人类用户满意，编辑审核通过后，解读将发送给结束节点。")
    print(f"8. 结束节点(模型: {MODELSCOPE_CONFIG['model']})用中文总结过程并写入 'output/塔罗分析总结.md'。")
    print("==================================================")

    print("\n开始执行流程，将显示详细的事件流：")
    print("-" * 50)

    cycle_count = 0
    try:
        print("\n开始运行GraphFlow团队...")
        event_count = 0
        async for event in team.run_stream(task="请使用塔罗牌为我解答问题"):
            event_count += 1
            print(f"\n接收到事件 #{event_count}: {type(event).__name__} from {getattr(event, 'source', 'N/A')} to {getattr(event, 'target', 'N/A')}")


            if hasattr(event, 'type') and event.type == "TextMessage":
                source_agent_name = getattr(event, 'source', 'unknown_agent')
                target_agent_name = getattr(event, 'target', 'unknown_agent_target')
                content = getattr(event, 'content', '')
                print(f"消息事件: 从 {source_agent_name} 到 {target_agent_name}, 内容长度: {len(content)}字符")

                if source_agent_name == writer.name and writer_needs_analysis(event):
                     cycle_count += 1
                     print(f"\n【占卜与分析循环】: 第 {cycle_count} 轮开始")


                # 打印智能体角色和语言提示
                if source_agent_name == writer.name:
                    print(f"\n[{writer.name}(DeepSeek, 中文)] -> [{target_agent_name}]")
                elif source_agent_name == reviewer1.name:
                    print(f"\n[{reviewer1.name}(DeepSeek, 英文)] -> [{target_agent_name}]")
                elif source_agent_name == reviewer2.name:
                    print(f"\n[{reviewer2.name}(DeepSeek, 英文)] -> [{target_agent_name}]")
                elif source_agent_name == summary_node.name:
                    print(f"\n[{summary_node.name}(DeepSeek, 中文总结)] -> [{target_agent_name}]")
                elif source_agent_name == editor.name:
                    print(f"\n[{editor.name}(DeepSeek, 中文交互)] -> [{target_agent_name}]")
                elif source_agent_name == end_node.name:
                    print(f"\n[{end_node.name}(DeepSeek, 中文报告)] -> [{target_agent_name}]")

                # 打印决策或状态
                if source_agent_name == writer.name and writer_needs_analysis(event):
                    print("【占卜师决策】: 初步解读完成，发送给分析师。")
                elif source_agent_name == summary_node.name:
                    if summary_needs_revision_cn(event):
                        print("【总结节点决策】: 中文判断 -> 需要修改。发回占卜师。")
                    elif summary_interpretation_complete_cn(event):
                        print("【总结节点决策】: 中文判断 -> 解读完成。发给编辑。")
                elif source_agent_name == editor.name:
                    if editor_approve_cn(event):
                        print("【编辑决策】: 中文判断 -> 同意交付。发给结束节点。")
                    elif editor_revision_cn(event):
                        print("【编辑决策】: 中文判断 -> 仍需调整。发回占卜师。")

                if content:
                    # 检查内容中是否包含JSON格式的工具调用 (主要针对 editor)
                    if source_agent_name == editor.name and "{" in content and "}" in content and "get_human_input" in content:
                        # (简单检查，实际解析在下面ToolCallRequestEvent中)
                        print(f"【检测到编辑节点可能发起工具调用】")


                    if len(content) > 300:
                        print(f"内容:\n{content[:300]}...\n(内容较长，已截断显示)")
                    else:
                        print(f"内容:\n{content}")
                    print("-" * 50)

            elif hasattr(event, 'type') and event.type == "ToolCallRequestEvent":
                source_agent = getattr(event, 'source', 'unknown')
                print(f"\n【工具调用请求】 from {source_agent}:")
                if hasattr(event, 'tool_call') and event.tool_call:
                    tool_name = event.tool_call.name
                    tool_params = event.tool_call.parameters
                    print(f"  工具名称: {tool_name}, 参数: {tool_params}")
                    if tool_name == "get_human_input":
                         print(f"  【人类参与】: {source_agent} 正在通过工具请求人类用户的意见: {tool_params.get('prompt')}")
                else: # 兼容旧版或不同事件结构
                    tool_name = getattr(event, 'tool_name', '未知工具')
                    tool_params = getattr(event, 'tool_params', {})
                    print(f"  工具名称: {tool_name}, 参数: {tool_params}")
                    if tool_name == "get_human_input":
                         print(f"  【人类参与】: {source_agent} 正在通过工具请求人类用户的意见: {tool_params.get('prompt')}")
                print("-" * 50)


            elif hasattr(event, 'type') and event.type == "ToolCallExecutionEvent":
                source_agent = getattr(event, 'source', 'unknown')
                print(f"\n【工具调用执行】 by {source_agent}:")
                tool_name = "N/A"
                if hasattr(event, 'tool_call') and event.tool_call:
                    tool_name = event.tool_call.name
                result = getattr(event, 'result', '未知结果')
                print(f"  工具名称: {tool_name}, 执行结果: {result}")
                if tool_name == "get_human_input":
                    print(f"  【人类参与】: {source_agent} 的人类输入请求已执行，收到: '{result}'")
                elif tool_name == "write_document":
                     print(f"  【文件操作】: {source_agent} 的文档写入工具已执行，结果: '{result}'")
                print("-" * 50)


            elif hasattr(event, 'name') and event.name == "DiGraphStopAgent": # AutoGen内部用于停止图流程的特殊Agent名
                print(f"\n【流程结束】: {getattr(event, 'content', '图流程正常结束')}")
                print(f"总共完成了 {cycle_count} 轮占卜与分析循环。") # cycle_count现在只计算占卜师到分析师的次数
                print("=" * 50)

                output_path = "output/塔罗分析总结.md"
                if os.path.exists(output_path):
                    print(f"\n【文件已创建】: {output_path}")
                    try:
                        with open(output_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            print(f"\n文件内容预览 (前300字符):\n{content[:300]}...")
                    except Exception as e:
                        print(f"读取文件时出错: {e}")
                else:
                    print(f"\n【警告】: 文件 {output_path} 未创建。请检查结束节点的逻辑和工具调用。")

    except Exception as e:
        print(f"\n执行过程中出现错误: {e}")
        print(f"总共完成了 {cycle_count} 轮占卜与分析循环。")
        print("\n详细错误信息:")
        print("-" * 50)
        print(traceback.format_exc())
        print("-" * 50)
        print("\n尝试诊断问题:")
        print("1. 检查API密钥和网络连接。 2. 检查Ollama服务是否正在运行且模型可用。")
        print("3. 检查模型客户端初始化。 4. 检查GraphFlow图结构和条件函数中的关键词是否与智能体输出完全一致。")
        print("5. 检查智能体系统提示词是否清晰，特别是对于语言转换和决策逻辑。")

    print("\n塔罗分析智能体交互测试完成！")

async def main() -> None:
    """主函数"""
    try:
        print("\n=== 开始执行塔罗分析条件控制循环测试 ===")
        await test_agent_interaction()
    except Exception as e:
        print(f"\n执行过程中出现严重错误: {e}")
        print("详细错误信息如下：")
        print("-" * 50)
        traceback.print_exc()
        print("-" * 50)

if __name__ == "__main__":
    # API密钥已配置好


    import platform
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
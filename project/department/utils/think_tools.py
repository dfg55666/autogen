"""
思考工具模块 - 基于AutoGen 0.5.6的思考工具

本模块提供了一组用于AI思考的工具，基于MCP Think Tool的功能，
使用Python实现并与AutoGen 0.5.6集成。

主要功能:
- 记录思考过程
- 查看历史思考记录
- 清除思考记录
- 获取思考统计信息
- 引导AI按照结构化步骤进行思考和开发
  - 研究模式：收集信息
  - 创新模式：集思广益
  - 计划模式：创建技术规范
  - 执行模式：实施计划
  - 回顾模式：验证实施

这些工具可以帮助AI在复杂问题解决过程中进行结构化思考，
提高推理能力和问题解决效率。
"""

import json
import datetime
from typing import List, Dict, Optional, Any
from typing_extensions import Annotated

# 全局思考记录存储
# 注意：这是一个简单实现，在实际应用中可能需要更复杂的存储机制
_thoughts_log = []

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


def think(
    thought: Annotated[str, "要记录的思考内容，可以是结构化推理、逐步分析、政策验证或任何有助于问题解决的思考过程"] = ""
) -> str:
    """
    用于记录思考过程的工具。它不会获取新信息或改变任何内容，只是将思考添加到日志中。
    当需要复杂推理或缓存记忆时使用此工具。

    参数:
        thought: 要思考的内容。这可以是结构化推理、逐步分析、政策验证或任何有助于问题解决的思考过程。

    返回:
        记录的思考内容
    """
    # 记录思考，带有时间戳
    timestamp = datetime.datetime.now().isoformat()
    _thoughts_log.append({
        "timestamp": timestamp,
        "thought": thought
    })

    # 返回确认信息
    return thought


def get_thoughts() -> str:
    """
    获取当前会话中记录的所有思考。

    此工具有助于回顾迄今为止发生的思考过程。

    返回:
        格式化的思考记录列表
    """
    if not _thoughts_log:
        return "尚未记录任何思考。"

    formatted_thoughts = []
    for i, entry in enumerate(_thoughts_log, 1):
        formatted_thoughts.append(f"思考 #{i} ({entry['timestamp']}):\n{entry['thought']}\n")

    return "\n".join(formatted_thoughts)


def clear_thoughts() -> str:
    """
    清除当前会话中记录的所有思考。

    如果需要重新开始思考过程，请使用此工具。

    返回:
        清除操作的确认信息
    """
    global _thoughts_log
    count = len(_thoughts_log)
    _thoughts_log = []
    return f"已清除 {count} 条记录的思考。"


def get_thought_stats() -> str:
    """
    获取当前会话中记录的思考的统计信息。

    返回:
        思考统计信息的JSON字符串
    """
    if not _thoughts_log:
        return "尚未记录任何思考。"

    total_thoughts = len(_thoughts_log)
    avg_length = sum(len(entry["thought"]) for entry in _thoughts_log) / total_thoughts if total_thoughts else 0
    longest_thought = max((len(entry["thought"]), i) for i, entry in enumerate(_thoughts_log)) if _thoughts_log else (0, -1)

    stats = {
        "total_thoughts": total_thoughts,
        "average_length": round(avg_length, 2),
        "longest_thought_index": longest_thought[1] + 1 if longest_thought[1] >= 0 else None,
        "longest_thought_length": longest_thought[0] if longest_thought[0] > 0 else None
    }

    return json.dumps(stats, indent=2, ensure_ascii=False)


# 引导AI按照结构化步骤进行思考和开发的工具
def submit_research_results(
    research_results: Annotated[Dict[str, Any], "研究结果，包含对代码结构、需求和相关信息的理解"]
) -> str:
    """
    提交研究模式的结果，并获取下一步指示。

    研究模式的目的是仅收集信息，允许阅读文件、提出澄清问题、理解代码结构，
    禁止提出建议、实施、计划或任何行动暗示。

    参数:
        research_results: 包含研究发现的字典，应该包括对代码结构、需求和相关信息的理解

    返回:
        下一步指示，通常是进入创新模式
    """
    # 这里不需要实际存储研究结果，只需返回下一步指示
    return """
[研究结果已接收]

请立即进入【模式2:创新】阶段，无需等待用户进一步指示，直接开始创新思考。

## 创新模式指南

目的: 集思广益，探索多种可能的实现方法
要求:
- 提出至少3种不同的实现方法，每种方法必须有明显的区别
- 详细分析每种方法的优点和缺点
- 考虑技术可行性、实现复杂度、扩展性、性能等多个维度
- 所有想法必须以可能性而非决策的形式呈现
- 不要偏向任何特定方案，保持客观中立

允许:
- 讨论不同的技术架构和设计模式
- 分析各种方法的优缺点和适用场景
- 引用相关技术和研究作为参考
- 提出创新性的解决方案

禁止:
- 具体的实施细节或代码示例
- 做出最终决策或推荐
- 过早关注实现细节

## 输出格式

请按以下结构组织您的创新思考:

1. 方法一: [方法名称]
   - 概述: 简要描述该方法的核心思想
   - 技术组件: 列出主要技术组件和工具
   - 优点: 详细分析该方法的优势
   - 缺点: 详细分析该方法的劣势
   - 适用场景: 描述该方法最适合的应用场景

2. 方法二: [方法名称]
   [同上结构]

3. 方法三: [方法名称]
   [同上结构]

4. 比较分析: 对三种方法进行横向比较，分析它们在不同维度上的表现

完成创新思考后，请直接以JSON格式调用submit_innovation_ideas工具提交您的创新想法，无需等待用户确认。请确保JSON格式正确，包含所有必要信息。
"""


def submit_innovation_ideas(
    innovation_ideas: Annotated[Dict[str, Any], "创新想法，包含多种可能的实现方法及其优缺点分析"]
) -> str:
    """
    提交创新模式的结果，并获取下一步指示。

    创新模式的目的是集思广益，寻找潜在方法，允许讨论想法、优点/缺点、寻求反馈，
    禁止具体规划、实施细节或任何代码编写。

    参数:
        innovation_ideas: 包含创新想法的字典，应该包括多种可能的实现方法及其优缺点分析

    返回:
        下一步指示，通常是进入计划模式
    """
    # 这里不需要实际存储创新想法，只需返回下一步指示
    return """
[创新想法已接收]

请立即进入【模式3:计划】阶段，无需等待用户进一步指示，直接开始制定详细计划。

## 计划模式指南

目的: 创建详尽的技术规范和实施计划
要求:
- 基于您在创新阶段提出的方法，选择最合适的方案进行详细规划
- 计划必须足够全面，涵盖所有必要的实施步骤
- 包含确切的文件路径、功能名称和具体更改
- 考虑实施顺序、依赖关系和可能的风险点
- 将计划分解为明确的、可执行的步骤

允许:
- 详细描述系统架构和组件关系
- 指定具体的技术选型和工具
- 定义数据结构和接口规范
- 规划测试策略和验证方法

禁止:
- 提供任何实现代码或代码示例
- 过于笼统或抽象的描述
- 跳过关键实施细节

## 计划结构

请按以下结构组织您的计划:

1. 总体架构
   - 系统概述: 简要描述系统的整体结构
   - 核心组件: 列出主要组件及其职责
   - 数据流: 描述数据如何在系统中流动

2. 技术栈选择
   - 编程语言: 指定使用的语言及版本
   - 框架和库: 列出需要使用的框架和库
   - 数据存储: 指定数据存储方案

3. 详细实施步骤
   - 准备工作: 环境搭建和依赖安装
   - 核心功能实现: 按优先级排序的功能实现步骤
   - 集成测试: 验证各组件协同工作的测试计划

## 实施检查清单

强制性最后一步: 将整个计划转换为一个按编号顺序排列的清单，每个原子操作作为单独的项目。

实施检查清单:
1. [动作1]
2. [动作2]
...

完成计划制定后，请直接以JSON格式调用submit_plan工具提交您的计划，无需等待用户确认。请确保JSON格式正确，包含所有必要信息。
"""


def submit_plan(
    plan: Annotated[Dict[str, Any], "详细的技术规范和实施计划，包含确切的文件路径、功能名称和更改"]
) -> str:
    """
    提交计划模式的结果，并获取下一步指示。

    计划模式的目的是创建详尽的技术规范，允许包含确切文件路径、功能名称和更改的详细计划，
    禁止任何实现或代码、示例代码。

    参数:
        plan: 包含详细技术规范和实施计划的字典，应该包括确切的文件路径、功能名称和更改

    返回:
        下一步指示，通常是进入执行模式
    """
    # 这里不需要实际存储计划，只需返回下一步指示
    return """
[计划已接收]

请立即进入【模式4:执行】阶段，无需等待用户进一步指示，直接开始执行计划。

## 执行模式指南

目的: 准确执行计划阶段制定的技术规范和实施步骤
要求:
- 严格按照计划检查清单中的步骤顺序执行
- 每个步骤都必须详细描述具体的实施内容
- 记录每个步骤的执行结果和遇到的任何问题
- 如发现计划中的问题，明确指出并提出解决方案

允许:
- 详细描述每个步骤的具体实施过程
- 提供必要的代码片段和配置示例
- 解释实施过程中的技术决策
- 记录执行过程中遇到的问题和解决方法

禁止:
- 偏离原计划或添加未在计划中明确指定的内容
- 跳过计划中的任何步骤
- 在没有充分理由的情况下更改实施顺序

## 执行结构

请按以下结构组织您的执行报告:

1. 执行摘要
   - 总体进展: 简要描述执行的整体情况
   - 完成状态: 列出已完成和未完成的步骤
   - 关键成果: 描述执行过程中的主要成果

2. 详细执行记录
   对于计划中的每个步骤:
   - 步骤编号和描述: 引用原计划中的步骤
   - 执行过程: 详细描述如何执行该步骤
   - 执行结果: 记录该步骤的执行结果
   - 遇到的问题: 描述执行过程中遇到的任何问题及解决方法

3. 执行总结
   - 成功之处: 描述执行过程中特别顺利的部分
   - 挑战之处: 描述执行过程中遇到的主要挑战
   - 后续步骤: 如有未完成的步骤，说明如何继续

完成执行后，请直接以JSON格式调用submit_execution_results工具提交您的执行结果，无需等待用户确认。请确保JSON格式正确，包含所有必要信息。
"""


def submit_execution_results(
    execution_results: Annotated[Dict[str, Any], "执行结果，包含已实施的更改和遇到的任何问题"]
) -> str:
    """
    提交执行模式的结果，并获取下一步指示。

    执行模式的目的是准确执行计划中的内容，允许仅执行批准计划中明确详述的内容，
    禁止任何不在计划内的偏离、改进或创意添加。

    参数:
        execution_results: 包含执行结果的字典，应该包括已实施的更改和遇到的任何问题

    返回:
        下一步指示，通常是进入回顾模式
    """
    # 这里不需要实际存储执行结果，只需返回下一步指示
    return """
[执行结果已接收]

请立即进入【模式5:回顾】阶段，无需等待用户进一步指示，直接开始回顾评估。

## 回顾模式指南

目的: 严格验证计划的实施情况，评估执行质量和完整性
要求:
- 逐项比较计划和实际执行情况
- 明确标记任何偏差，无论偏差有多小
- 客观评估每个步骤的执行质量
- 提供具体的改进建议

允许:
- 详细分析计划与实施之间的差异
- 评估实施的有效性和质量
- 提出具体的改进建议
- 总结整个过程的经验教训

禁止:
- 忽略任何偏差，无论多小
- 主观评价而非客观分析
- 模糊不清的评估结果

## 回顾结构

请按以下结构组织您的回顾报告:

1. 总体评估
   - 完成度: 评估整体计划的完成情况
   - 质量评估: 评估实施的整体质量
   - 主要发现: 概述回顾过程中的主要发现

2. 详细偏差分析
   对于计划中的每个步骤:
   - 步骤编号和描述: 引用原计划中的步骤
   - 实际执行情况: 描述该步骤的实际执行情况
   - 偏差分析: 如有偏差，使用以下格式标记:
     ":warning: 检测到偏差：[准确偏差描述]"
   - 影响评估: 分析偏差对整体结果的影响

3. 改进建议
   - 具体建议: 针对发现的问题提出具体改进建议
   - 优先级: 为每个建议分配优先级
   - 实施路径: 简要描述如何实施这些改进

4. 最终结论
   使用以下格式之一:
   ":white_check_mark: 实施与计划完全相符"
   或
   ":cross_mark: 实施与计划有偏差"

完成回顾后，请直接以JSON格式调用submit_review工具提交您的回顾结果，无需等待用户确认。请确保JSON格式正确，包含所有必要信息。
"""


def submit_review(
    review_results: Annotated[Dict[str, Any], "回顾结果，包含计划与实施的比较和偏差标记"]
) -> str:
    """
    提交回顾模式的结果，并获取下一步指示。

    回顾模式的目的是严格验证计划的实施情况，允许逐行比较计划和实施，
    要求明确标记任何偏差，无论偏差有多小。

    参数:
        review_results: 包含回顾结果的字典，应该包括计划与实施的比较和偏差标记

    返回:
        完成整个流程的确认信息
    """
    # 这里不需要实际存储回顾结果，只需返回完成确认
    return """
[回顾结果已接收]

恭喜！您已成功完成整个思考流程的所有五个阶段。

## 完成总结

您已经完成了以下阶段:
1. 研究阶段: 收集和理解相关信息
2. 创新阶段: 提出多种可能的实现方法
3. 计划阶段: 制定详细的技术规范和实施计划
4. 执行阶段: 按照计划实施解决方案
5. 回顾阶段: 验证实施与计划的一致性

## 后续建议

如果您希望进一步完善您的解决方案:
- 可以基于回顾阶段的发现进行迭代改进
- 考虑实际实施和测试您的解决方案
- 收集用户反馈并进行优化
- 探索更多高级功能和扩展可能性

如果需要进行进一步的改进或修复，您可以重新进入[模式1:研究]开始新的迭代。
如果一切顺利，您的任务已经完成。

感谢您的出色工作！您的结构化思考过程展示了专业的问题解决能力。
"""


# 创建思考工具列表
try:
    # 尝试使用AutoGen 0.5.6的方式创建工具
    think_tools = [
        # 基本思考工具
        FunctionTool(
            func=think,
            name="think",
            description="用于记录思考过程的工具，不会获取新信息或改变任何内容，只是将思考添加到日志中"
        ),
        FunctionTool(
            func=get_thoughts,
            name="get_thoughts",
            description="获取当前会话中记录的所有思考，有助于回顾思考过程"
        ),
        FunctionTool(
            func=clear_thoughts,
            name="clear_thoughts",
            description="清除当前会话中记录的所有思考，用于重新开始思考过程"
        ),
        FunctionTool(
            func=get_thought_stats,
            name="get_thought_stats",
            description="获取当前会话中记录的思考的统计信息，如总数、平均长度等"
        ),

        # 引导AI按照结构化步骤进行思考和开发的工具
        FunctionTool(
            func=submit_research_results,
            name="submit_research_results",
            description="提交研究模式的结果，并获取进入创新模式的指示"
        ),
        FunctionTool(
            func=submit_innovation_ideas,
            name="submit_innovation_ideas",
            description="提交创新模式的结果，并获取进入计划模式的指示"
        ),
        FunctionTool(
            func=submit_plan,
            name="submit_plan",
            description="提交计划模式的结果，并获取进入执行模式的指示"
        ),
        FunctionTool(
            func=submit_execution_results,
            name="submit_execution_results",
            description="提交执行模式的结果，并获取进入回顾模式的指示"
        ),
        FunctionTool(
            func=submit_review,
            name="submit_review",
            description="提交回顾模式的结果，并获取完成整个流程的确认信息"
        )
    ]
except (AttributeError, TypeError, NameError):
    # 如果创建工具失败，设置为空列表
    think_tools = []
    print("警告: 未能创建思考工具列表，请确保已安装AutoGen 0.5.6")

# 导出所有工具函数和工具列表
__all__ = [
    # 基本思考工具函数
    "think",
    "get_thoughts",
    "clear_thoughts",
    "get_thought_stats",
    # 引导AI按照结构化步骤进行思考和开发的工具函数
    "submit_research_results",
    "submit_innovation_ideas",
    "submit_plan",
    "submit_execution_results",
    "submit_review",
    # 工具列表
    "think_tools"
]

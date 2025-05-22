#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自定义消息类型 - 用于处理工具调用消息

这个模块提供了自定义的消息类型，用于在AutoGen群聊中处理工具调用。
主要功能是在消息传递过程中自动处理工具调用，而不是等到对话结束后再处理。

主要组件:
1. ToolCallMessage - 工具调用消息类型，继承自TextMessage
2. ToolCallProcessor - 工具调用处理器，用于处理工具调用并返回结果
"""

from typing import Optional, Dict, Sequence, Union

from autogen_agentchat.messages import TextMessage, BaseChatMessage
from autogen_core import CancellationToken
from autogen_core.tools import StaticWorkbench

# 注意：process_and_execute_tool_calls 会在需要时动态导入
# 这样可以避免循环导入问题

# 使用全局字典存储消息数据
_message_data = {}
# 消息计数器，用于生成唯一ID
_message_counter = 0

class ToolCallMessage(TextMessage):
    """
    工具调用消息类型，继承自TextMessage

    这个消息类型会在to_text()方法中自动处理工具调用，
    确保工具调用在消息传递过程中被处理，而不是等到对话结束后再处理。
    """

    def __init__(
        self,
        source: str,
        content: str,
        metadata: Optional[Dict[str, str]] = None,
        workbench: Optional[StaticWorkbench] = None,
        cancellation_token: Optional[CancellationToken] = None,
        processed: bool = False
    ):
        """
        初始化工具调用消息

        Args:
            source: 消息来源
            content: 消息内容
            metadata: 元数据
            workbench: 工具工作台
            cancellation_token: 取消令牌
            processed: 是否已处理
        """
        # 初始化元数据
        metadata = metadata or {}

        # 处理状态添加到元数据中，必须是字符串
        metadata["processed"] = str(processed).lower()

        # 调用父类初始化方法
        super().__init__(source=source, content=content, metadata=metadata)

        # 生成唯一ID
        global _message_counter
        self._message_id = f"msg_{_message_counter}"
        _message_counter += 1

        # 在全局字典中存储工作台和取消令牌
        _message_data[self._message_id] = {
            "workbench": workbench,
            "cancellation_token": cancellation_token,
            "processed": processed
        }

    def get_data(self):
        """获取消息关联的数据"""
        return _message_data.get(self._message_id, {})

    @property
    def workbench(self) -> Optional[StaticWorkbench]:
        """获取工作台"""
        return self.get_data().get("workbench")

    @property
    def cancellation_token(self) -> Optional[CancellationToken]:
        """获取取消令牌"""
        return self.get_data().get("cancellation_token")

    @property
    def processed(self) -> bool:
        """获取处理状态"""
        return self.get_data().get("processed", False)

    @processed.setter
    def processed(self, value: bool):
        """设置处理状态"""
        if self._message_id in _message_data:
            _message_data[self._message_id]["processed"] = value
        # 同时更新元数据中的字符串表示
        self.metadata["processed"] = str(value).lower()

    async def process_tool_calls(self) -> str:
        """
        处理消息中的工具调用

        Returns:
            处理后的消息内容
        """
        if self.processed or not self.workbench:
            print(f"[调试] {self.source} 的消息已处理或没有工作台，跳过处理")
            return self.content

        # 简化检测逻辑，只检查内容中是否包含"tool_calls"关键字
        if "tool_calls" not in self.content:
            print(f"[调试] {self.source} 的消息不包含工具调用，跳过处理")
            return self.content

        # 直接使用process_and_execute_tool_calls函数处理工具调用
        print(f"[系统] 处理 {self.source} 的工具调用: {self.content[:200]}...")
        try:
            # 导入process_and_execute_tool_calls函数
            from utils.json_parser import process_and_execute_tool_calls

            # 调用函数处理工具调用
            print(f"[调试] 开始调用process_and_execute_tool_calls函数")
            processed_content, success, error_message = await process_and_execute_tool_calls(
                content=self.content,
                workbench=self.workbench,
                agent_name=self.source,
                cancellation_token=self.cancellation_token
            )
            print(f"[调试] process_and_execute_tool_calls函数调用完成，成功: {success}")

            if success:
                print(f"[系统] 成功处理 {self.source} 的工具调用，处理结果: {processed_content[:200]}...")

                # 检查处理后的内容是否仍然包含工具调用
                if "tool_calls" in processed_content:
                    print(f"[警告] 处理后的内容仍然包含工具调用，尝试递归处理")
                    # 递归处理
                    recursive_processed_content, recursive_success, recursive_error = await process_and_execute_tool_calls(
                        content=processed_content,
                        workbench=self.workbench,
                        agent_name=self.source,
                        cancellation_token=self.cancellation_token
                    )

                    if recursive_success:
                        processed_content = recursive_processed_content
                        print(f"[系统] 递归处理成功，最终结果: {processed_content[:200]}...")
                    else:
                        print(f"[警告] 递归处理失败: {recursive_error}")

                return processed_content
            else:
                print(f"[错误] 处理工具调用失败: {error_message}")
                return self.content
        except Exception as e:
            import traceback
            print(f"[错误] 处理工具调用时出错: {e}")
            print(f"[错误] 详细错误信息: {traceback.format_exc()}")
            return self.content

    async def to_text(self) -> str:
        """
        将消息转换为文本

        如果消息包含工具调用，会先处理工具调用，然后返回处理后的内容

        Returns:
            处理后的消息内容
        """
        if not self.processed and self.workbench:
            processed_content = await self.process_tool_calls()
            # 标记为已处理
            self.processed = True
            return processed_content
        return self.content

    def to_model_text(self) -> str:
        """
        将消息转换为模型文本

        Returns:
            消息内容
        """
        return self.content

    @classmethod
    def from_text_message(cls, message: TextMessage, workbench: StaticWorkbench, cancellation_token: CancellationToken) -> 'ToolCallMessage':
        """
        从TextMessage创建ToolCallMessage

        Args:
            message: TextMessage实例
            workbench: 工具工作台
            cancellation_token: 取消令牌

        Returns:
            ToolCallMessage实例
        """
        # 创建一个新的ToolCallMessage实例
        return cls(
            source=message.source,
            content=message.content,
            metadata=message.metadata,
            workbench=workbench,
            cancellation_token=cancellation_token,
            processed=False
        )


class ToolCallMessageProcessor:
    """
    工具调用消息处理器

    用于将普通TextMessage转换为ToolCallMessage，并处理工具调用
    """

    def __init__(self, workbench: StaticWorkbench, cancellation_token: CancellationToken):
        """
        初始化工具调用消息处理器

        Args:
            workbench: 工具工作台
            cancellation_token: 取消令牌
        """
        self.workbench = workbench
        self.cancellation_token = cancellation_token

    async def process_message(self, message: BaseChatMessage) -> BaseChatMessage:
        """
        处理消息

        如果消息是TextMessage，会将其转换为ToolCallMessage，并处理工具调用

        Args:
            message: 消息实例

        Returns:
            处理后的消息实例
        """
        if isinstance(message, TextMessage) and not isinstance(message, ToolCallMessage):
            # 检查消息内容是否包含工具调用
            if "tool_calls" in message.content:
                # 创建ToolCallMessage
                tool_call_message = ToolCallMessage.from_text_message(
                    message=message,
                    workbench=self.workbench,
                    cancellation_token=self.cancellation_token
                )

                # 处理工具调用
                processed_content = await tool_call_message.process_tool_calls()

                # 如果内容有变化，返回处理后的消息
                if processed_content != message.content:
                    return ToolCallMessage(
                        source=message.source,
                        content=processed_content,
                        metadata=message.metadata,
                        workbench=self.workbench,
                        cancellation_token=self.cancellation_token,
                        processed=True
                    )

        return message

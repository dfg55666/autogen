#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
示例脚本：展示如何导入update_gemini_page模块并使用其功能
"""

import asyncio
from update_gemini_page import update_page, update_pages_batch

async def process_single_page():
    """处理单个页面示例"""
    print("开始处理单个页面（verbose=False）...")

    # 注意：设置verbose=False，这样模块不会输出任何消息
    result = await update_page('addgemini024', message='Hello from example_import.py', verbose=False)

    if result:
        print("\n处理成功！")
        print(f"模型: {result.get('model')}")
        print(f"回复URL: {result.get('message', {}).get('content')}")
    else:
        print("\n处理失败！")

async def process_multiple_pages():
    """批量处理多个页面示例"""
    print("\n开始批量处理多个页面（verbose=False）...")

    # 注意：设置verbose=False，这样模块不会输出任何消息
    results = await update_pages_batch(
        ['addgemini024', 'addgemini025'],
        message='Hello from batch processing',
        verbose=False
    )

    print("\n批处理结果:")
    for page_id, result in results.items():
        if result:
            print(f"页面 {page_id}: 成功")
            print(f"  回复URL: {result.get('message', {}).get('content')}")
        else:
            print(f"页面 {page_id}: 失败")

async def direct_chat_request():
    """直接发送聊天请求示例（使用内置重试机制）"""
    print("\n直接发送聊天请求示例...")

    # 使用一个新的页面ID，避免与之前的请求冲突
    page_id = 'addgemini026'  # 使用一个新的页面ID

    # 直接使用update_page函数发送聊天请求
    print(f"使用update_page函数发送聊天请求到页面 {page_id}...")
    result = await update_page(
        page_id,
        message='Hello direct chat',
        verbose=True  # 启用日志，查看详细信息
    )

    if result:
        print("\n聊天请求成功！")
        print(f"模型: {result.get('model')}")
        print(f"回复URL: {result.get('message', {}).get('content')}")
    else:
        print("\n聊天请求失败！")

async def main():
    """主函数"""
    # 处理单个页面
    await process_single_page()

    # 批量处理多个页面
    await process_multiple_pages()

    # 直接发送聊天请求
    await direct_chat_request()

if __name__ == "__main__":
    asyncio.run(main())

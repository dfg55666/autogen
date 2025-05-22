#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
页面更新和聊天模块 (同步版本)

这个模块提供了更新页面URL、重置计数器和缓存，以及发送聊天请求的功能。
可以作为命令行工具使用，也可以作为Python模块导入。
按顺序处理页面，一次处理一个页面。

特性:
1. 自动检测页面是否存在，如果不存在则自动创建
2. 根据页面ID前缀自动选择合适的URL:
   - addgemini开头的页面: https://gemini.google.com/app
   - addaistudio开头的页面: https://aistudio.google.com/prompts/new_chat
3. 支持批量处理多个页面（按顺序处理）
4. 支持重置计数器和缓存
5. 智能处理页面ID:
   - 首先检查原始ID是否存在，若存在则先关闭，然后更改ID为带add前缀的形式
   - 接收到不带"add"前缀的页面ID (如gemini002)，会在内部处理时临时添加前缀，完成后恢复原ID
   - 所有页面在ID更新后会自动重新启动，保持活跃状态
6. 简化的页面状态检测:
   - 启动页面前先检查页面状态
   - 如果页面状态不是"Open"，等待10秒后再检查
   - 如果依然不是"Open"状态，则先关闭再启动页面
7. 增强的网络稳定性:
   - 不使用代理，避免代理导致的连接问题
   - 请求超时设置，防止长时间等待
   - 内置自动重试机制，最多重试5次
   - 适当的页面加载等待时间(5秒)，确保页面完全加载
   - 自动检查AI回复是否包含URL，如果不包含则重试发送hello消息
   - 所有函数都默认包含重试机制，无需额外调用

作为命令行工具使用:
    python update_gemini_page.py <page_id> [--url URL] [--message MESSAGE] [--no-reset-counts] [--no-reset-cache]
    python update_gemini_page.py --batch page_id1 page_id2 page_id3 [--url URL] [--message MESSAGE]

作为模块导入:
    from update_gemini_page import update_page, update_pages_batch

    # 处理单个页面（不输出日志）- 推荐使用不带add前缀的ID
    result = update_page('gemini001', message='hello', verbose=False)

    # 批量处理多个页面（不输出日志）- 推荐使用不带add前缀的ID
    results = update_pages_batch(['gemini001', 'gemini002', 'aistudio003'], verbose=False)

    # 直接使用聊天请求函数（已内置重试机制）
    from update_gemini_page import send_chat_request

    # 所有函数都支持verbose参数，当作为模块导入时建议设置为False
    # 这样不会在控制台输出大量日志，让调用者自行决定如何处理结果

    # 所有函数都默认检查回复是否包含URL，可以通过check_url=False禁用此功能
"""

import requests
import argparse
import re
import time
from typing import Dict, List, Optional, Any, Tuple

# 配置参数
BASE_URL = "http://localhost:11434"
DEFAULT_URL = "https://gemini.google.com/app"
DEFAULT_MESSAGE = "hello"

# 页面类型对应的URL
PAGE_TYPE_URLS = {
    "addgemini": "https://gemini.google.com/app",
    "addaistudio": "https://aistudio.google.com/prompts/new_chat"
}

def set_base_url(url: str) -> None:
    """
    设置API基础URL

    参数:
        url (str): 新的基础URL
    """
    global BASE_URL
    BASE_URL = url

def check_page_exists(session: requests.Session, page_id: str, verbose: bool = True) -> bool:
    """
    检查页面是否存在

    参数:
        session (requests.Session): HTTP会话
        page_id (str): 页面ID
        verbose (bool): 是否输出详细日志，默认为True

    返回:
        bool: 页面是否存在
    """
    url = f"{BASE_URL}/control/pages/{page_id}/stop"
    try:
        response = session.post(url)
        if response.status_code == 404:
            if verbose:
                print(f"页面 {page_id} 不存在")
            return False
        return True
    except Exception as e:
        if verbose:
            print(f"检查页面是否存在时发生错误: {e}")
        return False

def get_accounts(session: requests.Session, verbose: bool = True) -> List[Dict[str, Any]]:
    """
    获取所有账号列表

    参数:
        session (requests.Session): HTTP会话
        verbose (bool): 是否输出详细日志，默认为True

    返回:
        List[Dict[str, Any]]: 账号列表
    """
    url = f"{BASE_URL}/control/accounts"
    try:
        response = session.get(url)
        response.raise_for_status()
        accounts = response.json()
        return accounts
    except Exception as e:
        if verbose:
            print(f"获取账号列表失败: {e}")
        return []

def create_page(session: requests.Session, account_id: str, page_id: str, url: str, verbose: bool = True) -> bool:
    """
    创建新页面

    参数:
        session (requests.Session): HTTP会话
        account_id (str): 账号ID
        page_id (str): 页面ID
        url (str): 页面URL
        verbose (bool): 是否输出详细日志，默认为True

    返回:
        bool: 创建是否成功
    """
    api_url = f"{BASE_URL}/control/accounts/{account_id}/pages"
    payload = {
        "url": url,
        "notes": f"自动创建的页面 {page_id}",
        "launch_mode": "default",
        "page_id": page_id
    }

    try:
        response = session.post(api_url, json=payload)
        response.raise_for_status()
        result = response.json()
        if verbose:
            print(f"成功创建页面: {result.get('id')}")
        return True
    except requests.exceptions.HTTPError as e:
        if verbose:
            print(f"创建页面失败: {e}")
            if e.response.status_code == 400:
                response_text = e.response.text
                print(f"错误详情: {response_text}")
        return False
    except Exception as e:
        if verbose:
            print(f"创建页面时发生错误: {e}")
        return False

def stop_page(session: requests.Session, page_id: str, verbose: bool = True) -> bool:
    """
    关闭指定ID的页面

    参数:
        session (requests.Session): HTTP会话
        page_id (str): 页面ID
        verbose (bool): 是否输出详细日志，默认为True

    返回:
        bool: 操作是否成功
    """
    url = f"{BASE_URL}/control/pages/{page_id}/stop"
    try:
        response = session.post(url)
        response.raise_for_status()
        if verbose:
            print(f"页面 {page_id} 已关闭")
        # 等待页面完全关闭
        time.sleep(2)
        return True
    except requests.exceptions.HTTPError as e:
        if verbose:
            print(f"关闭页面失败: {e}")
            if e.response.status_code == 404:
                print(f"页面 {page_id} 不存在或已经关闭")
        if e.response.status_code == 404:
            return True
        return False
    except Exception as e:
        if verbose:
            print(f"关闭页面时发生错误: {e}")
        return False

def update_page_url(session: requests.Session, page_id: str, new_url: str,
                  reset_counts: bool = True, reset_cache: bool = True, verbose: bool = True) -> bool:
    """
    更新页面URL和重置计数器/缓存

    参数:
        session (requests.Session): HTTP会话
        page_id (str): 页面ID
        new_url (str): 新的URL地址
        reset_counts (bool, optional): 是否重置计数器，默认为True
        reset_cache (bool, optional): 是否重置缓存，默认为True
        verbose (bool): 是否输出详细日志，默认为True

    返回:
        bool: 操作是否成功
    """
    url = f"{BASE_URL}/control/pages/{page_id}"
    payload = {
        "url": new_url,
        # 始终添加重置计数器和缓存的字段，明确指定其值
        "reset_counts": reset_counts,
        "reset_cache": reset_cache
    }

    try:
        response = session.patch(url, json=payload)
        response.raise_for_status()
        if verbose:
            print(f"页面 {page_id} URL已更新为: {new_url}")
            print(f"页面 {page_id} 的计数器重置: {'是' if reset_counts else '否'}")
            print(f"页面 {page_id} 的缓存重置: {'是' if reset_cache else '否'}")
        return True
    except requests.exceptions.HTTPError as e:
        if verbose:
            print(f"更新页面URL失败: {e}")
            if e.response.status_code == 400:
                response_text = e.response.text
                print(f"错误详情: {response_text}")
        return False
    except Exception as e:
        if verbose:
            print(f"更新页面URL时发生错误: {e}")
        return False

def update_page_id(session: requests.Session, old_page_id: str, new_page_id: str, verbose: bool = True) -> bool:
    """
    更新页面ID

    参数:
        session (requests.Session): HTTP会话
        old_page_id (str): 旧页面ID
        new_page_id (str): 新页面ID
        verbose (bool): 是否输出详细日志，默认为True

    返回:
        bool: 操作是否成功
    """
    # 检查是否需要更新
    if old_page_id == new_page_id:
        if verbose:
            print(f"页面ID '{old_page_id}' 无需更新")
        return True

    url = f"{BASE_URL}/control/pages/{old_page_id}"
    payload = {
        "new_page_id": new_page_id
    }

    try:
        # 尝试使用PATCH方法更新页面ID
        try:
            response = session.patch(url, json=payload)
            if response.status_code == 200:
                if verbose:
                    print(f"页面ID已更新: '{old_page_id}' -> '{new_page_id}'")
                return True
            else:
                # 如果PATCH方法失败，记录错误但不抛出异常
                if verbose:
                    print(f"使用PATCH方法更新页面ID失败，状态码: {response.status_code}")
                    try:
                        error_text = response.text
                        print(f"错误详情: {error_text}")
                    except:
                        pass
        except Exception as e:
            if verbose:
                print(f"PATCH请求失败: {e}")

        # 如果PATCH方法失败，尝试使用替代方法：删除旧页面并创建新页面
        if verbose:
            print(f"尝试使用替代方法更新页面ID: 删除并重新创建页面")

        # 获取旧页面的信息
        old_page_info = None
        try:
            response = session.get(f"{BASE_URL}/control/pages/{old_page_id}")
            if response.status_code == 200:
                old_page_info = response.json()
                if verbose:
                    print(f"成功获取页面 {old_page_id} 的信息")
            else:
                if verbose:
                    print(f"获取页面信息失败，状态码: {response.status_code}")
                return False
        except Exception as e:
            if verbose:
                print(f"获取页面信息时出错: {e}")
            return False

        if not old_page_info:
            if verbose:
                print(f"无法获取页面 {old_page_id} 的信息，无法继续")
            return False

        # 获取账号ID
        account_id = old_page_info.get("account_id")
        if not account_id:
            if verbose:
                print(f"无法获取页面 {old_page_id} 的账号ID，无法继续")
            return False

        # 删除旧页面
        try:
            response = session.delete(f"{BASE_URL}/control/pages/{old_page_id}")
            if response.status_code not in (200, 204):
                if verbose:
                    print(f"删除页面 {old_page_id} 失败，状态码: {response.status_code}")
                return False
            if verbose:
                print(f"成功删除页面 {old_page_id}")
        except Exception as e:
            if verbose:
                print(f"删除页面时出错: {e}")
            return False

        # 创建新页面
        create_payload = {
            "url": old_page_info.get("url", "https://gemini.google.com/app"),
            "notes": old_page_info.get("notes", f"从 {old_page_id} 迁移的页面"),
            "launch_mode": old_page_info.get("launch_mode", "default"),
            "page_id": new_page_id
        }

        try:
            response = session.post(f"{BASE_URL}/control/accounts/{account_id}/pages", json=create_payload)
            if response.status_code != 200:
                if verbose:
                    print(f"创建新页面 {new_page_id} 失败，状态码: {response.status_code}")
                return False
            if verbose:
                print(f"成功创建新页面 {new_page_id}")
            return True
        except Exception as e:
            if verbose:
                print(f"创建新页面时出错: {e}")
            return False

        return False
    except Exception as e:
        if verbose:
            print(f"更新页面ID时发生错误: {e}")
        return False

def start_page(session: requests.Session, page_id: str, wait_time: int = 5, verbose: bool = True) -> bool:
    """
    启动指定ID的页面，极简版本

    参数:
        session (requests.Session): HTTP会话
        page_id (str): 页面ID
        wait_time (int): 等待页面加载的时间（秒），默认5秒
        verbose (bool): 是否输出详细日志，默认为True

    返回:
        bool: 操作是否成功
    """
    # 首先检查页面状态
    status = check_page_status(session, page_id, verbose)

    # 如果页面状态已经是"Open"或"Running"，则无需启动
    if status in ["Open", "Running"]:
        if verbose:
            print(f"页面 {page_id} 已经处于打开状态 ({status})，无需启动")
        return True

    # 启动页面
    url = f"{BASE_URL}/control/pages/{page_id}/start"
    try:
        response = session.post(url)
        if verbose:
            print(f"页面 {page_id} 启动请求已发送")

        # 等待页面启动，最多等待wait_time秒
        start_time = time.time()
        while time.time() - start_time < wait_time:
            # 检查页面状态
            new_status = check_page_status(session, page_id, verbose=False)
            if new_status in ["Open", "Running"]:
                if verbose:
                    print(f"页面 {page_id} 已成功启动，当前状态: {new_status}")
                return True

            # 等待0.5秒后再次检查
            time.sleep(0.5)

        # 如果等待超时，再次检查状态
        final_status = check_page_status(session, page_id, verbose)
        if final_status in ["Open", "Running"]:
            if verbose:
                print(f"页面 {page_id} 已成功启动，当前状态: {final_status}")
            return True
        else:
            if verbose:
                print(f"页面 {page_id} 启动超时，当前状态: {final_status}")
            return False
    except Exception as e:
        if verbose:
            print(f"启动页面时发生错误: {e}")
        return False

def check_page_status(session: requests.Session, page_id: str, verbose: bool = True) -> str:
    """
    检查页面状态，使用正确的API端点获取状态

    参数:
        session (requests.Session): HTTP会话
        page_id (str): 页面ID
        verbose (bool): 是否输出详细日志，默认为True

    返回:
        str: 页面状态，如果获取失败则返回None
    """
    # 使用正确的API端点获取页面信息
    url = f"{BASE_URL}/control/pages/{page_id}"
    try:
        response = session.get(url)
        if response.status_code == 200:
            page_info = response.json()
            status = page_info.get("status")
            if verbose:
                print(f"页面 {page_id} 当前状态: {status}")
            return status
        else:
            if verbose:
                print(f"获取页面状态失败，状态码: {response.status_code}")
            return None
    except Exception as e:
        if verbose:
            print(f"检查页面状态时发生错误: {e}")
        return None

def send_chat_request(session: requests.Session, page_id: str, message: str,
                   max_retries: int = 5, retry_delay: float = 2.0,
                   timeout: int = 60, check_url: bool = True,
                   verbose: bool = True) -> Tuple[Optional[Dict[str, Any]], bool]:
    """
    使用Ollama格式发送聊天请求（带重试机制），简化版本
    在发送消息前先检查页面状态，如果不是open状态，等待10秒后再检查
    如果依然不是open状态，则先关闭再启动页面

    参数:
        session (requests.Session): HTTP会话
        page_id (str): 页面ID
        message (str): 聊天消息内容
        max_retries (int): 最大重试次数，默认5次
        retry_delay (float): 重试间隔时间（秒），默认2秒
        timeout (int): 请求超时时间（秒），默认60秒
        check_url (bool): 是否检查回复中是否包含URL，默认True
        verbose (bool): 是否输出详细日志，默认为True

    返回:
        Tuple[Optional[Dict[str, Any]], bool]:
            - 聊天响应结果，如果失败则返回None
            - 布尔值，表示是否成功检测到HTTP链接
    """
    # 首先检查页面状态
    status = check_page_status(session, page_id, verbose)

    # 如果页面状态不是"Open"，等待10秒后再检查
    if status != "Open":
        if verbose:
            print(f"页面 {page_id} 当前状态为 {status}，等待10秒后再检查...")
        time.sleep(10)
        status = check_page_status(session, page_id, verbose)

        # 如果依然不是"Open"状态，则先关闭再启动页面
        if status != "Open":
            if verbose:
                print(f"页面 {page_id} 状态仍为 {status}，尝试重启...")

            # 关闭页面
            stop_page(session, page_id, verbose)

            # 启动页面
            start_page(session, page_id, verbose=verbose)

            # 再次检查状态
            status = check_page_status(session, page_id, verbose)
            if status != "Open":
                if verbose:
                    print(f"页面 {page_id} 重启后状态仍为 {status}，发送消息可能会失败")

    url = f"{BASE_URL}/api/chat"
    payload = {
        "model": page_id,
        "messages": [
            {
                "role": "user",
                "content": message
            }
        ]
    }
    headers = {"Content-Type": "application/json"}

    # 是否检测到HTTP链接的标志
    http_detected = False

    # 重试循环
    for attempt in range(max_retries):
        try:
            if verbose:
                print(f"发送聊天请求到页面 {page_id}: {message}")
                if attempt > 0:
                    print(f"尝试 {attempt+1}/{max_retries}")

            # 发送请求
            response = session.post(url, json=payload, headers=headers, timeout=timeout)
            response.raise_for_status()
            result = response.json()

            # 检查是否收到回复
            if result:
                # 如果需要检查URL
                if check_url:
                    # 获取回复内容
                    reply_content = result.get('message', {}).get('content', '')

                    # 检查回复是否包含URL（简单检查是否包含http）
                    if 'http' in reply_content.lower():
                        http_detected = True
                        if verbose:
                            print(f"\n--- 聊天响应 (页面 {page_id}) ---")
                            print(f"模型: {result.get('model')}")
                            print(f"回复: {reply_content}")
                            print(f"HTTP链接检测: 成功")
                        return result, http_detected
                    else:
                        if verbose:
                            print(f"回复不包含URL: {reply_content}")
                            print(f"等待 {retry_delay} 秒后重试发送hello...")
                        # 不包含URL，等待后重试
                        time.sleep(retry_delay)
                        continue
                else:
                    # 不需要检查URL，直接返回结果
                    if verbose:
                        print(f"\n--- 聊天响应 (页面 {page_id}) ---")
                        print(f"模型: {result.get('model')}")
                        print(f"回复: {result.get('message', {}).get('content')}")
                    return result, True  # 不检查URL时默认为成功

            # 如果返回空结果，重试
            if verbose:
                print(f"请求返回空结果")

        except requests.exceptions.HTTPError as e:
            if verbose:
                print(f"发送聊天请求失败: {e}")
                if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                    print(f"HTTP状态码: {e.response.status_code}")
        except Exception as e:
            if verbose:
                print(f"发送聊天请求时发生错误: {e}")
                print(f"错误类型: {type(e).__name__}")

        # 如果不是最后一次尝试，等待后重试
        if attempt < max_retries - 1:
            if verbose:
                print(f"等待 {retry_delay} 秒后重试...")
            time.sleep(retry_delay)
        else:
            if verbose:
                print(f"已达到最大重试次数 ({max_retries})，放弃请求")
                if check_url:
                    print(f"HTTP链接检测: 失败")

    # 所有尝试都失败
    return None, http_detected

# 移除了添加和检查"add"前缀的函数，直接使用原始页面ID

def get_page_type_url(page_id: str) -> str:
    """
    根据页面ID获取对应的URL

    参数:
        page_id (str): 页面ID

    返回:
        str: 对应的URL
    """
    # 使用正则表达式提取前缀部分（字母部分）
    match = re.match(r'^([a-zA-Z]+)\d+$', page_id)
    if match:
        prefix = match.group(1).lower()
        # 检查前缀是否为gemini或aistudio
        if prefix == "gemini":
            return PAGE_TYPE_URLS["addgemini"]
        elif prefix == "aistudio":
            return PAGE_TYPE_URLS["addaistudio"]

    # 默认返回gemini的URL
    return DEFAULT_URL

def ensure_page_exists(session: requests.Session, page_id: str, verbose: bool = True) -> bool:
    """
    确保页面存在，如果不存在则创建

    简化逻辑：
    1. 检查页面ID是否存在
    2. 如果不存在，则创建新页面

    参数:
        session (requests.Session): HTTP会话
        page_id (str): 页面ID
        verbose (bool): 是否输出详细日志，默认为True

    返回:
        bool: 页面是否存在或创建成功
    """
    # 检查当前页面ID是否存在
    if check_page_exists(session, page_id, verbose):
        if verbose:
            print(f"页面 {page_id} 已存在")
        return True

    # 页面不存在，需要创建
    if verbose:
        print(f"页面 {page_id} 不存在，尝试创建...")

    # 获取账号列表
    accounts = get_accounts(session, verbose)
    if not accounts:
        if verbose:
            print("获取账号列表失败，无法创建页面")
        return False

    # 找到一个可用的账号（优先选择Running状态的）
    running_accounts = [acc for acc in accounts if acc.get("status") == "Running"]
    if running_accounts:
        account = running_accounts[0]
    else:
        # 如果没有Running状态的账号，使用第一个账号
        account = accounts[0]

    account_id = account.get("id")
    if verbose:
        print(f"使用账号 {account.get('account_alias')} (ID: {account_id}) 创建页面")

    # 根据页面ID确定URL
    url = get_page_type_url(page_id)

    # 创建页面
    return create_page(session, account_id, page_id, url, verbose)

def update_page(page_id: str, new_url: Optional[str] = None, message: Optional[str] = None,
             reset_counts: bool = True, reset_cache: bool = True,
             verbose: bool = True, check_url: bool = False) -> Tuple[Optional[Dict[str, Any]], bool, str]:
    """
    更新页面URL并发送聊天请求的主函数

    简化逻辑：
    1. 直接使用原始页面ID进行处理
    2. 检查页面是否存在，不存在则创建
    3. 关闭页面并更新URL为https://gemini.google.com/app
    4. 启动页面并发送hello消息
    5. 检测页面链接变化

    参数:
        page_id (str): 页面ID
        new_url (Optional[str]): 新的URL地址，默认为None，使用DEFAULT_URL
        message (Optional[str]): 聊天消息内容，默认为None，使用DEFAULT_MESSAGE
        reset_counts (bool): 是否重置计数器，默认为True
        reset_cache (bool): 是否重置缓存，默认为True
        verbose (bool): 是否输出详细日志，默认为True，作为模块导入时建议设为False
        check_url (bool): 是否检查回复中是否包含URL，默认为True

    返回:
        Tuple[Optional[Dict[str, Any]], bool, str]:
            - 聊天响应结果，如果失败则返回None
            - 布尔值，表示是否成功检测到HTTP链接
            - 字符串，最终使用的页面ID
    """
    # 如果没有指定URL，使用默认URL
    if new_url is None:
        new_url = get_page_type_url(page_id)

    if message is None:
        message = DEFAULT_MESSAGE

    if verbose:
        print(f"开始处理页面 {page_id}")
        print(f"重置计数器: {'是' if reset_counts else '否'}")
        print(f"重置缓存: {'是' if reset_cache else '否'}")

    with requests.Session() as session:
        # 确保页面存在，不存在则创建
        if not ensure_page_exists(session, page_id, verbose=verbose):
            if verbose:
                print(f"页面 {page_id} 不存在且无法创建，退出处理")
            return None, False, page_id

        # 步骤1: 关闭页面
        if not stop_page(session, page_id, verbose=verbose):
            if verbose:
                print(f"页面 {page_id} 无法关闭，退出处理")
            return None, False, page_id

        # 步骤2: 更新URL并重置计数器和缓存
        if not update_page_url(session, page_id, new_url, reset_counts=reset_counts, reset_cache=reset_cache, verbose=verbose):
            if verbose:
                print(f"页面 {page_id} 无法更新URL，退出处理")
            return None, False, page_id

        # 步骤3: 启动页面
        if not start_page(session, page_id, verbose=verbose):
            if verbose:
                print(f"页面 {page_id} 无法启动，退出处理")
            return None, False, page_id

        # 步骤4: 发送聊天请求（带重试机制，检查回复是否包含URL）
        result, http_detected = send_chat_request(
            session, page_id, message,
            max_retries=5, retry_delay=2.0, timeout=90,
            check_url=check_url, verbose=verbose
        )

        # 获取当前URL（可能已经变化）
        current_url = None
        try:
            response = session.get(f"{BASE_URL}/control/pages/{page_id}")
            if response.status_code == 200:
                page_info = response.json()
                current_url = page_info.get("url")
                if verbose:
                    print(f"获取到页面 {page_id} 的当前URL: {current_url}")
            else:
                if verbose:
                    print(f"获取页面信息失败，状态码: {response.status_code}")
                current_url = get_page_type_url(page_id)
                if verbose:
                    print(f"使用默认URL: {current_url}")
        except Exception as e:
            if verbose:
                print(f"获取页面信息时出错: {e}")
            current_url = get_page_type_url(page_id)
            if verbose:
                print(f"使用默认URL: {current_url}")

        # 输出成功标识
        if verbose and http_detected:
            print(f"✅ 页面 {page_id} 成功检测到HTTP链接")
        elif verbose and not http_detected:
            print(f"❌ 页面 {page_id} 未检测到HTTP链接")

        return result, http_detected, page_id

def update_pages_batch(page_ids: List[str], new_url: Optional[str] = None,
                    message: Optional[str] = None, reset_counts: bool = True,
                    reset_cache: bool = True, verbose: bool = True) -> Tuple[Dict[str, Any], bool]:
    """
    批量更新多个页面并发送聊天请求（按顺序处理）
    当最后一个模型返回URL后，等待一秒开始轮询检查页面状态，直到页面状态为open才返回成功

    参数:
        page_ids (List[str]): 页面ID列表
        new_url (Optional[str]): 新的URL地址，默认为None，使用DEFAULT_URL
        message (Optional[str]): 聊天消息内容，默认为None，使用DEFAULT_MESSAGE
        reset_counts (bool): 是否重置计数器，默认为True
        reset_cache (bool): 是否重置缓存，默认为True
        verbose (bool): 是否输出详细日志，默认为True，作为模块导入时建议设为False

    返回:
        Tuple[Dict[str, Any], bool]:
            - 字典，每个页面ID对应的处理结果，包含响应内容、HTTP检测状态和最终页面ID
            - 布尔值，表示所有页面是否都成功检测到HTTP链接
    """
    # 检查是否所有页面都成功检测到HTTP链接
    all_http_detected = True
    detailed_results = {}

    if verbose:
        print(f"\n=== 开始按顺序处理 {len(page_ids)} 个页面 ===")

    # 按顺序处理每个页面
    for page_id in page_ids:
        if verbose:
            print(f"\n--- 处理页面 {page_id} ---")

        try:
            # 处理单个页面
            result, http_detected, final_page_id = update_page(
                page_id,
                new_url=new_url,
                message=message,
                reset_counts=reset_counts,
                reset_cache=reset_cache,
                verbose=verbose
            )

            # 记录结果
            if verbose:
                status = "成功" if result is not None else "失败"
                http_status = "✅ 检测到HTTP链接" if http_detected else "❌ 未检测到HTTP链接"
                print(f"页面 {final_page_id}: {status} - {http_status}")

            # 更新全局HTTP检测状态
            if not http_detected:
                all_http_detected = False

            detailed_results[page_id] = {
                "response": result,
                "http_detected": http_detected,
                "final_page_id": final_page_id
            }

        except Exception as e:
            if verbose:
                print(f"页面 {page_id}: 处理失败 - {str(e)}")
            all_http_detected = False
            detailed_results[page_id] = {
                "response": None,
                "http_detected": False,
                "final_page_id": page_id,
                "error": str(e)
            }

    # 在所有页面处理完成后，等待1秒，然后开始轮询检查所有页面状态
    if verbose:
        print("\n=== 所有页面初始化完成，等待1秒后开始检查页面状态 ===")
    time.sleep(1)

    # 创建会话用于检查页面状态
    with requests.Session() as session:
        # 检查所有页面的状态，直到全部为Open
        max_check_attempts = 30  # 最多检查30次
        check_interval = 2  # 每次检查间隔2秒

        for attempt in range(max_check_attempts):
            all_pages_open = True

            for page_id, result in detailed_results.items():
                final_page_id = result.get("final_page_id", page_id)

                # 检查页面状态
                status = check_page_status(session, final_page_id, verbose=False)

                if status != "Open":
                    all_pages_open = False
                    if verbose:
                        print(f"页面 {final_page_id} 当前状态: {status}，等待变为Open状态...")

            if all_pages_open:
                if verbose:
                    print("\n✅✅✅ 所有页面都已成功打开 ✅✅✅")
                break

            if attempt < max_check_attempts - 1:
                if verbose:
                    print(f"等待 {check_interval} 秒后再次检查... (尝试 {attempt+1}/{max_check_attempts})")
                time.sleep(check_interval)

        # 如果达到最大检查次数仍有页面未打开，更新结果
        if not all_pages_open:
            if verbose:
                print("\n⚠️⚠️⚠️ 部分页面未能成功打开 ⚠️⚠️⚠️")

            # 再次检查每个页面的最终状态并更新结果
            for page_id, result in detailed_results.items():
                final_page_id = result.get("final_page_id", page_id)
                status = check_page_status(session, final_page_id, verbose=False)

                if status != "Open":
                    if verbose:
                        print(f"页面 {final_page_id} 最终状态: {status}")
                    result["page_open"] = False
                    all_http_detected = False  # 更新全局成功标志
                else:
                    result["page_open"] = True
                    if verbose:
                        print(f"页面 {final_page_id} 最终状态: Open")
        else:
            # 所有页面都成功打开，更新结果
            for result in detailed_results.values():
                result["page_open"] = True

    # 输出总体成功标识
    if verbose:
        print("\n=== 批处理结果摘要 ===")
        for page_id, result in detailed_results.items():
            status = "成功" if result.get("response") is not None else "失败"
            http_status = "✅ 检测到HTTP链接" if result.get("http_detected") else "❌ 未检测到HTTP链接"
            page_status = "✅ 页面已打开" if result.get("page_open", False) else "❌ 页面未打开"
            print(f"页面 {result.get('final_page_id', page_id)}: {status} - {http_status} - {page_status}")

        if all_http_detected:
            print("\n✅✅✅ 所有页面都成功处理并打开 ✅✅✅")
        else:
            print("\n❌❌❌ 部分页面处理失败或未打开 ❌❌❌")

    return detailed_results, all_http_detected

def main():
    """命令行入口函数"""
    parser = argparse.ArgumentParser(description='更新页面URL并发送聊天请求 (同步版本)')

    # 添加批处理模式
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('page_id', nargs='?', help='页面ID')
    group.add_argument('--batch', '-b', nargs='+', help='批量处理多个页面ID')

    parser.add_argument('--url', '-u', default=DEFAULT_URL, help=f'新的URL地址 (默认: {DEFAULT_URL})')
    parser.add_argument('--message', '-m', default=DEFAULT_MESSAGE, help=f'聊天消息内容 (默认: {DEFAULT_MESSAGE})')
    parser.add_argument('--no-reset-counts', action='store_false', dest='reset_counts', help='不重置消息计数器')
    parser.add_argument('--no-reset-cache', action='store_false', dest='reset_cache', help='不重置内容缓存')
    parser.add_argument('--quiet', '-q', action='store_true', help='静默模式，只输出成功标识')

    args = parser.parse_args()

    # 设置详细日志输出模式
    verbose = not args.quiet

    # 处理结果和成功标志
    success = False

    if args.batch:
        # 批量处理模式
        _, all_http_detected = update_pages_batch(
            args.batch,
            new_url=args.url,
            message=args.message,
            reset_counts=args.reset_counts,
            reset_cache=args.reset_cache,
            verbose=verbose
        )
        success = all_http_detected
    else:
        # 单页面处理模式
        _, http_detected, _ = update_page(
            args.page_id,
            new_url=args.url,
            message=args.message,
            reset_counts=args.reset_counts,
            reset_cache=args.reset_cache,
            verbose=verbose
        )
        success = http_detected

    # 在静默模式下，只输出成功标识
    if args.quiet:
        if success:
            print("SUCCESS")
        else:
            print("FAILURE")

    # 设置退出代码
    exit_code = 0 if success else 1

    # 当作为模块导入时，不会退出程序
    if __name__ == "__main__":
        import sys
        sys.exit(exit_code)

    return exit_code

if __name__ == "__main__":
    main()

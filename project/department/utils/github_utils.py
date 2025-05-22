"""
GitHub 工具包

这个模块提供了一组 GitHub 操作工具，包括仓库、问题、拉取请求等功能。
可以作为 AutoGen 的 tools 使用。
"""

import os
import json
import requests
from typing import Dict, List, Any, Optional, Union, Tuple, Annotated
import base64

# 尝试导入 AutoGen 相关模块
try:
    from autogen_core.tools import FunctionTool
    AUTOGEN_AVAILABLE = True
except ImportError:
    AUTOGEN_AVAILABLE = False
    print("未能导入 AutoGen 工具模块 (autogen_core.tools)，将无法注册为 AutoGen 的 tools")

class GitHubUtils:
    """GitHub 操作工具类"""

    def __init__(self, token: str = None, base_url: str = "https://api.github.com"):
        """
        初始化 GitHub 操作工具类

        Args:
            token: GitHub 个人访问令牌，默认从环境变量 GITHUB_TOKEN 获取
            base_url: GitHub API 基础 URL，默认为 https://api.github.com
        """
        self.token = token or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            print("警告: 未提供 GitHub 令牌，API 调用可能受到限制")

        self.base_url = base_url
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AutoGen-GitHub-Tools"
        }

        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    async def get_user(self) -> Dict[str, Any]:
        """
        获取当前认证用户的信息

        Returns:
            包含用户信息或错误信息的字典
        """
        try:
            response = requests.get(f"{self.base_url}/user", headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"获取用户信息时出错: {str(e)}"}

    async def get_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        获取仓库信息

        Args:
            owner: 仓库所有者
            repo: 仓库名称

        Returns:
            包含仓库信息或错误信息的字典
        """
        try:
            response = requests.get(f"{self.base_url}/repos/{owner}/{repo}", headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"获取仓库信息时出错: {str(e)}"}

    async def list_repositories(self, username: str = None, page: int = 1, per_page: int = 30) -> Dict[str, Any]:
        """
        列出用户的仓库

        Args:
            username: 用户名，如果为 None 则列出当前认证用户的仓库
            page: 页码
            per_page: 每页结果数

        Returns:
            包含仓库列表或错误信息的字典
        """
        try:
            url = f"{self.base_url}/user/repos" if username is None else f"{self.base_url}/users/{username}/repos"
            params = {"page": page, "per_page": per_page}
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"列出仓库时出错: {str(e)}"}

    async def create_repository(self, name: str, description: str = "", private: bool = False) -> Dict[str, Any]:
        """
        创建新仓库

        Args:
            name: 仓库名称
            description: 仓库描述
            private: 是否为私有仓库

        Returns:
            包含新仓库信息或错误信息的字典
        """
        try:
            data = {
                "name": name,
                "description": description,
                "private": private
            }
            response = requests.post(f"{self.base_url}/user/repos", headers=self.headers, json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"创建仓库时出错: {str(e)}"}

    async def get_file_contents(self, owner: str, repo: str, path: str, ref: str = None) -> Dict[str, Any]:
        """
        获取文件内容

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            path: 文件路径
            ref: 分支、标签或提交 SHA

        Returns:
            包含文件内容或错误信息的字典
        """
        try:
            url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}"
            params = {}
            if ref:
                params["ref"] = ref

            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()

            content_data = response.json()
            if "content" in content_data and content_data.get("encoding") == "base64":
                # 解码 base64 内容
                decoded_content = base64.b64decode(content_data["content"]).decode("utf-8")
                content_data["decoded_content"] = decoded_content

            return content_data
        except Exception as e:
            return {"error": f"获取文件内容时出错: {str(e)}"}

    async def create_or_update_file(self, owner: str, repo: str, path: str,
                                   message: str, content: str,
                                   branch: str = None, sha: str = None) -> Dict[str, Any]:
        """
        创建或更新文件

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            path: 文件路径
            message: 提交消息
            content: 文件内容
            branch: 分支名称，默认为仓库的默认分支
            sha: 如果更新现有文件，需要提供文件的当前 SHA

        Returns:
            包含操作结果或错误信息的字典
        """
        try:
            url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}"

            # 将内容编码为 base64
            content_bytes = content.encode("utf-8")
            base64_content = base64.b64encode(content_bytes).decode("utf-8")

            data = {
                "message": message,
                "content": base64_content
            }

            if branch:
                data["branch"] = branch

            if sha:
                data["sha"] = sha

            response = requests.put(url, headers=self.headers, json=data)
            response.raise_for_status()

            return response.json()
        except Exception as e:
            return {"error": f"创建或更新文件时出错: {str(e)}"}

    async def list_branches(self, owner: str, repo: str, page: int = 1, per_page: int = 30) -> Dict[str, Any]:
        """
        列出仓库的分支

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            page: 页码
            per_page: 每页结果数

        Returns:
            包含分支列表或错误信息的字典
        """
        try:
            url = f"{self.base_url}/repos/{owner}/{repo}/branches"
            params = {"page": page, "per_page": per_page}

            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()

            return response.json()
        except Exception as e:
            return {"error": f"列出分支时出错: {str(e)}"}

    async def create_branch(self, owner: str, repo: str, branch: str, sha: str) -> Dict[str, Any]:
        """
        创建新分支

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            branch: 新分支名称
            sha: 基于哪个提交创建分支

        Returns:
            包含操作结果或错误信息的字典
        """
        try:
            # 创建引用（分支）
            url = f"{self.base_url}/repos/{owner}/{repo}/git/refs"
            data = {
                "ref": f"refs/heads/{branch}",
                "sha": sha
            }

            response = requests.post(url, headers=self.headers, json=data)
            response.raise_for_status()

            return response.json()
        except Exception as e:
            return {"error": f"创建分支时出错: {str(e)}"}

    async def get_issue(self, owner: str, repo: str, issue_number: int) -> Dict[str, Any]:
        """
        获取问题详情

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            issue_number: 问题编号

        Returns:
            包含问题详情或错误信息的字典
        """
        try:
            url = f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}"

            response = requests.get(url, headers=self.headers)
            response.raise_for_status()

            return response.json()
        except Exception as e:
            return {"error": f"获取问题详情时出错: {str(e)}"}

    async def create_issue(self, owner: str, repo: str, title: str, body: str = "",
                          labels: List[str] = None, assignees: List[str] = None) -> Dict[str, Any]:
        """
        创建新问题

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            title: 问题标题
            body: 问题内容
            labels: 标签列表
            assignees: 受理人列表

        Returns:
            包含新问题信息或错误信息的字典
        """
        try:
            url = f"{self.base_url}/repos/{owner}/{repo}/issues"

            data = {
                "title": title,
                "body": body
            }

            if labels:
                data["labels"] = labels

            if assignees:
                data["assignees"] = assignees

            response = requests.post(url, headers=self.headers, json=data)
            response.raise_for_status()

            return response.json()
        except Exception as e:
            return {"error": f"创建问题时出错: {str(e)}"}

    async def add_issue_comment(self, owner: str, repo: str, issue_number: int, body: str) -> Dict[str, Any]:
        """
        添加问题评论

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            issue_number: 问题编号
            body: 评论内容

        Returns:
            包含评论信息或错误信息的字典
        """
        try:
            url = f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}/comments"

            data = {
                "body": body
            }

            response = requests.post(url, headers=self.headers, json=data)
            response.raise_for_status()

            return response.json()
        except Exception as e:
            return {"error": f"添加评论时出错: {str(e)}"}

    async def get_pull_request(self, owner: str, repo: str, pull_number: int) -> Dict[str, Any]:
        """
        获取拉取请求详情

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            pull_number: 拉取请求编号

        Returns:
            包含拉取请求详情或错误信息的字典
        """
        try:
            url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pull_number}"

            response = requests.get(url, headers=self.headers)
            response.raise_for_status()

            return response.json()
        except Exception as e:
            return {"error": f"获取拉取请求详情时出错: {str(e)}"}

    async def create_pull_request(self, owner: str, repo: str, title: str, head: str, base: str,
                                 body: str = "", draft: bool = False) -> Dict[str, Any]:
        """
        创建拉取请求

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            title: 拉取请求标题
            head: 包含更改的分支
            base: 要合并到的目标分支
            body: 拉取请求描述
            draft: 是否为草稿拉取请求

        Returns:
            包含新拉取请求信息或错误信息的字典
        """
        try:
            url = f"{self.base_url}/repos/{owner}/{repo}/pulls"

            data = {
                "title": title,
                "head": head,
                "base": base,
                "body": body,
                "draft": draft
            }

            response = requests.post(url, headers=self.headers, json=data)
            response.raise_for_status()

            return response.json()
        except Exception as e:
            return {"error": f"创建拉取请求时出错: {str(e)}"}

    async def merge_pull_request(self, owner: str, repo: str, pull_number: int,
                                commit_title: str = None, commit_message: str = None,
                                merge_method: str = "merge") -> Dict[str, Any]:
        """
        合并拉取请求

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            pull_number: 拉取请求编号
            commit_title: 合并提交的标题
            commit_message: 合并提交的消息
            merge_method: 合并方法，可选值为 "merge"、"squash" 或 "rebase"

        Returns:
            包含合并结果或错误信息的字典
        """
        try:
            url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pull_number}/merge"

            data = {
                "merge_method": merge_method
            }

            if commit_title:
                data["commit_title"] = commit_title

            if commit_message:
                data["commit_message"] = commit_message

            response = requests.put(url, headers=self.headers, json=data)
            response.raise_for_status()

            return response.json()
        except Exception as e:
            return {"error": f"合并拉取请求时出错: {str(e)}"}

    async def search_repositories(self, query: str, sort: str = None,
                                 order: str = None, page: int = 1,
                                 per_page: int = 30) -> Dict[str, Any]:
        """
        搜索仓库

        Args:
            query: 搜索查询
            sort: 排序字段
            order: 排序顺序，可选值为 "asc" 或 "desc"
            page: 页码
            per_page: 每页结果数

        Returns:
            包含搜索结果或错误信息的字典
        """
        try:
            url = f"{self.base_url}/search/repositories"

            params = {
                "q": query,
                "page": page,
                "per_page": per_page
            }

            if sort:
                params["sort"] = sort

            if order:
                params["order"] = order

            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()

            return response.json()
        except Exception as e:
            return {"error": f"搜索仓库时出错: {str(e)}"}

    async def search_issues(self, query: str, sort: str = None,
                           order: str = None, page: int = 1,
                           per_page: int = 30) -> Dict[str, Any]:
        """
        搜索问题和拉取请求

        Args:
            query: 搜索查询
            sort: 排序字段
            order: 排序顺序，可选值为 "asc" 或 "desc"
            page: 页码
            per_page: 每页结果数

        Returns:
            包含搜索结果或错误信息的字典
        """
        try:
            url = f"{self.base_url}/search/issues"

            params = {
                "q": query,
                "page": page,
                "per_page": per_page
            }

            if sort:
                params["sort"] = sort

            if order:
                params["order"] = order

            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()

            return response.json()
        except Exception as e:
            return {"error": f"搜索问题时出错: {str(e)}"}


# 创建默认的 GitHub 工具实例
default_github_utils = GitHubUtils()

# 便捷函数
async def get_user() -> Dict[str, Any]:
    """获取当前认证用户的信息"""
    return await default_github_utils.get_user()

async def get_repository(owner: str, repo: str) -> Dict[str, Any]:
    """获取仓库信息"""
    return await default_github_utils.get_repository(owner, repo)

async def list_repositories(username: str = None, page: int = 1, per_page: int = 30) -> Dict[str, Any]:
    """列出用户的仓库"""
    return await default_github_utils.list_repositories(username, page, per_page)

async def create_repository(name: str, description: str = "", private: bool = False) -> Dict[str, Any]:
    """创建新仓库"""
    return await default_github_utils.create_repository(name, description, private)

async def get_file_contents(owner: str, repo: str, path: str, ref: str = None) -> Dict[str, Any]:
    """获取文件内容"""
    return await default_github_utils.get_file_contents(owner, repo, path, ref)

async def create_or_update_file(owner: str, repo: str, path: str, message: str, content: str, branch: str = None, sha: str = None) -> Dict[str, Any]:
    """创建或更新文件"""
    return await default_github_utils.create_or_update_file(owner, repo, path, message, content, branch, sha)

async def list_branches(owner: str, repo: str, page: int = 1, per_page: int = 30) -> Dict[str, Any]:
    """列出仓库的分支"""
    return await default_github_utils.list_branches(owner, repo, page, per_page)

async def create_branch(owner: str, repo: str, branch: str, sha: str) -> Dict[str, Any]:
    """创建新分支"""
    return await default_github_utils.create_branch(owner, repo, branch, sha)

async def get_issue(owner: str, repo: str, issue_number: int) -> Dict[str, Any]:
    """获取问题详情"""
    return await default_github_utils.get_issue(owner, repo, issue_number)

async def create_issue(owner: str, repo: str, title: str, body: str = "", labels: List[str] = None, assignees: List[str] = None) -> Dict[str, Any]:
    """创建新问题"""
    return await default_github_utils.create_issue(owner, repo, title, body, labels, assignees)

async def add_issue_comment(owner: str, repo: str, issue_number: int, body: str) -> Dict[str, Any]:
    """添加问题评论"""
    return await default_github_utils.add_issue_comment(owner, repo, issue_number, body)

async def get_pull_request(owner: str, repo: str, pull_number: int) -> Dict[str, Any]:
    """获取拉取请求详情"""
    return await default_github_utils.get_pull_request(owner, repo, pull_number)

async def create_pull_request(owner: str, repo: str, title: str, head: str, base: str, body: str = "", draft: bool = False) -> Dict[str, Any]:
    """创建拉取请求"""
    return await default_github_utils.create_pull_request(owner, repo, title, head, base, body, draft)

async def merge_pull_request(owner: str, repo: str, pull_number: int, commit_title: str = None, commit_message: str = None, merge_method: str = "merge") -> Dict[str, Any]:
    """合并拉取请求"""
    return await default_github_utils.merge_pull_request(owner, repo, pull_number, commit_title, commit_message, merge_method)

async def search_repositories(query: str, sort: str = None, order: str = None, page: int = 1, per_page: int = 30) -> Dict[str, Any]:
    """搜索仓库"""
    return await default_github_utils.search_repositories(query, sort, order, page, per_page)

async def search_issues(query: str, sort: str = None, order: str = None, page: int = 1, per_page: int = 30) -> Dict[str, Any]:
    """搜索问题和拉取请求"""
    return await default_github_utils.search_issues(query, sort, order, page, per_page)


# 创建 AutoGen 工具
if AUTOGEN_AVAILABLE:
    # 同步版本的函数，用于 AutoGen 工具
    def get_user_sync() -> str:
        """
        获取当前认证用户的信息。

        Returns:
            包含用户信息或错误信息的 JSON 字符串
        """
        import asyncio
        result = asyncio.run(default_github_utils.get_user())
        return json.dumps(result, ensure_ascii=False)

    def get_repository_sync(
        owner: Annotated[str, "仓库所有者"],
        repo: Annotated[str, "仓库名称"]
    ) -> str:
        """
        获取仓库信息。

        Args:
            owner: 仓库所有者
            repo: 仓库名称

        Returns:
            包含仓库信息或错误信息的 JSON 字符串
        """
        import asyncio
        result = asyncio.run(default_github_utils.get_repository(owner, repo))
        return json.dumps(result, ensure_ascii=False)

    def list_repositories_sync(
        username: Annotated[str, "用户名，如果为空则列出当前认证用户的仓库"] = None,
        page: Annotated[int, "页码"] = 1,
        per_page: Annotated[int, "每页结果数"] = 30
    ) -> str:
        """
        列出用户的仓库。

        Args:
            username: 用户名，如果为空则列出当前认证用户的仓库
            page: 页码
            per_page: 每页结果数

        Returns:
            包含仓库列表或错误信息的 JSON 字符串
        """
        import asyncio
        result = asyncio.run(default_github_utils.list_repositories(username, page, per_page))
        return json.dumps(result, ensure_ascii=False)

    def create_repository_sync(
        name: Annotated[str, "仓库名称"],
        description: Annotated[str, "仓库描述"] = "",
        private: Annotated[bool, "是否为私有仓库"] = False
    ) -> str:
        """
        创建新仓库。

        Args:
            name: 仓库名称
            description: 仓库描述
            private: 是否为私有仓库

        Returns:
            包含新仓库信息或错误信息的 JSON 字符串
        """
        import asyncio
        result = asyncio.run(default_github_utils.create_repository(name, description, private))
        return json.dumps(result, ensure_ascii=False)

    def get_file_contents_sync(
        owner: Annotated[str, "仓库所有者"],
        repo: Annotated[str, "仓库名称"],
        path: Annotated[str, "文件路径"],
        ref: Annotated[str, "分支、标签或提交 SHA"] = None
    ) -> str:
        """
        获取文件内容。

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            path: 文件路径
            ref: 分支、标签或提交 SHA

        Returns:
            包含文件内容或错误信息的 JSON 字符串
        """
        import asyncio
        result = asyncio.run(default_github_utils.get_file_contents(owner, repo, path, ref))
        return json.dumps(result, ensure_ascii=False)

    def create_or_update_file_sync(
        owner: Annotated[str, "仓库所有者"],
        repo: Annotated[str, "仓库名称"],
        path: Annotated[str, "文件路径"],
        message: Annotated[str, "提交消息"],
        content: Annotated[str, "文件内容"],
        branch: Annotated[str, "分支名称"] = None,
        sha: Annotated[str, "如果更新现有文件，需要提供文件的当前 SHA"] = None
    ) -> str:
        """
        创建或更新文件。

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            path: 文件路径
            message: 提交消息
            content: 文件内容
            branch: 分支名称
            sha: 如果更新现有文件，需要提供文件的当前 SHA

        Returns:
            包含操作结果或错误信息的 JSON 字符串
        """
        import asyncio
        result = asyncio.run(default_github_utils.create_or_update_file(owner, repo, path, message, content, branch, sha))
        return json.dumps(result, ensure_ascii=False)

    def list_branches_sync(
        owner: Annotated[str, "仓库所有者"],
        repo: Annotated[str, "仓库名称"],
        page: Annotated[int, "页码"] = 1,
        per_page: Annotated[int, "每页结果数"] = 30
    ) -> str:
        """
        列出仓库的分支。

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            page: 页码
            per_page: 每页结果数

        Returns:
            包含分支列表或错误信息的 JSON 字符串
        """
        import asyncio
        result = asyncio.run(default_github_utils.list_branches(owner, repo, page, per_page))
        return json.dumps(result, ensure_ascii=False)

    def create_branch_sync(
        owner: Annotated[str, "仓库所有者"],
        repo: Annotated[str, "仓库名称"],
        branch: Annotated[str, "新分支名称"],
        sha: Annotated[str, "基于哪个提交创建分支"]
    ) -> str:
        """
        创建新分支。

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            branch: 新分支名称
            sha: 基于哪个提交创建分支

        Returns:
            包含操作结果或错误信息的 JSON 字符串
        """
        import asyncio
        result = asyncio.run(default_github_utils.create_branch(owner, repo, branch, sha))
        return json.dumps(result, ensure_ascii=False)

    def get_issue_sync(
        owner: Annotated[str, "仓库所有者"],
        repo: Annotated[str, "仓库名称"],
        issue_number: Annotated[int, "问题编号"]
    ) -> str:
        """
        获取问题详情。

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            issue_number: 问题编号

        Returns:
            包含问题详情或错误信息的 JSON 字符串
        """
        import asyncio
        result = asyncio.run(default_github_utils.get_issue(owner, repo, issue_number))
        return json.dumps(result, ensure_ascii=False)

    def create_issue_sync(
        owner: Annotated[str, "仓库所有者"],
        repo: Annotated[str, "仓库名称"],
        title: Annotated[str, "问题标题"],
        body: Annotated[str, "问题内容"] = "",
        labels: Annotated[str, "标签列表，JSON 格式"] = None,
        assignees: Annotated[str, "受理人列表，JSON 格式"] = None
    ) -> str:
        """
        创建新问题。

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            title: 问题标题
            body: 问题内容
            labels: 标签列表，JSON 格式
            assignees: 受理人列表，JSON 格式

        Returns:
            包含新问题信息或错误信息的 JSON 字符串
        """
        import asyncio
        try:
            labels_list = json.loads(labels) if labels else None
            assignees_list = json.loads(assignees) if assignees else None
            result = asyncio.run(default_github_utils.create_issue(owner, repo, title, body, labels_list, assignees_list))
            return json.dumps(result, ensure_ascii=False)
        except json.JSONDecodeError:
            return json.dumps({"error": "标签或受理人列表不是有效的 JSON 格式"}, ensure_ascii=False)

    def add_issue_comment_sync(
        owner: Annotated[str, "仓库所有者"],
        repo: Annotated[str, "仓库名称"],
        issue_number: Annotated[int, "问题编号"],
        body: Annotated[str, "评论内容"]
    ) -> str:
        """
        添加问题评论。

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            issue_number: 问题编号
            body: 评论内容

        Returns:
            包含评论信息或错误信息的 JSON 字符串
        """
        import asyncio
        result = asyncio.run(default_github_utils.add_issue_comment(owner, repo, issue_number, body))
        return json.dumps(result, ensure_ascii=False)

    def get_pull_request_sync(
        owner: Annotated[str, "仓库所有者"],
        repo: Annotated[str, "仓库名称"],
        pull_number: Annotated[int, "拉取请求编号"]
    ) -> str:
        """
        获取拉取请求详情。

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            pull_number: 拉取请求编号

        Returns:
            包含拉取请求详情或错误信息的 JSON 字符串
        """
        import asyncio
        result = asyncio.run(default_github_utils.get_pull_request(owner, repo, pull_number))
        return json.dumps(result, ensure_ascii=False)

    def create_pull_request_sync(
        owner: Annotated[str, "仓库所有者"],
        repo: Annotated[str, "仓库名称"],
        title: Annotated[str, "拉取请求标题"],
        head: Annotated[str, "包含更改的分支"],
        base: Annotated[str, "要合并到的目标分支"],
        body: Annotated[str, "拉取请求描述"] = "",
        draft: Annotated[bool, "是否为草稿拉取请求"] = False
    ) -> str:
        """
        创建拉取请求。

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            title: 拉取请求标题
            head: 包含更改的分支
            base: 要合并到的目标分支
            body: 拉取请求描述
            draft: 是否为草稿拉取请求

        Returns:
            包含新拉取请求信息或错误信息的 JSON 字符串
        """
        import asyncio
        result = asyncio.run(default_github_utils.create_pull_request(owner, repo, title, head, base, body, draft))
        return json.dumps(result, ensure_ascii=False)

    def merge_pull_request_sync(
        owner: Annotated[str, "仓库所有者"],
        repo: Annotated[str, "仓库名称"],
        pull_number: Annotated[int, "拉取请求编号"],
        commit_title: Annotated[str, "合并提交的标题"] = None,
        commit_message: Annotated[str, "合并提交的消息"] = None,
        merge_method: Annotated[str, "合并方法，可选值为 merge、squash 或 rebase"] = "merge"
    ) -> str:
        """
        合并拉取请求。

        Args:
            owner: 仓库所有者
            repo: 仓库名称
            pull_number: 拉取请求编号
            commit_title: 合并提交的标题
            commit_message: 合并提交的消息
            merge_method: 合并方法，可选值为 merge、squash 或 rebase

        Returns:
            包含合并结果或错误信息的 JSON 字符串
        """
        import asyncio
        result = asyncio.run(default_github_utils.merge_pull_request(owner, repo, pull_number, commit_title, commit_message, merge_method))
        return json.dumps(result, ensure_ascii=False)

    def search_repositories_sync(
        query: Annotated[str, "搜索查询"],
        sort: Annotated[str, "排序字段"] = None,
        order: Annotated[str, "排序顺序，可选值为 asc 或 desc"] = None,
        page: Annotated[int, "页码"] = 1,
        per_page: Annotated[int, "每页结果数"] = 30
    ) -> str:
        """
        搜索仓库。

        Args:
            query: 搜索查询
            sort: 排序字段
            order: 排序顺序，可选值为 asc 或 desc
            page: 页码
            per_page: 每页结果数

        Returns:
            包含搜索结果或错误信息的 JSON 字符串
        """
        import asyncio
        result = asyncio.run(default_github_utils.search_repositories(query, sort, order, page, per_page))
        return json.dumps(result, ensure_ascii=False)

    def search_issues_sync(
        query: Annotated[str, "搜索查询"],
        sort: Annotated[str, "排序字段"] = None,
        order: Annotated[str, "排序顺序，可选值为 asc 或 desc"] = None,
        page: Annotated[int, "页码"] = 1,
        per_page: Annotated[int, "每页结果数"] = 30
    ) -> str:
        """
        搜索问题和拉取请求。

        Args:
            query: 搜索查询
            sort: 排序字段
            order: 排序顺序，可选值为 asc 或 desc
            page: 页码
            per_page: 每页结果数

        Returns:
            包含搜索结果或错误信息的 JSON 字符串
        """
        import asyncio
        result = asyncio.run(default_github_utils.search_issues(query, sort, order, page, per_page))
        return json.dumps(result, ensure_ascii=False)

    # 创建 AutoGen 工具
    get_user_tool = FunctionTool(
        name="get_github_user",
        description="获取当前认证 GitHub 用户的信息",
        func=get_user_sync
    )

    get_repository_tool = FunctionTool(
        name="get_github_repository",
        description="获取 GitHub 仓库信息",
        func=get_repository_sync
    )

    list_repositories_tool = FunctionTool(
        name="list_github_repositories",
        description="列出 GitHub 用户的仓库",
        func=list_repositories_sync
    )

    create_repository_tool = FunctionTool(
        name="create_github_repository",
        description="创建新的 GitHub 仓库",
        func=create_repository_sync
    )

    get_file_contents_tool = FunctionTool(
        name="get_github_file_contents",
        description="获取 GitHub 仓库中文件的内容",
        func=get_file_contents_sync
    )

    create_or_update_file_tool = FunctionTool(
        name="create_or_update_github_file",
        description="在 GitHub 仓库中创建或更新文件",
        func=create_or_update_file_sync
    )

    list_branches_tool = FunctionTool(
        name="list_github_branches",
        description="列出 GitHub 仓库的分支",
        func=list_branches_sync
    )

    create_branch_tool = FunctionTool(
        name="create_github_branch",
        description="在 GitHub 仓库中创建新分支",
        func=create_branch_sync
    )

    get_issue_tool = FunctionTool(
        name="get_github_issue",
        description="获取 GitHub 仓库中问题的详情",
        func=get_issue_sync
    )

    create_issue_tool = FunctionTool(
        name="create_github_issue",
        description="在 GitHub 仓库中创建新问题",
        func=create_issue_sync
    )

    add_issue_comment_tool = FunctionTool(
        name="add_github_issue_comment",
        description="在 GitHub 仓库的问题中添加评论",
        func=add_issue_comment_sync
    )

    get_pull_request_tool = FunctionTool(
        name="get_github_pull_request",
        description="获取 GitHub 仓库中拉取请求的详情",
        func=get_pull_request_sync
    )

    create_pull_request_tool = FunctionTool(
        name="create_github_pull_request",
        description="在 GitHub 仓库中创建新拉取请求",
        func=create_pull_request_sync
    )

    merge_pull_request_tool = FunctionTool(
        name="merge_github_pull_request",
        description="合并 GitHub 仓库中的拉取请求",
        func=merge_pull_request_sync
    )

    search_repositories_tool = FunctionTool(
        name="search_github_repositories",
        description="搜索 GitHub 仓库",
        func=search_repositories_sync
    )

    search_issues_tool = FunctionTool(
        name="search_github_issues",
        description="搜索 GitHub 问题和拉取请求",
        func=search_issues_sync
    )

    # GitHub 工具列表
    github_tools = [
        get_user_tool,
        get_repository_tool,
        list_repositories_tool,
        create_repository_tool,
        get_file_contents_tool,
        create_or_update_file_tool,
        list_branches_tool,
        create_branch_tool,
        get_issue_tool,
        create_issue_tool,
        add_issue_comment_tool,
        get_pull_request_tool,
        create_pull_request_tool,
        merge_pull_request_tool,
        search_repositories_tool,
        search_issues_tool
    ]

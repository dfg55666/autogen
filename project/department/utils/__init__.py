"""
department.utils 包

这个包提供了各种实用工具，包括文件操作、系统信息获取、多模态内容处理等功能。
支持多种文件格式，包括纯文本文件、Markdown、Word、Excel、PDF等。
可以作为 AutoGen 的 tools 使用。
"""

from .file_utils import (
    FileUtils,
    get_file_tools,
    # 文件格式支持状态
    DOCX_AVAILABLE,
    XLSX_AVAILABLE,
    PANDAS_AVAILABLE,
    PDF_AVAILABLE,
    MARKDOWN_AVAILABLE,
    BS4_AVAILABLE,
    YAML_AVAILABLE,
    XML_AVAILABLE,
    # AutoGen 工具
    AUTOGEN_AVAILABLE
)

# 定义导出的符号
__all__ = [
    'FileUtils',
    'get_file_tools',
    # 文件格式支持状态
    'DOCX_AVAILABLE',
    'XLSX_AVAILABLE',
    'PANDAS_AVAILABLE',
    'PDF_AVAILABLE',
    'MARKDOWN_AVAILABLE',
    'BS4_AVAILABLE',
    'YAML_AVAILABLE',
    'XML_AVAILABLE',
    # AutoGen 工具状态
    'AUTOGEN_AVAILABLE',
    'AUTOGEN_MCP_AVAILABLE'
]

# 注意：我们现在使用 get_file_tools() 函数来获取所有工具，
# 不再单独导入每个工具函数

# 如果 MCP 工具可用，添加到导出列表
if 'McpTools' in locals():
    __all__.extend([
        'McpTools',
        'create_fetch_tools',
        'create_playwright_tools',
        'create_filesystem_tools',
        'close_mcp_tools'
    ])

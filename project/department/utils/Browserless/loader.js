/**
 * Browserless工具加载器 - 用于加载和使用自定义JS脚本
 *
 * 这个模块提供了一种方式，可以在Browserless会话中加载和使用自定义JS脚本，
 * 使得AI助手可以更容易地执行复杂的浏览器自动化任务。
 */

// 导入所有工具模块
const htmlParser = require('./html_parser');
const pageInteraction = require('./page_interaction');

/**
 * 加载所有工具到浏览器环境
 *
 * @returns {Object} 加载结果
 */
function loadAllTools() {
  try {
    // 将所有工具函数添加到全局对象
    Object.assign(global, htmlParser, pageInteraction);

    // 返回已加载的工具列表
    return {
      success: true,
      loadedTools: {
        htmlParser: Object.keys(htmlParser),
        pageInteraction: Object.keys(pageInteraction)
      }
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
}

/**
 * 执行指定的工具函数
 *
 * @param {string} toolName - 要执行的工具函数名称
 * @param {Array} args - 传递给函数的参数
 * @returns {any} 函数执行结果
 */
async function executeTool(toolName, ...args) {
  try {
    // 查找工具函数
    const tool = findTool(toolName);
    if (!tool) {
      return {
        success: false,
        error: `未找到工具函数: ${toolName}`
      };
    }

    // 执行工具函数
    const result = await tool(...args);
    return {
      success: true,
      result
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
}

/**
 * 查找工具函数
 *
 * @param {string} toolName - 工具函数名称
 * @returns {Function|null} 工具函数或null
 */
function findTool(toolName) {
  // 在所有模块中查找工具函数
  if (htmlParser[toolName]) {
    return htmlParser[toolName];
  }

  if (searchHelper[toolName]) {
    return searchHelper[toolName];
  }

  if (pageInteraction[toolName]) {
    return pageInteraction[toolName];
  }

  return null;
}

/**
 * 获取所有可用工具的列表
 *
 * @returns {Object} 工具列表
 */
function listAvailableTools() {
  return {
    htmlParser: Object.keys(htmlParser).map(name => ({
      name,
      description: getToolDescription(name, htmlParser)
    })),
    searchHelper: Object.keys(searchHelper).map(name => ({
      name,
      description: getToolDescription(name, searchHelper)
    })),
    pageInteraction: Object.keys(pageInteraction).map(name => ({
      name,
      description: getToolDescription(name, pageInteraction)
    }))
  };
}

/**
 * 获取工具函数的描述
 *
 * @param {string} toolName - 工具函数名称
 * @param {Object} module - 工具模块
 * @returns {string} 工具描述
 */
function getToolDescription(toolName, module) {
  const tool = module[toolName];
  if (!tool) return '';

  // 尝试从函数注释中提取描述
  const funcStr = tool.toString();
  const commentMatch = /\/\*\*([\s\S]*?)\*\//.exec(funcStr);
  if (commentMatch) {
    const comment = commentMatch[1];
    const descriptionMatch = /\s*\*\s*(.*?)(?:\s*\*\s*@|\s*\*\/)/.exec(comment);
    if (descriptionMatch) {
      return descriptionMatch[1].trim();
    }
  }

  return '无描述';
}

// 导出所有函数
module.exports = {
  loadAllTools,
  executeTool,
  findTool,
  listAvailableTools
};

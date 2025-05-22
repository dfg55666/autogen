/**
 * JSON解析器 - 用于处理搜索结果和其他结构化数据的JavaScript函数集合
 *
 * 这些函数可以通过Browserless的evaluate API在浏览器中执行，
 * 用于解析和格式化从网页中提取的结构化数据。
 */

/**
 * 格式化搜索结果
 * 
 * @param {Object} searchData - 从网页中提取的搜索数据
 * @param {number} maxResults - 最大结果数量
 * @returns {Object} 格式化后的搜索结果
 */
function formatSearchResults(searchData, maxResults = 10) {
  try {
    if (!searchData || !searchData.results) {
      return {
        error: '无效的搜索数据',
        engine: searchData?.engine || 'unknown'
      };
    }

    // 限制结果数量
    const limitedResults = searchData.results.slice(0, maxResults);
    
    // 格式化每个结果
    const formattedResults = limitedResults.map(result => {
      // 确保所有字段都存在
      return {
        title: result.title || '',
        url: result.url || '',
        snippet: result.snippet || '',
        date: result.date || '',
        domain: result.domain || extractDomainFromUrl(result.url || ''),
        type: result.type || 'web'
      };
    });
    
    // 构建格式化后的搜索数据
    const formattedData = {
      engine: searchData.engine || 'unknown',
      query: searchData.metadata?.query || '',
      results: formattedResults,
      totalResults: searchData.metadata?.totalResults || formattedResults.length,
      searchTime: searchData.metadata?.searchTime || null,
      relatedSearches: searchData.metadata?.relatedSearches || [],
      url: searchData.url || window.location.href
    };
    
    return formattedData;
  } catch (error) {
    console.error('格式化搜索结果时出错:', error);
    return {
      error: error.message,
      engine: searchData?.engine || 'unknown'
    };
  }
}

/**
 * 从URL中提取域名
 * 
 * @param {string} url - URL
 * @returns {string} 域名
 */
function extractDomainFromUrl(url) {
  try {
    if (!url) return '';
    
    // 尝试使用URL API
    const urlObj = new URL(url);
    return urlObj.hostname.replace(/^www\./, '');
  } catch (error) {
    // 如果URL无效，使用正则表达式
    const match = url.match(/^(?:https?:\/\/)?(?:www\.)?([^\/]+)/i);
    return match ? match[1] : '';
  }
}

/**
 * 将搜索结果转换为Markdown格式
 * 
 * @param {Object} searchData - 格式化后的搜索数据
 * @returns {string} Markdown格式的搜索结果
 */
function searchResultsToMarkdown(searchData) {
  try {
    if (!searchData || !searchData.results) {
      return `# 搜索失败\n\n${searchData?.error || '未知错误'}`;
    }
    
    let markdown = `# ${searchData.engine.charAt(0).toUpperCase() + searchData.engine.slice(1)} 搜索结果\n\n`;
    
    // 添加查询和元数据
    if (searchData.query) {
      markdown += `**查询**: ${searchData.query}\n\n`;
    }
    
    if (searchData.totalResults) {
      markdown += `**找到约 ${searchData.totalResults} 条结果**`;
      
      if (searchData.searchTime) {
        markdown += ` (${searchData.searchTime} 秒)`;
      }
      
      markdown += '\n\n';
    }
    
    // 添加搜索结果
    searchData.results.forEach((result, index) => {
      markdown += `## ${index + 1}. ${result.title}\n`;
      markdown += `**链接**: [${result.url}](${result.url})\n\n`;
      
      if (result.snippet) {
        markdown += `${result.snippet}\n\n`;
      }
      
      if (result.date) {
        markdown += `**日期**: ${result.date} | `;
      }
      
      markdown += `**类型**: ${result.type}\n\n`;
      markdown += '---\n\n';
    });
    
    // 添加相关搜索
    if (searchData.relatedSearches && searchData.relatedSearches.length > 0) {
      markdown += '## 相关搜索\n\n';
      searchData.relatedSearches.forEach(term => {
        markdown += `- ${term}\n`;
      });
    }
    
    return markdown;
  } catch (error) {
    console.error('将搜索结果转换为Markdown时出错:', error);
    return `# 转换失败\n\n${error.message}`;
  }
}

/**
 * 将搜索结果转换为HTML格式
 * 
 * @param {Object} searchData - 格式化后的搜索数据
 * @returns {string} HTML格式的搜索结果
 */
function searchResultsToHtml(searchData) {
  try {
    if (!searchData || !searchData.results) {
      return `<h1>搜索失败</h1><p>${searchData?.error || '未知错误'}</p>`;
    }
    
    let html = `<h1>${searchData.engine.charAt(0).toUpperCase() + searchData.engine.slice(1)} 搜索结果</h1>`;
    
    // 添加查询和元数据
    if (searchData.query) {
      html += `<p><strong>查询</strong>: ${searchData.query}</p>`;
    }
    
    if (searchData.totalResults) {
      html += `<p><strong>找到约 ${searchData.totalResults} 条结果</strong>`;
      
      if (searchData.searchTime) {
        html += ` (${searchData.searchTime} 秒)`;
      }
      
      html += '</p>';
    }
    
    // 添加搜索结果
    html += '<div class="search-results">';
    searchData.results.forEach((result, index) => {
      html += `<div class="search-result">`;
      html += `<h2>${index + 1}. ${result.title}</h2>`;
      html += `<p class="url"><a href="${result.url}" target="_blank">${result.url}</a></p>`;
      
      if (result.snippet) {
        html += `<p class="snippet">${result.snippet}</p>`;
      }
      
      html += `<p class="meta">`;
      if (result.date) {
        html += `<span class="date">日期: ${result.date}</span> | `;
      }
      
      html += `<span class="type">类型: ${result.type}</span>`;
      html += `</p>`;
      html += `<hr>`;
      html += `</div>`;
    });
    html += '</div>';
    
    // 添加相关搜索
    if (searchData.relatedSearches && searchData.relatedSearches.length > 0) {
      html += '<div class="related-searches">';
      html += '<h2>相关搜索</h2>';
      html += '<ul>';
      searchData.relatedSearches.forEach(term => {
        html += `<li>${term}</li>`;
      });
      html += '</ul>';
      html += '</div>';
    }
    
    return html;
  } catch (error) {
    console.error('将搜索结果转换为HTML时出错:', error);
    return `<h1>转换失败</h1><p>${error.message}</p>`;
  }
}

/**
 * 将搜索结果转换为JSON格式
 * 
 * @param {Object} searchData - 格式化后的搜索数据
 * @returns {string} JSON格式的搜索结果
 */
function searchResultsToJson(searchData) {
  try {
    return JSON.stringify(searchData, null, 2);
  } catch (error) {
    console.error('将搜索结果转换为JSON时出错:', error);
    return JSON.stringify({ error: error.message }, null, 2);
  }
}

// 导出所有函数
module.exports = {
  formatSearchResults,
  extractDomainFromUrl,
  searchResultsToMarkdown,
  searchResultsToHtml,
  searchResultsToJson
};

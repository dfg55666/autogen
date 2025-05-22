/**
 * HTML解析器 - 用于从网页中提取有用信息的JavaScript函数集合
 *
 * 这些函数可以通过Browserless的evaluate API在浏览器中执行，
 * 用于提取结构化数据，如表格数据、列表等。
 */

/**
 * 提取表格数据
 *
 * @param {string} tableSelector - 表格的CSS选择器
 * @returns {Array} 表格数据数组，每行是一个对象，键为表头
 */
function extractTableData(tableSelector = 'table') {
  const table = document.querySelector(tableSelector);
  if (!table) return [];

  const rows = table.querySelectorAll('tr');
  if (!rows || rows.length === 0) return [];

  const headers = [];
  const headerCells = rows[0].querySelectorAll('th');

  // 提取表头
  if (headerCells && headerCells.length > 0) {
    for (const cell of headerCells) {
      headers.push(cell.textContent.trim());
    }
  } else {
    // 如果没有<th>元素，使用第一行的<td>作为表头
    const firstRowCells = rows[0].querySelectorAll('td');
    for (const cell of firstRowCells) {
      headers.push(cell.textContent.trim());
    }
    // 跳过第一行数据处理
    rows.shift();
  }

  const data = [];

  // 处理数据行
  for (let i = 1; i < rows.length; i++) {
    const row = rows[i];
    const cells = row.querySelectorAll('td');
    if (!cells || cells.length === 0) continue;

    const rowData = {};
    for (let j = 0; j < Math.min(headers.length, cells.length); j++) {
      rowData[headers[j] || `column${j}`] = cells[j].textContent.trim();
    }

    data.push(rowData);
  }

  return data;
}

/**
 * 提取页面中的所有链接
 *
 * @param {string} selector - 限制范围的CSS选择器（可选）
 * @returns {Array} 链接数组，每个链接包含文本和URL
 */
function extractLinks(selector = 'body') {
  const container = document.querySelector(selector);
  if (!container) return [];

  const links = container.querySelectorAll('a');
  const result = [];

  for (const link of links) {
    if (link.href && !link.href.startsWith('javascript:')) {
      result.push({
        text: link.textContent.trim(),
        url: link.href,
        title: link.title || ''
      });
    }
  }

  return result;
}

/**
 * 提取网页摘要信息
 *
 * 提取网页的标题、描述、关键词、作者等元数据，以及主要内容的摘要
 *
 * @returns {Object} 包含网页摘要信息的对象
 */
function extractPageSummary() {
  try {
    const result = {
      title: '',
      description: '',
      keywords: [],
      author: '',
      publishDate: '',
      mainContent: '',
      mainContentSummary: '',
      wordCount: 0,
      images: [],
      links: [],
      domain: ''
    };

    // 提取标题
    result.title = document.title || '';

    // 提取域名
    result.domain = window.location.hostname;

    // 提取元数据
    const metaTags = document.querySelectorAll('meta');
    for (const meta of metaTags) {
      const name = meta.getAttribute('name') || meta.getAttribute('property') || '';
      const content = meta.getAttribute('content') || '';

      if (name && content) {
        if (name === 'description' || name === 'og:description') {
          if (!result.description) result.description = content;
        } else if (name === 'keywords') {
          result.keywords = content.split(',').map(k => k.trim());
        } else if (name === 'author' || name === 'og:author') {
          if (!result.author) result.author = content;
        } else if (name === 'article:published_time' || name === 'datePublished') {
          if (!result.publishDate) result.publishDate = content;
        }
      }
    }

    // 尝试从结构化数据中提取信息
    const jsonLdScripts = document.querySelectorAll('script[type="application/ld+json"]');
    for (const script of jsonLdScripts) {
      try {
        const data = JSON.parse(script.textContent);
        if (data['@type'] === 'Article' || data['@type'] === 'NewsArticle') {
          if (!result.author && data.author) {
            result.author = typeof data.author === 'string' ? data.author :
                           (data.author.name || '');
          }
          if (!result.publishDate && data.datePublished) {
            result.publishDate = data.datePublished;
          }
          if (!result.description && data.description) {
            result.description = data.description;
          }
        }
      } catch (e) {
        console.error('解析JSON-LD时出错:', e);
      }
    }

    // 提取主要内容
    // 尝试多种选择器找到主要内容区域
    const contentSelectors = [
      'article', 'main', '.content', '.article', '.post', '.entry',
      '#content', '#main', '[role="main"]'
    ];

    let mainContentElement = null;
    for (const selector of contentSelectors) {
      const element = document.querySelector(selector);
      if (element) {
        mainContentElement = element;
        break;
      }
    }

    // 如果没有找到主要内容区域，使用body
    if (!mainContentElement) {
      mainContentElement = document.body;
    }

    // 提取主要内容的文本
    if (mainContentElement) {
      // 创建一个副本以便操作
      const contentClone = mainContentElement.cloneNode(true);

      // 移除不需要的元素
      const removeSelectors = [
        'script', 'style', 'nav', 'header', 'footer', '.sidebar', '.comments',
        '.ad', '.advertisement', '.banner', '.menu', '.navigation'
      ];

      for (const selector of removeSelectors) {
        const elements = contentClone.querySelectorAll(selector);
        for (const element of elements) {
          if (element.parentNode) {
            element.parentNode.removeChild(element);
          }
        }
      }

      // 获取清理后的文本
      result.mainContent = contentClone.textContent.replace(/\s+/g, ' ').trim();

      // 计算字数
      result.wordCount = result.mainContent.split(/\s+/).filter(w => w.length > 0).length;

      // 创建摘要 (前200个字符)
      result.mainContentSummary = result.mainContent.substring(0, 200) +
                                 (result.mainContent.length > 200 ? '...' : '');

      // 提取图片
      const images = mainContentElement.querySelectorAll('img');
      for (const img of images) {
        if (img.src && !img.src.startsWith('data:')) {
          result.images.push({
            src: img.src,
            alt: img.alt || '',
            width: img.width,
            height: img.height
          });
        }
      }

      // 提取链接
      const links = mainContentElement.querySelectorAll('a');
      for (const link of links) {
        if (link.href && !link.href.startsWith('javascript:')) {
          result.links.push({
            text: link.textContent.trim(),
            url: link.href,
            isExternal: link.hostname !== window.location.hostname
          });
        }
      }
    }

    return result;
  } catch (e) {
    console.error('提取页面摘要时出错:', e);
    return {
      error: e.message,
      title: document.title || '',
      url: window.location.href
    };
  }
}

/**
 * 分析网页内容并提取关键信息
 *
 * @returns {Object} 包含网页分析结果的对象
 */
function analyzeWebpage() {
  try {
    // 获取基本摘要信息
    const summary = extractPageSummary();

    // 分析页面类型
    let pageType = 'generic';
    const url = window.location.href;
    const domain = window.location.hostname;

    if (url.includes('/product') || url.includes('/item') ||
        document.querySelector('.product, .item, [itemtype*="Product"]')) {
      pageType = 'product';
    } else if (url.includes('/article') || url.includes('/post') || url.includes('/blog') ||
              document.querySelector('article, .post, [itemtype*="Article"]')) {
      pageType = 'article';
    } else if (url.includes('/news') || domain.includes('news')) {
      pageType = 'news';
    } else if (document.querySelector('form[action*="search"]')) {
      pageType = 'search';
    } else if (document.querySelector('.profile, [itemtype*="Person"]')) {
      pageType = 'profile';
    }

    // 提取主题和关键概念
    const topics = [];
    const headings = document.querySelectorAll('h1, h2, h3');
    for (const heading of headings) {
      const text = heading.textContent.trim();
      if (text && text.length > 3) {
        topics.push(text);
      }
    }

    // 返回完整分析结果
    return {
      summary: summary,
      pageType: pageType,
      topics: topics.slice(0, 10), // 限制为前10个主题
      url: window.location.href,
      timestamp: new Date().toISOString()
    };
  } catch (e) {
    console.error('分析网页时出错:', e);
    return {
      error: e.message,
      url: window.location.href
    };
  }
}

// 导出所有函数
module.exports = {
  extractTableData,
  extractLinks,
  extractPageSummary,
  analyzeWebpage
};

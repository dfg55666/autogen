/**
 * 页面交互助手 - 用于复杂页面交互的JavaScript函数集合
 *
 * 这些函数可以通过Browserless的evaluate API在浏览器中执行，
 * 用于表单填写、导航、等待条件等高级交互。
 */

/**
 * 填写表单
 *
 * @param {Object} formData - 表单数据，键为字段选择器，值为要填入的值
 * @param {string} submitSelector - 提交按钮的选择器（可选）
 * @returns {Object} 操作结果
 */
async function fillForm(formData, submitSelector = null) {
  try {
    const results = {};

    // 遍历表单数据并填写
    for (const [selector, value] of Object.entries(formData)) {
      const element = document.querySelector(selector);
      if (!element) {
        results[selector] = { success: false, error: '未找到元素' };
        continue;
      }

      // 根据元素类型执行不同的操作
      const tagName = element.tagName.toLowerCase();
      const type = element.type ? element.type.toLowerCase() : '';

      if (tagName === 'input') {
        if (type === 'checkbox' || type === 'radio') {
          // 复选框或单选按钮
          element.checked = !!value;
        } else if (type === 'file') {
          // 文件上传（在浏览器中无法直接操作）
          results[selector] = { success: false, error: '无法在浏览器中直接操作文件上传' };
          continue;
        } else {
          // 文本输入框
          element.value = value;
          // 触发输入事件
          element.dispatchEvent(new Event('input', { bubbles: true }));
          element.dispatchEvent(new Event('change', { bubbles: true }));
        }
      } else if (tagName === 'textarea') {
        // 文本区域
        element.value = value;
        element.dispatchEvent(new Event('input', { bubbles: true }));
        element.dispatchEvent(new Event('change', { bubbles: true }));
      } else if (tagName === 'select') {
        // 下拉选择框
        element.value = value;
        element.dispatchEvent(new Event('change', { bubbles: true }));
      } else {
        // 其他元素
        results[selector] = { success: false, error: '不支持的元素类型' };
        continue;
      }

      results[selector] = { success: true };
    }

    // 如果提供了提交按钮选择器，则点击提交
    if (submitSelector) {
      const submitButton = document.querySelector(submitSelector);
      if (submitButton) {
        submitButton.click();
        results.formSubmitted = { success: true };
      } else {
        results.formSubmitted = { success: false, error: '未找到提交按钮' };
      }
    }

    return { success: true, results };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

/**
 * 等待页面加载完成
 *
 * @param {Object} options - 等待选项
 * @returns {Object} 操作结果
 */
async function waitForPageLoad(options = {}) {
  try {
    const defaultOptions = {
      timeout: 30000,
      checkInterval: 100,
      readyState: 'complete',
      networkIdle: true,
      networkIdleTime: 500
    };

    const mergedOptions = { ...defaultOptions, ...options };

    // 等待文档就绪状态
    if (document.readyState !== mergedOptions.readyState) {
      return new Promise((resolve) => {
        const checkReadyState = () => {
          if (document.readyState === mergedOptions.readyState) {
            resolve({ success: true, readyState: document.readyState });
          } else {
            setTimeout(checkReadyState, mergedOptions.checkInterval);
          }
        };
        checkReadyState();
      });
    }

    // 等待网络空闲
    if (mergedOptions.networkIdle) {
      let lastNetworkActivity = Date.now();
      let isNetworkIdle = false;

      const originalFetch = window.fetch;
      const originalXHR = window.XMLHttpRequest.prototype.open;

      // 监听网络请求
      window.fetch = function(...args) {
        lastNetworkActivity = Date.now();
        return originalFetch.apply(this, args);
      };

      window.XMLHttpRequest.prototype.open = function(...args) {
        lastNetworkActivity = Date.now();
        return originalXHR.apply(this, args);
      };

      return new Promise((resolve) => {
        const checkNetworkIdle = () => {
          const timeSinceLastActivity = Date.now() - lastNetworkActivity;
          if (timeSinceLastActivity >= mergedOptions.networkIdleTime) {
            // 恢复原始方法
            window.fetch = originalFetch;
            window.XMLHttpRequest.prototype.open = originalXHR;
            resolve({ success: true, networkIdle: true });
          } else {
            setTimeout(checkNetworkIdle, mergedOptions.checkInterval);
          }
        };
        checkNetworkIdle();
      });
    }

    return { success: true };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

/**
 * 滚动到页面指定位置
 *
 * @param {Object} options - 滚动选项
 * @returns {Object} 操作结果
 */
function scrollPage(options = {}) {
  try {
    const defaultOptions = {
      behavior: 'smooth',
      top: null,
      left: null,
      selector: null,
      position: 'center' // 'start', 'center', 'end', 'nearest'
    };

    const mergedOptions = { ...defaultOptions, ...options };

    // 如果提供了选择器，滚动到元素
    if (mergedOptions.selector) {
      const element = document.querySelector(mergedOptions.selector);
      if (!element) {
        return { success: false, error: '未找到元素' };
      }

      element.scrollIntoView({
        behavior: mergedOptions.behavior,
        block: mergedOptions.position,
        inline: mergedOptions.position
      });

      return { success: true, scrolledToElement: true };
    }

    // 否则滚动到指定位置
    window.scrollTo({
      behavior: mergedOptions.behavior,
      top: mergedOptions.top,
      left: mergedOptions.left
    });

    return { success: true, scrolledToPosition: true };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

/**
 * 提取页面元数据
 *
 * @returns {Object} 页面元数据
 */
function extractPageMetadata() {
  try {
    // 提取标题
    const title = document.title;

    // 提取描述
    let description = '';
    const metaDescription = document.querySelector('meta[name="description"]');
    if (metaDescription) {
      description = metaDescription.getAttribute('content');
    }

    // 提取关键词
    let keywords = '';
    const metaKeywords = document.querySelector('meta[name="keywords"]');
    if (metaKeywords) {
      keywords = metaKeywords.getAttribute('content');
    }

    // 提取规范URL
    let canonicalUrl = '';
    const linkCanonical = document.querySelector('link[rel="canonical"]');
    if (linkCanonical) {
      canonicalUrl = linkCanonical.getAttribute('href');
    }

    // 提取Open Graph元数据
    const ogMetadata = {};
    const ogTags = document.querySelectorAll('meta[property^="og:"]');
    for (const tag of ogTags) {
      const property = tag.getAttribute('property').substring(3);
      ogMetadata[property] = tag.getAttribute('content');
    }

    // 提取Twitter卡片元数据
    const twitterMetadata = {};
    const twitterTags = document.querySelectorAll('meta[name^="twitter:"]');
    for (const tag of twitterTags) {
      const name = tag.getAttribute('name').substring(8);
      twitterMetadata[name] = tag.getAttribute('content');
    }

    return {
      success: true,
      url: window.location.href,
      title,
      description,
      keywords,
      canonicalUrl,
      ogMetadata,
      twitterMetadata
    };
  } catch (error) {
    return { success: false, error: error.message };
  }
}





// 导出所有函数
module.exports = {
  fillForm,
  waitForPageLoad,
  scrollPage,
  extractPageMetadata
};

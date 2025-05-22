// ====================================================================================
// 辅助函数：延迟执行
// ====================================================================================
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ====================================================================================
// 核心函数：提取当前Google搜索结果页面上的数据 (与之前版本类似，可能需要微调选择器)
// ====================================================================================
function extractCurrentPageGoogleResults() {
  const results = [];
  const searchResultElements = document.querySelectorAll(
    '.tF2Cxc.asEBEc, div.g.tF2Cxc, div.g.Ww4FFb, div.hlcw0c .MjjYud, div.kvgmc, .g, .RzdJxc' // 增加了更多可能的选择器
  );

  console.log(`当前页面找到 ${searchResultElements.length} 个潜在结果元素。`);

  searchResultElements.forEach((resultElement, index) => {
    let title = 'N/A';
    let url = 'N/A';
    let displayUrl = 'N/A';
    let summary = 'N/A';

    try {
      let titleLinkElement = resultElement.querySelector('h3 a, a h3, div[role="heading"] a, a div[role="heading"]');
      if (!titleLinkElement) {
        const h3Tag = resultElement.querySelector('h3');
        if (h3Tag && h3Tag.closest('a')) {
            titleLinkElement = h3Tag.closest('a');
            title = h3Tag.textContent.trim();
        } else if (h3Tag) { // 有些h3没有父a标签，但h3本身可能包含链接或其兄弟节点有链接
             title = h3Tag.textContent.trim();
             let siblingLink = h3Tag.nextElementSibling;
             while(siblingLink && siblingLink.tagName !== 'A') {
                 siblingLink = siblingLink.nextElementSibling;
             }
             if(siblingLink && siblingLink.href) url = siblingLink.href;
             else { // 尝试在h3的父元素中找链接
                 const parentAnchor = h3Tag.closest('a');
                 if(parentAnchor) url = parentAnchor.href;
             }
        }
      } else {
         const h3OrHeading = titleLinkElement.querySelector('h3, div[role="heading"]');
         title = h3OrHeading ? h3OrHeading.textContent.trim() : titleLinkElement.textContent.trim().split('\n')[0];
         url = titleLinkElement.href;
      }

      if (!titleLinkElement && title === 'N/A') { // 更通用的链接查找
        const generalLink = resultElement.querySelector('a[href^="http"], a[href^="/url"]');
        if(generalLink) {
            url = generalLink.href;
            let potentialTitle = generalLink.textContent.trim().split('\n')[0];
            if (potentialTitle && potentialTitle.length > 5 && potentialTitle.length < 150) {
                title = potentialTitle;
            }
        }
      }

      if(title === 'N/A' && resultElement.matches('.RzdJxc')){ // 视频结果
           const videoTitleElement = resultElement.querySelector('.fc9yUc.tNxQIb, .X5OiLe, .yDYNvb');
           if(videoTitleElement) title = videoTitleElement.textContent.trim();
           const videoLinkElement = resultElement.querySelector('a.X5OiLe, a.lcAnhc');
           if(videoLinkElement) url = videoLinkElement.href;
      }


      if (url && url.includes("/url?q=")) {
        try {
          const urlParams = new URLSearchParams(new URL(url, window.location.origin).search);
          if (urlParams.has('q')) {
            url = urlParams.get('q');
          }
        } catch (e) { console.warn("解析Google重定向链接时出错: ", url, e); }
      }

      const citeElement = resultElement.querySelector('cite, .VuuXrf, .UPmit, .tjvcx');
      if (citeElement) displayUrl = citeElement.textContent.trim();

      let summaryParts = [];
      const summarySelectors = [
        '.VwiC3b span:not([aria-hidden="true"])', '.MUxGbd span:not([aria-hidden="true"])', '.GI74hd span:not([aria-hidden="true"])',
        'span[data-sncf="1"]', 'div[data-sncf="2"] > div > span:not([aria-hidden="true"])', '.VwiC3b:not(:has(cite))',
        '.s3v9rd .OSrXXb', // 视频摘要
        'div[data-content-feature="1"]', // 另一种可能的摘要父容器
        '.st' // 有时摘要在这个类里
      ];
      summarySelectors.forEach(selector => {
        resultElement.querySelectorAll(selector).forEach(el => {
          if (!el.closest('h3') && !el.closest('cite') && !el.closest('a[href="' + url + '"]') && el.textContent.trim().length > 15) {
            summaryParts.push(el.textContent.trim());
          }
        });
      });
      if (summaryParts.length > 0) {
        summary = [...new Set(summaryParts)].join(' ').replace(/\s+/g, ' ').trim(); // 去重并合并
      } else {
         let tempElement = resultElement.cloneNode(true);
         tempElement.querySelectorAll('h3, a, cite, .fc9yUc.tNxQIb, .X5OiLe, .VuuXrf, .UPmit, .tjvcx, script, style, [aria-hidden="true"], .csDOgf, .wHYlTd, .P8P9y').forEach(el => el.remove()); // 移除更多无关元素
         summary = tempElement.textContent.replace(/\s+/g, ' ').trim();
         if (summary.length > 350) summary = summary.substring(0, 350) + "...";
      }
      if (!summary.replace(/\.\.\.$/, '').trim() || summary.toLowerCase().startsWith(title.toLowerCase().substring(0,15)) && title.length > 15) {
          summary = '未找到有效摘要。';
      }

      if (title && title !== 'N/A' && url && url !== 'N/A' && !url.startsWith('javascript:void')) {
        results.push({ title, url, displayUrl, summary });
      }
    } catch (e) {
      console.error(`提取结果 ${index + 1} 时发生错误:`, e, resultElement);
    }
  });
  return results;
}


// ====================================================================================
// 主控制函数 (修改版)
// ====================================================================================
async function startFullGoogleSearchAutomation(keyword) {
  const SESSION_KEY_STATE = 'googleFullSearchState';
  const MAX_PAGES_TO_SCRAPE = 10; // 可以调整最大翻页数

  let state = {
    keyword: keyword,
    currentPageNum: 1,
    allResults: [],
    currentPhase: "INITIATE_SEARCH", // PHASES: INITIATE_SEARCH, ON_GOOGLE_HOME, SCRAPING_RESULTS, FINISHED
    maxPages: MAX_PAGES_TO_SCRAPE
  };

  // 尝试从 sessionStorage 加载状态
  try {
    const storedState = sessionStorage.getItem(SESSION_KEY_STATE);
    if (storedState) {
      const parsedState = JSON.parse(storedState);
      // 如果传入了新的关键词，则重置状态，否则使用存储的状态
      if (keyword && parsedState.keyword === keyword) {
        state = parsedState;
        console.log("从 sessionStorage 恢复状态:", state);
      } else if (keyword) { // 新关键词，重置
        console.log("新关键词，重置存储状态。");
        state.keyword = keyword; // 更新关键词
        state.currentPageNum = 1;
        state.allResults = [];
        state.currentPhase = "INITIATE_SEARCH"; // 重新开始
      } else if (!keyword && parsedState.keyword) { // 没有传入关键词，但有存储的关键词
         state = parsedState;
         console.log("未提供关键词，使用存储的关键词继续:", state.keyword);
      }
      // 如果没有传入关键词也没有存储的关键词，则脚本无法执行
      if (!state.keyword) {
          console.error("错误：未提供搜索关键词，且无法从sessionStorage恢复。请使用 automateGoogleSearch('您的关键词') 调用。");
          sessionStorage.removeItem(SESSION_KEY_STATE);
          return;
      }
    } else if (!keyword) {
        console.error("错误：首次运行必须提供搜索关键词。请使用 automateGoogleSearch('您的关键词') 调用。");
        return;
    }
  } catch (e) {
    console.error("解析 sessionStorage 中的状态失败:", e);
    // 如果解析失败，并且没有传入关键词，则无法继续
    if (!keyword) {
        console.error("错误：无法从sessionStorage恢复状态且未提供关键词。");
        return;
    }
    // 如果有新关键词，则会覆盖旧的损坏状态
  }

  // 保存当前状态
  function saveState() {
    sessionStorage.setItem(SESSION_KEY_STATE, JSON.stringify(state));
  }

  function displayAndClearFinalResults() {
    console.log("=========================================");
    console.log("所有提取到的结果:");
    console.table(state.allResults);
    console.log(`总共 ${state.allResults.length} 条结果。`);
    console.log("可以使用 copy(JSON.parse(sessionStorage.getItem('googleFullSearchState')).allResults) 将JSON结果复制到剪贴板 (如果需要)。");
    sessionStorage.removeItem(SESSION_KEY_STATE); // 完成后清除状态
  }

  // --- 阶段处理 ---
  console.log(`当前阶段: ${state.currentPhase}, 关键词: "${state.keyword}", 页码: ${state.currentPageNum}`);

  if (state.currentPhase === "INITIATE_SEARCH") {
    if (!window.location.hostname.includes("google.com") || window.location.pathname !== "/") {
      console.log("当前不在 Google 首页，正在导航...");
      state.currentPhase = "ON_GOOGLE_HOME";
      saveState();
      window.location.href = "https://www.google.com/";
      return; // 导航后由自执行脚本接管
    } else {
      // 如果已经在首页，直接进入输入阶段
      state.currentPhase = "ON_GOOGLE_HOME";
      saveState();
      // 页面不需要重新加载，直接调用处理函数
      await processGoogleHomePage();
    }
  } else if (state.currentPhase === "ON_GOOGLE_HOME" && window.location.hostname.includes("google.com") && (window.location.pathname === "/" || window.location.pathname === "/webhp")) {
     await processGoogleHomePage();
  } else if (state.currentPhase === "SCRAPING_RESULTS" && window.location.href.includes("/search?q=")) {
     await processSearchResultsPage();
  } else if (state.currentPhase === "FINISHED") {
    displayAndClearFinalResults();
    return;
  } else {
    console.warn("脚本状态异常或当前页面不匹配，可能需要手动干预或重新开始。当前阶段:", state.currentPhase, "当前URL:", window.location.href);
    // 尝试重置到初始搜索，如果关键词存在
    if (state.keyword) {
        console.log("尝试重新导航到Google首页以开始搜索...");
        state.currentPhase = "INITIATE_SEARCH";
        state.currentPageNum = 1;
        state.allResults = [];
        saveState();
        window.location.href = "https://www.google.com/";
    } else {
        sessionStorage.removeItem(SESSION_KEY_STATE); // 清除无效状态
    }
  }

  async function processGoogleHomePage() {
    console.log("在 Google 首页，准备输入关键词并搜索...");
    await sleep(1500 + Math.random() * 1000); // 等待页面元素加载

    const searchInput = document.querySelector('textarea[name="q"], input[name="q"]');
    const searchButton = document.querySelector('input[name="btnK"], button[aria-label*="Search"], button[type="submit"]'); // 更通用的按钮选择

    if (searchInput && searchButton) {
      searchInput.value = state.keyword;
      console.log(`关键词 "${state.keyword}" 已输入。`);
      await sleep(500 + Math.random() * 500);

      // 优先选择非 "I'm Feeling Lucky" 的按钮
      let actualSearchButton = searchButton;
      if (searchButton.name === 'btnI' || (searchButton.getAttribute('aria-label') && searchButton.getAttribute('aria-label').toLowerCase().includes('feeling lucky'))) {
          const allButtons = document.querySelectorAll('input[name="btnK"], button[type="submit"]');
          for(let btn of allButtons){
              if(btn.name !== 'btnI' && (!btn.getAttribute('aria-label') || !btn.getAttribute('aria-label').toLowerCase().includes('feeling lucky'))){
                  actualSearchButton = btn;
                  break;
              }
          }
      }
      console.log("尝试点击搜索按钮:", actualSearchButton);
      state.currentPhase = "SCRAPING_RESULTS"; // 更新阶段为准备抓取结果
      saveState();
      actualSearchButton.click(); // 提交搜索
    } else {
      console.error("未找到搜索框或搜索按钮。请检查Google首页的HTML结构。");
      sessionStorage.removeItem(SESSION_KEY_STATE); // 出错则清除状态
    }
  }

  async function processSearchResultsPage() {
    console.log(`在搜索结果页，提取关键词 "${state.keyword}" 的第 ${state.currentPageNum} 页...`);
    await sleep(2500 + Math.random() * 1500); // 给页面更长时间加载

    const currentPageData = extractCurrentPageGoogleResults();
    console.log(`第 ${state.currentPageNum} 页提取到 ${currentPageData.length} 条结果。`);

    if (currentPageData.length > 0) {
      currentPageData.forEach(newItem => {
        if (!state.allResults.some(existingItem => existingItem.url === newItem.url && existingItem.title === newItem.title)) {
          state.allResults.push(newItem);
        }
      });
      console.table(currentPageData.slice(0, 5)); // 显示前5条，避免控制台过长
    } else {
      console.log("当前页未提取到新结果。");
    }

    if (state.currentPageNum >= state.maxPages) {
      console.log(`已达到最大翻页数 (${state.maxPages})，停止抓取。`);
      state.currentPhase = "FINISHED";
      saveState();
      displayAndClearFinalResults();
      return;
    }

    const nextPageButton = document.querySelector('a#pnnext, a[aria-label="Next page"], a[aria-label="下一页"]'); // Google 的下一页按钮选择器
    if (nextPageButton && nextPageButton.href) {
      console.log(`找到“下一页”按钮，准备跳转到第 ${state.currentPageNum + 1} 页...`);
      state.currentPageNum++;
      // currentPhase 保持 SCRAPING_RESULTS
      saveState();
      await sleep(500 + Math.random() * 500); // 点击前稍作停顿
      nextPageButton.click();
    } else {
      console.log("未找到“下一页”按钮，或已到达最后一页。提取完成。");
      state.currentPhase = "FINISHED";
      saveState();
      displayAndClearFinalResults();
    }
  }
}


// ====================================================================================
// 页面加载后自动执行的逻辑
// ====================================================================================
(function() {
  function onPageLoad() {
    const storedStateRaw = sessionStorage.getItem('googleFullSearchState');
    if (storedStateRaw) {
      try {
        const storedState = JSON.parse(storedStateRaw);
        if (storedState.keyword && storedState.currentPhase && storedState.currentPhase !== "FINISHED") {
          console.log("页面加载完成，检测到需要继续的自动化搜索任务...");
          // 延迟执行以确保页面完全渲染和所有脚本加载完毕
          setTimeout(() => {
            startFullGoogleSearchAutomation(storedState.keyword); // 传入存储的关键词继续
          }, 2000 + Math.random() * 1000); // 增加随机延迟
        } else if (storedState.currentPhase === "FINISHED") {
            console.log("上次搜索已标记为完成。如需重新开始，请调用 startFullGoogleSearchAutomation('您的关键词')");
        }
      } catch (e) {
        console.error("解析sessionStorage中的搜索状态失败:", e);
        sessionStorage.removeItem('googleFullSearchState'); // 清除损坏的状态
      }
    } else {
      // 这是脚本第一次在某个会话中加载（或者状态已被清除）
      console.log("网页抓取脚本已加载。请通过调用 startFullGoogleSearchAutomation('您的关键词') 来启动。");
    }
  }

  if (document.readyState === "complete" || (document.readyState !== "loading" && !document.documentElement.doScroll)) {
    onPageLoad();
  } else {
    document.addEventListener("DOMContentLoaded", onPageLoad);
  }
})();
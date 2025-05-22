function autoLoginAndChat(email, password, chatMessage) {
  console.log("Attempting to log in...");

  // --- Login Phase ---
  const emailInput = document.querySelector('span[data-testid="mg-login-email-input"] input.arco-input');
  const passwordInput = document.querySelector('span[data-testid="mg-login-password-input"] input.arco-input');
  const signInButton = document.querySelector('button[data-testid="mg-login-signin-btn"]');

  if (!emailInput) {
    console.error("错误：未能找到邮箱输入框。");
    return;
  }
  if (!passwordInput) {
    console.error("错误：未能找到密码输入框。");
    return;
  }
  if (!signInButton) {
    console.error("错误：未能找到登录按钮。");
    return;
  }

  emailInput.value = email;
  emailInput.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
  emailInput.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
  emailInput.dispatchEvent(new Event('blur', { bubbles: true, cancelable: true }));

  passwordInput.value = password;
  passwordInput.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
  passwordInput.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
  passwordInput.dispatchEvent(new Event('blur', { bubbles: true, cancelable: true }));

  signInButton.click();
  console.log(`使用账号: ${email} 尝试登录...`);

  // --- Post-Login Actions ---
  // Wait for the page to load after login attempt
  setTimeout(() => {
    console.log("登录后等待页面加载...");

    // --- Model Selection Phase ---
    const modelSelectorDropdown = document.querySelector('span[data-testid="mg-model-select"]');
    if (!modelSelectorDropdown) {
      console.error("错误：未能找到模型选择器下拉菜单。可能登录失败或页面结构不同。");
      return;
    }
    console.log("找到模型选择器，尝试点击...");
    modelSelectorDropdown.click();

    // Wait for dropdown options to become visible
    setTimeout(() => {
      console.log("等待模型选项出现...");
      const options = document.querySelectorAll('li[data-testid="mg-model-select-options"]');
      let targetOption = null;

      if (options.length === 0) {
          console.error("错误：模型选项列表为空。");
          return;
      }
      console.log(`找到 ${options.length} 个模型选项。`);

      options.forEach(option => {
        const modelNameElement = option.querySelector('.lh-16px.c-60.mt-4px'); // Element containing "claude-3-7-sonnet"
        if (modelNameElement && modelNameElement.textContent.trim().toLowerCase() === 'claude-3-7-sonnet') {
          targetOption = option;
        }
      });

      if (targetOption) {
        console.log("找到目标模型 'claude-3-7-sonnet'，尝试点击...");
        targetOption.click();

        // Wait for model selection to potentially update UI
        setTimeout(() => {
          console.log("模型已选择，准备输入聊天内容...");

          // --- Chat Input Phase ---
          const chatEditor = document.querySelector('div[data-testid="mg-home-message-input"] div.ql-editor');
          const sendButton = document.querySelector('div[data-testid="mg-home-send-message-btn"]');

          if (!chatEditor) {
            console.error("错误：未能找到聊天输入框 (ql-editor)。");
            return;
          }
          if (!sendButton) {
            console.error("错误：未能找到发送按钮。");
            return;
          }

          console.log("向聊天框输入内容:", chatMessage);
          // For Quill editors, it's best to set innerHTML with a paragraph,
          // and then dispatch input events if necessary, though often setting innerHTML
          // and then clicking send is enough if the editor updates its internal state.
          chatEditor.innerHTML = `<p>${chatMessage}</p>`; // Wrap in <p> for Quill
          // Optionally, remove placeholder if it doesn't hide automatically
          const placeholder = document.querySelector('div[data-testid="mg-home-message-input"] .qlEditorPlaceholder');
          if (placeholder) {
              placeholder.style.display = 'none';
          }


          // Dispatch an input event to ensure the editor recognizes the change
          chatEditor.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
          chatEditor.dispatchEvent(new Event('keyup', { bubbles: true, cancelable: true })); // Some editors might listen for keyup
          chatEditor.dispatchEvent(new Event('focus', { bubbles: true, cancelable: true })); // Focus before sending


          // Click the send button
          console.log("尝试点击发送按钮...");
          // A slight delay before sending might be needed if the input event processing is slow
          setTimeout(() => {
            sendButton.click();
            console.log("消息已发送。");
          }, 300); // Adjust delay if needed

        }, 1000); // Delay after selecting model

      } else {
        console.error("错误：未能找到模型选项 'claude-3-7-sonnet'。可用选项:");
        options.forEach(opt => console.log(opt.textContent.trim()));
      }
    }, 1500); // Delay for dropdown options to appear, adjust if needed

  }, 3000); // Delay after login click, adjust if page loads slower/faster
}

// --- 如何使用 ---
// 1. 打开浏览器开发者工具 (通常按 F12)
// 2. 切换到 "Console" (控制台) 标签页
// 3. 将上面的整个 autoLoginAndChat 函数代码粘贴到控制台，然后按 Enter 执行。
// 4. 然后调用该函数并传入您的账号、密码和聊天内容，例如：
//    autoLoginAndChat('xltyz@jdjf999.ggff.net', '4K=3Jd~iP@qbM(', '你好，Claude！');
//    将其中的参数替换为实际的值。
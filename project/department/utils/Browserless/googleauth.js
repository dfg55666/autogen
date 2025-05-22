async function automateGoogleSignup() {
    // 辅助函数：延迟指定毫秒数
    const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

    // 辅助函数：等待某个元素出现在DOM中且可交互
    async function waitForElement(selector, timeout = 15000) {
        const startTime = Date.now();
        while (Date.now() - startTime < timeout) {
            const element = document.querySelector(selector);
            if (element && element.offsetParent !== null) {
                const rect = element.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0 && rect.top < window.innerHeight && rect.bottom > 0 && rect.left < window.innerWidth && rect.right > 0) {
                    const elementAtPoint = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
                    if (element === elementAtPoint || element.contains(elementAtPoint)) {
                        return element;
                    }
                }
            }
            await delay(200);
        }
        console.error(`元素 ${selector} 在 ${timeout}ms 后未找到或不可见/不可交互。`);
        throw new Error(`元素 ${selector} 在 ${timeout}ms 后未找到或不可见/不可交互。`);
    }

    // 辅助函数：点击元素
    async function clickElement(selector, description) {
        try {
            const element = await waitForElement(selector);
            element.click();
            console.log(`已点击 ${description || selector}`);
        } catch (error) {
            console.error(`点击失败 ${description || selector}:`, error);
            throw error;
        }
    }

    // 辅助函数：在输入框中输入文本
    async function typeInElement(selector, text, description) {
        try {
            const element = await waitForElement(selector);
            element.value = text;
            // Dispatch events to ensure frameworks recognize the change
            element.dispatchEvent(new Event('input', { bubbles: true }));
            element.dispatchEvent(new Event('change', { bubbles: true }));
            element.focus(); // For Google's material components
            element.blur();  // For Google's material components
            console.log(`在 ${description || selector} 中输入了 "${text}"`);
        } catch (error) {
            console.error(`输入失败 ${description || selector}:`, error);
            throw error;
        }
    }
    
    // Helper function to dispatch input/change events (from user)
    function triggerEvents(element) {
        if (element) {
            element.dispatchEvent(new Event('input', { bubbles: true }));
            element.dispatchEvent(new Event('change', { bubbles: true }));
            // For Google's material components, focus and blur can also be important
            element.focus();
            element.blur();
        }
    }

    // Helper function for random integer (from user)
    function getRandomInt(min, max) {
        min = Math.ceil(min);
        max = Math.floor(max);
        return Math.floor(Math.random() * (max - min + 1)) + min;
    }

    // 辅助函数：查找并点击包含特定文本的按钮
    async function clickButtonByText(buttonText) {
        try {
            let textsToTry = Array.isArray(buttonText) ? buttonText : [buttonText];
            if (textsToTry.includes("下一步") && !textsToTry.includes("Next")) textsToTry.push("Next");
            if (textsToTry.includes("Next") && !textsToTry.includes("下一步")) textsToTry.push("下一步");

            for (const text of textsToTry) {
                console.log(`尝试点击包含文本 "${text}" 的按钮 (大小写不敏感)`);
                const lowerText = text.toLowerCase();
                const spans = Array.from(document.querySelectorAll('button span'));
                for (const span of spans) {
                    if (span.textContent.trim().toLowerCase() === lowerText) {
                        const parentButton = span.closest('button');
                        if (parentButton && !parentButton.disabled) {
                            parentButton.click();
                            console.log(`已点击 "${text}" 按钮 (通过 span 内容匹配)`);
                            return true;
                        }
                    }
                }
                const buttons = Array.from(document.querySelectorAll('button'));
                for (const btn of buttons) {
                    if (btn.disabled) continue;
                    const buttonContent = ((btn.textContent || "") + (btn.getAttribute('aria-label') || "") + Array.from(btn.querySelectorAll('div, span')).map(el => el.textContent || "").join(" ")).trim().toLowerCase();
                    if (buttonContent.includes(lowerText)) {
                        btn.click();
                        console.log(`已点击 "${text}" 按钮 (通过备用内容匹配: "${buttonContent.substring(0,50)}")`);
                        return true;
                    }
                }
            }
            console.error(`未找到包含文本 "${textsToTry.join('" 或 "')}" 的可点击按钮。`);
            return false;
        } catch (error) {
            console.error(`点击按钮失败 (尝试文本: "${JSON.stringify(buttonText)}"):`, error);
            throw error;
        }
    }

    // Helper function to select an option in a custom dropdown (adapted from user)
    async function selectCustomDropdownOption(dropdownId, optionValueToSelect) {
        let dropdownContainer, dropdownTrigger, optionsList, optionElement;
        try {
            dropdownContainer = await waitForElement(`#${dropdownId}`); // Use waitForElement
        } catch (e) {
            console.error(`Dropdown container with id "${dropdownId}" not found.`);
            return false;
        }

        try {
            dropdownTrigger = await waitForElement(`#${dropdownId} .VfPpkd-TkwUic`); // Use waitForElement
        } catch (e) {
            console.error(`Dropdown trigger for "${dropdownId}" not found.`);
            return false;
        }

        dropdownTrigger.click(); // 1. Click to open the dropdown
        await delay(300); // 2. Wait for options to render (increased delay slightly)

        try {
            // Ensure the options list is associated with the specific dropdown container
            optionsList = await waitForElement(`#${dropdownId} ul[jsname="rymPhb"]`); // Use waitForElement
        } catch (e) {
            console.error(`Options list (ul[jsname="rymPhb"]) for "${dropdownId}" not found after opening.`);
            // Attempt to close dropdown if it seems stuck open
            const menuElement = dropdownContainer.querySelector('.VfPpkd-xl07Ob-XxIAqe');
            if (menuElement && document.body.getAttribute('data-panel-opened-id') === menuElement.getAttribute('data-menu-uid')) {
                dropdownTrigger.click(); // Try clicking again to close
            }
            return false;
        }

        try {
            optionElement = await waitForElement(`#${dropdownId} ul[jsname="rymPhb"] li[data-value="${optionValueToSelect}"]`); // Use waitForElement
        } catch (e) {
            console.error(`Option with data-value "${optionValueToSelect}" for "${dropdownId}" not found.`);
            const menuElement = dropdownContainer.querySelector('.VfPpkd-xl07Ob-XxIAqe');
             if (menuElement && document.body.getAttribute('data-panel-opened-id') === menuElement.getAttribute('data-menu-uid')) {
                dropdownTrigger.click(); // Try clicking again to close
            }
            return false;
        }
        
        optionElement.click(); // 3. Click the specific option
        await delay(150); // Give a moment for UI to update after click

        // Manually update display text (from user's logic)
        const displaySpan = dropdownTrigger.querySelector('.VfPpkd-uusGie-fmcmS[jsname="Fb0Bif"]');
        const placeholderSpan = dropdownTrigger.querySelector('.VfPpkd-NLUYnc-V67aGc[jsname="V67aGc"]'); // This is the label
        
        if (displaySpan && optionElement) { // Ensure optionElement is valid before accessing textContent
            displaySpan.textContent = optionElement.textContent.trim();
        }
        if (placeholderSpan) {
            // This class makes the placeholder float up and indicates a value has been selected
            placeholderSpan.classList.add('VfPpkd-NLUYnc-V67aGc-OWXEXe-TATcMc');
        }
        return true;
    }

    let chosenEmail = "未能获取@gmail.com";

    try {
        console.log("开始谷歌账户创建自动化脚本...");
        await delay(1000);

        // 步骤 1: 填写名字和姓氏
        console.log("步骤 1: 填写姓名信息...");
        const lastNames = ["Li", "Wang", "Zhang", "Liu", "Chen", "Yang", "Zhao", "Huang", "Zhou", "Wu", "Xu", "Sun", "Hu", "Zhu", "Gao", "Lin", "He", "Guo", "Ma", "Luo"];
        const firstNamesChars = ["Wei", "Fang", "Min", "Jing", "Hui", "Qiang", "Lei", "Yan", "Juan", "Ting", "Mei", "Na", "Ping", "Fei", "Shu", "Yi", "Xin", "Jia", "Ling", "Rong", "Bo", "Chao", "Dong", "Feng", "Gang", "Hao", "Jun", "Kai", "Liang", "Peng", "Tao", "Xiang", "Yong", "Zhi"];
        const randomLastName = lastNames[Math.floor(Math.random() * lastNames.length)];
        let randomFirstName = firstNamesChars[Math.floor(Math.random() * firstNamesChars.length)];
        if (Math.random() > 0.5) randomFirstName += firstNamesChars[Math.floor(Math.random() * firstNamesChars.length)].toLowerCase();
        const randomNumber = Math.floor(Math.random() * 100);
        await typeInElement("#firstName", randomFirstName + randomNumber, "名字输入框 (First name)");
        await typeInElement("#lastName", randomLastName, "姓氏输入框 (Last name)");
        await delay(500);
        if (!await clickButtonByText(["下一步", "Next"])) {
            await clickElement("button.VfPpkd-LgbsSe.VfPpkd-LgbsSe-OWXEXe-k8QpJ.VfPpkd-RLmnJb", "姓名后的'下一步'按钮 (备用CSS选择器)");
        }
        await delay(3000);

        // 步骤 2: 填写生日和性别 (New logic from user)
        console.log("步骤 2: 填写生日和性别 (新逻辑)...");
        
        const yearInput = document.getElementById('year');
        if (yearInput) {
            const randomYear = getRandomInt(2003, 2006);
            yearInput.value = randomYear;
            triggerEvents(yearInput);
            console.log(`已设置年份为: ${randomYear}`);
        } else {
            console.error("年份输入框 (#year) 未找到。");
            throw new Error("年份输入框 (#year) 未找到。");
        }
        await delay(200);

        const dayInput = document.getElementById('day');
        if (dayInput) {
            const randomDay = getRandomInt(1, 28);
            dayInput.value = randomDay;
            triggerEvents(dayInput);
            console.log(`已设置日期为: ${randomDay}`);
        } else {
            console.error("日期输入框 (#day) 未找到。");
            throw new Error("日期输入框 (#day) 未找到。");
        }
        await delay(200);

        const randomMonthValue = getRandomInt(1, 12);
        console.log(`尝试设置月份值为: ${randomMonthValue}`);
        const monthSet = await selectCustomDropdownOption('month', randomMonthValue.toString());
        if (monthSet) console.log(`月份选择成功，值为: ${randomMonthValue}`);
        else console.error(`月份选择失败，值为: ${randomMonthValue}`);
        await delay(500);

        const genderOptions = [
            { value: "1", name: "Male" },
            { value: "2", name: "Female" },
            { value: "3", name: "Rather not say" },
            { value: "4", name: "Custom" }
        ];
        const randomGenderOption = genderOptions[getRandomInt(0, genderOptions.length - 1)];
        console.log(`尝试设置性别为: ${randomGenderOption.name} (值: ${randomGenderOption.value})`);
        const genderSet = await selectCustomDropdownOption('gender', randomGenderOption.value);
        if (genderSet) console.log(`性别选择成功: ${randomGenderOption.name}`);
        else console.error(`性别选择失败: ${randomGenderOption.name}`);
        await delay(500);

        if (randomGenderOption.value === "4" && genderSet) {
            await delay(500);
            try {
                const customGenderContainer = await waitForElement('#customGender', 5000);
                const customGenderInput = customGenderContainer.querySelector('input[type="text"]');
                if (customGenderInput) {
                    const parentVisibilityCheck = customGenderInput.closest('.XTGJqd');
                    if (parentVisibilityCheck && (parentVisibilityCheck.style.display !== 'none' && !parentVisibilityCheck.classList.contains('L6cTce'))) {
                        customGenderInput.value = "CustomValue " + getRandomInt(1, 100);
                        triggerEvents(customGenderInput);
                        console.log(`已设置自定义性别为: ${customGenderInput.value}`);
                    } else {
                        console.warn("自定义性别输入框存在但当前不可见。跳过填写。");
                    }
                } else {
                    console.error("在 #customGender 内未找到自定义性别文本输入框。");
                }
            } catch (e) {
                console.error("查找自定义性别输入框容器 (#customGender) 失败:", e.message);
            }
        }
        await delay(500);

        if (!await clickButtonByText(["下一步", "Next"])) {
            await clickElement("button.VfPpkd-LgbsSe.VfPpkd-LgbsSe-OWXEXe-k8QpJ.VfPpkd-RLmnJb", "生日性别后的'下一步'按钮 (备用CSS选择器)");
        }
        await delay(5000);

        // 步骤 3: 选择用户名 (选择第一个推荐)
        console.log("步骤 3: 选择第一个推荐的用户名...");
        let firstEmailOptionContainer;
        let firstRadioButtonToClick;
        let emailTextElementToRead;

        try {
            // Selector for the container of the first email suggestion option, based on provided HTML structure
            // radiogroup (jscontroller="wPRNsd") -> slot (jsname="bN97Pc") -> first option container (div[jsname="wQNmvb"]:first-child)
            const firstOptionSelector = 'div[jscontroller="wPRNsd"][role="radiogroup"] > span[jsname="bN97Pc"] > div[jsname="wQNmvb"]:first-child';
            firstEmailOptionContainer = await waitForElement(firstOptionSelector, 20000);
            
            if (firstEmailOptionContainer) {
                // Inside the first option container, find the actual radio button to click
                firstRadioButtonToClick = firstEmailOptionContainer.querySelector('div[jsname="ornU0b"][role="radio"]');
                // And find the element containing the email text
                emailTextElementToRead = firstEmailOptionContainer.querySelector('div[jsname="CeL6Qc"]');

                if (firstRadioButtonToClick && emailTextElementToRead) {
                    const suggestedEmailText = emailTextElementToRead.textContent.trim();
                    
                    if (suggestedEmailText && suggestedEmailText.includes('@')) { // Basic check if it's an email
                        chosenEmail = suggestedEmailText; // Store the full email
                        console.log("捕获到的第一个推荐邮箱:", chosenEmail);

                        firstRadioButtonToClick.click(); // Click the radio button
                        console.log("已点击第一个推荐的邮箱单选按钮。");
                        
                        await delay(200); // Brief pause for UI to update
                        if (firstRadioButtonToClick.getAttribute('aria-checked') !== 'true') {
                            console.warn("点击后，单选按钮未显示为已选中状态。可能存在交互问题或页面结构与预期不符。");
                        }

                    } else {
                        console.error("未能从第一个推荐选项中提取有效的邮箱文本。获取到的文本:", `"${suggestedEmailText}"`);
                        throw new Error("未能从第一个推荐选项中提取有效的邮箱文本。");
                    }
                } else {
                    if (!firstRadioButtonToClick) console.error("在第一个推荐选项容器中未找到可点击的单选按钮元素 (div[jsname='ornU0b'][role='radio'])。");
                    if (!emailTextElementToRead) console.error("在第一个推荐选项容器中未找到邮箱文本元素 (div[jsname='CeL6Qc'])。");
                    throw new Error("第一个推荐邮箱选项的内部结构不完整或与预期不符。");
                }
            } else {
                console.error("未能找到第一个推荐邮箱的容器元素。选择器:", firstOptionSelector);
                throw new Error("未能找到第一个推荐邮箱的容器元素。");
            }
        } catch (e) {
            console.error("选择第一个推荐邮箱时发生错误:", e.message);
            // If this critical step fails, re-throw to stop the script.
            throw e; 
        }
        await delay(1000);


        if (!await clickButtonByText(["下一步", "Next"])) {
            await clickElement("button.VfPpkd-LgbsSe.VfPpkd-LgbsSe-OWXEXe-k8QpJ.VfPpkd-RLmnJb", "选择用户名后的'下一步'按钮 (备用CSS选择器)");
        }
        await delay(4000);

        // 步骤 4: 输入密码
        console.log("步骤 4: 输入密码...");
        const userPassword = "Password123!Test"; // 请使用强密码!
        await typeInElement("input[name='Passwd']", userPassword, "密码输入框");
        await typeInElement("input[name='PasswdAgain']", userPassword, "确认密码输入框");
        await delay(500);

        if (!await clickButtonByText(["下一步", "Next"])) {
            await clickElement("button.VfPpkd-LgbsSe.VfPpkd-LgbsSe-OWXEXe-k8QpJ.VfPpkd-RLmnJb", "输入密码后的'下一步'按钮 (备用CSS选择器)");
        }
        await delay(5000);

        console.log("自动化脚本已完成至密码提交步骤。");
        console.log("最终选定的邮箱地址是:", chosenEmail);
        alert(`自动化脚本初步完成。\n选定的邮箱地址 (请查看控制台): ${chosenEmail}\n\n后续步骤 (如电话验证, CAPTCHA, 同意条款等) 很可能需要您手动完成。`);

    } catch (error) {
        console.error("自动化脚本执行失败:", error);
        alert("自动化脚本遇到错误。请检查浏览器控制台获取详细信息。\n您可能需要手动解决CAPTCHA，或者页面结构已发生变化导致选择器失效。");
        if (chosenEmail !== "未能获取@gmail.com") {
            console.log("发生错误前，记录的邮箱地址是:", chosenEmail);
        }
    }
}

console.log("谷歌账户注册自动化脚本已加载。");
console.warn("重要提示：\n" +
    "1. 此脚本通过模拟用户界面操作进行，可能随时因Google更新页面结构而失效。\n" +
    "2. Google有反机器人机制 (如CAPTCHA)，此脚本无法绕过。如遇CAPTCHA，需手动完成。\n" +
    "3. 请负责任地使用此脚本，仅用于学习和测试目的。\n" +
    "4. 执行脚本前，请确保您已打开Google账户创建的第一步页面 (填写姓名的页面)。\n" +
    "5. 要启动自动化，请在控制台输入 `automateGoogleSignup()` 然后按 Enter。");

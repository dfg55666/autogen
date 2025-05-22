function autoFillLiuYaoForm(divinationQuestion, divinationNumber, customTime = "") {
    try {
        // 1. 设置占卜问题
        if (!divinationQuestion || divinationQuestion.trim() === "") {
            console.error("占卜问题未提供或为空，脚本终止。");
            return;
        }
        const questionInput = document.querySelector('input[name="g_quetitle"]');
        if (questionInput) {
            questionInput.value = divinationQuestion;
        } else {
            console.error("未找到占卜问题输入框。");
            return;
        }

        // 2. 选择占事分类为 "杂占/其它" (value="28")
        const categorySelect = document.querySelector('select[name="typeid"]');
        if (categorySelect) {
            categorySelect.value = "28";
        } else {
            console.error("未找到占事分类选择框。");
            return;
        }

        // 3. 选择卦主性别为 "男" (value="1")
        const genderMaleRadio = document.querySelector('input[name="g_sex"][value="1"]');
        if (genderMaleRadio) {
            genderMaleRadio.checked = true;
        } else {
            console.error("未找到性别为男的单选按钮。");
            return;
        }

        // 4. 选择起卦方式为 "单数起卦"
        const singleNumberMethodButton = document.getElementById('type3');
        if (singleNumberMethodButton && typeof chooseType === 'function') {
            singleNumberMethodButton.click(); // 确保相关的视图被正确显示和初始化
            console.log("已选择'单数起卦'方式。");
        } else {
            console.error("未找到'单数起卦'按钮或 chooseType 函数未定义。");
            // 尝试直接确保 typeView3 可见，但这可能不完整
            const typeView3 = document.querySelector('.typeView3');
            if (typeView3) {
                typeView3.style.width = 'auto';
                typeView3.style.height = 'auto';
                typeView3.style.zIndex = '99';
                typeView3.style.overflow = 'hidden';
                console.warn("尝试直接显示 typeView3，但可能未触发所有页面逻辑。");
            } else {
                console.error("未找到 .typeView3 容器。");
                return;
            }
        }

        // 等待一小段时间，确保 typeView3 中的元素已准备好
        setTimeout(() => {
            // 5. 在 "单数起卦" (typeView3) 中输入数字
            if (!divinationNumber || divinationNumber.toString().trim() === "") {
                console.error("起卦数字未提供或为空，脚本终止。");
                return;
            }
            const numberInputInTypeView3 = document.querySelector('.typeView3 input[name="g_number3"]');
            if (numberInputInTypeView3) {
                numberInputInTypeView3.value = divinationNumber.toString();
            } else {
                console.error("在'单数起卦'视图中未找到数字输入框。");
                return;
            }

            // 6. 在 "单数起卦" (typeView3) 中设置可选时间
            const timeInputInTypeView3 = document.querySelector('.typeView3 input#g_submittime2');
            const hiddenSubtimeInput = document.querySelector('input[name="subtime"]');

            if (customTime && customTime.trim() !== "") {
                if (timeInputInTypeView3) {
                    timeInputInTypeView3.value = customTime.trim();
                } else {
                    console.error("在'单数起卦'视图中未找到时间输入框 g_submittime2。");
                }
                if (hiddenSubtimeInput) {
                    hiddenSubtimeInput.value = customTime.trim();
                } else {
                     console.error("未找到隐藏的 subtime 输入框。");
                }
            } else {
                console.log("未提供自定义时间，将使用页面默认的当前时间。");
                // 确保时间输入框与隐藏的subtime同步（如果一个有值而另一个没有）
                if (timeInputInTypeView3 && !timeInputInTypeView3.value && hiddenSubtimeInput && hiddenSubtimeInput.value) {
                    timeInputInTypeView3.value = hiddenSubtimeInput.value;
                } else if (timeInputInTypeView3 && timeInputInTypeView3.value && hiddenSubtimeInput && !hiddenSubtimeInput.value) {
                    hiddenSubtimeInput.value = timeInputInTypeView3.value;
                }
            }

            // 7. 找到并点击 "单数起卦" (typeView3) 中的 "开始起卦" 按钮
            const startButton = document.querySelector('.typeView3 input[type="button"][value="开始起卦"]');
            if (startButton && typeof toPaiPan === 'function') {
                console.log("表单已填写完毕，准备点击'开始起卦'按钮...");
                startButton.click();
                console.log("已点击'开始起卦'按钮。");
            } else {
                console.error("在'单数起卦'视图中未找到'开始起卦'按钮或 toPaiPan 函数未定义。");
            }
        }, 100); // 100毫秒延迟

    } catch (error) {
        console.error("脚本执行过程中发生错误:", error);
    }
}

// --- 如何调用函数 ---

// 示例1: 提供所有参数，包括自定义时间
// autoFillLiuYaoForm(
//     "测试今日运势如何？",  // 占卜问题
//     "12345",              // 起卦数字
//     "2025-05-16 10:30:00" // 自定义起卦时间 (格式 YYYY-MM-DD hh:mm 或 YYYY-MM-DD hh:mm:ss)
// );

// 示例2: 不提供自定义时间 (将使用页面默认的当前时间)
// autoFillLiuYaoForm(
//     "下午的会议是否顺利？", // 占卜问题
//     "789"                  // 起卦数字
// );

// 示例3: 如果需要，可以先定义变量再传入
// const myQuestion = "这个项目前景如何";
// const myNumber = "668";
// const myTime = "2025-05-15 15:00:00";
// autoFillLiuYaoForm(myQuestion, myNumber, myTime);

// 要实际运行，请取消注释上面的一个示例调用，并根据您的需要修改参数值。
// 例如，要运行示例2:
// autoFillLiuYaoForm("下午的会议是否顺利？", "789");
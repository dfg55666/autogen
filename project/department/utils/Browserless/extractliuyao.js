function extractAndFormatYaoData() {
    let output = "";

    // 尝试获取页面内容
    const pageContent = document.body.innerHTML;
    console.log("页面内容长度:", pageContent.length);

    // 检查页面是否包含关键内容
    if (pageContent.includes('yaociXiangXi')) {
        console.log("找到爻辞详细元素");
    } else {
        console.log("未找到爻辞详细元素");
    }

    // 尝试获取主容器
    const lyTextElement = document.getElementById('ly_text');

    if (!lyTextElement) {
        console.error("Main container #ly_text not found.");

        // 尝试使用替代方法提取内容
        const yaociElement = document.querySelector('.yaociXiangXi');
        if (yaociElement) {
            console.log("找到爻辞详细元素，尝试提取内容");
            const yaociText = yaociElement.textContent
                .split('\n')
                .map(line => line.trim())
                .filter(line => line)
                .join('\n');

            return "从爻辞详细元素提取的内容:\n\n" + yaociText;
        }

        // 尝试获取页面上的所有文本
        const allText = document.body.textContent
            .split('\n')
            .map(line => line.trim())
            .filter(line => line)
            .join('\n');

        return "未找到主容器，页面文本内容:\n\n" + allText.substring(0, 1000) + "...";
    }

    const getText = (selector, parent = lyTextElement, trim = true, getAllTextNodes = false) => {
        const el = parent.querySelector(selector);
        if (!el) return 'N/A';

        let text = "";
        if (getAllTextNodes) {
            // Collect all direct text child nodes
            el.childNodes.forEach(node => {
                if (node.nodeType === Node.TEXT_NODE) {
                    text += node.textContent;
                }
            });
        } else {
            text = el.textContent;
        }

        if (trim) {
            text = text.trim().replace(/\s+/g, ' ');
        }
        return text;
    };

    // --- System Title ---
    let systemTitle = getText('div[style*="text-align:center"] > b[style*="font-size: 16px"]').trim();
    if (systemTitle !== "易师汇六爻在线排盘系统") {
        output += `**${systemTitle}**\n\n`;
    }

    // --- 占类, 起卦方式 ---
    let 占类Text = 'N/A';
    let 起卦方式Text = 'N/A';
    const zhanLeiOuterSpan = Array.from(lyTextElement.querySelectorAll('div > span'))
        .find(s => s.querySelector('span[style*="font-weight: bold"]')?.textContent.trim() === "占类：" &&
                   s.querySelector('b[style*="margin-left:20px"]')?.textContent.trim() === "起卦方式：");

    if (zhanLeiOuterSpan) {
        const 占类LabelNode = zhanLeiOuterSpan.querySelector('span[style*="font-weight: bold"]');
        if (占类LabelNode && 占类LabelNode.nextSibling && 占类LabelNode.nextSibling.nodeType === Node.TEXT_NODE) {
            占类Text = 占类LabelNode.nextSibling.textContent.trim().replace(/\s+/g, ' ');
        }

        const 起卦方式LabelNode = zhanLeiOuterSpan.querySelector('b[style*="margin-left:20px"]');
        if (起卦方式LabelNode && 起卦方式LabelNode.nextElementSibling && 起卦方式LabelNode.nextElementSibling.tagName === 'SPAN') {
            起卦方式Text = 起卦方式LabelNode.nextElementSibling.textContent.trim().replace(/\s+/g, ' ');
        } else if (起卦方式LabelNode && 起卦方式LabelNode.nextSibling && 起卦方式LabelNode.nextSibling.nodeType === Node.TEXT_NODE && 起卦方式LabelNode.nextSibling.textContent.trim() !== "") {
             起卦方式Text = 起卦方式LabelNode.nextSibling.textContent.trim().split(/\s{2,}/)[0];
        }
    }
    output += `**占类：** ${占类Text}\n`;
    output += `**起卦方式：** ${起卦方式Text}\n`;

    // --- 排卦 ---
    let 排卦Value = "";
    const 排卦LabelElement = Array.from(lyTextElement.querySelectorAll('div > span > b'))
                                .find(b => b.textContent.trim() === "排卦：");
    if (排卦LabelElement && 排卦LabelElement.nextSibling) {
        排卦Value = 排卦LabelElement.nextSibling.nodeType === Node.TEXT_NODE ? 排卦LabelElement.nextSibling.textContent.trim() : "";
        if (排卦LabelElement.nextElementSibling && 排卦LabelElement.nextElementSibling.tagName === 'A') {
            排卦Value += " " + 排卦LabelElement.nextElementSibling.textContent.trim();
        }
    }
    排卦Value = 排卦Value.replace(/\s+/g, ' ').trim();

    if (排卦Value !== "易师汇六爻排盘 pp.yishihui.net") {
        output += `**排卦：** ${排卦Value || 'N/A'}\n`;
    }


    // --- 公历, 节气, 干支 ---
     const getLabeledSiblingText = (labelTextRegex) => {
        const labelElement = Array.from(lyTextElement.querySelectorAll('b'))
            .find(b => labelTextRegex.test(b.textContent.trim()));
        if (labelElement && labelElement.nextElementSibling && labelElement.nextElementSibling.tagName === 'SPAN') {
            // For 公历
            if (labelElement.nextElementSibling.querySelector('span')) {
                 return labelElement.nextElementSibling.querySelector('span').textContent.trim().replace(/\s+/g, ' ');
            }
            // For 干支, which has multiple following elements
            let text = labelElement.nextElementSibling.textContent.trim();
            let next = labelElement.nextElementSibling.nextElementSibling;
            while(next && (next.tagName === 'B' || next.tagName === 'SPAN')) {
                text += " " + next.textContent.trim();
                next = next.nextElementSibling;
            }
             return text.replace(/\s+/g, ' ').trim();
        }
        return 'N/A';
    };
    output += `**公历：** ${getLabeledSiblingText(/^公历：$/)}\n`;

    let 节气Text = 'N/A';
    const 节气LabelNode = Array.from(lyTextElement.querySelectorAll('b')).find(b => b.textContent.trim() === "节气：");
    if (节气LabelNode && 节气LabelNode.nextElementSibling && 节气LabelNode.nextElementSibling.tagName === 'SPAN' && 节气LabelNode.nextElementSibling.style.fontSize === '13px') {
        节气Text = 节气LabelNode.nextElementSibling.textContent.trim().replace(/\s*~\s*/g, '~');
    }
    output += `**节气：** ${节气Text}\n`;
    output += `**干支：** ${getLabeledSiblingText(/^干支：$/)}\n`;


    // --- 卦身, 世身 ---
    // 使用新的提取函数获取卦身世身信息
    function extractGuaShenShiShen() {
        let guaShen = null;
        let shiShen = null;
        const allSpans = document.querySelectorAll('span'); // 获取页面上所有span

        for (let i = 0; i < allSpans.length; i++) {
            const span = allSpans[i];
            const textContent = span.textContent || span.innerText || "";

            const regex = /卦身：\s*(\S+)\s*世身：\s*(\S+)/;
            const match = textContent.match(regex);

            if (match && match[1] && match[2]) {
                guaShen = match[1].trim();
                shiShen = match[2].trim();
                break;
            }
        }

        return {
            卦身: guaShen || "未找到",
            世身: shiShen || "未找到"
        };
    }

    // 调用函数获取结果
    const guaInfo = extractGuaShenShiShen();

    if (guaInfo && guaInfo.卦身 !== "未找到" && guaInfo.世身 !== "未找到") {
        output += `**卦身：** ${guaInfo.卦身}\n`;
        output += `**世身：** ${guaInfo.世身}\n\n`;
    } else {
        // 如果新方法失败，尝试使用原来的方法
        const 卦身世身ParentSpan = Array.from(lyTextElement.querySelectorAll('div > span'))
            .find(s => s.textContent.includes("卦身：") && s.textContent.includes("世身："));
        if (卦身世身ParentSpan) {
            let 卦身Text = 'N/A', 世身Text = 'N/A';
            const 卦身Label = Array.from(卦身世身ParentSpan.querySelectorAll('b')).find(b => b.textContent.trim() === "卦身：");
            if (卦身Label && 卦身Label.nextSibling && 卦身Label.nextSibling.nodeType === Node.TEXT_NODE) {
               卦身Text = 卦身Label.nextSibling.textContent.trim();
            }
            const 世身Label = Array.from(卦身世身ParentSpan.querySelectorAll('b')).find(b => b.textContent.trim() === "世身：");
            if (世身Label && 世身Label.nextSibling && 世身Label.nextSibling.nodeType === Node.TEXT_NODE) {
               世身Text = 世身Label.nextSibling.textContent.trim();
            }
            output += `**卦身：** ${卦身Text}\n`;
            output += `**世身：** ${世身Text}\n\n`;
        } else {
            output += "**卦身：** N/A\n";
            output += "**世身：** N/A\n\n";
        }
    }


    // --- 神煞 ---
    output += "**神煞：** ";
    const shenshaDiv = Array.from(lyTextElement.querySelectorAll('div.subtime')).find(d => d.textContent.includes("神煞："));
    if (shenshaDiv) {
        let shenshaItems = [];
        // Get items from the first span (visible ones)
        const firstSpanGroup = shenshaDiv.querySelector('span:not(.shenshaBox)');
        if (firstSpanGroup) {
            firstSpanGroup.querySelectorAll('span:not(.shenshaShow)').forEach(s => {
                const text = s.textContent.trim();
                if (text) shenshaItems.push(text);
            });
        }
        // Get items from all shenshaBox spans
        shenshaDiv.querySelectorAll('span.shenshaBox > span').forEach(s => {
            const text = s.textContent.trim();
            if (text) shenshaItems.push(text);
        });
        output += shenshaItems.join('　') + "\n\n";
    } else {
        output += "N/A\n\n";
    }
    output += "---\n\n";


    // --- Hexagram Table ---
    output += "**排盘结构：**\n\n";
    const liushenBox = lyTextElement.querySelector('.liushenbox');
    if (liushenBox) {
        // 提取卦名信息
        const hexagramNamesDiv = liushenBox.querySelector('ul > div[style*="font-weight: bold"]');
        let mainHexName = 'N/A';
        let changedHexName = 'N/A';

        if (hexagramNamesDiv) {
            const divs = hexagramNamesDiv.querySelectorAll('div');
            if (divs.length >= 2) {
                // For: <div style="width:50%">六神　<span style="color:blue">兑为泽</span>(兑宫)</div>
                // We want "兑为泽(兑宫)"
                let mainHexTextContent = divs[0].textContent.trim();
                mainHexName = mainHexTextContent.replace(/^六神\s*　\s*/, '').trim();

                // For: <div style="">　　<span style="color:blue;">水泽节</span>(坎宫)</div>
                // We want "水泽节(坎宫)"
                changedHexName = divs[1].textContent.trim().replace(/^　　\s*/, '').trim();
            }
        }
        output += `六神　 ${mainHexName}　　 ${changedHexName}\n`;

        // Process each <li> for Yao lines
        try {
            const yaoRows = liushenBox.querySelectorAll('ul > li');

            yaoRows.forEach(row => {
                let liuShen = 'N/A';
                let mainYaoText = 'N/A';
                let changedYaoText = 'N/A';

                const mainYaoDiv = row.querySelector('div[style*="width:50%"]');
                const changedYaoDiv = row.querySelector('div:not([style*="width:50%"])');

                if (mainYaoDiv) {
                    // Extract Liu Shen: It's the first text part in mainYaoDiv.
                    // e.g., "玄武　" from "玄武　 父母丁未土..."
                    let firstTextContent = "";
                    for (let k = 0; k < mainYaoDiv.childNodes.length; k++) {
                        const node = mainYaoDiv.childNodes[k];
                        if (node.nodeType === Node.TEXT_NODE && node.textContent.trim() !== "") {
                            firstTextContent = node.textContent; // Gets "玄武　 " (includes trailing space)
                            break;
                        }
                    }
                    liuShen = firstTextContent.trim().split(/\s+/)[0]; // "玄武"
                    if (!liuShen) liuShen = 'N/A';


                    // Extract Main Yao Text: The rest of mainYaoDiv's text content.
                    const fullMainYaoDivText = mainYaoDiv.textContent.trim(); // "玄武　 父母丁未土▅　▅世"

                    if (fullMainYaoDivText.startsWith(liuShen)) {
                        // Remove the liuShen part from the beginning
                        mainYaoText = fullMainYaoDivText.substring(liuShen.length).trim(); // "父母丁未土▅　▅世"
                    } else {
                        // Fallback if liuShen wasn't exactly at the start after trimming (less likely with current logic)
                        mainYaoText = fullMainYaoDivText;
                    }
                    // Normalize multiple spaces to a single space, but try to preserve ideographic spaces if they are distinct
                    mainYaoText = mainYaoText.replace(/\s+/g, ' '); // General space normalization
                }

                if (changedYaoDiv) {
                    changedYaoText = changedYaoDiv.textContent.trim();
                    changedYaoText = changedYaoText.replace(/\s+/g, ' '); // General space normalization
                }

                // To better match the desired output formatting with ideographic spaces:
                // Let's refine how text is cleaned to preserve specific spacing.
                // Instead of .replace(/\s+/g, ' '), just use .trim() for mainYaoText and changedYaoText
                // if the source HTML already has the desired spacing.
                // From your HTML, `mainYaoDiv.textContent` is like "玄武　 父母丁未土▅　▅世"
                // `liuShen` is "玄武"
                // `fullMainYaoDivText.substring(liuShen.length).trim()` -> "父母丁未土▅　▅世" (ideographic space is preserved by trim)

                // Re-evaluate mainYaoText and changedYaoText extraction for better space preservation:
                if (mainYaoDiv) {
                    // liuShen extraction as above is fine.
                    const fullMainYaoDivText = mainYaoDiv.textContent; // Don't trim yet
                    let potentialMainYao = "";
                    if (fullMainYaoDivText.includes(liuShen)) { // Check if liuShen is present
                        potentialMainYao = fullMainYaoDivText.substring(fullMainYaoDivText.indexOf(liuShen) + liuShen.length);
                    } else {
                        potentialMainYao = fullMainYaoDivText; // Fallback
                    }
                    mainYaoText = potentialMainYao.trim().replace(/\s+/g, ' '); // Trim and normalize spaces
                }

                if (changedYaoDiv) {
                    changedYaoText = changedYaoDiv.textContent.trim().replace(/\s+/g, ' '); // Trim and normalize spaces
                }


                // Format and append the combined line
                // The spacing "　　" (two ideographic spaces) and "　　　" (three ideographic spaces) is from your original code.
                output += `${liuShen}　　${mainYaoText}　　　 ${changedYaoText}\n`;
            });
        } catch (error) {
            console.error("提取爻位信息时出错:", error);
            output += "提取爻位信息时出错\n";
        }
    } else {
        output += "Hexagram table (.liushenbox) not found.\n";
    }
    output += "\n---\n\n";

    // --- Gua Ci / Yao Ci ---
    output += `**卦名 卦辞爻辞：**\n\n`;

    // 使用新的提取函数获取卦辞爻辞
    function extractVisibleTextContent() {
      // 1. 找到目标 "内筒" 元素
      const innerTubeElement = document.querySelector('.yaociXiangXi');

      // 2. 检查是否找到了该元素
      if (innerTubeElement) {
        // 3. 获取该元素的文本内容 (忽略 HTML 标签)
        // textContent 会自动忽略 HTML 标签，并拼接所有文本节点的内容
        const textContent = innerTubeElement.textContent;

        // 4. 对提取的文本进行一些清理，比如去除多余的空白行和首尾空格
        const cleanedText = textContent
          .split('\n')             // 按换行符分割成数组
          .map(line => line.trim()) // 去除每行首尾的空格
          .filter(line => line)     // 去除空行
          .join('\n');            // 用换行符重新组合成字符串

        return cleanedText;
      } else {
        console.error("未能找到类名为 'yaociXiangXi' 的元素。");
        return null;
      }
    }

    // 调用函数获取结果
    const extractedText = extractVisibleTextContent();

    if (extractedText) {
      output += extractedText;
    } else {
      output += "未能提取到卦辞爻辞内容。\n";

      // 尝试获取基本卦名信息作为备用
      const allDivs = Array.from(document.querySelectorAll('div'));
      const guaCiDiv = allDivs.find(d =>
          d.style.border === "1px solid rgb(153, 153, 153)" &&
          d.querySelector('b[style*="font-size: 16px;"]'));

      if (guaCiDiv && guaCiDiv.querySelector('b[style*="font-size: 16px;"]')) {
          const guaName = guaCiDiv.querySelector('b[style*="font-size: 16px;"]').textContent;
          output += `*   **${guaName}**\n`;

          if (guaCiDiv.querySelector('span.guaci1')) {
              output += `*   ${guaCiDiv.querySelector('span.guaci1').textContent}\n`;
          }

          if (guaCiDiv.querySelector('span.guaci2')) {
              output += `*   ${guaCiDiv.querySelector('span.guaci2').textContent}\n`;
          }
      } else {
          output += "卦辞爻辞部分未找到。\n";
      }
    }

    // Stop extraction before "独家大数据智能解卦"
    // The structure of the function will naturally do this as no more output += lines are added for those sections.

    console.log(output);
    return output;
}

// To run in browser console on the page:
// extractAndFormatYaoData();
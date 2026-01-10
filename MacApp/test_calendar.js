#!/usr/bin/env node
/**
 * 测试 Apple Calendar 写入功能
 */

const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

// 测试数据
const testEventData = {
    activity: "测试活动",
    start_time: "2026-01-05T21:00:00",
    end_time: "2026-01-05T22:00:00",
    description: "这是一个测试事件",
    status: "completed"
};

console.log("🧪 测试 Apple Calendar 写入功能\n");
console.log("测试数据:", JSON.stringify(testEventData, null, 2));
console.log("\n");

// 转义特殊字符
function escapeAppleScript(str) {
    if (!str) return '';
    return str.replace(/\\/g, '\\\\')
               .replace(/"/g, '\\"')
               .replace(/\n/g, '\\n')
               .replace(/\r/g, '');
}

// 计算从当前时间到目标时间的秒数差（用于 AppleScript）
function getSecondsFromNow(targetDate) {
    const now = new Date();
    const diffMs = targetDate.getTime() - now.getTime();
    return Math.round(diffMs / 1000); // 转换为秒
}

// 生成 AppleScript
function generateAppleScript(eventData) {
    const { activity, start_time, end_time, description, status } = eventData;
    
    const startDate = new Date(start_time);
    const endDate = new Date(end_time);
    
    const escapedActivity = escapeAppleScript(activity || '未命名活动');
    const descText = description || (status ? `状态: ${status}` : '');
    const escapedDescription = escapeAppleScript(descText);
    
    const startSeconds = getSecondsFromNow(startDate);
    const endSeconds = getSecondsFromNow(endDate);
    
    return `
tell application "Calendar"
    activate
    set calendarName to "TimeFlow"
    
    -- 检查是否存在 TimeFlow 日历，如果不存在则创建
    try
        set targetCalendar to calendar calendarName
    on error
        make new calendar with properties {name:calendarName}
        set targetCalendar to calendar calendarName
    end try
    
    -- 创建事件
    -- 使用 current date 和秒数偏移量来计算时间
    set startSeconds to ${startSeconds}
    set endSeconds to ${endSeconds}
    
    tell targetCalendar
        make new event at end with properties {
            summary: "${escapedActivity}",
            start date: (current date) + startSeconds,
            end date: (current date) + endSeconds,
            description: "${escapedDescription}"
        }
    end tell
    
    return "success"
end tell
`.trim();
}

// 测试函数
function testCalendarWrite(eventData) {
    return new Promise((resolve, reject) => {
        const appleScript = generateAppleScript(eventData);
        
        console.log("生成的 AppleScript:");
        console.log("=".repeat(60));
        console.log(appleScript);
        console.log("=".repeat(60));
        console.log("\n");
        
        // 保存到临时文件
        const tmpFile = path.join(os.tmpdir(), `test_calendar_${Date.now()}.scpt`);
        fs.writeFileSync(tmpFile, appleScript);
        
        console.log(`执行 AppleScript: ${tmpFile}\n`);
        
        exec(`osascript "${tmpFile}"`, (error, stdout, stderr) => {
            // 清理临时文件
            try {
                fs.unlinkSync(tmpFile);
            } catch (e) {
                // 忽略清理错误
            }
            
            if (error) {
                console.error("❌ 错误:", error.message);
                console.error("stderr:", stderr);
                reject(error);
            } else {
                console.log("✅ 成功!");
                console.log("输出:", stdout);
                resolve(stdout);
            }
        });
    });
}

// 运行测试
testCalendarWrite(testEventData)
    .then(() => {
        console.log("\n✅ 测试完成！请检查 Apple Calendar 中的 TimeFlow 日历。");
        process.exit(0);
    })
    .catch((error) => {
        console.error("\n❌ 测试失败:", error);
        process.exit(1);
    });


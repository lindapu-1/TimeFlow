#!/usr/bin/env python3
"""
测试重复性事件写入功能
支持：
1. 使用标签/分类
2. 重复性事件（每天、每周等）
3. 批量写入多个事件
"""

import subprocess
import json
from datetime import datetime, timedelta

def escape_apple_script(text):
    """转义 AppleScript 特殊字符"""
    if not text:
        return ''
    return text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


def add_recurring_event(activity, start_time, end_time, calendar_name="生活", description="", recurrence="daily"):
    """
    添加重复性事件到日历
    
    Args:
        activity: 活动名称
        start_time: 开始时间 (格式: "HH:MM" 或 datetime)
        end_time: 结束时间 (格式: "HH:MM" 或 datetime)
        calendar_name: 日历名称（标签）
        description: 描述
        recurrence: 重复规则 ("daily", "weekly", "monthly", "yearly")
    """
    # 解析时间
    if isinstance(start_time, str):
        # 格式: "10:00" 或 "2024-01-01T10:00:00"
        if 'T' in start_time:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        else:
            # 假设是今天的时间
            today = datetime.now().date()
            hour, minute = map(int, start_time.split(':'))
            start_dt = datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute))
    else:
        start_dt = start_time
    
    if isinstance(end_time, str):
        if 'T' in end_time:
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        else:
            today = datetime.now().date()
            hour, minute = map(int, end_time.split(':'))
            end_dt = datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute))
    else:
        end_dt = end_time
    
    # 计算从当前时间到目标时间的秒数差
    now = datetime.now()
    start_seconds = int((start_dt - now).total_seconds())
    end_seconds = int((end_dt - now).total_seconds())
    
    # 转义文本
    escaped_activity = escape_apple_script(activity)
    escaped_description = escape_apple_script(description)
    escaped_calendar = escape_apple_script(calendar_name)
    
    # 构建 AppleScript
    # macOS Calendar 的 recurrence 属性使用 iCal 格式
    commands = [
        'tell application "Calendar"',
        'activate',
        f'set calendarName to "{escaped_calendar}"',
        'try',
        f'set targetCalendar to calendar calendarName',
        'on error',
        f'make new calendar with properties {{name:calendarName}}',
        f'set targetCalendar to calendar calendarName',
        'end try',
        'tell targetCalendar',
        f'make new event at end with properties {{summary:"{escaped_activity}", start date:(current date) + {start_seconds}, end date:(current date) + {end_seconds}, description:"{escaped_description}"}}',
        'set newEvent to result'
    ]
    
    # 添加重复规则（如果指定）
    if recurrence:
        if recurrence == "daily":
            commands.append('set recurrence of newEvent to "FREQ=DAILY;INTERVAL=1"')
        elif recurrence == "weekly":
            commands.append('set recurrence of newEvent to "FREQ=WEEKLY;INTERVAL=1"')
        elif recurrence == "monthly":
            commands.append('set recurrence of newEvent to "FREQ=MONTHLY;INTERVAL=1"')
        elif recurrence == "yearly":
            commands.append('set recurrence of newEvent to "FREQ=YEARLY;INTERVAL=1"')
    
    commands.extend([
        'end tell',
        'return "success"',
        'end tell'
    ])
    
    # 转义单引号
    escaped_commands = [c.replace("'", "'\\''") for c in commands]
    
    # 执行 AppleScript
    cmd = "osascript " + " ".join([f"-e '{c}'" for c in escaped_commands])
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print(f"✅ 成功添加事件: {activity} ({start_time} - {end_time}) 到日历 '{calendar_name}'")
            return {"success": True, "message": result.stdout.strip()}
        else:
            print(f"❌ 添加失败: {result.stderr}")
            return {"success": False, "error": result.stderr}
    except Exception as e:
        print(f"❌ 错误: {e}")
        return {"success": False, "error": str(e)}


def test_recurring_events():
    """测试重复性事件"""
    print("=" * 60)
    print("🔄 测试重复性事件写入")
    print("=" * 60)
    print()
    
    # 获取今天的日期
    today = datetime.now().date()
    
    # 测试用例1: 10-12点吃饭（生活）- 每天重复
    print("1️⃣  测试: 10:00-12:00 吃饭（生活标签，每天重复）")
    start1 = datetime.combine(today, datetime.min.time().replace(hour=10, minute=0))
    end1 = datetime.combine(today, datetime.min.time().replace(hour=12, minute=0))
    
    result1 = add_recurring_event(
        activity="吃饭",
        start_time=start1,
        end_time=end1,
        calendar_name="生活",
        description="日常用餐",
        recurrence="daily"
    )
    print()
    
    # 测试用例2: 14-18点休息（生活）- 每天重复
    print("2️⃣  测试: 14:00-18:00 休息（生活标签，每天重复）")
    start2 = datetime.combine(today, datetime.min.time().replace(hour=14, minute=0))
    end2 = datetime.combine(today, datetime.min.time().replace(hour=18, minute=0))
    
    result2 = add_recurring_event(
        activity="休息",
        start_time=start2,
        end_time=end2,
        calendar_name="生活",
        description="日常休息时间",
        recurrence="daily"
    )
    print()
    
    # 总结
    print("=" * 60)
    print("📊 测试结果")
    print("=" * 60)
    print(f"事件1 (吃饭): {'✅ 成功' if result1.get('success') else '❌ 失败'}")
    print(f"事件2 (休息): {'✅ 成功' if result2.get('success') else '❌ 失败'}")
    print()
    
    if result1.get('success') and result2.get('success'):
        print("✅ 所有测试通过！")
        print()
        print("💡 提示：")
        print("   - 事件已添加到 '生活' 日历")
        print("   - 设置为每天重复")
        print("   - 可以在 macOS Calendar 应用中查看和编辑")
    else:
        print("⚠️  部分测试失败，请检查错误信息")
    
    return result1.get('success') and result2.get('success')


def test_simple_events_with_tag():
    """测试简单事件（不使用重复规则，但使用标签）"""
    print()
    print("=" * 60)
    print("📅 测试简单事件（使用标签，不重复）")
    print("=" * 60)
    print()
    
    today = datetime.now().date()
    
    # 测试用例: 今天的事件
    print("测试: 今天 10:00-12:00 吃饭（生活标签）")
    start = datetime.combine(today, datetime.min.time().replace(hour=10, minute=0))
    end = datetime.combine(today, datetime.min.time().replace(hour=12, minute=0))
    
    result = add_recurring_event(
        activity="吃饭",
        start_time=start,
        end_time=end,
        calendar_name="生活",
        description="测试事件",
        recurrence=""  # 不重复
    )
    
    return result.get('success')


if __name__ == "__main__":
    try:
        # 测试重复性事件
        success1 = test_recurring_events()
        
        # 测试简单事件
        # success2 = test_simple_events_with_tag()
        
        print()
        print("=" * 60)
        print("✅ 测试完成")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\n👋 测试已取消")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


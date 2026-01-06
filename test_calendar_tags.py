#!/usr/bin/env python3
"""
测试从 macOS Calendar 中提取标签和分类
支持提取：
1. 所有日历名称（可作为分类）
2. 事件摘要中的关键词（可作为标签）
3. 事件描述中的关键词
4. 最近使用的事件摘要（可作为常用标签）
"""

import subprocess
import json
from datetime import datetime, timedelta
from collections import Counter
import re

def run_applescript(script):
    """执行 AppleScript 并返回结果"""
    try:
        # 将脚本转换为单行命令
        escaped_script = script.replace("'", "'\\''")
        cmd = f"osascript -e '{escaped_script}'"
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30  # 增加超时时间
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            print(f"AppleScript 错误: {result.stderr}")
            return None
    except subprocess.TimeoutExpired:
        print(f"⚠️  AppleScript 执行超时（30秒）")
        return None
    except Exception as e:
        print(f"执行错误: {e}")
        return None


def get_all_calendars():
    """获取所有日历名称"""
    script = '''
    tell application "Calendar"
        set calendarNames to {}
        repeat with cal in calendars
            set end of calendarNames to name of cal
        end repeat
        return calendarNames
    end tell
    '''
    
    result = run_applescript(script)
    if result:
        # AppleScript 返回的是逗号分隔的列表
        calendars = [name.strip() for name in result.split(',')]
        return calendars
    return []


def get_recent_events_summaries(days=30, limit=50):
    """获取最近事件摘要（用于提取常用标签）"""
    # 使用更高效的方法：只查询主要日历，限制数量
    script = f'''
    tell application "Calendar"
        set eventSummaries to {{}}
        set startDate to (current date) - {days} * days
        set endDate to (current date) + 1 * days
        set eventCount to 0
        
        -- 只查询前5个主要日历，避免超时
        set mainCalendars to {{}}
        repeat with i from 1 to (count of calendars)
            if i > 5 then exit repeat
            set end of mainCalendars to calendar i
        end repeat
        
        repeat with cal in mainCalendars
            try
                set eventsList to (every event of cal whose start date is greater than startDate and start date is less than endDate)
                repeat with evt in eventsList
                    if eventCount >= {limit} then exit repeat
                    if summary of evt is not "" then
                        set end of eventSummaries to summary of evt
                        set eventCount to eventCount + 1
                    end if
                end repeat
                if eventCount >= {limit} then exit repeat
            end try
        end repeat
        
        return eventSummaries
    end tell
    '''
    
    result = run_applescript(script)
    if result:
        # AppleScript 返回的是逗号分隔的列表
        summaries = [s.strip() for s in result.split(',') if s.strip()]
        return summaries[:limit]
    return []


def get_event_keywords(summaries, top_n=20):
    """从事件摘要中提取关键词（作为标签候选）"""
    # 中文分词（简单方法：按空格和常见分隔符分割）
    all_words = []
    
    for summary in summaries:
        # 移除标点符号，保留中文和英文
        cleaned = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', summary)
        # 分割单词
        words = cleaned.split()
        all_words.extend(words)
    
    # 统计词频
    word_freq = Counter(all_words)
    
    # 过滤掉太短或太长的词
    filtered_words = {
        word: count for word, count in word_freq.items()
        if len(word) >= 2 and len(word) <= 10 and count >= 2
    }
    
    # 按频率排序，返回前 N 个
    top_words = sorted(filtered_words.items(), key=lambda x: x[1], reverse=True)[:top_n]
    
    return [word for word, count in top_words]


def extract_categories_from_summaries(summaries):
    """从摘要中提取可能的分类（基于常见模式）"""
    categories = set()
    
    # 常见活动类型关键词
    activity_keywords = {
        '工作': ['会议', '工作', '项目', '讨论', '汇报'],
        '学习': ['学习', '课程', '读书', '作业', '复习'],
        '运动': ['运动', '跑步', '健身', '游泳', '瑜伽', '跳舞'],
        '娱乐': ['电影', '游戏', '音乐', '唱歌', '练歌'],
        '社交': ['聚餐', '吃饭', '咖啡', '见面', '聚会'],
        '生活': ['购物', '买菜', '做饭', '家务', '休息'],
        '出行': ['出门', '通勤', '旅行', '出差', '回家'],
    }
    
    for summary in summaries:
        summary_lower = summary.lower()
        for category, keywords in activity_keywords.items():
            if any(keyword in summary for keyword in keywords):
                categories.add(category)
    
    return list(categories)


def get_calendar_statistics():
    """获取日历统计信息"""
    script = '''
    tell application "Calendar"
        set stats to {{}}
        set totalEvents to 0
        
        repeat with cal in calendars
            try
                set eventCount to count of (every event of cal)
                set totalEvents to totalEvents + eventCount
            end try
        end repeat
        
        return totalEvents
    end tell
    '''
    
    result = run_applescript(script)
    return int(result) if result and result.isdigit() else 0


def main():
    print("=" * 60)
    print("📅 macOS Calendar 标签提取测试")
    print("=" * 60)
    print()
    
    # 1. 获取所有日历名称
    print("1️⃣  获取所有日历...")
    calendars = get_all_calendars()
    print(f"   找到 {len(calendars)} 个日历:")
    for i, cal in enumerate(calendars, 1):
        print(f"   {i}. {cal}")
    print()
    
    # 2. 获取最近事件摘要
    print("2️⃣  获取最近30天的事件摘要...")
    summaries = get_recent_events_summaries(days=30, limit=100)
    print(f"   找到 {len(summaries)} 个事件摘要")
    if summaries:
        print("   示例摘要:")
        for i, summary in enumerate(summaries[:5], 1):
            print(f"   {i}. {summary}")
    print()
    
    # 3. 提取关键词（标签候选）
    print("3️⃣  提取常用关键词（标签候选）...")
    keywords = get_event_keywords(summaries, top_n=20)
    print(f"   找到 {len(keywords)} 个常用关键词:")
    for i, keyword in enumerate(keywords, 1):
        print(f"   {i}. {keyword}")
    print()
    
    # 4. 提取分类
    print("4️⃣  提取活动分类...")
    categories = extract_categories_from_summaries(summaries)
    print(f"   找到 {len(categories)} 个分类:")
    for i, category in enumerate(categories, 1):
        print(f"   {i}. {category}")
    print()
    
    # 5. 生成标签建议
    print("5️⃣  生成标签建议...")
    all_tags = {
        "calendars": calendars,
        "keywords": keywords,
        "categories": categories,
        "recent_summaries": summaries[:10]  # 最近10个摘要作为参考
    }
    
    print("   标签数据结构:")
    print(json.dumps(all_tags, ensure_ascii=False, indent=2))
    print()
    
    # 6. 保存结果
    output_file = "calendar_tags.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_tags, f, ensure_ascii=False, indent=2)
    print(f"✅ 结果已保存到: {output_file}")
    print()
    
    # 7. 生成使用建议
    print("=" * 60)
    print("💡 使用建议")
    print("=" * 60)
    print("""
1. **日历名称**：可以作为分类标签，用户可以选择使用哪个日历
2. **关键词**：从用户的历史事件中提取，可以作为自动标签建议
3. **分类**：基于常见活动类型，可以用于快速分类
4. **最近摘要**：可以作为用户常用活动的参考

**集成建议**：
- 在用户首次使用时，显示这些标签供选择
- 在语音输入后，根据关键词自动匹配标签
- 允许用户自定义标签
- 定期更新标签列表（基于新的事件）
    """)
    
    return all_tags


if __name__ == "__main__":
    try:
        tags = main()
    except KeyboardInterrupt:
        print("\n\n👋 测试已取消")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


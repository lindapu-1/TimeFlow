#!/usr/bin/env python3
"""测试写入苹果日历功能"""
import requests
import json
import subprocess
import os
from datetime import datetime, timedelta

API_BASE_URL = "http://127.0.0.1:8000"

# 测试用例（来自 benchmark_ollama_models.py）
TEST_CASES = [
    {
        "name": "15秒音频-多时间块",
        "transcript": "今 天 早 上 八 点 出 门 然 后 九 点 到 了 咖 啡 厅 九 点 到 九 点 半 呢 我 开 始 学 习",
    },
    {
        "name": "8秒音频-单时间块",
        "transcript": "今 天 晚 上 八 点 到 九 点 我 会 在 练 歌 房 练 歌 上 一 节 声 乐 课",
    },
    {
        "name": "9秒音频-相对时间",
        "transcript": "刚 刚 半 个 小 时 我 在 吃 饭 好 朋 友 吃 饭 餐 厅 特 别 好 吃",
    },
    {
        "name": "相对时间-跳舞",
        "transcript": "刚 刚 半 个 小 时 我 在 跳 舞",
    }
]


def escape_apple_script(text):
    """转义 AppleScript 特殊字符"""
    if not text:
        return ''
    return text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


def format_date_for_applescript(date_str):
    """将 ISO 8601 日期字符串转换为 AppleScript 可用的格式"""
    try:
        # 解析 ISO 8601 格式（处理时区信息）
        if 'Z' in date_str:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        elif '+' in date_str or date_str.count('-') > 2:
            # 包含时区信息，需要处理
            dt = datetime.fromisoformat(date_str)
        else:
            # 不包含时区信息，直接解析
            dt = datetime.fromisoformat(date_str)
        
        # 如果 dt 是时区感知的，转换为本地时区
        if dt.tzinfo is not None:
            # 转换为本地时区（移除时区信息）
            dt = dt.replace(tzinfo=None)
        
        # 计算从当前时间到目标时间的秒数差
        now = datetime.now()
        diff_seconds = int((dt - now).total_seconds())
        return diff_seconds
    except Exception as e:
        print(f"   ⚠️ 日期解析错误: {e}, 日期字符串: {date_str}")
        return 0


def add_to_calendar(event_data):
    """使用 AppleScript 添加到苹果日历"""
    activity = event_data.get('activity', '未命名活动')
    start_time = event_data.get('start_time')
    end_time = event_data.get('end_time')
    description = event_data.get('description', '') or event_data.get('location', '')
    
    # 转义特殊字符
    escaped_activity = escape_apple_script(activity)
    escaped_description = escape_apple_script(description)
    
    # 格式化日期
    if start_time:
        start_seconds = format_date_for_applescript(start_time)
    else:
        # 如果没有开始时间，使用当前时间
        start_seconds = 0
    
    if end_time:
        end_seconds = format_date_for_applescript(end_time)
    else:
        # 如果没有结束时间，使用开始时间 + 1小时
        end_seconds = start_seconds + 3600
    
    # 构建 AppleScript 命令（使用多个 -e 参数，避免多行字符串问题）
    commands = [
        'tell application "Calendar"',
        'activate',
        'set calendarName to "TimeFlow"',
        'try',
        'set targetCalendar to calendar calendarName',
        'on error',
        'make new calendar with properties {name:calendarName}',
        'set targetCalendar to calendar calendarName',
        'end try',
        'tell targetCalendar',
        f'make new event at end with properties {{summary:"{escaped_activity}", start date:(current date) + {start_seconds}, end date:(current date) + {end_seconds}, description:"{escaped_description}"}}',
        'end tell',
        'return "success"',
        'end tell'
    ]
    
    # 转义单引号：将 ' 替换为 '\''
    escaped_commands = [c.replace("'", "'\\''") for c in commands]
    
    # 使用多个 -e 参数执行 AppleScript
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
            return {"success": True, "message": result.stdout.strip()}
        else:
            return {"success": False, "error": result.stderr.strip()}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "AppleScript 执行超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def test_analyze_and_write(test_case):
    """测试分析并写入日历"""
    print(f"\n{'='*60}")
    print(f"📝 测试用例: {test_case['name']}")
    print(f"   转录文本: {test_case['transcript']}")
    print(f"{'='*60}\n")
    
    # 1. 调用分析 API
    print("1️⃣ 调用 LLM 分析 API...")
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/analyze",
            json={
                "transcript": test_case['transcript'],
                "use_ollama": False  # 使用默认的豆包模型（最佳性能）
            },
            timeout=60
        )
        
        if response.status_code != 200:
            print(f"   ❌ API 错误: {response.status_code} - {response.text}")
            return False
        
        result = response.json()
        
        if not result.get('success'):
            print(f"   ❌ 分析失败: {result.get('error')}")
            return False
        
        data = result.get('data', {})
        method = result.get('method', 'unknown')
        model = result.get('model', 'unknown')
        
        print(f"   ✅ 分析成功")
        print(f"   方法: {method}")
        print(f"   模型: {model}")
        print(f"   活动: {data.get('activity', '-')}")
        print(f"   开始时间: {data.get('start_time', '-')}")
        print(f"   结束时间: {data.get('end_time', '-')}")
        print(f"   地点: {data.get('location', '-')}")
        print(f"   描述: {data.get('description', '-')}")
        
        # 2. 写入苹果日历
        print(f"\n2️⃣ 写入苹果日历...")
        calendar_result = add_to_calendar(data)
        
        if calendar_result.get('success'):
            print(f"   ✅ 成功写入苹果日历！")
            print(f"   消息: {calendar_result.get('message', '')}")
            return True
        else:
            print(f"   ❌ 写入失败: {calendar_result.get('error', '未知错误')}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"   ❌ 无法连接到后端 API ({API_BASE_URL})")
        print(f"   请确保后端服务正在运行")
        return False
    except Exception as e:
        print(f"   ❌ 异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("🧪 测试写入苹果日历功能\n")
    print("="*60)
    print("📋 将使用以下测试用例:")
    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"   {i}. {test_case['name']}")
    print("="*60)
    
    # 检查后端是否运行
    print("\n🔍 检查后端服务...")
    try:
        response = requests.get(f"{API_BASE_URL}/", timeout=2)
        print(f"   ✅ 后端服务运行正常")
    except:
        print(f"   ❌ 后端服务未运行，请先启动: python3 app.py")
        return
    
    # 检查 Ollama 是否运行
    print("\n🔍 检查 Ollama 服务...")
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        print(f"   ✅ Ollama 服务运行正常")
    except:
        print(f"   ⚠️  Ollama 服务未运行，将回退到云端 API")
    
    # 询问用户要测试哪些用例
    print("\n" + "="*60)
    print("请选择要测试的用例:")
    print("  0. 测试所有用例")
    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"  {i}. {test_case['name']}")
    
    try:
        choice = input("\n请输入选项 (0-{}): ".format(len(TEST_CASES)))
        choice = int(choice.strip())
        
        if choice == 0:
            # 测试所有用例
            test_cases_to_run = TEST_CASES
        elif 1 <= choice <= len(TEST_CASES):
            test_cases_to_run = [TEST_CASES[choice - 1]]
        else:
            print("❌ 无效选项")
            return
        
        # 执行测试
        success_count = 0
        total_count = len(test_cases_to_run)
        
        for test_case in test_cases_to_run:
            if test_analyze_and_write(test_case):
                success_count += 1
        
        # 总结
        print("\n" + "="*60)
        print("📊 测试总结")
        print("="*60)
        print(f"   总测试数: {total_count}")
        print(f"   成功: {success_count}")
        print(f"   失败: {total_count - success_count}")
        print(f"   成功率: {success_count/total_count*100:.1f}%")
        
        if success_count == total_count:
            print("\n   ✅ 所有测试通过！")
        else:
            print("\n   ⚠️  部分测试失败，请检查错误信息")
            
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
    except ValueError:
        print("❌ 无效输入，请输入数字")
    except Exception as e:
        print(f"❌ 异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()


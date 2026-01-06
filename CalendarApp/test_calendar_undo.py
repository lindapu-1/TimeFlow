#!/usr/bin/env python3
"""测试苹果日历撤回功能"""
import requests
import json
import subprocess
import os
from datetime import datetime

API_BASE_URL = "http://127.0.0.1:8000"

# 存储最近写入的事件ID
RECENT_EVENT_FILE = "/tmp/timeflow_recent_event.json"


def escape_apple_script(text):
    """转义 AppleScript 特殊字符"""
    if not text:
        return ''
    return text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


def add_to_calendar(event_data):
    """使用 AppleScript 添加到苹果日历，返回事件ID"""
    activity = event_data.get('activity', '未命名活动')
    start_time = event_data.get('start_time')
    end_time = event_data.get('end_time')
    description = event_data.get('description', '') or event_data.get('location', '')
    
    # 转义特殊字符
    escaped_activity = escape_apple_script(activity)
    escaped_description = escape_apple_script(description)
    
    # 格式化日期
    if start_time:
        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        if start_dt.tzinfo:
            start_dt = start_dt.replace(tzinfo=None)
        now_dt = datetime.now()
        start_seconds = int((start_dt - now_dt).total_seconds())
    else:
        start_seconds = 0
    
    if end_time:
        end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        if end_dt.tzinfo:
            end_dt = end_dt.replace(tzinfo=None)
        now_dt = datetime.now()
        end_seconds = int((end_dt - now_dt).total_seconds())
    else:
        end_seconds = start_seconds + 3600
    
    # 构建 AppleScript 命令（创建事件并返回事件ID）
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
        'set newEvent to result',
        'set eventId to id of newEvent',
        'return eventId',
        'end tell',
        'end tell'
    ]
    
    # 转义单引号
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
            event_id = result.stdout.strip()
            # 保存事件ID到文件
            event_info = {
                "event_id": event_id,
                "activity": activity,
                "start_time": start_time,
                "end_time": end_time,
                "created_at": datetime.now().isoformat()
            }
            with open(RECENT_EVENT_FILE, 'w', encoding='utf-8') as f:
                json.dump(event_info, f, ensure_ascii=False, indent=2)
            return {"success": True, "event_id": event_id, "message": result.stdout.strip()}
        else:
            return {"success": False, "error": result.stderr.strip()}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "AppleScript 执行超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def undo_last_event():
    """撤回最近写入的日历事件"""
    # 读取最近的事件信息
    if not os.path.exists(RECENT_EVENT_FILE):
        return {"success": False, "error": "没有找到最近写入的事件"}
    
    try:
        with open(RECENT_EVENT_FILE, 'r', encoding='utf-8') as f:
            event_info = json.load(f)
        
        event_id = event_info.get('event_id')
        if not event_id:
            return {"success": False, "error": "事件ID不存在"}
        
        # 构建 AppleScript 命令（删除事件）
        # 注意：event id 需要用引号包裹
        commands = [
            'tell application "Calendar"',
            'activate',
            'set calendarName to "TimeFlow"',
            'set targetCalendar to calendar calendarName',
            'tell targetCalendar',
            f'set eventToDelete to event id "{event_id}"',
            'delete eventToDelete',
            'return "success"',
            'end tell',
            'end tell'
        ]
        
        # 转义单引号
        escaped_commands = [c.replace("'", "'\\''") for c in commands]
        
        # 使用多个 -e 参数执行 AppleScript
        cmd = "osascript " + " ".join([f"-e '{c}'" for c in escaped_commands])
        
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            # 删除事件信息文件
            os.remove(RECENT_EVENT_FILE)
            return {
                "success": True,
                "message": "事件已撤回",
                "deleted_event": event_info
            }
        else:
            return {"success": False, "error": result.stderr.strip()}
            
    except FileNotFoundError:
        return {"success": False, "error": "没有找到最近写入的事件"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def test_add_and_undo():
    """测试添加和撤回功能"""
    print("🧪 测试苹果日历撤回功能\n")
    print("="*60)
    
    # 1. 调用分析 API
    print("1️⃣ 调用 LLM 分析 API...")
    test_transcript = "今 天 晚 上 八 点 到 九 点 我 会 在 练 歌 房 练 歌"
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/analyze",
            json={
                "transcript": test_transcript,
                "use_ollama": False
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
        
        # 2. 写入苹果日历
        print(f"\n2️⃣ 写入苹果日历...")
        calendar_result = add_to_calendar(data)
        
        if not calendar_result.get('success'):
            print(f"   ❌ 写入失败: {calendar_result.get('error', '未知错误')}")
            return False
        
        event_id = calendar_result.get('event_id')
        print(f"   ✅ 成功写入苹果日历！")
        print(f"   事件ID: {event_id}")
        print(f"   消息: {calendar_result.get('message', '')}")
        
        # 等待一下，让事件完全创建
        print(f"\n3️⃣ 等待事件创建完成...")
        import time
        time.sleep(2)
        print(f"   事件已创建，事件ID: {event_id}")
        
        # 3. 撤回事件
        print(f"\n4️⃣ 撤回最近写入的事件...")
        undo_result = undo_last_event()
        
        if undo_result.get('success'):
            print(f"   ✅ 事件已成功撤回！")
            deleted_event = undo_result.get('deleted_event', {})
            print(f"   撤回的活动: {deleted_event.get('activity', '-')}")
            print(f"   撤回的时间: {deleted_event.get('start_time', '-')} - {deleted_event.get('end_time', '-')}")
            print(f"\n   请检查苹果日历，确认事件已删除")
            return True
        else:
            print(f"   ❌ 撤回失败: {undo_result.get('error', '未知错误')}")
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
    print("🧪 苹果日历撤回功能测试\n")
    print("="*60)
    
    # 检查后端是否运行
    print("\n🔍 检查后端服务...")
    try:
        response = requests.get(f"{API_BASE_URL}/", timeout=2)
        print(f"   ✅ 后端服务运行正常")
    except:
        print(f"   ❌ 后端服务未运行，请先启动: python3 app.py")
        return
    
    # 运行测试
    success = test_add_and_undo()
    
    print("\n" + "="*60)
    print("📊 测试总结")
    print("="*60)
    if success:
        print("   ✅ 测试通过！撤回功能正常工作")
    else:
        print("   ❌ 测试失败，请检查错误信息")


if __name__ == "__main__":
    main()


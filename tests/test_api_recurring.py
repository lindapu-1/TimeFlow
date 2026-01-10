#!/usr/bin/env python3
"""
测试 API 的重复性事件和标签功能
"""

import requests
import json
from datetime import datetime, timedelta

API_BASE_URL = "http://127.0.0.1:8000"

def test_recurring_events_api():
    """测试通过 API 添加重复性事件"""
    print("=" * 60)
    print("🔄 测试 API 重复性事件功能")
    print("=" * 60)
    print()
    
    # 获取今天的日期和时间
    today = datetime.now().date()
    
    # 测试用例1: 10-12点吃饭（生活标签，每天重复）
    print("1️⃣  测试: 10:00-12:00 吃饭（生活标签，每天重复）")
    start1 = datetime.combine(today, datetime.min.time().replace(hour=10, minute=0))
    end1 = datetime.combine(today, datetime.min.time().replace(hour=12, minute=0))
    
    event1 = {
        "activity": "吃饭",
        "start_time": start1.isoformat(),
        "end_time": end1.isoformat(),
        "description": "日常用餐",
        "calendar_name": "生活",  # 使用"生活"标签
        "recurrence": "daily"  # 每天重复
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/calendar/add",
            json=event1,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print(f"   ✅ 成功: {result.get('message')}")
            else:
                print(f"   ❌ 失败: {result.get('error')}")
        else:
            print(f"   ❌ HTTP错误: {response.status_code}")
            print(f"   响应: {response.text}")
    except Exception as e:
        print(f"   ❌ 错误: {e}")
    
    print()
    
    # 测试用例2: 14-18点休息（生活标签，每天重复）
    print("2️⃣  测试: 14:00-18:00 休息（生活标签，每天重复）")
    start2 = datetime.combine(today, datetime.min.time().replace(hour=14, minute=0))
    end2 = datetime.combine(today, datetime.min.time().replace(hour=18, minute=0))
    
    event2 = {
        "activity": "休息",
        "start_time": start2.isoformat(),
        "end_time": end2.isoformat(),
        "description": "日常休息时间",
        "calendar_name": "生活",  # 使用"生活"标签
        "recurrence": "daily"  # 每天重复
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/calendar/add",
            json=event2,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print(f"   ✅ 成功: {result.get('message')}")
            else:
                print(f"   ❌ 失败: {result.get('error')}")
        else:
            print(f"   ❌ HTTP错误: {response.status_code}")
            print(f"   响应: {response.text}")
    except Exception as e:
        print(f"   ❌ 错误: {e}")
    
    print()
    print("=" * 60)
    print("✅ 测试完成")
    print("=" * 60)
    print()
    print("💡 提示：")
    print("   - 事件已添加到 '生活' 日历")
    print("   - 设置为每天重复")
    print("   - 可以在 macOS Calendar 应用中查看和编辑")


def test_batch_recurring_events():
    """测试批量添加重复性事件"""
    print()
    print("=" * 60)
    print("📦 测试批量添加重复性事件")
    print("=" * 60)
    print()
    
    today = datetime.now().date()
    
    events = [
        {
            "activity": "吃饭",
            "start_time": datetime.combine(today, datetime.min.time().replace(hour=10, minute=0)).isoformat(),
            "end_time": datetime.combine(today, datetime.min.time().replace(hour=12, minute=0)).isoformat(),
            "description": "日常用餐",
            "calendar_name": "生活",
            "recurrence": "daily"
        },
        {
            "activity": "休息",
            "start_time": datetime.combine(today, datetime.min.time().replace(hour=14, minute=0)).isoformat(),
            "end_time": datetime.combine(today, datetime.min.time().replace(hour=18, minute=0)).isoformat(),
            "description": "日常休息时间",
            "calendar_name": "生活",
            "recurrence": "daily"
        }
    ]
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/calendar/add-multiple",
            json=events,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                count = result.get("count", 0)
                print(f"   ✅ 成功添加 {count} 个事件")
            else:
                print(f"   ❌ 失败: {result.get('error')}")
        else:
            print(f"   ❌ HTTP错误: {response.status_code}")
            print(f"   响应: {response.text}")
    except Exception as e:
        print(f"   ❌ 错误: {e}")


if __name__ == "__main__":
    try:
        # 测试单个重复性事件
        test_recurring_events_api()
        
        # 测试批量添加
        # test_batch_recurring_events()
        
    except KeyboardInterrupt:
        print("\n\n👋 测试已取消")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


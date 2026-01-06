#!/usr/bin/env python3
"""
测试标签分类功能
测试 LLM 是否能正确提取 tag 字段，并写入到对应的日历
"""

import requests
import json
from datetime import datetime

API_BASE_URL = "http://127.0.0.1:8000"

# 测试用例
TEST_CASES = [
    {
        "name": "工作类",
        "transcript": "今天下午三点开会讨论项目进度",
        "expected_tag": "工作"
    },
    {
        "name": "学习类",
        "transcript": "刚刚半小时我在学习Python编程",
        "expected_tag": "学习"
    },
    {
        "name": "生活类",
        "transcript": "今天早上八点到九点我在吃饭",
        "expected_tag": "生活"
    },
    {
        "name": "娱乐类",
        "transcript": "今天晚上八点到九点我会在练歌房练歌",
        "expected_tag": "娱乐"
    },
    {
        "name": "运动类",
        "transcript": "刚刚半小时我在跑步",
        "expected_tag": "运动"
    },
    {
        "name": "多时间块-不同标签",
        "transcript": "今天早上八点出门然后九点到了咖啡厅九点到九点半呢我开始学习",
        "expected_tags": ["生活", "学习"]  # 通勤可能是生活，学习是学习
    }
]


def test_tag_classification():
    """测试标签分类"""
    print("=" * 60)
    print("🏷️  测试标签分类功能")
    print("=" * 60)
    print()
    
    results = []
    
    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"{i}️⃣  测试: {test_case['name']}")
        print(f"   文本: {test_case['transcript']}")
        
        try:
            # 调用分析 API
            response = requests.post(
                f"{API_BASE_URL}/api/analyze",
                json={
                    "transcript": test_case['transcript'],
                    "use_ollama": False  # 使用云端AI
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get("success"):
                    events = result.get("data", [])
                    
                    if isinstance(events, list) and len(events) > 0:
                        print(f"   ✅ 分析成功，提取到 {len(events)} 个事件")
                        
                        # 检查每个事件的 tag
                        for j, event in enumerate(events, 1):
                            tag = event.get('tag', '未分类')
                            activity = event.get('activity', 'N/A')
                            start_time = event.get('start_time', 'N/A')
                            end_time = event.get('end_time', 'N/A')
                            
                            print(f"      事件 {j}:")
                            print(f"        活动: {activity}")
                            print(f"        时间: {start_time} - {end_time}")
                            print(f"        标签: {tag}")
                            
                            # 验证标签
                            if 'expected_tags' in test_case:
                                # 多个事件的情况
                                if j <= len(test_case['expected_tags']):
                                    expected = test_case['expected_tags'][j-1]
                                    if tag == expected:
                                        print(f"        ✅ 标签正确: {tag}")
                                    else:
                                        print(f"        ⚠️  标签不匹配: 期望 {expected}, 实际 {tag}")
                            else:
                                # 单个事件的情况
                                expected = test_case.get('expected_tag')
                                if tag == expected:
                                    print(f"        ✅ 标签正确: {tag}")
                                else:
                                    print(f"        ⚠️  标签不匹配: 期望 {expected}, 实际 {tag}")
                        
                        results.append({
                            "test": test_case['name'],
                            "success": True,
                            "events": events
                        })
                    else:
                        print(f"   ❌ 未提取到事件")
                        results.append({
                            "test": test_case['name'],
                            "success": False,
                            "error": "未提取到事件"
                        })
                else:
                    print(f"   ❌ 分析失败: {result.get('error')}")
                    results.append({
                        "test": test_case['name'],
                        "success": False,
                        "error": result.get('error')
                    })
            else:
                print(f"   ❌ HTTP错误: {response.status_code}")
                print(f"   响应: {response.text}")
                results.append({
                    "test": test_case['name'],
                    "success": False,
                    "error": f"HTTP {response.status_code}"
                })
        except Exception as e:
            print(f"   ❌ 错误: {e}")
            results.append({
                "test": test_case['name'],
                "success": False,
                "error": str(e)
            })
        
        print()
    
    # 总结
    print("=" * 60)
    print("📊 测试结果总结")
    print("=" * 60)
    
    success_count = sum(1 for r in results if r.get('success'))
    total_count = len(results)
    
    print(f"总测试数: {total_count}")
    print(f"成功: {success_count}")
    print(f"失败: {total_count - success_count}")
    print()
    
    # 显示每个测试的标签
    print("标签提取结果:")
    for result in results:
        if result.get('success'):
            events = result.get('events', [])
            tags = [e.get('tag', '未分类') for e in events]
            print(f"  {result['test']}: {', '.join(tags)}")
        else:
            print(f"  {result['test']}: ❌ {result.get('error', '失败')}")
    
    return results


def test_write_to_calendar_with_tag():
    """测试使用标签写入日历"""
    print()
    print("=" * 60)
    print("📅 测试使用标签写入日历")
    print("=" * 60)
    print()
    
    # 测试用例：学习类事件
    test_transcript = "刚刚半小时我在学习Python编程"
    
    print(f"测试文本: {test_transcript}")
    print()
    
    try:
        # 1. 分析文本
        print("1️⃣  分析文本...")
        response = requests.post(
            f"{API_BASE_URL}/api/analyze",
            json={
                "transcript": test_transcript,
                "use_ollama": False
            },
            timeout=60
        )
        
        if response.status_code != 200:
            print(f"   ❌ 分析失败: {response.status_code}")
            return
        
        result = response.json()
        if not result.get("success"):
            print(f"   ❌ 分析失败: {result.get('error')}")
            return
        
        events = result.get("data", [])
        if not events:
            print("   ❌ 未提取到事件")
            return
        
        print(f"   ✅ 分析成功，提取到 {len(events)} 个事件")
        
        # 显示提取的事件
        for i, event in enumerate(events, 1):
            print(f"      事件 {i}:")
            print(f"        活动: {event.get('activity')}")
            print(f"        标签: {event.get('tag', '未分类')}")
            print(f"        时间: {event.get('start_time')} - {event.get('end_time')}")
        
        print()
        
        # 2. 写入日历
        print("2️⃣  写入日历...")
        calendar_events = []
        for event in events:
            calendar_events.append({
                "activity": event.get('activity'),
                "start_time": event.get('start_time'),
                "end_time": event.get('end_time'),
                "description": event.get('description', ''),
                "location": event.get('location', ''),
                "calendar_name": event.get('tag', 'TimeFlow'),  # 使用 tag 作为日历名称
                "recurrence": None
            })
        
        response = requests.post(
            f"{API_BASE_URL}/api/calendar/add-multiple",
            json=calendar_events,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                count = result.get("count", 0)
                print(f"   ✅ 成功写入 {count} 个事件到日历")
                
                # 显示写入的日历
                for i, event in enumerate(events, 1):
                    tag = event.get('tag', 'TimeFlow')
                    print(f"      事件 {i} 已写入 '{tag}' 日历")
            else:
                print(f"   ❌ 写入失败: {result.get('error')}")
        else:
            print(f"   ❌ HTTP错误: {response.status_code}")
            print(f"   响应: {response.text}")
    
    except Exception as e:
        print(f"   ❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        # 测试标签分类
        results = test_tag_classification()
        
        # 测试写入日历
        test_write_to_calendar_with_tag()
        
        print()
        print("=" * 60)
        print("✅ 测试完成")
        print("=" * 60)
        print()
        print("💡 提示：")
        print("   - 检查 macOS Calendar 应用，查看事件是否写入到对应的标签日历")
        print("   - 如果标签分类不正确，可以修改 prompts.md 中的标签分类规则")
        
    except KeyboardInterrupt:
        print("\n\n👋 测试已取消")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


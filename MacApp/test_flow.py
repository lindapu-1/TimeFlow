#!/usr/bin/env python3
"""测试完整流程"""
import requests
import json

API_BASE_URL = "http://127.0.0.1:8000"

print("🧪 测试 TimeFlow Calendar 完整流程\n")

# 测试用例
test_transcript = "刚刚一个小时，我吃了饭"

print(f"📝 测试文本: {test_transcript}\n")

# 1. 测试分析 API
print("1️⃣ 测试 AI 分析...")
try:
    response = requests.post(
        f"{API_BASE_URL}/api/analyze",
        json={
            "transcript": test_transcript,
            "use_ollama": True
        },
        timeout=60
    )
    
    print(f"   状态码: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"   成功: {result.get('success')}")
        print(f"   方法: {result.get('method')}")
        print(f"   模型: {result.get('model')}")
        
        if result.get('success'):
            data = result.get('data', {})
            print(f"   活动: {data.get('activity')}")
            print(f"   状态: {data.get('status')}")
            print(f"   开始时间: {data.get('start_time')}")
            print(f"   结束时间: {data.get('end_time')}")
            print(f"   持续时间: {data.get('duration_minutes')} 分钟")
            print("\n   ✅ 分析成功！")
        else:
            print(f"   ❌ 分析失败: {result.get('error')}")
    else:
        print(f"   ❌ HTTP 错误: {response.text}")
        
except Exception as e:
    print(f"   ❌ 异常: {e}")

print("\n" + "="*50)
print("✅ 测试完成！")





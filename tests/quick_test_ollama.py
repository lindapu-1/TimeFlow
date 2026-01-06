#!/usr/bin/env python3
"""快速测试 Ollama 集成"""
import requests
import json
import time

API_URL = "http://127.0.0.1:8000/api/analyze"

test_cases = [
    "我刚刚吃完饭了",
    "过去的 2 小时我在做家务"
]

print("🚀 快速测试 Ollama 集成\n")

for i, transcript in enumerate(test_cases, 1):
    print(f"测试 {i}: {transcript}")
    start = time.time()
    
    try:
        r = requests.post(API_URL, json={
            "transcript": transcript,
            "use_ollama": True
        }, timeout=20)
        
        if r.status_code == 200:
            result = r.json()
            if result.get("success"):
                elapsed = time.time() - start
                data = result.get("data", {})
                method = result.get("method", "unknown")
                print(f"  ✅ 成功 ({elapsed:.1f}秒, {method})")
                print(f"  📝 活动: {data.get('activity')}")
                print(f"  ⏰ 状态: {data.get('status')}")
            else:
                print(f"  ❌ 失败: {result.get('error')}")
        else:
            print(f"  ❌ HTTP {r.status_code}")
    except Exception as e:
        print(f"  ❌ 错误: {e}")
    
    print()

print("✅ 测试完成！")





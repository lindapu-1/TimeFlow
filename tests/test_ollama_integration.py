#!/usr/bin/env python3
"""
测试 Ollama 集成到 TimeFlow API
"""
import requests
import json
import time

API_BASE_URL = "http://127.0.0.1:8000/api"

def test_ollama_analysis(transcript):
    """测试使用 Ollama 进行时间分析"""
    print("=" * 60)
    print("测试 Ollama AI 分析")
    print("=" * 60)
    print(f"转录文本: {transcript}")
    print()
    
    try:
        start_time = time.time()
        
        response = requests.post(
            f"{API_BASE_URL}/analyze",
            json={
                "transcript": transcript,
                "use_ollama": True
            },
            timeout=30
        )
        
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get("success"):
                print("✅ 分析成功！")
                print(f"⏱️ 耗时: {elapsed:.2f} 秒")
                method = result.get('method', 'unknown')
                model = result.get('model', 'unknown')
                print(f"📊 使用方法: {method}")
                print(f"🤖 使用模型: {model}")
                print()
                print("分析结果:")
                print(json.dumps(result.get("data"), indent=2, ensure_ascii=False))
                return True
            else:
                print(f"❌ 分析失败: {result.get('error')}")
                return False
        else:
            print(f"❌ HTTP 错误: {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"❌ 发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 测试几个示例
    test_cases = [
        "我刚刚吃完饭了",
        "过去的 2 小时我在做家务",
        "我接下来打算开始看书"
    ]
    
    for i, transcript in enumerate(test_cases, 1):
        print(f"\n【测试 {i}/{len(test_cases)}】")
        test_ollama_analysis(transcript)
        print("\n" + "-" * 60 + "\n")


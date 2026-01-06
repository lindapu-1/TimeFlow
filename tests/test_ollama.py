#!/usr/bin/env python3
"""
测试 Ollama 本地 LLM API
"""
import requests
import json
import time

OLLAMA_API_URL = "http://localhost:11434/api"

def test_ollama_models():
    """列出可用的 Ollama 模型"""
    try:
        response = requests.get(f"{OLLAMA_API_URL}/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = data.get("models", [])
            print("=" * 60)
            print("📦 可用的 Ollama 模型：")
            print("=" * 60)
            for model in models:
                name = model.get("name", "unknown")
                size = model.get("size", 0) / (1024**3)  # 转换为 GB
                print(f"  • {name} ({size:.2f} GB)")
            return [m.get("name") for m in models]
        else:
            print(f"❌ 无法获取模型列表: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Ollama 服务器未运行或无法连接: {str(e)}")
        print("   请确保 Ollama 已启动: ollama serve")
        return []


def test_ollama_chat(model_name="llama3.2", prompt="你好"):
    """测试 Ollama 聊天功能"""
    print("=" * 60)
    print(f"测试 Ollama 模型: {model_name}")
    print("=" * 60)
    print(f"提示词: {prompt}")
    print()
    
    try:
        start_time = time.time()
        
        response = requests.post(
            f"{OLLAMA_API_URL}/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            elapsed = time.time() - start_time
            
            print("✅ 响应成功！")
            print(f"耗时: {elapsed:.2f} 秒")
            print()
            print("响应内容:")
            print("-" * 60)
            print(result.get("response", ""))
            print("-" * 60)
            print()
            
            return {
                "success": True,
                "response": result.get("response", ""),
                "time": elapsed
            }
        else:
            print(f"❌ 请求失败: {response.status_code}")
            print(response.text)
            return {"success": False, "error": response.text}
            
    except Exception as e:
        print(f"❌ 发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def test_time_analysis(model_name="llama3.2"):
    """测试时间分析功能"""
    print("=" * 60)
    print("测试时间分析功能")
    print("=" * 60)
    
    transcript = "我刚刚吃完饭了"
    
    system_prompt = """你是一个时间记录助手。用户会通过语音输入时间信息，你需要从文本中提取以下信息：
1. 活动名称（activity）：用户在做什么
2. 开始时间（start_time）：活动的开始时间（ISO 8601 格式）
3. 结束时间（end_time）：活动的结束时间（ISO 8601 格式）
4. 持续时间（duration_minutes）：如果提到了时长，转换为分钟数

注意：
- 如果用户说"刚刚"、"刚才"，使用当前时间作为结束时间
- 如果用户说"接下来"、"打算"，这是未来的活动，只设置开始时间
- 如果用户提到具体时长（如"2小时"、"30分钟"），计算持续时间
- 如果用户提到时间点（如"9点到11点"），使用这些时间点
- 如果只提到活动名称，假设是刚刚完成的活动，结束时间为当前时间

返回 JSON 格式：
{
  "activity": "活动名称",
  "start_time": "2024-01-01T09:00:00" 或 null,
  "end_time": "2024-01-01T11:00:00" 或 null,
  "duration_minutes": 120 或 null,
  "status": "completed" | "ongoing" | "planned"
}"""

    user_prompt = f"""请分析以下语音转录文本，提取时间信息：

"{transcript}"

当前时间：2024-01-05T17:00:00

请返回 JSON 格式的时间数据。只返回 JSON，不要其他内容。"""

    full_prompt = f"{system_prompt}\n\n{user_prompt}"
    
    result = test_ollama_chat(model_name, full_prompt)
    
    if result.get("success"):
        print(f"\n⏱️ 分析耗时: {result['time']:.2f} 秒")
        print(f"📝 响应长度: {len(result['response'])} 字符")
    
    return result


if __name__ == "__main__":
    print("🔍 检查 Ollama 连接...")
    models = test_ollama_models()
    
    if not models:
        print("\n❌ 没有可用的模型")
        print("   请先安装模型: ollama pull llama3.2")
        exit(1)
    
    print()
    
    # 测试默认模型（通常是第一个或 llama3.2）
    test_model = "llama3.2"
    if test_model not in models and models:
        test_model = models[0]
    
    print(f"使用模型: {test_model}")
    print()
    
    # 测试简单对话
    print("【测试 1】简单对话")
    test_ollama_chat(test_model, "你好，请用一句话介绍你自己")
    print()
    
    # 测试时间分析
    print("【测试 2】时间分析功能")
    test_time_analysis(test_model)





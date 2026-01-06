#!/usr/bin/env python3
"""
测试 Faster Whisper 本地语音转录
"""
import time
import os
from faster_whisper import WhisperModel

# 测试音频文件
AUDIO_FILE = "/Users/lindadexiaoaojiao/Desktop/Builder/AIArchitect/测试.m4a"

def test_faster_whisper(model_size="base", compute_type="int8"):
    """
    测试 Faster Whisper 转录
    
    Args:
        model_size: 模型大小 (tiny, base, small, medium, large)
        compute_type: 计算类型 (int8, float16, float32)
    """
    print("=" * 60)
    print(f"测试 Faster Whisper - {model_size} 模型")
    print("=" * 60)
    print(f"音频文件: {AUDIO_FILE}")
    print(f"计算类型: {compute_type}")
    print()
    
    # 检查文件是否存在
    if not os.path.exists(AUDIO_FILE):
        print(f"❌ 音频文件不存在: {AUDIO_FILE}")
        return
    
    # 加载模型
    print("📥 加载模型...")
    start_time = time.time()
    
    try:
        model = WhisperModel(
            model_size, 
            device="cpu",  # 或 "cuda" 如果有 GPU
            compute_type=compute_type
        )
        load_time = time.time() - start_time
        print(f"✅ 模型加载完成 (耗时: {load_time:.2f} 秒)")
        print()
    except Exception as e:
        print(f"❌ 模型加载失败: {str(e)}")
        return
    
    # 转录音频
    print("🎤 开始转录...")
    transcribe_start = time.time()
    
    try:
        segments, info = model.transcribe(
            AUDIO_FILE, 
            language="zh",  # 指定中文
            beam_size=5
        )
        
        # 收集所有文本
        transcript_parts = []
        for segment in segments:
            transcript_parts.append(segment.text)
            print(f"  [{segment.start:.2f}s - {segment.end:.2f}s] {segment.text}")
        
        transcript = " ".join(transcript_parts)
        transcribe_time = time.time() - transcribe_start
        
        print()
        print("=" * 60)
        print("✅ 转录完成！")
        print("=" * 60)
        print(f"完整转录: {transcript}")
        print()
        print(f"检测到的语言: {info.language} (概率: {info.language_probability:.2%})")
        print(f"转录耗时: {transcribe_time:.2f} 秒")
        print(f"总耗时: {time.time() - start_time:.2f} 秒")
        print()
        
        return transcript
        
    except Exception as e:
        print(f"❌ 转录失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def test_different_models():
    """测试不同大小的模型"""
    models_to_test = [
        ("base", "int8"),
        ("small", "int8"),
    ]
    
    results = {}
    
    for model_size, compute_type in models_to_test:
        print("\n" + "=" * 60)
        print(f"测试 {model_size} 模型 ({compute_type})")
        print("=" * 60)
        
        result = test_faster_whisper(model_size, compute_type)
        if result:
            results[model_size] = result
        
        print("\n" + "-" * 60 + "\n")
    
    # 对比结果
    if len(results) > 1:
        print("=" * 60)
        print("📊 模型对比")
        print("=" * 60)
        for model, transcript in results.items():
            print(f"\n{model} 模型:")
            print(f"  {transcript}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # 指定模型大小
        model_size = sys.argv[1]
        compute_type = sys.argv[2] if len(sys.argv) > 2 else "int8"
        test_faster_whisper(model_size, compute_type)
    else:
        # 测试默认模型
        print("使用默认配置测试 base 模型")
        print("用法: python3 test_faster_whisper.py [model_size] [compute_type]")
        print("示例: python3 test_faster_whisper.py small int8")
        print()
        test_faster_whisper("base", "int8")





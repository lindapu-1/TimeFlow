#!/usr/bin/env python3
"""
对比 Faster Whisper 和云端 STT API 的准确率
使用测试录音文件夹中的录音文件进行测试
"""
import os
import sys
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 加载环境变量
load_dotenv()

# 导入模型
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    print("⚠️  Faster Whisper 未安装")

# API 配置
TRANSCRIPTION_API_URL = "https://space.ai-builders.com/backend/v1/audio/transcriptions"
api_key = os.getenv("SUPER_MIND_API_KEY") or os.getenv("AI_BUILDER_TOKEN")

if not api_key:
    print("❌ 错误：未设置 SUPER_MIND_API_KEY 或 AI_BUILDER_TOKEN")
    sys.exit(1)


def transcribe_with_whisper(audio_path: str) -> dict:
    """使用 Faster Whisper 转写"""
    if not FASTER_WHISPER_AVAILABLE:
        return {"success": False, "error": "Faster Whisper 未安装"}
    
    try:
        print(f"  🔄 加载 Faster Whisper tiny 模型...")
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        
        print(f"  🎤 开始转写（Faster Whisper）...")
        start_time = time.time()
        segments, info = model.transcribe(audio_path, language="zh")
        transcript = "".join([segment.text for segment in segments]).strip()
        elapsed = time.time() - start_time
        
        return {
            "success": True,
            "transcript": transcript,
            "detected_language": info.language,
            "confidence": info.language_probability,
            "duration": elapsed,
            "method": "Faster Whisper tiny"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def transcribe_with_cloud_api(audio_path: str) -> dict:
    """使用云端 STT API 转写"""
    try:
        print(f"  🎤 开始转写（云端 API）...")
        start_time = time.time()
        
        with open(audio_path, 'rb') as f:
            files = {
                'audio_file': (os.path.basename(audio_path), f, 'audio/m4a')
            }
            data = {
                'language': 'zh-CN'
            }
            
            response = requests.post(
                TRANSCRIPTION_API_URL,
                files=files,
                data=data,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=60
            )
        
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            return {
                "success": True,
                "transcript": result.get("text", ""),
                "detected_language": result.get("detected_language"),
                "confidence": result.get("confidence"),
                "duration": elapsed,
                "method": "云端 STT API",
                "billing": result.get("billing")
            }
        else:
            return {
                "success": False,
                "error": f"API 错误: {response.status_code} - {response.text}"
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


def normalize_text(text: str) -> str:
    """规范化文本用于对比"""
    import re
    if not text:
        return ""
    # 去掉标点符号和空格
    text = re.sub(r'[，。！？；：,.!?;:\s]+', '', text)
    return text.lower()


def calculate_similarity(text1: str, text2: str) -> float:
    """计算两个文本的相似度（简单的字符匹配）"""
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)
    
    if not norm1 or not norm2:
        return 0.0
    
    # 计算最长公共子序列长度
    def lcs_length(s1, s2):
        m, n = len(s1), len(s2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i-1] == s2[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])
        return dp[m][n]
    
    lcs = lcs_length(norm1, norm2)
    similarity = (2.0 * lcs) / (len(norm1) + len(norm2)) if (len(norm1) + len(norm2)) > 0 else 0.0
    return similarity * 100


def main():
    """主测试函数"""
    # 测试录音文件夹路径
    test_audio_dir = Path(__file__).parent.parent / "MacApp" / "测试录音"
    
    if not test_audio_dir.exists():
        print(f"❌ 错误：测试录音文件夹不存在: {test_audio_dir}")
        sys.exit(1)
    
    # 获取所有音频文件
    audio_files = list(test_audio_dir.glob("*.m4a"))
    if not audio_files:
        print(f"❌ 错误：测试录音文件夹中没有找到 .m4a 文件")
        sys.exit(1)
    
    print("=" * 80)
    print("🎤 STT 模型对比测试")
    print("=" * 80)
    print(f"📁 测试文件目录: {test_audio_dir}")
    print(f"📊 找到 {len(audio_files)} 个测试文件\n")
    
    results = []
    
    for audio_file in sorted(audio_files):
        print(f"\n{'='*80}")
        print(f"📄 测试文件: {audio_file.name}")
        print(f"{'='*80}")
        
        file_size = audio_file.stat().st_size / 1024  # KB
        print(f"📦 文件大小: {file_size:.2f} KB")
        
        # 测试 Faster Whisper
        print(f"\n1️⃣  Faster Whisper tiny:")
        whisper_result = transcribe_with_whisper(str(audio_file))
        
        if whisper_result.get("success"):
            print(f"   ✅ 转写成功")
            print(f"   📝 文本: {whisper_result['transcript']}")
            print(f"   ⏱️  耗时: {whisper_result['duration']:.2f} 秒")
            print(f"   🌐 语言: {whisper_result.get('detected_language', 'N/A')}")
            print(f"   📊 置信度: {whisper_result.get('confidence', 0):.2%}")
        else:
            print(f"   ❌ 转写失败: {whisper_result.get('error')}")
            whisper_result = None
        
        # 测试云端 API
        print(f"\n2️⃣  云端 STT API:")
        cloud_result = transcribe_with_cloud_api(str(audio_file))
        
        if cloud_result.get("success"):
            print(f"   ✅ 转写成功")
            print(f"   📝 文本: {cloud_result['transcript']}")
            print(f"   ⏱️  耗时: {cloud_result['duration']:.2f} 秒")
            print(f"   🌐 语言: {cloud_result.get('detected_language', 'N/A')}")
            conf = cloud_result.get('confidence')
            if conf is not None:
                print(f"   📊 置信度: {conf:.2%}")
            else:
                print(f"   📊 置信度: N/A")
            if cloud_result.get("billing"):
                billing = cloud_result["billing"]
                print(f"   💰 成本: ${billing.get('total_cost', 0):.6f} USD")
        else:
            print(f"   ❌ 转写失败: {cloud_result.get('error')}")
            cloud_result = None
        
        # 对比结果
        if whisper_result and cloud_result and whisper_result.get("success") and cloud_result.get("success"):
            similarity = calculate_similarity(
                whisper_result['transcript'],
                cloud_result['transcript']
            )
            
            print(f"\n📊 对比结果:")
            print(f"   🔄 相似度: {similarity:.1f}%")
            print(f"   ⚡ 速度对比:")
            print(f"      - Faster Whisper: {whisper_result['duration']:.2f}s")
            print(f"      - 云端 API: {cloud_result['duration']:.2f}s")
            print(f"      - 速度差异: {abs(whisper_result['duration'] - cloud_result['duration']):.2f}s")
            
            # 判断哪个更准确（基于置信度）
            whisper_conf = whisper_result.get('confidence', 0) or 0
            cloud_conf = cloud_result.get('confidence', 0) or 0
            
            if cloud_conf == 0 and whisper_conf > 0:
                print(f"   🏆 Faster Whisper 提供置信度 ({whisper_conf:.2%})")
            elif whisper_conf == 0 and cloud_conf > 0:
                print(f"   🏆 云端 API 提供置信度 ({cloud_conf:.2%})")
            elif whisper_conf > cloud_conf:
                print(f"   🏆 Faster Whisper 置信度更高 ({whisper_conf:.2%} vs {cloud_conf:.2%})")
            elif cloud_conf > whisper_conf:
                print(f"   🏆 云端 API 置信度更高 ({cloud_conf:.2%} vs {whisper_conf:.2%})")
            elif whisper_conf > 0:
                print(f"   🤝 置信度相同 ({whisper_conf:.2%})")
            else:
                print(f"   📊 无法比较置信度（两个模型都未提供）")
            
            results.append({
                "file": audio_file.name,
                "whisper": whisper_result,
                "cloud": cloud_result,
                "similarity": similarity
            })
        else:
            print(f"\n⚠️  无法对比（部分转写失败）")
    
    # 总结
    print(f"\n{'='*80}")
    print("📈 测试总结")
    print(f"{'='*80}")
    
    if results:
        avg_similarity = sum(r["similarity"] for r in results) / len(results)
        avg_whisper_time = sum(r["whisper"]["duration"] for r in results) / len(results)
        avg_cloud_time = sum(r["cloud"]["duration"] for r in results) / len(results)
        
        print(f"\n📊 平均相似度: {avg_similarity:.1f}%")
        print(f"⚡ 平均转写时间:")
        print(f"   - Faster Whisper: {avg_whisper_time:.2f}s")
        print(f"   - 云端 API: {avg_cloud_time:.2f}s")
        
        print(f"\n🏆 推荐:")
        if avg_similarity > 90:
            print("   ✅ 两个模型结果高度一致，可以任选其一")
        elif avg_similarity > 70:
            print("   ⚠️  两个模型结果有一定差异，建议人工对比")
        else:
            print("   ❌ 两个模型结果差异较大，需要进一步测试")
        
        if avg_whisper_time < avg_cloud_time:
            print(f"   ⚡ Faster Whisper 更快 ({avg_whisper_time:.2f}s vs {avg_cloud_time:.2f}s)")
        else:
            print(f"   ⚡ 云端 API 更快 ({avg_cloud_time:.2f}s vs {avg_whisper_time:.2f}s)")
    else:
        print("⚠️  没有成功对比的结果")


if __name__ == "__main__":
    main()

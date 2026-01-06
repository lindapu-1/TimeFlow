#!/usr/bin/env python3
"""
ElevenLabs Scribe API 测试脚本
根据官方文档：https://elevenlabs.io/docs/developers/guides/cookbooks/speech-to-text/streaming
"""
import os
import time
import json
import base64
import argparse
from pathlib import Path
from dotenv import load_dotenv
import logging

# 加载环境变量
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def convert_audio_to_pcm16(audio_path: str, sample_rate: int = 16000) -> bytes:
    """将音频文件转换为PCM16格式"""
    try:
        import librosa
        import numpy as np
        
        # 使用librosa加载音频并转换为指定采样率
        audio, sr = librosa.load(audio_path, sr=sample_rate, mono=True)
        
        # 转换为PCM16格式
        audio_int16 = (audio * 32767).astype(np.int16)
        
        return audio_int16.tobytes()
    except Exception as e:
        logger.error(f"音频转换失败: {e}")
        raise


def test_elevenlabs_realtime(audio_path: str, api_key: str):
    """使用ElevenLabs实时API转录音频文件"""
    try:
        import websocket
        from websocket import WebSocketApp
        import threading
        import json as json_lib
        
        # 首先需要获取single-use token
        logger.info("获取single-use token...")
        import requests
        
        token_response = requests.post(
            "https://api.elevenlabs.io/v1/single-use-token/realtime_scribe",
            headers={
                "xi-api-key": api_key,
            },
            timeout=10
        )
        
        if token_response.status_code != 200:
            return {
                "error": f"获取token失败: {token_response.status_code} - {token_response.text}",
                "elapsed_time": 0
            }
        
        token_data = token_response.json()
        token = token_data.get("token")
        
        if not token:
            return {
                "error": "未获取到token",
                "elapsed_time": 0
            }
        
        logger.info("✅ Token获取成功")
        
        # 转换音频为PCM16
        logger.info("转换音频格式...")
        pcm_data = convert_audio_to_pcm16(audio_path)
        logger.info(f"✅ 音频转换完成，大小: {len(pcm_data)} bytes")
        
        # WebSocket连接配置
        # 根据官方文档，token应该通过URL参数传递
        ws_url = f"wss://api.elevenlabs.io/v1/speech-to-text/realtime/ws?model_id=scribe_v2_realtime&sample_rate=16000&audio_format=pcm_16&include_timestamps=false&token={token}"
        
        transcripts = []
        error_occurred = {"value": False}
        error_message = {"value": ""}
        session_started = {"value": False}
        transcription_complete = threading.Event()
        
        def on_message(ws, message):
            try:
                data = json_lib.loads(message)
                event_type = data.get("type")
                
                if event_type == "session_started":
                    logger.info("✅ WebSocket会话已启动")
                    session_started["value"] = True
                    
                elif event_type == "partial_transcript":
                    partial_text = data.get("text", "")
                    logger.info(f"  部分转录: {partial_text[:50]}...")
                    
                elif event_type == "committed_transcript":
                    committed_text = data.get("text", "")
                    logger.info(f"  已提交转录: {committed_text}")
                    transcripts.append(committed_text)
                    
                elif event_type in ["error", "auth_error", "transcriber_error", "input_error"]:
                    error_occurred["value"] = True
                    error_message["value"] = data.get("message", f"错误类型: {event_type}")
                    logger.error(f"❌ API错误: {error_message['value']}")
                    transcription_complete.set()
                    
            except Exception as e:
                logger.error(f"处理消息时出错: {e}")
        
        def on_error(ws, error):
            error_str = str(error)
            logger.error(f"WebSocket错误: {error_str}")
            
            # 检查是否是403错误，可能是权限问题
            if "403" in error_str:
                logger.error("❌ 403 Forbidden - 可能的原因：")
                logger.error("  1. 账户没有访问Scribe的权限")
                logger.error("  2. 需要在ElevenLabs控制台接受服务条款")
                logger.error("  3. API密钥权限不足")
                logger.error("  请访问: https://elevenlabs.io/app/settings/api-keys")
            
            error_occurred["value"] = True
            error_message["value"] = error_str
            transcription_complete.set()
        
        def on_close(ws, close_status_code, close_msg):
            logger.info("WebSocket连接已关闭")
            transcription_complete.set()
        
        def on_open(ws):
            logger.info("✅ WebSocket连接已建立")
            # 等待会话启动（token已在URL中，不需要单独认证）
            import time as time_module
            timeout = 5
            wait_start = time_module.time()
            while not session_started["value"] and (time_module.time() - wait_start) < timeout:
                time_module.sleep(0.1)
            
            if not session_started["value"]:
                logger.error("❌ 会话启动超时")
                ws.close()
                return
            
            # 分块发送音频数据
            logger.info("开始发送音频数据...")
            chunk_size = 4096  # 约0.1秒的音频（16kHz采样率）
            
            for i in range(0, len(pcm_data), chunk_size):
                chunk = pcm_data[i:i+chunk_size]
                chunk_base64 = base64.b64encode(chunk).decode('utf-8')
                
                audio_message = {
                    "type": "input_audio_chunk",
                    "audio_base_64": chunk_base64
                }
                ws.send(json_lib.dumps(audio_message))
                
                # 小延迟以模拟实时流
                time.sleep(0.05)
            
            # 发送commit消息
            logger.info("提交转录...")
            commit_message = {
                "type": "commit"
            }
            ws.send(json_lib.dumps(commit_message))
            
            # 等待最终转录结果
            time.sleep(2)
        
        # 创建WebSocket连接
        logger.info("建立WebSocket连接...")
        ws = WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )
        
        start_time = time.time()
        
        # 在单独线程中运行WebSocket
        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
        
        # 等待转录完成（最多30秒）
        transcription_complete.wait(timeout=30)
        
        elapsed_time = time.time() - start_time
        
        # 关闭连接
        ws.close()
        ws_thread.join(timeout=2)
        
        if error_occurred["value"]:
            return {
                "error": error_message["value"],
                "elapsed_time": elapsed_time
            }
        
        final_transcript = " ".join(transcripts)
        
        return {
            "transcript": final_transcript,
            "elapsed_time": elapsed_time,
            "partial_transcripts": len(transcripts)
        }
        
    except ImportError as e:
        import sys
        import subprocess
        logger.warning(f"缺少依赖库: {e}")
        logger.info("尝试安装websocket-client...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "websocket-client", "-q"])
            # 重新导入
            import websocket
            from websocket import WebSocketApp
            logger.info("✅ websocket-client安装成功，继续测试...")
            # 递归调用一次
            return test_elevenlabs_realtime(audio_path, api_key)
        except:
            return {
                "error": f"缺少依赖库: {e}。请手动安装: pip install websocket-client librosa numpy",
                "elapsed_time": 0
            }
    except Exception as e:
        return {
            "error": str(e),
            "elapsed_time": time.time() - start_time if 'start_time' in locals() else 0
        }


def main():
    parser = argparse.ArgumentParser(description="测试ElevenLabs Scribe实时API")
    parser.add_argument("audio_file", help="音频文件路径")
    parser.add_argument("--iterations", "-n", type=int, default=3, help="测试次数（默认3次）")
    parser.add_argument("--output", "-o", help="输出JSON结果文件")
    
    args = parser.parse_args()
    
    audio_path = Path(args.audio_file)
    if not audio_path.exists():
        logger.error(f"❌ 音频文件不存在: {audio_path}")
        return
    
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        logger.error("❌ ELEVENLABS_API_KEY 未设置")
        logger.info("请在.env文件中设置: ELEVENLABS_API_KEY=your_key")
        return
    
    logger.info(f"📁 音频文件: {audio_path}")
    logger.info(f"🔄 测试次数: {args.iterations}")
    logger.info("="*60)
    
    results = []
    for i in range(args.iterations):
        logger.info(f"\n第 {i+1}/{args.iterations} 次测试...")
        result = test_elevenlabs_realtime(str(audio_path), api_key)
        results.append(result)
        
        if "error" in result:
            logger.error(f"❌ 测试失败: {result['error']}")
        else:
            logger.info(f"✅ 耗时: {result['elapsed_time']:.2f}秒")
            logger.info(f"📝 转录: {result['transcript'][:100]}...")
    
    # 汇总结果
    successful_results = [r for r in results if "error" not in r]
    if successful_results:
        avg_time = sum(r["elapsed_time"] for r in successful_results) / len(successful_results)
        min_time = min(r["elapsed_time"] for r in successful_results)
        max_time = max(r["elapsed_time"] for r in successful_results)
        
        logger.info("\n" + "="*60)
        logger.info("测试结果汇总")
        logger.info("="*60)
        logger.info(f"成功次数: {len(successful_results)}/{args.iterations}")
        logger.info(f"平均耗时: {avg_time:.2f}秒")
        logger.info(f"最快: {min_time:.2f}秒")
        logger.info(f"最慢: {max_time:.2f}秒")
        if successful_results:
            logger.info(f"转录结果: {successful_results[0]['transcript']}")
    else:
        logger.error("\n❌ 所有测试都失败了")
        if results:
            logger.error(f"错误信息: {results[0].get('error', '未知错误')}")
    
    # 保存结果
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"\n✅ 结果已保存到: {args.output}")


if __name__ == "__main__":
    main()


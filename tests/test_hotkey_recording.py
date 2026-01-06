#!/usr/bin/env python3
"""
快捷键录音测试脚本
功能：
1. 监听快捷键 Cmd+Shift+T
2. 按住快捷键时开始录音
3. 松开快捷键时停止录音
4. 自动调用后端API进行转录、分析、添加到日历
5. 记录并显示各个步骤的耗时
"""
import time
import threading
import queue
import tempfile
import os
import sys
import requests
import json
from datetime import datetime
from pathlib import Path

# 配置
API_BASE_URL = "http://127.0.0.1:8000"
HOTKEY = "cmd+shift+t"  # macOS快捷键
SAMPLE_RATE = 16000  # 采样率
CHANNELS = 1  # 单声道
CHUNK_SIZE = 1024  # 音频块大小

# 全局状态
is_recording = False
audio_queue = queue.Queue()
recording_thread = None
audio_data = []

# 时间记录
timings = {
    "recording_duration": 0,
    "stt_time": 0,
    "analysis_time": 0,
    "calendar_time": 0,
    "total_time": 0
}


def check_dependencies():
    """检查依赖库"""
    missing = []
    
    try:
        import pynput
    except ImportError:
        missing.append("pynput")
    
    try:
        import sounddevice
    except ImportError:
        missing.append("sounddevice")
    
    try:
        import numpy
    except ImportError:
        missing.append("numpy")
    
    if missing:
        print(f"❌ 缺少依赖库: {', '.join(missing)}")
        print(f"请安装: pip install {' '.join(missing)}")
        return False
    
    return True


def record_audio():
    """录音线程函数"""
    global is_recording, audio_data
    
    try:
        import sounddevice as sd
        import numpy as np
        
        print("🎤 开始录音...")
        audio_data = []
        
        def audio_callback(indata, frames, time_info, status):
            if status:
                print(f"⚠️ 录音状态: {status}")
            if is_recording:
                audio_data.append(indata.copy())
        
        # 开始录音流
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            callback=audio_callback,
            blocksize=CHUNK_SIZE
        )
        
        with stream:
            while is_recording:
                sd.sleep(100)  # 等待100ms
        
        # 合并音频数据
        if audio_data:
            audio_array = np.concatenate(audio_data, axis=0)
            # 如果是2D数组，取第一个声道
            if len(audio_array.shape) > 1:
                audio_array = audio_array[:, 0]
            duration = len(audio_array) / SAMPLE_RATE
            print(f"✅ 录音完成，时长: {duration:.2f}秒")
            return audio_array
        else:
            print("⚠️ 没有录制到音频数据")
            return None
            
    except Exception as e:
        print(f"❌ 录音错误: {e}")
        import traceback
        traceback.print_exc()
        return None


def save_audio_to_file(audio_array, filepath):
    """保存音频数组为WAV文件"""
    try:
        import numpy as np
        
        # 确保是numpy数组
        if not isinstance(audio_array, np.ndarray):
            audio_array = np.array(audio_array)
        
        # 如果是2D数组（多声道），取第一个声道
        if len(audio_array.shape) > 1:
            audio_array = audio_array[:, 0]
        
        try:
            import soundfile as sf
            
            # 确保是float32格式
            if audio_array.dtype != 'float32':
                audio_array = audio_array.astype('float32')
            
            # 归一化到[-1, 1]范围
            max_val = np.abs(audio_array).max()
            if max_val > 0:
                audio_array = audio_array / max_val
            
            sf.write(filepath, audio_array, SAMPLE_RATE)
            print(f"💾 音频已保存: {filepath}")
            return True
        except ImportError:
            # 如果没有soundfile，尝试使用scipy
            try:
                from scipy.io import wavfile
                
                # 转换为int16格式
                max_val = np.abs(audio_array).max()
                if max_val > 0:
                    audio_array = audio_array / max_val
                audio_int16 = (audio_array * 32767).astype(np.int16)
                wavfile.write(filepath, SAMPLE_RATE, audio_int16)
                print(f"💾 音频已保存: {filepath}")
                return True
            except ImportError:
                print("❌ 需要安装 soundfile 或 scipy 来保存音频")
                print("安装: pip install soundfile")
                return False
    except Exception as e:
        print(f"❌ 保存音频失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def transcribe_audio(audio_file_path):
    """调用后端API转录音频"""
    try:
        start_time = time.time()
        
        with open(audio_file_path, 'rb') as f:
            files = {
                'audio_file': (os.path.basename(audio_file_path), f, 'audio/wav')
            }
            data = {
                'language': 'zh-CN',
                'use_local': 'true'  # 使用本地FunASR模型（中文识别最准确）
                # FunASR是默认的本地STT模型，专门针对中文优化
            }
            
            response = requests.post(
                f"{API_BASE_URL}/api/transcribe",
                files=files,
                data=data,
                timeout=60
            )
        
        elapsed = time.time() - start_time
        timings["stt_time"] = elapsed
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                transcript = result.get("transcript", "")
                print(f"📝 转录完成 ({elapsed:.2f}秒): {transcript[:50]}...")
                return transcript
            else:
                print(f"❌ 转录失败: {result.get('error')}")
                return None
        else:
            print(f"❌ 转录API错误: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 转录错误: {e}")
        import traceback
        traceback.print_exc()
        return None


def analyze_transcript(transcript):
    """调用后端API分析文本，提取时间事件"""
    try:
        start_time = time.time()
        
        response = requests.post(
            f"{API_BASE_URL}/api/analyze",
            json={
                "transcript": transcript,
                "use_ollama": False  # 使用云端AI（更快）
            },
            timeout=60
        )
        
        elapsed = time.time() - start_time
        timings["analysis_time"] = elapsed
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                data = result.get("data", [])
                if not isinstance(data, list):
                    data = [data]
                print(f"🤖 分析完成 ({elapsed:.2f}秒): 提取到 {len(data)} 个事件")
                return data
            else:
                print(f"❌ 分析失败: {result.get('error')}")
                return None
        else:
            print(f"❌ 分析API错误: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 分析错误: {e}")
        import traceback
        traceback.print_exc()
        return None


def add_to_calendar(events_data):
    """调用后端API添加到日历"""
    try:
        start_time = time.time()
        
        if len(events_data) == 1:
            # 单个事件
            event = events_data[0]
            response = requests.post(
                f"{API_BASE_URL}/api/calendar/add",
                json={
                    "activity": event.get("activity", ""),
                    "start_time": event.get("start_time", ""),
                    "end_time": event.get("end_time", ""),
                    "description": event.get("description", ""),
                    "location": event.get("location", "")
                },
                timeout=30
            )
        else:
            # 多个事件 - 需要转换为CalendarEventRequest格式
            events_list = []
            for event in events_data:
                events_list.append({
                    "activity": event.get("activity", ""),
                    "start_time": event.get("start_time", ""),
                    "end_time": event.get("end_time", ""),
                    "description": event.get("description", ""),
                    "location": event.get("location", "")
                })
            response = requests.post(
                f"{API_BASE_URL}/api/calendar/add-multiple",
                json=events_list,  # 直接传数组，不是{"events": ...}
                timeout=30
            )
        
        elapsed = time.time() - start_time
        timings["calendar_time"] = elapsed
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                event_ids = result.get("event_ids", [])
                print(f"📅 日历写入完成 ({elapsed:.2f}秒): {len(event_ids)} 个事件")
                return True
            else:
                print(f"❌ 日历写入失败: {result.get('error')}")
                return False
        else:
            print(f"❌ 日历API错误: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 日历写入错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def process_recording(audio_array):
    """处理录音：转录 -> 分析 -> 添加到日历"""
    total_start_time = time.time()
    
    print("\n" + "="*60)
    print("开始处理录音...")
    print("="*60)
    
    # 1. 保存音频文件
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
        audio_file_path = tmp_file.name
    
    if not save_audio_to_file(audio_array, audio_file_path):
        return False
    
    try:
        # 2. 转录音频
        transcript = transcribe_audio(audio_file_path)
        if not transcript:
            return False
        
        # 3. 分析文本，提取事件
        events_data = analyze_transcript(transcript)
        if not events_data:
            return False
        
        # 显示提取的事件
        print("\n📋 提取的事件:")
        for i, event in enumerate(events_data, 1):
            print(f"  事件 {i}:")
            print(f"    活动: {event.get('activity', 'N/A')}")
            print(f"    开始: {event.get('start_time', 'N/A')}")
            print(f"    结束: {event.get('end_time', 'N/A')}")
            if event.get('location'):
                print(f"    地点: {event.get('location')}")
        
        # 4. 添加到日历
        success = add_to_calendar(events_data)
        
        # 计算总时间
        total_elapsed = time.time() - total_start_time
        timings["total_time"] = total_elapsed
        
        # 显示时间统计
        print("\n" + "="*60)
        print("⏱️  时间统计")
        print("="*60)
        print(f"录音时长: {timings['recording_duration']:.2f}秒")
        print(f"STT转录: {timings['stt_time']:.2f}秒")
        print(f"事件提取: {timings['analysis_time']:.2f}秒")
        print(f"日历写入: {timings['calendar_time']:.2f}秒")
        print(f"总耗时: {timings['total_time']:.2f}秒 (从松开快捷键到完成)")
        print("="*60)
        
        return success
        
    finally:
        # 清理临时文件
        try:
            os.unlink(audio_file_path)
        except:
            pass


def on_hotkey_press():
    """快捷键按下时的回调"""
    global is_recording, recording_thread, audio_data, timings
    
    if not is_recording:
        # 开始录音
        is_recording = True
        audio_data = []
        timings = {
            "recording_duration": 0,
            "stt_time": 0,
            "analysis_time": 0,
            "calendar_time": 0,
            "total_time": 0
        }
        
        recording_start_time = time.time()
        
        # 启动录音线程
        recording_thread = threading.Thread(target=lambda: record_audio_thread(recording_start_time))
        recording_thread.daemon = True
        recording_thread.start()
        
        print("\n🔴 录音开始（按住 Cmd+Shift+T）...")
        sys.stdout.flush()  # 立即刷新输出


def record_audio_thread(start_time):
    """录音线程包装函数"""
    global is_recording, timings
    
    audio_array = record_audio()
    
    if audio_array is not None:
        recording_duration = time.time() - start_time
        timings["recording_duration"] = recording_duration
        
        # 处理录音
        process_recording(audio_array)
    else:
        print("❌ 录音失败，跳过处理")


def on_hotkey_release():
    """快捷键松开时的回调"""
    global is_recording
    
    if is_recording:
        # 停止录音
        is_recording = False
        print("⏹️  录音停止（已松开 Cmd+Shift+T）")
        sys.stdout.flush()  # 立即刷新输出


def main():
    """主函数"""
    print("="*60)
    print("🎙️  快捷键录音测试")
    print("="*60)
    print(f"快捷键: {HOTKEY.upper()}")
    print("操作说明:")
    print("  1. 按住 Cmd+Shift+T 开始录音")
    print("  2. 说话...")
    print("  3. 松开 Cmd+Shift+T 停止录音并自动处理")
    print("  4. 按 Ctrl+C 退出")
    print("="*60)
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 检查后端服务
    try:
        response = requests.get(f"{API_BASE_URL}/", timeout=5)
        print(f"✅ 后端服务连接正常: {API_BASE_URL}")
    except:
        print(f"❌ 无法连接到后端服务: {API_BASE_URL}")
        print("   请确保后端服务正在运行: python3 app.py")
        sys.exit(1)
    
    # 设置快捷键监听
    try:
        from pynput import keyboard
        
        # 快捷键组合键状态
        pressed_keys = set()
        cmd_pressed = False
        shift_pressed = False
        t_pressed = False
        
        def on_press(key):
            """键盘按下事件"""
            nonlocal cmd_pressed, shift_pressed, t_pressed
            
            try:
                # 记录按下的键
                pressed_keys.add(key)
                
                # 检测修饰键和字符键
                if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                    cmd_pressed = True
                elif key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
                    shift_pressed = True
                elif hasattr(key, 'char') and key.char:
                    if key.char.lower() == 't':
                        t_pressed = True
                elif str(key) == "'t'":
                    t_pressed = True
                
                # 检查是否按下了目标组合键 (Cmd+Shift+T)
                if cmd_pressed and shift_pressed and t_pressed:
                    if not is_recording:
                        on_hotkey_press()
            except Exception as e:
                print(f"⚠️ 按键检测错误: {e}")
        
        def on_release(key):
            """键盘松开事件"""
            nonlocal cmd_pressed, shift_pressed, t_pressed
            
            try:
                # 移除松开的键
                pressed_keys.discard(key)
                
                # 更新按键状态
                if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                    cmd_pressed = False
                elif key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
                    shift_pressed = False
                elif hasattr(key, 'char') and key.char:
                    if key.char.lower() == 't':
                        t_pressed = False
                elif str(key) == "'t'":
                    t_pressed = False
                
                # 如果正在录音，且所有目标键都已松开，则停止录音
                if is_recording:
                    if not (cmd_pressed and shift_pressed and t_pressed):
                        on_hotkey_release()
            except Exception as e:
                print(f"⚠️ 按键检测错误: {e}")
        
        # 启动监听器
        listener = keyboard.Listener(
            on_press=on_press,
            on_release=on_release
        )
        
        listener.start()
        print("\n✅ 快捷键监听已启动")
        print("等待快捷键按下...\n")
        print("⚠️  如果快捷键无响应，请检查macOS权限设置：")
        print("   系统设置 → 隐私与安全性 → 辅助功能")
        print("   添加 Terminal 或 Python 到允许列表\n")
        
        # 保持运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n👋 退出程序")
            listener.stop()
            
    except ImportError:
        print("❌ pynput 未安装")
        print("安装: pip install pynput")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 快捷键监听错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


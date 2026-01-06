#!/bin/bash
# 快捷键录音测试启动脚本

cd "$(dirname "$0")"

echo "🚀 启动快捷键录音测试..."
echo ""

# 检查后端服务
if lsof -ti:8000 > /dev/null 2>&1; then
    echo "✅ 后端服务正在运行"
else
    echo "⚠️  后端服务未运行，请先运行: python3 app.py"
    echo ""
fi

# 检查依赖
python3 -c "import pynput, sounddevice, soundfile, numpy" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 安装依赖..."
    python3 -m pip install pynput sounddevice soundfile numpy --user -q
fi

echo ""
echo "============================================================"
echo "🎙️  快捷键录音测试已启动"
echo "============================================================"
echo "快捷键: CMD+SHIFT+T"
echo ""
echo "操作说明:"
echo "  1. 按住 Cmd+Shift+T 开始录音"
echo "  2. 说话..."
echo "  3. 松开 Cmd+Shift+T 停止录音并自动处理"
echo "  4. 按 Ctrl+C 退出"
echo "============================================================"
echo ""

# 运行测试脚本
python3 test_hotkey_recording.py



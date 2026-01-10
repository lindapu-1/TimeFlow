#!/bin/bash
# 快速重启后端服务

# 切换到脚本所在目录的上一级（TimeFlow 根目录）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "🔄 重启后端服务..."
echo "📁 工作目录: $(pwd)"
echo ""

# 停止占用 8000 端口的进程
PORT_PID=$(lsof -ti:8000 2>/dev/null)
if [ -n "$PORT_PID" ]; then
    echo "停止进程 PID: $PORT_PID"
    kill $PORT_PID 2>/dev/null
    sleep 1
    # 如果还在运行，强制停止
    if kill -0 $PORT_PID 2>/dev/null; then
        kill -9 $PORT_PID 2>/dev/null
    fi
    echo "✅ 已停止"
else
    echo "ℹ️  没有运行中的服务"
fi

echo ""
echo "启动新的后端服务..."
echo "📍 服务地址: http://127.0.0.1:8000"
echo "💡 按 Ctrl+C 停止服务"
echo ""

# 启动服务（前台运行，可以看到日志）
python3 app.py


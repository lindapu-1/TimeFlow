#!/bin/bash
# 重启后端服务脚本

echo "🔄 重启后端服务..."
echo ""

# 1. 查找并停止现有的后端进程
echo "1️⃣  查找现有进程..."

# 查找占用 8000 端口的进程
PORT_PID=$(lsof -ti:8000 2>/dev/null)
if [ -n "$PORT_PID" ]; then
    echo "   找到占用 8000 端口的进程: PID $PORT_PID"
    echo "   正在停止..."
    kill $PORT_PID 2>/dev/null
    sleep 2
    
    # 如果还在运行，强制杀死
    if kill -0 $PORT_PID 2>/dev/null; then
        echo "   强制停止..."
        kill -9 $PORT_PID 2>/dev/null
    fi
    echo "   ✅ 进程已停止"
else
    echo "   ℹ️  没有找到运行中的后端服务"
fi

# 查找 app.py 进程
APP_PIDS=$(ps aux | grep "app.py" | grep -v grep | awk '{print $2}')
if [ -n "$APP_PIDS" ]; then
    echo "   找到 app.py 进程: $APP_PIDS"
    echo "   正在停止..."
    echo $APP_PIDS | xargs kill 2>/dev/null
    sleep 2
    echo "   ✅ app.py 进程已停止"
fi

echo ""

# 2. 等待端口释放
echo "2️⃣  等待端口释放..."
sleep 1

# 3. 启动新的后端服务
echo "3️⃣  启动新的后端服务..."
echo ""

# 切换到脚本所在目录的上一级（TimeFlow 根目录）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

# 检查后端文件是否存在
if [ ! -f "app.py" ]; then
    echo "❌ 错误: 找不到 app.py 文件"
    echo "   当前目录: $(pwd)"
    exit 1
fi

# 启动后端服务（后台运行）
echo "   启动命令: python3 app.py"
echo "   日志将输出到终端"
echo ""
echo "   💡 提示: 按 Ctrl+C 可以停止服务"
echo ""

# 在前台运行，这样可以看到日志
python3 app.py


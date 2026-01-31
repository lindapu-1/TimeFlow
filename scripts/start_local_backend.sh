#!/bin/bash
# 启动本地后端服务脚本

# 切换到项目根目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "🚀 TimeFlow 本地后端服务启动"
echo "================================"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 未安装"
    exit 1
fi

echo "✅ Python: $(python3 --version)"

# 检查端口
if lsof -ti:8000 > /dev/null 2>&1; then
    echo "⚠️  端口 8000 已被占用"
    echo "   正在停止占用端口的进程..."
    kill $(lsof -ti:8000) 2>/dev/null
    sleep 2
    echo "   ✅ 端口已释放"
fi

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "⚠️  .env 文件不存在"
    echo "   请创建 .env 文件并配置 API keys"
    echo "   参考 .env.example"
    exit 1
fi

echo "✅ .env 文件存在"

# 检查核心依赖
echo ""
echo "检查依赖..."
python3 -c "import fastapi, uvicorn, openai, requests, httpx" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  部分依赖缺失，正在安装..."
    python3 -m pip install -q fastapi uvicorn openai requests httpx python-dotenv pydantic python-multipart
fi
echo "✅ 核心依赖已安装"

# 检查可选依赖
python3 -c "import faster_whisper" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "ℹ️  faster-whisper 未安装（可选，使用云端 API 时不需要）"
fi

echo ""
echo "================================"
echo "📡 启动后端服务..."
echo "================================"
echo ""
echo "📍 服务地址: http://127.0.0.1:8000"
echo "📚 API 文档: http://127.0.0.1:8000/docs"
echo "📱 移动端接口: http://127.0.0.1:8000/api/mobile/process"
echo ""
echo "💡 提示:"
echo "   - 按 Ctrl+C 停止服务"
echo "   - 修改代码后需要重启服务（或使用 uvicorn --reload）"
echo ""
echo "================================"
echo ""

# 启动服务
python3 app.py

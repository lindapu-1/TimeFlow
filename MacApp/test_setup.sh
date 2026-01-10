#!/bin/bash
# 快速测试设置脚本

echo "🚀 TimeFlow Calendar - 快速测试"
echo "================================"
echo ""

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js 未安装"
    exit 1
fi

echo "✅ Node.js: $(node --version)"

# 检查 npm
if ! command -v npm &> /dev/null; then
    echo "❌ npm 未安装"
    exit 1
fi

echo "✅ npm: $(npm --version)"

# 检查是否已安装依赖
if [ ! -d "node_modules" ]; then
    echo "📦 安装依赖..."
    npm install
else
    echo "✅ 依赖已安装"
fi

# 检查 Python 后端
echo ""
echo "检查 Python 后端..."
if curl -s http://127.0.0.1:8000/ > /dev/null 2>&1; then
    echo "✅ 后端正在运行"
else
    echo "⚠️  后端未运行，请先启动:"
    echo "   cd .. && python3 app.py"
fi

# 检查 Ollama
echo ""
echo "检查 Ollama..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Ollama 正在运行"
else
    echo "⚠️  Ollama 未运行，请启动:"
    echo "   ollama serve"
fi

echo ""
echo "✅ 准备就绪！"
echo ""
echo "启动应用:"
echo "   npm start"
echo ""





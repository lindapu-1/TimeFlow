#!/bin/bash
# 修复麦克风权限脚本

echo "🔧 macOS 麦克风权限修复指南"
echo "============================================================"
echo ""

echo "❌ 无法访问麦克风的原因："
echo "   macOS 需要授予应用麦克风权限"
echo ""

echo "📋 解决步骤："
echo ""
echo "1️⃣  打开系统设置"
echo "   系统设置 → 隐私与安全性 → 麦克风"
echo ""
echo "2️⃣  添加 Electron 应用到允许列表"
echo "   查找并勾选以下应用之一："
echo "   - Electron（如果看到）"
echo "   - MacApp（应用名称）"
echo "   - 或者你运行 Electron 应用时使用的应用"
echo ""
echo "3️⃣  如果找不到应用，尝试："
echo "   - 重新启动 Electron 应用"
echo "   - 应用启动时会自动请求权限"
echo "   - 在弹出的权限请求对话框中点击'允许'"
echo ""

echo "============================================================"
echo "正在打开系统设置..."
echo ""

# 打开系统设置到麦克风权限页面
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"

echo "✅ 已打开系统设置"
echo ""
echo "💡 提示："
echo "   1. 在麦克风权限列表中，找到并勾选 Electron 或 MacApp"
echo "   2. 如果列表中没有，重新启动应用时会自动请求权限"
echo "   3. 确保在权限请求对话框中点击'允许'"
echo ""
echo "🔄 修复后，重新启动 Electron 应用即可"


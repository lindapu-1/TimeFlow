#!/bin/bash
# macOS权限修复脚本

echo "🔧 macOS权限设置指南"
echo "============================================================"
echo ""
echo "快捷键录音需要以下权限："
echo ""
echo "1️⃣  辅助功能权限（用于监听全局快捷键）"
echo "   系统设置 → 隐私与安全性 → 辅助功能"
echo "   添加以下应用之一："
echo "   - Terminal"
echo "   - Python"
echo "   - 或者你运行脚本的应用"
echo ""
echo "2️⃣  麦克风权限（用于录音）"
echo "   系统设置 → 隐私与安全性 → 麦克风"
echo "   添加以下应用之一："
echo "   - Terminal"
echo "   - Python"
echo ""
echo "============================================================"
echo ""
echo "正在打开系统设置..."
echo ""

# 打开系统设置到辅助功能页面
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"

echo "✅ 已打开系统设置"
echo ""
echo "请按照上述说明添加权限，然后重新运行测试脚本"


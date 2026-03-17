#!/bin/bash
# ERP-4 安全检查脚本
# 用法: bash scripts/security-check.sh

echo "=== ERP-4 安全检查 ==="

echo ""
echo "1. Python 依赖漏洞扫描..."
if command -v pip-audit &> /dev/null; then
    pip-audit -r backend/requirements.txt
else
    echo "   pip-audit 未安装，运行: pip install pip-audit"
fi

echo ""
echo "2. 检查 .env 是否在 git 跟踪中..."
if git ls-files --error-unmatch .env 2>/dev/null; then
    echo "   ⚠️  .env 文件被 git 跟踪！请立即移除"
else
    echo "   ✅ .env 未被 git 跟踪"
fi

echo ""
echo "3. 检查硬编码密钥..."
grep -rn "password.*=.*['\"]" backend/app/config.py docker-compose.yml 2>/dev/null | grep -v "environ" | grep -v "#" | grep -v "example" || echo "   ✅ 未发现硬编码密钥"

echo ""
echo "4. 检查 DEBUG 模式..."
if [ "${DEBUG}" = "true" ] || [ "${DEBUG}" = "1" ]; then
    echo "   ⚠️  DEBUG 模式已启用，生产环境请关闭"
else
    echo "   ✅ DEBUG 模式未启用"
fi

echo ""
echo "=== 检查完成 ==="

#!/bin/bash
# 飞书 PDF 签字工具启动脚本

cd "$(dirname "$0")/.."

echo "🚀 启动飞书 PDF 签字工具..."
echo ""

# 设置飞书凭证环境变量（从当前shell环境继承）
if [ -z "$FEISHU_APP_ID" ]; then
    # 从OpenClaw配置读取main账号的app_id
    FEISHU_APP_ID=$(grep -o '"appId": "cli[^"]*"' ~/.openclaw/openclaw.json 2>/dev/null | head -1 | sed 's/"appId": "//;s/"$//')
    if [ -n "$FEISHU_APP_ID" ]; then
        export FEISHU_APP_ID
        echo "✅ 已设置 FEISHU_APP_ID"
    fi
fi

if [ -z "$FEISHU_APP_SECRET" ]; then
    # 从环境变量继承
    :  # 已在shell环境中
fi

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "📦 安装依赖..."
pip install -q -r requirements.txt

echo ""
echo "✅ 准备就绪！"
echo ""
echo "📝 配置页面: http://localhost:5000/config"
echo ""

# 启动服务器
python3 server.py

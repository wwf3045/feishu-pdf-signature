# 📝 飞书 PDF 在线签字工具

从飞书多维表格读取 PDF 文件，生成一次性在线签字链接，用户手写签字后自动回传到多维表格。

## ✨ 功能特性

- ✅ **配置页面** - 可视化配置多维表格连接
- ✅ **一次性链接** - 每个链接只能使用一次，签字后自动失效
- ✅ **手写签字** - Canvas 支持鼠标/触摸设备
- ✅ **PDF 预览** - 实时预览 PDF 文档
- ✅ **自动回传** - 签字完成后自动上传到多维表格

## 🚀 快速开始

### 1. 启动服务

```bash
cd ~/.openclaw/workspace/skills/feishu-pdf-signature
./scripts/start.sh
```

### 2. 配置多维表格

访问: http://localhost:5000/config

填写以下信息：
- **多维表格 App Token**: 从 URL 获取（例如 `bascnxxxxxxxxxxxx`）
- **数据表 ID**: 要操作的数据表 ID
- **PDF 文件字段名**: 存储待签字 PDF 的字段
- **签字后 PDF 字段名**: 存储签字后 PDF 的字段
- **签字人字段名**: （可选）记录签字人姓名

### 3. 生成签字链接

调用 API 生成签字链接：

```bash
curl -X POST http://localhost:5000/api/generate-link \
  -H "Content-Type: application/json" \
  -d '{
    "record_id": "记录ID",
    "pdf_url": "PDF下载地址"
  }'
```

返回：
```json
{
  "success": true,
  "url": "http://localhost:5000/sign?token=xxx",
  "token": "raw_token"
}
```

## 📁 目录结构

```
feishu-pdf-signature/
├── SKILL.md              # Skill 说明
├── README.md             # 本文件
├── server.py             # Flask 主服务器
├── requirements.txt      # Python 依赖
├── config.json           # 配置文件（自动生成）
├── tokens.json           # Token 数据库（自动生成）
├── scripts/
│   └── start.sh          # 启动脚本
├── templates/
│   ├── config.html       # 配置页面
│   └── sign.html         # 签字页面
└── static/               # 静态资源（自动创建）
```

## 🔧 技术栈

- **后端**: Flask + Python
- **前端**: 原生 JavaScript + PDF.js + pdf-lib
- **存储**: JSON 文件（配置 + Token）
- **签字**: Canvas（支持触摸/鼠标）

## 📋 API 文档

### POST /api/generate-link

生成签字链接

**请求体:**
```json
{
  "record_id": "多维表格记录ID",
  "pdf_url": "PDF文件下载地址"
}
```

**响应:**
```json
{
  "success": true,
  "url": "签字页面完整URL",
  "token": "原始token"
}
```

### POST /api/sign/submit

提交签字（内部使用）

## ⚠️ 注意事项

1. **飞书 API 配置**: 当前版本需要手动配置飞书访问令牌
2. **生产环境**: 建议使用数据库替代 JSON 文件存储
3. **HTTPS**: 生产环境建议使用 HTTPS

## 🎯 待完善功能

- [ ] 飞书 OAuth 自动获取 access_token
- [ ] 签字位置选择（用户可拖拽选择签字位置）
- [ ] 支持多页 PDF 签字
- [ ] 签字历史记录
- [ ] 短信/邮件验证签字人身份

## 📞 问题反馈

如有问题请联系开发者。

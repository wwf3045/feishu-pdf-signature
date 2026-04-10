# feishu-pdf-signature - 飞书 PDF 在线签字工具

## 功能

从飞书多维表格读取 PDF 文件，生成一次性在线签字链接，用户签字后自动回传到多维表格。

## 目录结构

```
feishu-pdf-signature/
├── SKILL.md
├── server.py              # Flask Web 服务
├── config.json            # 配置文件
├── requirements.txt       # Python 依赖
└── scripts/
    └── start.sh           # 启动脚本
```

## 安装

```bash
cd ~/.openclaw/workspace/skills/feishu-pdf-signature
pip3 install -r requirements.txt
```

## 启动

```bash
python3 server.py
```

默认运行在 `http://localhost:5000`

## 配置

访问 `http://localhost:5000/config` 配置：
- 多维表格 app_token
- PDF 文件字段名
- 签字后文件字段名
- 签字人姓名字段（可选）

## API

- `GET /config` - 配置页面
- `POST /config` - 保存配置
- `GET /sign?record_id=xxx` - 签字页面
- `POST /sign/submit` - 提交签字

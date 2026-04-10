#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书 PDF 在线签字工具 - 主服务器
"""

import os
import json
import uuid
import datetime
import secrets
import tempfile
import base64
from io import BytesIO
from flask import Flask, request, jsonify, render_template, redirect, send_from_directory
from flask_cors import CORS
import requests
import jwt
import io
import os

# 配置
app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = secrets.token_hex(32)

# 路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')
TOKEN_DB_FILE = os.path.join(BASE_DIR, 'tokens.json')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
PDF_DIR = os.path.join(BASE_DIR, 'pdfs')

# 确保目录存在
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)

# 初始化文件
def init_files():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'app_token': '',
                'table_id': '',
                'pdf_field': '',
                'signed_pdf_field': '',
                'signer_field': '',
                'jwt_secret': secrets.token_hex(32)
            }, f, ensure_ascii=False, indent=2)

    if not os.path.exists(TOKEN_DB_FILE):
        with open(TOKEN_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)

init_files()

# 加载配置
def load_config():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# Token 管理
def load_tokens():
    with open(TOKEN_DB_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_tokens(tokens):
    with open(TOKEN_DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(tokens, f, ensure_ascii=False, indent=2)

def create_token(record_id, pdf_url, config=None):
    """创建一次性签字 token(可传入多表格配置)"""
    if config is None:
        config = load_config()

    tokens = load_tokens()

    # 如果pdf_url已经是本地路径(/pdf/...)，直接使用，不再重复下载
    if pdf_url and pdf_url.startswith('/pdf/'):
        pdf_filename = pdf_url.replace('/pdf/', '')
        pdf_path = os.path.join(PDF_DIR, pdf_filename)
        if os.path.exists(pdf_path):
            print(f"✅ PDF已存在，直接使用: {pdf_path}")
        else:
            print(f"⚠️ PDF文件不存在: {pdf_path}")
            pdf_filename = None
    else:
        # 下载 PDF 到本地
        pdf_filename = f"{record_id}_{uuid.uuid4().hex[:8]}.pdf"
        pdf_path = os.path.join(PDF_DIR, pdf_filename)

        try:
            # 尝试下载 PDF
            headers = {}
            response = requests.get(pdf_url, headers=headers, timeout=30)
            response.raise_for_status()

            with open(pdf_path, 'wb') as f:
                f.write(response.content)

            print(f"✅ PDF 已下载: {pdf_path}")
        except Exception as e:
            print(f"⚠️ PDF 下载失败: {e}, 将使用示例 PDF")
            pdf_filename = None

    token = secrets.token_urlsafe(32)
    tokens[token] = {
        'record_id': record_id,
        'pdf_url': pdf_url,
        'pdf_filename': pdf_filename,
        'created_at': datetime.datetime.now().isoformat(),
        'used': False,
        'used_at': None,
        # 存储多表格配置,签字完成时使用
        'app_token': config.get('app_token'),
        'table_id': config.get('table_id'),
        'signed_pdf_field': config.get('signed_pdf_field', '已签字PDF'),
        'pdf_field': config.get('pdf_field', '原始PDF'),
        'personal_base_token': config.get('personal_base_token'),
    }

    save_tokens(tokens)

    # 直接返回简单token(不含特殊字符)
    return token, token

def validate_token(token):
    """验证 token 是否有效"""
    try:
        tokens = load_tokens()

        if token not in tokens:
            return None

        token_data = tokens[token]
        if token_data['used']:
            return None

        return token_data
    except Exception as e:
        print(f"Token 验证失败: {e}")
        return None

def mark_token_used(token):
    """标记 token 为已使用"""
    try:
        tokens = load_tokens()

        if token in tokens:
            tokens[token]['used'] = True
            tokens[token]['used_at'] = datetime.datetime.now().isoformat()
            save_tokens(tokens)
            return True
    except Exception as e:
        print(f"标记 token 失败: {e}")
        pass
    return False
    return False

# 飞书 API
def get_feishu_access_token(personal_base_token=None):
    """获取飞书访问令牌

    优先级:
    1. personal_base_token(多维表格服务侧插件授权码)
    2. tenant_access_token(应用凭证,通过 app_id/app_secret 获取)
    """
    # 优先使用 PersonalBaseToken(多表格服务侧插件场景)
    if personal_base_token:
        return personal_base_token

    # 否则使用 tenant_access_token
    app_id = os.environ.get('FEISHU_APP_ID') or os.environ.get('APP_ID')
    app_secret = os.environ.get('FEISHU_APP_SECRET') or os.environ.get('APP_SECRET')

    if not app_id or not app_secret:
        print("⚠️ 未配置飞书凭证,使用模拟模式")
        return None

    try:
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={"app_id": app_id, "app_secret": app_secret}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get('code') == 0:
            return data.get('tenant_access_token')
        else:
            print(f"❌ 获取access_token失败: {data}")
            return None
    except Exception as e:
        print(f"❌ 获取access_token异常: {e}")
        return None

def download_pdf(url):
    """下载 PDF 文件"""
    response = requests.get(url)
    response.raise_for_status()
    return response.content

def download_pdf_from_feishu(file_token, personal_base_token=None):
    """从飞书下载PDF文件"""
    import sys
    access_token = get_feishu_access_token(personal_base_token)
    if not access_token:
        print("❌ 无法获取飞书访问令牌")
        return None

    # 多维表格服务侧插件用 base-api.feishu.cn
    domain = "https://base-api.feishu.cn" if personal_base_token else "https://open.feishu.cn"
    url = f"{domain}/open-apis/drive/v1/medias/{file_token}/download"

    # 对 token 进行 ASCII 编码,替换非ASCII字符,避免 HTTP header 编码错误
    def safe_token(t):
        if t is None:
            return None
        if isinstance(t, str):
            return t.encode('ascii', errors='replace').decode('ascii')
        if isinstance(t, bytes):
            return t.decode('ascii', errors='replace')
        return str(t)

    safe_access_token = safe_token(access_token)

    # 调试
    token_repr = str(access_token)[:50] if access_token else 'None'
    print(f"🔍 token类型: {type(access_token)}, 值: {token_repr}")

    # 确保Authorization header只包含ASCII字符
    auth_value = f"Bearer {safe_access_token}"
    # 强制ASCII编码检查
    try:
        auth_value.encode('ascii')
        print(f"✅ Authorization header ASCII检查通过,长度: {len(auth_value)}")
    except UnicodeEncodeError as e:
        print(f"⚠️ Authorization header包含非ASCII字符: {e}")
        auth_value = auth_value.encode('ascii', errors='replace').decode('ascii')
        print(f"🔧 清洗后: {auth_value[:50]}")

    headers = {
        "Authorization": auth_value
    }

    print(f"📥 正在从飞书下载文件: {file_token}")

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        print(f"✅ 下载成功,大小: {len(response.content)} 字节")
        return response.content
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def upload_to_feishu(pdf_content, filename, config=None):
    """上传文件到飞书并获取 file_token(用于多维表格附件)"""
    if config is None:
        config = load_config()

    # 先保存到本地
    local_path = os.path.join(PDF_DIR, filename)
    with open(local_path, 'wb') as f:
        f.write(pdf_content)
    print(f"✅ PDF 已保存到本地: {local_path}")

    # 上传到飞书
    personal_base_token = config.get('personal_base_token')
    access_token = get_feishu_access_token(personal_base_token)
    if not access_token:
        print("⚠️ 无法获取飞书访问令牌,返回本地文件名")
        return filename

    try:
        # 使用正确的 media upload API
        domain = "https://base-api.feishu.cn" if personal_base_token else "https://open.feishu.cn"
        url = f"{domain}/open-apis/drive/v1/medias/upload_all"
        def safe_token(t):
            if isinstance(t, str):
                return t.encode('ascii', errors='replace').decode('ascii')
            return t
        headers = {
            "Authorization": f"Bearer {safe_token(access_token)}"
        }

        # 使用 requests_toolbelt 处理 multipart
        try:
            from requests_toolbelt import MultipartEncoder
            m = MultipartEncoder(
                fields={
                    'file_name': filename,
                    'parent_type': 'bitable_file',
                    'parent_node': config.get('app_token', ''),
                    'size': str(len(pdf_content)),
                    'file': (filename, pdf_content, 'application/pdf'),
                }
            )
            headers['Content-Type'] = m.content_type
            response = requests.post(url, headers=headers, data=m, timeout=30)
        except ImportError:
            # 如果没有 requests_toolbelt,使用普通 multipart
            response = requests.post(
                url,
                headers=headers,
                data={
                    'file_name': filename,
                    'parent_type': 'bitable_file',
                    'parent_node': config.get('app_token', ''),
                    'size': str(len(pdf_content)),
                },
                files={'file': (filename, pdf_content, 'application/pdf')},
                timeout=30
            )

        data = response.json()

        if data.get('code') == 0:
            file_token = data.get('data', {}).get('file_token')
            print(f"✅ 文件上传成功,file_token: {file_token}")
            return file_token
        else:
            print(f"❌ 文件上传失败: {data.get('msg')}")
            return filename
    except Exception as e:
        print(f"❌ 上传异常: {e}")
        import traceback
        traceback.print_exc()
        return filename

def add_signature_to_pdf(pdf_bytes, signature_bytes, x=50, y=300, width=150, height=50):
    """把签字图片添加到 PDF 指定位置"""
    try:
        # 保存签字图片
        sig_path = os.path.join(PDF_DIR, f"temp_sig_{uuid.uuid4().hex[:8]}.png")
        with open(sig_path, 'wb') as f:
            f.write(signature_bytes)
        print(f"✅ 签字图片已保存: {sig_path}")

        return pdf_bytes
    except Exception as e:
        print(f"⚠️ 添加签字到 PDF 失败: {e}")
        import traceback
        traceback.print_exc()
        return pdf_bytes

def update_bitable_record(record_id, field_name, value, config=None):
    """更新多维表格记录(通用版,可用于文本/URL/附件)"""
    if config is None:
        config = load_config()

    if not config.get('app_token') or not config.get('table_id'):
        raise Exception("未配置多维表格信息")

    personal_base_token = config.get('personal_base_token')
    access_token = get_feishu_access_token(personal_base_token)
    if not access_token:
        raise Exception("无法获取飞书访问令牌")

    print(f"📝 准备更新多维表格:")
    print(f"   - 记录 ID: {record_id}")
    print(f"   - 字段名: {field_name}")
    print(f"   - 值类型: {'URL' if str(value).startswith('http') else '附件/file_token'}")

    try:
        # 多维表格服务侧插件用 base-api.feishu.cn
        domain = "https://base-api.feishu.cn" if personal_base_token else "https://open.feishu.cn"
        url = f"{domain}/open-apis/bitable/v1/apps/{config['app_token']}/tables/{config['table_id']}/records/{record_id}"
        def safe_token(t):
            if isinstance(t, str):
                return t.encode('ascii', errors='replace').decode('ascii')
            return t
        headers = {
            "Authorization": f"Bearer {safe_token(access_token)}",
            "Content-Type": "application/json"
        }

        # 判断是URL文本还是附件file_token
        if str(value).startswith('http'):
            # URL文本字段(如超链接)
            field_data = value
        else:
            # 附件字段(file_token)
            field_data = [{
                "file_token": value,
                "name": f"signed_{record_id}.pdf",
                "size": 0
            }]

        data = {
            "fields": {
                field_name: field_data
            }
        }

        print(f"📤 正在更新多维表格... payload={data}")
        response = requests.put(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        result = response.json()

        if result.get('code') == 0:
            print("✅ 多维表格记录更新成功")
            return True
        else:
            print(f"❌ 更新失败: {result.get('msg')}")
            raise Exception(result.get('msg'))
    except Exception as e:
        print(f"❌ 更新多维表格异常: {e}")
        import traceback
        traceback.print_exc()
        raise e

def get_bitable_record(record_id, config):
    """从多维表格获取记录"""
    app_token = config.get('app_token')
    table_id = config.get('table_id')
    personal_base_token = config.get('personal_base_token')

    if not app_token or not table_id:
        raise Exception("未配置多维表格信息")

    access_token = get_feishu_access_token(personal_base_token)
    if not access_token:
        raise Exception("无法获取飞书访问令牌")

    # 多维表格服务侧插件用 base-api.feishu.cn
    domain = "https://base-api.feishu.cn" if personal_base_token else "https://open.feishu.cn"
    url = f"{domain}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}"
    def safe_token(t):
        if isinstance(t, str):
            return t.encode('ascii', errors='replace').decode('ascii')
        return t
    headers = {
        "Authorization": f"Bearer {safe_token(access_token)}",
        "Content-Type": "application/json"
    }

    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if data.get('code') == 0:
        return data.get('data', {}).get('record', {})
    else:
        raise Exception(f"获取记录失败: {data.get('msg')}")

def get_file_download_url(file_token, config=None):
    """获取文件的下载链接"""
    if config is None:
        config = load_config()
    personal_base_token = config.get('personal_base_token')
    access_token = get_feishu_access_token(personal_base_token)
    if not access_token:
        return None

    domain = "https://base-api.feishu.cn" if personal_base_token else "https://open.feishu.cn"
    url = f"{domain}/open-apis/drive/v1/medias/{file_token}/download"
    return url

# 路由
@app.route('/')
def index():
    return redirect('/config')

@app.route('/config', methods=['GET', 'POST'])
def config_page():
    if request.method == 'POST':
        config = load_config()
        config.update({
            'app_token': request.form.get('app_token', ''),
            'table_id': request.form.get('table_id', ''),
            'pdf_field': request.form.get('pdf_field', ''),
            'signed_pdf_field': request.form.get('signed_pdf_field', ''),
            'signer_field': request.form.get('signer_field', '')
        })
        save_config(config)
        return redirect('/config?success=1')

    config = load_config()
    return render_template('config.html', config=config, success=request.args.get('success'))

@app.route('/sign', methods=['GET'])
def sign_page():
    token = request.args.get('token')
    if not token:
        return "无效的链接", 400

    token_data = validate_token(token)
    if not token_data:
        return "链接已失效或不存在", 404

    return render_template('sign.html', jwt_token=token)

@app.route('/pdf/<filename>')
def serve_pdf(filename):
    """提供下载的 PDF 文件"""
    return send_from_directory(PDF_DIR, filename)

def create_demo_pdf_bytes():
    """创建演示 PDF"""
    try:
        from pypdf import PdfWriter, PdfReader
        from pypdf.generic import NameObject, DictionaryObject, ArrayObject, NumberObject
        import io

        writer = PdfWriter()
        page = writer.add_blank_page(width=600, height=800)

        # 保存演示 PDF
        demo_path = os.path.join(PDF_DIR, 'demo.pdf')
        with open(demo_path, 'wb') as f:
            writer.write(f)

        with open(demo_path, 'rb') as f:
            return f.read()
    except Exception as e:
        print(f"创建演示 PDF 失败: {e}")
        # 返回空的 PDF
        return b'%PDF-1.4'

def embed_signature_in_pdf(pdf_bytes, signature_bytes, position_data):
    """将签字图片嵌入 PDF 指定位置,保留所有页面"""
    try:
        from pdf2image import convert_from_bytes
        from PIL import Image
        import io
        from pypdf import PdfReader, PdfWriter

        print(f"📐 位置信息: {position_data}")

        # 如果没有位置信息,使用默认位置
        if not position_data:
            position_data = {'page': 1, 'x': 50, 'y': 700, 'width': 150, 'height': 50}

        page_num = position_data.get('page', 1)  # 页码从1开始
        x = position_data.get('x', 50)
        y = position_data.get('y', 700)
        sig_width = position_data.get('width', 150)
        sig_height = position_data.get('height', 50)

        print(f"📝 签字位置: 页{page_num}, x={x}, y={y}, 宽={sig_width}, 高={sig_height}")

        # 获取原PDF总页数
        reader = PdfReader(io.BytesIO(pdf_bytes))
        total_pages = len(reader.pages)
        print(f"📄 PDF总页数: {total_pages}")

        # 将整个PDF转换为图片
        print("🖼️ 正在转换 PDF 为图片...")
        images = convert_from_bytes(pdf_bytes, dpi=150)
        if not images:
            print("❌ PDF 转换失败")
            return pdf_bytes

        print(f"✅ 转换得到 {len(images)} 张图片")

        # 打开签字图片(保持原始大小,后面会按比例缩放)
        sig_image = Image.open(io.BytesIO(signature_bytes)).convert("RGBA")

        # 在对应页面上添加签字
        target_page_idx = page_num - 1  # 转为0索引
        if target_page_idx < len(images):
            page_image = images[target_page_idx]
            pdf_width, pdf_height = page_image.size
            print(f"✅ 第{page_num}页尺寸: {pdf_width}x{pdf_height}")

            # 前端发送的坐标是600x800设计坐标系,原点在左下角
            # 需要映射到实际图片尺寸
            # x_ratio = pdf_width / 600, y_ratio = pdf_height / 800
            x_ratio = pdf_width / 600.0
            y_ratio = pdf_height / 800.0

            # PDF坐标系:y=0是底部,y=800是顶部
            # 图片坐标系:y=0是顶部,y=pdf_height是底部
            # 所以:y_offset = (800 - y - sig_height) * y_ratio
            x_pos = x * x_ratio
            y_offset = (800 - y - sig_height) * y_ratio

            print(f"📍 坐标映射: 前端(600x800)→实际({pdf_width}x{pdf_height})")
            print(f"📍 前端坐标: x={x}, y={y}, sig_w={sig_width}, sig_h={sig_height}")
            print(f"📍 实际坐标: x_pos={x_pos}, y_offset={y_offset}")

            # 调整签字图片大小以匹配比例
            sig_image_resized = sig_image.resize(
                (int(sig_width * x_ratio), int(sig_height * y_ratio)),
                Image.Resampling.LANCZOS
            )

            # 在图片上粘贴签字(使用alpha遮罩)
            page_image.paste(sig_image_resized, (int(x_pos), int(y_offset)), sig_image_resized)
            images[target_page_idx] = page_image
        else:
            print(f"⚠️ 页码 {page_num} 超出范围")

        # 将所有图片转回 PDF(多页)
        print("📄 正在将图片转回 PDF...")
        output_buffer = io.BytesIO()
        # 保存第一页
        images[0].save(
            output_buffer,
            format='PDF',
            resolution=150,
            save_all=True,
            append_images=images[1:]
        )
        output_bytes = output_buffer.getvalue()

        print(f"✅ 签字嵌入完成,输出大小: {len(output_bytes)} 字节")
        return output_bytes

    except Exception as e:
        print(f"❌ 签字嵌入失败: {e}")
        import traceback
        traceback.print_exc()
        return pdf_bytes  # 返回原始PDF

@app.route('/api/sign/submit', methods=['POST'])
def submit_sign():
    print("\n========== 收到提交请求 ==========")
    data = request.json
    print(f"收到数据: {list(data.keys()) if data else 'None'}")

    jwt_token = data.get('token')
    signature_data = data.get('signature')  # base64 图片
    position_data = data.get('position')  # 签字位置信息
    pdf_base64 = data.get('pdf')  # base64 PDF

    if not jwt_token or not signature_data:
        print("❌ 参数缺失")
        return jsonify({'success': False, 'error': '参数缺失'}), 400

    token_data = validate_token(jwt_token)
    if not token_data:
        print("❌ Token 已失效")
        return jsonify({'success': False, 'error': '链接已失效'}), 400

    try:
        # 优先用token里存的配置(支持多表格),否则fallback到全局config
        token_config = {
            'app_token': token_data.get('app_token'),
            'table_id': token_data.get('table_id'),
            'signed_pdf_field': token_data.get('signed_pdf_field', '已签字PDF'),
            'pdf_field': token_data.get('pdf_field', '原始PDF'),
            'personal_base_token': token_data.get('personal_base_token'),
        }
        config = load_config()
        # token里的配置优先
        if token_config.get('app_token'):
            config.update(token_config)
        print(f"✅ 配置加载成功: app_token={config.get('app_token')}, signed_pdf_field={config.get('signed_pdf_field')}")

        # 解码签字图片
        print("🖼️ 正在解码签字图片...")
        sig_part = signature_data.split(',')[1] if ',' in signature_data else signature_data
        signature_bytes = base64.b64decode(sig_part)
        print(f"✅ 签字解码成功,大小: {len(signature_bytes)} 字节")

        # 获取 PDF 文件
        pdf_bytes = None

        if pdf_base64:
            print("📄 前端发送了 PDF 数据")
            pdf_bytes = base64.b64decode(pdf_base64)
            print(f"✅ PDF 解码成功,大小: {len(pdf_bytes)} 字节")
        else:
            print("⚠️ 前端未发送 PDF 数据,尝试其他方式...")
            # 尝试从服务端保存的源文件读取
            pdf_url = token_data.get('pdf_url', '')
            if pdf_url and pdf_url.startswith('/pdf/'):
                pdf_filename = pdf_url.replace('/pdf/', '')
                pdf_path = os.path.join(PDF_DIR, pdf_filename)
                if os.path.exists(pdf_path):
                    print(f"📄 从服务端缓存读取 PDF: {pdf_path}")
                    with open(pdf_path, 'rb') as f:
                        pdf_bytes = f.read()
                    print(f"✅ PDF 读取成功,大小: {len(pdf_bytes)} 字节")

        if not pdf_bytes:
            print("❌ 无法获取 PDF,使用空白 PDF")
            pdf_bytes = create_demo_pdf_bytes()

        # 将签字嵌入 PDF
        print("📝 正在将签字嵌入 PDF...")
        pdf_bytes = embed_signature_in_pdf(pdf_bytes, signature_bytes, position_data)
        print(f"✅ PDF 签字嵌入完成,大小: {len(pdf_bytes)} 字节")

        # 保存到本地
        filename = f"signed_{token_data['record_id']}_{uuid.uuid4().hex[:8]}.pdf"
        local_path = os.path.join(PDF_DIR, filename)
        with open(local_path, 'wb') as f:
            f.write(pdf_bytes)
        print(f"💾 PDF已保存到本地: {local_path}")

        # 生成下载链接
        download_url = f"/pdf/{filename}"
        print(f"🔗 下载链接: {download_url}")

        # 标记 token 已使用
        mark_token_used(jwt_token)
        print("✅ Token 已标记为已使用")

        # 尝试回传多维表格
        bitable_success = False
        try:
            signed_pdf_field = config.get('signed_pdf_field', '已签字PDF')
            if signed_pdf_field and config.get('app_token') and config.get('table_id'):
                print("📤 正在上传签字PDF到飞书...")
                file_token = upload_to_feishu(pdf_bytes, filename, config)
                if file_token and file_token != filename:
                    print("📝 正在更新多维表格...")
                    update_bitable_record(token_data['record_id'], signed_pdf_field, file_token, config)
                    bitable_success = True
                    print("✅ 已回传多维表格")
                else:
                    print("⚠️ 上传失败,跳过多维表格更新")
            else:
                print("⚠️ 未配置多维表格字段,跳过")
        except Exception as e:
            print(f"⚠️ 回传多维表格失败: {e}")

        print("========== 提交成功 ==========\n")
        return jsonify({
            'success': True,
            'filename': filename,
            'download_url': download_url,
            'bitable_success': bitable_success
        })
    except Exception as e:
        print(f"❌ 提交失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/pdf-info', methods=['GET'])
def get_pdf_info():
    """获取 PDF 信息"""
    jwt_token = request.args.get('token')
    if not jwt_token:
        return jsonify({'success': False, 'error': '参数缺失'}), 400

    token_data = validate_token(jwt_token)
    if not token_data:
        return jsonify({'success': False, 'error': '链接已失效'}), 400

    return jsonify({
        'success': True,
        'pdf_filename': token_data.get('pdf_filename'),
        'pdf_url': token_data.get('pdf_url')
    })

@app.route('/api/generate-link', methods=['POST'])
def generate_link():
    """生成签字链接(供外部调用)"""
    data = request.json
    record_id = data.get('record_id')
    pdf_url = data.get('pdf_url')  # 可选,如果不传则从多维表格获取

    if not record_id:
        return jsonify({'success': False, 'error': '缺少record_id'}), 400

    config = load_config()

    # 如果没有提供pdf_url,从多维表格获取
    if not pdf_url and config.get('app_token') and config.get('table_id') and config.get('pdf_field'):
        try:
            print(f"📋 从多维表格获取PDF: record_id={record_id}")
            # 获取记录
            record = get_bitable_record(record_id, config)
            if record:
                # 获取fields字典
                fields = record.get('fields', {})
                pdf_field_data = fields.get(config['pdf_field'])
                print(f"📄 字段数据: {pdf_field_data}")
                if pdf_field_data and len(pdf_field_data) > 0:
                    # 获取文件token
                    file_token = pdf_field_data[0].get('token') or pdf_field_data[0].get('file_token')
                    pdf_name = pdf_field_data[0].get('name', 'document.pdf')
                    print(f"📄 文件token: {file_token}, 文件名: {pdf_name}")

                    if file_token:
                        # 服务端下载PDF
                        pdf_bytes = download_pdf_from_feishu(file_token)
                        if pdf_bytes:
                            # 保存到本地
                            local_filename = f"source_{record_id}_{uuid.uuid4().hex[:8]}.pdf"
                            local_path = os.path.join(PDF_DIR, local_filename)
                            with open(local_path, 'wb') as f:
                                f.write(pdf_bytes)
                            print(f"✅ PDF已下载保存到本地: {local_path}")
                            pdf_url = f"/pdf/{local_filename}"
                        else:
                            return jsonify({'success': False, 'error': 'PDF下载失败'}), 500
                    else:
                        return jsonify({'success': False, 'error': 'PDF文件token无效'}), 400
                else:
                    return jsonify({'success': False, 'error': '多维表格中该记录没有PDF文件'}), 400
            else:
                return jsonify({'success': False, 'error': '找不到该记录'}), 400
        except Exception as e:
            print(f"❌ 从多维表格获取PDF失败: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': f'获取PDF失败: {str(e)}'}), 500

    if not pdf_url:
        return jsonify({'success': False, 'error': '缺少pdf_url'}), 400

    jwt_token, raw_token = create_token(record_id, pdf_url)
    sign_url = f"{request.host_url}sign?token={jwt_token}"

    return jsonify({
        'success': True,
        'url': sign_url,
        'token': raw_token
    })


@app.route('/api/generate_link', methods=['POST'])
def generate_link_get():
    """生成签字链接（POST接口，供多维表格自动化调用）
    
    参数（JSON body）:
        record_id: 多维表格记录ID（必填）
        app_token: 多维表格的app_token（可选，有默认值）
        table_id: 数据表ID（可选，有默认值）
        pdf_field: PDF字段名（可选，默认"原始PDF"）
        signed_pdf_field: 已签字PDF字段名（可选，默认"已签字PDF"）
        sign_link_field: 签字链接回填到的字段名（可选，不传则只生成链接不回填）
        personal_base_token: 多维表格授权码（可选，用于多表格场景）
    
    示例:
        POST http://192.168.111.10:5000/api/generate_link
        {
            "record_id": "recxxxxx",
            "app_token": "xxx",
            "table_id": "xxx",
            "pdf_field": "原始PDF",
            "signed_pdf_field": "已签字PDF",
            "sign_link_field": "签字链接",
            "personal_base_token": "pt-xxx"
        }
    """
    data = request.json
    if not data:
        return jsonify({'success': False, 'error': '缺少JSON body'}), 400
    
    record_id = data.get('record_id')
    if not record_id:
        return jsonify({'success': False, 'error': '缺少record_id参数'}), 400
    
    # 优先使用JSON参数，否则使用config默认值
    config = load_config()
    app_token = data.get('app_token') or config.get('app_token')
    table_id = data.get('table_id') or config.get('table_id')
    pdf_field = data.get('pdf_field') or config.get('pdf_field', '原始PDF')
    signed_pdf_field = data.get('signed_pdf_field') or config.get('signed_pdf_field', '已签字PDF')
    sign_link_field = data.get('sign_link_field')
    personal_base_token = data.get('personal_base_token') or config.get('personal_base_token')
    
    print(f"📋 [POST] 生成签字链接: record_id={record_id}")
    print(f"   app_token={app_token}, table_id={table_id}, pdf_field={pdf_field}")
    print(f"   signed_pdf_field={signed_pdf_field}, sign_link_field={sign_link_field}")
    print(f"   personal_base_token: {'已传入' if personal_base_token else '未传入'}")

    if not app_token or not table_id:
        return jsonify({'success': False, 'error': '缺少app_token或table_id，请通过参数传入'}), 400

    # 构建临时config(包含personal_base_token用于API调用认证)
    temp_config = {
        'app_token': app_token,
        'table_id': table_id,
        'pdf_field': pdf_field,
        'signed_pdf_field': signed_pdf_field,
        'personal_base_token': personal_base_token
    }

    # 从多维表格获取PDF
    try:
        record = get_bitable_record(record_id, temp_config)
        if record:
            fields = record.get('fields', {})
            pdf_field_data = fields.get(pdf_field)
            print(f"📄 字段「{pdf_field}」数据: {pdf_field_data}")
            if pdf_field_data and len(pdf_field_data) > 0:
                file_token = pdf_field_data[0].get('token') or pdf_field_data[0].get('file_token')
                pdf_name = pdf_field_data[0].get('name', 'document.pdf')
                print(f"📄 文件token: {file_token}, 文件名: {pdf_name}")
                
                if file_token:
                    pdf_bytes = download_pdf_from_feishu(file_token, temp_config.get('personal_base_token'))
                    if pdf_bytes:
                        local_filename = f"source_{record_id}_{uuid.uuid4().hex[:8]}.pdf"
                        local_path = os.path.join(PDF_DIR, local_filename)
                        with open(local_path, 'wb') as f:
                            f.write(pdf_bytes)
                        print(f"✅ PDF已下载保存到本地: {local_path}")
                        pdf_url = f"/pdf/{local_filename}"
                    else:
                        return jsonify({'success': False, 'error': 'PDF下载失败'}), 500
                else:
                    return jsonify({'success': False, 'error': 'PDF文件token无效'}), 400
            else:
                return jsonify({'success': False, 'error': f'字段「{pdf_field}」中没有PDF文件'}), 400
        else:
            return jsonify({'success': False, 'error': '找不到该记录'}), 400
    except Exception as e:
        print(f"❌ [POST] 从多维表格获取PDF失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'获取PDF失败: {str(e)}'}), 500
    
    jwt_token, raw_token = create_token(record_id, pdf_url, temp_config)
    sign_url = f"{request.host_url}sign?token={jwt_token}"
    
    # 如果提供了sign_link_field，回填到多维表格
    if sign_link_field:
        try:
            print(f"📝 正在回填签字链接到字段「{sign_link_field}」...")
            update_bitable_record(record_id, sign_link_field, sign_url, temp_config)
            print("✅ 签字链接已回填到多维表格")
        except Exception as e:
            print(f"❌ 回填签字链接失败: {e}")
            return jsonify({
                'success': False,
                'error': f'回填签字链接失败: {str(e)}',
                'url': sign_url,
                'token': raw_token
            }), 500
    
    return jsonify({
        'success': True,
        'url': sign_url,
        'token': raw_token
    })

if __name__ == '__main__':
    print("🚀 飞书 PDF 签字工具启动...")
    print(f"📁 工作目录: {BASE_DIR}")
    print(f"🔗 配置页面: http://localhost:5000/config")
    app.run(host='0.0.0.0', port=5000, debug=False)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速生成 PDF 签字链接脚本
"""

import requests
import json
import sys

def load_config():
    """加载配置"""
    import os
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_sign_link(record_id, pdf_url):
    """生成签字链接"""
    config = load_config()
    
    url = "http://localhost:5000/api/generate-link"
    data = {
        "record_id": record_id,
        "pdf_url": pdf_url
    }
    
    response = requests.post(url, json=data)
    result = response.json()
    
    if result.get('success'):
        print("✅ 签字链接生成成功！")
        print(f"🔗 链接: {result['url']}")
        return result['url']
    else:
        print(f"❌ 生成失败: {result.get('error')}")
        return None

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("使用方法:")
        print(f"  python3 {sys.argv[0]} <记录ID> <PDF下载地址>")
        print("")
        print("示例:")
        print(f"  python3 {sys.argv[0]} recxxxxxxxxxxxx https://example.com/test.pdf")
        sys.exit(1)
    
    record_id = sys.argv[1]
    pdf_url = sys.argv[2]
    
    generate_sign_link(record_id, pdf_url)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
工具函数模块，包含一些通用的辅助函数
"""

import os
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse


def extract_domain(url: str) -> str:
    """从URL中提取域名
    
    Args:
        url: 网页URL
        
    Returns:
        域名字符串
    """
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        return domain.replace('.', '_')
    except Exception:
        # 如果解析失败，使用简单的分割方法
        return url.split('//')[-1].split('/')[0].replace('.', '_')


def ensure_directory(directory: str) -> None:
    """确保目录存在，如果不存在则创建
    
    Args:
        directory: 目录路径
    """
    os.makedirs(directory, exist_ok=True)


def is_valid_url(url: str) -> bool:
    """检查URL是否有效
    
    Args:
        url: 要检查的URL
        
    Returns:
        URL是否有效
    """
    if not isinstance(url, str):
        return False
        
    return url.startswith('http://') or url.startswith('https://')


def format_filename(index: int, domain: str, timestamp: str, extension: str) -> str:
    """格式化文件名
    
    Args:
        index: URL索引
        domain: 域名
        timestamp: 时间戳
        extension: 文件扩展名
        
    Returns:
        格式化后的文件名
    """
    return f"{index}_{domain}_{timestamp}.{extension}"

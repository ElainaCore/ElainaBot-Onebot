#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
通用工具函数模块
提供框架中常用的工具函数
"""

import re
import json
import time
import hashlib
import logging
import asyncio
import threading
from typing import Dict, Any, Optional, List, Union, Callable, TypeVar
from functools import lru_cache

from .constants import (
    CQ_ESCAPE_CHARS, CQ_UNESCAPE_CHARS,
    SEGMENT_DISPLAY_MAP, MESSAGE_DISPLAY_MAX_LENGTH
)

logger = logging.getLogger('ElainaBot.core.utils')

T = TypeVar('T')


# ==================== 字符串处理 ====================

def escape_cq(s: str, escape_comma: bool = True) -> str:
    """转义CQ码特殊字符"""
    result = s.replace("&", "&amp;").replace("[", "&#91;").replace("]", "&#93;")
    if escape_comma:
        result = result.replace(",", "&#44;")
    return result


def unescape_cq(s: str) -> str:
    """反转义CQ码特殊字符"""
    for escaped, original in CQ_UNESCAPE_CHARS.items():
        s = s.replace(escaped, original)
    return s


def truncate_string(s: str, max_length: int = MESSAGE_DISPLAY_MAX_LENGTH, suffix: str = "...") -> str:
    """截断字符串"""
    if len(s) <= max_length:
        return s
    return s[:max_length] + suffix


def safe_json_dumps(obj: Any, ensure_ascii: bool = False, default: Callable = str) -> str:
    """安全的JSON序列化"""
    try:
        return json.dumps(obj, ensure_ascii=ensure_ascii, default=default)
    except Exception:
        return str(obj)


def safe_json_loads(s: str, default: Any = None) -> Any:
    """安全的JSON反序列化"""
    try:
        return json.loads(s)
    except Exception:
        return default


# ==================== 消息处理 ====================

def extract_plain_text(message: List[Dict[str, Any]]) -> str:
    """从消息段列表中提取纯文本"""
    text_parts = []
    for segment in message:
        if isinstance(segment, dict) and segment.get('type') == 'text':
            text_parts.append(segment.get('data', {}).get('text', ''))
    return ''.join(text_parts).strip()


def format_message_for_display(message: Union[str, List[Dict[str, Any]]]) -> str:
    """格式化消息用于显示"""
    if isinstance(message, str):
        return truncate_string(message)
    
    content_parts = []
    for segment in message:
        if not isinstance(segment, dict):
            continue
        
        seg_type = segment.get('type', '')
        seg_data = segment.get('data', {})
        
        if seg_type == 'text':
            content_parts.append(seg_data.get('text', '').strip())
        elif seg_type == 'at':
            qq = seg_data.get('qq', '')
            content_parts.append('@全体' if qq == 'all' else f'@{qq}')
        elif seg_type in SEGMENT_DISPLAY_MAP:
            display = SEGMENT_DISPLAY_MAP[seg_type]
            if '{qq}' in display:
                display = display.format(qq=seg_data.get('qq', ''))
            content_parts.append(display)
        else:
            content_parts.append(f'[{seg_type}]')
    
    content = ''.join(content_parts) or "[空消息]"
    return truncate_string(content)


def build_text_segment(text: str) -> Dict[str, Any]:
    """构建文本消息段"""
    return {"type": "text", "data": {"text": text}}


def build_at_segment(user_id: Union[int, str]) -> Dict[str, Any]:
    """构建@消息段"""
    return {"type": "at", "data": {"qq": str(user_id)}}


def build_image_segment(file: str, **kwargs) -> Dict[str, Any]:
    """构建图片消息段"""
    data = {"file": file}
    data.update(kwargs)
    return {"type": "image", "data": data}


def build_reply_segment(message_id: Union[int, str]) -> Dict[str, Any]:
    """构建回复消息段"""
    return {"type": "reply", "data": {"id": str(message_id)}}


def normalize_message(content: Any) -> List[Dict[str, Any]]:
    """标准化消息格式"""
    if isinstance(content, str):
        return [build_text_segment(content)]
    if isinstance(content, dict):
        return [content]
    if isinstance(content, list):
        return content
    return [build_text_segment(str(content))]


# ==================== 正则表达式 ====================

@lru_cache(maxsize=256)
def compile_regex(pattern: str, flags: int = re.DOTALL) -> Optional[re.Pattern]:
    """编译正则表达式（带缓存）"""
    try:
        return re.compile(pattern, flags)
    except re.error as e:
        logger.error(f"正则表达式编译失败: {pattern}, {e}")
        return None


def enhance_pattern(pattern: str) -> str:
    """增强正则表达式（添加行首匹配）"""
    return pattern if pattern.startswith('^') else f"^{pattern}"


# ==================== 异步工具 ====================

def run_async(coroutine):
    """在同步环境中运行异步函数"""
    try:
        # 检查是否已有运行中的事件循环
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        
        if loop is not None:
            # 在新线程中运行
            import queue
            result_queue = queue.Queue()
            
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    result = new_loop.run_until_complete(coroutine)
                    result_queue.put(('success', result))
                except Exception as e:
                    result_queue.put(('error', e))
                finally:
                    new_loop.close()
                    asyncio.set_event_loop(None)
            
            thread = threading.Thread(target=run_in_thread, daemon=True)
            thread.start()
            thread.join()
            
            result_type, result_data = result_queue.get()
            if result_type == 'error':
                raise result_data
            return result_data
        else:
            # 创建新的事件循环
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(coroutine)
    except Exception as e:
        logger.error(f"异步执行失败: {e}")
        raise


def create_task_safe(coroutine, name: str = None):
    """安全创建异步任务"""
    try:
        loop = asyncio.get_running_loop()
        return loop.create_task(coroutine, name=name)
    except RuntimeError:
        # 没有运行中的事件循环
        return asyncio.ensure_future(coroutine)


# ==================== 时间工具 ====================

def get_timestamp() -> int:
    """获取当前时间戳"""
    return int(time.time())


def get_timestamp_ms() -> int:
    """获取当前毫秒时间戳"""
    return int(time.time() * 1000)


def format_timestamp(timestamp: Union[int, float] = None, fmt: str = '%Y-%m-%d %H:%M:%S') -> str:
    """格式化时间戳"""
    if timestamp is None:
        timestamp = time.time()
    return time.strftime(fmt, time.localtime(timestamp))


def parse_timestamp(time_str: str, fmt: str = '%Y-%m-%d %H:%M:%S') -> int:
    """解析时间字符串为时间戳"""
    return int(time.mktime(time.strptime(time_str, fmt)))


# ==================== ID 生成 ====================

def generate_id(prefix: str = "") -> str:
    """生成唯一ID"""
    import uuid
    unique_id = str(uuid.uuid4()).replace('-', '')[:16]
    return f"{prefix}{unique_id}" if prefix else unique_id


def generate_hash(content: str, algorithm: str = 'md5') -> str:
    """生成哈希值"""
    if algorithm == 'md5':
        return hashlib.md5(content.encode()).hexdigest()
    elif algorithm == 'sha1':
        return hashlib.sha1(content.encode()).hexdigest()
    elif algorithm == 'sha256':
        return hashlib.sha256(content.encode()).hexdigest()
    else:
        raise ValueError(f"不支持的哈希算法: {algorithm}")


# ==================== 类型检查 ====================

def is_valid_qq(qq: Any) -> bool:
    """检查是否是有效的QQ号"""
    if qq is None:
        return False
    qq_str = str(qq)
    return qq_str.isdigit() and 5 <= len(qq_str) <= 11


def is_valid_group_id(group_id: Any) -> bool:
    """检查是否是有效的群号"""
    if group_id is None:
        return False
    group_str = str(group_id)
    return group_str.isdigit() and 5 <= len(group_str) <= 12


def ensure_str(value: Any, default: str = "") -> str:
    """确保值为字符串"""
    if value is None:
        return default
    return str(value)


def ensure_int(value: Any, default: int = 0) -> int:
    """确保值为整数"""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def ensure_list(value: Any) -> List:
    """确保值为列表"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


# ==================== 字典工具 ====================

def deep_get(d: Dict, path: str, default: Any = None, separator: str = '/') -> Any:
    """深度获取字典值"""
    try:
        keys = path.split(separator)
        result = d
        for key in keys:
            if not key:
                continue
            if isinstance(result, dict):
                result = result.get(key)
            else:
                return default
            if result is None:
                return default
        return result
    except Exception:
        return default


def deep_set(d: Dict, path: str, value: Any, separator: str = '/') -> Dict:
    """深度设置字典值"""
    keys = path.split(separator)
    current = d
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value
    return d


def merge_dicts(base: Dict, override: Dict) -> Dict:
    """深度合并字典"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


# ==================== 模块信息提取 ====================

def extract_module_info(file_path: str) -> tuple:
    """从文件路径提取模块信息"""
    import os
    if not file_path:
        return "未知目录", "未知模块", "unknown"
    
    dir_name = os.path.basename(os.path.dirname(file_path))
    module_name = os.path.splitext(os.path.basename(file_path))[0]
    full_name = f"plugins.{dir_name}.{module_name}"
    
    return dir_name, module_name, full_name


# ==================== 权限检查 ====================

def check_owner(user_id: str, owner_ids: List[str]) -> bool:
    """检查是否是主人"""
    return str(user_id) in owner_ids


def check_permission(
    handler_info: Dict[str, Any],
    is_owner: bool,
    is_group: bool
) -> tuple:
    """检查权限"""
    if handler_info.get('owner_only', False) and not is_owner:
        return False, 'owner_denied'
    if handler_info.get('group_only', False) and not is_group:
        return False, 'group_denied'
    return True, None

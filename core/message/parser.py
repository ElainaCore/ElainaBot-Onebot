#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
消息解析器模块
提供消息内容解析功能
"""

import re
import logging
from typing import Dict, Any, Optional, List, Union, Tuple

from ..constants import SegmentTypes

logger = logging.getLogger('ElainaBot.core.message.parser')


# CQ码正则表达式
CQ_CODE_PATTERN = re.compile(r'\[CQ:(\w+)(?:,([^\]]*))?\]')


def _unescape_cq(s: str) -> str:
    """反转义CQ码特殊字符"""
    return (
        s.replace("&#44;", ",")
        .replace("&#91;", "[")
        .replace("&#93;", "]")
        .replace("&amp;", "&")
    )


class MessageParser:
    """消息解析器"""
    
    @staticmethod
    def parse_cq_code(cq_string: str) -> List[Dict[str, Any]]:
        """
        解析CQ码字符串为消息段列表
        
        Args:
            cq_string: CQ码字符串
        
        Returns:
            消息段列表
        """
        segments = []
        last_end = 0
        
        for match in CQ_CODE_PATTERN.finditer(cq_string):
            # 添加前面的文本
            if match.start() > last_end:
                text = cq_string[last_end:match.start()]
                if text:
                    segments.append({
                        "type": SegmentTypes.TEXT,
                        "data": {"text": _unescape_cq(text)}
                    })
            
            # 解析CQ码
            cq_type = match.group(1)
            params_str = match.group(2) or ""
            
            data = {}
            if params_str:
                for param in params_str.split(","):
                    if "=" in param:
                        key, value = param.split("=", 1)
                        data[key] = _unescape_cq(value)
            
            segments.append({
                "type": cq_type,
                "data": data
            })
            
            last_end = match.end()
        
        # 添加剩余的文本
        if last_end < len(cq_string):
            text = cq_string[last_end:]
            if text:
                segments.append({
                    "type": SegmentTypes.TEXT,
                    "data": {"text": _unescape_cq(text)}
                })
        
        return segments
    
    @staticmethod
    def parse_message_array(message: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        解析消息数组，提取各种信息
        
        Args:
            message: 消息段列表
        
        Returns:
            解析结果字典，包含:
            - plain_text: 纯文本内容
            - at_users: 被@的用户列表
            - images: 图片列表
            - reply_id: 回复的消息ID
            - has_at_all: 是否@全体
        """
        result = {
            'plain_text': '',
            'at_users': [],
            'images': [],
            'reply_id': None,
            'has_at_all': False,
            'segments': message
        }
        
        text_parts = []
        
        for segment in message:
            if not isinstance(segment, dict):
                continue
            
            seg_type = segment.get('type', '')
            seg_data = segment.get('data', {})
            
            if seg_type == SegmentTypes.TEXT:
                text_parts.append(seg_data.get('text', ''))
            
            elif seg_type == SegmentTypes.AT:
                qq = seg_data.get('qq', '')
                if qq == 'all':
                    result['has_at_all'] = True
                elif qq:
                    result['at_users'].append(str(qq))
            
            elif seg_type == SegmentTypes.IMAGE:
                url = seg_data.get('url') or seg_data.get('file', '')
                if url:
                    result['images'].append({
                        'url': url,
                        'file': seg_data.get('file', ''),
                        'type': seg_data.get('type', '')
                    })
            
            elif seg_type == SegmentTypes.REPLY:
                result['reply_id'] = seg_data.get('id')
        
        result['plain_text'] = ''.join(text_parts).strip()
        return result
    
    @staticmethod
    def extract_command(text: str, prefixes: List[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        从文本中提取命令和参数
        
        Args:
            text: 文本内容
            prefixes: 命令前缀列表，默认为 ['/', '!', '！']
        
        Returns:
            (命令名, 参数字符串) 或 (None, None)
        """
        if prefixes is None:
            prefixes = ['/', '!', '！']
        
        text = text.strip()
        
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):]
                break
        else:
            # 没有匹配的前缀
            return None, None
        
        parts = text.split(None, 1)
        if not parts:
            return None, None
        
        command = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        
        return command, args


# ==================== 便捷函数 ====================

def parse_message(message: Union[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """
    解析消息
    
    Args:
        message: CQ码字符串或消息段列表
    
    Returns:
        解析结果
    """
    if isinstance(message, str):
        segments = MessageParser.parse_cq_code(message)
    else:
        segments = message
    
    return MessageParser.parse_message_array(segments)


def parse_cq_code(cq_string: str) -> List[Dict[str, Any]]:
    """解析CQ码字符串"""
    return MessageParser.parse_cq_code(cq_string)


def extract_plain_text(message: Union[str, List[Dict[str, Any]]]) -> str:
    """提取纯文本"""
    result = parse_message(message)
    return result['plain_text']


def extract_images(message: Union[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """提取图片"""
    result = parse_message(message)
    return result['images']


def extract_at_users(message: Union[str, List[Dict[str, Any]]]) -> List[str]:
    """提取被@的用户"""
    result = parse_message(message)
    return result['at_users']

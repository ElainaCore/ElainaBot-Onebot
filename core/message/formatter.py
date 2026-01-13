#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
消息格式化模块
提供消息显示格式化功能
"""

import logging
from typing import Dict, Any, Optional, List, Union

from ..constants import SEGMENT_DISPLAY_MAP, MESSAGE_DISPLAY_MAX_LENGTH, SegmentTypes

logger = logging.getLogger('ElainaBot.core.message.formatter')


class MessageFormatter:
    """消息格式化器"""
    
    @staticmethod
    def format_segment(segment: Dict[str, Any]) -> str:
        """
        格式化单个消息段用于显示
        
        Args:
            segment: 消息段字典
        
        Returns:
            格式化后的字符串
        """
        if not isinstance(segment, dict):
            return ""
        
        seg_type = segment.get('type', '')
        seg_data = segment.get('data', {})
        
        if seg_type == SegmentTypes.TEXT:
            return seg_data.get('text', '').strip()
        
        elif seg_type == SegmentTypes.AT:
            qq = seg_data.get('qq', '')
            return '@全体' if qq == 'all' else f'@{qq}'
        
        elif seg_type == SegmentTypes.FACE:
            face_id = seg_data.get('id', '')
            return f'[表情{face_id}]'
        
        elif seg_type == SegmentTypes.IMAGE:
            return '[图片]'
        
        elif seg_type == SegmentTypes.RECORD:
            return '[语音]'
        
        elif seg_type == SegmentTypes.VIDEO:
            return '[视频]'
        
        elif seg_type == SegmentTypes.REPLY:
            return '↩️'
        
        elif seg_type == SegmentTypes.FORWARD:
            return '[转发消息]'
        
        elif seg_type == SegmentTypes.SHARE:
            title = seg_data.get('title', '')
            return f'[分享: {title}]' if title else '[分享]'
        
        elif seg_type == SegmentTypes.JSON:
            return '[JSON消息]'
        
        elif seg_type == SegmentTypes.XML:
            return '[XML消息]'
        
        elif seg_type in SEGMENT_DISPLAY_MAP:
            return SEGMENT_DISPLAY_MAP[seg_type]
        
        else:
            return f'[{seg_type}]'
    
    @classmethod
    def format_message(
        cls,
        message: Union[str, List[Dict[str, Any]]],
        max_length: int = MESSAGE_DISPLAY_MAX_LENGTH,
        show_ellipsis: bool = True
    ) -> str:
        """
        格式化消息用于显示
        
        Args:
            message: 消息内容（字符串或消息段列表）
            max_length: 最大长度
            show_ellipsis: 超长时是否显示省略号
        
        Returns:
            格式化后的字符串
        """
        if isinstance(message, str):
            content = message
        else:
            parts = []
            for segment in message:
                formatted = cls.format_segment(segment)
                if formatted:
                    parts.append(formatted)
            content = ''.join(parts)
        
        content = content or "[空消息]"
        
        if len(content) > max_length:
            if show_ellipsis:
                content = content[:max_length] + "..."
            else:
                content = content[:max_length]
        
        return content
    
    @classmethod
    def format_for_log(
        cls,
        message: Union[str, List[Dict[str, Any]]],
        is_group: bool,
        chat_id: str,
        sender_name: str = "",
        is_sent: bool = False
    ) -> str:
        """
        格式化消息用于日志
        
        Args:
            message: 消息内容
            is_group: 是否群聊
            chat_id: 聊天ID（群号或用户ID）
            sender_name: 发送者名称
            is_sent: 是否是发送的消息
        
        Returns:
            格式化后的日志字符串
        """
        content = cls.format_message(message)
        
        if is_sent:
            icon = "📤"
            sender = "Bot"
        else:
            icon = "📨"
            sender = sender_name or chat_id
        
        if is_group:
            msg_type = "群聊"
            location = f"群({chat_id})"
        else:
            msg_type = "私聊"
            location = f"私聊({chat_id})"
        
        return f"{icon} {msg_type} | {location} | {sender}: {content}"
    
    @classmethod
    def format_notice(cls, notice_type: str, **kwargs) -> str:
        """
        格式化通知事件
        
        Args:
            notice_type: 通知类型
            **kwargs: 通知相关参数
        
        Returns:
            格式化后的字符串
        """
        group_id = kwargs.get('group_id', '')
        user_id = kwargs.get('user_id', '')
        operator_id = kwargs.get('operator_id', '')
        
        if notice_type == 'group_recall':
            message_id = kwargs.get('message_id', '')
            if operator_id == user_id:
                return f"📬 群({group_id}) | {user_id} 撤回了自己的消息 msg_id:{message_id}"
            else:
                return f"📬 群({group_id}) | {operator_id} 撤回了 {user_id} 的消息 msg_id:{message_id}"
        
        elif notice_type == 'group_increase':
            return f"📬 群({group_id}) | {user_id} 加入了群聊"
        
        elif notice_type == 'group_decrease':
            if operator_id and operator_id != user_id:
                return f"📬 群({group_id}) | {user_id} 被 {operator_id} 踢出群聊"
            else:
                return f"📬 群({group_id}) | {user_id} 退出了群聊"
        
        elif notice_type == 'group_admin':
            sub_type = kwargs.get('sub_type', '')
            action = "被设为管理员" if sub_type == 'set' else "被取消管理员"
            return f"📬 群({group_id}) | {user_id} {action}"
        
        elif notice_type == 'group_ban':
            sub_type = kwargs.get('sub_type', '')
            duration = kwargs.get('duration', 0)
            if sub_type == 'lift_ban' or duration == 0:
                return f"📬 群({group_id}) | {operator_id} 解除了 {user_id} 的禁言"
            else:
                return f"📬 群({group_id}) | {operator_id} 禁言了 {user_id} {duration}秒"
        
        elif notice_type == 'friend_recall':
            message_id = kwargs.get('message_id', '')
            return f"📬 好友 {user_id} 撤回了消息 msg_id:{message_id}"
        
        elif notice_type == 'friend_add':
            return f"📬 新好友 {user_id} 已添加"
        
        elif notice_type == 'notify':
            sub_type = kwargs.get('sub_type', '')
            if sub_type == 'poke':
                target_id = kwargs.get('target_id', '')
                return f"📬 群({group_id}) | {user_id} 戳了戳 {target_id}"
            else:
                return f"📬 群({group_id}) | 通知: {sub_type}"
        
        else:
            return f"📬 通知事件: {notice_type} | 群 {group_id} | 用户 {user_id}"


# ==================== 便捷函数 ====================

def format_message_for_display(
    message: Union[str, List[Dict[str, Any]]],
    max_length: int = MESSAGE_DISPLAY_MAX_LENGTH
) -> str:
    """格式化消息用于显示"""
    return MessageFormatter.format_message(message, max_length)


def format_message_for_log(
    message: Union[str, List[Dict[str, Any]]],
    is_group: bool,
    chat_id: str,
    sender_name: str = "",
    is_sent: bool = False
) -> str:
    """格式化消息用于日志"""
    return MessageFormatter.format_for_log(message, is_group, chat_id, sender_name, is_sent)

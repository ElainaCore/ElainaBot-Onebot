#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
日志格式化模块
提供统一的日志格式化和消息显示功能
"""

import logging
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass

from .constants import (
    LogFormats, NoticeTypes, RequestTypes,
    SEGMENT_DISPLAY_MAP, MESSAGE_DISPLAY_MAX_LENGTH
)
from .utils import truncate_string, ensure_str

logger = logging.getLogger('ElainaBot.core.log_formatter')


@dataclass
class FormattedLog:
    """格式化后的日志"""
    message: str
    level: int = logging.INFO
    extra: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.extra is None:
            self.extra = {}


class LogFormatter:
    """日志格式化器"""
    
    @staticmethod
    def format_message_content(message: Union[str, List[Dict[str, Any]]]) -> str:
        """格式化消息内容用于显示"""
        if isinstance(message, str):
            return truncate_string(message, MESSAGE_DISPLAY_MAX_LENGTH)
        
        content_parts = []
        for segment in message:
            if not isinstance(segment, dict):
                continue
            
            seg_type = segment.get('type', '')
            seg_data = segment.get('data', {})
            
            if seg_type == 'text':
                text = seg_data.get('text', '').strip()
                if text:
                    content_parts.append(text)
            elif seg_type == 'at':
                qq = seg_data.get('qq', '')
                content_parts.append('@全体' if qq == 'all' else f'@{qq}')
            elif seg_type in SEGMENT_DISPLAY_MAP:
                display = SEGMENT_DISPLAY_MAP[seg_type]
                content_parts.append(display)
            else:
                content_parts.append(f'[{seg_type}]')
        
        content = ''.join(content_parts) or "[空消息]"
        return truncate_string(content, MESSAGE_DISPLAY_MAX_LENGTH)
    
    @classmethod
    def format_received_message(
        cls,
        is_group: bool,
        group_id: Optional[str],
        user_id: str,
        sender_name: str,
        message: Union[str, List[Dict[str, Any]]]
    ) -> FormattedLog:
        """格式化接收到的消息"""
        content = cls.format_message_content(message)
        
        if is_group:
            msg = LogFormats.RECEIVED_GROUP.format(
                group_id=group_id,
                sender=sender_name,
                content=content
            )
        else:
            msg = LogFormats.RECEIVED_PRIVATE.format(
                user_id=user_id,
                sender=sender_name,
                content=content
            )
        
        return FormattedLog(
            message=msg,
            extra={
                'is_group': is_group,
                'group_id': group_id,
                'user_id': user_id,
                'content': content
            }
        )
    
    @classmethod
    def format_sent_message(
        cls,
        is_group: bool,
        chat_id: str,
        message: Union[str, List[Dict[str, Any]]]
    ) -> FormattedLog:
        """格式化发送的消息"""
        content = cls.format_message_content(message)
        
        if is_group:
            msg = LogFormats.SENT_GROUP.format(
                group_id=chat_id,
                content=content
            )
        else:
            msg = LogFormats.SENT_PRIVATE.format(
                user_id=chat_id,
                content=content
            )
        
        return FormattedLog(
            message=msg,
            extra={
                'is_group': is_group,
                'chat_id': chat_id,
                'content': content
            }
        )
    
    @classmethod
    def format_notice_event(cls, event) -> FormattedLog:
        """格式化通知事件"""
        notice_type = getattr(event, 'notice_type', 'unknown')
        group_id = ensure_str(getattr(event, 'group_id', ''))
        user_id = ensure_str(getattr(event, 'user_id', ''))
        operator_id = ensure_str(getattr(event, 'operator_id', ''))
        
        # 获取原始数据
        data = getattr(event, 'data', {}) if hasattr(event, 'data') else {}
        message_id = ensure_str(data.get('message_id', ''))
        sub_type = data.get('sub_type', '')
        duration = data.get('duration', 0)
        target_id = ensure_str(data.get('target_id', ''))
        
        # 根据通知类型生成日志
        if notice_type == NoticeTypes.GROUP_RECALL:
            if operator_id == user_id:
                msg = LogFormats.NOTICE_RECALL_SELF.format(
                    group_id=group_id,
                    user_id=user_id,
                    message_id=message_id
                )
            else:
                msg = LogFormats.NOTICE_RECALL_OTHER.format(
                    group_id=group_id,
                    operator_id=operator_id,
                    user_id=user_id,
                    message_id=message_id
                )
        
        elif notice_type == NoticeTypes.GROUP_INCREASE:
            msg = LogFormats.NOTICE_GROUP_INCREASE.format(
                group_id=group_id,
                user_id=user_id
            )
        
        elif notice_type == NoticeTypes.GROUP_DECREASE:
            if operator_id and operator_id != user_id:
                msg = LogFormats.NOTICE_GROUP_DECREASE_KICK.format(
                    group_id=group_id,
                    user_id=user_id,
                    operator_id=operator_id
                )
            else:
                msg = LogFormats.NOTICE_GROUP_DECREASE_LEAVE.format(
                    group_id=group_id,
                    user_id=user_id
                )
        
        elif notice_type == NoticeTypes.GROUP_ADMIN:
            if sub_type == 'set':
                msg = LogFormats.NOTICE_ADMIN_SET.format(
                    group_id=group_id,
                    user_id=user_id
                )
            else:
                msg = LogFormats.NOTICE_ADMIN_UNSET.format(
                    group_id=group_id,
                    user_id=user_id
                )
        
        elif notice_type == NoticeTypes.GROUP_BAN:
            if sub_type == 'lift_ban' or duration == 0:
                msg = LogFormats.NOTICE_UNBAN.format(
                    group_id=group_id,
                    operator_id=operator_id,
                    user_id=user_id
                )
            else:
                msg = LogFormats.NOTICE_BAN.format(
                    group_id=group_id,
                    operator_id=operator_id,
                    user_id=user_id,
                    duration=duration
                )
        
        elif notice_type == NoticeTypes.FRIEND_RECALL:
            msg = f"📬 好友 {user_id} 撤回了消息 msg_id:{message_id}"
        
        elif notice_type == NoticeTypes.FRIEND_ADD:
            msg = f"📬 新好友 {user_id} 已添加"
        
        elif notice_type == NoticeTypes.NOTIFY:
            if sub_type == 'poke':
                msg = LogFormats.NOTICE_POKE.format(
                    group_id=group_id,
                    user_id=user_id,
                    target_id=target_id
                )
            else:
                msg = f"📬 群({group_id}) | 通知: {sub_type}"
        
        else:
            msg = f"📬 通知事件: {notice_type} | 群 {group_id} | 用户 {user_id}"
        
        return FormattedLog(
            message=msg,
            extra={
                'notice_type': notice_type,
                'group_id': group_id,
                'user_id': user_id,
                'operator_id': operator_id
            }
        )
    
    @classmethod
    def format_request_event(cls, event) -> FormattedLog:
        """格式化请求事件"""
        request_type = getattr(event, 'request_type', 'unknown')
        group_id = ensure_str(getattr(event, 'group_id', ''))
        user_id = ensure_str(getattr(event, 'user_id', ''))
        comment = ensure_str(getattr(event, 'comment', ''))
        
        if request_type == RequestTypes.FRIEND:
            msg = LogFormats.REQUEST_FRIEND.format(
                user_id=user_id,
                comment=comment
            )
        elif request_type == RequestTypes.GROUP:
            msg = LogFormats.REQUEST_GROUP.format(
                group_id=group_id,
                user_id=user_id,
                comment=comment
            )
        else:
            msg = f"📮 请求事件: {request_type} | 用户 {user_id} | 验证消息: {comment}"
        
        return FormattedLog(
            message=msg,
            extra={
                'request_type': request_type,
                'group_id': group_id,
                'user_id': user_id,
                'comment': comment
            }
        )
    
    @classmethod
    def format_plugin_load(
        cls,
        dir_name: str,
        plugin_name: str,
        results: List[str],
        is_hot_reload: bool = False
    ) -> FormattedLog:
        """格式化插件加载日志"""
        status = "热更新" if is_hot_reload else "加载"
        results_str = ', '.join(results) if results else ""
        
        if results_str:
            msg = f"{status}: {dir_name}/{plugin_name} - {results_str}"
        else:
            msg = f"{status}: {dir_name}/{plugin_name}"
        
        return FormattedLog(
            message=msg,
            extra={
                'dir_name': dir_name,
                'plugin_name': plugin_name,
                'is_hot_reload': is_hot_reload,
                'results': results
            }
        )
    
    @classmethod
    def format_plugin_delete(
        cls,
        dir_name: str,
        plugin_name: str,
        count: int
    ) -> FormattedLog:
        """格式化插件删除日志"""
        msg = LogFormats.FRAMEWORK_PLUGIN_DELETE.format(
            dir_name=dir_name,
            plugin_name=plugin_name,
            count=count
        )
        
        return FormattedLog(
            message=msg,
            extra={
                'dir_name': dir_name,
                'plugin_name': plugin_name,
                'count': count
            }
        )
    
    @classmethod
    def format_error(
        cls,
        error_msg: str,
        traceback_str: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> FormattedLog:
        """格式化错误日志"""
        full_msg = error_msg
        if traceback_str:
            full_msg = f"{error_msg}\n{traceback_str}"
        
        return FormattedLog(
            message=full_msg,
            level=logging.ERROR,
            extra={
                'error_msg': error_msg,
                'traceback': traceback_str,
                'context': context or {}
            }
        )


# 便捷函数
def format_message(message: Union[str, List[Dict[str, Any]]]) -> str:
    """格式化消息内容"""
    return LogFormatter.format_message_content(message)


def format_received(
    is_group: bool,
    group_id: Optional[str],
    user_id: str,
    sender_name: str,
    message: Union[str, List[Dict[str, Any]]]
) -> str:
    """格式化接收消息"""
    return LogFormatter.format_received_message(
        is_group, group_id, user_id, sender_name, message
    ).message


def format_sent(
    is_group: bool,
    chat_id: str,
    message: Union[str, List[Dict[str, Any]]]
) -> str:
    """格式化发送消息"""
    return LogFormatter.format_sent_message(is_group, chat_id, message).message


def format_notice(event) -> str:
    """格式化通知事件"""
    return LogFormatter.format_notice_event(event).message


def format_request(event) -> str:
    """格式化请求事件"""
    return LogFormatter.format_request_event(event).message

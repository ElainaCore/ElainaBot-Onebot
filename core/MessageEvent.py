#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
OneBot v11 协议的 MessageEvent 实现
包含消息段（MessageSegment）和消息事件（MessageEvent）
"""

import json
import time
import logging
from typing import Dict, Any, Optional, List, Union, Iterable

from core.onebot.api import get_onebot_api, run_async_api
from core.utils import escape_cq as escape, unescape_cq as unescape
from core.constants import PostTypes, MessageTypes, SegmentTypes
from core.log_formatter import LogFormatter

logger = logging.getLogger('ElainaBot.core.event.MessageEvent_OneBot')
# 从新的消息构建器模块导入
from core.message.builder import MessageSegment, MessageBuilder as Message


# ==================== MessageEvent ====================

# 消息类型常量
GROUP_MESSAGE = MessageTypes.GROUP
PRIVATE_MESSAGE = MessageTypes.PRIVATE
UNKNOWN_MESSAGE = MessageTypes.UNKNOWN

# OneBot 事件类型到内部类型的映射
_ONEBOT_MESSAGE_TYPES = {
    'group': GROUP_MESSAGE,
    'private': PRIVATE_MESSAGE,
}


class OneBotMessageEvent:
    """OneBot v11 事件类（支持 message/notice/request）"""
    
    # 消息类型常量（保持向后兼容）
    GROUP_MESSAGE = GROUP_MESSAGE
    PRIVATE_MESSAGE = PRIVATE_MESSAGE
    UNKNOWN_MESSAGE = UNKNOWN_MESSAGE
    
    def __init__(self, data, skip_recording=False, http_context=None):
        self.raw_data = data
        self.skip_recording = skip_recording
        
        # 解析数据
        if isinstance(data, str):
            try:
                self.data = json.loads(data)
            except:
                self.data = {}
        else:
            self.data = data
        
        # 基本信息
        self.post_type = self.data.get('post_type', '')
        self.time = self.data.get('time', int(time.time()))
        self.self_id = str(self.data.get('self_id', ''))
        
        # 用户和群组信息（所有事件都可能有）
        self.user_id = str(self.data.get('user_id', '')) if self.data.get('user_id') else None
        self.group_id = str(self.data.get('group_id', '')) if self.data.get('group_id') else None
        
        # 根据事件类型初始化
        self._init_by_post_type()
        
        # 其他通用属性
        self.ignore = False
        self.matches = None
        self._api = None
        self.is_master = self._check_is_master()
        self.timestamp = str(self.time)
    
    def _init_by_post_type(self):
        """根据事件类型初始化属性"""
        if self.post_type == PostTypes.MESSAGE:
            self._init_message_event()
        elif self.post_type == PostTypes.NOTICE:
            self._init_notice_event()
        elif self.post_type == PostTypes.REQUEST:
            self._init_request_event()
        else:
            self._init_default_event()
    
    def _init_message_event(self):
        """初始化消息事件"""
        self.message_type = self._parse_message_type()
        self.message_id = self.data.get('message_id', '')
        
        # 发送者信息
        self.sender = self.data.get('sender', {})
        self.sender_nickname = self.sender.get('nickname', '')
        self.sender_card = self.sender.get('card', '')
        
        # 消息内容
        self.message = self.data.get('message', [])
        self.raw_message = self.data.get('raw_message', '')
        self.content = self._parse_content()
        
        # 消息类型判断
        self.is_group = self.message_type == GROUP_MESSAGE
        self.is_private = self.message_type == PRIVATE_MESSAGE
        
        # event_type 属性
        if self.is_group:
            self.event_type = "GROUP_MESSAGE"
        elif self.is_private:
            self.event_type = "PRIVATE_MESSAGE"
        else:
            self.event_type = "MESSAGE"
    
    def _init_notice_event(self):
        """初始化通知事件"""
        self.notice_type = self.data.get('notice_type', '')
        self.sub_type = self.data.get('sub_type', '')
        self.operator_id = str(self.data.get('operator_id', '')) if self.data.get('operator_id') else None
        
        logger.debug(f"解析通知事件: notice_type={self.notice_type}, group_id={self.group_id}, user_id={self.user_id}")
        
        # 设置默认值
        self._set_default_message_fields()
        self.is_group = bool(self.group_id)
        self.is_private = False
        self.event_type = f"NOTICE_{self.notice_type.upper()}"
    
    def _init_request_event(self):
        """初始化请求事件"""
        self.request_type = self.data.get('request_type', '')
        self.sub_type = self.data.get('sub_type', '')
        self.comment = self.data.get('comment', '')
        self.flag = self.data.get('flag', '')
        
        logger.debug(f"解析请求事件: request_type={self.request_type}, group_id={self.group_id}, user_id={self.user_id}")
        
        # 设置默认值
        self._set_default_message_fields()
        self.content = self.comment
        self.is_group = self.request_type == 'group'
        self.is_private = False
        self.event_type = f"REQUEST_{self.request_type.upper()}"
    
    def _init_default_event(self):
        """初始化默认事件（元事件或未知类型）"""
        self._set_default_message_fields()
        self.is_group = False
        self.is_private = False
        self.event_type = self.post_type.upper()
    
    def _set_default_message_fields(self):
        """设置消息相关字段的默认值"""
        self.message_type = UNKNOWN_MESSAGE
        self.message_id = ''
        self.sender = {}
        self.sender_nickname = ''
        self.sender_card = ''
        self.message = []
        self.raw_message = ''
        self.content = ''
    
    def _parse_message_type(self) -> str:
        """解析消息类型"""
        if self.data.get('post_type') != PostTypes.MESSAGE:
            return UNKNOWN_MESSAGE
        
        message_type = self.data.get('message_type', '')
        return _ONEBOT_MESSAGE_TYPES.get(message_type, UNKNOWN_MESSAGE)
    
    def _parse_content(self) -> str:
        """解析消息内容"""
        content_parts = []
        for segment in self.message:
            if isinstance(segment, dict):
                seg_type = segment.get('type', '')
                seg_data = segment.get('data', {})
                if seg_type == SegmentTypes.TEXT:
                    content_parts.append(seg_data.get('text', ''))
                elif seg_type == SegmentTypes.IMAGE:
                    url = seg_data.get('url', seg_data.get('file', ''))
                    if url:
                        content_parts.append(f"<{url}>")
        
        content = ''.join(content_parts).strip()
        if not content and self.raw_message:
            content = self.raw_message
        if content and content[0] == '/':
            content = content[1:]
        return content
    
    @property
    def api(self):
        """获取 API 实例"""
        if self._api is None:
            self._api = get_onebot_api()
        return self._api
    
    def get(self, path):
        """从数据中获取值"""
        try:
            data = self.data
            for key in path.split('/'):
                if not key:
                    continue
                data = data.get(key) if isinstance(data, dict) else None
                if data is None:
                    return None
            return data
        except:
            return None
    
    def reply(self, content='', auto_delete_time=None, **kwargs):
        """回复消息"""
        if not content:
            return None
        
        message = self._build_message(content)
        
        if self.is_group:
            result = run_async_api(self.api.send_group_msg(self.group_id, message, **kwargs))
            chat_id = self.group_id
        elif self.is_private:
            result = run_async_api(self.api.send_private_msg(self.user_id, message, **kwargs))
            chat_id = self.user_id
        else:
            return None
        
        if result and result.get('retcode') == 0:
            message_id = result.get('data', {}).get('message_id')
            
            # 输出控制台日志
            try:
                from main import log_sent_message
                log_sent_message(message, self.is_group, chat_id)
            except:
                pass
            
            if auto_delete_time and message_id:
                import threading
                threading.Timer(auto_delete_time, self._auto_recall, args=[message_id]).start()
            return message_id
        return None
    
    def _build_message(self, content):
        """构建消息格式"""
        if isinstance(content, str):
            return [{"type": "text", "data": {"text": content}}]
        if isinstance(content, Message):
            return content.to_onebot_array()
        if isinstance(content, list):
            return content
        if isinstance(content, dict):
            return [content]
        return [{"type": "text", "data": {"text": str(content)}}]
    
    def _auto_recall(self, message_id):
        """自动撤回消息"""
        try:
            run_async_api(self.api.delete_msg(message_id))
        except:
            pass
    
    def recall_message(self, message_id):
        """撤回消息"""
        try:
            result = run_async_api(self.api.delete_msg(message_id))
            return result and result.get('retcode') == 0
        except:
            return False
    
    def _record_message_to_db_only(self):
        """记录消息到数据库"""
        try:
            from function.log_db import add_log_to_db
            import datetime
            
            reply_id = None
            for segment in self.message:
                if isinstance(segment, dict) and segment.get('type') == 'reply':
                    reply_id = segment.get('data', {}).get('id')
                    break
            
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            add_log_to_db('received', {
                'timestamp': timestamp,
                'content': self.content or "",
                'user_id': self.user_id or "unknown",
                'group_id': self.group_id or "private",
                'message_id': str(self.message_id),
                'real_seq': str(self.data.get('real_seq', '')),
                'reply_id': str(reply_id) if reply_id else None,
                'raw_message': json.dumps(self.data, ensure_ascii=False),
                'message_segments': json.dumps(self.message, ensure_ascii=False),
                'message_type': 'group' if self.is_group else 'private'
            })
        except:
            pass
    
    def _record_user_and_group(self):
        pass
    
    def record_last_message_id(self):
        pass
    
    def _check_is_master(self):
        """检查是否是主人"""
        try:
            from config import OWNER_IDS
            return str(self.user_id) in OWNER_IDS
        except:
            return False
    
    async def call_api(self, api_name, params=None):
        """调用 OneBot API"""
        try:
            from core.onebot.api import call_onebot_api
            return await call_onebot_api(api_name, params or {})
        except Exception as e:
            logger.error(f"API 调用失败: {api_name}, {str(e)}")
            return None
    
    def get_at_users(self):
        """获取所有被 @ 的用户 ID"""
        at_users = []
        for segment in self.message:
            if isinstance(segment, dict) and segment.get('type') == 'at':
                qq = segment.get('data', {}).get('qq', '')
                if qq and qq != 'all':
                    at_users.append(str(qq))
        return at_users
    
    def get_first_at_user(self):
        """获取第一个被 @ 的用户 ID"""
        at_users = self.get_at_users()
        return at_users[0] if at_users else None
    
    def has_at_all(self):
        """检查是否包含 @全体成员"""
        for segment in self.message:
            if isinstance(segment, dict) and segment.get('type') == 'at':
                if segment.get('data', {}).get('qq') == 'all':
                    return True
        return False
    
    def has_at_bot(self):
        """检查是否 @ 了机器人"""
        for segment in self.message:
            if isinstance(segment, dict) and segment.get('type') == 'at':
                if segment.get('data', {}).get('qq') == str(self.self_id):
                    return True
        return False
    
    def _notify_web_display(self, timestamp):
        """通知Web界面显示消息"""
        try:
            from web.tools.log_handler import add_display_message
            
            msg_type = "群聊" if self.is_group else "私聊"
            sender = self.sender_card or self.sender_nickname or str(self.user_id)
            location = f"群({self.group_id})" if self.is_group else f"私聊({self.user_id})"
            
            # 简单解析消息内容
            content_parts = []
            for segment in self.message:
                if isinstance(segment, dict):
                    seg_type = segment.get('type', '')
                    seg_data = segment.get('data', {})
                    if seg_type == 'text':
                        content_parts.append(seg_data.get('text', '').strip())
                    elif seg_type == 'at':
                        qq = seg_data.get('qq', '')
                        content_parts.append('@全体' if qq == 'all' else f'@{qq}')
                    elif seg_type == 'image':
                        content_parts.append('[图片]')
                    elif seg_type == 'reply':
                        content_parts.append('↩️')
                    else:
                        content_parts.append(f'[{seg_type}]')
            
            content = ''.join(content_parts) or self.content or "[空消息]"
            display_content = content[:100] + "..." if len(content) > 100 else content
            formatted_message = f"{msg_type} | {location} | {sender}: {display_content}"
            
            add_display_message(
                formatted_message=formatted_message,
                timestamp=timestamp,
                user_id=str(self.user_id),
                group_id=str(self.group_id) if self.is_group else None,
                message_content=content
            )
        except:
            pass
    


# 为了兼容性，导出为 MessageEvent
MessageEvent = OneBotMessageEvent


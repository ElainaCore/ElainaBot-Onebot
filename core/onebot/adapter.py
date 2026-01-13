#!/usr/bin/env python
# -*- coding: utf-8 -*-

import hmac
import json
import asyncio
import logging
from typing import Any, Optional, Dict

logger = logging.getLogger('ElainaBot.core.onebot')


class OneBotV11Event:
    def __init__(self, **data):
        self.time = data.get('time', 0)
        self.self_id = data.get('self_id', '')
        self.post_type = data.get('post_type', '')
        self._data = data
    
    def get_type(self) -> str:
        return self.post_type
    
    def to_dict(self) -> dict:
        return self._data


class MessageEvent(OneBotV11Event):
    def __init__(self, **data):
        super().__init__(**data)
        self.message_type = data.get('message_type', '')
        self.user_id = data.get('user_id', 0)
        self.message_id = data.get('message_id', 0)
        self.message = data.get('message', [])
        self.raw_message = data.get('raw_message', '')
        self.sender = data.get('sender', {})
        self.group_id = data.get('group_id')
        self.to_me = False
        self.reply = None


class PrivateMessageEvent(MessageEvent):
    pass


class GroupMessageEvent(MessageEvent):
    pass


class MetaEvent(OneBotV11Event):
    def __init__(self, **data):
        super().__init__(**data)
        self.meta_event_type = data.get('meta_event_type', '')


class LifecycleMetaEvent(MetaEvent):
    pass


class HeartbeatMetaEvent(MetaEvent):
    pass


class NoticeEvent(OneBotV11Event):
    """通知事件"""
    def __init__(self, **data):
        super().__init__(**data)
        self.notice_type = data.get('notice_type', '')
        self.user_id = data.get('user_id', 0)
        self.group_id = data.get('group_id')


class GroupIncreaseNoticeEvent(NoticeEvent):
    """群成员增加事件"""
    def __init__(self, **data):
        super().__init__(**data)
        self.sub_type = data.get('sub_type', '')  # approve/invite
        self.operator_id = data.get('operator_id', 0)


class GroupDecreaseNoticeEvent(NoticeEvent):
    """群成员减少事件"""
    def __init__(self, **data):
        super().__init__(**data)
        self.sub_type = data.get('sub_type', '')  # leave/kick/kick_me
        self.operator_id = data.get('operator_id', 0)


class RequestEvent(OneBotV11Event):
    """请求事件"""
    def __init__(self, **data):
        super().__init__(**data)
        self.request_type = data.get('request_type', '')
        self.user_id = data.get('user_id', 0)
        self.comment = data.get('comment', '')
        self.flag = data.get('flag', '')


class FriendRequestEvent(RequestEvent):
    """好友请求事件"""
    pass


class GroupRequestEvent(RequestEvent):
    """加群请求事件"""
    def __init__(self, **data):
        super().__init__(**data)
        self.sub_type = data.get('sub_type', '')  # add/invite
        self.group_id = data.get('group_id', 0)


class OneBotV11Adapter:
    def __init__(self, access_token: Optional[str] = None, secret: Optional[str] = None):
        self.access_token = access_token
        self.secret = secret
        self.bots: Dict[str, Any] = {}
        self.websockets: Dict[str, Any] = {}
        self.api_responses: Dict[str, asyncio.Future] = {}
        logger.info("✅ OneBot 适配器初始化")
    
    def _check_signature(self, body: bytes, signature: Optional[str]) -> bool:
        if not self.secret or not signature:
            return not self.secret
        sig = hmac.new(self.secret.encode('utf-8'), body, 'sha1').hexdigest()
        return signature == "sha1=" + sig
    
    def _check_access_token(self, auth_header: Optional[str]) -> bool:
        if not self.access_token or not auth_header:
            return not self.access_token
        parts = auth_header.split(' ', 1)
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return False
        return parts[1] == self.access_token
    
    @classmethod
    def json_to_event(cls, json_data: Any) -> Optional[OneBotV11Event]:
        if not isinstance(json_data, dict) or "post_type" not in json_data:
            return None
        
        try:
            post_type = json_data.get("post_type")
            if post_type == "message":
                message_type = json_data.get("message_type")
                if message_type == "private":
                    return PrivateMessageEvent(**json_data)
                elif message_type == "group":
                    return GroupMessageEvent(**json_data)
                return MessageEvent(**json_data)
            elif post_type == "meta_event":
                meta_event_type = json_data.get("meta_event_type")
                if meta_event_type == "lifecycle":
                    return LifecycleMetaEvent(**json_data)
                elif meta_event_type == "heartbeat":
                    return HeartbeatMetaEvent(**json_data)
                return MetaEvent(**json_data)
            elif post_type == "notice":
                notice_type = json_data.get("notice_type")
                # 已适配的通知类型
                adapted_notice_types = {"group_increase", "group_decrease", "group_recall", "group_admin", "group_ban", "group_upload", "notify", "friend_add", "friend_recall"}
                if notice_type not in adapted_notice_types:
                    logger.info(f"🔔 收到通知事件: {notice_type} | 原始数据: {json_data}")
                if notice_type == "group_increase":
                    return GroupIncreaseNoticeEvent(**json_data)
                elif notice_type == "group_decrease":
                    return GroupDecreaseNoticeEvent(**json_data)
                return NoticeEvent(**json_data)
            elif post_type == "request":
                request_type = json_data.get("request_type")
                logger.info(f"📮 收到请求事件: {request_type} | 原始数据: {json_data}")
                if request_type == "friend":
                    return FriendRequestEvent(**json_data)
                elif request_type == "group":
                    return GroupRequestEvent(**json_data)
                return RequestEvent(**json_data)
            return OneBotV11Event(**json_data)
        except:
            return None
    
    def handle_http_callback(self, body: bytes, headers: dict) -> tuple[bool, Optional[OneBotV11Event]]:
        self_id = headers.get("x-self-id") or headers.get("X-Self-ID")
        if not self_id:
            logger.warning("⚠️ 缺少 X-Self-ID")
            return False, None
        
        signature = headers.get("x-signature") or headers.get("X-Signature")
        if not self._check_signature(body, signature):
            logger.warning("⚠️ 签名验证失败")
            return False, None
        
        try:
            json_data = json.loads(body)
        except:
            logger.error("❌ JSON 解析失败")
            return False, None
        
        event = self.json_to_event(json_data)
        if not event:
            return False, None
        
        if self_id not in self.bots:
            self.bots[self_id] = {"self_id": self_id, "type": "http"}
            logger.info(f"✅ Bot {self_id} HTTP 连接")
        
        return True, event
    
    def validate_websocket_headers(self, headers: dict) -> tuple[bool, Optional[str], Optional[str]]:
        self_id = headers.get("x-self-id") or headers.get("X-Self-ID")
        if not self_id:
            return False, None, "Missing X-Self-ID"
        
        if self_id in self.bots:
            return False, self_id, "Duplicate Connection"
        
        auth_header = headers.get("authorization") or headers.get("Authorization")
        if not self._check_access_token(auth_header):
            return False, self_id, "Unauthorized"
        
        return True, self_id, None
    
    def register_bot(self, self_id: str, ws=None):
        self.bots[self_id] = {"self_id": self_id, "type": "websocket" if ws else "http", "ws": ws}
        if ws:
            self.websockets[self_id] = ws
        logger.info(f"✅ Bot {self_id}")
    
    def unregister_bot(self, self_id: str):
        if self_id in self.bots:
            del self.bots[self_id]
        if self_id in self.websockets:
            del self.websockets[self_id]


_adapter: Optional[OneBotV11Adapter] = None


def get_adapter() -> OneBotV11Adapter:
    global _adapter
    if _adapter is None:
        _adapter = OneBotV11Adapter()
    return _adapter


def init_adapter(access_token: Optional[str] = None, secret: Optional[str] = None):
    global _adapter
    _adapter = OneBotV11Adapter(access_token=access_token, secret=secret)
    return _adapter


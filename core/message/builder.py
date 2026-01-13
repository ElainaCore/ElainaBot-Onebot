#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
消息构建器模块
提供链式调用的消息构建API
"""

from typing import Dict, Any, Optional, List, Union
from ..constants import SegmentTypes


def _escape_cq(s: str, escape_comma: bool = True) -> str:
    """转义CQ码特殊字符"""
    result = s.replace("&", "&amp;").replace("[", "&#91;").replace("]", "&#93;")
    if escape_comma:
        result = result.replace(",", "&#44;")
    return result


class MessageSegment:
    """
    消息段类
    支持链式调用和运算符重载
    """
    
    __slots__ = ('type', 'data')
    
    def __init__(self, type: str, data: Dict[str, Any] = None):
        self.type = type
        self.data = data or {}
    
    def __str__(self) -> str:
        """转换为CQ码字符串"""
        if self.type == SegmentTypes.TEXT:
            return _escape_cq(self.data.get("text", ""), escape_comma=False)
        
        params = ",".join(
            f"{k}={_escape_cq(str(v))}" 
            for k, v in self.data.items() 
            if v is not None
        )
        return f"[CQ:{self.type}{',' if params else ''}{params}]"
    
    def __repr__(self) -> str:
        return f"MessageSegment(type={self.type!r}, data={self.data!r})"
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, MessageSegment):
            return False
        return self.type == other.type and self.data == other.data
    
    def __add__(self, other: Union[str, "MessageSegment", "MessageBuilder"]) -> "MessageBuilder":
        return MessageBuilder(self) + other
    
    def __radd__(self, other: Union[str, "MessageSegment", "MessageBuilder"]) -> "MessageBuilder":
        return MessageBuilder(other) + self
    
    def is_text(self) -> bool:
        """是否是文本消息段"""
        return self.type == SegmentTypes.TEXT
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {"type": self.type, "data": self.data.copy()}
    
    # ==================== 工厂方法 ====================
    
    @classmethod
    def text(cls, text: str) -> "MessageSegment":
        """文本消息段"""
        return cls(SegmentTypes.TEXT, {"text": text})
    
    @classmethod
    def at(cls, user_id: Union[int, str]) -> "MessageSegment":
        """@消息段"""
        return cls(SegmentTypes.AT, {"qq": str(user_id)})
    
    @classmethod
    def at_all(cls) -> "MessageSegment":
        """@全体成员"""
        return cls(SegmentTypes.AT, {"qq": "all"})
    
    @classmethod
    def face(cls, face_id: int) -> "MessageSegment":
        """表情消息段"""
        return cls(SegmentTypes.FACE, {"id": str(face_id)})
    
    @classmethod
    def image(
        cls,
        file: str,
        type: Optional[str] = None,
        cache: bool = True,
        proxy: bool = True,
        timeout: Optional[int] = None
    ) -> "MessageSegment":
        """图片消息段"""
        data = {"file": file}
        if type:
            data["type"] = type
        if not cache:
            data["cache"] = "0"
        if not proxy:
            data["proxy"] = "0"
        if timeout:
            data["timeout"] = str(timeout)
        return cls(SegmentTypes.IMAGE, data)
    
    @classmethod
    def record(
        cls,
        file: str,
        magic: bool = False,
        cache: bool = True,
        proxy: bool = True,
        timeout: Optional[int] = None
    ) -> "MessageSegment":
        """语音消息段"""
        data = {"file": file}
        if magic:
            data["magic"] = "1"
        if not cache:
            data["cache"] = "0"
        if not proxy:
            data["proxy"] = "0"
        if timeout:
            data["timeout"] = str(timeout)
        return cls(SegmentTypes.RECORD, data)
    
    @classmethod
    def video(
        cls,
        file: str,
        cache: bool = True,
        proxy: bool = True,
        timeout: Optional[int] = None
    ) -> "MessageSegment":
        """视频消息段"""
        data = {"file": file}
        if not cache:
            data["cache"] = "0"
        if not proxy:
            data["proxy"] = "0"
        if timeout:
            data["timeout"] = str(timeout)
        return cls(SegmentTypes.VIDEO, data)
    
    @classmethod
    def reply(cls, message_id: Union[int, str]) -> "MessageSegment":
        """回复消息段"""
        return cls(SegmentTypes.REPLY, {"id": str(message_id)})
    
    @classmethod
    def forward(cls, forward_id: str) -> "MessageSegment":
        """转发消息段"""
        return cls(SegmentTypes.FORWARD, {"id": forward_id})
    
    @classmethod
    def share(
        cls,
        url: str,
        title: str,
        content: Optional[str] = None,
        image: Optional[str] = None
    ) -> "MessageSegment":
        """分享消息段"""
        data = {"url": url, "title": title}
        if content:
            data["content"] = content
        if image:
            data["image"] = image
        return cls(SegmentTypes.SHARE, data)
    
    @classmethod
    def json(cls, data: str) -> "MessageSegment":
        """JSON消息段"""
        return cls(SegmentTypes.JSON, {"data": data})
    
    @classmethod
    def xml(cls, data: str) -> "MessageSegment":
        """XML消息段"""
        return cls(SegmentTypes.XML, {"data": data})
    
    @classmethod
    def poke(cls, type: str, id: str) -> "MessageSegment":
        """戳一戳消息段"""
        return cls(SegmentTypes.POKE, {"type": type, "id": id})
    
    @classmethod
    def music(
        cls,
        type: str,
        id: Optional[str] = None,
        url: Optional[str] = None,
        audio: Optional[str] = None,
        title: Optional[str] = None,
        content: Optional[str] = None,
        image: Optional[str] = None
    ) -> "MessageSegment":
        """音乐消息段"""
        data = {"type": type}
        if id:
            data["id"] = id
        if url:
            data["url"] = url
        if audio:
            data["audio"] = audio
        if title:
            data["title"] = title
        if content:
            data["content"] = content
        if image:
            data["image"] = image
        return cls(SegmentTypes.MUSIC, data)


class MessageBuilder:
    """
    消息构建器
    支持链式调用构建复杂消息
    
    Example:
        msg = (MessageBuilder()
            .text("Hello ")
            .at(123456)
            .text(" 你好！")
            .image("https://example.com/image.png")
            .build())
    """
    
    __slots__ = ('_segments',)
    
    def __init__(self, message: Union[str, MessageSegment, List[MessageSegment], "MessageBuilder", None] = None):
        self._segments: List[MessageSegment] = []
        
        if message is None:
            pass
        elif isinstance(message, str):
            self._segments.append(MessageSegment.text(message))
        elif isinstance(message, MessageSegment):
            self._segments.append(message)
        elif isinstance(message, MessageBuilder):
            self._segments = message._segments.copy()
        elif isinstance(message, list):
            for item in message:
                if isinstance(item, MessageSegment):
                    self._segments.append(item)
                elif isinstance(item, dict):
                    self._segments.append(MessageSegment(item.get("type", "text"), item.get("data", {})))
    
    def __str__(self) -> str:
        return "".join(str(seg) for seg in self._segments)
    
    def __repr__(self) -> str:
        return f"MessageBuilder({self._segments!r})"
    
    def __len__(self) -> int:
        return len(self._segments)
    
    def __bool__(self) -> bool:
        return len(self._segments) > 0
    
    def __add__(self, other: Union[str, MessageSegment, "MessageBuilder"]) -> "MessageBuilder":
        result = MessageBuilder(self)
        if isinstance(other, str):
            result._segments.append(MessageSegment.text(other))
        elif isinstance(other, MessageSegment):
            result._segments.append(other)
        elif isinstance(other, MessageBuilder):
            result._segments.extend(other._segments)
        return result
    
    def __radd__(self, other: Union[str, MessageSegment]) -> "MessageBuilder":
        result = MessageBuilder()
        if isinstance(other, str):
            result._segments.append(MessageSegment.text(other))
        elif isinstance(other, MessageSegment):
            result._segments.append(other)
        result._segments.extend(self._segments)
        return result
    
    def __iter__(self):
        return iter(self._segments)
    
    def __getitem__(self, index: int) -> MessageSegment:
        return self._segments[index]
    
    # ==================== 链式方法 ====================
    
    def append(self, segment: Union[str, MessageSegment]) -> "MessageBuilder":
        """追加消息段"""
        if isinstance(segment, str):
            self._segments.append(MessageSegment.text(segment))
        elif isinstance(segment, MessageSegment):
            self._segments.append(segment)
        return self
    
    def text(self, text: str) -> "MessageBuilder":
        """追加文本"""
        return self.append(MessageSegment.text(text))
    
    def at(self, user_id: Union[int, str]) -> "MessageBuilder":
        """追加@"""
        return self.append(MessageSegment.at(user_id))
    
    def at_all(self) -> "MessageBuilder":
        """追加@全体"""
        return self.append(MessageSegment.at_all())
    
    def face(self, face_id: int) -> "MessageBuilder":
        """追加表情"""
        return self.append(MessageSegment.face(face_id))
    
    def image(self, file: str, **kwargs) -> "MessageBuilder":
        """追加图片"""
        return self.append(MessageSegment.image(file, **kwargs))
    
    def record(self, file: str, **kwargs) -> "MessageBuilder":
        """追加语音"""
        return self.append(MessageSegment.record(file, **kwargs))
    
    def video(self, file: str, **kwargs) -> "MessageBuilder":
        """追加视频"""
        return self.append(MessageSegment.video(file, **kwargs))
    
    def reply(self, message_id: Union[int, str]) -> "MessageBuilder":
        """追加回复"""
        return self.append(MessageSegment.reply(message_id))
    
    def forward(self, forward_id: str) -> "MessageBuilder":
        """追加转发"""
        return self.append(MessageSegment.forward(forward_id))
    
    def share(self, url: str, title: str, **kwargs) -> "MessageBuilder":
        """追加分享"""
        return self.append(MessageSegment.share(url, title, **kwargs))
    
    def json(self, data: str) -> "MessageBuilder":
        """追加JSON"""
        return self.append(MessageSegment.json(data))
    
    def xml(self, data: str) -> "MessageBuilder":
        """追加XML"""
        return self.append(MessageSegment.xml(data))
    
    def newline(self) -> "MessageBuilder":
        """追加换行"""
        return self.text("\n")
    
    def space(self, count: int = 1) -> "MessageBuilder":
        """追加空格"""
        return self.text(" " * count)
    
    # ==================== 输出方法 ====================
    
    def build(self) -> List[Dict[str, Any]]:
        """构建消息数组"""
        return [seg.to_dict() for seg in self._segments]
    
    def to_cq_string(self) -> str:
        """转换为CQ码字符串"""
        return str(self)
    
    def extract_plain_text(self) -> str:
        """提取纯文本"""
        return "".join(
            seg.data.get("text", "") 
            for seg in self._segments 
            if seg.is_text()
        )
    
    def copy(self) -> "MessageBuilder":
        """复制消息构建器"""
        return MessageBuilder(self)
    
    def clear(self) -> "MessageBuilder":
        """清空消息段"""
        self._segments.clear()
        return self
    
    # ==================== 查询方法 ====================
    
    def has_type(self, segment_type: str) -> bool:
        """是否包含指定类型的消息段"""
        return any(seg.type == segment_type for seg in self._segments)
    
    def get_segments_by_type(self, segment_type: str) -> List[MessageSegment]:
        """获取指定类型的所有消息段"""
        return [seg for seg in self._segments if seg.type == segment_type]
    
    def get_at_users(self) -> List[str]:
        """获取所有被@的用户ID"""
        at_users = []
        for seg in self._segments:
            if seg.type == SegmentTypes.AT:
                qq = seg.data.get('qq', '')
                if qq and qq != 'all':
                    at_users.append(str(qq))
        return at_users
    
    def has_at_all(self) -> bool:
        """是否包含@全体"""
        for seg in self._segments:
            if seg.type == SegmentTypes.AT and seg.data.get('qq') == 'all':
                return True
        return False
    
    def get_images(self) -> List[str]:
        """获取所有图片URL"""
        images = []
        for seg in self._segments:
            if seg.type == SegmentTypes.IMAGE:
                url = seg.data.get('url') or seg.data.get('file', '')
                if url:
                    images.append(url)
        return images
    
    def get_reply_id(self) -> Optional[str]:
        """获取回复的消息ID"""
        for seg in self._segments:
            if seg.type == SegmentTypes.REPLY:
                return seg.data.get('id')
        return None


# 便捷别名
Message = MessageBuilder
Segment = MessageSegment

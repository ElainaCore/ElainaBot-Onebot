#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
统一类型定义模块
提供框架中使用的所有类型定义、枚举和数据类
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Union, Callable, TypeVar, Generic
from abc import ABC, abstractmethod


# ==================== 枚举类型 ====================

class PostType(str, Enum):
    """OneBot 事件类型"""
    MESSAGE = "message"
    NOTICE = "notice"
    REQUEST = "request"
    META_EVENT = "meta_event"


class MessageType(str, Enum):
    """消息类型"""
    GROUP = "group"
    PRIVATE = "private"
    UNKNOWN = "unknown"


class NoticeType(str, Enum):
    """通知类型"""
    GROUP_INCREASE = "group_increase"
    GROUP_DECREASE = "group_decrease"
    GROUP_RECALL = "group_recall"
    GROUP_ADMIN = "group_admin"
    GROUP_BAN = "group_ban"
    GROUP_UPLOAD = "group_upload"
    FRIEND_ADD = "friend_add"
    FRIEND_RECALL = "friend_recall"
    NOTIFY = "notify"
    POKE = "poke"


class RequestType(str, Enum):
    """请求类型"""
    FRIEND = "friend"
    GROUP = "group"


class SegmentType(str, Enum):
    """消息段类型"""
    TEXT = "text"
    AT = "at"
    FACE = "face"
    IMAGE = "image"
    RECORD = "record"
    VIDEO = "video"
    REPLY = "reply"
    FORWARD = "forward"
    SHARE = "share"
    JSON = "json"
    XML = "xml"


class LogLevel(str, Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogType(str, Enum):
    """日志类型"""
    RECEIVED = "received"
    PLUGIN = "plugin"
    FRAMEWORK = "framework"
    ERROR = "error"


# ==================== 数据类 ====================

@dataclass
class HandlerConfig:
    """处理器配置"""
    handler: str
    owner_only: bool = False
    group_only: bool = False
    priority: int = 10
    description: str = ""
    
    @classmethod
    def from_dict(cls, data: Union[str, Dict[str, Any]]) -> "HandlerConfig":
        """从字典或字符串创建配置"""
        if isinstance(data, str):
            return cls(handler=data)
        return cls(
            handler=data.get('handler', ''),
            owner_only=data.get('owner_only', False),
            group_only=data.get('group_only', False),
            priority=data.get('priority', 10),
            description=data.get('description', '')
        )


@dataclass
class WebRouteConfig:
    """Web路由配置"""
    path: str
    menu_name: str = ""
    menu_icon: str = "bi-puzzle"
    description: str = ""
    handler: str = "render_page"
    priority: int = 100
    api_routes: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ApiRouteConfig:
    """API路由配置"""
    path: str
    handler: str
    methods: List[str] = field(default_factory=lambda: ["GET"])
    require_auth: bool = True
    require_token: bool = True


@dataclass
class PluginInfo:
    """插件信息"""
    name: str
    source_file: str
    priority: int = 10
    handlers_count: int = 0
    is_hot_reload: bool = False
    web_routes: List[WebRouteConfig] = field(default_factory=list)
    api_routes: List[ApiRouteConfig] = field(default_factory=list)


@dataclass
class EventContext:
    """事件上下文"""
    post_type: PostType
    time: int
    self_id: str
    user_id: Optional[str] = None
    group_id: Optional[str] = None
    message_id: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PermissionResult:
    """权限检查结果"""
    allowed: bool
    deny_reason: Optional[str] = None
    
    @classmethod
    def allow(cls) -> "PermissionResult":
        return cls(allowed=True)
    
    @classmethod
    def deny(cls, reason: str) -> "PermissionResult":
        return cls(allowed=False, deny_reason=reason)


# ==================== 抽象基类 ====================

class IPlugin(ABC):
    """插件接口"""
    priority: int = 10
    
    @staticmethod
    @abstractmethod
    def get_regex_handlers() -> Dict[str, Union[str, Dict[str, Any]]]:
        """返回正则处理器字典"""
        raise NotImplementedError
    
    @classmethod
    def on_event(cls, event: Any) -> Optional[bool]:
        """事件钩子（可选实现）"""
        pass
    
    @classmethod
    def on_plugin_load(cls) -> None:
        """插件加载时调用（可选实现）"""
        pass
    
    @classmethod
    def on_plugin_unload(cls) -> None:
        """插件卸载时调用（可选实现）"""
        pass


class IEventHandler(ABC):
    """事件处理器接口"""
    
    @abstractmethod
    def handle(self, event: Any) -> bool:
        """处理事件"""
        raise NotImplementedError
    
    @abstractmethod
    def can_handle(self, event: Any) -> bool:
        """判断是否能处理该事件"""
        raise NotImplementedError


class IMessageBuilder(ABC):
    """消息构建器接口"""
    
    @abstractmethod
    def build(self) -> List[Dict[str, Any]]:
        """构建消息"""
        raise NotImplementedError
    
    @abstractmethod
    def to_string(self) -> str:
        """转换为字符串"""
        raise NotImplementedError


# ==================== 泛型类型 ====================

T = TypeVar('T')
R = TypeVar('R')


class Result(Generic[T]):
    """操作结果封装"""
    
    def __init__(self, success: bool, data: Optional[T] = None, error: Optional[str] = None):
        self.success = success
        self.data = data
        self.error = error
    
    @classmethod
    def ok(cls, data: T) -> "Result[T]":
        return cls(success=True, data=data)
    
    @classmethod
    def fail(cls, error: str) -> "Result[T]":
        return cls(success=False, error=error)
    
    def __bool__(self) -> bool:
        return self.success
    
    def unwrap(self) -> T:
        if not self.success:
            raise ValueError(f"Result is not successful: {self.error}")
        return self.data
    
    def unwrap_or(self, default: T) -> T:
        return self.data if self.success else default


# ==================== 类型别名 ====================

MessageSegmentDict = Dict[str, Any]
MessageArray = List[MessageSegmentDict]
HandlerDict = Dict[str, Union[str, Dict[str, Any]]]
EventData = Dict[str, Any]
ApiResponse = Dict[str, Any]

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
常量定义模块
集中管理框架中使用的所有常量
"""

from typing import Dict, Set, FrozenSet


# ==================== 版本信息 ====================

VERSION = "2.0.0"
VERSION_NAME = "ElainaBot OneBot"
PROTOCOL_VERSION = "v11"


# ==================== 系统常量 ====================

# 默认优先级
DEFAULT_PLUGIN_PRIORITY = 10

# 线程池配置
PLUGIN_EXECUTOR_MAX_WORKERS = 300
PLUGIN_EXECUTOR_THREAD_PREFIX = "PluginWorker"

# 垃圾回收配置
GC_INTERVAL = 30  # 秒
GC_THRESHOLD = (700, 10, 5)

# 缓存配置
REGEX_CACHE_MAX_SIZE = 200
HANDLER_CACHE_MAX_SIZE = 200
CACHE_CLEANUP_INTERVAL = 300  # 秒

# 插件执行超时
PLUGIN_EXECUTION_TIMEOUT = 3.0  # 秒


# ==================== OneBot 协议常量 ====================

# 事件类型
class PostTypes:
    MESSAGE = "message"
    NOTICE = "notice"
    REQUEST = "request"
    META_EVENT = "meta_event"


# 消息类型
class MessageTypes:
    GROUP = "group"
    PRIVATE = "private"
    UNKNOWN = "unknown"


# 通知类型
class NoticeTypes:
    GROUP_INCREASE = "group_increase"
    GROUP_DECREASE = "group_decrease"
    GROUP_RECALL = "group_recall"
    GROUP_ADMIN = "group_admin"
    GROUP_BAN = "group_ban"
    GROUP_UPLOAD = "group_upload"
    FRIEND_ADD = "friend_add"
    FRIEND_RECALL = "friend_recall"
    NOTIFY = "notify"


# 请求类型
class RequestTypes:
    FRIEND = "friend"
    GROUP = "group"


# 消息段类型
class SegmentTypes:
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
    POKE = "poke"
    DICE = "dice"
    RPS = "rps"
    MUSIC = "music"
    LOCATION = "location"
    CONTACT = "contact"


# 已适配的通知类型集合
ADAPTED_NOTICE_TYPES: FrozenSet[str] = frozenset({
    "group_increase",
    "group_decrease",
    "group_recall",
    "group_admin",
    "group_ban",
    "group_upload",
    "notify",
    "friend_add",
    "friend_recall"
})


# ==================== 日志常量 ====================

# 日志类型
class LogTypes:
    RECEIVED = "received"
    PLUGIN = "plugin"
    FRAMEWORK = "framework"
    ERROR = "error"


LOG_TYPES_LIST = ["received", "plugin", "framework", "error"]

# 日志数据库配置
LOG_SAVE_INTERVAL = 3  # 秒
LOG_BATCH_SIZE = 1000


# ==================== HTTP 连接池常量 ====================

class HttpPoolConfig:
    MAX_CONNECTIONS = 200
    MAX_KEEPALIVE = 75
    KEEPALIVE_EXPIRY = 30.0
    TIMEOUT = 30.0
    VERIFY_SSL = False
    REBUILD_INTERVAL = 43200  # 12小时


# ==================== 权限常量 ====================

class PermissionDenyReasons:
    OWNER_DENIED = "owner_denied"
    GROUP_DENIED = "group_denied"
    ADMIN_DENIED = "admin_denied"
    COOLDOWN = "cooldown"
    BLACKLIST = "blacklist"


# ==================== 消息格式化常量 ====================

# CQ码特殊字符
CQ_ESCAPE_CHARS: Dict[str, str] = {
    "&": "&amp;",
    "[": "&#91;",
    "]": "&#93;",
    ",": "&#44;"
}

CQ_UNESCAPE_CHARS: Dict[str, str] = {
    "&#44;": ",",
    "&#91;": "[",
    "&#93;": "]",
    "&amp;": "&"
}


# ==================== 消息显示常量 ====================

# 消息段显示映射
SEGMENT_DISPLAY_MAP: Dict[str, str] = {
    "text": "",
    "at": "@{qq}",
    "face": "[表情]",
    "image": "[图片]",
    "record": "[语音]",
    "video": "[视频]",
    "reply": "↩️",
    "forward": "[转发消息]",
    "share": "[分享]",
    "json": "[JSON消息]",
    "xml": "[XML消息]",
    "poke": "[戳一戳]",
    "dice": "[骰子]",
    "rps": "[猜拳]",
    "music": "[音乐]",
    "location": "[位置]",
    "contact": "[名片]"
}

# 消息内容最大显示长度
MESSAGE_DISPLAY_MAX_LENGTH = 100


# ==================== Web 面板常量 ====================

# 默认图标
DEFAULT_MENU_ICON = "bi-puzzle"

# 默认处理器
DEFAULT_WEB_HANDLER = "render_page"

# 默认优先级
DEFAULT_WEB_PRIORITY = 100


# ==================== 错误消息模板 ====================

class ErrorMessages:
    PLUGIN_LOAD_FAILED = "插件 {name} 加载失败: {error}"
    PLUGIN_EXECUTE_FAILED = "插件 {name} 执行失败: {error}"
    PLUGIN_REGISTER_FAILED = "插件 {name} 注册失败: {error}"
    REGEX_COMPILE_FAILED = "正则表达式 '{pattern}' 编译失败: {error}"
    API_CALL_FAILED = "API 调用失败: {api_name}, {error}"
    EVENT_DISPATCH_FAILED = "事件分发失败: {error}"
    MESSAGE_SEND_FAILED = "消息发送失败: {error}"
    DB_WRITE_FAILED = "数据库写入失败: {error}"
    CONFIG_LOAD_FAILED = "配置加载失败: {error}"


# ==================== 成功消息模板 ====================

class SuccessMessages:
    PLUGIN_LOADED = "✅ 插件 {name} 加载成功"
    PLUGIN_RELOADED = "✅ 插件 {name} 热更新成功"
    BOT_CONNECTED = "✅ Bot {bot_id} 已连接"
    BOT_DISCONNECTED = "⚠️ Bot {bot_id} 已断开"
    SYSTEM_STARTED = "🚀 系统启动成功"


# ==================== 日志格式模板 ====================

class LogFormats:
    # 接收消息
    RECEIVED_GROUP = "📨 群聊 | 群({group_id}) | {sender}: {content}"
    RECEIVED_PRIVATE = "📨 私聊 | 私聊({user_id}) | {sender}: {content}"
    
    # 发送消息
    SENT_GROUP = "📤 群聊 | 群({group_id}) | Bot: {content}"
    SENT_PRIVATE = "📤 私聊 | 私聊({user_id}) | Bot: {content}"
    
    # 通知事件
    NOTICE_RECALL_SELF = "📬 群({group_id}) | {user_id} 撤回了自己的消息 msg_id:{message_id}"
    NOTICE_RECALL_OTHER = "📬 群({group_id}) | {operator_id} 撤回了 {user_id} 的消息 msg_id:{message_id}"
    NOTICE_GROUP_INCREASE = "📬 群({group_id}) | {user_id} 加入了群聊"
    NOTICE_GROUP_DECREASE_KICK = "📬 群({group_id}) | {user_id} 被 {operator_id} 踢出群聊"
    NOTICE_GROUP_DECREASE_LEAVE = "📬 群({group_id}) | {user_id} 退出了群聊"
    NOTICE_ADMIN_SET = "📬 群({group_id}) | {user_id} 被设为管理员"
    NOTICE_ADMIN_UNSET = "📬 群({group_id}) | {user_id} 被取消管理员"
    NOTICE_BAN = "📬 群({group_id}) | {operator_id} 禁言了 {user_id} {duration}秒"
    NOTICE_UNBAN = "📬 群({group_id}) | {operator_id} 解除了 {user_id} 的禁言"
    NOTICE_POKE = "📬 群({group_id}) | {user_id} 戳了戳 {target_id}"
    
    # 请求事件
    REQUEST_FRIEND = "📮 好友请求 | 用户 {user_id} | 验证消息: {comment}"
    REQUEST_GROUP = "📮 加群请求 | 群 {group_id} | 用户 {user_id} | 验证消息: {comment}"
    
    # 框架日志
    FRAMEWORK_PLUGIN_LOAD = "加载: {dir_name}/{plugin_name} - {results}"
    FRAMEWORK_PLUGIN_RELOAD = "热更新: {dir_name}/{plugin_name} - {results}"
    FRAMEWORK_PLUGIN_DELETE = "删除 {dir_name}/{plugin_name}，注销 {count}"

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
示例插件
展示新架构的插件开发方式
"""

from core.plugin.base import BasePlugin
from core.plugin.decorators import handler
from core.message.builder import MessageBuilder, MessageSegment
from core.decorators import safe_execute, timing
from core.utils import truncate_string, format_timestamp
from core.constants import PostTypes


class ExamplePlugin(BasePlugin):
    """
    示例插件类
    展示标准的插件结构和API使用
    """
    
    # 插件元信息
    name = "示例插件"
    description = "展示新架构的插件开发方式"
    author = "ElainaBot"
    version = "2.0.0"
    
    # 插件配置
    priority = 10  # 优先级，数字越小越先执行
    enabled = True
    
    @staticmethod
    def get_regex_handlers():
        """
        返回正则处理器字典
        
        支持两种格式:
        1. 简单格式: 'pattern': 'handler_name'
        2. 完整格式: 'pattern': {'handler': 'name', 'owner_only': True, ...}
        """
        return {
            # 简单格式
            r'^示例帮助$': 'handle_help',
            
            # 完整格式
            r'^示例测试\s*(.*)$': {
                'handler': 'handle_test',
                'owner_only': False,
                'group_only': False,
                'description': '测试命令，可带参数'
            },
            
            # 仅主人可用
            r'^示例管理$': {
                'handler': 'handle_admin',
                'owner_only': True,
                'description': '管理员命令'
            },
            
            # 仅群聊可用
            r'^示例群聊$': {
                'handler': 'handle_group_only',
                'group_only': True,
                'description': '仅群聊可用的命令'
            },
            
            # 消息构建器示例
            r'^示例消息$': {
                'handler': 'handle_message_builder',
                'description': '展示消息构建器用法'
            }
        }
    
    @classmethod
    def on_plugin_load(cls):
        """插件加载时调用"""
        cls.log_info("插件已加载")
    
    @classmethod
    def on_plugin_unload(cls):
        """插件卸载时调用"""
        cls.log_info("插件已卸载")
    
    @classmethod
    def on_event(cls, event):
        """
        事件钩子，所有事件都会调用
        可用于处理通知、请求等非消息事件
        """
        # 处理通知事件
        if event.post_type == PostTypes.NOTICE:
            notice_type = getattr(event, 'notice_type', '')
            if notice_type == 'group_increase':
                # 新成员入群
                cls.log_info(f"新成员 {event.user_id} 加入群 {event.group_id}")
        
        # 返回 None 继续传递事件
        return None
    
    # ==================== 处理器方法 ====================
    
    @staticmethod
    def handle_help(event):
        """帮助命令处理器"""
        help_text = """📚 示例插件帮助

命令列表:
• 示例帮助 - 显示此帮助
• 示例测试 [参数] - 测试命令
• 示例管理 - 管理员命令（仅主人）
• 示例群聊 - 群聊命令（仅群聊）
• 示例消息 - 消息构建器示例

插件版本: 2.0.0"""
        
        event.reply(help_text)
        return True
    
    @staticmethod
    @timing(threshold_ms=100)  # 记录执行时间超过100ms的调用
    def handle_test(event):
        """测试命令处理器"""
        # 获取正则匹配的参数
        param = event.matches[0] if event.matches else ""
        
        if param:
            reply = f"✅ 测试成功！\n参数: {truncate_string(param, 50)}"
        else:
            reply = "✅ 测试成功！（无参数）"
        
        # 添加时间戳
        reply += f"\n时间: {format_timestamp()}"
        
        event.reply(reply)
        return True
    
    @staticmethod
    def handle_admin(event):
        """管理员命令处理器（仅主人可用）"""
        event.reply("🔐 这是管理员命令，只有主人可以使用")
        return True
    
    @staticmethod
    def handle_group_only(event):
        """群聊命令处理器（仅群聊可用）"""
        event.reply(f"👥 这是群聊命令\n当前群: {event.group_id}")
        return True
    
    @staticmethod
    @safe_execute("消息构建失败: {error}", default_return=False)
    def handle_message_builder(event):
        """消息构建器示例"""
        # 使用链式调用构建消息
        msg = (MessageBuilder()
            .text("📝 消息构建器示例\n\n")
            .text("1. 文本消息\n")
            .text("2. ")
            .at(event.user_id)
            .text(" @用户\n")
            .text("3. 表情: ")
            .face(1)
            .newline()
            .text("\n✨ 构建完成！"))
        
        # 发送构建的消息
        event.reply(msg.build())
        return True


class AdvancedExamplePlugin(BasePlugin):
    """
    高级示例插件
    展示更多高级功能
    """
    
    name = "高级示例"
    description = "展示高级插件功能"
    priority = 20
    
    # 插件状态
    _counter = 0
    
    @staticmethod
    def get_regex_handlers():
        return {
            r'^计数器$': {
                'handler': 'handle_counter',
                'description': '显示并增加计数器'
            },
            r'^重置计数器$': {
                'handler': 'handle_reset',
                'owner_only': True,
                'description': '重置计数器'
            }
        }
    
    @classmethod
    def handle_counter(cls, event):
        """计数器处理器"""
        cls._counter += 1
        event.reply(f"🔢 当前计数: {cls._counter}")
        return True
    
    @classmethod
    def handle_reset(cls, event):
        """重置计数器"""
        old_value = cls._counter
        cls._counter = 0
        event.reply(f"🔄 计数器已重置\n原值: {old_value} → 0")
        return True

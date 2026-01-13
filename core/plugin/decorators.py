#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
插件装饰器模块
提供插件开发相关的装饰器
"""

from typing import Callable, Optional


def handler(
    pattern: str,
    owner_only: bool = False,
    group_only: bool = False,
    priority: int = None,
    description: str = ""
) -> Callable:
    """
    处理器装饰器
    用于标记方法为消息处理器
    
    Args:
        pattern: 正则表达式模式
        owner_only: 仅主人可用
        group_only: 仅群聊可用
        priority: 处理器优先级
        description: 处理器描述
    
    Example:
        class MyPlugin(BasePlugin):
            @handler(r'^测试$', description='测试命令')
            def handle_test(self, event):
                event.reply("测试成功！")
    """
    def decorator(func: Callable) -> Callable:
        func._handler_config = {
            'pattern': pattern,
            'handler': func.__name__,
            'owner_only': owner_only,
            'group_only': group_only,
            'priority': priority,
            'description': description
        }
        return func
    return decorator


def event_hook(event_type: str = None) -> Callable:
    """
    事件钩子装饰器
    用于标记方法为事件钩子
    
    Args:
        event_type: 事件类型过滤（message/notice/request）
    
    Example:
        class MyPlugin(BasePlugin):
            @event_hook('notice')
            def on_notice(self, event):
                if event.notice_type == 'group_increase':
                    event.reply("欢迎新成员！")
    """
    def decorator(func: Callable) -> Callable:
        func._event_hook = {
            'event_type': event_type
        }
        return func
    return decorator


def scheduled(interval: int = 60, enabled: bool = True) -> Callable:
    """
    定时任务装饰器
    
    Args:
        interval: 执行间隔（秒）
        enabled: 是否启用
    
    Example:
        class MyPlugin(BasePlugin):
            @scheduled(interval=3600)
            def hourly_task(self):
                print("每小时执行一次")
    """
    def decorator(func: Callable) -> Callable:
        func._schedule_config = {
            'interval': interval,
            'enabled': enabled
        }
        return func
    return decorator


def command(
    cmd: str,
    aliases: list = None,
    owner_only: bool = False,
    group_only: bool = False,
    description: str = ""
) -> Callable:
    """
    命令装饰器
    简化的命令注册方式
    
    Args:
        cmd: 命令名称
        aliases: 命令别名列表
        owner_only: 仅主人可用
        group_only: 仅群聊可用
        description: 命令描述
    
    Example:
        class MyPlugin(BasePlugin):
            @command('help', aliases=['帮助', '?'])
            def handle_help(self, event):
                event.reply("帮助信息")
    """
    def decorator(func: Callable) -> Callable:
        # 构建正则表达式
        all_cmds = [cmd] + (aliases or [])
        pattern = r'^(' + '|'.join(all_cmds) + r')(?:\s+(.*))?$'
        
        func._handler_config = {
            'pattern': pattern,
            'handler': func.__name__,
            'owner_only': owner_only,
            'group_only': group_only,
            'priority': None,
            'description': description,
            'command': cmd,
            'aliases': aliases or []
        }
        return func
    return decorator


def admin_only(func: Callable) -> Callable:
    """
    管理员限制装饰器
    
    Example:
        class MyPlugin(BasePlugin):
            @admin_only
            def handle_admin(self, event):
                ...
    """
    func._admin_only = True
    return func


def cooldown(seconds: int) -> Callable:
    """
    冷却时间装饰器
    
    Args:
        seconds: 冷却时间（秒）
    
    Example:
        class MyPlugin(BasePlugin):
            @cooldown(60)
            def handle_limited(self, event):
                ...
    """
    def decorator(func: Callable) -> Callable:
        func._cooldown = seconds
        return func
    return decorator


def rate_limit(calls: int, period: int) -> Callable:
    """
    频率限制装饰器
    
    Args:
        calls: 允许的调用次数
        period: 时间周期（秒）
    
    Example:
        class MyPlugin(BasePlugin):
            @rate_limit(calls=5, period=60)  # 每分钟最多5次
            def handle_api(self, event):
                ...
    """
    def decorator(func: Callable) -> Callable:
        func._rate_limit = {
            'calls': calls,
            'period': period
        }
        return func
    return decorator

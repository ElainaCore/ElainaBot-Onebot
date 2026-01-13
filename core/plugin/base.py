#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
插件基类模块
提供标准化的插件开发接口
"""

import logging
from typing import Dict, Any, Optional, List, Union
from abc import ABC, abstractmethod

from ..types import HandlerConfig, PermissionResult
from ..constants import DEFAULT_PLUGIN_PRIORITY

logger = logging.getLogger('ElainaBot.core.plugin.base')


class PluginMeta(type):
    """插件元类，用于自动注册和验证插件"""
    
    _plugins: Dict[str, type] = {}
    
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        
        # 跳过基类
        if name in ('BasePlugin', 'Plugin', 'ScheduledPlugin', 'WebPlugin'):
            return cls
        
        # 验证插件
        if hasattr(cls, 'get_regex_handlers'):
            handlers = cls.get_regex_handlers()
            if not isinstance(handlers, dict):
                raise TypeError(f"插件 {name} 的 get_regex_handlers 必须返回字典")
        
        # 注册插件
        mcs._plugins[name] = cls
        
        return cls


class BasePlugin(metaclass=PluginMeta):
    """
    插件基类
    所有插件应继承此类
    
    Example:
        class MyPlugin(BasePlugin):
            name = "我的插件"
            description = "这是一个示例插件"
            priority = 10
            
            @staticmethod
            def get_regex_handlers():
                return {
                    r'^测试': {
                        'handler': 'handle_test',
                        'description': '测试命令'
                    }
                }
            
            @staticmethod
            def handle_test(event):
                event.reply("测试成功！")
                return True
    """
    
    # 插件元信息
    name: str = ""
    description: str = ""
    author: str = ""
    version: str = "1.0.0"
    
    # 插件配置
    priority: int = DEFAULT_PLUGIN_PRIORITY
    enabled: bool = True
    
    # 内部属性（由框架设置）
    _source_file: str = ""
    _is_hot_reload: bool = False
    _load_time: float = 0
    
    @staticmethod
    def get_regex_handlers() -> Dict[str, Union[str, Dict[str, Any]]]:
        """
        返回正则处理器字典
        
        Returns:
            Dict[str, Union[str, Dict]]: 正则表达式到处理器的映射
            
            键: 正则表达式字符串
            值: 处理器名称字符串 或 处理器配置字典
            
            处理器配置字典支持的键:
            - handler: str - 处理方法名（必需）
            - owner_only: bool - 仅主人可用（默认False）
            - group_only: bool - 仅群聊可用（默认False）
            - priority: int - 处理器优先级（默认使用插件优先级）
            - description: str - 处理器描述
            - cooldown: int - 冷却时间（秒）
        
        Example::
        
            return {
                r'^帮助'$': 'handle_help',
                r'^设置\s+(.+)': {
                    'handler': 'handle_setting',
                    'owner_only': True,
                    'description': '修改设置'
                }
            }
        """
        return {}
    
    @classmethod
    def on_event(cls, event) -> Optional[bool]:
        """
        事件钩子，所有事件都会调用此方法
        
        Args:
            event: 事件对象
        
        Returns:
            None: 继续传递事件
            False: 拦截事件，停止传递
            True: 已处理，继续传递
        """
        pass
    
    @classmethod
    def on_plugin_load(cls) -> None:
        """插件加载时调用"""
        pass
    
    @classmethod
    def on_plugin_unload(cls) -> None:
        """插件卸载时调用"""
        pass
    
    @classmethod
    def on_plugin_reload(cls) -> None:
        """插件热重载时调用"""
        pass
    
    # ==================== Web 路由支持 ====================
    
    @classmethod
    def get_web_routes(cls) -> Optional[Dict[str, Any]]:
        """
        返回Web路由配置
        
        Returns:
            Dict: Web路由配置
        """
        return None
    
    # ==================== 辅助方法 ====================
    
    @classmethod
    def get_plugin_info(cls) -> Dict[str, Any]:
        """获取插件信息"""
        return {
            'name': cls.name or cls.__name__,
            'description': cls.description,
            'author': cls.author,
            'version': cls.version,
            'priority': cls.priority,
            'enabled': cls.enabled,
            'source_file': cls._source_file,
            'handlers': list(cls.get_regex_handlers().keys())
        }
    
    @classmethod
    def check_permission(cls, event, handler_config: Dict[str, Any]) -> PermissionResult:
        """检查权限"""
        if handler_config.get('owner_only', False):
            if not getattr(event, 'is_master', False):
                return PermissionResult.deny('owner_denied')
        
        if handler_config.get('group_only', False):
            if not getattr(event, 'is_group', False):
                return PermissionResult.deny('group_denied')
        
        return PermissionResult.allow()
    
    @classmethod
    def log_info(cls, message: str):
        """记录信息日志"""
        logger.info(f"[{cls.name or cls.__name__}] {message}")
    
    @classmethod
    def log_warning(cls, message: str):
        """记录警告日志"""
        logger.warning(f"[{cls.name or cls.__name__}] {message}")
    
    @classmethod
    def log_error(cls, message: str, exc_info: bool = False):
        """记录错误日志"""
        logger.error(f"[{cls.name or cls.__name__}] {message}", exc_info=exc_info)


# 兼容旧版本的别名
Plugin = BasePlugin


class ScheduledPlugin(BasePlugin):
    """
    定时任务插件基类
    支持定时执行任务
    """
    
    schedule_interval: int = 60
    schedule_enabled: bool = True
    
    @classmethod
    def on_schedule(cls) -> None:
        """定时任务执行方法"""
        pass
    
    @classmethod
    def get_schedule_config(cls) -> Dict[str, Any]:
        """获取定时任务配置"""
        return {
            'interval': cls.schedule_interval,
            'enabled': cls.schedule_enabled
        }


class WebPlugin(BasePlugin):
    """
    Web插件基类
    提供Web界面的插件应继承此类
    """
    
    web_path: str = ""
    web_menu_name: str = ""
    web_menu_icon: str = "bi-puzzle"
    web_priority: int = 100
    
    @classmethod
    def get_web_routes(cls) -> Optional[Dict[str, Any]]:
        """返回Web路由配置"""
        if not cls.web_path:
            return None
        
        return {
            'path': cls.web_path,
            'menu_name': cls.web_menu_name or cls.name or cls.__name__,
            'menu_icon': cls.web_menu_icon,
            'description': cls.description,
            'handler': 'render_page',
            'priority': cls.web_priority,
            'api_routes': cls.get_api_routes()
        }
    
    @classmethod
    def get_api_routes(cls) -> List[Dict[str, Any]]:
        """返回API路由列表"""
        return []
    
    @classmethod
    def render_page(cls, request) -> str:
        """渲染页面"""
        return f"<h1>{cls.web_menu_name or cls.name}</h1><p>{cls.description}</p>"

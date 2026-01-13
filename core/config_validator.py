#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
配置验证模块
提供配置验证和类型检查功能
"""

import logging
from typing import Dict, Any, Optional, List, Union, Type, Callable
from dataclasses import dataclass, field

logger = logging.getLogger('ElainaBot.core.config_validator')


@dataclass
class ConfigField:
    """配置字段定义"""
    name: str
    type: Type
    required: bool = True
    default: Any = None
    validator: Optional[Callable[[Any], bool]] = None
    description: str = ""
    
    def validate(self, value: Any) -> tuple:
        """
        验证字段值
        
        Returns:
            (is_valid, error_message)
        """
        # 检查必填
        if value is None:
            if self.required:
                return False, f"字段 '{self.name}' 是必填的"
            return True, None
        
        # 检查类型
        if not isinstance(value, self.type):
            # 尝试类型转换
            try:
                if self.type == bool and isinstance(value, str):
                    value = value.lower() in ('true', '1', 'yes')
                elif self.type == int and isinstance(value, str):
                    value = int(value)
                elif self.type == float and isinstance(value, (int, str)):
                    value = float(value)
                elif self.type == str:
                    value = str(value)
                elif self.type == list and isinstance(value, (tuple, set)):
                    value = list(value)
                else:
                    return False, f"字段 '{self.name}' 类型错误，期望 {self.type.__name__}，实际 {type(value).__name__}"
            except (ValueError, TypeError):
                return False, f"字段 '{self.name}' 类型转换失败"
        
        # 自定义验证
        if self.validator and not self.validator(value):
            return False, f"字段 '{self.name}' 验证失败"
        
        return True, None


@dataclass
class ConfigSchema:
    """配置模式定义"""
    name: str
    fields: List[ConfigField] = field(default_factory=list)
    description: str = ""
    
    def add_field(
        self,
        name: str,
        type: Type,
        required: bool = True,
        default: Any = None,
        validator: Optional[Callable[[Any], bool]] = None,
        description: str = ""
    ) -> "ConfigSchema":
        """添加字段定义"""
        self.fields.append(ConfigField(
            name=name,
            type=type,
            required=required,
            default=default,
            validator=validator,
            description=description
        ))
        return self
    
    def validate(self, config: Dict[str, Any]) -> tuple:
        """
        验证配置
        
        Returns:
            (is_valid, errors, validated_config)
        """
        errors = []
        validated = {}
        
        for field in self.fields:
            value = config.get(field.name, field.default)
            is_valid, error = field.validate(value)
            
            if not is_valid:
                errors.append(error)
            else:
                validated[field.name] = value if value is not None else field.default
        
        return len(errors) == 0, errors, validated


class ConfigValidator:
    """配置验证器"""
    
    # 预定义的验证器
    @staticmethod
    def is_positive(value: Union[int, float]) -> bool:
        """正数验证"""
        return value > 0
    
    @staticmethod
    def is_non_negative(value: Union[int, float]) -> bool:
        """非负数验证"""
        return value >= 0
    
    @staticmethod
    def is_port(value: int) -> bool:
        """端口号验证"""
        return 1 <= value <= 65535
    
    @staticmethod
    def is_not_empty(value: str) -> bool:
        """非空字符串验证"""
        return bool(value and value.strip())
    
    @staticmethod
    def is_valid_qq(value: str) -> bool:
        """QQ号验证"""
        return value.isdigit() and 5 <= len(value) <= 11
    
    @staticmethod
    def is_valid_host(value: str) -> bool:
        """主机地址验证"""
        import re
        # 简单验证：IP地址或域名
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*$'
        return bool(re.match(ip_pattern, value) or re.match(domain_pattern, value) or value == '0.0.0.0')
    
    @staticmethod
    def in_range(min_val: Union[int, float], max_val: Union[int, float]) -> Callable:
        """范围验证器工厂"""
        def validator(value: Union[int, float]) -> bool:
            return min_val <= value <= max_val
        return validator
    
    @staticmethod
    def in_list(allowed: List[Any]) -> Callable:
        """列表验证器工厂"""
        def validator(value: Any) -> bool:
            return value in allowed
        return validator
    
    @staticmethod
    def matches_pattern(pattern: str) -> Callable:
        """正则验证器工厂"""
        import re
        compiled = re.compile(pattern)
        def validator(value: str) -> bool:
            return bool(compiled.match(value))
        return validator


# ==================== 预定义配置模式 ====================

# 服务器配置模式
SERVER_CONFIG_SCHEMA = ConfigSchema(
    name="SERVER_CONFIG",
    description="服务器配置"
).add_field(
    "host", str, default="0.0.0.0",
    validator=ConfigValidator.is_valid_host,
    description="监听地址"
).add_field(
    "port", int, default=5003,
    validator=ConfigValidator.is_port,
    description="监听端口"
)

# 日志配置模式
LOG_CONFIG_SCHEMA = ConfigSchema(
    name="LOG_CONFIG",
    description="日志配置"
).add_field(
    "level", str, default="INFO",
    validator=ConfigValidator.in_list(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    description="日志级别"
)

# OneBot配置模式
ONEBOT_CONFIG_SCHEMA = ConfigSchema(
    name="ONEBOT_CONFIG",
    description="OneBot配置"
).add_field(
    "access_token", str, required=False, default="",
    description="访问令牌"
).add_field(
    "secret", str, required=False, default="",
    description="签名密钥"
)

# Web安全配置模式
WEB_SECURITY_SCHEMA = ConfigSchema(
    name="WEB_SECURITY",
    description="Web安全配置"
).add_field(
    "access_token", str, required=False, default="",
    description="Web访问令牌"
).add_field(
    "admin_password", str, required=False, default="",
    description="管理员密码"
)

# 日志数据库配置模式
LOG_DB_CONFIG_SCHEMA = ConfigSchema(
    name="LOG_DB_CONFIG",
    description="日志数据库配置"
).add_field(
    "retention_days", int, default=30,
    validator=ConfigValidator.is_positive,
    description="日志保留天数"
).add_field(
    "auto_cleanup", bool, default=True,
    description="自动清理"
)


def validate_all_configs(configs: Dict[str, Dict[str, Any]]) -> tuple:
    """
    验证所有配置
    
    Args:
        configs: 配置字典，键为配置名，值为配置内容
    
    Returns:
        (is_valid, all_errors, validated_configs)
    """
    schemas = {
        "SERVER_CONFIG": SERVER_CONFIG_SCHEMA,
        "LOG_CONFIG": LOG_CONFIG_SCHEMA,
        "ONEBOT_CONFIG": ONEBOT_CONFIG_SCHEMA,
        "WEB_SECURITY": WEB_SECURITY_SCHEMA,
        "LOG_DB_CONFIG": LOG_DB_CONFIG_SCHEMA,
    }
    
    all_errors = {}
    validated_configs = {}
    all_valid = True
    
    for config_name, schema in schemas.items():
        config = configs.get(config_name, {})
        is_valid, errors, validated = schema.validate(config)
        
        if not is_valid:
            all_valid = False
            all_errors[config_name] = errors
        
        validated_configs[config_name] = validated
    
    return all_valid, all_errors, validated_configs


def load_and_validate_config(config_module) -> Dict[str, Dict[str, Any]]:
    """
    加载并验证配置模块
    
    Args:
        config_module: 配置模块
    
    Returns:
        验证后的配置字典
    """
    configs = {
        "SERVER_CONFIG": getattr(config_module, 'SERVER_CONFIG', {}),
        "LOG_CONFIG": getattr(config_module, 'LOG_CONFIG', {}),
        "ONEBOT_CONFIG": getattr(config_module, 'ONEBOT_CONFIG', {}),
        "WEB_SECURITY": getattr(config_module, 'WEB_SECURITY', {}),
        "LOG_DB_CONFIG": getattr(config_module, 'LOG_DB_CONFIG', {}),
    }
    
    is_valid, errors, validated = validate_all_configs(configs)
    
    if not is_valid:
        for config_name, config_errors in errors.items():
            for error in config_errors:
                logger.warning(f"配置验证警告 [{config_name}]: {error}")
    
    return validated

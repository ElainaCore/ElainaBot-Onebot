#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
装饰器模块
提供统一的错误处理、日志记录、性能监控等装饰器
"""

import time
import logging
import functools
import traceback
import asyncio
from typing import Callable, TypeVar, Any, Optional, Union

logger = logging.getLogger('ElainaBot.core.decorators')

F = TypeVar('F', bound=Callable[..., Any])


def safe_execute(
    error_msg_template: str = "执行失败: {error}",
    default_return: Any = None,
    log_error: bool = True,
    reraise: bool = False
) -> Callable[[F], F]:
    """
    安全执行装饰器，捕获异常并记录日志
    
    Args:
        error_msg_template: 错误消息模板，支持 {error} 占位符
        default_return: 异常时的默认返回值
        log_error: 是否记录错误日志
        reraise: 是否重新抛出异常
    
    Example:
        @safe_execute("处理消息失败: {error}", default_return=False)
        def handle_message(event):
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_error:
                    error_msg = error_msg_template.format(error=str(e))
                    logger.error(f"{error_msg}\n{traceback.format_exc()}")
                    
                    # 推送到Web前台
                    try:
                        from web.app import add_error_log
                        add_error_log(error_msg, traceback.format_exc())
                    except:
                        pass
                
                if reraise:
                    raise
                return default_return
        return wrapper
    return decorator


def async_safe_execute(
    error_msg_template: str = "异步执行失败: {error}",
    default_return: Any = None,
    log_error: bool = True,
    reraise: bool = False
) -> Callable[[F], F]:
    """
    异步安全执行装饰器
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if log_error:
                    error_msg = error_msg_template.format(error=str(e))
                    logger.error(f"{error_msg}\n{traceback.format_exc()}")
                    
                    try:
                        from web.app import add_error_log
                        add_error_log(error_msg, traceback.format_exc())
                    except:
                        pass
                
                if reraise:
                    raise
                return default_return
        return wrapper
    return decorator


def log_execution(
    level: int = logging.DEBUG,
    log_args: bool = False,
    log_result: bool = False,
    max_result_length: int = 200
) -> Callable[[F], F]:
    """
    执行日志装饰器，记录函数调用信息
    
    Args:
        level: 日志级别
        log_args: 是否记录参数
        log_result: 是否记录返回值
        max_result_length: 返回值最大记录长度
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__qualname__
            
            if log_args:
                args_str = f"args={args}, kwargs={kwargs}"
                logger.log(level, f"调用 {func_name}({args_str})")
            else:
                logger.log(level, f"调用 {func_name}")
            
            result = func(*args, **kwargs)
            
            if log_result:
                result_str = str(result)[:max_result_length]
                logger.log(level, f"{func_name} 返回: {result_str}")
            
            return result
        return wrapper
    return decorator


def timing(
    threshold_ms: float = 0,
    log_level: int = logging.DEBUG
) -> Callable[[F], F]:
    """
    执行时间监控装饰器
    
    Args:
        threshold_ms: 超过此阈值才记录日志（毫秒）
        log_level: 日志级别
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            
            if elapsed_ms >= threshold_ms:
                logger.log(log_level, f"{func.__qualname__} 执行耗时: {elapsed_ms:.2f}ms")
            
            return result
        return wrapper
    return decorator


def async_timing(
    threshold_ms: float = 0,
    log_level: int = logging.DEBUG
) -> Callable[[F], F]:
    """
    异步执行时间监控装饰器
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            result = await func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            
            if elapsed_ms >= threshold_ms:
                logger.log(log_level, f"{func.__qualname__} 执行耗时: {elapsed_ms:.2f}ms")
            
            return result
        return wrapper
    return decorator


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
) -> Callable[[F], F]:
    """
    重试装饰器
    
    Args:
        max_attempts: 最大尝试次数
        delay: 初始延迟（秒）
        backoff: 延迟倍数
        exceptions: 需要重试的异常类型
        on_retry: 重试时的回调函数
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts - 1:
                        if on_retry:
                            on_retry(e, attempt + 1)
                        
                        logger.warning(f"{func.__qualname__} 第 {attempt + 1} 次尝试失败: {e}，{current_delay}秒后重试")
                        time.sleep(current_delay)
                        current_delay *= backoff
            
            raise last_exception
        return wrapper
    return decorator


def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
) -> Callable[[F], F]:
    """
    异步重试装饰器
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts - 1:
                        if on_retry:
                            on_retry(e, attempt + 1)
                        
                        logger.warning(f"{func.__qualname__} 第 {attempt + 1} 次尝试失败: {e}，{current_delay}秒后重试")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
            
            raise last_exception
        return wrapper
    return decorator


def singleton(cls):
    """
    单例装饰器
    
    Example:
        @singleton
        class MyManager:
            pass
    """
    instances = {}
    
    @functools.wraps(cls)
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    
    return get_instance


def deprecated(reason: str = "", replacement: str = ""):
    """
    弃用警告装饰器
    
    Args:
        reason: 弃用原因
        replacement: 替代方案
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            msg = f"{func.__qualname__} 已弃用"
            if reason:
                msg += f"：{reason}"
            if replacement:
                msg += f"，请使用 {replacement}"
            
            logger.warning(msg)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def validate_args(**validators):
    """
    参数验证装饰器
    
    Args:
        **validators: 参数名到验证函数的映射
    
    Example:
        @validate_args(
            user_id=lambda x: x and str(x).isdigit(),
            content=lambda x: x and len(x) <= 1000
        )
        def send_message(user_id, content):
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 获取函数参数名
            import inspect
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            
            # 验证参数
            for param_name, validator in validators.items():
                if param_name in bound.arguments:
                    value = bound.arguments[param_name]
                    if not validator(value):
                        raise ValueError(f"参数 {param_name} 验证失败: {value}")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def cache_result(ttl: float = 60.0, maxsize: int = 128):
    """
    结果缓存装饰器（带过期时间）
    
    Args:
        ttl: 缓存过期时间（秒）
        maxsize: 最大缓存数量
    """
    def decorator(func: F) -> F:
        cache = {}
        cache_times = {}
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            key = (args, tuple(sorted(kwargs.items())))
            current_time = time.time()
            
            # 检查缓存
            if key in cache:
                if current_time - cache_times[key] < ttl:
                    return cache[key]
                else:
                    del cache[key]
                    del cache_times[key]
            
            # 执行函数
            result = func(*args, **kwargs)
            
            # 清理过期缓存
            if len(cache) >= maxsize:
                expired_keys = [k for k, t in cache_times.items() if current_time - t >= ttl]
                for k in expired_keys:
                    cache.pop(k, None)
                    cache_times.pop(k, None)
                
                # 如果还是满了，删除最旧的
                if len(cache) >= maxsize:
                    oldest_key = min(cache_times, key=cache_times.get)
                    cache.pop(oldest_key, None)
                    cache_times.pop(oldest_key, None)
            
            # 存入缓存
            cache[key] = result
            cache_times[key] = current_time
            
            return result
        
        wrapper.cache_clear = lambda: (cache.clear(), cache_times.clear())
        return wrapper
    return decorator

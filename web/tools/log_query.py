#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
日志查询模块
支持从 SQLite 数据库获取日志
"""

from datetime import datetime
from flask import request, jsonify

received_messages = None
plugin_logs = None
framework_logs = None
error_logs = None
LOG_DB_CONFIG = None
add_error_log = None

_LOGS_MAP = {}
_DEFAULT_LIMIT = 100
_LOG_TYPES = frozenset(('plugin', 'framework', 'error'))

def set_log_queues(received, plugin, framework, error):
    global received_messages, plugin_logs, framework_logs, error_logs, _LOGS_MAP
    received_messages = received
    plugin_logs = plugin
    framework_logs = framework
    error_logs = error
    _LOGS_MAP = {
        'received': received_messages,
        'plugin': plugin_logs,
        'framework': framework_logs,
        'error': error_logs
    }

def set_config(log_db_config, error_log_func):
    global LOG_DB_CONFIG, add_error_log
    LOG_DB_CONFIG = log_db_config
    add_error_log = error_log_func

def handle_get_logs(log_type):
    if log_type not in _LOGS_MAP:
        return jsonify({'error': '无效的日志类型'}), 400
    
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('size', 50, type=int)
    
    logs = list(_LOGS_MAP[log_type])
    logs.reverse()
    start = (page - 1) * page_size
    
    return jsonify({
        'logs': logs[start:start + page_size],
        'total': len(logs),
        'page': page,
        'page_size': page_size,
        'total_pages': (len(logs) + page_size - 1) // page_size
    })

def get_today_logs_from_db(log_type, limit=100):
    """从 SQLite 数据库获取今日日志"""
    try:
        from function.log_db import get_log_from_db
        
        results = get_log_from_db(log_type, limit=limit)
        
        if not results:
            return []
        
        if not isinstance(results, list):
            results = [results]
        
        logs = []
        for row in results:
            log_entry = {
                'timestamp': row.get('timestamp', ''),
                'content': row.get('content', '')
            }
            
            if log_type == 'received':
                log_entry.update({
                    'user_id': row.get('user_id', ''),
                    'group_id': row.get('group_id', ''),
                    'message_type': row.get('message_type', ''),
                    'message_id': row.get('message_id', ''),
                    'message': row.get('content', '')  # 前端使用 message 字段
                })
            elif log_type == 'plugin':
                log_entry.update({
                    'user_id': row.get('user_id', ''),
                    'group_id': row.get('group_id', ''),
                    'plugin_name': row.get('plugin_name', '')
                })
            elif log_type == 'error':
                if row.get('traceback'):
                    log_entry['traceback'] = row['traceback']
                if row.get('resp_obj'):
                    log_entry['resp_obj'] = row['resp_obj']
                if row.get('send_payload'):
                    log_entry['send_payload'] = row['send_payload']
                if row.get('raw_message'):
                    log_entry['raw_message'] = row['raw_message']
            
            logs.append(log_entry)
        
        return logs
    except Exception as e:
        if add_error_log:
            add_error_log(f"获取数据库日志失败 {log_type}: {e}")
        return []

def get_today_message_logs_from_db(limit=100):
    """从 SQLite 数据库获取今日消息日志"""
    try:
        from function.log_db import get_log_from_db
        
        results = get_log_from_db('received', limit=limit)
        
        if not results:
            return []
        
        if not isinstance(results, list):
            results = [results]
        
        logs = []
        for row in results:
            logs.append({
                'timestamp': row.get('timestamp', ''),
                'content': row.get('content', ''),
                'user_id': row.get('user_id', ''),
                'group_id': row.get('group_id', 'c2c'),
                'message': row.get('content', ''),  # 前端使用 message 字段
                'message_type': row.get('message_type', ''),
                'message_id': row.get('message_id', '')
            })
        
        return logs
    except Exception as e:
        if add_error_log:
            add_error_log(f"获取今日消息日志失败: {e}")
        return []

def handle_get_today_logs():
    """获取今日所有类型的日志"""
    try:
        limit = request.args.get('limit', type=int) or _DEFAULT_LIMIT
        
        # 获取接收消息日志
        received_logs = get_today_message_logs_from_db(limit)
        result = {
            'received': {
                'logs': received_logs,
                'total': len(received_logs),
                'type': 'received'
            }
        }
        
        # 获取其他类型日志
        for log_type in _LOG_TYPES:
            logs = get_today_logs_from_db(log_type, limit)
            result[log_type] = {
                'logs': logs,
                'total': len(logs),
                'type': log_type
            }
        
        return jsonify({
            'success': True,
            'data': result,
            'limit': limit,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'message': f'成功获取今日日志，每种类型最多{limit}条'
        })
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': f'获取今日日志失败: {e}',
            'traceback': traceback.format_exc()
        }), 500

def handle_combined_logs():
    """获取合并的日志（内存 + 数据库）"""
    try:
        limit = request.args.get('limit', type=int, default=100)
        
        result = {}
        log_types = ['received', 'plugin', 'framework', 'error']
        
        for log_type in log_types:
            # 从内存获取
            if log_type in _LOGS_MAP and _LOGS_MAP[log_type]:
                memory_logs = list(_LOGS_MAP[log_type])[-limit:]
            else:
                memory_logs = []
            
            # 从数据库获取
            if log_type == 'received':
                db_logs = get_today_message_logs_from_db(limit)
            else:
                db_logs = get_today_logs_from_db(log_type, limit)
            
            # 合并并去重
            combined = []
            seen = set()
            
            for log in memory_logs + db_logs:
                log_key = f"{log.get('timestamp', '')}_{str(log.get('content', ''))[:50]}"
                if log_key not in seen:
                    seen.add(log_key)
                    combined.append(log)
            
            # 按时间戳排序
            combined.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            result[log_type] = {
                'logs': combined[:limit],
                'total': len(combined[:limit]),
                'type': log_type
            }
        
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取日志失败: {e}'
        }), 500

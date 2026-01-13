#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, time, shutil, json, gc, threading, logging, asyncio, signal
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Header, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
from config import LOG_DB_CONFIG, SERVER_CONFIG, WEB_SECURITY, ONEBOT_CONFIG
from function.httpx_pool import get_pool_manager

logger = logging.getLogger('ElainaBot')

try:
    from function.log_db import add_log_to_db
except:
    add_log_to_db = lambda *a, **k: False

http_pool = get_pool_manager()
_message_handler_ready = threading.Event()
_plugins_preloaded = False
_onebot_adapter = None

def setup_logging():
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
    formatter = logging.Formatter('[ElainaBot] %(asctime)s - %(levelname)s - %(message)s', datefmt='%m-%d %H:%M:%S')
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    for name in ['werkzeug', 'socketio', 'engineio', 'urllib3', 'uvicorn.access']:
        logging.getLogger(name).setLevel(logging.ERROR)

def convert_onebot_event(onebot_event):
    from core.onebot.adapter import OneBotV11Event
    if not isinstance(onebot_event, OneBotV11Event):
        return None
    from core.MessageEvent import MessageEvent
    return MessageEvent(json.dumps(onebot_event.to_dict(), ensure_ascii=False))

async def process_onebot_event(onebot_event):
    if hasattr(onebot_event, 'post_type') and onebot_event.post_type == 'meta_event':
        return
    
    event = convert_onebot_event(onebot_event)
    if not event:
        return
    
    if event.post_type == 'message':
        log_message(event)
    elif event.post_type == 'notice':
        log_notice(event)
    elif event.post_type == 'request':
        logger.info(f"📨 请求: {event.request_type} | 群 {event.group_id} | 用户 {event.user_id}")
    
    await asyncio.to_thread(process_event, event)

def log_message(event):
    msg_type = "群聊" if event.is_group else "私聊"
    sender = event.sender_card or event.sender_nickname or event.user_id
    location = f"群({event.group_id})" if event.is_group else f"私聊({event.user_id})"
    
    parts = []
    for seg in event.message:
        if not isinstance(seg, dict):
            continue
        t, d = seg.get('type', ''), seg.get('data', {})
        if t == 'text':
            parts.append(d.get('text', '').strip())
        elif t == 'at':
            parts.append('@全体' if d.get('qq') == 'all' else f"@{d.get('qq')}")
        elif t == 'image':
            parts.append('[图片]')
        elif t == 'reply':
            parts.append('↩️')
        else:
            parts.append(f'[{t}]')
    
    content = ''.join(parts) or event.content or "[空消息]"
    display = content[:100] + "..." if len(content) > 100 else content
    logger.info(f"📨 {msg_type} | {location} | {sender}: {display}")

def log_notice(event):
    notice_type = getattr(event, 'notice_type', 'unknown')
    group_id = str(event.group_id) if event.group_id else ''
    user_id = str(event.user_id) if event.user_id else ''
    operator_id = str(getattr(event, 'operator_id', '')) or ''
    
    msg_map = {
        'group_recall': f"📬 群({group_id}) | {operator_id or user_id} 撤回消息",
        'group_increase': f"📬 群({group_id}) | {user_id} 加入群聊",
        'group_decrease': f"📬 群({group_id}) | {user_id} 离开群聊",
        'friend_add': f"📬 新好友 {user_id}",
    }
    logger.info(msg_map.get(notice_type, f"📬 通知: {notice_type} | 群 {group_id} | 用户 {user_id}"))

def process_event(event):
    global _plugins_preloaded
    if not _plugins_preloaded:
        _message_handler_ready.wait(timeout=5)
    
    if event.ignore:
        return
    
    def db_tasks():
        if not event.skip_recording:
            event._record_user_and_group()
            event._record_message_to_db_only()
            import datetime
            event._notify_web_display(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        event.record_last_message_id()
    
    threading.Thread(target=db_tasks, daemon=True).start()
    
    from core.PluginManager import PluginManager
    PluginManager.dispatch_message(event)

def create_app():
    global _onebot_adapter
    
    app = FastAPI(title="ElainaBot")
    
    from core.onebot.adapter import init_adapter
    _onebot_adapter = init_adapter(
        access_token=ONEBOT_CONFIG.get('access_token'),
        secret=ONEBOT_CONFIG.get('secret')
    )
    
    @app.get("/")
    async def root():
        return {"status": "ok"}
    
    @app.post("/")
    @app.post("/onebot/v11/")
    @app.post("/onebot/v11/http")
    @app.post("/OneBotv11")
    async def onebot_http(request: Request):
        data = await request.body()
        if not data:
            raise HTTPException(status_code=400)
        
        success, event = _onebot_adapter.handle_http_callback(data, dict(request.headers))
        if event:
            asyncio.create_task(process_onebot_event(event))
        return JSONResponse(content={}, status_code=204)
    
    @app.websocket("/onebot/v11/")
    @app.websocket("/onebot/v11/ws")
    @app.websocket("/OneBotv11")
    async def onebot_ws(websocket: WebSocket):
        from core.onebot.api import set_main_loop
        set_main_loop(asyncio.get_running_loop())
        
        headers = dict(websocket.headers)
        valid, self_id, error = _onebot_adapter.validate_websocket_headers(headers)
        if not valid:
            await websocket.close(code=1008)
            return
        
        await websocket.accept()
        _onebot_adapter.register_bot(self_id, websocket)
        logger.info(f"✅ OneBot 连接: {websocket.client.host} | Bot {self_id}")
        
        try:
            while True:
                data = json.loads(await websocket.receive_text())
                event = _onebot_adapter.json_to_event(data)
                if event:
                    asyncio.create_task(process_onebot_event(event))
                elif "echo" in data and data["echo"] in _onebot_adapter.api_responses:
                    future = _onebot_adapter.api_responses.pop(data["echo"])
                    if not future.done():
                        future.set_result(data)
        except WebSocketDisconnect:
            logger.info(f"⚠️ 断开: Bot {self_id}")
        finally:
            _onebot_adapter.unregister_bot(self_id)
    
    # 挂载 Web 面板
    try:
        from flask import Flask
        from flask_socketio import SocketIO
        from fastapi.middleware.wsgi import WSGIMiddleware
        from flask_cors import CORS
        from web.app import web as web_blueprint, register_socketio_handlers
        from web.tools import log_handler
        
        web_dir = os.path.join(os.path.dirname(__file__), 'web')
        flask_app = Flask(__name__, static_folder=os.path.join(web_dir, 'static'), template_folder=os.path.join(web_dir, 'templates'))
        flask_app.config['SECRET_KEY'] = 'elainabot'
        flask_app.register_blueprint(web_blueprint, url_prefix='')
        CORS(flask_app)
        
        socketio = SocketIO(flask_app, cors_allowed_origins="*", logger=False, engineio_logger=False, async_mode='threading', path='/web/socket.io')
        log_handler.set_socketio(socketio)
        register_socketio_handlers(socketio)
        
        app.mount("/web", WSGIMiddleware(flask_app))
    except Exception as e:
        logger.error(f"Web 面板挂载失败: {e}")
    
    return app

def init_systems():
    global _plugins_preloaded
    setup_logging()
    gc.enable()
    
    def load_plugins():
        global _plugins_preloaded
        from core.PluginManager import PluginManager
        PluginManager.load_plugins()
        logger.info(f"✅ 加载插件: {len(PluginManager._plugins)} 个")
        _plugins_preloaded = True
        _message_handler_ready.set()
    
    threading.Thread(target=load_plugins, daemon=True).start()

def main():
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    
    init_systems()
    app = create_app()
    
    host = SERVER_CONFIG.get('host', '0.0.0.0')
    port = SERVER_CONFIG.get('port', 5004)
    
    logger.info(f"🚀 ElainaBot | 端口: {port}")
    logger.info(f"📡 OneBot: ws://{host}:{port}/OneBotv11")
    logger.info(f"🌐 Web: http://{host}:{port}/web/?token={WEB_SECURITY.get('access_token', '')}")
    
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="error", access_log=False)

if __name__ == "__main__":
    main()

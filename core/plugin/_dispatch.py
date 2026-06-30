"""事件分发 — PluginManager 的 Mixin (OneBot v11 适配)"""

import asyncio
import time

from core.base.logger import PLUGIN, get_logger, report_error

log = get_logger(PLUGIN, '管理器')


class _DispatchMixin:
    """异步事件分发"""

    def _build_dispatch_index(self):
        """按 priority 排序并预分桶 (消息桶/通用桶/类型桶), 避免每条事件遍历全部处理器"""
        self._all_handlers = sorted(self._all_handlers, key=lambda h: -h['priority'])
        self._all_interceptors = sorted(self._all_interceptors, key=lambda i: -i['priority'])

        msg, generic, typed = [], [], {}
        for h in self._all_handlers:
            event_types = h['event_types']
            if not event_types:
                msg.append(h)
                generic.append(h)
                continue
            if 'message' in event_types:
                msg.append(h)
            for et in event_types:
                if et != 'message':
                    typed.setdefault(et, []).append(h)
        self._msg_handlers = msg
        self._generic_handlers = generic
        self._typed_handlers = typed

    async def dispatch(self, event) -> bool:
        """异步分发事件到匹配的处理器, 返回是否命中"""
        content = event.content
        post_type = event.post_type

        # 拦截器
        for ic in self._all_interceptors:
            try:
                r = await ic['func'](event) if ic['is_coro'] else await asyncio.to_thread(ic['func'], event)
                if r is True:
                    return True
            except Exception as e:
                report_error(PLUGIN, ic.get('_plugin', '?'), e)

        # 消息事件 — 仅遍历消息桶 (event 必为 MessageEvent, 直取属性)
        if post_type == 'message':
            matched = []
            for h in self._msg_handlers:
                if h['group_only'] and not event.is_group:
                    continue
                if h['private_only'] and not event.is_private:
                    continue
                if h['owner_only'] and not self._is_owner(event):
                    continue
                m = h['compiled'].search(content)
                if not m:
                    continue
                if h['cooldown'] > 0:
                    key = f"{h['name']}:{event.user_id}"
                    now = time.time()
                    if now - self._cooldowns.get(key, 0) < h['cooldown']:
                        continue
                    self._cooldowns[key] = now
                matched.append((h, m))
                if h.get('block', False):  # 默认放行, block=True 时拦截后续
                    break
            if not matched:
                return False
            asyncio.create_task(self._run_chain(matched, event))
            return True

        # 通知/请求/元事件 — 候选 = 通用桶 + 该事件类型桶, 按优先级合并
        else:
            event_type = post_type
            if hasattr(event, 'notice_type'):
                event_type = f'notice.{event.notice_type}'
            elif hasattr(event, 'request_type'):
                event_type = f'request.{event.request_type}'

            typed = self._typed_handlers.get(event_type)
            if typed and self._generic_handlers:
                candidates = sorted((*self._generic_handlers, *typed), key=lambda h: -h['priority'])
            else:
                candidates = typed or self._generic_handlers

            matched = []
            for h in candidates:
                # 对非消息事件也尝试正则匹配 (pattern='.*' 可匹配所有)
                m = h['compiled'].search(content or event_type)
                if not m:
                    continue
                matched.append((h, m))
                if h.get('block', False):  # 默认放行, block=True 时拦截后续
                    break
            if not matched:
                return False
            asyncio.create_task(self._run_chain(matched, event))
            return True

    async def _run_chain(self, matched, event):
        """顺序执行命中的处理器链 (回复顺序与 priority 一致)"""
        for h, match in matched:
            await self._run_handler(h, event, match)

    async def _run_handler(self, h, event, match):
        """执行单个处理器 (带超时和异常捕获)"""
        plugin_name = h['name'] or h.get('_plugin', '')
        try:
            fn = h['func']
            async with asyncio.timeout(300):
                if h['is_coro']:
                    await fn(event, match)
                else:
                    await asyncio.to_thread(fn, event, match)
        except TimeoutError:
            report_error(PLUGIN, plugin_name, f'处理器 [{h["name"]}] 超时(300s)')
        except Exception as e:
            report_error(
                PLUGIN, plugin_name, e,
                context={
                    'handler': h['name'],
                    'user_id': str(getattr(event, 'user_id', '')),
                    'group_id': str(getattr(event, 'group_id', '')),
                    'content': (event.content if hasattr(event, 'content') else '')[:200],
                },
            )

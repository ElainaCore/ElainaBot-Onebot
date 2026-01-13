#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OneBot v11 API 完整实现
包含所有标准接口和扩展接口（NapCat/go-cqhttp）
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger('ElainaBot.core.onebot')

class OneBotAPI:
    """OneBot v11 API 封装类"""
    
    def __init__(self, client=None):
        self.client = client
    
    async def call_api(self, action: str, **params) -> Optional[Dict[str, Any]]:
        """
        调用 OneBot API
        
        Args:
            action: API 动作名称
            **params: API 参数
        
        Returns:
            API 响应结果，失败返回 None
        """
        try:
            from core.onebot.adapter import get_adapter
            adapter = get_adapter()
            if not adapter.bots:
                return None
            bot_id = list(adapter.bots.keys())[0]
            bot_info = adapter.bots[bot_id]
            if bot_info.get("type") != "websocket":
                return None
            ws = bot_info.get("ws")
            if not ws:
                return None
            echo = f"{time.time()}_{action}"
            request = {"action": action, "params": params, "echo": echo}
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            adapter.api_responses[echo] = future
            try:
                await ws.send_text(json.dumps(request))
            except Exception as e:
                logger.error(f"❌ API 请求失败: {action} - {e}")
                adapter.api_responses.pop(echo, None)
                return None
            try:
                return await asyncio.wait_for(future, timeout=30.0)
            except asyncio.TimeoutError:
                logger.warning(f"⏱️ API 超时: {action}")
                adapter.api_responses.pop(echo, None)
                return None
        except Exception as e:
            logger.error(f"❌ API 调用异常: {action} - {e}")
            return None

    # ==================== 消息相关 ====================
    
    async def send_private_msg(self, user_id: Union[str, int], message: Any, **kwargs) -> Optional[Dict]:
        """发送私聊消息"""
        return await self.call_api("send_private_msg", user_id=int(user_id), message=message, **kwargs)
    
    async def send_group_msg(self, group_id: Union[str, int], message: Any, **kwargs) -> Optional[Dict]:
        """发送群聊消息"""
        return await self.call_api("send_group_msg", group_id=int(group_id), message=message, **kwargs)
    
    async def send_msg(self, message_type: str = None, user_id: Union[str, int] = None, 
                      group_id: Union[str, int] = None, message: Any = None, **kwargs) -> Optional[Dict]:
        """发送消息（自动判断私聊/群聊）"""
        params = {"message": message}
        if message_type: params["message_type"] = message_type
        if user_id: params["user_id"] = int(user_id)
        if group_id: params["group_id"] = int(group_id)
        params.update(kwargs)
        return await self.call_api("send_msg", **params)
    
    async def delete_msg(self, message_id: Union[str, int]) -> Optional[Dict]:
        """撤回消息"""
        return await self.call_api("delete_msg", message_id=int(message_id))
    
    async def get_msg(self, message_id: Union[str, int]) -> Optional[Dict]:
        """获取消息详情"""
        return await self.call_api("get_msg", message_id=int(message_id))
    
    async def get_forward_msg(self, id: str) -> Optional[Dict]:
        """获取合并转发消息内容"""
        return await self.call_api("get_forward_msg", id=id)
    
    async def send_group_forward_msg(self, group_id: Union[str, int], messages: List[Dict]) -> Optional[Dict]:
        """发送群聊合并转发消息"""
        return await self.call_api("send_group_forward_msg", group_id=int(group_id), messages=messages)
    
    async def send_private_forward_msg(self, user_id: Union[str, int], messages: List[Dict]) -> Optional[Dict]:
        """发送私聊合并转发消息"""
        return await self.call_api("send_private_forward_msg", user_id=int(user_id), messages=messages)
    
    async def get_group_msg_history(self, group_id: Union[str, int], message_seq: int = 0, count: int = 20) -> Optional[Dict]:
        """获取群历史消息（message_seq=0 为最新）"""
        return await self.call_api("get_group_msg_history", group_id=int(group_id), message_seq=message_seq, count=count)
    
    async def get_friend_msg_history(self, user_id: Union[str, int], message_seq: int = 0, count: int = 20) -> Optional[Dict]:
        """获取好友历史消息"""
        return await self.call_api("get_friend_msg_history", user_id=int(user_id), message_seq=message_seq, count=count)
    
    async def mark_msg_as_read(self, message_id: Union[str, int]) -> Optional[Dict]:
        """标记消息已读"""
        return await self.call_api("mark_msg_as_read", message_id=int(message_id))
    
    async def mark_group_msg_as_read(self, group_id: Union[str, int]) -> Optional[Dict]:
        """标记群消息已读"""
        return await self.call_api("mark_group_msg_as_read", group_id=int(group_id))
    
    async def mark_private_msg_as_read(self, user_id: Union[str, int]) -> Optional[Dict]:
        """标记私聊消息已读"""
        return await self.call_api("mark_private_msg_as_read", user_id=int(user_id))
    
    async def mark_all_as_read(self) -> Optional[Dict]:
        """标记所有消息已读"""
        return await self.call_api("mark_all_as_read")
    
    async def forward_group_single_msg(self, group_id: Union[str, int], message_id: Union[str, int]) -> Optional[Dict]:
        """转发单条消息到群"""
        return await self.call_api("forward_group_single_msg", group_id=int(group_id), message_id=int(message_id))
    
    async def forward_friend_single_msg(self, user_id: Union[str, int], message_id: Union[str, int]) -> Optional[Dict]:
        """转发单条消息到好友"""
        return await self.call_api("forward_friend_single_msg", user_id=int(user_id), message_id=int(message_id))
    
    async def set_msg_emoji_like(self, message_id: Union[str, int], emoji_id: str) -> Optional[Dict]:
        """给消息点表情回应"""
        return await self.call_api("set_msg_emoji_like", message_id=int(message_id), emoji_id=emoji_id)

    # ==================== 戳一戳 ====================
    
    async def send_poke(self, user_id: Union[str, int], group_id: Union[str, int] = None, target_id: Union[str, int] = None) -> Optional[Dict]:
        """发送戳一戳（通用，group_id 不填则为私聊戳）"""
        params = {"user_id": int(user_id)}
        if group_id: params["group_id"] = int(group_id)
        if target_id: params["target_id"] = int(target_id)
        return await self.call_api("send_poke", **params)
    
    async def group_poke(self, group_id: Union[str, int], user_id: Union[str, int]) -> Optional[Dict]:
        """发送群聊戳一戳"""
        return await self.call_api("group_poke", group_id=int(group_id), user_id=int(user_id))
    
    async def friend_poke(self, user_id: Union[str, int], target_id: Union[str, int] = None) -> Optional[Dict]:
        """发送私聊戳一戳"""
        params = {"user_id": int(user_id)}
        if target_id: params["target_id"] = int(target_id)
        return await self.call_api("friend_poke", **params)

    # ==================== 账号相关 ====================
    
    async def get_login_info(self) -> Optional[Dict]:
        """获取登录号信息（QQ号、昵称）"""
        return await self.call_api("get_login_info")
    
    async def set_qq_profile(self, nickname: str = None, company: str = None, email: str = None, 
                            college: str = None, personal_note: str = None) -> Optional[Dict]:
        """设置登录号资料"""
        params = {}
        if nickname: params["nickname"] = nickname
        if company: params["company"] = company
        if email: params["email"] = email
        if college: params["college"] = college
        if personal_note: params["personal_note"] = personal_note
        return await self.call_api("set_qq_profile", **params)
    
    async def get_stranger_info(self, user_id: Union[str, int], no_cache: bool = False) -> Optional[Dict]:
        """获取陌生人信息"""
        return await self.call_api("get_stranger_info", user_id=int(user_id), no_cache=no_cache)
    
    async def get_friend_list(self, no_cache: bool = False) -> Optional[List[Dict]]:
        """获取好友列表"""
        result = await self.call_api("get_friend_list", no_cache=no_cache)
        return result.get("data", []) if result and result.get("retcode") == 0 else []
    
    async def get_unidirectional_friend_list(self) -> Optional[List[Dict]]:
        """获取单向好友列表"""
        result = await self.call_api("get_unidirectional_friend_list")
        return result.get("data", []) if result and result.get("retcode") == 0 else []
    
    async def delete_friend(self, user_id: Union[str, int]) -> Optional[Dict]:
        """删除好友"""
        return await self.call_api("delete_friend", user_id=int(user_id))
    
    async def delete_unidirectional_friend(self, user_id: Union[str, int]) -> Optional[Dict]:
        """删除单向好友"""
        return await self.call_api("delete_unidirectional_friend", user_id=int(user_id))

    # ==================== 群聊信息 ====================
    
    async def get_group_list(self, no_cache: bool = False) -> Optional[List[Dict]]:
        """获取群列表"""
        result = await self.call_api("get_group_list", no_cache=no_cache)
        return result.get("data", []) if result and result.get("retcode") == 0 else []
    
    async def get_group_info(self, group_id: Union[str, int], no_cache: bool = False) -> Optional[Dict]:
        """获取群信息"""
        return await self.call_api("get_group_info", group_id=int(group_id), no_cache=no_cache)
    
    async def get_group_member_info(self, group_id: Union[str, int], user_id: Union[str, int], no_cache: bool = False) -> Optional[Dict]:
        """获取群成员信息"""
        return await self.call_api("get_group_member_info", group_id=int(group_id), user_id=int(user_id), no_cache=no_cache)
    
    async def get_group_member_list(self, group_id: Union[str, int], no_cache: bool = False) -> Optional[List[Dict]]:
        """获取群成员列表"""
        result = await self.call_api("get_group_member_list", group_id=int(group_id), no_cache=no_cache)
        return result.get("data", []) if result and result.get("retcode") == 0 else []
    
    async def get_group_honor_info(self, group_id: Union[str, int], type: str = "all") -> Optional[Dict]:
        """获取群荣誉信息（type: talkative/performer/legend/strong_newbie/emotion/all）"""
        return await self.call_api("get_group_honor_info", group_id=int(group_id), type=type)
    
    async def get_group_system_msg(self) -> Optional[Dict]:
        """获取群系统消息（加群请求等）"""
        return await self.call_api("get_group_system_msg")
    
    async def get_essence_msg_list(self, group_id: Union[str, int]) -> Optional[Dict]:
        """获取群精华消息列表"""
        return await self.call_api("get_essence_msg_list", group_id=int(group_id))
    
    async def get_group_at_all_remain(self, group_id: Union[str, int]) -> Optional[Dict]:
        """获取群 @全体成员 剩余次数"""
        return await self.call_api("get_group_at_all_remain", group_id=int(group_id))
    
    async def get_prohibited_member_list(self, group_id: Union[str, int]) -> Optional[Dict]:
        """获取群禁言成员列表"""
        return await self.call_api("get_prohibited_member_list", group_id=int(group_id))

    # ==================== 群操作 ====================
    
    async def set_group_name(self, group_id: Union[str, int], group_name: str) -> Optional[Dict]:
        """设置群名称"""
        return await self.call_api("set_group_name", group_id=int(group_id), group_name=group_name)
    
    async def set_group_portrait(self, group_id: Union[str, int], file: str, cache: int = 1) -> Optional[Dict]:
        """设置群头像（file 支持 file:// / http:// / base64://）"""
        return await self.call_api("set_group_portrait", group_id=int(group_id), file=file, cache=cache)
    
    async def set_group_admin(self, group_id: Union[str, int], user_id: Union[str, int], enable: bool = True) -> Optional[Dict]:
        """设置/取消群管理员"""
        return await self.call_api("set_group_admin", group_id=int(group_id), user_id=int(user_id), enable=enable)
    
    async def set_group_card(self, group_id: Union[str, int], user_id: Union[str, int], card: str = "") -> Optional[Dict]:
        """设置群名片（card 为空则取消）"""
        return await self.call_api("set_group_card", group_id=int(group_id), user_id=int(user_id), card=card)
    
    async def set_group_special_title(self, group_id: Union[str, int], user_id: Union[str, int], 
                                     special_title: str = "", duration: int = -1) -> Optional[Dict]:
        """设置群专属头衔（duration=-1 为永久）"""
        return await self.call_api("set_group_special_title", group_id=int(group_id), user_id=int(user_id), 
                                  special_title=special_title, duration=duration)
    
    async def set_group_ban(self, group_id: Union[str, int], user_id: Union[str, int], duration: int = 1800) -> Optional[Dict]:
        """群单人禁言（duration=0 为解除禁言，单位秒）"""
        return await self.call_api("set_group_ban", group_id=int(group_id), user_id=int(user_id), duration=duration)
    
    async def set_group_whole_ban(self, group_id: Union[str, int], enable: bool = True) -> Optional[Dict]:
        """群全员禁言"""
        return await self.call_api("set_group_whole_ban", group_id=int(group_id), enable=enable)
    
    async def set_group_anonymous_ban(self, group_id: Union[str, int], anonymous: Dict = None, 
                                     anonymous_flag: str = None, duration: int = 1800) -> Optional[Dict]:
        """群匿名用户禁言"""
        params = {"group_id": int(group_id), "duration": duration}
        if anonymous: params["anonymous"] = anonymous
        if anonymous_flag: params["anonymous_flag"] = anonymous_flag
        return await self.call_api("set_group_anonymous_ban", **params)
    
    async def set_essence_msg(self, message_id: Union[str, int]) -> Optional[Dict]:
        """设置群精华消息"""
        return await self.call_api("set_essence_msg", message_id=int(message_id))
    
    async def delete_essence_msg(self, message_id: Union[str, int]) -> Optional[Dict]:
        """移除群精华消息"""
        return await self.call_api("delete_essence_msg", message_id=int(message_id))
    
    async def send_group_sign(self, group_id: Union[str, int]) -> Optional[Dict]:
        """群打卡"""
        return await self.call_api("send_group_sign", group_id=int(group_id))
    
    async def set_group_anonymous(self, group_id: Union[str, int], enable: bool = True) -> Optional[Dict]:
        """开启/关闭群匿名"""
        return await self.call_api("set_group_anonymous", group_id=int(group_id), enable=enable)
    
    async def send_group_notice(self, group_id: Union[str, int], content: str, image: str = None) -> Optional[Dict]:
        """发送群公告"""
        params = {"group_id": int(group_id), "content": content}
        if image: params["image"] = image
        return await self.call_api("_send_group_notice", **params)
    
    async def get_group_notice(self, group_id: Union[str, int]) -> Optional[Dict]:
        """获取群公告"""
        return await self.call_api("_get_group_notice", group_id=int(group_id))
    
    async def set_group_kick(self, group_id: Union[str, int], user_id: Union[str, int], reject_add_request: bool = False) -> Optional[Dict]:
        """踢出群成员（reject_add_request=True 拒绝再次加群）"""
        return await self.call_api("set_group_kick", group_id=int(group_id), user_id=int(user_id), reject_add_request=reject_add_request)
    
    async def set_group_leave(self, group_id: Union[str, int], is_dismiss: bool = False) -> Optional[Dict]:
        """退出群聊（is_dismiss=True 且为群主时解散群）"""
        return await self.call_api("set_group_leave", group_id=int(group_id), is_dismiss=is_dismiss)

    # ==================== 请求处理 ====================
    
    async def set_friend_add_request(self, flag: str, approve: bool = True, remark: str = "") -> Optional[Dict]:
        """处理好友添加请求"""
        return await self.call_api("set_friend_add_request", flag=flag, approve=approve, remark=remark)
    
    async def set_group_add_request(self, flag: str, sub_type: str, approve: bool = True, reason: str = "") -> Optional[Dict]:
        """处理加群请求/邀请（sub_type: add/invite）"""
        return await self.call_api("set_group_add_request", flag=flag, sub_type=sub_type, approve=approve, reason=reason)

    # ==================== 文件相关 ====================
    
    async def upload_group_file(self, group_id: Union[str, int], file: str, name: str, folder: str = None) -> Optional[Dict]:
        """上传群文件"""
        params = {"group_id": int(group_id), "file": file, "name": name}
        if folder: params["folder"] = folder
        return await self.call_api("upload_group_file", **params)
    
    async def delete_group_file(self, group_id: Union[str, int], file_id: str, busid: int) -> Optional[Dict]:
        """删除群文件"""
        return await self.call_api("delete_group_file", group_id=int(group_id), file_id=file_id, busid=busid)
    
    async def create_group_file_folder(self, group_id: Union[str, int], name: str, parent_id: str = "/") -> Optional[Dict]:
        """创建群文件夹"""
        return await self.call_api("create_group_file_folder", group_id=int(group_id), name=name, parent_id=parent_id)
    
    async def delete_group_folder(self, group_id: Union[str, int], folder_id: str) -> Optional[Dict]:
        """删除群文件夹"""
        return await self.call_api("delete_group_folder", group_id=int(group_id), folder_id=folder_id)
    
    async def get_group_file_system_info(self, group_id: Union[str, int]) -> Optional[Dict]:
        """获取群文件系统信息（文件数量、空间使用等）"""
        return await self.call_api("get_group_file_system_info", group_id=int(group_id))
    
    async def get_group_root_files(self, group_id: Union[str, int]) -> Optional[Dict]:
        """获取群根目录文件列表"""
        return await self.call_api("get_group_root_files", group_id=int(group_id))
    
    async def get_group_files_by_folder(self, group_id: Union[str, int], folder_id: str) -> Optional[Dict]:
        """获取群子目录文件列表"""
        return await self.call_api("get_group_files_by_folder", group_id=int(group_id), folder_id=folder_id)
    
    async def get_group_file_url(self, group_id: Union[str, int], file_id: str, busid: int) -> Optional[Dict]:
        """获取群文件下载链接"""
        return await self.call_api("get_group_file_url", group_id=int(group_id), file_id=file_id, busid=busid)
    
    async def upload_private_file(self, user_id: Union[str, int], file: str, name: str) -> Optional[Dict]:
        """上传私聊文件"""
        return await self.call_api("upload_private_file", user_id=int(user_id), file=file, name=name)

    # ==================== 图片/语音/视频 ====================
    
    async def get_image(self, file: str) -> Optional[Dict]:
        """获取图片信息"""
        return await self.call_api("get_image", file=file)
    
    async def get_record(self, file: str, out_format: str = "mp3") -> Optional[Dict]:
        """获取语音文件"""
        return await self.call_api("get_record", file=file, out_format=out_format)
    
    async def can_send_image(self) -> Optional[Dict]:
        """检查是否可以发送图片"""
        return await self.call_api("can_send_image")
    
    async def can_send_record(self) -> Optional[Dict]:
        """检查是否可以发送语音"""
        return await self.call_api("can_send_record")
    
    async def ocr_image(self, image: str) -> Optional[Dict]:
        """图片 OCR 文字识别"""
        return await self.call_api("ocr_image", image=image)
    
    async def download_file(self, url: str, thread_count: int = 1, headers: Union[str, List[str]] = None) -> Optional[Dict]:
        """下载文件到缓存目录"""
        params = {"url": url, "thread_count": thread_count}
        if headers: params["headers"] = headers
        return await self.call_api("download_file", **params)

    # ==================== 系统相关 ====================
    
    async def get_version_info(self) -> Optional[Dict]:
        """获取 OneBot 实现版本信息"""
        return await self.call_api("get_version_info")
    
    async def get_status(self) -> Optional[Dict]:
        """获取运行状态"""
        return await self.call_api("get_status")
    
    async def set_restart(self, delay: int = 0) -> Optional[Dict]:
        """重启 OneBot 实现（delay 为延迟毫秒数）"""
        return await self.call_api("set_restart", delay=delay)
    
    async def clean_cache(self) -> Optional[Dict]:
        """清理缓存"""
        return await self.call_api("clean_cache")
    
    async def get_cookies(self, domain: str = "") -> Optional[Dict]:
        """获取 Cookies"""
        return await self.call_api("get_cookies", domain=domain)
    
    async def get_csrf_token(self) -> Optional[Dict]:
        """获取 CSRF Token"""
        return await self.call_api("get_csrf_token")
    
    async def get_credentials(self, domain: str = "") -> Optional[Dict]:
        """获取 QQ 相关接口凭证"""
        return await self.call_api("get_credentials", domain=domain)

    # ==================== 扩展接口 (NapCat/go-cqhttp) ====================
    
    async def get_online_clients(self, no_cache: bool = False) -> Optional[Dict]:
        """获取当前账号在线客户端列表"""
        return await self.call_api("get_online_clients", no_cache=no_cache)
    
    async def get_model_show(self, model: str) -> Optional[Dict]:
        """获取在线机型"""
        return await self.call_api("_get_model_show", model=model)
    
    async def set_model_show(self, model: str, model_show: str) -> Optional[Dict]:
        """设置在线机型"""
        return await self.call_api("_set_model_show", model=model, model_show=model_show)
    
    async def check_url_safely(self, url: str) -> Optional[Dict]:
        """检查链接安全性"""
        return await self.call_api("check_url_safely", url=url)
    
    async def get_word_slices(self, content: str) -> Optional[Dict]:
        """获取中文分词"""
        return await self.call_api(".get_word_slices", content=content)
    
    async def handle_quick_operation(self, context: Dict, operation: Dict) -> Optional[Dict]:
        """快速操作（对事件执行快速操作）"""
        return await self.call_api(".handle_quick_operation", context=context, operation=operation)
    
    async def get_robot_uin_range(self) -> Optional[Dict]:
        """获取机器人 QQ 号范围"""
        return await self.call_api("get_robot_uin_range")
    
    async def set_online_status(self, status: int, ext_status: int = 0, battery_status: int = 0) -> Optional[Dict]:
        """设置在线状态（status: 11在线/31离开/41隐身/50忙碌/60Q我吧/70请勿打扰）"""
        return await self.call_api("set_online_status", status=status, ext_status=ext_status, battery_status=battery_status)
    
    async def get_friends_with_category(self) -> Optional[Dict]:
        """获取好友列表（带分组信息）"""
        return await self.call_api("get_friends_with_category")
    
    async def set_qq_avatar(self, file: str) -> Optional[Dict]:
        """设置 QQ 头像"""
        return await self.call_api("set_qq_avatar", file=file)
    
    async def get_file(self, file_id: str) -> Optional[Dict]:
        """获取文件信息"""
        return await self.call_api("get_file", file_id=file_id)
    
    async def forward_single_msg_to_group(self, message_id: Union[str, int], group_id: Union[str, int]) -> Optional[Dict]:
        """转发单条消息到群（别名）"""
        return await self.call_api("forward_single_msg_to_group", message_id=int(message_id), group_id=int(group_id))
    
    async def forward_single_msg_to_friend(self, message_id: Union[str, int], user_id: Union[str, int]) -> Optional[Dict]:
        """转发单条消息到好友（别名）"""
        return await self.call_api("forward_single_msg_to_friend", message_id=int(message_id), user_id=int(user_id))
    
    async def translate_en2zh(self, words: List[str]) -> Optional[Dict]:
        """英译中"""
        return await self.call_api("translate_en2zh", words=words)
    
    async def set_input_status(self, user_id: Union[str, int], event_type: str) -> Optional[Dict]:
        """设置输入状态（event_type: EventType_InputStatus）"""
        return await self.call_api("set_input_status", user_id=int(user_id), event_type=event_type)
    
    async def get_group_info_ex(self, group_id: Union[str, int]) -> Optional[Dict]:
        """获取群详细信息（扩展）"""
        return await self.call_api("get_group_info_ex", group_id=int(group_id))
    
    async def get_group_ignore_add_request(self, group_id: Union[str, int]) -> Optional[Dict]:
        """获取群过滤系统消息"""
        return await self.call_api("get_group_ignore_add_request", group_id=int(group_id))
    
    async def set_group_sign_in(self, group_id: Union[str, int]) -> Optional[Dict]:
        """群签到（别名）"""
        return await self.call_api("set_group_sign_in", group_id=int(group_id))
    
    async def get_mini_app_ark(self, type: str, title: str, desc: str, pic_url: str, jump_url: str) -> Optional[Dict]:
        """获取小程序卡片 Ark JSON"""
        return await self.call_api("get_mini_app_ark", type=type, title=title, desc=desc, pic_url=pic_url, jump_url=jump_url)
    
    async def get_ai_characters(self, group_id: Union[str, int], chat_type: int = 1) -> Optional[Dict]:
        """获取 AI 语音角色列表"""
        return await self.call_api("get_ai_characters", group_id=int(group_id), chat_type=chat_type)
    
    async def send_group_ai_record(self, group_id: Union[str, int], character: str, text: str) -> Optional[Dict]:
        """发送群 AI 语音"""
        return await self.call_api("send_group_ai_record", group_id=int(group_id), character=character, text=text)
    
    async def get_ai_record(self, group_id: Union[str, int], character: str, text: str) -> Optional[Dict]:
        """获取 AI 语音（返回文件路径）"""
        return await self.call_api("get_ai_record", group_id=int(group_id), character=character, text=text)


# ==================== 全局实例和辅助函数 ====================

_onebot_api_instance: Optional[OneBotAPI] = None
_main_loop = None

def get_onebot_api() -> OneBotAPI:
    """获取 OneBotAPI 单例实例"""
    global _onebot_api_instance
    if _onebot_api_instance is None:
        _onebot_api_instance = OneBotAPI()
    return _onebot_api_instance

def set_main_loop(loop):
    """设置主事件循环（用于跨线程调用）"""
    global _main_loop
    _main_loop = loop

def run_async_api(coro):
    """
    在同步环境中运行异步 API
    自动处理事件循环和跨线程调用
    """
    import concurrent.futures
    try:
        try:
            loop = asyncio.get_running_loop()
            if _main_loop and _main_loop != loop:
                future = asyncio.run_coroutine_threadsafe(coro, _main_loop)
                return future.result(timeout=30)
            else:
                new_loop = asyncio.new_event_loop()
                def run():
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(coro)
                    finally:
                        new_loop.close()
                with concurrent.futures.ThreadPoolExecutor() as ex:
                    return ex.submit(run).result(timeout=30)
        except RuntimeError:
            if _main_loop:
                future = asyncio.run_coroutine_threadsafe(coro, _main_loop)
                return future.result(timeout=30)
            else:
                new_loop = asyncio.new_event_loop()
                def run():
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(coro)
                    finally:
                        new_loop.close()
                with concurrent.futures.ThreadPoolExecutor() as ex:
                    return ex.submit(run).result(timeout=30)
    except Exception as e:
        logger.error(f"❌ run_async_api 异常: {e}")
        return None

# ==================== 同步便捷函数 ====================

def send_private_msg_sync(user_id, message, **kwargs):
    """同步发送私聊消息"""
    return run_async_api(get_onebot_api().send_private_msg(user_id, message, **kwargs))

def send_group_msg_sync(group_id, message, **kwargs):
    """同步发送群聊消息"""
    return run_async_api(get_onebot_api().send_group_msg(group_id, message, **kwargs))

def send_msg_sync(message_type=None, user_id=None, group_id=None, message=None, **kwargs):
    """同步发送消息"""
    return run_async_api(get_onebot_api().send_msg(message_type, user_id, group_id, message, **kwargs))

def delete_msg_sync(message_id):
    """同步撤回消息"""
    return run_async_api(get_onebot_api().delete_msg(message_id))

def get_login_info_sync():
    """同步获取登录信息"""
    return run_async_api(get_onebot_api().get_login_info())

def get_group_member_info_sync(group_id, user_id, no_cache=False):
    """同步获取群成员信息"""
    return run_async_api(get_onebot_api().get_group_member_info(group_id, user_id, no_cache))

def get_stranger_info_sync(user_id, no_cache=False):
    """同步获取陌生人信息"""
    return run_async_api(get_onebot_api().get_stranger_info(user_id, no_cache))

def set_group_ban_sync(group_id, user_id, duration=1800):
    """同步群禁言"""
    return run_async_api(get_onebot_api().set_group_ban(group_id, user_id, duration))

def set_group_kick_sync(group_id, user_id, reject_add_request=False):
    """同步踢出群成员"""
    return run_async_api(get_onebot_api().set_group_kick(group_id, user_id, reject_add_request))

def set_group_card_sync(group_id, user_id, card=""):
    """同步设置群名片"""
    return run_async_api(get_onebot_api().set_group_card(group_id, user_id, card))

async def call_onebot_api(action: str, params: Dict = None):
    """通用 API 调用（异步）"""
    return await get_onebot_api().call_api(action, **(params or {}))

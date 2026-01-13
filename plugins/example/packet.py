#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import random
import logging
import traceback
import gzip
import struct
from typing import Dict, Any, Optional, Union
from io import BytesIO

from core.plugin.base import BasePlugin as Plugin
from core.onebot.api import get_onebot_api, run_async_api

logger = logging.getLogger('ElainaBot.plugins.packet')

# 全局变量：消息获取模式（1=平铺模式，2=嵌套模式）
PACKET_MODE = 2


# ==================== ProtoBuf 编解码器 ====================

class Writer:
    def __init__(self):
        self.buf = BytesIO()
    
    @classmethod
    def create(cls):
        return cls()
    
    def uint32(self, value: int):
        while value > 0x7f:
            self.buf.write(bytes([(value & 0x7f) | 0x80]))
            value >>= 7
        self.buf.write(bytes([value & 0x7f]))
        return self
    
    def int32(self, value: int):
        if value < 0:
            value = (1 << 32) + value
        return self.uint32(value)
    
    def int64(self, value: Union[int, str]):
        if isinstance(value, str):
            value = int(value)
        if value < 0:
            value = (1 << 64) + value
        return self.uint32(value)
    
    def string(self, value: str):
        data = value.encode('utf-8')
        self.uint32(len(data))
        self.buf.write(data)
        return self
    
    def bool(self, value: bool):
        return self.uint32(1 if value else 0)
    
    def bytes(self, value: bytes):
        self.uint32(len(value))
        self.buf.write(value)
        return self
    
    def fixed32(self, value: int):
        self.buf.write(struct.pack('<I', value))
        return self
    
    def fixed64(self, value: int):
        self.buf.write(struct.pack('<Q', value))
        return self
    
    def finish(self) -> bytes:
        return self.buf.getvalue()


class Reader:
    def __init__(self, data: bytes):
        self.buf = data
        self.pos = 0
        self.len = len(data)
    
    @classmethod
    def create(cls, data: bytes):
        return cls(data)
    
    def uint32(self) -> int:
        result = 0
        shift = 0
        while True:
            if self.pos >= self.len:
                break
            byte_val = self.buf[self.pos]
            self.pos += 1
            result |= (byte_val & 0x7f) << shift
            if not (byte_val & 0x80):
                break
            shift += 7
        return result
    
    def int64(self):
        value = self.uint32()
        if value > 0x7fffffffffffffff:
            value = value - (1 << 64)
        return value
    
    def fixed64(self):
        data = self.buf[self.pos:self.pos + 8]
        self.pos += 8
        return struct.unpack('<Q', data)[0]
    
    def bytes(self) -> bytes:
        length = self.uint32()
        data = self.buf[self.pos:self.pos + length]
        self.pos += length
        return data
    
    def fixed32(self) -> int:
        data = self.buf[self.pos:self.pos + 4]
        self.pos += 4
        return struct.unpack('<I', data)[0]


class Protobuf:
    def __init__(self):
        self.Writer = Writer
        self.Reader = Reader
    
    def _should_encode_as_string(self, value: dict) -> bool:
        """通用检测：判断字典是否应该被编码为字符串而不是嵌套结构"""
        # 使用通用的检测方法来判断
        return self._looks_like_misdecoded_string(value)
    
    def encode(self, obj):
        writer = self.Writer.create()
        for tag in sorted(map(int, obj.keys())):
            value = obj[tag]
            self._encode(writer, tag, value)
        return writer.finish()
    
    def _encode(self, writer, tag, value):
        if value is None:
            return
        
        if isinstance(value, int) and not isinstance(value, bool):
            writer.uint32((tag << 3) | 0).int32(value)
        elif isinstance(value, int) and abs(value) > 2147483647:
            writer.uint32((tag << 3) | 0).int64(str(value))
        elif isinstance(value, str):
            writer.uint32((tag << 3) | 2).string(value)
        elif isinstance(value, bool):
            writer.uint32((tag << 3) | 0).bool(value)
        elif isinstance(value, (dict, list, bytes, bytearray)):
            if isinstance(value, (bytes, bytearray)):
                writer.uint32((tag << 3) | 2).bytes(bytes(value))
            elif isinstance(value, list):
                for item in value:
                    self._encode(writer, tag, item)
            elif value is None:
                pass
            elif isinstance(value, dict):
                # 检查是否应该编码为字符串
                if self._should_encode_as_string(value):
                    # 将嵌套结构编码为字节，然后作为字符串编码
                    nested_bytes = self.encode(value)
                    # 将字节转换为 base64 或直接作为字符串
                    # 但这里我们需要保持原始字节格式
                    writer.uint32((tag << 3) | 2).bytes(nested_bytes)
                else:
                    nested_buffer = self.encode(value)
                    writer.uint32((tag << 3) | 2).bytes(nested_buffer)
        else:
            raise Exception(f"Unsupported type: {type(value).__name__}")
    
    def _should_keep_as_string(self, decoded_value: dict, original_bytes: bytes) -> bool:
        """
        通用检测：判断递归解码的结果是否应该保持为字符串格式
        参考 JavaScript 原始实现的逻辑
        """
        # 首先检查原始字节是否可以解码为有效的 UTF-8 字符串
        try:
            decoded_str = original_bytes.decode('utf-8')
            re_encoded = decoded_str.encode('utf-8')
            # 如果重新编码后与原始字节相同，说明原始数据可能是字符串
            if re_encoded == original_bytes:
                # 检查解码后的字符串是否包含大量控制字符或特殊字符
                # 如果包含很多控制字符，说明这可能是二进制数据被错误解码，应该保持为嵌套结构
                if self._has_too_many_control_chars(decoded_str):
                    return False
                
                # 检查递归解码的结果是否"可疑"（看起来像应该被编码为字符串的结构）
                # 只有当递归解码的结果看起来像是一个简单的、可能被误解码的结构时，才使用字符串
                return self._looks_like_misdecoded_string(decoded_value)
        except:
            pass
        return False
    
    def _has_too_many_control_chars(self, text: str) -> bool:
        """检查字符串是否包含过多的控制字符或特殊字符"""
        if not text:
            return False
        
        # 统计控制字符和特殊字符的数量
        control_char_count = 0
        total_chars = len(text)
        
        for char in text:
            # 检查是否是控制字符（除了常见的空白字符）
            if ord(char) < 32 and char not in ('\n', '\r', '\t'):
                control_char_count += 1
            # 检查是否是其他特殊字符（如 \u0012 等）
            elif ord(char) >= 0x7F and ord(char) < 0xA0:
                control_char_count += 1
        
        # 如果控制字符占比超过 5%，说明可能是二进制数据被错误解码
        if total_chars > 0:
            control_ratio = control_char_count / total_chars
            if control_ratio > 0.05:
                return True
        
        # 如果控制字符数量超过 10 个，也认为是过多的
        if control_char_count > 10:
            return True
        
        return False
    
    def _looks_like_misdecoded_string(self, value: dict) -> bool:
        """
        检测嵌套结构是否看起来像被误解码的字符串字段
        参考 JavaScript 原始实现的简单逻辑，但添加更严格的判断
        """
        if not isinstance(value, dict):
            return False
        
        keys = list(value.keys())
        key_count = len(keys)
        
        # 如果字段数量很少（1-4个），可能是误解码的字符串字段
        # 真正的嵌套结构通常有更多字段或更复杂的结构
        if key_count < 1 or key_count > 4:
            return False
        
        # 检查是否有超大整数键（这通常是误解码的字符串）
        # 如果键是很大的整数（超过 1000000），很可能是误解码的字符串
        has_large_int_key = False
        for key in keys:
            if isinstance(key, int) and abs(key) > 1000000:
                has_large_int_key = True
                break
        
        # 如果包含超大整数键，很可能是误解码的字符串
        if has_large_int_key:
            return True
        
        # 检查字段类型组合和结构复杂度
        has_string = False
        has_list = False
        has_nested_dict = False
        has_complex_nested = False
        simple_type_count = 0
        
        for key in keys:
            val = value[key]
            if isinstance(val, str):
                has_string = True
                simple_type_count += 1
            elif isinstance(val, (int, float, bool)):
                simple_type_count += 1
            elif isinstance(val, list):
                has_list = True
                # 检查列表中的元素是否简单
                for item in val:
                    if isinstance(item, dict):
                        has_nested_dict = True
                        # 检查嵌套字典是否复杂（超过 2 个字段）
                        if len(item) > 2:
                            has_complex_nested = True
                        break
                    elif not isinstance(item, (str, int, float, bool)):
                        has_nested_dict = True
                        break
            elif isinstance(val, dict):
                has_nested_dict = True
                # 检查嵌套字典是否复杂（超过 2 个字段）
                if len(val) > 2:
                    has_complex_nested = True
        
        # 如果有复杂嵌套结构，不太可能是字符串字段
        if has_complex_nested:
            return False
        
        # 如果包含嵌套字典，且字段数量较多，不太可能是字符串字段
        if has_nested_dict and key_count > 3:
            return False
        
        # 如果只有一个字段，且是嵌套字典，检查嵌套字典是否简单
        if key_count == 1 and has_nested_dict:
            nested_val = value[keys[0]]
            if isinstance(nested_val, dict):
                # 如果嵌套字典只有一个字段，且值是简单类型，可能是误解码的字符串
                if len(nested_val) == 1:
                    nested_key = list(nested_val.keys())[0]
                    nested_value = nested_val[nested_key]
                    if isinstance(nested_value, (str, int, float, bool)):
                        # 如果嵌套键是超大整数，很可能是误解码的字符串
                        if isinstance(nested_key, int) and abs(nested_key) > 1000000:
                            return True
                        # 如果嵌套值也是简单类型，可能是误解码的字符串
                        return True
        
        # 如果包含字符串和列表，且没有深层嵌套，很可能是字符串字段
        if has_string and has_list and not has_nested_dict:
            return True
        
        # 如果只有简单类型字段（字符串、数字），且字段数量很少，也可能是字符串字段
        if simple_type_count == key_count and key_count <= 3:
            return True
        
        # 如果包含字符串，且大部分字段是简单类型，且没有嵌套字典，也可能是字符串字段
        if has_string and simple_type_count >= key_count - 1 and key_count <= 3 and not has_nested_dict:
            return True
        
        return False
    
    def decode(self, buffer):
        if isinstance(buffer, str):
            buffer = bytes.fromhex(buffer)
        
        result = {}
        reader = self.Reader.create(buffer)
        
        while reader.pos < reader.len:
            k = reader.uint32()
            tag = k >> 3
            wire_type = k & 0b111
            
            value = None
            
            if wire_type == 0:
                value = self.long2int(reader.int64())
            elif wire_type == 1:
                value = self.long2int(reader.fixed64())
            elif wire_type == 2:
                value = reader.bytes()
                original_bytes = value  # 保存原始字节
                try:
                    decoded_value = self.decode(value)
                    # 检查是否应该保持为字符串
                    if self._should_keep_as_string(decoded_value, original_bytes):
                        # 尝试解码为字符串
                        try:
                            value = original_bytes.decode('utf-8')
                        except:
                            # 如果无法解码为 UTF-8，保持为原始字节的十六进制表示
                            value = original_bytes.hex()
                    else:
                        value = decoded_value
                except:
                    try:
                        decoded = value.decode('utf-8')
                        re_encoded = decoded.encode('utf-8')
                        if all(a == b for a, b in zip(re_encoded, value)):
                            value = decoded
                    except:
                        pass
            elif wire_type == 5:
                value = reader.fixed32()
            else:
                raise Exception(f"Unsupported wire type: {wire_type}")
            
            if tag in result:
                if isinstance(result[tag], list):
                    result[tag].append(value)
                else:
                    result[tag] = [result[tag], value]
            else:
                result[tag] = value
        
        return result
    
    def long2int(self, long):
        """
        将长整数转换为整数或字符串
        参考 JavaScript 原始实现：如果超过 Number.MAX_SAFE_INTEGER，返回字符串
        """
        if isinstance(long, int):
            # JavaScript Number.MAX_SAFE_INTEGER = 9007199254740991
            # 如果超过这个范围，应该返回字符串
            if -9007199254740991 <= long <= 9007199254740991:
                return long
            else:
                # 超过安全整数范围，返回字符串
                return str(long)
        return long


pb = Protobuf()


# ==================== Packet 辅助类 ====================

class PacketHelper:
    @staticmethod
    def random_uint() -> int:
        return random.randint(0, 0xFFFFFFFF)
    
    @staticmethod
    def process_json(data: Union[str, dict]) -> dict:
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as e:
                logger.error(f"JSON 解析失败: {str(e)}")
                return {}
        return PacketHelper._process_json_recursive(data)
    
    @staticmethod
    def _process_json_recursive(obj: Any, path: list = None) -> Any:
        if path is None:
            path = []
        
        if isinstance(obj, bytes):
            return obj
        elif isinstance(obj, list):
            return [PacketHelper._process_json_recursive(item, path + [str(i+1)]) for i, item in enumerate(obj)]
        elif isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                try:
                    num_key = int(key)
                except ValueError:
                    logger.warning(f"键不是有效的整数: {key}")
                    continue
                
                current_path = path + [key]
                
                if isinstance(value, dict):
                    result[num_key] = PacketHelper._process_json_recursive(value, current_path)
                elif isinstance(value, list):
                    result[num_key] = [PacketHelper._process_json_recursive(item, current_path + [str(i+1)]) 
                                      for i, item in enumerate(value)]
                elif isinstance(value, str):
                    if value.startswith("hex->"):
                        hex_str = value[5:]
                        if PacketHelper._is_hex_string(hex_str):
                            result[num_key] = bytes.fromhex(hex_str)
                        else:
                            result[num_key] = value
                    else:
                        result[num_key] = value
                else:
                    result[num_key] = value
            return result
        else:
            return obj
    
    @staticmethod
    def _is_hex_string(s: str) -> bool:
        if len(s) % 2 != 0:
            return False
        try:
            bytes.fromhex(s)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def json_dumps_with_bytes(obj: Any) -> str:
        def default(o):
            if isinstance(o, bytes):
                return f"hex->{o.hex()}"
            raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")
        return json.dumps(obj, default=default, indent=2, ensure_ascii=False)


# ==================== Packet 发送器 ====================

class PacketSender:
    def __init__(self, event):
        self.event = event
        self.api = event.api
    
    async def send_packet(self, cmd: str, content: Union[dict, str]) -> Optional[dict]:
        try:
            if isinstance(content, str):
                content = json.loads(content)
            
            processed = PacketHelper.process_json(content)
            data_bytes = pb.encode(processed)
            data_hex = data_bytes.hex()
            
            result = await self.api.call_api('send_packet', cmd=cmd, data=data_hex)
            
            if result and isinstance(result, dict):
                response_data = result.get('data')
                
                if isinstance(response_data, str) and response_data:
                    try:
                        decoded = pb.decode(response_data)
                        return decoded
                    except Exception as e:
                        logger.error(f"解码响应失败: {str(e)}")
                        return result
                elif isinstance(response_data, dict) and response_data:
                    return response_data
            
            return result
        except Exception as e:
            logger.error(f"发送数据包失败: {str(e)}")
            logger.error(traceback.format_exc())
            return None
    
    async def send_elem(self, content: Union[dict, str]) -> Optional[dict]:
        try:
            if isinstance(content, str):
                content = json.loads(content)
            
            processed_content = PacketHelper.process_json(content)
            
            target_id = self.event.group_id if self.event.is_group else self.event.user_id
            packet = {
                1: {
                    (2 if self.event.is_group else 1): {
                        1: int(target_id)
                    }
                },
                2: {
                    1: 1,
                    2: 0,
                    3: 0
                },
                3: {
                    1: {
                        2: processed_content
                    }
                },
                4: PacketHelper.random_uint(),
                5: PacketHelper.random_uint()
            }
            
            return await self.send_packet('MessageSvc.PbSendMsg', packet)
        except Exception as e:
            logger.error(f"发送元素失败: {str(e)}")
            return None
    
    async def send_long(self, content: Union[dict, str]) -> Optional[dict]:
        try:
            resid = await self.upload_long(content)
            if not resid:
                logger.error("上传长消息失败")
                return None
            
            elem = {
                37: {
                    6: 1,
                    7: resid,
                    17: 0,
                    19: {
                        15: 0,
                        31: 0,
                        41: 0
                    }
                }
            }
            
            return await self.send_elem(elem)
        except Exception as e:
            logger.error(f"发送长消息失败: {str(e)}")
            return None
    
    async def upload_long(self, content: Union[dict, str]) -> Optional[str]:
        try:
            if isinstance(content, str):
                content = json.loads(content)
            
            processed_content = PacketHelper.process_json(content)
            
            data = {
                2: {
                    1: "MultiMsg",
                    2: {
                        1: [{
                            3: {
                                1: {
                                    2: processed_content
                                }
                            }
                        }]
                    }
                }
            }
            
            data_bytes = pb.encode(data)
            compressed_data = gzip.compress(data_bytes)
            
            target_id = int(self.event.group_id if self.event.is_group else self.event.user_id)
            packet = {
                2: {
                    1: 3 if self.event.is_group else 1,
                    2: {
                        2: target_id
                    },
                    3: str(target_id),
                    4: compressed_data
                },
                15: {
                    1: 4,
                    2: 2,
                    3: 9,
                    4: 0
                }
            }
            
            resp = await self.send_packet('trpc.group.long_msg_interface.MsgService.SsoSendLongMsg', packet)
            
            if resp and isinstance(resp, dict):
                resid = resp.get("2", {}).get("3")
                return resid
            
            return None
        except Exception as e:
            logger.error(f"上传长消息失败: {str(e)}")
            return None
    
    async def get_msg(self, message_id: Union[str, int], real_seq: Optional[str] = None) -> Optional[dict]:
        try:
            if not real_seq:
                msg_info = await self.api.get_msg(message_id)
                
                if not msg_info:
                    logger.error("获取消息失败：API 无响应")
                    return None
                
                if isinstance(msg_info, dict):
                    if msg_info.get('retcode') == 0:
                        real_seq = msg_info.get('data', {}).get('real_seq')
                    else:
                        real_seq = msg_info.get('real_seq')
                
                if not real_seq:
                    logger.error("未找到 real_seq")
                    return None
            
            seq = int(real_seq)
            
            packet = {
                1: {
                    1: int(self.event.group_id),
                    2: seq,
                    3: seq
                },
                2: True
            }
            
            return await self.send_packet('trpc.msg.register_proxy.RegisterProxy.SsoGetGroupMsg', packet)
        except Exception as e:
            logger.error(f"获取消息失败: {str(e)}")
            return None


# ==================== Packet 插件 ====================

# 全局变量：消息获取模式（1=平铺模式，2=嵌套模式）
PACKET_MODE = 1

class PacketPlugin(Plugin):
    priority = 1000
    
    @staticmethod
    def get_regex_handlers():
        return {
            r'^(api|API)\s*\{': {'handler': 'handle_api', 'owner_only': True},
            r'^(pb|PB)\s*\{': {'handler': 'handle_pb', 'owner_only': True},
            r'^(pbl|PBL)\s*\{': {'handler': 'handle_pbl', 'owner_only': True},
            r'^(raw|RAW)\s*\{': {'handler': 'handle_raw', 'owner_only': True},
            r'^取\s*(\d+)$': 'handle_get_msg_by_seq',
            r'^取$': 'handle_get_msg',
            r'^取上一条$': 'handle_get_previous_msg',
            r'^模式取1$': 'handle_set_mode_1',
            r'^模式取2$': 'handle_set_mode_2'
        }
    
    @staticmethod
    def handle_set_mode_1(event):
        """设置为模式1：平铺模式（所有消息平铺在一个合并消息中）"""
        global PACKET_MODE
        PACKET_MODE = 1
        event.reply("✅ 已切换到模式1：平铺模式\n所有数据将平铺展示在一个合并消息中")
        return True
    
    @staticmethod
    def handle_set_mode_2(event):
        """设置为模式2：嵌套模式（使用嵌套合并消息）"""
        global PACKET_MODE
        PACKET_MODE = 2
        event.reply("✅ 已切换到模式2：嵌套模式\n数据将使用嵌套合并消息展示")
        return True
    
    @staticmethod
    def handle_api(event):
        try:
            content = event.content
            content = content[3:].strip()  # 去掉 "api" 或 "API"
            
            lines = content.split('\n', 1)
            if len(lines) < 2:
                brace_pos = content.find('{')
                if brace_pos == -1:
                    event.reply("格式错误，请使用: #api <action>\\n<json>")
                    return True
                action = content[:brace_pos].strip()
                params_str = content[brace_pos:]
            else:
                action = lines[0].strip()
                params_str = lines[1].strip()
            
            try:
                params = json.loads(params_str)
            except json.JSONDecodeError as e:
                event.reply(f"JSON 解析失败: {str(e)}")
                return True
            
            result = run_async_api(event.api.call_api(action, **params))
            result_str = json.dumps(result, indent=2, ensure_ascii=False)
            event.reply(f"API 调用结果:\n{result_str}")
            
            return True
        except Exception as e:
            logger.error(f"API 调用失败: {str(e)}")
            event.reply(f"处理失败: {str(e)}")
            return True
    
    @staticmethod
    def handle_pb(event):
        try:
            content = event.content
            content = content[2:].strip()  # 去掉 "pb" 或 "PB"
            
            sender = PacketSender(event)
            result = run_async_api(sender.send_elem(content))
            
            if result:
                event.reply("✅ 发送成功")
            else:
                event.reply("❌ 发送失败")
            
            return True
        except Exception as e:
            logger.error(f"PB 发送失败: {str(e)}")
            event.reply(f"处理失败: {str(e)}")
            return True
    
    @staticmethod
    def handle_pbl(event):
        try:
            content = event.content
            content = content[3:].strip()  # 去掉 "pbl" 或 "PBL"
            
            sender = PacketSender(event)
            result = run_async_api(sender.send_long(content))
            
            if result:
                event.reply("✅ 长消息发送成功")
            else:
                event.reply("❌ 发送失败")
            
            return True
        except Exception as e:
            logger.error(f"PBL 发送失败: {str(e)}")
            event.reply(f"处理失败: {str(e)}")
            return True
    
    @staticmethod
    def handle_raw(event):
        try:
            content = event.content
            content = content[3:].strip()  # 去掉 "raw" 或 "RAW"
            
            lines = content.split('\n', 1)
            if len(lines) < 2:
                brace_pos = content.find('{')
                if brace_pos == -1:
                    event.reply("格式错误，请使用: #raw <cmd>\\n<json>")
                    return True
                cmd = content[:brace_pos].strip()
                packet_str = content[brace_pos:]
            else:
                cmd = lines[0].strip()
                packet_str = lines[1].strip()
            
            sender = PacketSender(event)
            result = run_async_api(sender.send_packet(cmd, packet_str))
            
            if result:
                result_str = PacketHelper.json_dumps_with_bytes(result)
                event.reply(f"✅ 发送成功\n响应:\n{result_str}")
            else:
                event.reply("❌ 发送失败")
            
            return True
        except Exception as e:
            logger.error(f"RAW 发送失败: {str(e)}")
            event.reply(f"处理失败: {str(e)}")
            return True
    
    @staticmethod
    def _extract_sender_info(pb_data):
        """从PB数据中提取发送者信息"""
        try:
            # QQ群消息PB数据结构分析
            # 发送者信息位置：
            # - 3.6.1.1 (发送者QQ)
            # - 3.6.1.8.4 (发送者昵称)

            sender_qq = None
            sender_name = None

            # 从确认的字段位置提取发送者信息
            if isinstance(pb_data, dict):
                # 尝试3.6.1结构（发送者QQ和昵称）
                field3 = pb_data.get(3, {})
                if isinstance(field3, dict):
                    field6 = field3.get(6, {})
                    if isinstance(field6, dict):
                        field1_in_6 = field6.get(1, {})
                        if isinstance(field1_in_6, dict):
                            # 获取发送者QQ (3.6.1.1)
                            sender_qq = field1_in_6.get(1)

                            # 获取发送者昵称 (3.6.1.8.4)
                            field8_in_1_6 = field1_in_6.get(8, {})
                            if isinstance(field8_in_1_6, dict):
                                field4_in_8 = field8_in_1_6.get(4)
                                if field4_in_8 and isinstance(field4_in_8, str):
                                    sender_name = field4_in_8

            # 验证并格式化发送者QQ
            if sender_qq and isinstance(sender_qq, (int, str)):
                sender_qq = str(sender_qq)
                # QQ号通常是数字，且长度合理
                if not (sender_qq.isdigit() and 5 <= len(sender_qq) <= 12):
                    sender_qq = None

            # 如果至少有QQ或昵称之一，则返回结果
            if sender_qq or sender_name:
                return sender_qq, sender_name

            return None, None

        except Exception as e:
            logger.warning(f"解析发送者信息失败: {str(e)}")
            return None, None

    @staticmethod
    def handle_get_previous_msg(event):
        try:
            if not event.is_group:
                event.reply("该功能仅支持群聊")
                return True

            # 确定要获取哪条消息的real_seq
            target_real_seq = None

            # 检查是否是回复消息
            for segment in event.message:
                if isinstance(segment, dict) and segment.get('type') == 'reply':
                    reply_id = segment.get('data', {}).get('id')
                    if reply_id:
                        # 获取被回复消息的real_seq
                        msg_info = run_async_api(event.api.get_msg(reply_id))
                        if msg_info and isinstance(msg_info, dict):
                            if msg_info.get('retcode') == 0:
                                target_real_seq = msg_info.get('data', {}).get('real_seq')
                            else:
                                target_real_seq = msg_info.get('real_seq')
                        break

            # 如果不是回复消息，则获取当前消息的real_seq
            if target_real_seq is None:
                msg_info = run_async_api(event.api.get_msg(event.message_id))
                if msg_info and isinstance(msg_info, dict):
                    if msg_info.get('retcode') == 0:
                        target_real_seq = msg_info.get('data', {}).get('real_seq')
                    else:
                        target_real_seq = msg_info.get('real_seq')

            if not target_real_seq:
                event.reply("❌ 无法获取消息的real_seq")
                return True

            # 计算上一条消息的real_seq
            previous_real_seq = int(target_real_seq) - 1
            logger.info(f"目标消息real_seq: {target_real_seq}, 上一条消息real_seq: {previous_real_seq}")

            # 使用PacketSender获取上一条消息的PB数据
            sender = PacketSender(event)
            pb_data = run_async_api(sender.get_msg(event.message_id, real_seq=str(previous_real_seq)))

            if not pb_data:
                event.reply("❌ 未找到上一条消息")
                return True

            # 尝试从PB数据中提取发送者信息
            sender_qq, sender_name = PacketPlugin._extract_sender_info(pb_data)

            # 构建消息节点列表
            bot_qq = event.self_id
            bot_name = "Bot"
            nodes = []

            # 第一条：消息基本信息
            msg_info_parts = ["📦 消息基本信息", f"Real Seq: {previous_real_seq}"]
            if sender_qq:
                msg_info_parts.append(f"发送者QQ: {sender_qq}")
            if sender_name:
                msg_info_parts.append(f"发送者昵称: {sender_name}")
            
            nodes.append({
                "type": "node",
                "data": {
                    "name": bot_name,
                    "uin": str(bot_qq),
                    "content": '\n'.join(msg_info_parts)
                }
            })

            # 第二条：Body 数据（消息元素）- 单独提取
            body_data = PacketPlugin._extract_body_data(pb_data)
            if body_data:
                body_title = "📦 Body 数据（消息元素）"
                body_content = PacketHelper.json_dumps_with_bytes(body_data)
                nodes.append({
                    "type": "node",
                    "data": {
                        "name": bot_name,
                        "uin": str(bot_qq),
                        "content": body_title
                    }
                })
                nodes.append({
                    "type": "node",
                    "data": {
                        "name": bot_name,
                        "uin": str(bot_qq),
                        "content": body_content
                    }
                })

            # 第三条：ProtoBuf 完整数据
            pb_title = "🔍 ProtoBuf 完整数据"
            pb_content = PacketHelper.json_dumps_with_bytes(pb_data)
            nodes.append({
                "type": "node",
                "data": {
                    "name": bot_name,
                    "uin": str(bot_qq),
                    "content": pb_title
                }
            })
            nodes.append({
                "type": "node",
                "data": {
                    "name": bot_name,
                    "uin": str(bot_qq),
                    "content": pb_content
                }
            })

            # 发送合并转发
            result = run_async_api(event.api.send_group_forward_msg(event.group_id, nodes))

            if not result or result.get('retcode') != 0:
                event.reply("❌ 发送合并转发失败")

            return True

        except Exception as e:
            logger.error(f"获取上一条消息失败: {str(e)}")
            logger.error(traceback.format_exc())
            event.reply(f"获取上一条消息失败: {str(e)}")
            return True

    @staticmethod
    def handle_get_msg_by_seq(event):
        try:
            if not event.is_group:
                event.reply("该功能仅支持群聊")
                return True

            # 从消息中提取 Real Seq
            import re
            match = re.match(r'^取\s*(\d+)$', event.content)
            if not match:
                event.reply("格式错误，请使用: 取 <Real Seq>")
                return True

            target_real_seq = int(match.group(1))
            logger.info(f"用户指定的 Real Seq: {target_real_seq}")

            # 使用PacketSender获取指定Real Seq的消息PB数据
            sender = PacketSender(event)
            pb_data = run_async_api(sender.get_msg(event.message_id, real_seq=str(target_real_seq)))

            if not pb_data:
                event.reply(f"❌ 未找到 Real Seq {target_real_seq} 的消息")
                return True

            # 尝试从PB数据中提取发送者信息
            sender_qq, sender_name = PacketPlugin._extract_sender_info(pb_data)

            # 构建消息内容
            pb_content = "=== ProtoBuf 完整数据 ===\n" + PacketHelper.json_dumps_with_bytes(pb_data)

            # 构建合并转发消息
            bot_qq = event.self_id
            bot_name = "Bot"

            # 构建第一条消息内容
            first_msg_content = f"=== 指定消息 ===\nReal Seq: {target_real_seq}"
            if sender_qq:
                first_msg_content += f"\n发送者QQ: {sender_qq}"
            if sender_name:
                first_msg_content += f"\n发送者昵称: {sender_name}"

            nodes = [
                {
                    "type": "node",
                    "data": {
                        "name": bot_name,
                        "uin": str(bot_qq),
                        "content": first_msg_content
                    }
                },
                {
                    "type": "node",
                    "data": {
                        "name": bot_name,
                        "uin": str(bot_qq),
                        "content": pb_content
                    }
                }
            ]

            # 发送合并转发
            result = run_async_api(event.api.send_group_forward_msg(event.group_id, nodes))

            if not result or result.get('retcode') != 0:
                event.reply("❌ 发送合并转发失败")

            return True

        except Exception as e:
            logger.error(f"获取指定消息失败: {str(e)}")
            logger.error(traceback.format_exc())
            event.reply(f"获取指定消息失败: {str(e)}")
            return True

    @staticmethod
    def _extract_body_data(pb_data):
        """从 ProtoBuf 数据中提取 body 内容（消息元素）"""
        try:
            # QQ消息的body数据通常在 3.6.3.1.2 位置
            # 这是消息元素数组的位置
            if isinstance(pb_data, dict):
                field3 = pb_data.get(3, {})
                if isinstance(field3, dict):
                    field6 = field3.get(6, {})
                    if isinstance(field6, dict):
                        field3_in_6 = field6.get(3, {})
                        if isinstance(field3_in_6, dict):
                            field1_in_3_6 = field3_in_6.get(1, {})
                            if isinstance(field1_in_3_6, dict):
                                # 获取消息元素数组 (3.6.3.1.2)
                                body_elements = field1_in_3_6.get(2)
                                if body_elements:
                                    return body_elements
            return None
        except Exception as e:
            logger.warning(f"提取 body 数据失败: {str(e)}")
            return None

    @staticmethod
    def handle_get_msg(event):
        try:
            if not event.is_group:
                event.reply("该功能仅支持群聊")
                return True
            
            reply_id = None
            for segment in event.message:
                if isinstance(segment, dict) and segment.get('type') == 'reply':
                    reply_id = segment.get('data', {}).get('id')
                    break
            
            if not reply_id:
                event.reply("请回复要获取的消息")
                return True
            
            real_seq = None
            try:
                from function.log_db import get_log_from_db
                db_msg = get_log_from_db('received', message_id=reply_id)
                if db_msg:
                    real_seq = db_msg.get('real_seq')
            except Exception as e:
                logger.warning(f"从数据库获取 real_seq 失败: {str(e)}")
            
            sender = PacketSender(event)
            msg_info = run_async_api(event.api.get_msg(reply_id))
            
            # 使用 logging 输出 OneBot 原始消息数据
            import logging
            logging.info(f"=== OneBot 原始消息数据 ===\n{json.dumps(msg_info, indent=2, ensure_ascii=False)}")
            
            msg_data = {}
            if msg_info:
                if isinstance(msg_info, dict):
                    if msg_info.get('retcode') == 0:
                        msg_data = msg_info.get('data', {})
                        if not real_seq:
                            real_seq = msg_data.get('real_seq')
                    else:
                        msg_data = msg_info
                        if not real_seq:
                            real_seq = msg_info.get('real_seq')
            
            pb_data = None
            if real_seq:
                pb_data = run_async_api(sender.get_msg(reply_id, real_seq=real_seq))
            
            # 获取发送者信息
            sender_info = msg_data.get('sender', {})
            if isinstance(sender_info, dict):
                sender_qq = str(sender_info.get('user_id', event.self_id))
                sender_nickname = sender_info.get('nickname', 'Unknown')
            else:
                sender_qq = str(event.self_id)
                sender_nickname = 'Bot'
            
            # 构建消息节点列表
            bot_qq = event.self_id
            
            # === 节点1: 消息基本信息 ===
            msg_info_parts = ["📦 消息基本信息", f"消息ID: {reply_id}"]
            if real_seq:
                msg_info_parts.append(f"Real Seq: {real_seq}")
            msg_info_parts.append(f"消息类型: {msg_data.get('message_type', 'unknown')}")
            msg_info_parts.append(f"发送者QQ: {sender_qq}")
            msg_info_parts.append(f"发送者昵称: {sender_nickname}")
            
            msg_time = msg_data.get('time', 0)
            if msg_time:
                from datetime import datetime
                time_str = datetime.fromtimestamp(msg_time).strftime('%Y-%m-%d %H:%M:%S')
                msg_info_parts.append(f"发送时间: {time_str}")
            
            raw_message = msg_data.get('raw_message', '')
            if raw_message:
                msg_info_parts.append(f"原始文本: {raw_message}")
            
            node1 = {
                "type": "node",
                "data": {
                    "name": sender_nickname,
                    "uin": sender_qq,
                    "content": '\n'.join(msg_info_parts)
                }
            }
            
            # === 节点2: OneBot 数据（content 是节点数组）===
            message_array = msg_data.get('message', [])
            onebot_sub_nodes = [
                {
                    "type": "node",
                    "data": {
                        "name": sender_nickname,
                        "uin": sender_qq,
                        "content": "=== OneBot 消息数组 ==="
                    }
                },
                {
                    "type": "node",
                    "data": {
                        "name": sender_nickname,
                        "uin": sender_qq,
                        "content": json.dumps(message_array, indent=2, ensure_ascii=False)
                    }
                }
            ]
            
            node2 = {
                "type": "node",
                "data": {
                    "name": "📋 OneBot 数据",
                    "uin": sender_qq,
                    "content": onebot_sub_nodes
                }
            }
            
            # === 节点3: ProtoBuf 数据（content 是节点数组）===
            if pb_data:
                pb_sub_nodes = [
                    {
                        "type": "node",
                        "data": {
                            "name": sender_nickname,
                            "uin": sender_qq,
                            "content": "=== ProtoBuf 完整数据 ==="
                        }
                    },
                    {
                        "type": "node",
                        "data": {
                            "name": sender_nickname,
                            "uin": sender_qq,
                            "content": PacketHelper.json_dumps_with_bytes(pb_data)
                        }
                    }
                ]
                
                node3 = {
                    "type": "node",
                    "data": {
                        "name": "📦 ProtoBuf 数据",
                        "uin": sender_qq,
                        "content": pb_sub_nodes
                    }
                }
                
                # === 节点4: Body 数据（content 是节点数组）===
                body_data = PacketPlugin._extract_body_data(pb_data)
                if body_data:
                    body_sub_nodes = [
                        {
                            "type": "node",
                            "data": {
                                "name": sender_nickname,
                                "uin": sender_qq,
                                "content": "=== Body 数据（消息元素）==="
                            }
                        },
                        {
                            "type": "node",
                            "data": {
                                "name": sender_nickname,
                                "uin": sender_qq,
                                "content": PacketHelper.json_dumps_with_bytes(body_data)
                            }
                        }
                    ]
                    
                    node4 = {
                        "type": "node",
                        "data": {
                            "name": "📦 Body 数据",
                            "uin": sender_qq,
                            "content": body_sub_nodes
                        }
                    }
                    
                    outer_nodes = [node1, node2, node3, node4]
                else:
                    outer_nodes = [node1, node2, node3]
            else:
                node3 = {
                    "type": "node",
                    "data": {
                        "name": "📦 ProtoBuf 数据",
                        "uin": sender_qq,
                        "content": "⚠️ 未找到 real_seq，无法获取 PB 数据"
                    }
                }
                outer_nodes = [node1, node2, node3]
            
            # === 根据模式选择发送方式 ===
            global PACKET_MODE
            logger.info(f"=== 当前模式: 模式{PACKET_MODE} ===")
            
            if PACKET_MODE == 1:
                # 模式1：平铺模式 - 所有节点平铺在一个合并消息中
                logger.info(f"=== 使用模式1：平铺模式 ===")
                flat_nodes = [node1]
                
                # 添加 OneBot 数据节点（平铺）
                flat_nodes.extend(onebot_sub_nodes)
                
                # 添加 ProtoBuf 数据节点（平铺）
                flat_nodes.extend(pb_sub_nodes)
                
                # 添加 Body 数据节点（平铺，如果存在）
                body_data = PacketPlugin._extract_body_data(pb_data)
                if body_data:
                    flat_nodes.append({
                        "type": "node",
                        "data": {
                            "name": sender_nickname,
                            "uin": sender_qq,
                            "content": "=== Body 数据（消息元素）==="
                        }
                    })
                    flat_nodes.append({
                        "type": "node",
                        "data": {
                            "name": sender_nickname,
                            "uin": sender_qq,
                            "content": PacketHelper.json_dumps_with_bytes(body_data)
                        }
                    })
                
                final_nodes = flat_nodes
            else:
                # 模式2：嵌套模式 - 使用嵌套节点数组
                logger.info(f"=== 使用模式2：嵌套模式 ===")
                final_nodes = [
                    node1,  # 节点1：消息基本信息（文本）
                    {
                        "type": "node",
                        "data": {
                            "name": "📋 OneBot 数据",
                            "uin": sender_qq,
                            "content": onebot_sub_nodes  # 直接使用节点数组
                        }
                    },
                    {
                        "type": "node",
                        "data": {
                            "name": "📦 ProtoBuf 数据",
                            "uin": sender_qq,
                            "content": pb_sub_nodes  # 直接使用节点数组
                        }
                    }
                ]
                
                # 如果有 Body 数据，添加节点4
                body_data = PacketPlugin._extract_body_data(pb_data)
                if body_data:
                    body_sub_nodes = [
                        {
                            "type": "node",
                            "data": {
                                "name": sender_nickname,
                                "uin": sender_qq,
                                "content": "=== Body 数据（消息元素）==="
                            }
                        },
                        {
                            "type": "node",
                            "data": {
                                "name": sender_nickname,
                                "uin": sender_qq,
                                "content": PacketHelper.json_dumps_with_bytes(body_data)
                            }
                        }
                    ]
                    
                    final_nodes.append({
                        "type": "node",
                        "data": {
                            "name": "📦 Body 数据",
                            "uin": sender_qq,
                            "content": body_sub_nodes  # 直接使用节点数组
                        }
                    })
            
            # === 发送最终合并消息到群 ===
            logger.info(f"=== 发送最终合并消息到群 ===")
            logger.info(f"最终合并消息构造:\n{json.dumps(final_nodes, indent=2, ensure_ascii=False, default=str)}")
            
            final_result = run_async_api(event.api.send_group_forward_msg(event.group_id, final_nodes))
            logger.info(f"最终发送结果:\n{json.dumps(final_result, indent=2, ensure_ascii=False)}")
            
            if not final_result or (isinstance(final_result, dict) and final_result.get('retcode') != 0):
                event.reply("❌ 发送最终合并消息到群失败")
            
            return True
        except Exception as e:
            logger.error(f"获取消息失败: {str(e)}")
            logger.error(traceback.format_exc())
            event.reply(f"获取消息失败: {str(e)}")
            return True

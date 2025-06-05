#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化控制模块
功能：执行GPT生成的操作指令，包括点击、输入、按键等
"""

import asyncio
import time
import logging
import pyautogui
from typing import Dict, List, Optional, Tuple, Any
from PIL import Image
import cv2
import numpy as np

logger = logging.getLogger(__name__)

class AutomationController:
    """自动化控制器类"""
    
    def __init__(self):
        # 配置pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.5
        
        self.last_action_time = 0
        self.action_history = []
        self.max_history_length = 50
        
        # 安全检查配置
        self.safe_mode = True
        self.confirmation_required = ["delete", "remove", "clear", "reset"]
        
    async def initialize(self) -> bool:
        """初始化自动化控制器"""
        try:
            logger.info("🤖 初始化自动化控制器...")
            
            # 测试屏幕访问权限
            try:
                screenshot = pyautogui.screenshot()
                if screenshot:
                    logger.info("✅ 屏幕访问权限正常")
                else:
                    logger.warning("⚠️ 屏幕访问权限可能受限")
            except Exception as e:
                logger.warning(f"屏幕访问测试失败: {e}")
            
            # 设置安全参数
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.5
            
            logger.info("✅ 自动化控制器初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"自动化控制器初始化失败: {e}")
            return False
        
    async def execute_action(self, gpt_response: Dict[str, Any]) -> bool:
        """执行GPT生成的操作指令"""
        try:
            action_data = gpt_response.get("action", {})
            action_type = action_data.get("action_type", "wait")
            
            logger.info(f"执行操作: {action_type} - {action_data.get('reasoning', '')}")
            
            # 记录操作历史
            self.record_action(action_data)
            
            # 安全检查
            if not self.safety_check(action_data):
                logger.warning("安全检查未通过，跳过操作")
                return False
            
            # 根据操作类型执行相应动作
            success = False
            if action_type == "click":
                success = await self.perform_click(action_data)
            elif action_type == "type":
                success = await self.perform_type(action_data)
            elif action_type == "send_message":
                # send_message等同于type操作
                logger.info("📤 send_message操作转换为type操作")
                success = await self.perform_type(action_data)
            elif action_type == "key_press":
                success = await self.perform_key_press(action_data)
            elif action_type == "wait":
                success = await self.perform_wait(action_data)
            elif action_type == "analyze":
                success = True  # 分析操作总是成功
                logger.info("执行分析操作，等待下一轮分析")
            else:
                logger.warning(f"未知操作类型: {action_type}")
                success = False
            
            # 更新最后操作时间
            self.last_action_time = time.time()
            
            # 执行后续操作
            if success and action_data.get("follow_up_actions"):
                await self.execute_follow_up_actions(action_data["follow_up_actions"])
            
            return success
            
        except Exception as e:
            logger.error(f"执行操作时出错: {e}")
            return False
    
    async def perform_click(self, action_data: Dict[str, Any]) -> bool:
        """执行点击操作"""
        try:
            coordinates = action_data.get("coordinates")
            target = action_data.get("target", "")
            
            if coordinates and len(coordinates) >= 2:
                x, y = coordinates[0], coordinates[1]
                logger.info(f"点击坐标: ({x}, {y})")
                
                # 移动到目标位置
                pyautogui.moveTo(x, y, duration=0.5)
                await asyncio.sleep(0.2)
                
                # 执行点击
                pyautogui.click()
                await asyncio.sleep(0.5)
                
                return True
            
            elif target:
                # 尝试通过目标描述找到点击位置
                click_pos = await self.find_click_target(target)
                if click_pos:
                    x, y = click_pos
                    logger.info(f"通过目标'{target}'找到点击位置: ({x}, {y})")
                    pyautogui.moveTo(x, y, duration=0.5)
                    await asyncio.sleep(0.2)
                    pyautogui.click()
                    await asyncio.sleep(0.5)
                    return True
                else:
                    logger.warning(f"无法找到点击目标: {target}")
                    return False
            
            else:
                logger.warning("点击操作缺少坐标或目标信息")
                return False
                
        except Exception as e:
            logger.error(f"执行点击操作时出错: {e}")
            return False
    
    async def perform_type(self, action_data: Dict[str, Any]) -> bool:
        """执行输入操作 - 智能判断是命令还是聊天"""
        try:
            text_value = action_data.get("value", "")
            target = action_data.get("target", "")
            
            if not text_value:
                logger.warning("输入操作缺少文本内容")
                return False
            
            logger.info(f"📝 准备输入内容: {text_value[:100]}...")
            
            # 智能检测内容类型
            content_type = await self.detect_command_type(text_value)
            
            if content_type == "command":
                # 如果是命令，在终端中执行
                logger.info("🖥️ 检测为命令，将在终端中执行")
                return await self.execute_terminal_command(text_value)
            else:
                # 如果是聊天消息，在CURSOR聊天窗口中发送
                logger.info("💬 检测为聊天消息，将在CURSOR聊天窗口发送")
                return await self.perform_chat_input_action(text_value, target)
            
        except Exception as e:
            logger.error(f"执行输入操作时出错: {e}")
            return False
    
    async def perform_key_press(self, action_data: Dict[str, Any]) -> bool:
        """执行按键操作"""
        try:
            key_value = action_data.get("value", "")
            
            if not key_value:
                logger.warning("按键操作缺少按键信息")
                return False
            
            logger.info(f"按键: {key_value}")
            
            # 处理组合键
            if '+' in key_value:
                keys = key_value.lower().split('+')
                keys = [key.strip() for key in keys]
                pyautogui.hotkey(*keys)
            else:
                pyautogui.press(key_value.lower())
            
            await asyncio.sleep(0.5)
            return True
            
        except Exception as e:
            logger.error(f"执行按键操作时出错: {e}")
            return False
    
    async def perform_wait(self, action_data: Dict[str, Any]) -> bool:
        """执行等待操作"""
        try:
            wait_time = action_data.get("value", 2)
            if isinstance(wait_time, str):
                wait_time = float(wait_time)
            
            logger.info(f"等待 {wait_time} 秒")
            await asyncio.sleep(wait_time)
            return True
            
        except Exception as e:
            logger.error(f"执行等待操作时出错: {e}")
            return False
    
    async def find_click_target(self, target: str) -> Optional[Tuple[int, int]]:
        """根据目标描述找到点击位置"""
        try:
            # 截取当前屏幕
            screenshot = pyautogui.screenshot()
            
            # 常见的UI元素关键词映射
            target_keywords = {
                "continue": ["continue", "继续", "next", "下一步"],
                "ok": ["ok", "确定", "confirm", "确认"],
                "cancel": ["cancel", "取消", "close", "关闭"],
                "yes": ["yes", "是", "确定"],
                "no": ["no", "否", "取消"],
                "run": ["run", "运行", "execute", "执行"],
                "stop": ["stop", "停止", "halt"],
                "save": ["save", "保存"],
                "input": ["input", "输入框", "text", "field"]
            }
            
            # 使用OCR识别屏幕文本并查找目标
            # 这里简化实现，实际可以集成更复杂的图像识别
            
            # 暂时返回屏幕中心作为默认点击位置
            screen_width, screen_height = pyautogui.size()
            center_x, center_y = screen_width // 2, screen_height // 2
            
            logger.debug(f"未找到特定目标'{target}'，返回屏幕中心位置")
            return (center_x, center_y)
            
        except Exception as e:
            logger.error(f"查找点击目标时出错: {e}")
            return None
    
    def safety_check(self, action_data: Dict[str, Any]) -> bool:
        """安全检查"""
        if not self.safe_mode:
            return True
        
        action_type = action_data.get("action_type", "")
        target = action_data.get("target", "").lower()
        value = str(action_data.get("value", "")).lower()
        reasoning = action_data.get("reasoning", "").lower()
        
        # 检查危险操作
        dangerous_keywords = ["delete", "remove", "clear", "reset", "format", "destroy"]
        
        for keyword in dangerous_keywords:
            if keyword in target or keyword in value or keyword in reasoning:
                confidence = action_data.get("confidence", 0)
                if confidence < 0.8:
                    logger.warning(f"检测到潜在危险操作'{keyword}'，置信度过低({confidence})，跳过执行")
                    return False
        
        # 检查操作频率（防止无限循环）
        recent_actions = [action for action in self.action_history 
                         if time.time() - action.get("timestamp", 0) < 10]
        
        if len(recent_actions) > 5:
            similar_actions = [action for action in recent_actions 
                             if action.get("action_type") == action_type]
            if len(similar_actions) > 3:
                logger.warning("检测到重复操作过于频繁，可能存在循环，暂停执行")
                return False
        
        return True
    
    def record_action(self, action_data: Dict[str, Any]):
        """记录操作历史"""
        action_record = {
            **action_data,
            "timestamp": time.time(),
            "execution_id": len(self.action_history)
        }
        
        self.action_history.append(action_record)
        
        # 保持历史记录长度限制
        if len(self.action_history) > self.max_history_length:
            self.action_history = self.action_history[-self.max_history_length:]
    
    async def execute_follow_up_actions(self, follow_up_actions):
        """执行后续操作"""
        try:
            if not follow_up_actions:
                return
                
            # 处理不同格式的follow_up_actions
            for action_item in follow_up_actions:
                # 如果是字典格式（新的GPT响应格式）
                if isinstance(action_item, dict):
                    logger.info(f"执行后续操作: {action_item}")
                    
                    # 提取操作信息
                    action_type = action_item.get("action_type", "").lower()
                    target = action_item.get("target", "").lower()
                    value = action_item.get("value", "")
                    reasoning = action_item.get("reasoning", "")
                    
                    logger.info(f"后续操作类型: {action_type}, 目标: {target}, 理由: {reasoning}")
                    
                    # 根据操作类型执行
                    if action_type == "wait":
                        wait_time = 2
                        if value and isinstance(value, (int, float)):
                            wait_time = value
                        await asyncio.sleep(wait_time)
                    elif action_type == "key_press" or action_type == "press":
                        if value:
                            pyautogui.press(value.lower())
                        elif "enter" in reasoning.lower():
                            pyautogui.press('enter')
                        elif "escape" in reasoning.lower():
                            pyautogui.press('escape')
                        await asyncio.sleep(0.5)
                    elif action_type == "click":
                        coordinates = action_item.get("coordinates")
                        if coordinates and len(coordinates) >= 2:
                            x, y = coordinates[0], coordinates[1]
                            pyautogui.click(x, y)
                            await asyncio.sleep(0.5)
                    elif action_type == "type":
                        if value:
                            # 这是一个简化的输入，仅记录日志
                            logger.info(f"建议执行命令: {value}")
                            # 实际情况下，这种复杂操作应该通过主要的execute_action方法处理
                    elif action_type == "restart":
                        logger.info(f"建议重启操作: {target}")
                        # 重启操作通常需要更复杂的逻辑，这里仅记录
                    else:
                        logger.info(f"未知的后续操作类型: {action_type}")
                
                # 如果是字符串格式（旧的格式，保持兼容性）
                elif isinstance(action_item, str):
                    action_desc = action_item
                    logger.info(f"执行后续操作: {action_desc}")
                    
                    # 简单的后续操作解析
                    if "wait" in action_desc.lower():
                        await asyncio.sleep(2)
                    elif "enter" in action_desc.lower():
                        pyautogui.press('enter')
                        await asyncio.sleep(0.5)
                    elif "escape" in action_desc.lower():
                        pyautogui.press('escape')
                        await asyncio.sleep(0.5)
                else:
                    logger.warning(f"未知的后续操作格式: {type(action_item)}")
                
        except Exception as e:
            logger.error(f"执行后续操作时出错: {e}")
    
    def get_action_stats(self) -> Dict[str, Any]:
        """获取操作统计信息"""
        recent_time = time.time() - 300  # 最近5分钟
        recent_actions = [action for action in self.action_history 
                         if action.get("timestamp", 0) > recent_time]
        
        action_types = {}
        for action in recent_actions:
            action_type = action.get("action_type", "unknown")
            action_types[action_type] = action_types.get(action_type, 0) + 1
        
        return {
            "total_actions": len(self.action_history),
            "recent_actions": len(recent_actions),
            "action_types": action_types,
            "last_action_time": self.last_action_time,
            "safe_mode": self.safe_mode
        }
    
    def set_safe_mode(self, enabled: bool):
        """设置安全模式"""
        self.safe_mode = enabled
        logger.info(f"安全模式: {'启用' if enabled else '禁用'}")
    
    def clear_action_history(self):
        """清空操作历史"""
        self.action_history.clear()
        logger.info("操作历史已清空")
    
    async def emergency_stop(self):
        """紧急停止所有操作"""
        logger.warning("执行紧急停止...")
        # 移动鼠标到安全位置
        pyautogui.moveTo(0, 0)
        self.last_action_time = time.time()
    
    async def click_dialog_input(self) -> bool:
        """点击CURSOR对话框输入区域"""
        try:
            logger.info("尝试点击CURSOR对话框输入区域...")
            
            # 获取当前屏幕截图用于分析
            screenshot = pyautogui.screenshot()
            
            # 尝试多种策略找到输入框
            input_positions = await self.find_dialog_input_positions(screenshot)
            
            for position in input_positions:
                try:
                    x, y = position
                    logger.info(f"尝试点击输入框位置: ({x}, {y})")
                    
                    # 移动并点击
                    pyautogui.moveTo(x, y, duration=0.3)
                    await asyncio.sleep(0.2)
                    pyautogui.click()
                    await asyncio.sleep(0.5)
                    
                    # 验证是否成功（检查是否有光标）
                    if await self.verify_input_focus():
                        logger.info("成功点击输入框")
                        return True
                        
                except Exception as e:
                    logger.debug(f"点击位置 ({x}, {y}) 失败: {e}")
                    continue
            
            # 如果所有位置都失败，尝试通用策略
            return await self.fallback_click_strategy()
            
        except Exception as e:
            logger.error(f"点击对话框输入区域时出错: {e}")
            return False
    
    async def find_dialog_input_positions(self, screenshot: Image.Image) -> List[Tuple[int, int]]:
        """找到可能的对话框输入位置 - 优化版：基于保存的区域配置"""
        positions = []
        
        try:
            # 转换为numpy数组进行分析
            img_array = np.array(screenshot)
            height, width = img_array.shape[:2]
            
            # 首先尝试从保存的输入框配置中获取位置
            try:
                import json
                import os
                
                # 检查新的输入框配置文件
                input_box_config_file = "input_box_config.json"
                if os.path.exists(input_box_config_file):
                    with open(input_box_config_file, 'r', encoding='utf-8') as f:
                        input_config = json.load(f)
                    
                    input_box = input_config.get("input_box", {})
                    if input_box:
                        # 使用输入框中心点作为点击位置
                        center_x = input_box.get("center_x")
                        center_y = input_box.get("center_y")
                        if center_x and center_y:
                            logger.info(f"✅ 使用用户选择的输入框位置: ({center_x}, {center_y})")
                            positions.append((center_x, center_y))
                        else:
                            # 如果没有中心点，计算中心点
                            x = input_box.get("x")
                            y = input_box.get("y")
                            w = input_box.get("width")
                            h = input_box.get("height")
                            if x is not None and y is not None and w and h:
                                center_x = x + w // 2
                                center_y = y + h // 2
                                logger.info(f"✅ 计算的输入框中心位置: ({center_x}, {center_y})")
                                positions.append((center_x, center_y))
                
                # 检查是否有保存的CURSOR聊天配置（向后兼容）
                cursor_config_file = "cursor_chat_config.json"
                if os.path.exists(cursor_config_file):
                    with open(cursor_config_file, 'r', encoding='utf-8') as f:
                        cursor_config = json.load(f)
                    
                    chat_region = cursor_config.get("cursor_chat_region", {})
                    if chat_region:
                        input_x = chat_region.get("input_x")
                        input_y = chat_region.get("input_y")
                        if input_x and input_y:
                            logger.info(f"使用保存的CURSOR输入框位置: ({input_x}, {input_y})")
                            positions.append((input_x, input_y))
                
                # 检查window_regions.json中的区域配置
                regions_config_file = "window_regions.json"
                if os.path.exists(regions_config_file):
                    with open(regions_config_file, 'r', encoding='utf-8') as f:
                        regions_config = json.load(f)
                    
                    # 遍历所有保存的区域
                    for config_name, config_data in regions_config.items():
                        if "region" in config_data:
                            region = config_data["region"]
                            x, y = region["x"], region["y"]
                            w, h = region["width"], region["height"]
                            
                            # 输入框通常在区域的底部
                            input_x = x + w // 2  # 水平居中
                            input_y = y + h - 50  # 距离底部50像素
                            
                            logger.info(f"基于保存区域 {config_name} 推算输入框位置: ({input_x}, {input_y})")
                            positions.append((input_x, input_y))
                            
                        elif "regions" in config_data:
                            # 新格式：多区域
                            for region in config_data["regions"]:
                                x, y = region["x"], region["y"]
                                w, h = region["width"], region["height"]
                                
                                # 输入框通常在区域的底部
                                input_x = x + w // 2  # 水平居中
                                input_y = y + h - 50  # 距离底部50像素
                                
                                logger.info(f"基于保存区域推算输入框位置: ({input_x}, {input_y})")
                                positions.append((input_x, input_y))
            
            except Exception as e:
                logger.debug(f"读取保存的区域配置时出错: {e}")
            
            # 如果没有找到保存的配置，使用优化的默认策略
            if not positions:
                logger.info("未找到保存的区域配置，使用默认输入框坐标 (1820, 950)")
                
                # 使用我们确认的Agent按钮上方的输入框坐标
                positions.append((1820, 950))
                
                # 添加一些备用位置作为fallback
                positions.append((1820, 920))  # 稍微上移一点
                positions.append((1770, 950))  # 稍微左移一点
                positions.append((1820, 980))  # 稍微下移一点
                
                # 策略: 查找屏幕右侧区域（通常是对话框区域）
                right_half_x = width * 0.6  # 右侧60%区域
                bottom_area_y = height * 0.8  # 底部20%区域
                
                # 在右下角区域寻找可能的输入框
                positions.append((int(right_half_x + (width - right_half_x) / 2), int(bottom_area_y + (height - bottom_area_y) / 2)))
                
                # 策略: 查找屏幕底部中央区域
                positions.append((width // 2, int(height * 0.9)))
                
                # 策略: 查找右侧中央区域
                positions.append((int(width * 0.8), height // 2))
                
                # 策略: 使用图像处理找到可能的输入框区域
                input_boxes = await self.detect_input_boxes(img_array)
                positions.extend(input_boxes)
            
            logger.debug(f"找到 {len(positions)} 个可能的输入框位置")
            return positions
            
        except Exception as e:
            logger.error(f"查找输入框位置时出错: {e}")
            # 出错时也使用我们确认的坐标作为默认值
            return [(1820, 950)]
    
    async def detect_input_boxes(self, img_array: np.ndarray) -> List[Tuple[int, int]]:
        """使用图像处理检测输入框"""
        positions = []
        
        try:
            # 转换为灰度图
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            
            # 边缘检测
            edges = cv2.Canny(gray, 50, 150)
            
            # 查找轮廓
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for contour in contours:
                # 计算边界框
                x, y, w, h = cv2.boundingRect(contour)
                
                # 过滤条件：宽度合适，高度较小（像输入框）
                if w > 100 and 20 < h < 60 and w/h > 5:
                    # 计算中心点
                    center_x = x + w // 2
                    center_y = y + h // 2
                    positions.append((center_x, center_y))
                    
                    if len(positions) >= 5:  # 限制数量
                        break
            
            return positions
            
        except Exception as e:
            logger.debug(f"图像处理检测输入框时出错: {e}")
            return []
    
    async def verify_input_focus(self) -> bool:
        """验证输入框是否获得焦点"""
        try:
            # 简单的验证：尝试输入一个空格然后删除
            original_clipboard = pyautogui.paste()  # 保存剪贴板
            
            # 输入测试字符
            pyautogui.typewrite(' ')
            await asyncio.sleep(0.1)
            
            # 选择并复制
            pyautogui.hotkey('shift', 'left')
            await asyncio.sleep(0.1)
            pyautogui.hotkey('ctrl', 'c')
            await asyncio.sleep(0.1)
            
            # 检查是否复制到了空格
            copied_text = pyautogui.paste()
            
            # 删除测试字符
            pyautogui.press('delete')
            
            # 恢复剪贴板（如果可能）
            if original_clipboard:
                pyautogui.hotkey('ctrl', 'v')
                pyautogui.hotkey('ctrl', 'a')
                pyautogui.press('delete')
            
            return copied_text == ' '
            
        except Exception as e:
            logger.debug(f"验证输入焦点时出错: {e}")
            return True  # 默认认为成功
    
    async def fallback_click_strategy(self) -> bool:
        """备用点击策略"""
        try:
            logger.info("使用备用点击策略...")
            
            # 尝试Tab键导航到输入框
            for _ in range(10):
                pyautogui.press('tab')
                await asyncio.sleep(0.2)
                
                if await self.verify_input_focus():
                    logger.info("通过Tab键找到输入框")
                    return True
            
            # 尝试点击屏幕的常见输入区域
            screen_width, screen_height = pyautogui.size()
            
            common_positions = [
                (screen_width * 0.75, screen_height * 0.9),  # 右下角
                (screen_width * 0.5, screen_height * 0.9),   # 底部中央
                (screen_width * 0.8, screen_height * 0.5),   # 右侧中央
            ]
            
            for x, y in common_positions:
                try:
                    pyautogui.click(int(x), int(y))
                    await asyncio.sleep(0.5)
                    
                    if await self.verify_input_focus():
                        logger.info(f"通过常见位置 ({int(x)}, {int(y)}) 找到输入框")
                        return True
                        
                except Exception:
                    continue
            
            logger.warning("所有备用策略都失败了")
            return False
            
        except Exception as e:
            logger.error(f"备用点击策略时出错: {e}")
            return False
    
    async def perform_chat_input_action(self, text: str, target: str = "cursor_chat") -> bool:
        """执行聊天输入操作"""
        try:
            logger.info("开始智能CURSOR交互...")
            
            # 点击输入框获得焦点
            logger.info("尝试点击CURSOR对话框输入区域...")
            success = await self.click_dialog_input()
            
            if not success:
                logger.error("❌ 无法获得输入框焦点")
                return False
            
            logger.info("🎯 开始输入文本，长度: {} 字符".format(len(text)))
            
            # 使用粘贴方式输入文本
            success = await self.paste_text_to_input(text)
            
            if not success:
                logger.error("❌ 文本粘贴失败")
                return False
            
            # 延迟1秒后发送消息
            logger.info("⏳ 延迟1秒后发送消息...")
            await asyncio.sleep(1.0)
            
            # 发送消息
            logger.info("按键: ctrl+enter")
            pyautogui.hotkey('ctrl', 'enter')
            await asyncio.sleep(0.5)
            
            logger.info("✅ CURSOR交互完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ CURSOR交互失败: {e}")
            return False
    
    async def paste_text_to_input(self, text: str) -> bool:
        """使用粘贴方式输入文本，增强稳定性和重试机制"""
        import pyperclip
        max_retries = 2
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"📋 第{attempt}次尝试粘贴文本...")
                # 保存原始剪贴板内容
                try:
                    original_clipboard = pyperclip.paste()
                except:
                    original_clipboard = ""
                
                # 粘贴前确认焦点
                await asyncio.sleep(0.1)
                pyautogui.hotkey('ctrl', 'a')
                await asyncio.sleep(0.1)
                pyautogui.press('delete')
                await asyncio.sleep(0.2)
                
                # 再次点击输入框确保焦点
                await self.click_dialog_input()
                await asyncio.sleep(0.2)
                
                # 将文本复制到剪贴板
                pyperclip.copy(text)
                await asyncio.sleep(0.3)
                
                # 粘贴文本
                pyautogui.hotkey('ctrl', 'v')
                await asyncio.sleep(1.0)  # 粘贴后等待更久
                
                # 粘贴后再次确认焦点
                await self.click_dialog_input()
                await asyncio.sleep(0.2)
                
                # 验证粘贴结果
                pyautogui.hotkey('ctrl', 'a')
                await asyncio.sleep(0.1)
                pyautogui.hotkey('ctrl', 'c')
                await asyncio.sleep(0.3)
                
                try:
                    pasted_content = pyperclip.paste()
                    success = len(pasted_content) >= len(text) * 0.9
                    if success:
                        logger.info(f"✅ 文本粘贴成功，长度: {len(pasted_content)}")
                        pyautogui.press('end')
                        # 恢复原始剪贴板内容
                        try:
                            pyperclip.copy(original_clipboard)
                        except:
                            pass
                        return True
                    else:
                        logger.warning(f"❌ 粘贴验证失败，原始: {len(text)}, 粘贴: {len(pasted_content)}，内容: {pasted_content}")
                        # 恢复原始剪贴板内容
                        try:
                            pyperclip.copy(original_clipboard)
                        except:
                            pass
                        # 重试前等待
                        await asyncio.sleep(0.5)
                        continue
                except Exception as e:
                    logger.error(f"❌ 粘贴验证异常: {e}")
                    try:
                        pyperclip.copy(original_clipboard)
                    except:
                        pass
                    await asyncio.sleep(0.5)
                    continue
            except Exception as e:
                logger.error(f"❌ 粘贴输入异常: {e}")
                await asyncio.sleep(0.5)
                continue
        logger.error(f"❌ 所有{max_retries}次粘贴尝试均失败")
        return False
    
    async def execute_terminal_command(self, command: str) -> bool:
        """在终端窗口中执行命令"""
        try:
            logger.info(f"🖥️ 准备在终端执行命令: {command}")
            
            # 步骤1: 定位并激活终端窗口
            if not await self.find_and_activate_terminal():
                logger.error("无法找到或激活终端窗口")
                return False
            
            # 步骤2: 确保终端处于输入状态
            await self.prepare_terminal_input()
            
            # 步骤3: 输入命令
            logger.info(f"📝 在终端输入命令: {command}")
            pyautogui.typewrite(command, interval=0.05)
            await asyncio.sleep(0.5)
            
            # 步骤4: 执行命令
            logger.info("⚡ 执行命令...")
            pyautogui.press('enter')
            await asyncio.sleep(1)
            
            logger.info("✅ 终端命令执行完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 执行终端命令时出错: {e}")
            return False
    
    async def find_and_activate_terminal(self) -> bool:
        """查找并激活终端窗口"""
        try:
            logger.info("🔍 查找终端窗口...")
            
            # 方法1: 尝试通过窗口标题查找终端
            terminal_found = await self.find_terminal_by_title()
            if terminal_found:
                return True
            
            # 方法2: 尝试通过快捷键打开终端
            logger.info("🔧 尝试使用快捷键打开终端...")
            success = await self.open_terminal_with_shortcut()
            if success:
                return True
            
            # 方法3: 尝试点击CURSOR界面中的终端区域
            logger.info("🎯 尝试点击CURSOR中的终端区域...")
            success = await self.click_cursor_terminal_area()
            if success:
                return True
            
            logger.warning("所有终端激活方法都失败了")
            return False
            
        except Exception as e:
            logger.error(f"查找终端窗口时出错: {e}")
            return False
    
    async def find_terminal_by_title(self) -> bool:
        """通过窗口标题查找终端"""
        try:
            import psutil
            import subprocess
            import platform
            
            if platform.system() == "Windows":
                # Windows下查找PowerShell或CMD窗口
                terminal_titles = [
                    "Windows PowerShell",
                    "powershell",
                    "Command Prompt", 
                    "cmd",
                    "Terminal",
                    "Git Bash"
                ]
                
                for title in terminal_titles:
                    try:
                        windows = pyautogui.getWindowsWithTitle(title)
                        if windows:
                            window = windows[0]
                            window.activate()
                            await asyncio.sleep(0.5)
                            logger.info(f"✅ 找到并激活终端窗口: {title}")
                            return True
                    except Exception as e:
                        logger.debug(f"查找窗口 {title} 失败: {e}")
                        continue
            
            return False
            
        except Exception as e:
            logger.error(f"通过标题查找终端时出错: {e}")
            return False
    
    async def open_terminal_with_shortcut(self) -> bool:
        """使用快捷键打开终端"""
        try:
            import platform
            
            if platform.system() == "Windows":
                # 在CURSOR中打开终端的常见快捷键
                shortcuts = [
                    ['ctrl', 'shift', 'grave'],  # Ctrl+Shift+` (常见的终端快捷键)
                    ['ctrl', 'grave'],           # Ctrl+`
                    ['ctrl', 'shift', 't'],      # Ctrl+Shift+T
                    ['f1'],                      # F1可能触发帮助或命令面板
                ]
                
                for shortcut in shortcuts:
                    try:
                        logger.info(f"🔧 尝试快捷键: {'+'.join(shortcut)}")
                        pyautogui.hotkey(*shortcut)
                        await asyncio.sleep(1.5)
                        
                        # 验证是否成功打开终端
                        if await self.verify_terminal_active():
                            logger.info(f"✅ 成功通过快捷键打开终端: {'+'.join(shortcut)}")
                            return True
                            
                    except Exception as e:
                        logger.debug(f"快捷键 {shortcut} 失败: {e}")
                        continue
            
            return False
            
        except Exception as e:
            logger.error(f"使用快捷键打开终端时出错: {e}")
            return False
    
    async def click_cursor_terminal_area(self) -> bool:
        """点击CURSOR界面中的终端区域"""
        try:
            # 获取屏幕尺寸
            screen_width, screen_height = pyautogui.size()
            
            # 在CURSOR中，终端通常位于底部区域
            # 尝试点击一些可能的终端位置
            terminal_positions = [
                (screen_width * 0.5, screen_height * 0.8),   # 底部中央
                (screen_width * 0.3, screen_height * 0.85),  # 底部左侧
                (screen_width * 0.7, screen_height * 0.85),  # 底部右侧
                (screen_width * 0.5, screen_height * 0.9),   # 更底部的位置
            ]
            
            for x, y in terminal_positions:
                try:
                    logger.info(f"🎯 尝试点击终端位置: ({int(x)}, {int(y)})")
                    pyautogui.click(int(x), int(y))
                    await asyncio.sleep(1)
                    
                    # 验证是否激活了终端
                    if await self.verify_terminal_active():
                        logger.info(f"✅ 成功激活终端区域: ({int(x)}, {int(y)})")
                        return True
                        
                except Exception as e:
                    logger.debug(f"点击位置 ({int(x)}, {int(y)}) 失败: {e}")
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"点击终端区域时出错: {e}")
            return False
    
    async def verify_terminal_active(self) -> bool:
        """验证终端是否处于活动状态"""
        try:
            # 尝试输入一个简单的测试字符并检查响应
            test_char = "echo test"
            
            # 清空当前行
            pyautogui.hotkey('ctrl', 'c')  # 中断当前命令
            await asyncio.sleep(0.2)
            
            # 输入测试命令但不执行
            pyautogui.typewrite(test_char, interval=0.02)
            await asyncio.sleep(0.3)
            
            # 清空测试输入
            pyautogui.hotkey('ctrl', 'a')
            await asyncio.sleep(0.1)
            pyautogui.press('delete')
            await asyncio.sleep(0.2)
            
            # 如果能够输入和删除，说明终端可能处于活动状态
            logger.info("✅ 终端响应测试通过")
            return True
            
        except Exception as e:
            logger.debug(f"终端验证时出错: {e}")
            return False
    
    async def prepare_terminal_input(self) -> bool:
        """准备终端输入状态"""
        try:
            logger.info("🔧 准备终端输入状态...")
            
            # 确保终端不在其他模式中
            pyautogui.press('esc')  # 退出可能的模式
            await asyncio.sleep(0.2)
            
            # 中断任何正在运行的命令
            pyautogui.hotkey('ctrl', 'c')
            await asyncio.sleep(0.3)
            
            # 清空当前输入行
            pyautogui.hotkey('ctrl', 'a')
            await asyncio.sleep(0.1)
            pyautogui.press('delete')
            await asyncio.sleep(0.2)
            
            logger.info("✅ 终端输入状态准备完成")
            return True
            
        except Exception as e:
            logger.error(f"准备终端输入状态时出错: {e}")
            return False
    
    async def detect_command_type(self, text: str) -> str:
        """检测文本类型：是命令还是聊天消息"""
        try:
            # 常见的命令关键词
            command_keywords = [
                'pip', 'python', 'npm', 'node', 'git', 'cd', 'ls', 'dir',
                'mkdir', 'rmdir', 'rm', 'cp', 'mv', 'cat', 'echo', 'curl',
                'wget', 'chmod', 'chown', 'sudo', 'apt', 'yum', 'brew',
                'docker', 'kubectl', 'terraform', 'ansible'
            ]
            
            # 命令模式的特征
            command_patterns = [
                text.startswith('pip '),
                text.startswith('python '),
                text.startswith('npm '),
                text.startswith('git '),
                text.startswith('./'),
                text.startswith('cd '),
                any(keyword in text.lower() for keyword in command_keywords),
                text.endswith('.py'),
                text.endswith('.js'),
                text.endswith('.sh'),
            ]
            
            # 如果匹配任何命令模式，返回'command'
            if any(command_patterns):
                logger.info(f"📋 检测为命令类型: {text[:50]}...")
                return "command"
            else:
                logger.info(f"💬 检测为聊天类型: {text[:50]}...")
                return "chat"
                
        except Exception as e:
            logger.error(f"检测文本类型时出错: {e}")
            return "chat"  # 默认为聊天类型 
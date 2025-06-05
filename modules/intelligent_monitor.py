#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能监控器模块
实现30秒超时机制和精确状态判断
只有在界面30秒无变化或检测到明确完成信号时才触发AI干预
"""

import time
import asyncio
import logging
import hashlib
from typing import Dict, Any, List, Optional
from collections import deque
from PIL import Image
from modules.window_selector import WindowSelector
import pyautogui

logger = logging.getLogger(__name__)

class IntelligentMonitor:
    """智能监控器 - 解决频繁误判和时间控制问题"""
    
    def __init__(self, screen_monitor, timeout_seconds: int = 30):
        self.timeout_seconds = timeout_seconds
        self.window_selector = WindowSelector()
        self.screen_monitor = screen_monitor # Store the ScreenMonitor instance
        
        # 改为支持多区域
        self.chat_regions = []  # 存储多个聊天区域
        self.region_selected = False
        
        # 状态跟踪
        self.current_state = None  # 添加缺失的current_state属性
        self.last_content_hash = None
        self.last_change_time = time.time()
        self.stable_duration = 0
        
        # 添加重复检测
        self.recent_analysis_results = deque(maxlen=5)  # 保存最近5次分析结果
        
        # 历史记录
        self.state_history = []
        self.content_history = []
        self.history_limit = 20
        self.hash_history_limit = 10
        
        # 配置
        self.stable_threshold = 3  # 连续稳定检测次数
        
    async def initialize(self) -> bool:
        """异步初始化方法"""
        try:
            logger.info("🎯 初始化智能监控器...")
            
            # 尝试获取全局OCR引用并设置到window_selector
            try:
                from modules.screen_monitor import ScreenMonitor
                if hasattr(ScreenMonitor, '_global_ocr_reader') and ScreenMonitor._global_ocr_reader:
                    self.window_selector.set_ocr_reader(ScreenMonitor._global_ocr_reader)
                    logger.debug("✅ 已设置window_selector的OCR引用")
            except Exception as e:
                logger.debug(f"⚠️ 设置OCR引用失败: {e}")
            
            # 尝试加载已保存的区域配置
            if self.load_saved_region_config():
                logger.info("✅ 已加载保存的区域配置")
                return True
            
            # 如果没有保存的配置，进行手动选择
            if self.setup_monitoring_region():
                logger.info("✅ 智能监控器初始化完成")
                return True
            else:
                logger.warning("⚠️ 智能监控器初始化失败 - 无监控区域")
                return False
                
        except Exception as e:
            logger.error(f"智能监控器初始化失败: {e}")
            return False
    
    def setup_monitoring_region(self) -> bool:
        """设置监控区域 - 支持窗口选择和区域选择"""
        try:
            logger.info("🎯 开始设置监控区域...")
            
            # 步骤1: 让用户选择CURSOR窗口
            selected_window = self._select_cursor_window()
            if not selected_window:
                logger.warning("⚠️ 未选择CURSOR窗口")
                return False
            
            self.selected_window_info = selected_window
            logger.info(f"✅ 已选择窗口: {selected_window['title']}")
            
            # 步骤2: 让用户选择监控区域
            selection_result = self.window_selector.select_chat_region_for_window(selected_window)
            if selection_result and selection_result['regions']:
                self.chat_regions = selection_result['regions']
                self.region_selected = True
                
                # 保存区域配置（包含窗口信息）
                self._save_region_config()
                
                logger.info(f"✅ 成功设置 {len(self.chat_regions)} 个监控区域")
                for i, region in enumerate(self.chat_regions, 1):
                    x, y, width, height = region
                    logger.info(f"   区域{i}: ({x}, {y}) 大小: {width}x{height}")
                return True
            else:
                logger.warning("❌ 未选择监控区域")
                self.region_selected = False
                return False
                
        except Exception as e:
            logger.error(f"设置监控区域时出错: {e}")
            self.region_selected = False
            return False
    
    def _select_cursor_window(self) -> dict:
        """让用户选择CURSOR窗口"""
        try:
            import win32gui
            import tkinter as tk
            from tkinter import messagebox, simpledialog
            
            # 查找所有CURSOR窗口
            cursor_windows = []
            def enum_handler(hwnd, result_list):
                if win32gui.IsWindowVisible(hwnd):
                    window_text = win32gui.GetWindowText(hwnd)
                    if 'cursor' in window_text.lower():
                        rect = win32gui.GetWindowRect(hwnd)
                        result_list.append({
                            'hwnd': hwnd,
                            'title': window_text,
                            'rect': rect,
                            'x': rect[0],
                            'y': rect[1],
                            'width': rect[2] - rect[0],
                            'height': rect[3] - rect[1]
                        })
            
            win32gui.EnumWindows(enum_handler, cursor_windows)
            
            if not cursor_windows:
                messagebox.showerror("错误", "未找到任何CURSOR窗口！\n请确保CURSOR正在运行。")
                return None
            
            if len(cursor_windows) == 1:
                # 只有一个窗口，直接使用
                window = cursor_windows[0]
                logger.info(f"🪟 自动选择唯一的CURSOR窗口: {window['title']}")
                return window
            
            # 多个窗口，让用户选择
            root = tk.Tk()
            root.withdraw()  # 隐藏主窗口
            
            window_options = []
            for i, window in enumerate(cursor_windows):
                option = f"{i+1}. {window['title']} (位置: {window['x']}, {window['y']} 大小: {window['width']}x{window['height']})"
                window_options.append(option)
            
            choice_text = "找到多个CURSOR窗口，请选择要监控的窗口：\n\n" + "\n".join(window_options)
            
            # 使用对话框让用户选择
            choice = simpledialog.askstring(
                "选择CURSOR窗口",
                choice_text + "\n\n请输入窗口编号 (1-" + str(len(cursor_windows)) + "):"
            )
            
            root.destroy()
            
            if choice and choice.isdigit():
                choice_num = int(choice)
                if 1 <= choice_num <= len(cursor_windows):
                    selected_window = cursor_windows[choice_num - 1]
                    logger.info(f"🎯 用户选择了窗口: {selected_window['title']}")
                    return selected_window
            
            logger.warning("⚠️ 用户取消了窗口选择或输入无效")
            return None
            
        except Exception as e:
            logger.error(f"选择CURSOR窗口时出错: {e}")
            return None
    
    def _save_region_config(self):
        """保存当前的区域配置"""
        try:
            if hasattr(self, 'selected_window_info') and self.selected_window_info and self.chat_regions:
                # 如果有窗口信息，使用新的保存方法
                self.window_selector.save_regions_with_window_info(
                    f"CURSOR配置_{int(time.time())}", 
                    self.chat_regions, 
                    self.selected_window_info
                )
            elif self.chat_regions:
                # 兼容旧版本保存方法
                config_name = f"区域配置_{int(time.time())}"
                if len(self.chat_regions) == 1:
                    region = self.chat_regions[0]
                    self.window_selector.save_region(config_name, region)
                else:
                    self.window_selector.save_regions(config_name, self.chat_regions)
                    
        except Exception as e:
            logger.error(f"保存区域配置时出错: {e}")
    
    def load_saved_region_config(self) -> bool:
        """加载已保存的区域配置 - 快速启动模式"""
        try:
            import json
            import os
            
            config_file = "window_regions.json"
            
            if not os.path.exists(config_file):
                logger.warning(f"⚠️ 配置文件不存在: {config_file}")
                return False
            
            with open(config_file, 'r', encoding='utf-8') as f:
                saved_regions = json.load(f)
            
            if not saved_regions:
                logger.warning("⚠️ 配置文件为空")
                return False
            
            # 获取第一个保存的配置
            config_name = list(saved_regions.keys())[0]
            region_data = saved_regions[config_name]
            
            logger.info(f"📁 加载配置: {config_name}")
            
            # 解析配置格式
            self.chat_regions = []
            
            # 检查是否是新格式（多区域）
            if "regions" in region_data:
                # 新格式：多区域
                for region_info in region_data["regions"]:
                    self.chat_regions.append((
                        region_info["x"],
                        region_info["y"],
                        region_info["width"],
                        region_info["height"]
                    ))
            elif "region" in region_data:
                # 中等格式：有嵌套region对象的单区域
                region_info = region_data["region"]
                self.chat_regions.append((
                    region_info["x"],
                    region_info["y"],
                    region_info["width"], 
                    region_info["height"]
                ))
            elif "x" in region_data:
                # 旧格式：直接字段的单区域
                self.chat_regions.append((
                    region_data["x"],
                    region_data["y"],
                    region_data["width"], 
                    region_data["height"]
                ))
            else:
                logger.error(f"❌ 未知的区域配置格式: {region_data}")
                return False
            
            if self.chat_regions:
                logger.info(f"✅ 成功加载 {len(self.chat_regions)} 个监控区域")
                for i, region in enumerate(self.chat_regions, 1):
                    x, y, width, height = region
                    logger.info(f"   区域{i}: ({x}, {y}) 大小: {width}x{height}")
                
                self.region_selected = True
                return True
            else:
                logger.warning("❌ 未能解析出有效的区域配置")
                return False
                
        except Exception as e:
            logger.error(f"加载区域配置时出错: {e}")
            return False
    
    async def analyze_screen(self, screenshot: Image.Image, extracted_text: str, 
                           ocr_reader=None) -> Dict[str, Any]:
        """分析屏幕状态 - 支持多区域监控"""
        try:
            current_time = time.time()
            
            # 如果有监控区域，分析主要区域（第一个区域）
            if self.region_selected and self.chat_regions:
                # 使用第一个区域作为主要分析区域
                main_region = self.chat_regions[0]
                x, y, width, height = main_region
                
                # 提取区域文本
                analysis_text = self.window_selector.extract_region_text(
                    screenshot, main_region, ocr_reader
                )
                
                # 裁剪图像到监控区域
                analysis_image = screenshot.crop((x, y, x + width, y + height))
                
                logger.debug(f"🎯 分析主要区域: ({x}, {y}) 大小: {width}x{height}")
            else:
                # 使用全屏
                analysis_text = extracted_text
                analysis_image = screenshot
                logger.debug("🖥️ 使用全屏分析")
            
            # 计算内容hash
            content_hash = self._calculate_content_hash(analysis_image, analysis_text)
            
            # 检测内容变化
            content_changed = self._detect_content_change(content_hash)
            
            # 更新时间记录
            if content_changed:
                self.last_change_time = current_time
                logger.debug(f"🔄 检测到内容变化: {current_time}")
            
            # 计算稳定时间
            stable_duration = current_time - self.last_change_time
            
            # 智能状态判断
            state_info = self._intelligent_state_detection(
                analysis_text, analysis_image, stable_duration, content_changed
            )
            
            # 更新当前状态
            self.current_state = state_info.get("state", "unknown")
            
            # 记录状态历史
            self._update_state_history([state_info])
            
            return state_info
            
        except Exception as e:
            logger.error(f"智能状态分析时出错: {e}")
            return self._get_default_state()
    
    def _calculate_content_hash(self, image: Image.Image, text: str) -> str:
        """计算内容hash"""
        try:
            # 降低图像分辨率以减少计算量
            small_image = image.resize((100, 100))
            
            # 组合图像和文本特征
            content = f"{text}_{hash(small_image.tobytes())}"
            
            return hashlib.md5(content.encode()).hexdigest()
            
        except Exception as e:
            logger.debug(f"计算内容hash时出错: {e}")
            return str(time.time())
    
    def _detect_content_change(self, current_hash: str) -> bool:
        """检测内容是否发生变化"""
        try:
            if self.last_content_hash is None:
                self.last_content_hash = current_hash
                return True
            
            if current_hash != self.last_content_hash:
                # 保存到历史
                self.content_history.append(self.last_content_hash)
                if len(self.content_history) > self.hash_history_limit:
                    self.content_history.pop(0)
                
                self.last_content_hash = current_hash
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"检测内容变化时出错: {e}")
            return False
    
    def _intelligent_state_detection(self, text: str, image: Image.Image, 
                                   stable_duration: float, content_changed: bool) -> Dict[str, Any]:
        """智能状态检测逻辑"""
        try:
            current_time = time.time()
            
            # 基础状态检测
            base_state = self._detect_base_state(text, image)
            
            # 检测明确的完成信号（优先级最高）
            completion_signals = self._detect_completion_signals(text, image)
            if completion_signals["detected"]:
                logger.info(f"✅ 检测到完成信号: {completion_signals['signal_type']}")
                return {
                    "state": "completed",
                    "reasoning": f"检测到完成信号: {completion_signals['signal_type']}",
                    "confidence": completion_signals["confidence"],
                    "stable_duration": stable_duration,
                    "content_changed": content_changed,
                    "base_state": base_state,
                    "requires_action": True,
                    "action_needed": True,
                    "action_type": "completion_analysis",
                    "signal_type": completion_signals['signal_type']
                }
            
            # 检测到completed基础状态时也应该触发干预
            if base_state == "completed":
                logger.info(f"🎯 基础状态检测到完成: {base_state}")
                return {
                    "state": "completed", 
                    "reasoning": f"基础状态检测到任务完成",
                    "confidence": 0.8,
                    "stable_duration": stable_duration,
                    "content_changed": content_changed,
                    "base_state": base_state,
                    "requires_action": True,
                    "action_needed": True,
                    "action_type": "completion_analysis"
                }
            
            # 检查是否系统正在运行（忙碌状态）
            if base_state in ["running", "processing"]:
                logger.debug(f"💼 系统忙碌中: {base_state}")
                return {
                    "state": base_state,
                    "reasoning": f"系统正在{base_state}，等待完成",
                    "confidence": 0.8,
                    "stable_duration": stable_duration,
                    "content_changed": content_changed,
                    "base_state": base_state,
                    "requires_action": False,
                    "action_needed": False
                }
            
            # **关键修复：30秒超时机制**
            # 如果界面稳定30秒且没有明确的运行状态，就应该干预
            if stable_duration >= self.timeout_seconds:
                logger.warning(f"⏰ 界面稳定{stable_duration:.1f}秒，触发超时干预")
                return {
                    "state": "timeout_intervention",
                    "reasoning": f"界面无变化超过{self.timeout_seconds}秒，可能需要人工干预",
                    "confidence": 0.9,
                    "stable_duration": stable_duration,
                    "content_changed": content_changed,
                    "base_state": base_state,
                    "requires_action": True,
                    "action_needed": True,
                    "action_type": "ai_analysis",
                    "timeout_triggered": True
                }
            
            # 其他状态处理
            logger.debug(f"🔍 当前状态: {base_state}, 稳定时间: {stable_duration:.1f}s")
            return {
                "state": base_state,
                "reasoning": f"基础状态检测: {base_state}",
                "confidence": 0.6,
                "stable_duration": stable_duration,
                "content_changed": content_changed,
                "base_state": base_state,
                "requires_action": False,
                "action_needed": False
            }
            
        except Exception as e:
            logger.error(f"智能状态检测时出错: {e}")
            return self._get_default_state()
    
    def _detect_base_state(self, text: str, image: Image.Image) -> str:
        """检测基础状态"""
        try:
            text_lower = text.lower()
            
            # 智能错误状态检测 - 避免误判
            if self._is_real_error(text_lower):
                return "error"
            
            # 新增：代码审查和任务完成状态检测（优先级高）
            review_keywords = [
                "review changes", "code review", "ready for review", 
                "changes ready", "implementation complete", "代码审查", 
                "请审查", "已完成实现", "review", "changes"
            ]
            if any(keyword in text_lower for keyword in review_keywords):
                logger.info(f"🔍 检测到审查/完成状态关键词在文本中")
                return "completed"
            
            # 运行状态检测
            running_keywords = ["running", "执行中", "processing", "loading", "正在", "generating", "thinking"]
            if any(keyword in text_lower for keyword in running_keywords):
                return "running"
            
            # 完成状态检测
            completion_keywords = ["completed", "完成", "success", "successfully", "✅", "🎉", "done", "finished"]
            if any(keyword in text_lower for keyword in completion_keywords):
                return "completed"
            
            # 默认为等待输入
            return "waiting_input"
            
        except Exception as e:
            logger.debug(f"检测基础状态时出错: {e}")
            return "waiting_input"
    
    def _is_real_error(self, text_lower: str) -> bool:
        """智能判断是否为真正的错误状态"""
        try:
            # 添加调试输出
            logger.debug(f"🔍 检查文本是否为错误状态...")
            logger.debug(f"📝 文本长度: {len(text_lower)} 字符")
            logger.debug(f"📄 文本预览: {repr(text_lower[:100])}")
            
            # 严重错误关键词（优先级高）
            critical_errors = [
                "fatal error", "critical error", "system error", "crash",
                "致命错误", "严重错误", "系统错误", "崩溃"
            ]
            
            for error in critical_errors:
                if error in text_lower:
                    logger.warning(f"🚨 检测到严重错误: {error}")
                    return True
            
            # 一般错误关键词（需要上下文判断）
            general_errors = ["error", "错误", "失败", "exception", "traceback", "failed"]
            
            # 扩展排除的上下文（这些情况下的错误关键词不算真正错误）
            exclude_contexts = [
                # 错误处理相关
                "error handling", "error message", "error code", "error log",
                "try catch", "exception handling", "error prevention",
                "错误处理", "错误信息", "错误代码", "错误日志", "异常处理",
                
                # 开发调试相关
                "debug", "test", "example", "示例", "测试", "调试",
                
                # 终端和系统输出相关
                "powershell", "cmd", "terminal", "console", "shell",
                "categoryinfo", "parsererror", "commandnotfound",
                "fullyqualifiedid", "itemnotfound", "objectnotfound",
                "parentcontains", "标记", "不是", "版本", "有效", "语句分隔符",
                
                # 日志和监控相关
                "log", "info", "warning", "监控", "检测", "分析",
                "cursor", "supervisor", "monitor", "智能", "状态",
                
                # OCR识别错误相关
                "ocr", "识别", "文本", "字符", "内容", "预览"
            ]
            
            # 检查是否有错误关键词
            found_errors = [keyword for keyword in general_errors if keyword in text_lower]
            
            if found_errors:
                logger.debug(f"⚠️ 发现错误关键词: {found_errors}")
                
                # 检查是否在排除的上下文中
                in_exclude_context = any(context in text_lower for context in exclude_contexts)
                
                if in_exclude_context:
                    logger.debug("🔍 检测到错误关键词，但在排除上下文中，不视为真正错误")
                    return False
                
                # 检查是否包含系统/终端特征词汇
                system_indicators = [
                    "ps ", "c:\\", "d:\\", "所在位置", "行:", "字符:", 
                    "cmdlet", "function", "script", "程序", "路径",
                    "拼写", "确保", "再试一次", "无法", "识别", "找不到"
                ]
                
                has_system_indicators = any(indicator in text_lower for indicator in system_indicators)
                if has_system_indicators:
                    logger.debug("🔍 检测到系统/终端特征，不视为真正错误")
                    return False
                
                # 检查文本长度 - 非常短的文本中的错误更可能是真正的错误
                if len(text_lower.strip()) < 20:
                    logger.warning("🚨 极短文本中检测到错误关键词，可能是真正错误")
                    return True
                
                # 检查错误关键词的密度和上下文
                error_count = len(found_errors)
                text_length = len(text_lower)
                error_density = error_count / max(text_length, 1) * 1000  # 每1000字符的错误词数
                
                # 如果错误密度很低（长文本中少量错误词），可能不是真正错误
                if error_density < 5 and text_length > 200:  # 每1000字符少于5个错误词
                    logger.debug(f"🔍 错误密度较低 ({error_density:.2f}/1000字符)，可能不是真正错误")
                    return False
                
                # 如果有多个错误关键词但文本很长，需要更仔细判断
                if error_count >= 2 and text_length > 500:
                    logger.debug("🔍 长文本中有多个错误关键词，但可能是日志或系统输出")
                    return False
                
                # 单个错误关键词在中等长度文本中，可能不是真正错误
                if error_count == 1 and text_length > 100:
                    logger.debug("🔍 中等长度文本中单个错误关键词，可能是误判")
                    return False
                
                # 其他情况，可能是真正错误
                logger.warning("🚨 可能检测到真正错误")
                return True
            else:
                logger.debug("✅ 未发现错误关键词")
            
            return False
            
        except Exception as e:
            logger.debug(f"智能错误判断时出错: {e}")
            return False
    
    def _detect_completion_signals(self, text: str, image: Image.Image) -> Dict[str, Any]:
        """检测明确的完成信号"""
        try:
            signals = {
                "detected": False,
                "signal_type": None,
                "confidence": 0.0
            }
            
            text_lower = text.lower()
            
            # 强完成信号
            strong_signals = [
                ("🎉", "celebration_emoji", 0.95),
                ("✅", "checkmark_emoji", 0.9),
                ("completed successfully", "completion_text", 0.9),
                ("任务完成", "task_completion_chinese", 0.9),
                ("execution finished", "execution_completion", 0.85),
                ("build successful", "build_completion", 0.85),
                # 新增：代码审查和任务交付相关信号
                ("review changes", "review_changes", 0.9),
                ("code review", "code_review", 0.85),
                ("ready for review", "ready_review", 0.85),
                ("changes ready", "changes_ready", 0.8),
                ("implementation complete", "implementation_complete", 0.85),
                ("代码审查", "code_review_chinese", 0.85),
                ("请审查", "please_review_chinese", 0.8),
                ("已完成实现", "implementation_done_chinese", 0.85)
            ]
            
            for signal, signal_type, confidence in strong_signals:
                if signal in text_lower:
                    signals["detected"] = True
                    signals["signal_type"] = signal_type
                    signals["confidence"] = confidence
                    logger.info(f"🎯 检测到强完成信号: {signal} (类型: {signal_type}, 置信度: {confidence})")
                    return signals
            
            # 弱完成信号（需要结合其他条件）
            weak_signals = [
                ("done", "done_text", 0.6),
                ("finished", "finished_text", 0.6),
                ("ready", "ready_text", 0.5),
                # 新增：其他可能的完成提示
                ("deploy", "deploy_ready", 0.7),
                ("test", "test_ready", 0.6),
                ("验证", "verify_chinese", 0.6),
                ("部署", "deploy_chinese", 0.7)
            ]
            
            for signal, signal_type, confidence in weak_signals:
                if signal in text_lower and len(text.strip()) < 100:  # 短文本更可能是完成信号
                    signals["detected"] = True
                    signals["signal_type"] = signal_type
                    signals["confidence"] = confidence
                    return signals
            
            return signals
            
        except Exception as e:
            logger.debug(f"检测完成信号时出错: {e}")
            return {"detected": False, "signal_type": None, "confidence": 0.0}
    
    def _update_state_history(self, state_infos: List[Dict[str, Any]]):
        """更新状态历史"""
        try:
            for state_info in state_infos:
                # 添加时间戳
                state_info["timestamp"] = time.time()
                
                # 添加到历史记录
                self.state_history.append(state_info)
                
                # 限制历史记录长度
                if len(self.state_history) > self.history_limit:
                    self.state_history.pop(0)
                    
        except Exception as e:
            logger.error(f"更新状态历史时出错: {e}")
    
    def _get_default_state(self) -> Dict[str, Any]:
        """获取默认状态"""
        return {
            "state": "monitoring",
            "reasoning": "默认监控状态",
            "confidence": 0.5,
            "stable_duration": 0.0,
            "requires_action": False,
            "action_type": "monitor",
            "timeout_triggered": False
        }
    
    def get_monitoring_stats(self) -> Dict[str, Any]:
        """获取监控统计信息"""
        try:
            current_time = time.time()
            
            # 从最新的状态历史中获取当前状态
            current_state = "unknown"
            if self.state_history:
                current_state = self.state_history[-1].get("state", "unknown")
            elif self.current_state:
                current_state = self.current_state
            
            return {
                "region_selected": self.region_selected,
                "chat_regions": self.chat_regions,
                "current_state": current_state,
                "stable_duration": current_time - self.last_change_time,
                "total_state_changes": len(self.state_history),
                "monitoring_active": True,
                "timeout_seconds": self.timeout_seconds
            }
            
        except Exception as e:
            logger.error(f"获取监控统计时出错: {e}")
            return {
                "region_selected": False,
                "chat_regions": [],
                "current_state": "error",
                "stable_duration": 0.0,
                "total_state_changes": 0,
                "monitoring_active": False,
                "timeout_seconds": self.timeout_seconds
            }
    
    def reset_monitoring(self):
        """重置监控状态"""
        try:
            self.current_state = None
            self.state_start_time = None
            self.last_change_time = time.time()
            self.last_content_hash = None
            self.stable_duration = 0
            self.state_history.clear()
            self.content_history.clear()
            
            logger.info("🔄 监控状态已重置")
            
        except Exception as e:
            logger.error(f"重置监控状态时出错: {e}")
    
    def should_trigger_ai_intervention(self, state_info: Dict[str, Any]) -> bool:
        """判断是否应该触发AI干预"""
        try:
            # 检查所有可能的action标志
            if state_info.get("requires_action", False) or state_info.get("action_needed", False):
                logger.info(f"🎯 触发干预原因: requires_action={state_info.get('requires_action')}, action_needed={state_info.get('action_needed')}")
                return True
            
            # 30秒超时触发
            if state_info.get("timeout_triggered", False):
                logger.info("⏰ 触发干预原因: 超时机制")
                return True
            
            # 检测到完成信号 - 多种方式检测
            state = state_info.get("state", "")
            if state in ["completed", "timeout_intervention"]:
                logger.info(f"✅ 触发干预原因: 状态 = {state}")
                return True
            
            # 持续错误状态
            if state == "persistent_error":
                logger.info("🚨 触发干预原因: 持续错误")
                return True
            
            # 检查是否有明确的完成信号
            if state_info.get("signal_type"):
                logger.info(f"🎉 触发干预原因: 检测到信号 = {state_info.get('signal_type')}")
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"判断AI干预时出错: {e}")
            return False
    
    def _is_clearly_running(self, text: str, image: Image.Image) -> bool:
        """检测是否明确在运行状态"""
        text_lower = text.lower()
        
        # 运行中的明确信号
        running_indicators = [
            "running", "执行中", "processing", "generating",
            "analyzing", "thinking", "loading", "waiting",
            "please wait", "请稍等", "正在", "处理中"
        ]
        
        for indicator in running_indicators:
            if indicator in text_lower:
                return True
        
        return False
    
    async def detect_cursor_window(self, screenshot: Image.Image) -> bool:
        """检测CURSOR窗口是否存在"""
        try:
            # 简单的窗口检测逻辑
            if screenshot:
                # 如果能获取到截图，认为窗口存在
                return True
            return False
            
        except Exception as e:
            logger.error(f"检测CURSOR窗口时出错: {e}")
            return False 
    
    async def extract_text_from_screenshot(self, screenshot: Image.Image) -> str:
        """从截图中提取文本 - 多区域支持，修复坐标转换问题"""
        try:
            if not self.chat_regions:
                logger.warning("⚠️ 没有设置监控区域")
                return ""

            all_region_texts = []
            
            # 🔧 关键修复：使用screen_monitor的窗口信息而不是重新查找
            try:
                # 优先使用screen_monitor中已经确定的窗口信息
                if (hasattr(self.screen_monitor, 'selected_window_info') and 
                    self.screen_monitor.selected_window_info and 
                    'position' in self.screen_monitor.selected_window_info):
                    
                    # 使用已保存的窗口信息
                    window_x, window_y, window_width, window_height = self.screen_monitor.selected_window_info['position']
                    window_right = window_x + window_width
                    window_bottom = window_y + window_height
                    
                    logger.debug(f"🎯 使用已选择的窗口: {self.screen_monitor.selected_window_info.get('title', 'Unknown')}")
                    logger.debug(f"🪟 窗口位置: ({window_x}, {window_y}) 大小: {window_width}x{window_height}")
                    
                    # 获取窗口截图
                    import pyautogui
                    window_screenshot = pyautogui.screenshot(region=(window_x, window_y, window_width, window_height))
                    logger.debug(f"📸 获取指定窗口截图: {window_screenshot.size}")
                    
                elif hasattr(self.screen_monitor, 'cursor_window_coords') and self.screen_monitor.cursor_window_coords:
                    # 使用screen_monitor的窗口坐标
                    window_x, window_y, window_right, window_bottom = self.screen_monitor.cursor_window_coords
                    window_width = window_right - window_x
                    window_height = window_bottom - window_y
                    
                    logger.debug(f"🎯 使用screen_monitor的窗口坐标")
                    logger.debug(f"🪟 窗口位置: ({window_x}, {window_y}) 大小: {window_width}x{window_height}")
                    
                    # 获取窗口截图
                    import pyautogui
                    window_screenshot = pyautogui.screenshot(region=(window_x, window_y, window_width, window_height))
                    logger.debug(f"📸 获取窗口截图: {window_screenshot.size}")
                    
                else:
                    logger.warning("⚠️ 没有可用的窗口信息，使用传入的截图")
                    window_screenshot = screenshot
                    window_x, window_y = 0, 0
                    
            except Exception as e:
                logger.warning(f"⚠️ 获取窗口信息失败: {e}，使用传入截图")
                window_screenshot = screenshot
                window_x, window_y = 0, 0

            # 处理每个监控区域
            for i, region_coords in enumerate(self.chat_regions, 1):
                try:
                    saved_x, saved_y, crop_width, crop_height = region_coords
                    
                    # 🔧 关键修复：将保存的绝对坐标转换为窗口相对坐标
                    rel_crop_x = saved_x - window_x
                    rel_crop_y = saved_y - window_y
                    
                    logger.debug(f"🎯 区域{i} 坐标转换:")
                    logger.debug(f"   保存的绝对坐标: ({saved_x}, {saved_y})")
                    logger.debug(f"   窗口位置: ({window_x}, {window_y})")
                    logger.debug(f"   转换后相对坐标: ({rel_crop_x}, {rel_crop_y}) 大小: {crop_width}x{crop_height}")
                    
                    # 验证相对坐标是否在窗口范围内
                    window_w, window_h = window_screenshot.size
                    if (rel_crop_x < 0 or rel_crop_y < 0 or 
                        rel_crop_x + crop_width > window_w or 
                        rel_crop_y + crop_height > window_h):
                        logger.warning(f"⚠️ 区域{i}相对坐标超出窗口范围，跳过")
                        logger.warning(f"   窗口: {window_w}x{window_h}, 区域: ({rel_crop_x},{rel_crop_y}) 到 ({rel_crop_x+crop_width},{rel_crop_y+crop_height})")
                        continue
                    
                    # 使用相对坐标裁剪窗口截图
                    cropped_image = window_screenshot.crop((rel_crop_x, rel_crop_y, rel_crop_x + crop_width, rel_crop_y + crop_height))
                    
                    # 验证裁剪图像是否有效
                    if cropped_image.size[0] <= 0 or cropped_image.size[1] <= 0:
                        logger.error(f"❌ 区域{i}裁剪图像尺寸无效: {cropped_image.size}")
                        continue

                    # 保存区域截图供调试
                    region_screenshot_path = f"region_screenshot_{i}_{int(time.time())}.png"
                    cropped_image.save(region_screenshot_path)
                    logger.debug(f"📸 已保存区域{i}截图: {region_screenshot_path}")
                    
                    # 使用OCR提取文字
                    # 使用OCR提取文字（核心方法）
                    region_text = await self._ocr_extract_text(cropped_image)
                    
                    if region_text and not region_text.startswith("OCR_FAILED"):
                        logger.info(f"✅ 区域{i} OCR成功: {region_text[:50]}...")
                        if self._is_valid_content(region_text):
                            all_region_texts.append(region_text)
                        else:
                            logger.debug(f"📝 区域{i} 内容无效，跳过: {region_text[:30]}...")
                    else:
                        logger.warning(f"⚠️ 区域{i} OCR失败或无内容: {region_text}")
                        
                except Exception as e:
                    logger.error(f"❌ 处理区域{i}时出错: {e}")
                    continue

            # 合并所有区域的文本
            if all_region_texts:
                combined_text = ' '.join(all_region_texts)
                logger.info(f"✅ 成功提取 {len(all_region_texts)} 个区域的文本，总长度: {len(combined_text)}")
                return combined_text
            else:
                logger.warning("⚠️ 所有区域都没有提取到有效文本")
                return ""

        except Exception as e:
            logger.error(f"❌ 从截图提取文本时出错: {e}")
            return f"OCR_FAILED:EXTRACT_ERROR:{e}"

    async def _ocr_extract_text(self, image: Image.Image) -> str:
        """OCR提取文本的核心方法"""
        try:
            # 尝试使用screen_monitor的预处理以提升识别率
            try:
                if getattr(self, 'screen_monitor', None):
                    image = self.screen_monitor.preprocess_image(image)
            except Exception as e:
                logger.debug(f"OCR预处理失败: {e}")

            # 尝试使用EasyOCR
            if hasattr(self, 'ocr_reader') and self.ocr_reader:
                import numpy as np
                img_array = np.array(image)
                results = self.ocr_reader.readtext(img_array)
                if results:
                    all_texts = [result[1].strip() for result in results if result[1] and result[1].strip()]
                    if all_texts:
                        combined_text = ' '.join(all_texts)
                        # 清理OCR乱码和噪声
                        cleaned_text = self._clean_ocr_text(combined_text)
                        return cleaned_text if cleaned_text else ""
            
            # 尝试使用全局OCR
            from modules.screen_monitor import ScreenMonitor
            if hasattr(ScreenMonitor, '_global_ocr_reader') and ScreenMonitor._global_ocr_reader:
                import numpy as np
                img_array = np.array(image)
                results = ScreenMonitor._global_ocr_reader.readtext(img_array)
                if results:
                    all_texts = [result[1].strip() for result in results if result[1] and result[1].strip()]
                    if all_texts:
                        combined_text = ' '.join(all_texts)
                        # 清理OCR乱码和噪声
                        cleaned_text = self._clean_ocr_text(combined_text)
                        return cleaned_text if cleaned_text else ""
            
            return ""
            
        except Exception as e:
            logger.warning(f"⚠️ 直接OCR提取失败: {e}")
            return ""
    
    def _clean_ocr_text(self, text: str) -> str:
        """清理OCR提取的文本，去除乱码和噪声"""
        try:
            if not text or not text.strip():
                return ""
            
            import re
            
            # 1. 移除常见的OCR乱码字符和模式
            ocr_noise_patterns = [
                r'[^\w\s\u4e00-\u9fff.,!?;:\'"()[\]{}\-+=<>/@#$%^&*~`|\\]',  # 保留基本标点和中英文
                r'[_]{3,}',  # 连续下划线
                r'[.]{4,}',  # 连续点号
                r'[|]{2,}',  # 连续竖线
                r'[~]{2,}',  # 连续波浪号
                r'[\u2500-\u257F]+',  # 线框字符
                r'[\u2580-\u259F]+',  # 块字符
            ]
            
            cleaned_text = text
            for pattern in ocr_noise_patterns:
                cleaned_text = re.sub(pattern, ' ', cleaned_text)
            
            # 2. 清理明显的乱码词汇（基于字符频率和模式）
            words = cleaned_text.split()
            valid_words = []
            
            for word in words:
                # 跳过太短的单词
                if len(word) < 2:
                    continue
                
                # 跳过包含过多特殊字符的单词
                special_char_ratio = len(re.findall(r'[^\w\u4e00-\u9fff]', word)) / len(word)
                if special_char_ratio > 0.5:
                    continue
                
                # 跳过明显的乱码模式
                noise_patterns = [
                    r'^[A-Z]{1,2}[0-9]+$',  # 类似 "A1", "B23"
                    r'^\w{1,2}[\u4e00-\u9fff]{0,1}[\w]*$',  # 混合乱码
                    r'^[a-z][A-Z][a-z]+$',  # 大小写混乱
                ]
                
                is_noise = False
                for pattern in noise_patterns:
                    if re.match(pattern, word) and len(word) < 6:
                        is_noise = True
                        break
                
                if not is_noise:
                    valid_words.append(word)
            
            # 3. 重组文本
            result = ' '.join(valid_words)
            
            # 4. 最终清理：规范化空格
            result = re.sub(r'\s+', ' ', result).strip()
            
            # 5. 如果清理后文本太短，返回空字符串
            if len(result) < 3:
                logger.debug(f"文本清理后太短，丢弃: '{result}'")
                return ""
            
            # 6. 记录清理结果
            if result != text.strip():
                logger.debug(f"OCR文本清理: '{text[:50]}...' -> '{result[:50]}...'")
            
            return result
            
        except Exception as e:
            logger.warning(f"清理OCR文本时出错: {e}")
            return text.strip() if text else ""
    
    def _is_valid_content(self, text: str) -> bool:
        """检查文本内容是否有效"""
        try:
            if not text or not text.strip():
                return False
            
            # 过滤太短的文本
            if len(text.strip()) < 3:
                return False
            
            # 过滤只包含特殊字符的文本
            import re
            if re.match(r'^[^\w\u4e00-\u9fff]+$', text.strip()):
                return False
            
            # 过滤明显的噪声文本
            noise_patterns = [
                r'^[_\-=+]{3,}$',  # 连续的符号
                r'^[0-9.]{3,}$',   # 纯数字
                r'^[A-Z]{1,2}$',   # 单独的字母
            ]
            
            for pattern in noise_patterns:
                if re.match(pattern, text.strip()):
                    return False
            
            return True
            
        except Exception as e:
            logger.debug(f"检查文本有效性时出错: {e}")
            return True  # 出错时默认认为有效
    
    def _extract_chat_content_from_full_text(self, full_text: str) -> str:
        """从全屏文本中智能提取聊天相关内容"""
        try:
            lines = full_text.split('\n')
            chat_lines = []
            
            # 查找可能的聊天内容关键词
            chat_keywords = [
                "claude", "cursor", "assistant", "ai", "助手",
                "代码", "函数", "错误", "实现", "完成", "修复",
                "测试", "运行", "调试", "配置", "安装"
            ]
            
            for line in lines:
                line_lower = line.lower().strip()
                if line_lower and len(line.strip()) > 10:  # 忽略太短的行
                    # 检查是否包含聊天相关内容
                    if any(keyword in line_lower for keyword in chat_keywords):
                        chat_lines.append(line.strip())
                    # 或者包含常见的编程相关内容
                    elif any(word in line_lower for word in ["error", "function", "class", "import", "def", "return"]):
                        chat_lines.append(line.strip())
            
            # 如果找到相关内容，返回最后几行（最新的对话）
            if chat_lines:
                # 返回最后5行最相关的内容
                relevant_content = "\n".join(chat_lines[-5:])
                logger.debug(f"智能提取聊天内容: {relevant_content[:100]}...")
                return relevant_content
            
            # 如果没有找到特定内容，返回最后几行作为fallback
            if lines:
                fallback_content = "\n".join([line.strip() for line in lines[-3:] if line.strip()])
                logger.debug(f"Fallback内容: {fallback_content[:100]}...")
                return fallback_content
                
            return ""
            
        except Exception as e:
            logger.debug(f"智能提取聊天内容失败: {e}")
            return full_text[:500] if full_text else ""  # 简单截取前500字符作为fallback
    
    async def cleanup(self):
        """清理资源"""
        try:
            logger.info("🧹 清理IntelligentMonitor资源...")
            
            # 清理状态历史
            self.state_history.clear()
            self.content_history.clear()
            self.recent_analysis_results.clear()
            
            # 重置状态
            self.current_state = None
            self.last_content_hash = None
            self.region_selected = False
            self.chat_regions.clear()
            
            logger.info("✅ IntelligentMonitor资源清理完成")
            
        except Exception as e:
            logger.error(f"清理IntelligentMonitor资源时出错: {e}") 
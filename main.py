#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CURSOR IDE监督系统主程序
功能：监控CURSOR状态，智能检测异常情况，并提供相应的操作建议
"""

import asyncio
import time
import logging
import os
import signal
import sys
import platform
from typing import Dict, Any, Optional, List, Tuple
from PIL import Image
import threading
import json
import re

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cursor_supervisor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# 导入自定义模块
try:
    from modules.screen_monitor import ScreenMonitor
    from modules.intelligent_monitor import IntelligentMonitor
    from modules.automation_controller import AutomationController
    from modules.gpt_controller import GPTController
    from modules.product_manager import ProductManager
    from modules.user_feedback import UserFeedbackManager
    from modules.project_planner import ProjectPlanner
    import config
    logger.info("✅ 所有模块导入成功")
except ImportError as e:
    logger.error(f"❌ 模块导入失败: {e}")
    sys.exit(1)

class CursorSupervisor:
    """CURSOR监督者主类"""
    
    def __init__(self):
        """初始化监督者"""
        self.screen_monitor = None
        self.intelligent_monitor = None
        self.automation_controller = None
        self.gpt_controller = None
        self.product_manager = None
        self.user_feedback_manager = UserFeedbackManager()
        self.project_planner = None  # 项目规划管理器
        
        # 状态管理
        self.is_running = False
        self.should_stop = False
        self.last_interaction_time = 0
        self.stuck_detection_time = 50  # 修改：从30秒改为50秒
        self.last_screenshot_hash = None
        
        # 监控配置
        self.monitor_interval = 20  # 修改：从5秒改为20秒
        self.max_retries = 3
        self.waiting_for_cursor_response = False
        
        # 输入框点击增强配置
        self.input_click_retries = 8  # 增加到8次重试
        self.input_verification_timeout = 3  # 输入验证超时秒数
        
        # 新增：智能交互状态管理
        self.cursor_is_processing = False  # CURSOR是否正在处理错误
        self.last_dialog_content = ""  # 上次对话内容
        self.dialog_history = []  # 对话历史记录
        self.conversation_turns = []  # 完整对话轮次记录
        self.current_turn = None  # 当前对话轮次
        self.last_content_change_time = time.time()  # 上次内容变化时间
        self.processing_keywords = [
            "正在处理", "修复中", "分析中", "生成中", "处理错误",
            "working on", "fixing", "analyzing", "generating", "processing"
        ]
        self.review_keywords = [
            "review changes", "审查变更", "检查修改", "查看变更",
            "Review Changes", "review the changes", "请审查"
        ]

        # 新增：重复处理防护机制
        self.is_processing_message = False  # 当前是否正在处理消息
        self.last_processed_content_hash = None  # 上次处理的内容哈希
        self.last_instruction_time = 0  # 上次发送指令的时间
        self.instruction_cooldown = 8  # 修复：指令发送冷却时间从15秒降低到8秒，减少卡住情况
        self.processed_message_hashes = set()  # 已处理消息的哈希集合
        self.max_processed_hashes = 50  # 最大保存的哈希数量
        
        # 新增：更强的重复检测机制
        self.content_repetition_count = {}  # 内容重复次数统计
        self.max_same_content_processing = 3  # 修复：相同内容最多处理3次（之前1次太严格）
        self.last_sent_instruction_hash = None  # 上次发送指令的内容哈希
        
        # 新增：功能状态跟踪
        self.project_status_file = "项目开发状态.txt"
        self.last_instruction_sent = ""  # 上次发送的指令
        self.current_feature_focus = ""  # 当前关注的功能
        
        # 新增：防卡住机制
        self.last_progress_time = time.time()  # 上次有进展的时间
        self.max_stuck_time = 120  # 最大卡住时间（2分钟）
        
        # 清理历史记录
        self.cleanup_project_status_file()
        
    def cleanup_project_status_file(self):
        """清理项目状态文件中的无效记录"""
        try:
            if not os.path.exists(self.project_status_file):
                return
                
            with open(self.project_status_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 过滤包含无效内容的行
            lines = content.split('\n')
            cleaned_lines = []
            
            for line in lines:
                # 保留文件头部信息
                if line.startswith('#') or line.strip() == "":
                    cleaned_lines.append(line)
                    continue
                
                # 检查是否包含无效内容
                invalid_indicators = [
                    "dark_content", "detected_features:", "high_brightness_content",
                    "stable_content", "unknown_content", "text_like_patterns"
                ]
                
                line_lower = line.lower()
                if any(indicator in line_lower for indicator in invalid_indicators):
                    logger.debug(f"🧹 清理无效状态记录: {line[:50]}...")
                    continue
                    
                cleaned_lines.append(line)
            
            # 写回清理后的内容
            cleaned_content = '\n'.join(cleaned_lines)
            if cleaned_content != content:
                with open(self.project_status_file, "w", encoding="utf-8") as f:
                    f.write(cleaned_content)
                logger.info(f"✅ 项目状态文件已清理，移除了包含无效内容的记录")
            
        except Exception as e:
            logger.error(f"❌ 清理项目状态文件失败: {e}")
    
    def _find_all_cursor_windows(self) -> List[Tuple[str, Tuple[int, int, int, int]]]:
        """查找所有CURSOR窗口"""
        windows = []
        
        try:
            if platform.system() == "Windows":
                windows = self._find_cursor_windows_windows()
            else:
                windows = self._find_cursor_windows_cross_platform()
        except Exception as e:
            logger.error(f"查找CURSOR窗口时出错: {e}")
        
        return windows
    
    def _find_cursor_windows_windows(self) -> List[Tuple[str, Tuple[int, int, int, int]]]:
        """在Windows上查找所有CURSOR窗口"""
        try:
            import win32gui
            
            def enum_windows_callback(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    window_title = win32gui.GetWindowText(hwnd)
                    if window_title and self._is_cursor_window(window_title):
                        rect = win32gui.GetWindowRect(hwnd)
                        if rect[2] > rect[0] and rect[3] > rect[1]:  # 确保窗口有有效尺寸
                            windows.append((window_title, rect))
                return True
            
            windows = []
            win32gui.EnumWindows(enum_windows_callback, windows)
            return windows
            
        except ImportError:
            logger.warning("⚠️ win32gui不可用，使用跨平台方法")
            return self._find_cursor_windows_cross_platform()
        except Exception as e:
            logger.error(f"Windows窗口查找失败: {e}")
            return []
    
    def _find_cursor_windows_cross_platform(self) -> List[Tuple[str, Tuple[int, int, int, int]]]:
        """跨平台查找CURSOR窗口"""
        try:
            import psutil
            windows = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and 'cursor' in proc.info['name'].lower():
                        windows.append((f"CURSOR (PID: {proc.info['pid']})", (100, 100, 1200, 800)))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return windows
        except Exception as e:
            logger.error(f"跨平台窗口查找失败: {e}")
            return []
    
    def _is_cursor_window(self, title: str) -> bool:
        """判断是否为CURSOR窗口"""
        title_lower = title.lower()
        cursor_indicators = ['cursor', 'code', 'vscode']
        exclude_indicators = ['选择', 'selection', 'dialog', '对话框']
        
        has_cursor_keyword = any(indicator in title_lower for indicator in cursor_indicators)
        is_not_excluded = not any(exclude in title_lower for exclude in exclude_indicators)
        
        return has_cursor_keyword and is_not_excluded
    
    def _select_cursor_window(self, windows: List[Tuple[str, Tuple[int, int, int, int]]]) -> Optional[Tuple[str, Tuple[int, int, int, int]]]:
        """选择CURSOR窗口"""
        if not windows:
            print("❌ 未找到CURSOR窗口！")
            return None
        
        if len(windows) == 1:
            print(f"✅ 找到唯一CURSOR窗口: {windows[0][0]}")
            return windows[0]
        
        print("\n🔍 找到多个CURSOR窗口：")
        for i, (title, coords) in enumerate(windows):
            x, y, w, h = coords
            size_info = f"{w-x}x{h-y}"
            print(f"  {i+1}. {title} [{size_info}]")
        
        while True:
            try:
                choice = input(f"\n请选择要监控的CURSOR窗口 (1-{len(windows)}): ").strip()
                if choice.isdigit():
                    index = int(choice) - 1
                    if 0 <= index < len(windows):
                        selected = windows[index]
                        print(f"✅ 选择了: {selected[0]}")
                        return selected
                
                print("❌ 请输入有效的数字")
            except KeyboardInterrupt:
                print("\n❌ 用户取消选择")
                return None
    
    def _select_monitoring_regions(self, selected_window) -> bool:
        """选择监控区域 - 使用新的窗口特定方法"""
        try:
            # 导入所需模块
            from modules.window_selector import WindowSelector
            
            print("\n📍 现在需要为选定的CURSOR窗口选择监控区域：")
            print("   1. 聊天区域（CURSOR回复内容的地方）")
            print("   2. 运行结果区域（可选，代码执行结果的地方）")
            print("\n💡 操作方法：用鼠标拖拽框选区域，按ESC取消，按回车确认")
            
            window_title, window_coords = selected_window
            window_x, window_y, window_right, window_bottom = window_coords
            
            # 构建窗口信息字典
            window_info = {
                'title': window_title,
                'x': window_x,
                'y': window_y, 
                'width': window_right - window_x,
                'height': window_bottom - window_y
            }
            
            print(f"📋 窗口信息: {window_title}")
            print(f"   位置: ({window_x}, {window_y})")
            print(f"   大小: {window_info['width']}x{window_info['height']}")
            
            # 检查是否有已保存的配置
            config_file = "window_regions.json"
            if os.path.exists(config_file):
                choice = input("\n发现已保存的区域配置，是否使用？(y/n，默认n): ").strip().lower()
                if choice == 'y' or choice == 'yes':
                    print("✅ 使用已保存的区域配置")
                    window_selector = WindowSelector()
                    selected_regions = window_selector.select_chat_region()
                    if selected_regions:
                        print("✅ 区域配置加载完成！")
                        return True
                else:
                    print("🔄 将重新选择区域...")
                    # 删除旧配置，强制重新选择
                    os.remove(config_file)
                    print("🗑️ 已删除旧配置文件")
            
            input("\n按回车键开始选择聊天区域...")
            
            # 使用新的窗口特定方法进行区域选择
            window_selector = WindowSelector()
            selection_result = window_selector.select_chat_region_for_window(window_info)
            
            if selection_result and (selection_result['regions'] or selection_result['input_box']):
                print("✅ 区域选择完成！")
                
                # 显示监控区域信息
                regions = selection_result['regions']
                if regions:
                    print(f"   已选择 {len(regions)} 个监控区域")
                    for i, region in enumerate(regions, 1):
                        x, y, w, h = region
                        print(f"   区域{i}: ({x}, {y}) 大小: {w}x{h}")
                else:
                    print("   未选择监控区域")
                
                # 显示输入框信息
                input_box = selection_result['input_box']
                if input_box:
                    x, y, w, h = input_box
                    print(f"   输入框: ({x}, {y}) 大小: {w}x{h}")
                else:
                    print("   未选择输入框")
                
                # 保存输入框位置到自动化控制器配置
                if input_box:
                    self._save_input_box_config(input_box, window_info)
                
                return True
            else:
                print("❌ 区域选择失败或被取消")
                return False
                
        except Exception as e:
            logger.error(f"区域选择出错: {e}")
            return False
    
    def _save_input_box_config(self, input_box: tuple, window_info: dict):
        """保存输入框配置到自动化控制器"""
        try:
            import json
            import os
            
            config_file = "input_box_config.json"
            x, y, w, h = input_box
            
            config_data = {
                "input_box": {
                    "x": x,
                    "y": y,
                    "width": w,
                    "height": h,
                    "center_x": x + w // 2,
                    "center_y": y + h // 2
                },
                "window": {
                    "title": window_info['title'],
                    "x": window_info['x'],
                    "y": window_info['y'],
                    "width": window_info['width'],
                    "height": window_info['height']
                },
                "timestamp": time.time()
            }
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ 输入框配置已保存到 {config_file}")
            
        except Exception as e:
            logger.error(f"保存输入框配置失败: {e}")

    async def initialize(self) -> bool:
        """初始化所有组件"""
        try:
            logger.info("🚀 初始化CURSOR监督系统...")
            
            # 步骤0：选择项目规划文件
            logger.info("🔍 步骤0: 选择项目规划文件...")
            self.project_planner = ProjectPlanner()
            project_file = self.project_planner.select_project_file()
            if project_file:
                if self.project_planner.load_project_file(project_file):
                    logger.info(f"✅ 项目规划器初始化成功，加载项目: {self.project_planner.project_title}")
                    logger.info(f"📊 项目进度: {len(self.project_planner.completed_tasks)}/{len(self.project_planner.tasks)} 任务完成")
                else:
                    logger.warning("⚠️ 项目文件加载失败，将使用默认产品经理模式")
                    self.project_planner = None
            else:
                logger.info("ℹ️ 未选择项目文件，将使用默认产品经理模式")
                self.project_planner = None
            
            # 步骤1：选择CURSOR窗口
            logger.info("🔍 步骤1: 查找并选择CURSOR窗口...")
            cursor_windows = self._find_all_cursor_windows()
            
            if not cursor_windows:
                logger.error("❌ 未找到CURSOR窗口！请确保CURSOR正在运行。")
                return False
            
            selected_window = self._select_cursor_window(cursor_windows)
            if not selected_window:
                logger.error("❌ 未选择CURSOR窗口")
                return False
            
            window_title, window_coords = selected_window
            logger.info(f"✅ 选择了CURSOR窗口: {window_title}")
            
            # 步骤2：选择监控区域
            logger.info("🔍 步骤2: 选择监控区域...")
            if not self._select_monitoring_regions(selected_window):
                logger.error("❌ 区域选择失败")
                return False
            
            # 准备窗口信息
            window_info = {
                'title': window_title,
                'position': window_coords  # (x, y, width, height)
            }
            
            # 初始化屏幕监控器并传递选择的窗口信息
            self.screen_monitor = ScreenMonitor(selected_window_info=window_info)
            if not await self.screen_monitor.initialize():
                logger.error("❌ 屏幕监控器初始化失败")
                return False
            
            # 初始化智能监控器
            self.intelligent_monitor = IntelligentMonitor(self.screen_monitor) # Pass screen_monitor instance
            if not await self.intelligent_monitor.initialize():
                logger.error("❌ 智能监控器初始化失败")
                return False
            
            # 初始化自动化控制器
            self.automation_controller = AutomationController()
            if not await self.automation_controller.initialize():
                logger.error("❌ 自动化控制器初始化失败")
                return False
            
            # 初始化GPT控制器
            self.gpt_controller = GPTController(
                api_key=config.OPENAI_API_KEY,
                base_url=config.OPENAI_BASE_URL
            )
            
            # 初始化产品经理
            self.product_manager = ProductManager(self.gpt_controller)
            
            logger.info("✅ 所有组件初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ 初始化失败: {e}")
            return False
    
    async def start_monitoring(self):
        """开始监控CURSOR"""
        try:
            if not await self.initialize():
                logger.error("❌ 初始化失败，无法开始监控")
                return
            
            self.is_running = True
            logger.info("👀 开始监控CURSOR...")
            
            # 设置信号处理
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
            
            # 主监控循环
            while self.is_running and not self.should_stop:
                try:
                    await self.monitoring_cycle()
                    await asyncio.sleep(self.monitor_interval)
                    
                except KeyboardInterrupt:
                    logger.info("⏹️ 收到中断信号，正在停止...")
                    break
                except Exception as e:
                    logger.error(f"❌ 监控循环出错: {e}")
                    await asyncio.sleep(5)
    
            await self.cleanup()
                
        except Exception as e:
            logger.error(f"❌ 监控启动失败: {e}")
    
    async def monitoring_cycle(self):
        """单次监控循环 - 优化版：过滤无效内容，完全依赖GPT-4O分析，防止重复处理"""
        try:
            # 获取屏幕截图
            screenshot = await self.screen_monitor.capture_screenshot()
            if not screenshot:
                logger.warning("⚠️ 无法获取屏幕截图")
                return

            # 检测CURSOR窗口状态
            cursor_detected = await self.intelligent_monitor.detect_cursor_window(screenshot)
            if not cursor_detected:
                logger.debug("ℹ️ 未检测到CURSOR窗口")
                return

            # 分析当前状态
            extracted_text = await self.intelligent_monitor.extract_text_from_screenshot(screenshot)
            logger.debug(f"📝 提取文本长度: {len(extracted_text)}字符")

            # 过滤无效内容（如dark_content等OCR错误）
            if not self.is_valid_content(extracted_text):
                logger.debug("🚫 检测到无效内容，跳过本次监控循环")
                return

            # 🔧 增强重复处理检测 - 防止死循环
            if self.is_duplicate_processing(extracted_text):
                # 检查是否需要强制推进
                current_time = time.time()
                stuck_duration = current_time - self.last_progress_time
                if stuck_duration > self.max_stuck_time:  # 2分钟无进展
                    logger.warning(f"🚨 系统卡住 {stuck_duration:.1f}秒，强制重置状态推进")
                    # 清空所有阻止机制
                    self.processed_message_hashes.clear()
                    self.content_repetition_count.clear()
                    self.is_processing_message = False
                    self.last_progress_time = current_time
                    # 强制触发介入
                    await self.handle_gpt_content_analysis_intervention(
                        screenshot, extracted_text,
                        "强制推进：系统卡住超过2分钟",
                        "force_progress"
                    )
                    return
                else:
                    logger.debug("🔄 检测到重复内容或正在处理中，跳过本次循环")
                    return
            
            # 🆕 新增：检测内容是否实质相同（处理OCR微小差异）
            if self.is_substantially_same_content(extracted_text):
                logger.debug("🔁 检测到实质相同的内容，检查是否需要超时介入")
                # 检查是否超过60秒相同内容，如果是，强制触发介入
                current_time = time.time()
                same_content_duration = current_time - self.last_content_change_time
                if same_content_duration > 60:  # 60秒超时
                    logger.warning(f"⏰ 相同内容已持续 {same_content_duration:.1f}秒，强制触发GPT-4O介入")
                    await self.handle_gpt_content_analysis_intervention(
                        screenshot, extracted_text, 
                        f"内容超时：相同内容持续{same_content_duration:.1f}秒", 
                        "timeout_intervention"
                    )
                    return
                else:
                    await self.handle_repeated_content(extracted_text)
                    return

            # 详细日志：显示提取的文本内容预览
            text_preview = extracted_text[:200] if extracted_text else "空内容"
            logger.debug(f"📄 提取文本预览: {text_preview}...")

            # 更新对话历史记录（已经包含内容有效性检查）
            self.update_dialog_history(extracted_text)
            
            # 关键状态检测 - 优化版：移除dark_content相关检测，增加详细日志
            logger.debug("🔍 开始状态检测...")
            
            has_review_changes = self.has_review_changes_signal(extracted_text)  # Review Changes = 完成回复
            cursor_generating = self.is_cursor_processing_error(extracted_text)  # Generating = 正在运行
            content_stuck = self.is_content_stuck(extracted_text)  # 内容卡住检测
            
            # 详细状态日志
            logger.debug(f"🔍 状态检测结果:")
            logger.debug(f"   📋 Review Changes: {has_review_changes}")
            logger.debug(f"   🔄 Generating状态: {cursor_generating}")
            logger.debug(f"   ⏰ 内容卡住: {content_stuck}")
            
            # 更新处理状态
            self.cursor_is_processing = cursor_generating
            
            # 智能决策逻辑：根据用户要求的精确时机进行介入
            should_intervene = False
            intervention_reason = ""
            intervention_type = "normal"
            
            # 1. 最高优先级：Review Changes图案 = CURSOR完成操作，立即分析回复内容
            if has_review_changes:
                should_intervene = True
                intervention_reason = "检测到Review Changes图案，CURSOR已完成当前操作"
                intervention_type = "review_changes_completed"
                logger.info("✅ Review Changes检测 - CURSOR完成操作，开始内容分析")
            
            # 2. Generating状态：CURSOR正在运行中，不干预
            elif cursor_generating:
                logger.debug("🔄 Generating状态 - CURSOR正在运行中，不进行干预")
                should_intervene = False
                # 注意：只有超过1分钟无新内容时，content_stuck才会返回True
            
            # 3. 内容卡住检测：超过阈值时间无变化（Generating状态为1分钟，其他为30秒）
            elif content_stuck:
                should_intervene = True
                intervention_reason = "内容超过阈值时间无变化，需要分析回复内容"
                intervention_type = "content_timeout_analysis"
                logger.info("⏰ 内容超时检测 - 准备分析回复内容并给出新指令")
            
            # 4. 正常完成检测：检测CURSOR回复完成信号
            elif self.is_cursor_response_finished(extracted_text) and not cursor_generating:
                should_intervene = True
                intervention_reason = "检测到CURSOR回复完成，需要分析内容"
                intervention_type = "response_completed"
                logger.info("🎯 回复完成检测 - 开始内容分析")
            
            else:
                logger.debug("✅ 状态正常，无需介入")
            
            # 决策日志
            logger.debug(f"🎯 介入决策: {should_intervene}")
            if should_intervene:
                logger.debug(f"   📝 介入原因: {intervention_reason}")
                logger.debug(f"   🏷️ 介入类型: {intervention_type}")
            
            # 执行介入操作 - 统一使用GPT-4O深度分析
            if should_intervene:
                await self.handle_gpt_content_analysis_intervention(
                    screenshot, extracted_text, intervention_reason, intervention_type
                )
            
        except Exception as e:
            logger.error(f"❌ 监控循环执行失败: {e}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
    
    async def handle_gpt_content_analysis_intervention(self, screenshot: Image.Image, extracted_text: str,
                                            reason: str, intervention_type: str):
        """处理基于GPT-4O深度分析的介入 - 增强版：防止重复处理"""
        try:
            # 设置处理状态锁
            if self.is_processing_message:
                logger.warning("🔒 已有消息正在处理中，跳过当前介入")
                return

            self.is_processing_message = True
            logger.info(f"🤖 GPT-4O深度分析介入: {reason} (类型: {intervention_type})")
            logger.info(f"📄 CURSOR回复内容长度: {len(extracted_text)}字符")

            # 标记内容为已处理
            self.mark_content_as_processed(extracted_text)

            # 获取完整对话上下文
            context = self.get_latest_conversation_context()
            logger.info(f"📋 对话上下文长度: {len(context)}字符")

            # 调用GPT-4O产品经理进行全面分析
            logger.info("🔮 调用GPT-4O产品经理进行深度分析...")
            pm_instruction = await self.generate_gpt_product_manager_instruction(
                screenshot, extracted_text, context, intervention_type
            )

            if not pm_instruction or len(pm_instruction.strip()) < 10:
                logger.warning("⚠️ GPT-4O分析结果为空或过短，使用备用策略")
                pm_instruction = f"根据当前状态，建议继续推进开发。请告诉我你需要什么帮助？({intervention_type})"

            logger.info(f"💡 GPT-4O生成的指令: {pm_instruction[:150]}...")

            # 执行输入操作
            interaction_action = {
                "action_type": "type",
                "value": pm_instruction
            }

            success = await self.ensure_input_focus_and_type(interaction_action)
            if success:
                logger.info("✅ GPT-4O产品经理指令已成功发送")
                # 记录发送的指令
                self.last_instruction_sent = pm_instruction
                self.last_instruction_time = time.time()  # 更新指令发送时间
                # 更新项目状态
                self.update_project_status(pm_instruction, extracted_text)
                # 重置内容变化时间，避免重复介入
                self.last_content_change_time = time.time()
                # 更新进展时间，防止卡住
                self.last_progress_time = time.time()
            else:
                logger.error("❌ GPT-4O指令发送失败")
                
        except Exception as e:
            logger.error(f"❌ GPT-4O深度分析介入处理失败: {e}")
            # 备用处理
            try:
                fallback_instruction = "我注意到你的回复，让我们继续推进开发。请告诉我当前的具体情况和需要什么帮助。"
                interaction_action = {
                    "action_type": "type",
                    "value": fallback_instruction
                }
                await self.ensure_input_focus_and_type(interaction_action)
                logger.info("🔧 备用指令已发送")
                self.last_instruction_time = time.time()  # 更新指令发送时间
            except Exception as fallback_error:
                logger.error(f"❌ 连备用指令都发送失败: {fallback_error}")
        finally:
            # 释放处理状态锁
            self.is_processing_message = False
            logger.debug("🔓 处理状态锁已释放")
    
    async def handle_intelligent_intervention(self, screenshot: Image.Image, extracted_text: str, 
                                            reason: str, intervention_type: str):
        """智能介入处理 - 重定向到GPT-4O方法"""
        logger.info("🔄 重定向到GPT-4O深度分析方法")
        await self.handle_gpt_content_analysis_intervention(screenshot, extracted_text, reason, intervention_type)
    
    async def handle_content_analysis_intervention(self, screenshot: Image.Image, extracted_text: str):
        """内容分析介入 - 重定向到GPT-4O方法"""
        logger.info("🔄 重定向到GPT-4O深度分析方法")
        await self.handle_gpt_content_analysis_intervention(screenshot, extracted_text, "内容分析介入", "content_analysis")
    
    async def handle_review_changes_intervention(self, screenshot: Image.Image, extracted_text: str):
        """Review Changes介入 - 重定向到GPT-4O方法"""
        logger.info("🔄 重定向到GPT-4O深度分析方法")
        await self.handle_gpt_content_analysis_intervention(screenshot, extracted_text, "Review Changes介入", "review_changes")
    
    async def handle_interaction_needed(self, analysis_result: Dict[str, Any], screenshot: Image.Image):
        """处理需要交互的情况"""
        try:
            action = analysis_result.get("action", {})
            action_type = action.get("action_type", "wait")
            
            logger.info(f"🎯 执行交互操作: {action_type}")
            
            if action_type == "type":
                # 这是输入操作，需要确保先点击输入框
                await self.ensure_input_focus_and_type(action)
            else:
                # 其他操作直接执行
                await self.automation_controller.execute_action(analysis_result)
            
        except Exception as e:
            logger.error(f"❌ 处理交互时出错: {e}")
    
    async def ensure_input_focus_and_type(self, action: Dict[str, Any]):
        """确保输入框获得焦点后再输入 - 使用新的粘贴输入方式"""
        try:
            text_to_type = action.get("value", "")
            if not text_to_type:
                logger.warning("⚠️ 没有要输入的文本")
                return False
            
            logger.info(f"📝 准备输入文本: {text_to_type[:100]}...")
            
            # 直接使用automation_controller的新方法
            success = await self.automation_controller.perform_chat_input_action(text_to_type)
            
            if success:
                logger.info("✅ 文本输入和发送成功")
                return True
            else:
                logger.error("❌ 文本输入或发送失败")
                return False
            
        except Exception as e:
            logger.error(f"❌ 确保输入焦点并输入时出错: {e}")
            return False
    
    async def check_stuck_status(self, screenshot: Image.Image):
        """检查卡住状态"""
        try:
            # 计算截图哈希
            screenshot_hash = str(hash(screenshot.tobytes()))
            
            if self.last_screenshot_hash == screenshot_hash:
                stuck_duration = time.time() - self.last_interaction_time
                if stuck_duration > self.stuck_detection_time:
                    logger.warning(f"⚠️ 检测到卡住状态，已持续 {stuck_duration:.1f} 秒")
                    await self.handle_stuck_situation(int(stuck_duration))
            else:
                self.last_screenshot_hash = screenshot_hash
                self.last_interaction_time = time.time()
                        
        except Exception as e:
            logger.error(f"❌ 检查卡住状态时出错: {e}")
    
    async def handle_stuck_situation(self, stuck_duration: int):
        """处理卡住情况"""
        try:
            logger.info(f"🔧 处理卡住情况，持续时间: {stuck_duration} 秒")
            
            screenshot = await self.screen_monitor.capture_screenshot()
            if screenshot:
                suggestion = self.gpt_controller.suggest_continuation(screenshot, stuck_duration)
                
                if suggestion.get("action"):
                    await self.automation_controller.execute_action(suggestion)
                    
        except Exception as e:
            logger.error(f"❌ 处理卡住情况时出错: {e}")
    
    async def product_manager_review(self, screenshot: Image.Image, completed_text: str):
        """产品经理质量检查"""
        try:
            logger.info("👔 启动产品经理质量检查...")
            
            # 调用正确的方法名 - 这是同步方法，不需要await
            review_result = self.product_manager.analyze_development_completion(
                screenshot, completed_text, "."
            )
            
            logger.info(f"📊 本地质量评分: {review_result.get('quality_score', 0):.2f}")
            
            # 如果质量分数较低，请求GPT深度分析
            if review_result.get('quality_score', 0) < 0.8:
                logger.info("🔍 质量分数较低，请求GPT深度分析...")
                try:
                    gpt_analysis = self.gpt_controller.analyze_completed_task(
                        screenshot, completed_text, "监控检测到的完成内容"
                    )
                    
                    logger.info(f"🤖 GPT完成任务分析: {gpt_analysis.get('action', {}).get('action_type', 'unknown')}")
                    
                    # 根据GPT分析结果决定是否需要交互
                    action_type = gpt_analysis.get('action', {}).get('action_type', '')
                    if action_type in ['continue_conversation', 'provide_feedback', 'suggest_improvements']:
                        logger.info("🚀 根据GPT分析结果，需要执行交互操作...")
                        
                        # 提取GPT建议的内容
                        master_analysis = gpt_analysis.get('master_analysis', '')
                        next_strategy = gpt_analysis.get('next_strategy', '')
                        
                        # 构建反馈消息
                        if master_analysis or next_strategy:
                            message_content = f"代码完成质量分析报告：\n\n{master_analysis[:200]}...\n\n建议行动：{next_strategy[:100]}..."
                        else:
                            # 使用质量报告生成
                            issues = review_result.get('issues', [])
                            recommendations = review_result.get('recommendations', [])
                            
                            message_content = f"代码实现已完成，但发现{len(issues)}个问题需要改进：\n"
                            for issue in issues[:3]:  # 只显示前3个问题
                                message_content += f"- {issue.get('issue', str(issue))}\n"
                            
                            if recommendations:
                                message_content += "\n建议优化方向：\n"
                                for rec in recommendations[:2]:  # 只显示前2个建议
                                    message_content += f"- {rec}\n"
                        
                        # 构造交互动作
                        interaction_action = {
                            "action_type": "type",
                            "value": message_content
                        }
                        
                        # 执行交互操作
                        success = await self.ensure_input_focus_and_type(interaction_action)
                        if success:
                            logger.info("✅ 完成信号后的交互操作已执行")
                        else:
                            logger.error("❌ 交互操作执行失败")
                    else:
                        logger.info("📋 GPT分析结果显示暂不需要交互操作")
                        
                except Exception as gpt_error:
                    logger.error(f"❌ GPT深度分析失败: {gpt_error}")
                    # GPT分析失败时，仍然发送基于质量报告的反馈
                    issues = review_result.get('issues', [])
                    message_content = f"代码质量检查完成，发现{len(issues)}个需要改进的问题，建议进行代码审查和优化。"
                    
                    interaction_action = {
                        "action_type": "type",
                        "value": message_content
                    }
                    
                    success = await self.ensure_input_focus_and_type(interaction_action)
                    if success:
                        logger.info("🔧 备用质量反馈已发送")
                    
            else:
                logger.info("✅ 代码质量良好，发送完成确认...")
                
                # 高质量代码的确认消息
                confirmation_message = "代码实现完成，质量检查通过。请进行最终审查。"
                
                interaction_action = {
                    "action_type": "type",
                    "value": confirmation_message
                }
                
                success = await self.ensure_input_focus_and_type(interaction_action)
                if success:
                    logger.info("✅ 高质量完成确认已发送")
                
        except Exception as e:
            logger.error(f"❌ 产品经理检查时出错: {e}")
            # 发生错误时也尝试发送一个基本的完成消息
            try:
                error_message = "代码实现已完成，但质量检查遇到问题，请手动审查。"
                interaction_action = {
                    "action_type": "type", 
                    "value": error_message
                }
                await self.ensure_input_focus_and_type(interaction_action)
                logger.info("🔧 错误情况下的完成消息已发送")
            except:
                logger.error("❌ 连错误消息都无法发送")
    
    async def cleanup(self):
        """清理资源"""
        try:
            logger.info("🧹 清理系统资源...")
            
            self.is_running = False
            
            if self.screen_monitor:
                await self.screen_monitor.cleanup()
            
            if self.intelligent_monitor:
                await self.intelligent_monitor.cleanup()
            
            logger.info("✅ 系统清理完成")
            
        except Exception as e:
            logger.error(f"❌ 清理资源时出错: {e}")
    
    def signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"📡 收到信号 {signum}，准备停止...")
        self.should_stop = True
    
    async def monitor_cursor_response(self):
        """监控CURSOR回复状态"""
        try:
            logger.info("👀 开始监控CURSOR回复...")
            self.waiting_for_cursor_response = True
            
            start_time = time.time()
            timeout = 120
            
            while self.waiting_for_cursor_response and time.time() - start_time < timeout:
                screenshot = await self.screen_monitor.capture_screenshot()
                if screenshot:
                    if self.intelligent_monitor.region_selected and self.intelligent_monitor.chat_regions:
                        main_chat_region = self.intelligent_monitor.chat_regions[0]
                        region_text = self.intelligent_monitor.window_selector.extract_region_text(
                            screenshot, main_chat_region
                        )
                        
                        if region_text and self.is_new_response(region_text):
                            logger.info("✅ 检测到CURSOR新回复")
                            self.waiting_for_cursor_response = False
                            return True

                await asyncio.sleep(2)
            
            if time.time() - start_time >= timeout:
                logger.warning("⏰ CURSOR回复监控超时")
                self.waiting_for_cursor_response = False
            
            return False
            
        except Exception as e:
            logger.error(f"❌ 监控CURSOR回复时出错: {e}")
            self.waiting_for_cursor_response = False
            return False
    
    def is_new_response(self, current_text: str) -> bool:
        """检查是否是新的回复"""
        return len(current_text) > 50 and "assistant" in current_text.lower()

    def is_cursor_processing_error(self, text: str) -> bool:
        """检测CURSOR是否正在处理错误"""
        if not text:
            return False
        
        text_lower = text.lower()
        
        # 1. 优先检测"Generating"图案 - 表示CURSOR正在运行中，不应干预
        if "generating" in text_lower:
            logger.info("🔄 检测到Generating状态，CURSOR正在运行中")
            return True
        
        # 2. 检查其他处理关键词
        for keyword in self.processing_keywords:
            if keyword.lower() in text_lower:
                return True
        
        # 3. 检查是否有进度指示符（如点点点、百分比等）
        if "..." in text or "。。。" in text:
            return True
        
        # 4. 检查是否有时间戳但内容在变化（表示正在生成内容）
        if len(text) > len(self.last_dialog_content) + 50:  # 内容显著增加
            # 检查是否包含生成、处理相关的词汇
            processing_indicators = ["生成", "处理", "分析", "创建", "正在", "generating", "processing", "creating"]
            if any(indicator in text_lower for indicator in processing_indicators):
                return True
            
        return False
    
    def has_review_changes_signal(self, text: str) -> bool:
        """检测是否出现了Review Changes信号 - 表示CURSOR完成回复（增强版）"""
        if not text:
            logger.debug("📋 Review Changes检测: 文本为空")
            return False
        
        text_lower = text.lower()
        logger.debug(f"📋 Review Changes检测: 文本长度{len(text)}字符")
        
        # 1. 优先检测"Review Changes"图案 - 这是CURSOR完成操作的明确信号
        if "review changes" in text_lower:
            logger.info("✅ 检测到Review Changes图案，CURSOR已完成当前操作")
            # 记录上下文信息
            pos = text_lower.find("review changes")
            context = text[max(0, pos-30):pos+50] if pos >= 0 else ""
            logger.debug(f"📍 Review Changes上下文: ...{context}...")
            return True
        
        # 2. 检查其他review关键词（增强版）
        review_keywords_extended = self.review_keywords + [
            "review the changes", "审查修改", "查看更改", "检查变更", 
            "review code", "代码审查", "Review Code"
        ]
        
        for keyword in review_keywords_extended:
            if keyword.lower() in text_lower:
                logger.info(f"🔍 检测到review信号: {keyword}")
                # 记录关键词位置
                pos = text_lower.find(keyword.lower())
                context = text[max(0, pos-20):pos+len(keyword)+20] if pos >= 0 else ""
                logger.debug(f"📍 关键词上下文: ...{context}...")
                return True
        
        logger.debug("📋 Review Changes检测: 未找到相关信号")
        return False
    
    def is_cursor_response_finished(self, text: str) -> bool:
        """检测CURSOR是否已完成回复 - 增强版：添加代码显示状态检测"""
        if not text:
            return False
        
        text_lower = text.lower()
        
        # 1. 优先检测Review Changes图案 - 这是最可靠的完成信号
        if "review changes" in text_lower:
            logger.info("✅ 检测到Review Changes图案，CURSOR回复完成")
            return True
        
        # 2. 移除错误的代码显示检测 - 这些只是用户提交的输入内容，不是完成状态
        # 注释：不应该将用户输入的代码片段误判为CURSOR完成状态
        
        # 3. 检测真正的完成信号
        completion_signals = [
            "完成", "done", "finished", "ready", "实现完毕", "运行完成",
            "执行完毕", "测试通过", "部署成功", "任务完成", "处理完成"
        ]
        
        for signal in completion_signals:
            if signal in text_lower:
                logger.info(f"✅ 检测到完成信号: {signal}")
                return True
        
        # 4. 检测特殊的完成模式（CURSOR询问用户下一步）
        question_patterns = [
            "你希望", "需要我", "是否需要", "还有什么", "接下来", "下一步",
            "你想要", "要不要", "可以继续", "请告诉我"
        ]
        
        for pattern in question_patterns:
            if pattern in text_lower:
                logger.info(f"🤔 检测到询问模式: {pattern}")
                return True
        
        return False
    
    def analyze_cursor_reply_content(self, text: str) -> Dict[str, Any]:
        """深度分析CURSOR回复内容（增强版）"""
        analysis = {
            "content_type": "unknown",
            "task_status": "unknown", 
            "has_errors": False,
            "next_action": "continue",
            "key_points": [],
            "raw_content": text[:500],  # 保存原始内容摘要
            "content_length": len(text),
            "detailed_analysis": {},  # 新增：详细分析结果
            "confidence_score": 0.0,  # 新增：分析置信度
            "cursor_intent": "unknown"  # 新增：CURSOR意图分析
        }
        
        if not text:
            return analysis
        
        text_lower = text.lower()
        
        # 1. 增强的内容类型识别
        content_type_patterns = {
            "error_report": ["错误", "error", "异常", "exception", "failed", "失败", "bug", "问题", "报错"],
            "bug_fix": ["修复", "fix", "解决", "solved", "resolved", "修正", "corrected", "fixed"],
            "feature_development": ["功能", "feature", "实现", "implement", "添加", "add", "新增", "开发"],
            "testing": ["测试", "test", "验证", "verify", "检查", "check", "验收", "validation"],
            "deployment": ["部署", "deploy", "发布", "release", "上线", "publish", "启动"],
            "code_implementation": ["代码", "code", "函数", "function", "类", "class", "方法", "method"],
            "documentation": ["文档", "document", "说明", "readme", "注释", "comment"],
            "optimization": ["优化", "optimize", "改进", "improve", "性能", "performance", "refactor"],
            "analysis": ["分析", "analyze", "研究", "investigation", "探索", "explore"]
        }
        
        type_scores = {}
        for content_type, keywords in content_type_patterns.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                type_scores[content_type] = score
        
        if type_scores:
            analysis["content_type"] = max(type_scores, key=type_scores.get)
            analysis["confidence_score"] = type_scores[analysis["content_type"]] / len(text_lower.split()) * 100
        
        # 2. 增强的任务状态识别 (优化版)
        status_patterns = {
            "completed": [
                "完成", "done", "finished", "ready", "成功", "success", "已实现", 
                "实现完毕", "结束", "解决", "修复完成", "开发完成", "测试通过"
            ],
            "in_progress": [
                "进行", "working", "处理", "processing", "开发", "developing", 
                "正在", "继续", "分析", "实现", "构建", "编写"
            ],
            "blocked": [
                "卡住", "stuck", "阻塞", "blocked", "困难", "difficulty", "无法", 
                "不能", "失败", "crash", "崩溃", "异常", "错误", "bug", "问题"
            ],
            "starting": [
                "开始", "start", "初始", "initial", "准备", "prepare", "启动",
                "创建", "建立", "设置"
            ],
            "reviewing": [
                "审查", "review", "检查", "check", "评估", "evaluate", "验证", "测试"
            ],
            "waiting": [
                "等待", "wait", "pending", "暂停", "pause", "稍候", "请稍等"
            ]
        }
        
        status_scores = {}
        text_words = text_lower.split()
        
        for status, keywords in status_patterns.items():
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    # 精确匹配得分更高
                    if keyword in text_words:
                        score += 2
                    else:
                        score += 1
            
            if score > 0:
                status_scores[status] = score
        
        # 特殊规则：如果有错误指示符，很可能是blocked状态
        if analysis["has_errors"]:
            status_scores["blocked"] = status_scores.get("blocked", 0) + 3
        
        # 选择得分最高的状态
        if status_scores:
            analysis["task_status"] = max(status_scores, key=status_scores.get)
        
        # 3. 错误检测增强
        error_indicators = ["error", "错误", "exception", "failed", "失败", "bug", "问题", "异常", "报错", "crash"]
        analysis["has_errors"] = any(indicator in text_lower for indicator in error_indicators)
        
        # 4. 新增：CURSOR意图分析 (优化版)
        intent_patterns = {
            "seeking_feedback": [
                "如何", "怎么", "建议", "意见", "反馈", "你觉得", "是否", "怎么样", 
                "什么建议", "改进", "评价", "看法", "想法", "应该", "可以吗",
                "不确定", "需要确认", "请明确", "是否需要", "帮助"
            ],
            "providing_update": [
                "已完成", "完成了", "更新", "进展", "状态", "实现了", "做了",
                "添加了", "修改了", "优化了", "升级了", "开发完成", "测试完成"
            ],
            "requesting_clarification": [
                "不确定", "需要确认", "请明确", "是否需要", "什么意思", "具体",
                "详细", "解释", "说明", "澄清"
            ],
            "showing_results": [
                "结果", "输出", "效果", "展示", "演示", "显示", "生成了", "产生了"
            ],
            "reporting_issue": [
                "遇到", "发现", "出现", "问题", "错误", "异常", "失败", "bug",
                "故障", "不工作", "崩溃", "crash"
            ],
            "proposing_solution": [
                "建议", "可以", "方案", "解决", "考虑", "推荐", "应该", "尝试",
                "用", "采用", "实现", "修复", "处理"
            ]
        }
        
        intent_scores = {}
        text_words = text_lower.split()
        
        for intent, keywords in intent_patterns.items():
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    # 精确匹配得分更高
                    if keyword in text_words:
                        score += 2
                    else:
                        score += 1
            
            if score > 0:
                intent_scores[intent] = score
        
        # 特殊规则：问句通常是寻求反馈
        if "？" in text or "?" in text:
            intent_scores["seeking_feedback"] = intent_scores.get("seeking_feedback", 0) + 3
        
        # 选择得分最高的意图
        if intent_scores:
            analysis["cursor_intent"] = max(intent_scores, key=intent_scores.get)
        
        # 5. 增强的下一步行动决策
        if analysis["task_status"] == "completed":
            if analysis["content_type"] == "bug_fix":
                analysis["next_action"] = "run_test"
            elif analysis["content_type"] == "feature_development":
                analysis["next_action"] = "run_demo"
            elif analysis["content_type"] == "code_implementation":
                analysis["next_action"] = "run_code"
            elif analysis["cursor_intent"] == "seeking_feedback":
                analysis["next_action"] = "provide_feedback"
            else:
                analysis["next_action"] = "continue_next"
        elif analysis["has_errors"]:
            analysis["next_action"] = "fix_errors"
        elif analysis["task_status"] == "blocked":
            analysis["next_action"] = "solve_problem"
        elif analysis["cursor_intent"] == "seeking_feedback":
            analysis["next_action"] = "provide_guidance"
        elif analysis["cursor_intent"] == "requesting_clarification":
            analysis["next_action"] = "clarify_requirements"
        else:
            analysis["next_action"] = "continue"
        
        # 6. 增强的关键信息提取
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if line and len(line) > 10:  # 过滤太短的行
                # 包含重要标记的行
                if any(marker in line for marker in ["1.", "2.", "3.", "-", "*", "•", "①", "②", "③"]):
                    analysis["key_points"].append(line[:150])
                # 包含重要关键词的行
                elif any(keyword in line.lower() for keyword in [
                    "重要", "注意", "提醒", "建议", "问题", "错误", "关键", "核心", 
                    "主要", "特别", "务必", "必须", "需要", "应该"
                ]):
                    analysis["key_points"].append(line[:150])
                # 包含代码或技术细节的行
                elif any(keyword in line for keyword in ["def ", "class ", "import ", "function", "method"]):
                    analysis["key_points"].append(f"代码: {line[:100]}")
        
        # 7. 详细分析结果
        analysis["detailed_analysis"] = {
            "word_count": len(text.split()),
            "line_count": len(lines),
            "contains_code": any(keyword in text for keyword in ["def ", "class ", "import ", "{", "}", "function"]),
            "contains_urls": "http" in text or "https" in text,
            "contains_numbers": any(char.isdigit() for char in text),
            "type_confidence": analysis["confidence_score"],
            "primary_topics": list(type_scores.keys())[:3] if type_scores else [],
            "sentiment": "positive" if any(word in text_lower for word in ["好", "成功", "完成", "excellent", "good", "success"]) else 
                       "negative" if any(word in text_lower for word in ["错误", "失败", "问题", "error", "failed", "issue"]) else "neutral"
        }
        
        # 提高置信度计算精度
        if analysis["content_type"] != "unknown" and analysis["task_status"] != "unknown":
            analysis["confidence_score"] = min(95.0, analysis["confidence_score"] + 20.0)
        
        logger.info(f"🔍 深度内容分析完成: 类型={analysis['content_type']}, 状态={analysis['task_status']}, 意图={analysis['cursor_intent']}, 置信度={analysis['confidence_score']:.1f}%")
        
        return analysis
    
    def update_dialog_history(self, current_text: str):
        """更新对话历史记录 - 优化版：清理无效历史"""
        if not current_text:
            return
            
        # 清理包含dark_content等OCR错误特征的历史记录
        if not self.is_valid_content(current_text):
            logger.debug("🧹 检测到无效内容（如dark_content），跳过历史记录更新")
            return
        
        # 检查内容是否真的发生了变化
        if current_text != self.last_dialog_content:
            # 内容发生了变化
            self.last_content_change_time = time.time()
            
            # 保存到历史记录
            timestamp = time.strftime("%H:%M:%S")
            self.dialog_history.append({
                "timestamp": timestamp,
                "content": current_text[:500],  # 只保存前500字符
                "full_content": current_text
            })
            
            # 保持历史记录数量在合理范围内
            if len(self.dialog_history) > 20:
                self.dialog_history = self.dialog_history[-15:]  # 保留最近15条
            
            # 管理对话轮次
            self.manage_conversation_turns(current_text, timestamp)
            
            self.last_dialog_content = current_text
            logger.debug(f"📝 更新对话历史，当前记录数: {len(self.dialog_history)}")
        else:
            logger.debug("📋 内容无变化，不更新历史记录")
    
    def is_valid_content(self, text: str) -> bool:
        """检查内容是否有效，过滤OCR错误等无效内容"""
        if not text or len(text.strip()) < 10:
            return False
        
        # 过滤OCR失败的特征内容
        invalid_patterns = [
            "dark_content", "detected_features:", "high_brightness_content",
            "text_like_patterns", "stable_content", "unknown_content"
        ]
        
        text_lower = text.lower()
        if any(pattern in text_lower for pattern in invalid_patterns):
            logger.debug(f"🚫 过滤无效内容: {text[:50]}...")
            return False
        
        return True

    def is_duplicate_processing(self, current_text: str) -> bool:
        """检测是否为重复处理 - 防止对同一条消息重复处理"""
        try:
            # 1. 检查是否正在处理消息
            if self.is_processing_message:
                logger.debug("🔒 当前正在处理消息，跳过重复处理")
                return True

            # 2. 检查指令发送冷却时间
            current_time = time.time()
            time_since_last_instruction = current_time - self.last_instruction_time
            if time_since_last_instruction < self.instruction_cooldown:
                logger.debug(f"❄️ 指令冷却中，距上次发送 {time_since_last_instruction:.1f}秒 (需要{self.instruction_cooldown}秒)")
                return True

            # 3. 计算内容哈希
            content_hash = self.calculate_content_hash(current_text)

            # 4. 检查是否已处理过相同内容
            if content_hash in self.processed_message_hashes:
                logger.debug(f"🔄 内容已处理过，哈希: {content_hash[:8]}...")
                return True

            # 5. 新增：检查内容重复次数限制
            if current_text in self.content_repetition_count:
                self.content_repetition_count[current_text] += 1
                if self.content_repetition_count[current_text] > self.max_same_content_processing:
                    logger.debug(f"🚫 相同内容处理次数超限 ({self.content_repetition_count[current_text]}/{self.max_same_content_processing})")
                    return True
            else:
                self.content_repetition_count[current_text] = 1

            # 6. 新增：检测是否为自己刚发送的指令的回显
            if self.last_instruction_sent and len(self.last_instruction_sent) > 20:
                if self.last_instruction_sent in current_text:
                    logger.debug("🔁 检测到指令回显，跳过处理")
                    return True

            # 7. 修复：检测是否为产品经理的自我回复（更严格的判断条件）
            # 产品经理的回复应该是在聊天输入框，而不是CURSOR的回复区域
            # 只有非常简短且包含明确的回复确认词汇才认为是产品经理回复
            pm_reply_indicators = [
                "收到", "明白了", "好的，我来", "了解，接下来", "收到指令", "我会"
            ]
            # 检查是否是很短的确认性回复，且不包含技术内容
            is_pm_reply = (
                len(current_text) < 50 and  # 更严格的长度限制
                any(indicator in current_text for indicator in pm_reply_indicators) and
                not any(tech_word in current_text for tech_word in [
                    "pygame", "python", "import", "class", "def", "function", 
                    "代码", "文件", "实现", "开发", "创建", "修改", "Snake", "game"
                ])
            )
            if is_pm_reply:
                logger.info("🚫 检测到这是产品经理自己的回复，跳过处理")
                return True

            # 8. 检查与上次处理内容的相似度（放宽限制）
            if self.last_processed_content_hash:
                similarity = self.calculate_content_similarity(current_text, self.last_dialog_content)
                if similarity > 0.99:  # 修复：从95%提高到99%，只有几乎完全相同才认为重复
                    logger.debug(f"📊 内容相似度过高: {similarity:.2%}，可能是重复处理")
                    return True

            # 9. 新增：管理内容重复计数器大小，防止内存泄漏
            if len(self.content_repetition_count) > 100:
                # 保留最近50个记录
                keys_to_remove = list(self.content_repetition_count.keys())[:-50]
                for key in keys_to_remove:
                    del self.content_repetition_count[key]
                logger.debug("🧹 清理内容重复计数器")

            logger.debug(f"✅ 内容检查通过，哈希: {content_hash[:8]}...")
            return False

        except Exception as e:
            logger.error(f"❌ 重复处理检测失败: {e}")
            return False

    def calculate_content_hash(self, text: str) -> str:
        """计算内容哈希值"""
        import hashlib
        # 标准化文本：去除空白字符、转小写
        normalized_text = ''.join(text.split()).lower()
        return hashlib.md5(normalized_text.encode('utf-8')).hexdigest()

    def calculate_content_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本的相似度"""
        if not text1 or not text2:
            return 0.0

        # 简单的字符级相似度计算
        len1, len2 = len(text1), len(text2)
        if len1 == 0 and len2 == 0:
            return 1.0
        if len1 == 0 or len2 == 0:
            return 0.0

        # 计算最长公共子序列长度
        common_chars = sum(1 for c1, c2 in zip(text1, text2) if c1 == c2)
        max_len = max(len1, len2)
        return common_chars / max_len

    def mark_content_as_processed(self, content: str):
        """标记内容为已处理"""
        try:
            content_hash = self.calculate_content_hash(content)
            self.processed_message_hashes.add(content_hash)
            self.last_processed_content_hash = content_hash

            # 新增：如果是发送指令后的内容，记录指令内容哈希
            if hasattr(self, 'last_instruction_sent') and self.last_instruction_sent:
                instruction_hash = self.calculate_content_hash(self.last_instruction_sent)
                self.last_sent_instruction_hash = instruction_hash

            # 限制哈希集合大小
            if len(self.processed_message_hashes) > self.max_processed_hashes:
                # 移除最旧的哈希（简单实现：清理一半）
                hashes_list = list(self.processed_message_hashes)
                self.processed_message_hashes = set(hashes_list[-self.max_processed_hashes//2:])
                logger.debug(f"🧹 清理已处理哈希，保留 {len(self.processed_message_hashes)} 个")

            logger.debug(f"✅ 内容已标记为处理，哈希: {content_hash[:8]}...")

        except Exception as e:
            logger.error(f"❌ 标记内容处理状态失败: {e}")

    def manage_conversation_turns(self, current_text: str, timestamp: str):
        """管理完整的对话轮次"""
        try:
            # 检测是否是新的用户指令（通常包含明确的请求词汇）
            user_indicators = ["请", "帮我", "实现", "修复", "优化", "添加", "创建", "please", "help", "implement", "fix", "optimize", "add", "create"]
            is_user_input = any(indicator in current_text.lower() for indicator in user_indicators)
            
            # 检测是否是CURSOR的回复结束（包含完成、结束等标识）
            completion_indicators = ["完成", "结束", "done", "finished", "completed", "ready", "实现完毕"]
            is_cursor_completion = any(indicator in current_text.lower() for indicator in completion_indicators)
            
            if is_user_input and not self.cursor_is_processing:
                # 开始新的对话轮次
                if self.current_turn:
                    # 结束上一轮对话
                    self.conversation_turns.append(self.current_turn)
                
                self.current_turn = {
                    "start_time": timestamp,
                    "user_request": current_text,
                    "cursor_responses": [],
                    "status": "active"
                }
                logger.info(f"🆕 开始新对话轮次: {current_text[:50]}...")
                
            elif self.current_turn and self.current_turn["status"] == "active":
                # 添加CURSOR的回复到当前轮次
                self.current_turn["cursor_responses"].append({
                    "timestamp": timestamp,
                    "content": current_text
                })
                
                if is_cursor_completion:
                    # 标记当前轮次完成
                    self.current_turn["status"] = "completed"
                    self.current_turn["end_time"] = timestamp
                    logger.info(f"✅ 对话轮次完成: {self.current_turn['user_request'][:30]}...")
            
            # 保持轮次记录数量合理
            if len(self.conversation_turns) > 10:
                self.conversation_turns = self.conversation_turns[-7:]  # 保留最近7轮
                
        except Exception as e:
            logger.error(f"❌ 管理对话轮次时出错: {e}")
    
    def get_latest_conversation_context(self) -> str:
        """获取最近的完整对话上下文"""
        try:
            if not self.conversation_turns and not self.current_turn:
                return "暂无对话历史"
            
            # 获取最近完成的对话轮次
            latest_completed = None
            if self.conversation_turns:
                latest_completed = self.conversation_turns[-1]
            
            # 获取当前进行中的对话轮次
            current_active = self.current_turn if self.current_turn and self.current_turn["status"] == "active" else None
            
            context_parts = []
            
            # 添加最近完成的对话
            if latest_completed:
                context_parts.append(f"上一轮对话：")
                context_parts.append(f"用户请求: {latest_completed['user_request'][:200]}")
                if latest_completed['cursor_responses']:
                    last_response = latest_completed['cursor_responses'][-1]['content']
                    context_parts.append(f"CURSOR回复: {last_response[:200]}")
            
            # 添加当前进行的对话
            if current_active:
                context_parts.append(f"当前对话：")
                context_parts.append(f"用户请求: {current_active['user_request'][:200]}")
                if current_active['cursor_responses']:
                    responses_summary = f"CURSOR已回复{len(current_active['cursor_responses'])}次"
                    latest_response = current_active['cursor_responses'][-1]['content']
                    context_parts.append(f"{responses_summary}，最新回复: {latest_response[:200]}")
            
            return "\n".join(context_parts) if context_parts else "暂无有效对话上下文"
            
        except Exception as e:
            logger.error(f"❌ 获取对话上下文时出错: {e}")
            return "获取对话上下文失败"
    
    async def generate_targeted_instruction(self, screenshot: Image.Image, 
                                          cursor_reply: str, 
                                          content_analysis: Dict[str, Any],
                                          conversation_context: str) -> str:
        """根据内容分析生成针对性指令（新增方法）"""
        try:
            # 构建专门的分析上下文，让GPT-4O了解分析结果
            analysis_context = f"""
内容分析结果：
- 内容类型: {content_analysis['content_type']}
- 任务状态: {content_analysis['task_status']}
- 是否有错误: {content_analysis['has_errors']}
- 建议行动: {content_analysis['next_action']}
- 关键要点: {'; '.join(content_analysis['key_points'][:3])}

CURSOR回复摘要: {content_analysis['raw_content']}
"""
            
            # 获取项目理解
            project_context = self.load_project_understanding()
            
            # 分析当前阶段
            current_stage = self.analyze_current_development_stage(cursor_reply, conversation_context)
            
            # 调用GPT-4O产品经理分析，传入详细的分析结果
            task_instruction = ""
            if self.project_planner:
                try:
                    task_instruction = self.project_planner.generate_task_instruction(cursor_reply)
                except Exception as e:
                    logger.error(f"生成任务指令失败: {e}")

            pm_reply = self.gpt_controller.analyze_as_product_manager(
                screenshot=screenshot,
                cursor_reply=f"{analysis_context}\n\n原始回复内容:\n{cursor_reply}",
                project_context=project_context,
                conversation_history=conversation_context,
                current_stage=f"{current_stage} (建议行动: {content_analysis['next_action']})",
                task_instruction=task_instruction
            )
            
            # 根据next_action调整指令
            enhanced_instruction = self.enhance_instruction_by_action(pm_reply, content_analysis['next_action'])
            
            logger.info(f"✅ 针对性指令生成完成: {enhanced_instruction[:50]}...")
            return enhanced_instruction
            
        except Exception as e:
            logger.error(f"❌ 针对性指令生成失败: {e}")
            # 根据分析结果生成备用指令
            return self.generate_fallback_instruction(content_analysis)
    
    def enhance_instruction_by_action(self, base_instruction: str, next_action: str) -> str:
        """根据建议行动增强指令（新增方法）"""
        action_enhancements = {
            "run_test": "建议现在运行测试验证修复效果。请执行相关测试用例，确保问题已彻底解决。",
            "run_demo": "功能开发完成，建议运行演示验证效果。请启动程序展示新功能的工作情况。",
            "run_code": "代码实现完成，建议立即运行验证。请执行代码确认功能正常工作。",
            "continue_next": "当前任务完成良好，可以继续下一阶段开发。建议明确下一个开发目标。",
            "fix_errors": "检测到错误信息，请先分析具体错误原因，然后提供修复方案。",
            "solve_problem": "发现开发阻塞，请详细说明遇到的具体问题，我来协助解决。"
        }
        
        enhancement = action_enhancements.get(next_action, "")
        if enhancement:
            return f"{base_instruction}\n\n{enhancement}"
        return base_instruction
    
    def generate_fallback_instruction(self, content_analysis: Dict[str, Any]) -> str:
        """生成备用指令（新增方法）"""
        if content_analysis["next_action"] == "run_test":
            return "看起来修复已完成，现在请运行测试验证一下修复效果，确保问题彻底解决。"
        elif content_analysis["next_action"] == "run_demo":
            return "功能开发完成了，请运行演示一下新功能的效果，让我看看实际工作情况。"
        elif content_analysis["next_action"] == "run_code":
            return "代码实现完成，请执行运行一下，验证功能是否正常工作。"
        elif content_analysis["has_errors"]:
            return "我注意到有错误信息，请先分析一下具体的错误原因，然后我们一起解决。"
        else:
            return "收到你的更新。根据当前进展，我们继续推进下一步。请告诉我你希望接下来做什么？"
    
    async def handle_stuck_intervention(self, screenshot: Image.Image, extracted_text: str):
        """处理卡住情况的介入"""
        try:
            logger.info("🔧 处理卡住情况介入...")
            
            # 获取完整对话上下文
            context = self.get_latest_conversation_context()
            logger.info(f"📋 卡住时的对话上下文: {context[:100]}...")
            
            # 使用GPT-4O产品经理分析生成回复
            pm_instruction = await self.generate_gpt_product_manager_instruction(
                screenshot, extracted_text, context, "卡住情况"
            )
            logger.info(f"🎯 GPT-4O产品经理指令: {pm_instruction[:100]}...")
            
            # 执行输入操作
            interaction_action = {
                "action_type": "type",
                "value": pm_instruction
            }
            
            success = await self.ensure_input_focus_and_type(interaction_action)
            if success:
                logger.info("✅ 卡住情况GPT产品经理指令已发送")
                # 记录发送的指令
                self.last_instruction_sent = pm_instruction
                # 更新项目状态
                self.update_project_status(pm_instruction, extracted_text)
                # 重置内容变化时间，避免重复介入
                self.last_content_change_time = time.time()
            else:
                logger.error("❌ 卡住情况指令发送失败")
                
        except Exception as e:
            logger.error(f"❌ 卡住情况介入处理失败: {e}")
    
    async def generate_gpt_product_manager_instruction(self, screenshot: Image.Image, 
                                                     cursor_reply: str, 
                                                     conversation_context: str, 
                                                     intervention_type: str) -> str:
        """使用GPT-4O生成指令，结合项目规划器提供的任务上下文"""
        try:
            logger.info(f"🤖 调用GPT-4O生成指令，介入类型: {intervention_type}")
            
            # 获取项目上下文
            if self.project_planner:
                # 使用项目规划器提供的具体任务上下文
                project_context = self.project_planner.get_project_context()
                current_task = self.project_planner.get_current_task()
                
                # 检查任务是否完成，更新项目进度
                if current_task and self.project_planner.is_task_completed(cursor_reply, current_task):
                    logger.info(f"✅ 检测到任务完成: {current_task['title']}")
                    self.project_planner.mark_task_completed(current_task['id'])
                    self.project_planner.current_task_index += 1
                    self.project_planner._save_progress()
                
                # 获取更新后的项目上下文
                project_context = self.project_planner.get_project_context()
                current_stage = f"当前任务阶段 - {self.project_planner.get_current_task()['title'] if self.project_planner.get_current_task() else '项目完成'}"
            else:
                # 回退到默认项目理解
                project_context = self.load_project_understanding()
                current_stage = self.analyze_current_development_stage(cursor_reply, conversation_context)
            
            # 调用GPT-4O产品经理分析，传入项目规划器的上下文
            task_instruction = ""
            if self.project_planner:
                try:
                    task_instruction = self.project_planner.generate_task_instruction(cursor_reply)
                except Exception as e:
                    logger.error(f"生成任务指令失败: {e}")

            pm_reply = self.gpt_controller.analyze_as_product_manager(
                screenshot=screenshot,
                cursor_reply=cursor_reply,
                project_context=project_context,
                conversation_history=conversation_context,
                current_stage=current_stage,
                task_instruction=task_instruction
            )
            
            logger.info(f"✅ GPT-4O指令生成完成: {pm_reply[:50]}...")
            return pm_reply
            
        except Exception as e:
            logger.error(f"❌ GPT-4O指令生成失败: {e}")
            # 返回简洁的备用指令
            if intervention_type == "review_changes":
                return "任务完成了！请继续下一个开发步骤。"
            else:
                return "请继续当前开发任务，有问题的话提供具体错误信息。"

    def generate_product_manager_instruction(self, current_text: str) -> str:
        """生成产品经理指令 - 保持向后兼容性，但推荐使用GPT版本"""
        logger.warning("⚠️ 使用了旧版产品经理指令生成，建议使用GPT-4O版本")
        try:
            # 读取项目理解文档
            project_context = self.load_project_understanding()
            
            # 获取对话上下文
            context = self.get_latest_conversation_context()
            
            # 基于CURSOR回复的具体内容分析当前阶段
            current_stage = self.analyze_current_development_stage(current_text, context)
            
            # 根据项目理解和当前阶段生成具体指令
            instruction = self.generate_contextual_instruction(current_text, current_stage, project_context)
            
            return instruction
            
        except Exception as e:
            logger.error(f"❌ 生成产品经理指令时出错: {e}")
            return "继续当前开发任务，遇到问题请提供具体错误信息。"
    
    def load_project_understanding(self) -> str:
        """加载项目理解文档"""
        try:
            with open("产品经理项目理解.txt", "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            # 如果文件不存在，返回基础项目理解
            return "CURSOR自动化监督系统：智能监控CURSOR IDE，自动处理人工干预，实现全自动编程。"
        except Exception as e:
            logger.error(f"❌ 读取项目理解文档失败: {e}")
            return "项目理解文档读取失败，使用默认配置。"
    
    def analyze_current_development_stage(self, current_text: str, context: str) -> str:
        """分析当前开发阶段"""
        text_lower = current_text.lower()
        
        # 基于CURSOR回复内容判断开发阶段
        if any(keyword in text_lower for keyword in ["功能目标", "核心要点", "需求"]):
            return "需求分析阶段"
        elif any(keyword in text_lower for keyword in ["代码实现", "核心功能", "编写"]):
            return "代码实现阶段"
        elif any(keyword in text_lower for keyword in ["异常处理", "边界情况", "bug"]):
            return "异常处理阶段"
        elif any(keyword in text_lower for keyword in ["注释", "文档", "readme"]):
            return "文档完善阶段"
        elif any(keyword in text_lower for keyword in ["单元测试", "集成测试", "验证"]):
            return "测试验证阶段"
        elif any(keyword in text_lower for keyword in ["提交", "推送", "交付"]):
            return "交付部署阶段"
        elif any(keyword in text_lower for keyword in ["监控功能", "智能交互", "产品经理"]):
            return "核心功能优化阶段"
        else:
            return "常规开发阶段"
    
    def generate_contextual_instruction(self, current_text: str, stage: str, project_context: str) -> str:
        """根据上下文生成具体指令"""
        
        # 基于当前正在开发的CURSOR监督系统的特点，生成针对性指令
        if "智能交互" in current_text or "产品经理" in current_text:
            return self.generate_supervisor_system_instruction(current_text, stage)
        elif "监控" in current_text or "检测" in current_text:
            return self.generate_monitoring_instruction(current_text, stage)
        elif "自动化" in current_text or "控制" in current_text or "操作" in current_text:
            return self.generate_automation_instruction(current_text, stage)
        elif "GPT" in current_text or "分析" in current_text or "AI" in current_text:
            return self.generate_ai_analysis_instruction(current_text, stage)
        elif "准确性" in current_text or "精度" in current_text or "优化" in current_text:
            return self.generate_optimization_focused_instruction(current_text, stage)
        elif "坐标" in current_text or "定位" in current_text:
            return self.generate_positioning_instruction(current_text, stage)
        else:
            return self.generate_general_instruction(current_text, stage)
    
    def generate_supervisor_system_instruction(self, current_text: str, stage: str) -> str:
        """生成监督系统相关指令"""
        if stage == "需求分析阶段":
            return "很好！请细化智能交互功能的具体需求：1)什么情况下介入对话 2)如何识别CURSOR处理状态 3)产品经理指令的具体格式。先明确这些核心需求。"
        elif stage == "代码实现阶段":
            return "开始实现智能交互核心逻辑：重点关注状态检测算法、对话轮次管理、指令生成策略。确保与现有监控系统的无缝集成。"
        elif stage == "测试验证阶段":
            return "对智能交互功能进行全面测试：1)模拟不同CURSOR状态 2)验证指令生成准确性 3)测试与监控系统的协同工作。记录测试结果。"
        else:
            return "继续完善监督系统的智能交互能力，确保能准确识别CURSOR状态并生成合适的产品经理指令。"
    
    def generate_monitoring_instruction(self, current_text: str, stage: str) -> str:
        """生成监控功能相关指令"""
        if stage == "需求分析阶段":
            return "明确监控功能需求：需要监控哪些CURSOR状态？如何提高检测准确性？监控频率如何优化？"
        elif stage == "代码实现阶段":
            return "实现监控核心功能：屏幕截图、OCR识别、状态判断逻辑。重点优化检测算法的准确性和性能。"
        elif stage == "测试验证阶段":
            return "测试监控功能稳定性：长时间运行测试、不同场景下的检测准确率、内存和CPU使用情况。"
        else:
            return "继续优化监控系统，提高CURSOR状态检测的准确性和响应速度。"
    
    def generate_automation_instruction(self, current_text: str, stage: str) -> str:
        """生成自动化功能相关指令"""
        if stage == "需求分析阶段":
            return "明确自动化操作需求：需要自动化哪些操作？如何确保操作的安全性？如何处理操作失败？"
        elif stage == "代码实现阶段":
            return "实现自动化控制逻辑：精确的坐标定位、输入操作、安全检查机制。确保操作的可靠性。"
        elif stage == "测试验证阶段":
            return "测试自动化操作准确性：不同分辨率下的兼容性、操作成功率、安全机制有效性。"
        else:
            return "继续完善自动化操作系统，提高操作精确性和安全性。"
    
    def generate_ai_analysis_instruction(self, current_text: str, stage: str) -> str:
        """生成AI分析功能相关指令"""
        if stage == "需求分析阶段":
            return "明确AI分析需求：GPT-4O需要分析什么内容？如何优化提示词？如何处理分析结果？"
        elif stage == "代码实现阶段":
            return "实现GPT分析逻辑：图像预处理、提示词优化、结果解析、错误处理。确保分析的准确性。"
        elif stage == "测试验证阶段":
            return "测试AI分析准确性：不同场景下的识别率、响应时间、成本控制。优化分析效果。"
        else:
            return "继续优化AI分析能力，提高对CURSOR状态的理解准确性。"
    
    def generate_optimization_focused_instruction(self, current_text: str, stage: str) -> str:
        """生成优化专项指令"""
        if "监控" in current_text:
            return "监控系统精度优化任务：1)分析当前检测准确率瓶颈 2)优化OCR识别算法 3)改进状态判断逻辑 4)增加多重验证机制。目标提升检测准确率到95%以上。"
        elif "检测" in current_text:
            return "检测功能优化专项：重点改进状态识别算法，增强对CURSOR不同状态的区分能力，优化响应时间，确保检测的实时性和准确性。"
        else:
            return f"针对{current_text[:20]}...的优化需求，请制定具体的优化方案：包括性能指标、实现步骤、验证方法。"
    
    def generate_positioning_instruction(self, current_text: str, stage: str) -> str:
        """生成定位相关指令"""
        if "坐标" in current_text and "自动化" in current_text:
            return "自动化坐标定位优化：1)检查屏幕分辨率适配 2)优化元素识别算法 3)增加多点验证机制 4)添加定位失败的回退策略。确保不同环境下的操作准确性。"
        else:
            return "定位功能问题排查：请提供具体的定位错误场景、屏幕分辨率、失败日志，我来制定针对性解决方案。"
    
    def generate_general_instruction(self, current_text: str, stage: str) -> str:
        """生成通用指令"""
        if "错误" in current_text or "异常" in current_text:
            return "发现错误情况，请提供具体错误信息：错误类型、出现场景、堆栈信息。我来帮你分析解决方案。"
        elif "完成" in current_text:
            return "功能实现完成后，请进行自测：功能是否符合需求？是否有边界情况未处理？代码质量如何？"
        elif "卡住" in current_text or "问题" in current_text:
            return "遇到开发问题，请详细说明：具体卡在哪个环节？已尝试了什么方法？需要什么样的帮助？"
        else:
            return "根据当前CURSOR监督系统的开发进度，请继续推进核心功能实现，重点关注智能交互和监控精确性。"
    
    def is_content_stuck(self, current_text: str) -> bool:
        """检测内容是否卡住 - 增强版：先验证内容有效性，添加详细日志"""
        
        # 首先检查内容是否有效，无效内容直接返回False
        if not self.is_valid_content(current_text):
            logger.debug("🚫 内容无效，不进行卡住检测")
            return False
        
        # 详细日志记录
        current_time = time.time()
        last_change_duration = current_time - self.last_content_change_time
        
        logger.debug(f"⏰ 卡住检测详情:")
        logger.debug(f"   📝 当前内容长度: {len(current_text)}字符")
        logger.debug(f"   📚 历史内容长度: {len(self.last_dialog_content)}字符")
        logger.debug(f"   🕐 距上次变化: {last_change_duration:.1f}秒")
        
        # 1. 如果内容完全相同，检查超时
        if current_text == self.last_dialog_content:
            stuck_duration = last_change_duration
            
            # 修改卡住检测时间：Generating状态需要1分钟，其他状态保持30秒
            text_lower = current_text.lower()
            if "generating" in text_lower:
                threshold = 60  # 1分钟
                logger.debug(f"🔄 Generating状态检测，当前等待时间: {stuck_duration:.1f}秒 (阈值: {threshold}秒)")
            else:
                threshold = self.stuck_detection_time  # 30秒
                logger.debug(f"📊 普通状态检测，当前等待时间: {stuck_duration:.1f}秒 (阈值: {threshold}秒)")
            
            if stuck_duration > threshold:
                logger.info(f"⏰ 内容卡住检测：已等待{stuck_duration:.1f}秒，超过阈值{threshold}秒")
                logger.debug(f"🔍 卡住内容预览: {current_text[:100]}...")
                return True
            else:
                logger.debug(f"⏰ 内容暂未卡住，继续等待 ({stuck_duration:.1f}/{threshold}秒)")
                
        # 2. 新增：检测内容是否在持续增长（表示CURSOR正在活跃工作）
        elif len(current_text) > len(self.last_dialog_content):
            # 内容在增长，说明CURSOR正在积极输出
            content_growth = len(current_text) - len(self.last_dialog_content)
            logger.debug(f"📈 检测到内容持续增长: +{content_growth}字符，CURSOR正在活跃工作中，不介入")
            
            # 重置内容变化时间，因为有新内容
            self.last_content_change_time = time.time()
            return False
            
        # 3. 内容减少的情况（可能是界面刷新或内容被删除）
        elif len(current_text) < len(self.last_dialog_content):
            content_decrease = len(self.last_dialog_content) - len(current_text)
            logger.debug(f"📉 检测到内容减少: -{content_decrease}字符，可能是界面刷新，重置计时器")
            self.last_content_change_time = time.time()
            return False
        
        # 4. 内容长度相同但内容不同（细微变化）
        else:
            logger.debug("🔄 检测到内容变化，重置计时器")
            self.last_content_change_time = time.time()
            return False
                
        return False

    def update_project_status(self, instruction_sent: str, cursor_response: str):
        """更新项目开发状态"""
        try:
            # 读取现有状态
            status_content = self.load_project_status()
            
            # 分析当前功能焦点
            current_focus = self.extract_feature_focus(instruction_sent, cursor_response)
            
            # 判断功能状态
            feature_status = self.analyze_feature_status(cursor_response)
            
            # 更新状态记录
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            new_entry = f"\n[{timestamp}] 功能焦点: {current_focus} | 状态: {feature_status} | 指令: {instruction_sent[:50]}..."
            
            # 写入状态文件
            updated_content = status_content + new_entry
            
            # 保持文件大小合理，只保留最近的记录
            lines = updated_content.split('\n')
            if len(lines) > 100:  # 保留最近100条记录
                updated_content = '\n'.join(lines[-80:])  # 保留最近80条
            
            with open(self.project_status_file, "w", encoding="utf-8") as f:
                f.write(updated_content)
                
            logger.info(f"📊 项目状态已更新: {current_focus} - {feature_status}")
            
        except Exception as e:
            logger.error(f"❌ 更新项目状态失败: {e}")
    
    def load_project_status(self) -> str:
        """加载项目状态"""
        try:
            with open(self.project_status_file, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            # 创建初始状态文件
            initial_content = f"# CURSOR监督系统开发状态跟踪\n# 创建时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            with open(self.project_status_file, "w", encoding="utf-8") as f:
                f.write(initial_content)
            return initial_content
        except Exception as e:
            logger.error(f"❌ 读取项目状态失败: {e}")
            return "# 项目状态文件读取失败\n"
    
    def extract_feature_focus(self, instruction: str, response: str) -> str:
        """提取当前功能焦点"""
        # 基于指令和回复内容判断当前关注的功能
        combined_text = (instruction + " " + response).lower()
        
        if "智能交互" in combined_text or "产品经理" in combined_text:
            return "智能交互系统"
        elif "监控" in combined_text or "检测" in combined_text:
            return "状态监控引擎"
        elif "自动化" in combined_text or "操作" in combined_text:
            return "自动化控制器"
        elif "gpt" in combined_text or "分析" in combined_text:
            return "AI分析模块"
        elif "安全" in combined_text or "保护" in combined_text:
            return "安全保护机制"
        elif "配置" in combined_text or "设置" in combined_text:
            return "配置管理系统"
        elif "日志" in combined_text or "记录" in combined_text:
            return "日志记录系统"
        elif "测试" in combined_text or "验证" in combined_text:
            return "测试验证模块"
        else:
            return "通用功能开发"
    
    def analyze_feature_status(self, response: str) -> str:
        """分析功能状态"""
        response_lower = response.lower()
        
        # 按优先级检测状态，避免重叠关键词的误判
        
        # 1. 首先检测明确的完成状态
        if any(keyword in response_lower for keyword in ["完成", "实现完毕", "已完成", "done", "finished", "完毕"]):
            return "已完成"
        
        # 2. 检测问题状态（高优先级）
        if any(keyword in response_lower for keyword in ["error", "错误", "failed", "失败", "exception", "异常", "bug", "问题"]):
            return "遇到问题"
        
        # 3. 检测测试状态（需要包含明确的测试词汇）
        if any(keyword in response_lower for keyword in ["单元测试", "集成测试", "测试验证", "testing", "verifying", "测试中"]):
            return "测试中"
        
        # 4. 检测需求分析状态
        if any(keyword in response_lower for keyword in ["需求分析", "设计", "规划", "分析用户", "功能范围", "planning", "analyzing", "requirements"]):
            return "需求分析"
        
        # 5. 检测优化状态
        if any(keyword in response_lower for keyword in ["重构", "优化", "改进", "提升", "refactor", "optimize", "improve", "enhancement"]):
            return "优化中"
        
        # 6. 检测开发状态（更精确的开发关键词）
        if any(keyword in response_lower for keyword in ["正在实现", "开发中", "编写", "实现中", "正在开发", "working", "implementing", "developing", "coding"]):
            return "开发中"
        
        # 7. 检测一般进行状态（较宽泛的关键词）
        if any(keyword in response_lower for keyword in ["正在", "开始", "继续", "进展", "进行", "处理"]):
            return "进行中"
        
        # 8. 默认状态
        return "进行中"
    
    def get_project_development_summary(self) -> str:
        """获取项目开发总结"""
        try:
            status_content = self.load_project_status()
            lines = status_content.split('\n')
            
            # 统计各功能的状态
            feature_counts = {}
            status_counts = {}
            
            for line in lines:
                if '功能焦点:' in line and '状态:' in line:
                    try:
                        # 提取功能和状态信息
                        parts = line.split('|')
                        feature_part = [p for p in parts if '功能焦点:' in p][0]
                        status_part = [p for p in parts if '状态:' in p][0]
                        
                        feature = feature_part.split('功能焦点:')[1].strip()
                        status = status_part.split('状态:')[1].split('指令:')[0].strip()
                        
                        feature_counts[feature] = feature_counts.get(feature, 0) + 1
                        status_counts[status] = status_counts.get(status, 0) + 1
                    except:
                        continue
            
            # 生成总结
            summary = "## 项目开发进度总结\n\n"
            summary += "### 功能模块活跃度\n"
            for feature, count in sorted(feature_counts.items(), key=lambda x: x[1], reverse=True):
                summary += f"- {feature}: {count}次活动\n"
            
            summary += "\n### 开发状态分布\n"
            for status, count in sorted(status_counts.items(), key=lambda x: x[1], reverse=True):
                summary += f"- {status}: {count}次\n"
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ 生成项目总结失败: {e}")
            return "项目总结生成失败"
    
    def should_proceed_with_intervention(self, content_analysis: Dict[str, Any], extracted_text: str) -> bool:
        """基于内容分析决定是否需要介入"""
        # 1. 如果置信度太低，但有明确的seeking_feedback意图，可以适当降低门槛
        if content_analysis['confidence_score'] < 30.0:
            # 特殊处理：寻求反馈的场景即使置信度较低也应该介入
            if content_analysis['cursor_intent'] == 'seeking_feedback':
                logger.info(f"💬 检测到明确的寻求反馈意图，虽然置信度较低({content_analysis['confidence_score']:.1f}%)，仍然介入")
                return True
            else:
                logger.info(f"🤔 分析置信度较低({content_analysis['confidence_score']:.1f}%)，暂不介入")
                return False
        
        # 2. 如果内容太短，但包含问号等反馈标识，仍然可以介入
        if content_analysis['content_length'] < 50:
            # 检查是否有明确的反馈请求信号
            feedback_signals = ["？", "?", "建议", "意见", "怎么样", "如何"]
            if any(signal in extracted_text for signal in feedback_signals):
                logger.info("💬 内容虽短但检测到反馈请求信号，需要介入")
                return True
            else:
                logger.info("📏 内容长度较短，可能不是完整回复，继续观察")
                return False
        
        # 3. 如果检测到CURSOR正在寻求反馈，应该介入
        if content_analysis['cursor_intent'] == 'seeking_feedback':
            logger.info("💬 检测到CURSOR寻求反馈，需要介入")
            return True
        
        # 4. 如果有明确的下一步行动建议，应该介入
        if content_analysis['next_action'] in ['run_test', 'run_demo', 'run_code', 'fix_errors']:
            logger.info(f"🎯 检测到明确的行动建议({content_analysis['next_action']})，需要介入")
            return True
        
        # 5. 如果任务状态为完成，应该介入
        if content_analysis['task_status'] == 'completed':
            logger.info("✅ 检测到任务完成状态，需要介入确认和推进")
            return True
        
        # 6. 如果检测到错误，应该介入
        if content_analysis['has_errors']:
            logger.info("❌ 检测到错误信息，需要介入协助解决")
            return True
        
        # 7. 默认：暂不介入，继续观察
        logger.info("😊 内容正常，暂不需要介入，继续观察CURSOR工作")
        return False
    
    def build_detailed_analysis_report(self, content_analysis: Dict[str, Any], extracted_text: str, context: str) -> str:
        """构建详细的分析报告"""
        report = f"""=== CURSOR回复深度分析报告 ===

📊 基础信息:
- 内容长度: {content_analysis['content_length']}字符
- 分析置信度: {content_analysis['confidence_score']:.1f}%
- 内容类型: {content_analysis['content_type']}
- 任务状态: {content_analysis['task_status']}
- CURSOR意图: {content_analysis['cursor_intent']}

🔍 详细解读:
- 词汇数量: {content_analysis['detailed_analysis']['word_count']}
- 行数: {content_analysis['detailed_analysis']['line_count']}
- 包含代码: {'是' if content_analysis['detailed_analysis']['contains_code'] else '否'}
- 情感倾向: {content_analysis['detailed_analysis']['sentiment']}
- 主要话题: {', '.join(content_analysis['detailed_analysis']['primary_topics'])}

🎯 关键信息点:
"""
        
        if content_analysis['key_points']:
            for i, point in enumerate(content_analysis['key_points'][:5], 1):
                report += f"{i}. {point}\n"
        else:
            report += "未识别到明显的关键信息点\n"
        
        report += f"""
🚀 建议行动: {content_analysis['next_action']}
❌ 错误检测: {'发现错误' if content_analysis['has_errors'] else '无错误'}

📄 原始内容摘要:
{content_analysis['raw_content']}

📋 对话上下文:
{context[:300]}...

---
请作为产品经理，基于以上深度分析，给出专业的下一步指导建议。
"""
        
        return report
    
    def record_analysis_session(self, content_analysis: Dict[str, Any], instruction_sent: str):
        """记录分析会话"""
        try:
            session_record = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "content_type": content_analysis['content_type'],
                "task_status": content_analysis['task_status'],
                "cursor_intent": content_analysis['cursor_intent'],
                "confidence_score": content_analysis['confidence_score'],
                "next_action": content_analysis['next_action'],
                "has_errors": content_analysis['has_errors'],
                "instruction_sent": instruction_sent[:100],
                "key_points_count": len(content_analysis['key_points'])
            }
            
            # 保存到分析历史
            if not hasattr(self, 'analysis_history'):
                self.analysis_history = []
            
            self.analysis_history.append(session_record)
            
            # 保持历史记录合理大小
            if len(self.analysis_history) > 50:
                self.analysis_history = self.analysis_history[-30:]
            
            logger.debug(f"📝 分析会话已记录: {content_analysis['content_type']} -> {content_analysis['next_action']}")
            
        except Exception as e:
            logger.error(f"❌ 记录分析会话失败: {e}")

    def collect_user_feedback(self, user: str, content: str):
        """收集用户反馈，自动识别反馈类型并存储"""
        feedback_keywords = [
            ("有帮助", "正向"),
            ("无帮助", "负向"),
            ("建议", "建议"),
            ("补充", "补充")
        ]
        feedback_type = "其他"
        for kw, ftype in feedback_keywords:
            if kw in content:
                feedback_type = ftype
                break
        self.user_feedback_manager.add_feedback(user, content, feedback_type)

    def get_feedback_report(self):
        """获取反馈分析报告"""
        analysis = self.user_feedback_manager.analyze_feedback()
        suggestions = self.user_feedback_manager.generate_improvement_suggestions()
        report = f"用户反馈统计：{analysis['summary']}\n总数：{analysis['total']}\n改进建议：{suggestions}"
        return report

    def is_substantially_same_content(self, current_text: str) -> bool:
        """检测内容是否实质相同 - 处理OCR微小差异导致的重复"""
        try:
            if not current_text or not self.last_dialog_content:
                return False
            
            # 标准化文本：去除空白、标点、特殊字符，转小写
            def normalize_text(text):
                import re
                # 只保留字母、数字、中文字符
                normalized = re.sub(r'[^\w\u4e00-\u9fff]', '', text.lower())
                return normalized
            
            normalized_current = normalize_text(current_text)
            normalized_last = normalize_text(self.last_dialog_content)
            
            # 如果标准化后的文本完全相同
            if normalized_current == normalized_last:
                logger.debug("🎯 检测到标准化后文本完全相同")
                return True
            
            # 计算相似度
            similarity = self.calculate_content_similarity(normalized_current, normalized_last)
            
            # 如果相似度超过90%，认为是实质相同
            if similarity > 0.9:
                logger.debug(f"🎯 检测到高相似度内容: {similarity:.2%}")
                return True
            
            # 检查是否为相同内容的子集或超集
            min_len = min(len(normalized_current), len(normalized_last))
            if min_len > 50:  # 只对足够长的文本进行子集检测
                if normalized_current in normalized_last or normalized_last in normalized_current:
                    logger.debug("🎯 检测到内容包含关系")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ 检测实质相同内容时出错: {e}")
            return False
    
    async def handle_repeated_content(self, current_text: str):
        """处理重复内容 - 增加计数器并在超过阈值时暂停监控"""
        try:
            # 初始化重复计数器
            if not hasattr(self, 'repeated_content_count'):
                self.repeated_content_count = 0
                self.last_repeated_content_time = time.time()
            
            self.repeated_content_count += 1
            current_time = time.time()
            
            logger.warning(f"🔁 检测到重复内容 #{self.repeated_content_count}")
            
            # 如果重复超过5次，暂停监控30秒
            if self.repeated_content_count >= 5:
                pause_duration = 30
                logger.warning(f"⏸️ 重复内容超过阈值，暂停监控 {pause_duration} 秒")
                logger.info(f"📝 重复内容预览: {current_text[:100]}...")
                
                # 暂停监控
                import asyncio
                await asyncio.sleep(pause_duration)
                
                # 重置计数器
                self.repeated_content_count = 0
                logger.info("🔄 重复内容监控暂停结束，重置计数器")
            
            # 如果重复超过10分钟，强制重置
            elif current_time - self.last_repeated_content_time > 600:  # 10分钟
                logger.info("⏰ 重复内容监控超过10分钟，强制重置计数器")
                self.repeated_content_count = 0
                self.last_repeated_content_time = current_time
            
        except Exception as e:
            logger.error(f"❌ 处理重复内容时出错: {e}")

async def main():
    """主程序"""
    logger.info("🎯 启动CURSOR监督系统...")
    
    supervisor = CursorSupervisor()
    
    try:
        await supervisor.start_monitoring()
    except KeyboardInterrupt:
        logger.info("⏹️ 收到中断信号，正在退出...")
    except Exception as e:
        logger.error(f"❌ 程序运行出错: {e}")
    finally:
        await supervisor.cleanup()
        logger.info("👋 CURSOR监督系统已退出")

if __name__ == "__main__":
    asyncio.run(main()) 
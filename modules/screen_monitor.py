#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
屏幕监控模块
功能：截取屏幕、识别文本、检测UI元素
"""

import asyncio
import cv2
import numpy as np
from PIL import Image, ImageGrab
import pyautogui
import psutil
import logging
import time
import io
import base64
from typing import Optional, Tuple, List
import subprocess
import platform

# 尝试导入OCR引擎
EASYOCR_AVAILABLE = False
PYTESSERACT_AVAILABLE = False

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    pass

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    pass

logger = logging.getLogger(__name__)

class ScreenMonitor:
    """屏幕监控类"""
    
    # 类级别的全局OCR引用，供其他模块使用
    _global_ocr_reader = None
    
    def __init__(self, selected_window_info: dict = None):
        self.ocr_reader = None
        self.use_easyocr = False
        self.last_screenshot = None
        self.cursor_window_coords = None
        self.selected_window_info = selected_window_info  # 用户选择的窗口信息
        
        # 如果提供了选定的窗口信息，直接使用
        if selected_window_info and 'position' in selected_window_info:
            x, y, width, height = selected_window_info['position']
            self.cursor_window_coords = (x, y, x + width, y + height)
            logger.info(f"🎯 使用指定窗口: {selected_window_info.get('title', 'Unknown')} at {self.cursor_window_coords}")
        
        # 初始化OCR引擎
        self._init_ocr()
        
        # 配置pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1
    
    def _init_ocr(self):
        """初始化OCR引擎"""
        # 尝试EasyOCR优先
        if EASYOCR_AVAILABLE:
            try:
                logger.info("🔍 正在初始化EasyOCR引擎...")
                self.ocr_reader = easyocr.Reader(['en', 'ch_sim'], gpu=False)  # 禁用GPU以避免CUDA问题
                self.use_easyocr = True
                
                # 设置全局OCR引用
                ScreenMonitor._global_ocr_reader = self.ocr_reader
                
                logger.info("✅ EasyOCR引擎初始化成功")
                return
            except Exception as e:
                logger.warning(f"⚠️ EasyOCR初始化失败: {e}")
        
        # 尝试Tesseract
        if PYTESSERACT_AVAILABLE:
            try:
                logger.info("🔍 正在测试Tesseract引擎...")
                from PIL import Image
                test_img = Image.new('RGB', (100, 30), color='white')
                pytesseract.image_to_string(test_img)
                logger.info("✅ Tesseract引擎可用")
                return
            except Exception as e:
                logger.warning(f"⚠️ Tesseract不可用: {e}")
                logger.info("💡 如需使用Tesseract，请参考以下安装方法：")
                logger.info("   Windows: 下载并安装 https://github.com/UB-Mannheim/tesseract/wiki")
                logger.info("   然后设置环境变量 PATH 包含 Tesseract 安装目录")
        
        logger.warning("⚠️ 没有可用的OCR引擎，文本提取功能将被禁用")
        logger.info("💡 推荐解决方案：")
        logger.info("   1. 关闭所有Python程序和IDE")
        logger.info("   2. 以管理员身份运行命令行")
        logger.info("   3. 执行: pip install easyocr")
        logger.info("   4. 或者安装Tesseract: https://github.com/UB-Mannheim/tesseract/wiki")
    
    async def initialize(self):
        """异步初始化方法"""
        try:
            logger.info("🚀 ScreenMonitor初始化中...")
            
            # 检查屏幕访问权限
            try:
                test_screenshot = pyautogui.screenshot()
                logger.info("✅ 屏幕访问权限正常")
            except Exception as e:
                logger.warning(f"⚠️ 屏幕访问可能受限: {e}")
            
            # 如果没有指定窗口，才自动查找CURSOR窗口
            if not self.cursor_window_coords:
                cursor_coords = self.find_cursor_window()
                if cursor_coords:
                    logger.info(f"✅ 找到CURSOR窗口: {cursor_coords}")
                else:
                    logger.info("⚠️ 未找到CURSOR窗口，将使用全屏模式")
            else:
                logger.info(f"✅ 使用指定CURSOR窗口: {self.cursor_window_coords}")
            
            logger.info("✅ ScreenMonitor初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"ScreenMonitor初始化失败: {e}")
            return False
    
    async def capture_screenshot(self) -> Optional[Image.Image]:
        """捕获屏幕截图 - 新的统一方法"""
        try:
            # 如果有CURSOR窗口坐标，优先截取该区域
            if self.cursor_window_coords:
                screenshot = ImageGrab.grab(bbox=self.cursor_window_coords)
            else:
                # 否则截取全屏
                screenshot = ImageGrab.grab()
            
            self.last_screenshot = screenshot
            return screenshot
            
        except Exception as e:
            logger.error(f"截取屏幕时出错: {e}")
            return None
    
    async def capture_cursor_window(self) -> Optional[Image.Image]:
        """捕获CURSOR窗口截图"""
        try:
            # 优先使用指定的窗口坐标
            cursor_coords = self.cursor_window_coords
            
            # 如果没有指定窗口，才重新查找
            if not cursor_coords:
                cursor_coords = self.find_cursor_window()
            
            if not cursor_coords:
                # 如果找不到CURSOR窗口，截取整个屏幕
                logger.info("未找到CURSOR窗口，截取整个屏幕")
                screenshot = ImageGrab.grab()
            else:
                # 截取指定区域
                screenshot = ImageGrab.grab(bbox=cursor_coords)
                logger.debug(f"📸 截取窗口区域: {cursor_coords}")
            
            self.last_screenshot = screenshot
            
            # 保存截图用于调试
            timestamp = int(time.time())
            debug_path = f"debug/screenshot_{timestamp}.png"
            screenshot.save(debug_path)
            logger.debug(f"截图已保存: {debug_path}")
            
            return screenshot
            
        except Exception as e:
            logger.error(f"截取窗口时出错: {e}")
            return None
    
    def find_cursor_window(self) -> Optional[Tuple[int, int, int, int]]:
        """查找CURSOR窗口坐标"""
        try:
            # 首先尝试使用系统命令查找窗口
            if platform.system() == "Windows":
                return self._find_cursor_window_windows()
            else:
                return self._find_cursor_window_cross_platform()
                
        except Exception as e:
            logger.error(f"查找CURSOR窗口时出错: {e}")
            return None
    
    def _find_cursor_window_windows(self) -> Optional[Tuple[int, int, int, int]]:
        """在Windows上查找CURSOR窗口"""
        try:
            import win32gui
            import win32con
            
            def enum_windows_callback(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    window_title = win32gui.GetWindowText(hwnd)
                    if window_title and ("cursor" in window_title.lower() or "code" in window_title.lower()):
                        rect = win32gui.GetWindowRect(hwnd)
                        windows.append((window_title, rect))
                return True
            
            windows = []
            win32gui.EnumWindows(enum_windows_callback, windows)
            
            for title, rect in windows:
                if "cursor" in title.lower():
                    self.cursor_window_coords = rect
                    logger.info(f"找到CURSOR窗口: {title}")
                    return rect
            
            # 如果没找到cursor，尝试找其他编辑器
            for title, rect in windows:
                if any(keyword in title.lower() for keyword in ["code", "vscode", "editor"]):
                    self.cursor_window_coords = rect
                    logger.info(f"找到编辑器窗口: {title}")
                    return rect
                    
        except ImportError:
            logger.warning("win32gui不可用，使用pyautogui方法")
            
        return self._find_cursor_window_cross_platform()
    
    def _find_cursor_window_cross_platform(self) -> Optional[Tuple[int, int, int, int]]:
        """跨平台方式查找CURSOR窗口"""
        try:
            # 使用pyautogui查找窗口
            window_titles = ["Cursor", "cursor", "Visual Studio Code", "Code"]
            
            for title in window_titles:
                try:
                    windows = pyautogui.getWindowsWithTitle(title)
                    if windows:
                        window = windows[0]
                        # 尝试激活窗口
                        try:
                            window.activate()
                        except:
                            pass
                        
                        # 获取窗口坐标
                        left, top, width, height = window.left, window.top, window.width, window.height
                        self.cursor_window_coords = (left, top, left + width, top + height)
                        logger.info(f"找到窗口: {title}")
                        return self.cursor_window_coords
                except Exception as e:
                    logger.debug(f"查找窗口 {title} 失败: {e}")
                    continue
            
            logger.warning("未找到CURSOR或相关编辑器窗口")
            return None
            
        except Exception as e:
            logger.error(f"跨平台窗口查找失败: {e}")
            return None
    
    async def extract_text(self, image: Image.Image) -> str:
        """从图像中提取文本 - 优化版本：增强fallback机制"""
        # 如果没有OCR引擎，使用智能图像分析fallback
        if not EASYOCR_AVAILABLE and not PYTESSERACT_AVAILABLE:
            logger.debug("💡 使用智能图像分析代替OCR")
            return await self.intelligent_text_fallback(image)
            
        try:
            # 预处理图像以提高OCR准确性
            processed_image = self.preprocess_image(image)
            
            if self.use_easyocr and self.ocr_reader:
                # 使用EasyOCR进行文本识别
                logger.debug("🔍 使用EasyOCR提取文本...")
                result = self.ocr_reader.readtext(np.array(processed_image))
                
                # 提取文本内容
                extracted_text = ' '.join([detection[1] for detection in result if detection[2] > 0.5])
                logger.debug(f"📝 EasyOCR提取到文本: {extracted_text[:100]}...")
                
                return extracted_text
            
            elif PYTESSERACT_AVAILABLE:
                # 使用Tesseract进行文本识别
                logger.debug("🔍 使用Tesseract提取文本...")
                extracted_text = pytesseract.image_to_string(processed_image, lang='eng+chi_sim')
                logger.debug(f"📝 Tesseract提取到文本: {extracted_text[:100]}...")
                
                return extracted_text.strip()
            
            else:
                logger.debug("❌ 没有可用的OCR引擎")
                return await self.intelligent_text_fallback(image)
                
        except Exception as e:
            logger.warning(f"⚠️ OCR文本提取失败: {e}")
            return await self.intelligent_text_fallback(image)
    
    async def intelligent_text_fallback(self, image: Image.Image) -> str:
        """智能图像分析fallback - 当OCR不可用时的替代方案"""
        try:
            # 基于图像特征分析推断可能的状态
            img_array = np.array(image)
            height, width = img_array.shape[:2]
            
            # 分析图像特征
            features = {
                "has_bright_areas": self.detect_bright_areas(img_array),
                "has_color_patterns": self.detect_color_patterns(img_array),
                "has_ui_elements": self.detect_basic_ui_elements(img_array),
                "bottom_area_activity": self.analyze_bottom_area(img_array)
            }
            
            # 根据特征推断可能的文本内容
            inferred_text = self.infer_text_from_features(features)
            
            logger.debug(f"💡 智能分析推断: {inferred_text}")
            return inferred_text
            
        except Exception as e:
            logger.debug(f"智能fallback分析失败: {e}")
            return "界面截图已获取，OCR功能暂时不可用"
    
    def detect_bright_areas(self, img_array) -> bool:
        """检测明亮区域（可能是对话框或通知）"""
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        bright_pixels = np.sum(gray > 200)
        total_pixels = gray.shape[0] * gray.shape[1]
        bright_ratio = bright_pixels / total_pixels
        return bright_ratio > 0.3
    
    def detect_color_patterns(self, img_array) -> dict:
        """检测颜色模式"""
        # 计算主要颜色
        colors = {}
        for channel in range(3):
            mean_val = np.mean(img_array[:, :, channel])
            colors[['red', 'green', 'blue'][channel]] = mean_val
        
        # 检测可能的状态颜色
        has_green = colors['green'] > 150 and colors['green'] > colors['red'] * 1.2
        has_red = colors['red'] > 150 and colors['red'] > colors['green'] * 1.2
        has_blue = colors['blue'] > 150
        
        return {
            "success_colors": has_green,
            "error_colors": has_red,
            "info_colors": has_blue,
            "dominant_color": max(colors, key=colors.get)
        }
    
    def detect_basic_ui_elements(self, img_array) -> dict:
        """检测基本UI元素"""
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        
        # 边缘检测
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / (edges.shape[0] * edges.shape[1])
        
        # 检测矩形（可能是按钮或对话框）
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        rectangles = []
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w > 50 and h > 20 and w/h > 2:  # 可能是按钮
                rectangles.append((x, y, w, h))
        
        return {
            "edge_density": edge_density,
            "button_like_elements": len(rectangles),
            "has_structure": edge_density > 0.1
        }
    
    def analyze_bottom_area(self, img_array) -> dict:
        """分析底部区域（通常是输入或状态区域）"""
        height = img_array.shape[0]
        bottom_area = img_array[int(height * 0.8):, :]  # 底部20%
        
        # 分析底部区域的颜色和亮度
        bottom_mean = np.mean(bottom_area, axis=(0, 1))
        bottom_brightness = np.mean(bottom_mean)
        
        # 检测底部是否有活动（颜色变化）
        bottom_std = np.std(bottom_area, axis=(0, 1))
        has_activity = np.mean(bottom_std) > 20
        
        return {
            "brightness": bottom_brightness,
            "has_activity": has_activity,
            "is_bright": bottom_brightness > 150
        }
    
    def infer_text_from_features(self, features: dict) -> str:
        """根据图像特征推断可能的文本内容"""
        inferences = []
        
        # 根据颜色模式推断
        if features.get("has_color_patterns", {}).get("success_colors"):
            inferences.append("检测到成功状态指示器")
        
        if features.get("has_color_patterns", {}).get("error_colors"):
            inferences.append("检测到错误状态指示器")
        
        # 根据UI元素推断
        if features.get("has_ui_elements", {}).get("button_like_elements", 0) > 0:
            inferences.append("检测到交互式UI元素")
        
        # 根据底部区域推断
        if features.get("bottom_area_activity", {}).get("has_activity"):
            inferences.append("底部区域有活动，可能是输入区域")
        
        # 根据亮度推断
        if features.get("has_bright_areas"):
            inferences.append("检测到高亮区域，可能是对话框或通知")
        
        if not inferences:
            return "图像已分析，等待进一步操作"
        
        return " | ".join(inferences)
    
    def preprocess_image(self, image: Image.Image) -> Image.Image:
        """预处理图像以提高OCR准确性"""
        try:
            # 转换为numpy数组
            img_array = np.array(image)

            # 转换为灰度图
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

            # 放大图像以提升小字体识别率
            gray = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_LINEAR)

            # 双边滤波保留边缘同时去噪
            filtered = cv2.bilateralFilter(gray, 9, 75, 75)

            # 自适应阈值处理
            thresh = cv2.adaptiveThreshold(
                filtered, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 31, 2
            )

            # 形态学操作进一步去噪
            kernel = np.ones((2, 2), np.uint8)
            morphed = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
            morphed = cv2.morphologyEx(morphed, cv2.MORPH_CLOSE, kernel)

            # 转换回PIL Image
            processed_image = Image.fromarray(morphed)

            return processed_image
            
        except Exception as e:
            logger.error(f"图像预处理时出错: {e}")
            return image
    
    def get_screenshot_base64(self, image: Image.Image) -> str:
        """将截图转换为base64编码"""
        try:
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            return img_base64
        except Exception as e:
            logger.error(f"转换base64时出错: {e}")
            return ""
    
    async def capture_dialog_area(self) -> Optional[Image.Image]:
        """捕获对话框区域"""
        try:
            full_screenshot = await self.capture_cursor_window()
            if not full_screenshot:
                return None
            
            # 分析截图，定位对话框区域
            # 这里可以添加更复杂的图像分析逻辑
            # 暂时返回右侧对话区域（假设是屏幕的右半部分）
            width, height = full_screenshot.size
            dialog_area = full_screenshot.crop((width//2, 0, width, height))
            
            return dialog_area
            
        except Exception as e:
            logger.error(f"捕获对话框区域时出错: {e}")
            return None
    
    def detect_ui_elements(self, image: Image.Image) -> dict:
        """检测UI元素（按钮、输入框等）"""
        try:
            # 使用OpenCV检测UI元素
            img_array = np.array(image)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            
            # 检测按钮（假设是矩形区域）
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            ui_elements = {
                'buttons': [],
                'input_fields': [],
                'text_areas': []
            }
            
            for contour in contours:
                # 计算轮廓面积和边界框
                area = cv2.contourArea(contour)
                if area > 1000:  # 过滤掉太小的区域
                    x, y, w, h = cv2.boundingRect(contour)
                    
                    # 根据宽高比判断元素类型
                    aspect_ratio = w / h
                    if 2 <= aspect_ratio <= 6:  # 可能是按钮
                        ui_elements['buttons'].append((x, y, w, h))
                    elif aspect_ratio > 6:  # 可能是输入框
                        ui_elements['input_fields'].append((x, y, w, h))
            
            return ui_elements
            
        except Exception as e:
            logger.error(f"检测UI元素时出错: {e}")
            return {}
    
    async def save_screenshot(self, image: Image.Image, filename: str) -> str:
        """保存截图"""
        try:
            filepath = f"screenshots/{filename}"
            image.save(filepath)
            logger.info(f"截图已保存: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"保存截图时出错: {e}")
            return ""
    
    def get_ocr_status(self) -> dict:
        """获取OCR引擎状态"""
        return {
            "easyocr_available": EASYOCR_AVAILABLE,
            "pytesseract_available": PYTESSERACT_AVAILABLE,
            "current_engine": "EasyOCR" if self.use_easyocr else "Tesseract" if PYTESSERACT_AVAILABLE else "None",
            "ocr_reader_initialized": self.ocr_reader is not None
        }
    
    async def cleanup(self):
        """清理资源"""
        try:
            logger.info("🧹 清理ScreenMonitor资源...")
            
            # 清理OCR引擎资源
            if self.ocr_reader:
                self.ocr_reader = None
                
            # 清理截图缓存
            self.last_screenshot = None
            
            logger.info("✅ ScreenMonitor资源清理完成")
            
        except Exception as e:
            logger.error(f"清理ScreenMonitor资源时出错: {e}") 
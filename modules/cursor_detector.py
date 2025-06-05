#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CURSOR检测模块
功能：检测CURSOR IDE是否正在运行，获取进程信息
"""

import psutil
import pyautogui
import time
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class CursorDetector:
    """CURSOR检测器类"""
    
    def __init__(self):
        self.cursor_process = None
        self.cursor_window = None
        self.last_check_time = 0
        self.check_interval = 5  # 检查间隔（秒）
        
    def is_cursor_running(self) -> bool:
        """检查CURSOR是否正在运行"""
        try:
            current_time = time.time()
            
            # 如果距离上次检查时间太短，直接返回缓存结果
            if (current_time - self.last_check_time < self.check_interval and 
                self.cursor_process is not None):
                return self.cursor_process.is_running()
            
            # 更新检查时间
            self.last_check_time = current_time
            
            # 查找CURSOR进程
            cursor_processes = self.find_cursor_processes()
            
            if cursor_processes:
                self.cursor_process = cursor_processes[0]  # 使用第一个找到的进程
                logger.info(f"检测到CURSOR进程: PID {self.cursor_process.pid}")
                return True
            else:
                self.cursor_process = None
                logger.warning("未检测到CURSOR进程")
                return False
                
        except Exception as e:
            logger.error(f"检查CURSOR运行状态时出错: {e}")
            return False
    
    def find_cursor_processes(self) -> List[psutil.Process]:
        """查找所有CURSOR相关进程"""
        cursor_processes = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    proc_info = proc.info
                    proc_name = proc_info['name'].lower()
                    
                    # 检查进程名是否包含cursor
                    if 'cursor' in proc_name:
                        cursor_processes.append(proc)
                        logger.debug(f"找到CURSOR进程: {proc_info['name']} (PID: {proc_info['pid']})")
                        
                    # 检查执行文件路径
                    if proc_info['exe']:
                        exe_path = proc_info['exe'].lower()
                        if 'cursor' in exe_path:
                            cursor_processes.append(proc)
                            logger.debug(f"找到CURSOR进程: {proc_info['exe']} (PID: {proc_info['pid']})")
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                    
        except Exception as e:
            logger.error(f"搜索CURSOR进程时出错: {e}")
            
        return cursor_processes
    
    def get_cursor_window_info(self) -> Optional[Dict]:
        """获取CURSOR窗口信息"""
        try:
            # 使用pyautogui查找窗口
            windows = pyautogui.getWindowsWithTitle("Cursor")
            
            if not windows:
                # 尝试其他可能的标题
                for title in ["cursor", "Cursor IDE", "Cursor Editor"]:
                    windows = pyautogui.getWindowsWithTitle(title)
                    if windows:
                        break
            
            if windows:
                window = windows[0]
                window_info = {
                    'title': window.title,
                    'left': window.left,
                    'top': window.top,
                    'width': window.width,
                    'height': window.height,
                    'is_maximized': window.isMaximized,
                    'is_minimized': window.isMinimized,
                    'is_active': window.isActive
                }
                
                self.cursor_window = window
                return window_info
            else:
                logger.warning("未找到CURSOR窗口")
                return None
                
        except Exception as e:
            logger.error(f"获取CURSOR窗口信息时出错: {e}")
            return None
    
    def activate_cursor_window(self) -> bool:
        """激活CURSOR窗口"""
        try:
            window_info = self.get_cursor_window_info()
            if window_info and self.cursor_window:
                
                # 如果窗口被最小化，先恢复
                if window_info['is_minimized']:
                    self.cursor_window.restore()
                    time.sleep(0.5)
                
                # 激活窗口
                self.cursor_window.activate()
                time.sleep(0.5)
                
                # 确保窗口在前台
                self.cursor_window.moveTo(window_info['left'] + 10, window_info['top'] + 10)
                pyautogui.click()
                
                logger.info("CURSOR窗口已激活")
                return True
            else:
                logger.warning("无法激活CURSOR窗口")
                return False
                
        except Exception as e:
            logger.error(f"激活CURSOR窗口时出错: {e}")
            return False
    
    def get_cursor_process_info(self) -> Optional[Dict]:
        """获取CURSOR进程详细信息"""
        try:
            if not self.cursor_process:
                if not self.is_cursor_running():
                    return None
            
            if self.cursor_process:
                proc_info = {
                    'pid': self.cursor_process.pid,
                    'name': self.cursor_process.name(),
                    'exe': self.cursor_process.exe(),
                    'cmdline': self.cursor_process.cmdline(),
                    'cpu_percent': self.cursor_process.cpu_percent(),
                    'memory_percent': self.cursor_process.memory_percent(),
                    'status': self.cursor_process.status(),
                    'create_time': self.cursor_process.create_time()
                }
                
                return proc_info
            
        except Exception as e:
            logger.error(f"获取CURSOR进程信息时出错: {e}")
            
        return None
    
    def wait_for_cursor_start(self, timeout: int = 60) -> bool:
        """等待CURSOR启动"""
        logger.info(f"等待CURSOR启动，超时时间: {timeout}秒")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_cursor_running():
                logger.info("CURSOR已启动")
                return True
            
            time.sleep(2)
        
        logger.warning(f"等待CURSOR启动超时 ({timeout}秒)")
        return False
    
    def is_cursor_responsive(self) -> bool:
        """检查CURSOR是否响应"""
        try:
            if not self.cursor_process:
                return False
            
            # 检查进程状态
            status = self.cursor_process.status()
            if status in ['zombie', 'dead']:
                return False
            
            # 检查CPU使用率（如果长时间CPU使用率为0可能表示卡住）
            cpu_percent = self.cursor_process.cpu_percent(interval=1)
            
            # 检查窗口是否响应
            window_info = self.get_cursor_window_info()
            if window_info:
                return True
            
            return True
            
        except Exception as e:
            logger.error(f"检查CURSOR响应性时出错: {e}")
            return False
    
    def kill_cursor_process(self) -> bool:
        """强制终止CURSOR进程"""
        try:
            if self.cursor_process:
                logger.warning(f"强制终止CURSOR进程: PID {self.cursor_process.pid}")
                self.cursor_process.terminate()
                
                # 等待进程终止
                try:
                    self.cursor_process.wait(timeout=10)
                    logger.info("CURSOR进程已正常终止")
                except psutil.TimeoutExpired:
                    # 如果等待超时，强制杀死进程
                    self.cursor_process.kill()
                    logger.warning("CURSOR进程被强制杀死")
                
                self.cursor_process = None
                return True
            
        except Exception as e:
            logger.error(f"终止CURSOR进程时出错: {e}")
            
        return False 
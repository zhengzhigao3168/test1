#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
功能：管理所有配置项，包括API密钥、监控设置等
"""

import json
import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class ConfigManager:
    """配置管理器类"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config_data = {}
        
        # 加载环境变量
        load_dotenv()
        
        # 默认配置
        self.default_config = {
            "openai": {
                "api_key": "",
                "base_url": None,
                "model": "gpt-4o",
                "max_tokens": 1000,
                "temperature": 0.1
            },
            "monitoring": {
                "interval": 3,  # 监控间隔（秒）
                "stuck_threshold": 300,  # 卡住判断时间（秒）
                "max_interventions_per_hour": 20,
                "screenshot_quality": "high"
            },
            "automation": {
                "safe_mode": True,
                "action_delay": 0.5,
                "confirmation_required": ["delete", "remove", "clear", "reset"],
                "max_retry_attempts": 3
            },
            "logging": {
                "level": "INFO",
                "file_path": "cursor_supervisor.log",
                "max_file_size": 10485760,  # 10MB
                "backup_count": 5
            },
            "ui": {
                "window_title_patterns": ["Cursor", "cursor", "Cursor IDE"],
                "dialog_detection_keywords": [
                    "waiting for", "please confirm", "continue?", 
                    "enter your", "输入", "确认", "等待"
                ],
                "error_detection_keywords": [
                    "error", "failed", "exception", "错误", 
                    "失败", "异常", "Error", "Exception"
                ]
            },
            "paths": {
                "screenshots_dir": "screenshots",
                "debug_dir": "debug", 
                "logs_dir": "logs"
            }
        }
        
        # 加载配置
        self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                
                # 合并配置（文件配置覆盖默认配置）
                self.config_data = self.merge_config(self.default_config, file_config)
                logger.info(f"从文件加载配置: {self.config_file}")
            else:
                # 使用默认配置
                self.config_data = self.default_config.copy()
                logger.info("使用默认配置")
            
            # 从环境变量更新配置
            self.update_from_env()
            
            # 确保必要的目录存在
            self.ensure_directories()
            
        except Exception as e:
            logger.error(f"加载配置时出错: {e}")
            self.config_data = self.default_config.copy()
    
    def save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            logger.info(f"配置已保存到: {self.config_file}")
        except Exception as e:
            logger.error(f"保存配置时出错: {e}")
    
    def merge_config(self, default: Dict, override: Dict) -> Dict:
        """递归合并配置字典"""
        result = default.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self.merge_config(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def update_from_env(self):
        """从环境变量和config.py更新配置"""
        # 从config.py导入配置（如果存在）
        try:
            import config
            if hasattr(config, 'API_KEY'):
                self.config_data['openai']['api_key'] = config.API_KEY
            if hasattr(config, 'BASE_URL'):
                self.config_data['openai']['base_url'] = config.BASE_URL
            logger.info("从config.py加载API配置")
        except ImportError:
            logger.debug("config.py文件不存在，跳过导入")
        except Exception as e:
            logger.warning(f"从config.py导入配置时出错: {e}")
        
        # OpenAI API密钥（环境变量优先，但只在环境变量存在且非空时覆盖）
        openai_key = os.getenv('OPENAI_API_KEY')
        if openai_key and openai_key.strip():  # 只有在环境变量存在且非空时才覆盖
            self.config_data['openai']['api_key'] = openai_key
        
        # OpenAI Base URL（环境变量优先，但只在环境变量存在且非空时覆盖）
        openai_base_url = os.getenv('OPENAI_BASE_URL')
        if openai_base_url and openai_base_url.strip():  # 只有在环境变量存在且非空时才覆盖
            self.config_data['openai']['base_url'] = openai_base_url
        
        # 日志级别
        log_level = os.getenv('LOG_LEVEL')
        if log_level:
            self.config_data['logging']['level'] = log_level.upper()
        
        # 安全模式
        safe_mode = os.getenv('SAFE_MODE')
        if safe_mode:
            self.config_data['automation']['safe_mode'] = safe_mode.lower() == 'true'
    
    def ensure_directories(self):
        """确保必要的目录存在"""
        directories = [
            self.config_data['paths']['screenshots_dir'],
            self.config_data['paths']['debug_dir'],
            self.config_data['paths']['logs_dir']
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def get(self, key_path: str, default=None) -> Any:
        """获取配置值，支持点分隔的路径"""
        try:
            keys = key_path.split('.')
            value = self.config_data
            
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return default
            
            return value
            
        except Exception as e:
            logger.error(f"获取配置值'{key_path}'时出错: {e}")
            return default
    
    def set(self, key_path: str, value: Any):
        """设置配置值，支持点分隔的路径"""
        try:
            keys = key_path.split('.')
            config = self.config_data
            
            # 导航到目标位置
            for key in keys[:-1]:
                if key not in config:
                    config[key] = {}
                config = config[key]
            
            # 设置值
            config[keys[-1]] = value
            logger.info(f"设置配置: {key_path} = {value}")
            
        except Exception as e:
            logger.error(f"设置配置值'{key_path}'时出错: {e}")
    
    def get_openai_key(self) -> str:
        """获取OpenAI API密钥"""
        api_key = self.get('openai.api_key', '')
        if not api_key:
            logger.warning("OpenAI API密钥未设置")
        return api_key
    
    def get_openai_base_url(self) -> Optional[str]:
        """获取OpenAI Base URL"""
        return self.get('openai.base_url')
    
    def get_monitor_interval(self) -> int:
        """获取监控间隔"""
        return self.get('monitoring.interval', 3)
    
    def get_stuck_threshold(self) -> int:
        """获取卡住判断阈值"""
        return self.get('monitoring.stuck_threshold', 300)
    
    def is_safe_mode(self) -> bool:
        """是否启用安全模式"""
        return self.get('automation.safe_mode', True)
    
    def get_action_delay(self) -> float:
        """获取操作延迟"""
        return self.get('automation.action_delay', 0.5)
    
    def get_log_level(self) -> str:
        """获取日志级别"""
        return self.get('logging.level', 'INFO')
    
    def get_window_title_patterns(self) -> list:
        """获取窗口标题匹配模式"""
        return self.get('ui.window_title_patterns', ['Cursor'])
    
    def get_dialog_keywords(self) -> list:
        """获取对话框检测关键词"""
        return self.get('ui.dialog_detection_keywords', [])
    
    def get_error_keywords(self) -> list:
        """获取错误检测关键词"""
        return self.get('ui.error_detection_keywords', [])
    
    def get_screenshots_dir(self) -> str:
        """获取截图目录"""
        return self.get('paths.screenshots_dir', 'screenshots')
    
    def get_debug_dir(self) -> str:
        """获取调试目录"""
        return self.get('paths.debug_dir', 'debug')
    
    def get_logs_dir(self) -> str:
        """获取日志目录"""
        return self.get('paths.logs_dir', 'logs')
    
    def validate_config(self) -> Dict[str, list]:
        """验证配置的有效性"""
        errors = {
            'critical': [],
            'warnings': []
        }
        
        # 检查必需的配置项
        if not self.get_openai_key():
            errors['critical'].append("OpenAI API密钥未设置")
        
        # 检查监控间隔
        interval = self.get_monitor_interval()
        if interval < 1 or interval > 60:
            errors['warnings'].append(f"监控间隔设置可能不合理: {interval}秒")
        
        # 检查目录权限
        for dir_name in ['screenshots_dir', 'debug_dir', 'logs_dir']:
            dir_path = self.get(f'paths.{dir_name}')
            if dir_path and not os.access(dir_path, os.W_OK):
                try:
                    # 尝试创建目录
                    Path(dir_path).mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    errors['warnings'].append(f"无法访问目录 {dir_path}: {e}")
        
        return errors
    
    def reset_to_default(self):
        """重置为默认配置"""
        self.config_data = self.default_config.copy()
        self.update_from_env()
        logger.info("配置已重置为默认值")
    
    def export_config(self, export_path: str):
        """导出配置到指定文件"""
        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            logger.info(f"配置已导出到: {export_path}")
        except Exception as e:
            logger.error(f"导出配置时出错: {e}")
    
    def import_config(self, import_path: str):
        """从指定文件导入配置"""
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                imported_config = json.load(f)
            
            # 合并导入的配置
            self.config_data = self.merge_config(self.config_data, imported_config)
            logger.info(f"配置已从 {import_path} 导入")
            
        except Exception as e:
            logger.error(f"导入配置时出错: {e}")
    
    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要信息"""
        return {
            "openai_configured": bool(self.get_openai_key()),
            "safe_mode": self.is_safe_mode(),
            "monitor_interval": self.get_monitor_interval(),
            "log_level": self.get_log_level(),
            "directories": {
                "screenshots": self.get_screenshots_dir(),
                "debug": self.get_debug_dir(),
                "logs": self.get_logs_dir()
            }
        } 
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPT控制器模块
功能：与GPT-4O API交互，分析截图并生成操作指令
"""

import asyncio
import base64
import json
import logging
import os
import time
from typing import Dict, List, Optional, Any
from openai import OpenAI  # 更改为同步客户端
from PIL import Image
import io

logger = logging.getLogger(__name__)

class GPTController:
    """GPT控制器类"""
    
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        # 简化客户端初始化，只传递必要参数
        client_kwargs = {"api_key": api_key}
        
        # 只有在base_url存在且有效时才添加
        if base_url and base_url.strip():
            # 清理base_url格式
            if base_url.endswith('/chat/completions'):
                base_url = base_url.replace('/chat/completions', '')
            if base_url.endswith('/v1'):
                base_url = base_url
            elif not base_url.endswith('/v1'):
                base_url = base_url.rstrip('/') + '/v1'
            
            client_kwargs["base_url"] = base_url
            logger.info(f"使用自定义API base_url: {base_url}")
        
        try:
            self.client = OpenAI(**client_kwargs)
            logger.info("OpenAI客户端初始化成功")
        except Exception as e:
            logger.error(f"OpenAI客户端初始化失败: {e}")
            # 尝试不使用base_url的基础初始化
            self.client = OpenAI(api_key=api_key)
            logger.info("使用基础API地址初始化")
            
        self.conversation_history = []
        self.analysis_cache = {}
        self.max_history_length = 10
        
        # 系统提示词 - 专注于项目功能完成的产品导向
        self.system_prompt = """
你是一个专业的CURSOR IDE自动化助手。你的任务是分析CURSOR界面的截图，识别当前状态，并提供准确的操作指令。你的目标是帮助快速完成整个项目的主要功能，而不是纠结于技术细节。
**核心原则：先做能用，再做完美**
你需要识别以下情况并提供相应的操作：

1. **等待输入状态**：
   - CURSOR显示"waiting for input"、"continue?"、"please confirm"等提示
   - 对话框中有输入框等待用户输入
   - 需要用户确认某个操作

2. **代码完成和审查状态**：
   - 看到"Review changes"、"代码完成"、"实现完成"等字样
   - 代码修改或实现已经完成，需要进行审查和反馈
   - 此时应该**输入文本进行代码审查和质量评估**，而不是点击按钮
   - 输入内容应包括：下一步建议等

你需要识别CURSOR当前状态并推动项目进展：

1. **功能开发状态**：
   - 当看到代码完成、Review changes、实现完成等信号时
   - 立即推动下一个功能的开发
   - 输入指令：继续开发下一个核心功能，不要停留在细节优化

2. **错误处理状态**：
   - 遇到错误时，快速找到解决方案
   - 优先选择最简单、最直接的修复方法
   - 输入指令：快速修复这个问题，使用最简单的方法，然后继续开发主要功能

3. **卡住状态**：
   - 如果开发停滞，立即推动继续
   - 输入指令：跳过这个细节问题，先完成核心功能，后续再优化

**指令生成原则**：
- **目标导向**：每个指令都要推动项目朝着"能用"的方向前进
- **简单有效**：选择最直接的解决方案，避免过度设计
- **功能优先**：优先完成主要功能，细节后续优化
- **快速迭代**：快速实现基础版本，然后逐步改进

**输入内容示例**：
- "很好！这个功能已经基本完成了。现在让我们快速实现下一个核心功能：[具体功能名称]。先做一个简单能用的版本。"
- "这个错误不是关键问题，我们用最简单的方法修复：[简单解决方案]。然后继续开发主要功能。"
- "当前进展良好，让我们继续推进项目。下一步需要实现：[下一个功能]。用最直接的方法实现。"

对于每种情况，提供JSON格式的操作指令：

```json
{
    "action_type": "type",
    "target": "chat_input",
    "value": "推动项目进展的具体指令",
    "confidence": 0.9,
    "reasoning": "推动项目功能完成"
}
```

**记住：我们的目标是快速搭建起整个程序并确保能用，细节优化留到后面！**
"""
    
    def analyze_situation(self, screenshot: Image.Image, context: str) -> Dict[str, Any]:
        """分析当前情况并生成操作指令"""
        try:
            # 将截图转换为base64
            screenshot_base64 = self.image_to_base64(screenshot)
            
            # 构建消息
            messages = [
                {
                    "role": "system", 
                    "content": self.system_prompt
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"分析这个CURSOR IDE截图的状态。上下文：{context}\n\n请提供详细的分析和操作建议。"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{screenshot_base64}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ]
            
            # 添加对话历史（最近几轮）
            messages.extend(self.conversation_history[-4:])
            
            # 调用GPT-4O
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=1000,
                temperature=0.1  # 低温度以获得更一致的结果
            )
            
            # 解析响应
            response_text = response.choices[0].message.content
            logger.info(f"GPT分析结果: {response_text[:200]}...")
            
            # 尝试提取JSON操作指令
            action_data = self.extract_action_from_response(response_text)
            
            # 更新对话历史
            self.update_conversation_history(context, response_text)
            
            return {
                "analysis": response_text,
                "action": action_data,
                "timestamp": time.time(),
                "context": context
            }
            
        except Exception as e:
            logger.error(f"GPT分析时出错: {e}")
            return {
                "analysis": f"分析失败: {str(e)}",
                "action": {
                    "action_type": "wait",
                    "target": "error_recovery",
                    "value": None,
                    "confidence": 0.0,
                    "reasoning": "分析出错，选择等待策略"
                },
                "timestamp": time.time(),
                "context": context
            }
    
    def extract_action_from_response(self, response_text: str) -> Dict[str, Any]:
        """从GPT响应中提取操作指令"""
        try:
            # 尝试找到JSON块
            import re
            json_pattern = r'```json\s*(.*?)\s*```'
            json_match = re.search(json_pattern, response_text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
                action_data = json.loads(json_str)
                
                # 验证必要字段
                required_fields = ["action_type", "confidence", "reasoning"]
                for field in required_fields:
                    if field not in action_data:
                        action_data[field] = self.get_default_value(field)
                
                return action_data
            
            # 如果没有找到JSON，尝试解析文本描述
            return self.parse_text_action(response_text)
            
        except Exception as e:
            logger.error(f"提取操作指令时出错: {e}")
            return {
                "action_type": "analyze",
                "target": "unknown",
                "confidence": 0.3,
                "reasoning": "无法解析GPT响应，需要重新分析"
            }
    
    def parse_text_action(self, text: str) -> Dict[str, Any]:
        """解析文本描述的操作"""
        text_lower = text.lower()
        
        # 识别操作类型
        if any(keyword in text_lower for keyword in ["click", "点击"]):
            action_type = "click"
        elif any(keyword in text_lower for keyword in ["type", "input", "输入"]):
            action_type = "type"
        elif any(keyword in text_lower for keyword in ["press", "按键"]):
            action_type = "key_press"
        elif any(keyword in text_lower for keyword in ["wait", "等待"]):
            action_type = "wait"
        else:
            action_type = "analyze"
        
        return {
            "action_type": action_type,
            "target": "parsed_from_text",
            "confidence": 0.6,
            "reasoning": f"从文本解析得出: {text[:100]}..."
        }
    
    def get_default_value(self, field: str) -> Any:
        """获取字段的默认值"""
        defaults = {
            "action_type": "wait",
            "target": "unknown",
            "value": None,
            "coordinates": None,
            "confidence": 0.5,
            "reasoning": "默认操作",
            "follow_up_actions": []
        }
        return defaults.get(field, None)
    
    def image_to_base64(self, image: Image.Image) -> str:
        """将PIL图像转换为base64字符串"""
        try:
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            return img_base64
        except Exception as e:
            logger.error(f"图像转base64时出错: {e}")
            return ""
    
    def update_conversation_history(self, context: str, response: str):
        """更新对话历史"""
        self.conversation_history.append({
            "role": "assistant",
            "content": response
        })
        
        # 保持历史长度限制
        if len(self.conversation_history) > self.max_history_length:
            self.conversation_history = self.conversation_history[-self.max_history_length:]
    
    def analyze_error(self, screenshot: Image.Image, error_text: str) -> Dict[str, Any]:
        """专门分析错误情况"""
        context = f"CURSOR出现错误，错误信息：{error_text}"
        
        messages = [
            {
                "role": "system",
                "content": self.system_prompt + "\n\n特别注意：这是一个错误分析请求，请重点关注错误修复。"
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"CURSOR IDE出现了错误。请分析截图中的错误信息并提供修复建议。\n错误上下文：{error_text}"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{self.image_to_base64(screenshot)}",
                            "detail": "high"
                        }
                    }
                ]
            }
        ]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=1200,
                temperature=0.1
            )
            
            response_text = response.choices[0].message.content
            action_data = self.extract_action_from_response(response_text)
            
            return {
                "analysis": response_text,
                "action": action_data,
                "error_context": error_text,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"错误分析时出错: {e}")
            return {
                "analysis": f"错误分析失败: {str(e)}",
                "action": {
                    "action_type": "wait",
                    "reasoning": "分析错误，暂时等待"
                },
                "timestamp": time.time()
            }
    
    def suggest_continuation(self, screenshot: Image.Image, stuck_duration: int) -> Dict[str, Any]:
        """为卡住的情况提供建议"""
        context = f"CURSOR已经卡住 {stuck_duration} 秒，需要干预"
        
        messages = [
            {
                "role": "system",
                "content": self.system_prompt + f"\n\n特别注意：CURSOR已经卡住了{stuck_duration}秒，需要采取行动让它继续工作。"
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"CURSOR IDE似乎卡住了（已经{stuck_duration}秒没有变化）。请分析当前状态并建议如何让它继续工作。"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{self.image_to_base64(screenshot)}",
                            "detail": "high"
                        }
                    }
                ]
            }
        ]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=1000,
                temperature=0.2
            )
            
            response_text = response.choices[0].message.content
            action_data = self.extract_action_from_response(response_text)
            
            return {
                "analysis": response_text,
                "action": action_data,
                "stuck_duration": stuck_duration,
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"卡住状态分析时出错: {e}")
            return {
                "analysis": f"卡住状态分析失败: {str(e)}",
                "action": {
                    "action_type": "key_press",
                    "value": "Escape",
                    "reasoning": "尝试按Escape键恢复"
                },
                "timestamp": time.time()
            }
    
    def clear_conversation_history(self):
        """清空对话历史"""
        self.conversation_history.clear()
        logger.info("对话历史已清空")
    
    def get_analysis_stats(self) -> Dict[str, Any]:
        """获取分析统计信息"""
        return {
            "conversation_length": len(self.conversation_history),
            "cache_size": len(self.analysis_cache),
            "last_analysis_time": getattr(self, 'last_analysis_time', 0)
        }
    
    def analyze_completed_task(self, screenshot: Image.Image, completed_text: str, context: str) -> Dict[str, Any]:
        """专门分析完成的任务内容，从主力操盘手角度提供深度分析和建议"""
        try:
            logger.info("🔍 开始GPT完成任务分析...")
            # 将截图转换为base64
            screenshot_base64 = self.image_to_base64(screenshot)
            
            # 构建专门针对完成任务的系统提示词
            completion_analysis_prompt = """
你是一个具备主力操盘手思维的CURSOR IDE专家助手。现在需要分析一个刚刚完成的编程任务。

从主力操盘手的角度，你需要：
1. **反人性分析**: 识别完成内容中可能的"诱多"陷阱或过度乐观
2. **深度价值评估**: 客观评估实际价值，避免被表面成功迷惑  
3. **下一步策略**: 从操盘手角度建议最优后续行动
4. **风险识别**: 指出可能被忽视的潜在问题

请提供简洁的分析结果（不超过500字）：

```json
{
    "action_type": "continue_conversation|provide_feedback|suggest_improvements|acknowledge_completion",
    "master_analysis": "从主力操盘手角度的深度分析",
    "value_assessment": "实际价值评估（避免被表面成功迷惑）",
    "risk_identification": "潜在风险和陷阱识别",  
    "next_strategy": "基于主力思维的下一步策略",
    "confidence": 0.0-1.0,
    "reasoning": "选择此行动的主力操盘手逻辑"
}
```

重要原则：
- 保持主力操盘手的冷静理性，不被表面成功冲昏头脑
- 识别散户思维陷阱，提供反人性的深度见解
- 关注长期战略价值，而非短期表面成果
- 提供具体可行的后续行动建议
"""
            
            # 构建消息
            messages = [
                {
                    "role": "system", 
                    "content": completion_analysis_prompt
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"""刚刚完成了一个编程任务，请从主力操盘手角度进行深度分析。

任务上下文：{context}

完成内容文本：{completed_text[:1000]}

请提供简洁的主力操盘手分析（不超过500字）。"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{screenshot_base64}",
                                "detail": "low"  # 降低图像细节以加快处理
                            }
                        }
                    ]
                }
            ]
            
            logger.info("📡 发送GPT API请求...")
            
            # 添加超时设置的API调用（Windows兼容版本）
            import signal
            import functools
            import threading
            import platform
            
            timeout_occurred = False
            timer = None
            
            def timeout_handler():
                nonlocal timeout_occurred
                timeout_occurred = True
                logger.warning("⏰ GPT API调用超时（30秒）")
            
            # Windows系统兼容的超时处理
            if platform.system() == "Windows":
                # 在Windows上使用Timer
                timer = threading.Timer(30.0, timeout_handler)
                timer.start()
            else:
                # 在Unix系统上使用SIGALRM
                def signal_timeout_handler(signum, frame):
                    raise TimeoutError("GPT API调用超时")
                signal.signal(signal.SIGALRM, signal_timeout_handler)
                signal.alarm(30)
            
            try:
                # 调用GPT-4O进行专门的完成任务分析
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    max_tokens=800,  # 减少token数量加快响应
                    temperature=0.2,  # 更低温度以获得更理性的分析
                    timeout=25  # 25秒超时
                )
                
                # 取消超时
                if timer:
                    timer.cancel()
                elif platform.system() != "Windows":
                    signal.alarm(0)
                
                # 检查是否超时
                if timeout_occurred:
                    logger.error("⏰ GPT API调用超时（30秒）")
                    return self._get_timeout_fallback_analysis(context, completed_text)
                
                logger.info("✅ GPT API响应成功")
                
            except TimeoutError:
                # 取消超时
                if timer:
                    timer.cancel()
                elif platform.system() != "Windows":
                    signal.alarm(0)
                logger.error("⏰ GPT API调用超时（30秒）")
                return self._get_timeout_fallback_analysis(context, completed_text)
            except Exception as api_error:
                # 取消超时
                if timer:
                    timer.cancel()
                elif platform.system() != "Windows":
                    signal.alarm(0)
                logger.error(f"❌ GPT API调用失败: {api_error}")
                return self._get_api_error_fallback_analysis(context, completed_text, str(api_error))
            
            # 解析响应
            response_text = response.choices[0].message.content
            logger.info(f"📝 GPT完成任务分析: {response_text[:300]}...")
            
            # 尝试提取JSON分析结果
            analysis_data = self.extract_completion_analysis(response_text)
            
            # 更新对话历史
            self.update_conversation_history(f"任务完成分析: {context}", response_text)
            
            return {
                "analysis": response_text,
                "action": analysis_data,
                "master_analysis": analysis_data.get("master_analysis", ""),
                "value_assessment": analysis_data.get("value_assessment", ""),
                "risk_identification": analysis_data.get("risk_identification", ""),
                "next_strategy": analysis_data.get("next_strategy", ""),
                "timestamp": time.time(),
                "context": context,
                "completion_text": completed_text
            }
            
        except Exception as e:
            logger.error(f"❌ 完成任务分析时出错: {e}")
            return self._get_general_error_fallback_analysis(context, completed_text, str(e))
    
    def _get_timeout_fallback_analysis(self, context: str, completed_text: str) -> Dict[str, Any]:
        """超时后的备用分析"""
        return {
            "analysis": "⏰ GPT分析超时，使用本地备用分析",
            "action": {
                "action_type": "provide_feedback",
                "master_analysis": "检测到任务完成，但网络分析超时。从主力角度建议：先验证基础功能是否正常",
                "value_assessment": "需要手动验证完成质量，避免被表面完成迷惑",
                "risk_identification": "网络分析不可用，存在盲点风险",
                "next_strategy": "优先进行本地测试，确认基础功能无误后再考虑下一步",
                "confidence": 0.6,
                "reasoning": "网络超时，采用保守的主力策略"
            },
            "timestamp": time.time(),
            "context": context,
            "fallback_reason": "api_timeout"
        }
    
    def _get_api_error_fallback_analysis(self, context: str, completed_text: str, error_msg: str) -> Dict[str, Any]:
        """API错误后的备用分析"""
        return {
            "analysis": f"❌ GPT API错误，使用本地备用分析: {error_msg}",
            "action": {
                "action_type": "provide_feedback", 
                "master_analysis": "检测到任务完成，但API分析失败。从主力角度：这种情况下更要保持理性",
                "value_assessment": "无法使用AI深度分析，需要依靠主力经验手动评估价值",
                "risk_identification": "分析工具失效，存在判断盲区风险",
                "next_strategy": "采用最保守策略：逐步验证，小步试错",
                "confidence": 0.5,
                "reasoning": "API失效时的主力应急策略"
            },
            "timestamp": time.time(),
            "context": context,
            "fallback_reason": "api_error"
        }
    
    def _get_general_error_fallback_analysis(self, context: str, completed_text: str, error_msg: str) -> Dict[str, Any]:
        """通用错误后的备用分析"""
        return {
            "analysis": f"🛠️ 分析系统遇到问题，使用本地备用分析: {error_msg}",
            "action": {
                "action_type": "acknowledge_completion",
                "master_analysis": "系统检测到任务完成。虽然深度分析暂时不可用，但主力思维告诉我们要保持冷静",
                "value_assessment": "需要手动验证完成质量和实际价值",
                "risk_identification": "分析系统异常，存在判断风险",
                "next_strategy": "使用传统方法：代码审查、手动测试、逐步验证",
                "confidence": 0.4,
                "reasoning": "系统异常时的主力保守策略"
            },
            "timestamp": time.time(),
            "context": context,
            "fallback_reason": "system_error"
        }
    
    def extract_completion_analysis(self, response_text: str) -> Dict[str, Any]:
        """从GPT响应中提取完成任务分析结果"""
        try:
            # 尝试找到JSON块
            import re
            json_pattern = r'```json\s*(.*?)\s*```'
            json_match = re.search(json_pattern, response_text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
                analysis_data = json.loads(json_str)
                
                # 验证必要字段
                required_fields = ["action_type", "confidence", "reasoning"]
                for field in required_fields:
                    if field not in analysis_data:
                        analysis_data[field] = self.get_completion_default_value(field)
                
                return analysis_data
            
            # 如果没有找到JSON，基于关键词生成分析
            return self.parse_completion_text_analysis(response_text)
            
        except Exception as e:
            logger.error(f"提取完成分析时出错: {e}")
            return {
                "action_type": "provide_feedback",
                "master_analysis": "从文本中解析的主力分析",
                "confidence": 0.6,
                "reasoning": f"解析完成分析，基于文本内容: {response_text[:200]}..."
            }
    
    def parse_completion_text_analysis(self, text: str) -> Dict[str, Any]:
        """解析文本形式的完成分析"""
        text_lower = text.lower()
        
        # 识别行动类型
        if any(keyword in text_lower for keyword in ["继续对话", "continue", "discuss", "交流"]):
            action_type = "continue_conversation"
        elif any(keyword in text_lower for keyword in ["改进", "improve", "optimize", "enhance"]):
            action_type = "suggest_improvements"
        elif any(keyword in text_lower for keyword in ["反馈", "feedback", "评价"]):
            action_type = "provide_feedback"
        else:
            action_type = "acknowledge_completion"
        
        return {
            "action_type": action_type,
            "master_analysis": f"基于主力操盘手思维的分析: {text[:300]}...",
            "confidence": 0.7,
            "reasoning": f"从文本分析得出的主力视角建议"
        }
    
    def get_completion_default_value(self, field: str) -> Any:
        """获取完成分析字段的默认值"""
        defaults = {
            "action_type": "acknowledge_completion",
            "master_analysis": "任务完成，需要从主力角度进一步分析",
            "value_assessment": "初步评估显示任务已完成，需深入验证实际价值",
            "risk_identification": "需要识别潜在风险和盲点",
            "next_strategy": "建议进行实战测试以验证真实效果",
            "confidence": 0.7,
            "reasoning": "基于主力操盘手经验的保守判断",
            "conversation_trigger": "建议主动对话以获取更多信息"
        }
        return defaults.get(field, None)
    
    async def analyze_cursor_state(self, screenshot: Image.Image, extracted_text: str, context: str = "") -> Dict[str, Any]:
        """异步分析CURSOR状态 - 保持向后兼容性"""
        try:
            return self.analyze_situation(screenshot, f"{context}\n当前文本内容: {extracted_text}")
        except Exception as e:
            logger.error(f"异步CURSOR状态分析失败: {e}")
            return {
                "analysis": f"异步分析失败: {str(e)}",
                "action": {
                    "action_type": "wait",
                    "confidence": 0.0,
                    "reasoning": "异步分析出错，等待恢复"
                }
            }

    def analyze_as_product_manager(self, screenshot: Image.Image, cursor_reply: str, 
                                 project_context: str, conversation_history: str, 
                                 current_stage: str) -> str:
        """作为产品经理分析CURSOR回复并生成对话回复"""
        try:
            # 产品导向的开发推进者系统提示词
            product_manager_prompt = """
你是一个专注于产品功能快速实现的开发推进者。你的使命是推动项目快速完成主要功能，避免陷入技术细节的无限优化。

**核心原则：功能优先，细节后续**

**你的任务**：
1. 快速识别当前功能完成状态
2. 立即推动下一个核心功能的开发
3. 遇到问题时选择最简单直接的解决方案
4. 避免过度优化和完美主义陷阱

**推进策略**：
- 当功能基本完成时：立即转向下一个功能
- 遇到错误时：快速修复，不深究原理
- 出现性能问题：先忽略，除非严重影响使用
- 代码不够完美：先能用，后续迭代

**回复模式**：
- "很好！[功能名]已经基本能用了，现在我们立即开始下一个核心功能：[下一功能]"
- "这个错误用最简单的方法解决：[简单方案]，然后继续推进主功能"
- "当前进展不错，让我们专注于核心功能实现，细节优化留到后面"

**绝对避免**：
- 过度分析技术细节
- 纠结于代码质量问题
- 无限制的性能优化
- 完美主义的重构需求

**目标导向**：
你的目标是让整个项目快速达到"能用"状态，形成完整的功能闭环，而不是打造完美的代码。

**回复要求**：
- 100-200字，直接推动下一步行动
- 专注于功能实现进度
- 保持高效快节奏
- 体现产品思维而非技术思维
"""

            # 将截图转换为base64
            screenshot_base64 = self.image_to_base64(screenshot)
            
            # 检查cursor_reply中是否包含GPT_VISION_REQUIRED标记
            vision_images = []
            cursor_reply_processed = cursor_reply
            
            # 处理GPT_VISION_REQUIRED标记
            if "GPT_VISION_REQUIRED:" in cursor_reply:
                lines = cursor_reply.split('\n')
                processed_lines = []
                
                for line in lines:
                    if "GPT_VISION_REQUIRED:" in line:
                        # 提取图片路径
                        try:
                            image_path = line.split("GPT_VISION_REQUIRED:")[1].strip()
                            if os.path.exists(image_path):
                                # 读取图片并转换为base64
                                from PIL import Image as PILImage
                                region_image = PILImage.open(image_path)
                                region_base64 = self.image_to_base64(region_image)
                                vision_images.append(region_base64)
                                processed_lines.append(f"[区域图片] OCR识别失败，已提供图片供视觉分析")
                                logger.info(f"✅ 已添加区域图片到GPT-4O视觉分析: {image_path}")
                            else:
                                processed_lines.append(f"[区域图片] 图片文件不存在: {image_path}")
                        except Exception as e:
                            logger.error(f"处理区域图片失败: {e}")
                            processed_lines.append(line)
                    else:
                        processed_lines.append(line)
                
                cursor_reply_processed = '\n'.join(processed_lines)
            
            # 构建用户消息内容
            user_content = [
                {
                    "type": "text",
                    "text": f"""作为产品功能推进者，请分析CURSOR的回复并推动项目快速完成：

**项目状态**：
{project_context[:400]}

**当前阶段**：{current_stage}

**最近进展**：
{conversation_history[:600]}

**CURSOR最新回复**：
{cursor_reply_processed}

**推进任务**：
基于CURSOR的回复，立即推动项目向前发展，避免陷入技术细节。

**推进重点**：
1. 快速判断当前功能是否基本可用
2. 如果可用，立即转向下一个核心功能
3. 如果有问题，选择最简单的解决方案
4. 明确下一步具体要实现的功能

**回复要求**：
- 100-200字，直接推动行动
- 专注于功能完成进度
- 避免技术细节纠结
- 体现"先能用，再完美"的产品思维

**立即给出推进指令，推动项目快速前进！**"""
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{screenshot_base64}",
                        "detail": "high"
                    }
                }
            ]
            
            # 添加额外的区域图片
            for region_base64 in vision_images:
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{region_base64}",
                        "detail": "high"
                    }
                })
            
            # 构建消息
            messages = [
                {
                    "role": "system",
                    "content": product_manager_prompt
                },
                {
                    "role": "user",
                    "content": user_content
                }
            ]
            
            # 调用GPT-4O
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=600,  # 增加token限制以支持更详细的技术回复
                temperature=0.3  # 降低温度以获得更准确的技术建议
            )
            
            # 获取回复内容
            pm_reply = response.choices[0].message.content.strip()
            
            logger.info(f"GPT-4O产品经理回复: {pm_reply[:100]}...")
            
            return pm_reply
            
        except Exception as e:
            logger.error(f"GPT-4O技术分析失败: {e}")
            # 返回一个技术性的fallback回复
            if "错误" in cursor_reply or "error" in cursor_reply.lower():
                return f"看到错误信息了。让我们先分析一下错误的根本原因，然后制定具体的修复方案。请提供完整的错误堆栈，这样我可以帮你定位问题所在。"
            elif "完成" in cursor_reply or "实现" in cursor_reply:
                return f"代码实现完成了。接下来需要验证功能是否正常工作，建议先进行单元测试，然后检查边界情况处理。有什么需要优化的地方吗？"
            else:
                return f"明白当前的技术状况。基于{current_stage}，建议我们先确认核心功能的实现逻辑，然后逐步完善细节。具体的实现方案你有什么想法？" 
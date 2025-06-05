#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目规划管理模块
功能：读取MD项目规划文件，解析任务，跟踪进度，生成针对性指令
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)

class ProjectPlanner:
    """项目规划管理器"""
    
    def __init__(self):
        self.project_file = None
        self.project_content = ""
        self.project_title = ""
        self.project_description = ""
        self.tasks = []
        self.current_task_index = 0
        self.progress_file = "project_progress.json"
        self.completed_tasks = set()
        self.task_status = {}
        
        # 任务完成检测关键词
        self.completion_keywords = [
            "完成", "完工", "完毕", "已完成", "finished", "completed", "done",
            "实现", "创建成功", "生成成功", "测试通过", "运行成功",
            "✅", "✓", "success", "successfully"
        ]
        
        # 任务进行中关键词
        self.in_progress_keywords = [
            "开始", "正在", "处理中", "开发中", "实现中", "编写中",
            "starting", "working", "developing", "implementing"
        ]
    
    def select_project_file(self) -> Optional[str]:
        """交互式选择项目MD文件"""
        print("\n" + "="*60)
        print("🎯 AI大脑系统 - 项目规划模式")
        print("="*60)
        
        # 扫描当前目录下的MD文件
        md_files = [f for f in os.listdir('.') if f.endswith('.md')]
        
        print("📁 当前目录MD文件:")
        if md_files:
            for i, file in enumerate(md_files, 1):
                print(f"  {i}. {file}")
        else:
            print("  ❌ 当前目录下没有MD文件")
        
        print("\n📝 请选择项目文件:")
        print("  - 输入文件编号 (1-{})".format(len(md_files)) if md_files else "")
        print("  - 输入文件名 (如: 贪吃蛇游戏项目.md)")
        print("  - 输入完整路径 (如: D:\\桌面备份\\AI\\CURSOR\\贪吃蛇游戏项目.md)")
        print("  - 按 Enter 跳过项目规划模式")
        
        while True:
            try:
                user_input = input("\n👉 您的选择: ").strip()
                
                if not user_input:
                    print("ℹ️ 跳过项目规划模式，使用默认产品经理模式")
                    return None
                
                # 尝试作为数字处理 (当前目录文件编号)
                if user_input.isdigit() and md_files:
                    index = int(user_input) - 1
                    if 0 <= index < len(md_files):
                        selected_file = md_files[index]
                        print(f"✅ 已选择项目文件: {selected_file}")
                        return selected_file
                    else:
                        print(f"❌ 无效编号，请输入 1-{len(md_files)}")
                        continue
                
                # 检查是否为完整路径
                if os.path.isabs(user_input):
                    if os.path.exists(user_input) and user_input.endswith('.md'):
                        print(f"✅ 已选择项目文件: {user_input}")
                        return user_input
                    else:
                        print(f"❌ 路径文件不存在或不是MD文件: {user_input}")
                        continue
                
                # 尝试作为当前目录的文件名处理
                if not user_input.endswith('.md'):
                    user_input += '.md'
                
                if os.path.exists(user_input):
                    print(f"✅ 已选择项目文件: {user_input}")
                    return user_input
                else:
                    print(f"❌ 文件不存在: {user_input}")
                    print("💡 提示：可以输入完整路径，例如:")
                    print("   D:\\桌面备份\\AI\\CURSOR\\贪吃蛇游戏项目.md")
                    continue
                        
            except ValueError:
                print("❌ 输入无效，请重新输入")
            except KeyboardInterrupt:
                print("\n❌ 用户取消操作")
                return None
    
    def load_project_file(self, file_path: str) -> bool:
        """加载项目MD文件"""
        try:
            if not os.path.exists(file_path):
                logger.error(f"❌ 项目文件不存在: {file_path}")
                return False
            
            with open(file_path, 'r', encoding='utf-8') as f:
                self.project_content = f.read()
            
            self.project_file = file_path
            self._parse_project_content()
            self._load_progress()
            
            logger.info(f"✅ 项目文件加载成功: {file_path}")
            logger.info(f"📋 项目标题: {self.project_title}")
            logger.info(f"📝 共发现 {len(self.tasks)} 个任务")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 加载项目文件失败: {e}")
            return False
    
    def _parse_project_content(self):
        """解析项目内容"""
        lines = self.project_content.split('\n')
        current_task = None
        task_content = []
        
        for line in lines:
            line = line.strip()
            
            # 提取项目标题 (第一个一级标题)
            if line.startswith('# ') and not self.project_title:
                self.project_title = line[2:].strip()
                continue
            
            # 提取项目描述 (第一个段落)
            if not self.project_description and line and not line.startswith('#'):
                if not line.startswith('-') and not line.startswith('*'):
                    self.project_description = line
                    continue
            
            # 识别任务标题 (二级标题或任务列表)
            if line.startswith('## ') or line.startswith('### '):
                # 保存上一个任务
                if current_task:
                    current_task['content'] = '\n'.join(task_content).strip()
                    self.tasks.append(current_task)
                
                # 开始新任务
                task_title = re.sub(r'^#+\s*', '', line).strip()
                current_task = {
                    'id': len(self.tasks),
                    'title': task_title,
                    'content': '',
                    'status': 'pending',
                    'dependencies': [],
                    'priority': 'normal'
                }
                task_content = []
                continue
            
            # 识别任务列表项
            if re.match(r'^[-*+]\s+', line):
                # 保存上一个任务
                if current_task:
                    current_task['content'] = '\n'.join(task_content).strip()
                    self.tasks.append(current_task)
                
                # 开始新任务
                task_title = re.sub(r'^[-*+]\s+', '', line).strip()
                current_task = {
                    'id': len(self.tasks),
                    'title': task_title,
                    'content': '',
                    'status': 'pending',
                    'dependencies': [],
                    'priority': 'normal'
                }
                task_content = []
                continue
            
            # 收集任务内容
            if current_task and line:
                task_content.append(line)
        
        # 保存最后一个任务
        if current_task:
            current_task['content'] = '\n'.join(task_content).strip()
            self.tasks.append(current_task)
        
        # 如果没有找到任务，尝试按段落分割
        if not self.tasks:
            self._parse_by_paragraphs()
    
    def _parse_by_paragraphs(self):
        """按段落解析任务"""
        paragraphs = self.project_content.split('\n\n')
        
        for i, paragraph in enumerate(paragraphs):
            paragraph = paragraph.strip()
            if paragraph and not paragraph.startswith('#'):
                # 取段落第一行作为标题
                lines = paragraph.split('\n')
                title = lines[0].strip()
                content = '\n'.join(lines[1:]).strip() if len(lines) > 1 else paragraph
                
                task = {
                    'id': len(self.tasks),
                    'title': title[:100] + '...' if len(title) > 100 else title,
                    'content': content,
                    'status': 'pending',
                    'dependencies': [],
                    'priority': 'normal'
                }
                self.tasks.append(task)
    
    def _load_progress(self):
        """加载项目进度"""
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress_data = json.load(f)
                
                if progress_data.get('project_file') == self.project_file:
                    self.current_task_index = progress_data.get('current_task_index', 0)
                    self.completed_tasks = set(progress_data.get('completed_tasks', []))
                    self.task_status = progress_data.get('task_status', {})
                    
                    # 更新任务状态
                    for task in self.tasks:
                        task_id = str(task['id'])
                        if task_id in self.task_status:
                            task['status'] = self.task_status[task_id]
                    
                    logger.info(f"✅ 加载项目进度: 当前任务 {self.current_task_index}")
                else:
                    logger.info("🔄 新项目，重置进度")
            else:
                logger.info("📝 创建新的项目进度文件")
                
        except Exception as e:
            logger.error(f"❌ 加载进度失败: {e}")
    
    def _save_progress(self):
        """保存项目进度"""
        try:
            progress_data = {
                'project_file': self.project_file,
                'current_task_index': self.current_task_index,
                'completed_tasks': list(self.completed_tasks),
                'task_status': self.task_status,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"❌ 保存进度失败: {e}")
    
    def get_current_task(self) -> Optional[Dict[str, Any]]:
        """获取当前任务"""
        if 0 <= self.current_task_index < len(self.tasks):
            return self.tasks[self.current_task_index]
        return None
    
    def get_project_context(self) -> str:
        """获取项目上下文信息"""
        context = f"📋 项目: {self.project_title}\n"
        if self.project_description:
            context += f"📝 描述: {self.project_description}\n"
        
        context += f"📊 进度: {len(self.completed_tasks)}/{len(self.tasks)} 任务完成\n"
        
        current_task = self.get_current_task()
        if current_task:
            context += f"🎯 当前任务: {current_task['title']}\n"
            if current_task['content']:
                context += f"📄 任务详情: {current_task['content'][:200]}...\n"
        
        return context
    
    def generate_task_instruction(self, cursor_reply: str = "") -> str:
        """基于当前任务生成具体指令"""
        current_task = self.get_current_task()
        
        if not current_task:
            return "所有任务已完成！🎉"
        
        # 检查任务是否已完成
        if self.is_task_completed(cursor_reply, current_task):
            self.mark_task_completed(current_task['id'])
            return self.move_to_next_task()
        
        # 生成任务指令
        instruction = self._generate_specific_instruction(current_task, cursor_reply)
        return instruction
    
    def _generate_specific_instruction(self, task: Dict[str, Any], cursor_reply: str) -> str:
        """生成具体的任务指令"""
        task_title = task['title']
        task_content = task['content']
        
        # 基于任务内容生成针对性指令
        if "创建" in task_title or "新建" in task_title:
            instruction = f"请创建 {task_title.replace('创建', '').replace('新建', '').strip()}"
        elif "实现" in task_title or "开发" in task_title:
            instruction = f"请实现 {task_title.replace('实现', '').replace('开发', '').strip()}"
        elif "修改" in task_title or "优化" in task_title:
            instruction = f"请修改和优化 {task_title.replace('修改', '').replace('优化', '').strip()}"
        elif "测试" in task_title:
            instruction = f"请测试 {task_title.replace('测试', '').strip()}"
        else:
            instruction = f"请完成: {task_title}"
        
        # 添加具体要求
        if task_content:
            instruction += f"\n\n具体要求:\n{task_content}"
        
        # 添加项目上下文
        instruction += f"\n\n项目背景: {self.project_title}"
        if self.project_description:
            instruction += f" - {self.project_description}"
        
        return instruction.strip()
    
    def is_task_completed(self, cursor_reply: str, task: Dict[str, Any]) -> bool:
        """检测任务是否完成"""
        if not cursor_reply:
            return False
        
        reply_lower = cursor_reply.lower()
        task_title_lower = task['title'].lower()
        
        # 检查完成关键词
        for keyword in self.completion_keywords:
            if keyword.lower() in reply_lower:
                # 进一步验证是否与当前任务相关
                if any(word in reply_lower for word in task_title_lower.split()):
                    logger.info(f"✅ 检测到任务完成信号: {keyword}")
                    return True
        
        # 检查具体的任务完成模式
        completion_patterns = [
            r'(?:已|成功)(?:创建|实现|完成|生成).*' + re.escape(task_title_lower.split()[0]) if task_title_lower.split() else '',
            r'(?:完成|finished|completed|done).*(?:任务|task)',
            r'(?:测试|test).*(?:通过|passed|success)',
            r'(?:运行|run).*(?:成功|successfully)',
        ]
        
        for pattern in completion_patterns:
            if pattern and re.search(pattern, reply_lower):
                logger.info(f"✅ 匹配任务完成模式: {pattern}")
                return True
        
        return False
    
    def mark_task_completed(self, task_id: int):
        """标记任务为已完成"""
        self.completed_tasks.add(task_id)
        self.task_status[str(task_id)] = 'completed'
        
        if 0 <= task_id < len(self.tasks):
            self.tasks[task_id]['status'] = 'completed'
        
        self._save_progress()
        logger.info(f"✅ 任务 {task_id} 已标记为完成")
    
    def move_to_next_task(self) -> str:
        """移动到下一个任务"""
        self.current_task_index += 1
        self._save_progress()
        
        next_task = self.get_current_task()
        if next_task:
            logger.info(f"🔄 切换到下一任务: {next_task['title']}")
            return f"任务完成！正在进行下一个任务: {next_task['title']}\n\n{self._generate_specific_instruction(next_task, '')}"
        else:
            logger.info("🎉 所有任务已完成!")
            return "🎉 恭喜！所有项目任务已完成！"
    
    def get_progress_summary(self) -> str:
        """获取进度摘要"""
        total_tasks = len(self.tasks)
        completed_count = len(self.completed_tasks)
        
        summary = f"📊 项目进度报告\n"
        summary += f"项目: {self.project_title}\n"
        summary += f"总任务数: {total_tasks}\n"
        summary += f"已完成: {completed_count}\n"
        summary += f"进度: {completed_count/total_tasks*100:.1f}%\n\n"
        
        # 列出任务状态
        for i, task in enumerate(self.tasks):
            status_icon = "✅" if task['status'] == 'completed' else "⏳" if i == self.current_task_index else "⏸️"
            summary += f"{status_icon} {task['title']}\n"
        
        return summary
    
    def reset_progress(self):
        """重置项目进度"""
        self.current_task_index = 0
        self.completed_tasks.clear()
        self.task_status.clear()
        
        for task in self.tasks:
            task['status'] = 'pending'
        
        self._save_progress()
        logger.info("🔄 项目进度已重置")
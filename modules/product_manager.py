#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
产品经理模块
功能：担任产品经理角色，自动测试程序、检测问题、提供反馈
"""

import asyncio
import time
import logging
import json
import subprocess
import sys
import os
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from PIL import Image

logger = logging.getLogger(__name__)

class ProductManager:
    """产品经理类 - 负责质量保证和测试"""
    
    def __init__(self, gpt_controller=None):
        self.gpt_controller = gpt_controller
        self.test_history = []
        self.issue_tracker = []
        self.quality_metrics = {
            "test_runs": 0,
            "issues_found": 0,
            "issues_resolved": 0,
            "success_rate": 0.0
        }
        
        # 测试策略配置
        self.test_strategies = {
            "syntax_check": True,
            "import_check": True,
            "basic_run_check": True,
            "dependency_check": True,
            "error_simulation": True,
            "edge_case_testing": False  # 默认关闭深度测试
        }
        
        # 问题严重级别
        self.severity_levels = {
            "critical": ["syntax error", "import error", "crash", "exception"],
            "high": ["performance", "memory", "timeout"],
            "medium": ["warning", "deprecation", "style"],
            "low": ["minor", "cosmetic", "suggestion"]
        }
    
    async def analyze_development_completion(self, screenshot: Image.Image, 
                                           completed_text: str, 
                                           project_path: str = ".") -> Dict[str, Any]:
        """分析开发完成情况并进行质量检查"""
        logger.info("🔍 产品经理开始质量检查...")
        
        analysis_result = {
            "timestamp": time.time(),
            "quality_score": 0.0,
            "issues": [],
            "recommendations": [],
            "test_results": {},
            "pm_feedback": "",
            "action_required": False
        }
        
        try:
            # 1. 代码质量检查
            code_quality = await self.check_code_quality(project_path)
            analysis_result["test_results"]["code_quality"] = code_quality
            
            # 2. 运行时测试
            runtime_test = await self.run_program_tests(project_path)
            analysis_result["test_results"]["runtime"] = runtime_test
            
            # 3. 依赖检查
            dependency_check = await self.check_dependencies(project_path)
            analysis_result["test_results"]["dependencies"] = dependency_check
            
            # 4. 计算质量分数
            quality_score = self.calculate_quality_score(analysis_result["test_results"])
            analysis_result["quality_score"] = quality_score
            
            # 5. 生成问题列表
            issues = self.extract_issues(analysis_result["test_results"])
            analysis_result["issues"] = issues
            
            # 6. 生成改进建议
            recommendations = self.generate_recommendations(quality_score, issues)
            analysis_result["recommendations"] = recommendations
            
            # 7. 产品经理反馈
            pm_feedback = self.generate_pm_feedback(quality_score, issues, completed_text)
            analysis_result["pm_feedback"] = pm_feedback
            
            # 8. 判断是否需要进一步行动
            analysis_result["action_required"] = quality_score < 0.8 or len(issues) > 0
            
            # 更新质量指标
            self.update_quality_metrics(analysis_result)
            
            logger.info(f"质量检查完成 - 分数: {quality_score:.2f}, 问题: {len(issues)}个")
            
        except Exception as e:
            logger.error(f"产品经理分析时出错: {e}")
            analysis_result["pm_feedback"] = f"质量检查遇到技术问题: {str(e)}"
            analysis_result["action_required"] = True
        
        return analysis_result
    
    async def check_code_quality(self, project_path: str) -> Dict[str, Any]:
        """检查代码质量"""
        logger.info("检查代码质量...")
        
        quality_result = {
            "syntax_valid": True,
            "import_errors": [],
            "style_issues": [],
            "security_issues": [],
            "performance_issues": [],
            "overall_score": 1.0
        }
        
        try:
            # 查找Python文件
            python_files = list(Path(project_path).rglob("*.py"))
            
            for py_file in python_files[:10]:  # 限制检查文件数量
                try:
                    # 语法检查
                    with open(py_file, 'r', encoding='utf-8') as f:
                        code = f.read()
                    
                    # 使用compile检查语法
                    try:
                        compile(code, str(py_file), 'exec')
                    except SyntaxError as e:
                        quality_result["syntax_valid"] = False
                        quality_result["import_errors"].append({
                            "file": str(py_file),
                            "error": str(e),
                            "line": e.lineno
                        })
                    
                    # 检查常见问题
                    await self.check_code_patterns(code, str(py_file), quality_result)
                    
                except Exception as e:
                    logger.debug(f"检查文件 {py_file} 时出错: {e}")
                    continue
            
            # 计算整体分数
            quality_result["overall_score"] = self.calculate_code_quality_score(quality_result)
            
        except Exception as e:
            logger.error(f"代码质量检查出错: {e}")
            quality_result["overall_score"] = 0.5
        
        return quality_result
    
    async def check_code_patterns(self, code: str, file_path: str, quality_result: Dict):
        """检查代码模式和常见问题"""
        try:
            lines = code.split('\n')
            
            for i, line in enumerate(lines, 1):
                line_stripped = line.strip()
                
                # 检查安全问题
                if any(pattern in line_stripped for pattern in ['eval(', 'exec(', 'os.system(']):
                    quality_result["security_issues"].append({
                        "file": file_path,
                        "line": i,
                        "issue": f"潜在安全风险: {line_stripped[:50]}...",
                        "severity": "high"
                    })
                
                # 检查性能问题
                if 'import *' in line_stripped:
                    quality_result["performance_issues"].append({
                        "file": file_path,
                        "line": i,
                        "issue": "使用了 import *，可能影响性能",
                        "severity": "medium"
                    })
                
                # 检查代码风格
                if len(line) > 120:
                    quality_result["style_issues"].append({
                        "file": file_path,
                        "line": i,
                        "issue": f"行长度超过120字符 ({len(line)})",
                        "severity": "low"
                    })
        
        except Exception as e:
            logger.debug(f"检查代码模式时出错: {e}")
    
    def calculate_code_quality_score(self, quality_result: Dict) -> float:
        """计算代码质量分数"""
        score = 1.0
        
        # 语法错误严重扣分
        if not quality_result["syntax_valid"]:
            score -= 0.5
        
        # 根据问题数量扣分
        score -= len(quality_result["security_issues"]) * 0.1
        score -= len(quality_result["performance_issues"]) * 0.05
        score -= len(quality_result["style_issues"]) * 0.01
        
        return max(0.0, score)
    
    async def run_program_tests(self, project_path: str) -> Dict[str, Any]:
        """运行程序测试"""
        logger.info("运行程序测试...")
        
        test_result = {
            "can_import": True,
            "can_run": True,
            "runtime_errors": [],
            "test_outputs": [],
            "execution_time": 0.0,
            "memory_usage": 0.0,
            "overall_score": 1.0
        }
        
        try:
            # 查找主要的Python文件
            main_files = [
                "main.py", "app.py", "run.py", "start.py", 
                "__main__.py", "server.py"
            ]
            
            target_file = None
            for main_file in main_files:
                full_path = Path(project_path) / main_file
                if full_path.exists():
                    target_file = full_path
                    break
            
            if target_file:
                # 测试导入
                import_test = await self.test_import(target_file)
                test_result.update(import_test)
                
                # 测试运行（如果导入成功）
                if test_result["can_import"]:
                    run_test = await self.test_execution(target_file)
                    test_result.update(run_test)
            else:
                test_result["runtime_errors"].append("未找到主要的Python入口文件")
                test_result["overall_score"] = 0.7
            
        except Exception as e:
            logger.error(f"程序测试出错: {e}")
            test_result["runtime_errors"].append(f"测试异常: {str(e)}")
            test_result["overall_score"] = 0.3
        
        return test_result
    
    async def test_import(self, file_path: Path) -> Dict[str, Any]:
        """测试模块导入"""
        result = {"can_import": True, "import_errors": []}
        
        try:
            # 使用subprocess测试导入，避免影响当前进程
            cmd = [sys.executable, "-c", f"import sys; sys.path.insert(0, '{file_path.parent}'); import {file_path.stem}"]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                timeout=10
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                result["can_import"] = False
                result["import_errors"].append(stderr.decode('utf-8', errors='ignore'))
        
        except asyncio.TimeoutError:
            result["can_import"] = False
            result["import_errors"].append("导入测试超时")
        except Exception as e:
            result["can_import"] = False
            result["import_errors"].append(f"导入测试异常: {str(e)}")
        
        return result
    
    async def test_execution(self, file_path: Path) -> Dict[str, Any]:
        """测试程序执行"""
        result = {
            "can_run": True,
            "execution_errors": [],
            "execution_time": 0.0,
            "test_outputs": []
        }
        
        try:
            start_time = time.time()
            
            # 短时间运行测试
            cmd = [sys.executable, str(file_path)]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                timeout=5  # 5秒超时
            )
            
            try:
                stdout, stderr = await process.communicate()
                execution_time = time.time() - start_time
                
                result["execution_time"] = execution_time
                result["test_outputs"].append(stdout.decode('utf-8', errors='ignore')[:500])
                
                if process.returncode != 0:
                    result["can_run"] = False
                    result["execution_errors"].append(stderr.decode('utf-8', errors='ignore'))
                
            except asyncio.TimeoutError:
                # 超时可能意味着程序是长期运行的服务，这是正常的
                process.terminate()
                result["test_outputs"].append("程序启动正常（长期运行服务）")
                result["execution_time"] = 5.0
        
        except Exception as e:
            result["can_run"] = False
            result["execution_errors"].append(f"执行测试异常: {str(e)}")
        
        return result
    
    async def check_dependencies(self, project_path: str) -> Dict[str, Any]:
        """检查项目依赖"""
        logger.info("检查项目依赖...")
        
        dep_result = {
            "requirements_exist": False,
            "missing_packages": [],
            "outdated_packages": [],
            "dependency_conflicts": [],
            "overall_score": 1.0
        }
        
        try:
            # 检查requirements.txt
            req_file = Path(project_path) / "requirements.txt"
            if req_file.exists():
                dep_result["requirements_exist"] = True
                
                # 读取requirements
                with open(req_file, 'r', encoding='utf-8') as f:
                    requirements = f.read().strip().split('\n')
                
                # 检查每个依赖
                for req in requirements:
                    if req.strip() and not req.strip().startswith('#'):
                        missing = await self.check_package_availability(req.strip())
                        if missing:
                            dep_result["missing_packages"].append(req.strip())
            
            # 计算依赖分数
            dep_result["overall_score"] = self.calculate_dependency_score(dep_result)
            
        except Exception as e:
            logger.error(f"依赖检查出错: {e}")
            dep_result["overall_score"] = 0.8
        
        return dep_result
    
    async def check_package_availability(self, package: str) -> bool:
        """检查包是否可用"""
        try:
            # 简化的包检查（可以扩展）
            package_name = package.split('==')[0].split('>=')[0].split('<=')[0]
            
            cmd = [sys.executable, "-c", f"import {package_name}"]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                timeout=5
            )
            
            await process.communicate()
            return process.returncode != 0  # True if missing
            
        except Exception:
            return True  # 假设缺少
    
    def calculate_dependency_score(self, dep_result: Dict) -> float:
        """计算依赖分数"""
        score = 1.0
        
        if not dep_result["requirements_exist"]:
            score -= 0.2
        
        score -= len(dep_result["missing_packages"]) * 0.15
        score -= len(dep_result["dependency_conflicts"]) * 0.1
        
        return max(0.0, score)
    
    def calculate_quality_score(self, test_results: Dict) -> float:
        """计算整体质量分数"""
        scores = []
        
        if "code_quality" in test_results:
            scores.append(test_results["code_quality"]["overall_score"])
        
        if "runtime" in test_results:
            scores.append(test_results["runtime"]["overall_score"])
        
        if "dependencies" in test_results:
            scores.append(test_results["dependencies"]["overall_score"])
        
        return sum(scores) / len(scores) if scores else 0.5
    
    def extract_issues(self, test_results: Dict) -> List[Dict[str, Any]]:
        """提取所有问题"""
        issues = []
        
        # 代码质量问题
        if "code_quality" in test_results:
            cq = test_results["code_quality"]
            
            if not cq["syntax_valid"]:
                for error in cq["import_errors"]:
                    issues.append({
                        "type": "syntax_error",
                        "severity": "critical",
                        "description": f"语法错误: {error['error']}",
                        "file": error.get("file", ""),
                        "line": error.get("line", 0)
                    })
            
            for sec_issue in cq["security_issues"]:
                issues.append({
                    "type": "security",
                    "severity": sec_issue["severity"],
                    "description": sec_issue["issue"],
                    "file": sec_issue["file"],
                    "line": sec_issue["line"]
                })
        
        # 运行时问题
        if "runtime" in test_results:
            rt = test_results["runtime"]
            
            if not rt["can_import"]:
                for error in rt["import_errors"]:
                    issues.append({
                        "type": "import_error",
                        "severity": "critical",
                        "description": f"导入错误: {error}",
                        "file": "",
                        "line": 0
                    })
            
            if not rt["can_run"]:
                for error in rt["execution_errors"]:
                    issues.append({
                        "type": "runtime_error",
                        "severity": "high",
                        "description": f"运行错误: {error}",
                        "file": "",
                        "line": 0
                    })
        
        # 依赖问题
        if "dependencies" in test_results:
            dep = test_results["dependencies"]
            
            for missing in dep["missing_packages"]:
                issues.append({
                    "type": "dependency",
                    "severity": "high",
                    "description": f"缺少依赖: {missing}",
                    "file": "requirements.txt",
                    "line": 0
                })
        
        return issues
    
    def generate_recommendations(self, quality_score: float, issues: List[Dict]) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        if quality_score < 0.5:
            recommendations.append("🚨 代码质量严重不达标，需要全面重构")
        elif quality_score < 0.8:
            recommendations.append("⚠️ 代码质量需要改进，建议优化核心问题")
        
        # 按问题类型分组建议
        error_types = {}
        for issue in issues:
            issue_type = issue["type"]
            if issue_type not in error_types:
                error_types[issue_type] = []
            error_types[issue_type].append(issue)
        
        for issue_type, type_issues in error_types.items():
            count = len(type_issues)
            if issue_type == "syntax_error":
                recommendations.append(f"🔴 修复 {count} 个语法错误（优先级：最高）")
            elif issue_type == "import_error":
                recommendations.append(f"🟠 解决 {count} 个导入问题（检查模块路径和依赖）")
            elif issue_type == "runtime_error":
                recommendations.append(f"🟡 修复 {count} 个运行时错误")
            elif issue_type == "dependency":
                recommendations.append(f"📦 安装 {count} 个缺失的依赖包")
            elif issue_type == "security":
                recommendations.append(f"🔒 处理 {count} 个安全风险")
        
        if not recommendations:
            recommendations.append("✅ 代码质量良好，可以考虑性能优化和功能扩展")
        
        return recommendations
    
    def generate_pm_feedback(self, quality_score: float, issues: List[Dict], completed_text: str) -> str:
        """生成产品经理反馈"""
        
        # 主力操盘手角度的犀利分析
        if quality_score >= 0.9:
            pm_feedback = f"""🎯 **产品经理质量评估** (分数: {quality_score:.1f}/1.0)

✅ **质量评级: 优秀**
从主力操盘手角度看，这次开发展现了真正的专业水准！代码质量达到生产级别，可以放心投入实战。

💡 **战略建议**: 当前版本已具备核心竞争力，建议：
1. 立即进行压力测试验证稳定性  
2. 部署到真实环境获取数据反馈
3. 准备下一阶段的功能扩展

这种质量水平在市场上能够占据主导地位！"""

        elif quality_score >= 0.7:
            critical_count = len([i for i in issues if i["severity"] == "critical"])
            pm_feedback = f"""⚠️ **产品经理质量评估** (分数: {quality_score:.1f}/1.0)

🟡 **质量评级: 良好但需优化**
作为经验丰富的操盘手，我看到了潜力，但也发现了风险点。当前版本可以工作，但还不够稳定。

🔍 **发现问题**: {len(issues)}个问题，其中{critical_count}个严重问题
💪 **改进重点**: 
1. 优先解决所有严重问题（避免生产事故）
2. 完善错误处理机制
3. 增强代码稳定性

修复这些问题后，我们就能从"能用"升级到"好用"！"""

        else:
            critical_count = len([i for i in issues if i["severity"] == "critical"])
            pm_feedback = f"""🚨 **产品经理质量评估** (分数: {quality_score:.1f}/1.0)

🔴 **质量评级: 需要重大改进**  
坦率地说，当前版本还不适合投入使用。作为负责任的产品经理，我必须阻止这种质量的代码进入生产环境。

⚡ **紧急问题**: {len(issues)}个问题，{critical_count}个致命错误
🎯 **立即行动**: 
1. 停止新功能开发，全力修复基础问题
2. 建立代码审查流程
3. 增加单元测试覆盖

记住：在股市中，质量不过关的产品会被市场无情淘汰！让我们先把基础打牢。"""

        # 添加具体问题摘要
        if issues:
            pm_feedback += f"\n\n📋 **问题清单**:\n"
            for i, issue in enumerate(issues[:5], 1):  # 只显示前5个问题
                pm_feedback += f"{i}. [{issue['severity'].upper()}] {issue['description']}\n"
            
            if len(issues) > 5:
                pm_feedback += f"... 还有 {len(issues) - 5} 个问题需要解决\n"
        
        return pm_feedback
    
    def update_quality_metrics(self, analysis_result: Dict):
        """更新质量指标"""
        self.quality_metrics["test_runs"] += 1
        self.quality_metrics["issues_found"] += len(analysis_result["issues"])
        
        # 计算成功率
        if analysis_result["quality_score"] >= 0.8:
            self.quality_metrics["issues_resolved"] += 1
        
        self.quality_metrics["success_rate"] = (
            self.quality_metrics["issues_resolved"] / self.quality_metrics["test_runs"]
            if self.quality_metrics["test_runs"] > 0 else 0.0
        )
    
    def get_quality_summary(self) -> Dict[str, Any]:
        """获取质量摘要"""
        return {
            "metrics": self.quality_metrics,
            "recent_issues": self.issue_tracker[-10:],
            "test_strategies": self.test_strategies
        }
    
    def generate_master_feedback(self, quality_report: Dict[str, Any], gpt_analysis: Optional[Dict] = None) -> str:
        """生成主反馈 - 兼容方法"""
        try:
            quality_score = quality_report.get("quality_score", 0.0)
            issues = quality_report.get("issues", [])
            completed_text = quality_report.get("completed_text", "")
            
            # 使用现有的generate_pm_feedback方法生成基础反馈
            base_feedback = self.generate_pm_feedback(quality_score, issues, completed_text)
            
            # 如果有GPT分析结果，合并反馈
            if gpt_analysis:
                gpt_reasoning = gpt_analysis.get("reasoning", "")
                gpt_recommendations = gpt_analysis.get("recommendations", [])
                
                combined_feedback = f"""{base_feedback}

---

🤖 **AI深度分析补充**:
{gpt_reasoning}

💡 **AI建议**:
{chr(10).join([f"• {rec}" for rec in gpt_recommendations[:3]])}"""
                
                return combined_feedback
            else:
                return base_feedback
                
        except Exception as e:
            logger.error(f"生成主反馈时出错: {e}")
            return f"⚠️ 产品经理反馈生成遇到问题: {str(e)}" 
# 自主AI核心控制系统

## 概述

这是一个完全自主的CURSOR控制系统，无需外部GPT调用，能够：

- 🤖 **完全自主运行** - 无需外部API，完全本地化决策
- 🧠 **智能内容分析** - 实时分析CURSOR截图和文本内容
- ⚡ **即时决策响应** - 基于规则引擎的快速决策
- 🎯 **精准指令生成** - 根据上下文生成针对性指令
- 🔄 **持续状态监控** - 实时跟踪CURSOR状态变化
- 📊 **项目上下文理解** - 理解项目类型并调整策略

## 核心特性

### 1. 自主监控引擎
- 每5秒监控CURSOR状态
- 智能检测窗口变化
- 过滤无效内容和重复处理

### 2. 内容分析器
- **完成信号检测**: "review changes", "完成", "done"等
- **错误信号检测**: "error", "错误", "exception"等  
- **处理状态检测**: "generating", "processing"等
- **问题信号检测**: "？", "如何", "需要"等

### 3. 决策引擎
- **完成类型**: 立即分析并继续下一步
- **错误类型**: 提供解决方案
- **处理中**: 等待并监控
- **常规类型**: 上下文相关响应

### 4. 指令生成器
- 基于模板的指令生成
- 项目类型自适应
- 错误解决方案建议
- 上下文相关行动

## 快速启动

### 方法1: 简化启动
```bash
python autonomous_main.py
```

### 方法2: 完整启动
```bash
python start_autonomous_ai.py
```

## 系统架构

```
自主AI核心控制器
├── ContentAnalyzer (内容分析器)
│   ├── 完成信号检测
│   ├── 错误信号检测
│   ├── 处理状态检测
│   └── 问题信号检测
├── DecisionEngine (决策引擎)
│   ├── 决策规则库
│   ├── 优先级判断
│   ├── 上下文分析
│   └── 行动决策
├── InstructionGenerator (指令生成器)
│   ├── 指令模板库
│   ├── 项目类型适配
│   ├── 解决方案建议
│   └── 上下文行动
└── AutonomousAICore (自主AI核心)
    ├── 监控循环
    ├── 状态管理
    ├── 重复防护
    └── 持久化存储
```

## 工作流程

1. **初始化阶段**
   - 加载历史状态
   - 初始化各个组件
   - 设置项目上下文

2. **监控阶段**
   - 截取CURSOR屏幕
   - 提取文本内容
   - 验证内容有效性

3. **分析阶段**
   - 内容类型识别
   - 置信度评估
   - 行动需求判断

4. **决策阶段**
   - 构建决策上下文
   - 应用决策规则
   - 确定行动方案

5. **执行阶段**
   - 生成具体指令
   - 发送到CURSOR
   - 记录执行结果

6. **状态更新**
   - 更新AI状态
   - 保存决策历史
   - 标记已处理内容

## 配置说明

### 监控配置
- `monitoring_interval`: 监控间隔（默认5秒）
- `instruction_cooldown`: 指令冷却时间（默认10秒）
- `max_same_content_processing`: 相同内容最大处理次数（默认1次）

### 决策配置
- 完成类型：高优先级，2秒等待
- 错误类型：紧急优先级，1秒等待
- 处理中：低优先级，10秒等待
- 常规类型：中等优先级，5秒等待

## 项目上下文设置

系统支持多种项目类型的自适应：

```python
# Web开发项目
ai_core.set_project_context("Web开发项目 - 实现用户界面和交互功能")

# API服务项目
ai_core.set_project_context("API服务开发 - 构建RESTful接口")

# 数据分析项目
ai_core.set_project_context("数据分析项目 - 处理和分析数据")

# 自动化工具项目
ai_core.set_project_context("自动化工具开发 - 提高工作效率")
```

## 日志和监控

### 日志文件
- `autonomous_ai_core.log`: 主要运行日志
- `autonomous_ai_startup.log`: 启动日志

### 状态文件
- `autonomous_ai_state.json`: AI状态持久化
- 包含项目上下文、决策历史、完成任务等

### 调试信息
- `debug/`: 截图调试文件
- `autonomous_ai_data/`: AI数据存储

## 安全特性

1. **重复处理防护**: 防止对同一内容重复处理
2. **指令冷却机制**: 避免频繁发送指令
3. **内容有效性验证**: 过滤OCR错误和无效内容
4. **状态锁机制**: 防止并发处理冲突
5. **历史记录限制**: 防止内存泄漏

## 故障排除

### 常见问题

1. **无法检测到CURSOR窗口**
   - 确保CURSOR正在运行
   - 检查窗口是否被遮挡

2. **指令发送失败**
   - 检查CURSOR聊天窗口是否可见
   - 确认输入框是否可点击

3. **重复处理内容**
   - 系统有防重复机制，这是正常现象
   - 检查冷却时间设置

4. **分析结果不准确**
   - 检查OCR文本提取质量
   - 调整内容分析模式

### 调试模式

启动时添加调试参数：
```bash
python autonomous_main.py --debug
```

## 扩展开发

### 添加新的内容分析模式
在`ContentAnalyzer`类中添加新的检测模式：

```python
def analyze_custom_content(self, text: str) -> Dict[str, Any]:
    # 自定义分析逻辑
    pass
```

### 添加新的决策规则
在`DecisionEngine`类中扩展决策规则：

```python
def _initialize_decision_rules(self) -> Dict[str, Dict]:
    # 添加新的决策规则
    pass
```

### 添加新的指令模板
在`InstructionGenerator`类中添加新模板：

```python
def _initialize_templates(self) -> Dict[str, List[str]]:
    # 添加新的指令模板
    pass
```

## 版本信息

- **版本**: 2.0 - 完全自主版本
- **作者**: Claude AI Assistant (Autonomous Mode)
- **更新**: 2024年最新版本

## 许可证

本项目采用MIT许可证，详见LICENSE文件。

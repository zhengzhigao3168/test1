# CURSOR Supervisor Core

这是CURSOR IDE的监督系统核心代码。该系统能够智能监控CURSOR的运行状态，检测异常情况，并提供相应的操作建议。

## 主要功能

- 屏幕监控和内容分析
- 智能异常检测
- 自动化控制
- GPT模型集成
- 产品经理模式
- 用户反馈管理
- 项目规划管理

## 目录结构

```
cursor_supervisor_core/
├── modules/
│   ├── screen_monitor.py
│   ├── intelligent_monitor.py
│   ├── automation_controller.py
│   ├── gpt_controller.py
│   ├── product_manager.py
│   ├── user_feedback.py
│   └── project_planner.py
├── main.py
├── config.py
├── requirements.txt
└── README.md
```

## 安装

1. 克隆仓库
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

## 使用

1. 配置config.py中的相关参数
2. 运行主程序：
   ```bash
   python main.py
   ```

## 依赖要求

- Python 3.8+
- 详细依赖请查看requirements.txt

## 注意事项

- 确保CURSOR IDE已经启动
- Windows系统需要安装pywin32
- 首次运行时会要求选择CURSOR窗口和监控区域 
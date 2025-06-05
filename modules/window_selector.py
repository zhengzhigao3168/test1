#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
窗口区域选择模块
功能：让用户选择要监控的CURSOR聊天窗口区域，解决多窗口问题
"""

import tkinter as tk
from tkinter import messagebox, ttk
import pyautogui
import json
import os
import time
from PIL import Image, ImageTk
import logging

logger = logging.getLogger(__name__)

class WindowSelector:
    """窗口区域选择器"""
    
    def __init__(self):
        self.selected_region = None
        self.screenshot = None
        self.config_file = "window_regions.json"
        self.root = None
        self.canvas = None
        self.selections = []
        self.selection_complete = False
        self._ocr_reader = None  # 添加OCR引用
        
    def load_saved_regions(self):
        """加载已保存的区域配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"加载区域配置时出错: {e}")
            return {}
    
    def save_region(self, name: str, region: tuple):
        """保存选中的区域"""
        try:
            regions = self.load_saved_regions()
            regions[name] = {
                "x": region[0],
                "y": region[1], 
                "width": region[2],
                "height": region[3],
                "timestamp": time.time()
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(regions, f, indent=2, ensure_ascii=False)
                
            logger.info(f"已保存区域配置: {name}")
            return True
            
        except Exception as e:
            logger.error(f"保存区域配置时出错: {e}")
            return False
    
    def select_chat_region(self) -> list:
        """选择聊天区域的主函数 - 支持多区域选择"""
        try:
            logger.info("🎯 开始选择CURSOR聊天窗口区域...")
            
            # 检查是否有已保存的区域
            saved_regions = self.load_saved_regions()
            if saved_regions:
                choice = self.ask_use_saved_region(saved_regions)
                if choice:
                    return choice
            
            # 截取当前屏幕
            self.screenshot = pyautogui.screenshot()
            
            # 创建选择界面
            selected_regions = self.create_selection_interface()
            
            if selected_regions:
                # 询问是否保存
                self.ask_save_regions(selected_regions)
                return selected_regions
            else:
                logger.warning("用户取消了区域选择")
                return None
                
        except Exception as e:
            logger.error(f"选择聊天区域时出错: {e}")
            return None
    
    def select_chat_region_for_window(self, window_info: dict) -> dict:
        """为特定窗口选择聊天区域 - 使用窗口相对坐标"""
        try:
            logger.info(f"🎯 为窗口 '{window_info['title']}' 选择聊天区域...")
            
            # 获取窗口截图
            window_x, window_y = window_info['x'], window_info['y']
            window_width, window_height = window_info['width'], window_info['height']
            
            # 截取窗口区域
            self.screenshot = pyautogui.screenshot(region=(window_x, window_y, window_width, window_height))
            self.window_info = window_info  # 保存窗口信息
            
            logger.info(f"📸 获取到窗口截图: {self.screenshot.size}")
            
            # 创建选择界面
            selection_result = self.create_selection_interface_for_window()
            
            if selection_result and (selection_result['regions'] or selection_result['input_box']):
                # 转换为绝对坐标（相对于全屏）
                result = {
                    'regions': [],
                    'input_box': None
                }
                
                # 处理监控区域
                if selection_result['regions']:
                    absolute_regions = []
                    for region in selection_result['regions']:
                        rel_x, rel_y, width, height = region
                        abs_x = rel_x + window_x
                        abs_y = rel_y + window_y
                        absolute_regions.append((abs_x, abs_y, width, height))
                    result['regions'] = absolute_regions
                    
                    logger.info(f"✅ 选择了 {len(absolute_regions)} 个监控区域（转换为绝对坐标）")
                    for i, region in enumerate(absolute_regions, 1):
                        x, y, w, h = region
                        logger.info(f"   区域{i}: ({x}, {y}) 大小: {w}x{h}")
                
                # 处理输入框
                if selection_result['input_box']:
                    rel_x, rel_y, width, height = selection_result['input_box']
                    abs_x = rel_x + window_x
                    abs_y = rel_y + window_y
                    result['input_box'] = (abs_x, abs_y, width, height)
                    
                    logger.info(f"✅ 选择了输入框（转换为绝对坐标）: ({abs_x}, {abs_y}) 大小: {width}x{height}")
                
                # 询问是否保存
                if result['regions']:
                    self.ask_save_regions_with_window_info(result['regions'], window_info)
                
                return result
            else:
                logger.warning("用户取消了区域选择")
                return {'regions': [], 'input_box': None}
                
        except Exception as e:
            logger.error(f"为窗口选择聊天区域时出错: {e}")
            return None
    
    def ask_use_saved_region(self, saved_regions: dict):
        """询问是否使用已保存的区域 - 支持多区域格式"""
        try:
            root = tk.Tk()
            root.title("CURSOR监督系统 - 区域选择")
            root.geometry("500x350")
            root.resizable(False, False)
            
            # 居中显示
            self.center_window(root, 500, 350)
            
            selected_regions = None
            
            def use_saved():
                nonlocal selected_regions
                try:
                    selection = region_listbox.curselection()
                    if not selection:
                        messagebox.showwarning("警告", "请先选择一个配置")
                        return
                        
                    config_name = list(saved_regions.keys())[selection[0]]
                    region_data = saved_regions[config_name]
                    
                    logger.info(f"尝试加载配置: {config_name}, 数据: {region_data}")
                    
                    # 检查是否是新格式（多区域）
                    if "regions" in region_data:
                        # 新格式：多区域
                        selected_regions = []
                        for region_info in region_data["regions"]:
                            selected_regions.append((
                                region_info["x"],
                                region_info["y"],
                                region_info["width"],
                                region_info["height"]
                            ))
                    elif "region" in region_data:
                        # 中等格式：有嵌套region对象的单区域
                        region_info = region_data["region"]
                        selected_regions = [(
                            region_info["x"],
                            region_info["y"],
                            region_info["width"], 
                            region_info["height"]
                        )]
                    elif "x" in region_data:
                        # 旧格式：直接字段的单区域
                        selected_regions = [(
                            region_data["x"],
                            region_data["y"],
                            region_data["width"], 
                            region_data["height"]
                        )]
                    else:
                        logger.error(f"未知的区域配置格式: {region_data}")
                        messagebox.showerror("错误", f"无法识别的区域配置格式: {config_name}")
                        return
                    
                    logger.info(f"成功加载区域配置: {config_name} ({len(selected_regions)}个区域)")
                    root.quit()
                    
                except Exception as e:
                    logger.error(f"加载区域配置时出错: {e}")
                    messagebox.showerror("错误", f"加载配置失败: {str(e)}")
                    return
            
            def select_new():
                nonlocal selected_regions
                selected_regions = "new"
                root.quit()
            
            # 标题
            title_label = tk.Label(root, text="发现已保存的聊天区域配置", font=("Arial", 12, "bold"))
            title_label.pack(pady=10)
            
            # 说明
            info_label = tk.Label(root, text="您可以使用已保存的区域配置，或重新选择新区域", 
                                font=("Arial", 9), fg="gray")
            info_label.pack(pady=5)
            
            # 区域列表
            list_frame = tk.Frame(root)
            list_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
            
            tk.Label(list_frame, text="已保存的区域配置:").pack(anchor=tk.W)
            
            # 创建列表框和滚动条
            listbox_frame = tk.Frame(list_frame)
            listbox_frame.pack(fill=tk.BOTH, expand=True, pady=5)
            
            region_listbox = tk.Listbox(listbox_frame, height=10)
            scrollbar = tk.Scrollbar(listbox_frame, orient=tk.VERTICAL)
            
            region_listbox.config(yscrollcommand=scrollbar.set)
            scrollbar.config(command=region_listbox.yview)
            
            region_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # 添加区域配置到列表
            for name, data in saved_regions.items():
                timestamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(data.get("timestamp", 0)))
                
                # 检查是否是新格式
                if "regions" in data:
                    region_count = data.get("region_count", len(data["regions"]))
                    region_listbox.insert(tk.END, f"{name} ({region_count}个区域, {timestamp})")
                else:
                    # 旧格式，单区域
                    region_listbox.insert(tk.END, f"{name} (1个区域, {timestamp})")
            
            # 默认选中第一个
            if region_listbox.size() > 0:
                region_listbox.selection_set(0)
            
            # 按钮
            button_frame = tk.Frame(root)
            button_frame.pack(pady=10)
            
            use_button = tk.Button(button_frame, text="使用选中配置", command=use_saved,
                                 bg="#4CAF50", fg="white", font=("Arial", 9, "bold"))
            use_button.pack(side=tk.LEFT, padx=5)
            
            new_button = tk.Button(button_frame, text="重新选择", command=select_new,
                                 bg="#2196F3", fg="white", font=("Arial", 9))
            new_button.pack(side=tk.LEFT, padx=5)
            
            root.mainloop()
            root.destroy()
            
            if selected_regions == "new":
                return None  # 继续新选择流程
            else:
                return selected_regions
                
        except Exception as e:
            logger.error(f"询问使用已保存区域时出错: {e}")
            return None
    
    def create_selection_interface(self) -> list:
        """创建区域选择界面 - 支持选择两个区域"""
        try:
            root = tk.Tk()
            root.title("CURSOR监督系统 - 选择聊天区域")
            
            # 获取屏幕尺寸
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            
            # 设置窗口大小为屏幕的90%，并居中显示
            window_width = int(screen_width * 0.9)
            window_height = int(screen_height * 0.9)
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            
            root.geometry(f"{window_width}x{window_height}+{x}+{y}")
            root.configure(bg='black')
            
            self.root = root
            selected_regions = []  # 存储多个选择的区域
            current_selection = 1  # 当前选择第几个区域
            
            # 计算画布大小，为控制面板留出空间
            canvas_height = window_height - 150  # 为控制面板预留150像素
            
            # 调整截图大小以适应画布
            img_width, img_height = self.screenshot.size
            scale = min(window_width / img_width, canvas_height / img_height) * 0.95
            
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
            
            resized_screenshot = self.screenshot.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # 转换为PhotoImage
            photo = ImageTk.PhotoImage(resized_screenshot)
            
            # 创建主容器
            main_frame = tk.Frame(root, bg='black')
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # 创建Canvas容器
            canvas_frame = tk.Frame(main_frame, bg='black')
            canvas_frame.pack(fill=tk.BOTH, expand=True)
            
            # 创建Canvas
            canvas = tk.Canvas(canvas_frame, width=new_width, height=new_height, bg='black', highlightthickness=0)
            canvas.pack()
            
            # 显示截图
            canvas.create_image(new_width//2, new_height//2, image=photo)
            
            # 选择框变量
            start_x = start_y = 0
            rect_id = None
            selection_coords = None
            confirmed_rects = []  # 存储已确认的矩形
            
            def clear_current_selection():
                """清除当前选择的临时矩形"""
                nonlocal rect_id
                if rect_id:
                    canvas.delete(rect_id)
                    rect_id = None
            
            def on_mouse_down(event):
                nonlocal start_x, start_y
                start_x, start_y = event.x, event.y
                clear_current_selection()
            
            def on_mouse_drag(event):
                nonlocal rect_id
                clear_current_selection()
                rect_id = canvas.create_rectangle(
                    start_x, start_y, event.x, event.y,
                    outline='red', width=3, fill='', stipple='gray50'
                )
            
            def on_mouse_up(event):
                nonlocal selection_coords
                if abs(event.x - start_x) > 20 and abs(event.y - start_y) > 20:
                    # 转换回原始坐标
                    orig_x1 = int(min(start_x, event.x) / scale)
                    orig_y1 = int(min(start_y, event.y) / scale)
                    orig_x2 = int(max(start_x, event.x) / scale)
                    orig_y2 = int(max(start_y, event.y) / scale)
                    
                    selection_coords = (orig_x1, orig_y1, orig_x2 - orig_x1, orig_y2 - orig_y1)
                    
                    # 显示确认信息
                    canvas.create_text(
                        event.x, event.y - 20,
                        text=f"区域{current_selection}: {orig_x2-orig_x1}x{orig_y2-orig_y1}",
                        fill='yellow', font=('Arial', 12, 'bold')
                    )
                    
                    confirm_button.config(state=tk.NORMAL)
            
            def confirm_selection():
                nonlocal selection_coords, current_selection, rect_id
                if selection_coords:
                    # 保存当前选择
                    selected_regions.append(selection_coords)
                    
                    # 将当前选择矩形变为永久显示（绿色）
                    if rect_id:
                        canvas.delete(rect_id)
                    
                    # 绘制确认后的区域（绿色）
                    display_x1 = int(selection_coords[0] * scale)
                    display_y1 = int(selection_coords[1] * scale)
                    display_x2 = int((selection_coords[0] + selection_coords[2]) * scale)
                    display_y2 = int((selection_coords[1] + selection_coords[3]) * scale)
                    
                    confirmed_rect = canvas.create_rectangle(
                        display_x1, display_y1, display_x2, display_y2,
                        outline='green', width=2, fill='', stipple='gray25'
                    )
                    confirmed_rects.append(confirmed_rect)
                    
                    # 添加区域标签
                    canvas.create_text(
                        display_x1 + 10, display_y1 + 10,
                        text=f"区域{current_selection}",
                        fill='lime', font=('Arial', 10, 'bold'), anchor='nw'
                    )
                    
                    rect_id = None
                    selection_coords = None
                    
                    if current_selection == 1:
                        # 第一个区域已选择，准备选择第二个
                        current_selection = 2
                        instruction.config(text="请选择第2个聊天区域（如侧边栏或其他对话窗口）")
                        confirm_button.config(text="确认第2个区域", state=tk.DISABLED)
                        
                        # 添加跳过按钮
                        skip_button.config(state=tk.NORMAL)
                        
                    elif current_selection == 2:
                        # 第二个区域已选择，完成选择
                        root.quit()
                    
                    confirm_button.config(state=tk.DISABLED)
            
            def skip_second_region():
                """跳过第二个区域的选择"""
                nonlocal current_selection
                if current_selection == 2:
                    logger.info("用户选择跳过第二个区域")
                    root.quit()
            
            def cancel_selection():
                nonlocal selected_regions
                selected_regions = []
                root.quit()
            
            # 绑定鼠标事件
            canvas.bind("<Button-1>", on_mouse_down)
            canvas.bind("<B1-Motion>", on_mouse_drag)
            canvas.bind("<ButtonRelease-1>", on_mouse_up)
            
            # 控制面板
            control_frame = tk.Frame(main_frame, bg='black')
            control_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
            
            # 说明文字
            instruction = tk.Label(control_frame, 
                                 text="请选择第1个聊天区域（主要的AI对话显示区域）",
                                 fg='white', bg='black', font=('Arial', 12, 'bold'))
            instruction.pack(pady=5)
            
            # 提示文字
            tip_label = tk.Label(control_frame,
                               text="提示：您可以选择1-2个区域。第1个是主聊天窗口，第2个可以是侧边栏等其他对话窗口",
                               fg='lightgray', bg='black', font=('Arial', 9))
            tip_label.pack(pady=2)
            
            # 按钮
            button_frame = tk.Frame(control_frame, bg='black')
            button_frame.pack(pady=10)
            
            confirm_button = tk.Button(button_frame, text="确认第1个区域", command=confirm_selection,
                                     bg='#4CAF50', fg='white', font=('Arial', 11, 'bold'),
                                     state=tk.DISABLED, padx=15, pady=8)
            confirm_button.pack(side=tk.LEFT, padx=8)
            
            skip_button = tk.Button(button_frame, text="只要1个区域", command=skip_second_region,
                                  bg='#FF9800', fg='white', font=('Arial', 11),
                                  state=tk.DISABLED, padx=15, pady=8)
            skip_button.pack(side=tk.LEFT, padx=8)
            
            cancel_button = tk.Button(button_frame, text="取消", command=cancel_selection,
                                    bg='#f44336', fg='white', font=('Arial', 11),
                                    padx=15, pady=8)
            cancel_button.pack(side=tk.LEFT, padx=8)
            
            # 保持photo引用避免被垃圾回收
            root.photo = photo
            
            root.mainloop()
            root.destroy()
            
            return selected_regions if selected_regions else None
            
        except Exception as e:
            logger.error(f"创建选择界面时出错: {e}")
            return None
    
    def ask_save_regions(self, regions: list):
        """询问是否保存选中的多个区域"""
        try:
            region_count = len(regions)
            region_info = ""
            for i, region in enumerate(regions, 1):
                region_info += f"区域{i}: {region[2]}x{region[3]} 位置({region[0]}, {region[1]})\n"
            
            result = messagebox.askyesno(
                "保存区域配置", 
                f"是否保存这{region_count}个区域的配置，以便下次使用？\n\n{region_info}"
            )
            
            if result:
                # 获取区域配置名称
                name = self.get_regions_name(region_count)
                if name:
                    self.save_regions(name, regions)
                    
        except Exception as e:
            logger.error(f"询问保存区域时出错: {e}")
    
    def save_regions(self, name: str, regions: list):
        """保存多个选中的区域"""
        try:
            configs = self.load_saved_regions()
            configs[name] = {
                "regions": [
                    {
                        "x": region[0],
                        "y": region[1], 
                        "width": region[2],
                        "height": region[3]
                    } for region in regions
                ],
                "region_count": len(regions),
                "timestamp": time.time()
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(configs, f, indent=2, ensure_ascii=False)
                
            logger.info(f"已保存{len(regions)}个区域的配置: {name}")
            return True
            
        except Exception as e:
            logger.error(f"保存区域配置时出错: {e}")
            return False
    
    def get_regions_name(self, region_count: int) -> str:
        """获取多区域配置的名称"""
        try:
            root = tk.Tk()
            root.title("保存区域配置")
            root.geometry("350x180")
            root.resizable(False, False)
            
            self.center_window(root, 350, 180)
            
            region_name = None
            
            def save_name():
                nonlocal region_name
                name = name_entry.get().strip()
                if name:
                    region_name = name
                    root.quit()
                else:
                    messagebox.showwarning("警告", "请输入配置名称")
            
            def cancel():
                root.quit()
            
            # 标题
            tk.Label(root, text=f"为这{region_count}个区域的配置命名:", font=("Arial", 11, "bold")).pack(pady=10)
            
            # 输入框
            name_entry = tk.Entry(root, font=("Arial", 10), width=30)
            name_entry.pack(pady=5)
            default_name = f"CURSOR多区域配置_{region_count}个区域_{int(time.time())}"
            name_entry.insert(0, default_name)
            name_entry.select_range(0, tk.END)
            name_entry.focus()
            
            # 提示
            tip_label = tk.Label(root, text=f"将保存{region_count}个聊天窗口区域", 
                               font=("Arial", 9), fg="gray")
            tip_label.pack(pady=5)
            
            # 按钮
            button_frame = tk.Frame(root)
            button_frame.pack(pady=15)
            
            save_button = tk.Button(button_frame, text="保存", command=save_name,
                                  bg="#4CAF50", fg="white", font=("Arial", 9, "bold"))
            save_button.pack(side=tk.LEFT, padx=5)
            
            cancel_button = tk.Button(button_frame, text="取消", command=cancel,
                                    bg="#f44336", fg="white", font=("Arial", 9))
            cancel_button.pack(side=tk.LEFT, padx=5)
            
            # 回车键保存
            name_entry.bind('<Return>', lambda e: save_name())
            
            root.mainloop()
            root.destroy()
            
            return region_name
            
        except Exception as e:
            logger.error(f"获取区域配置名称时出错: {e}")
            return None
    
    def center_window(self, window, width, height):
        """居中显示窗口"""
        try:
            screen_width = window.winfo_screenwidth()
            screen_height = window.winfo_screenheight()
            
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            
            window.geometry(f"{width}x{height}+{x}+{y}")
            
        except Exception as e:
            logger.debug(f"居中窗口时出错: {e}")
    
    def extract_region_text(self, window_screenshot, region_abs_coords: tuple, window_screen_x: int, window_screen_y: int, ocr_reader=None) -> str:
        """从指定区域提取文字 - 使用相对于窗口的坐标进行裁剪"""
        try:
            abs_crop_x, abs_crop_y, crop_width, crop_height = region_abs_coords
            
            # 计算相对于window_screenshot的裁剪坐标
            rel_crop_x = abs_crop_x - window_screen_x
            rel_crop_y = abs_crop_y - window_screen_y
            
            logger.debug(f"原始绝对区域坐标: {region_abs_coords}")
            logger.debug(f"窗口左上角屏幕坐标: ({window_screen_x}, {window_screen_y})")
            logger.debug(f"计算出的相对裁剪坐标: ({rel_crop_x}, {rel_crop_y}), 大小: {crop_width}x{crop_height}")
            
            # 裁剪图像到指定区域 (使用相对坐标)
            # crop expects (left, upper, right, lower)
            cropped_image = window_screenshot.crop((rel_crop_x, rel_crop_y, rel_crop_x + crop_width, rel_crop_y + crop_height))
            
            # 验证裁剪图像是否有效
            if cropped_image.size[0] <= 0 or cropped_image.size[1] <= 0:
                logger.error(f"❌ 裁剪图像尺寸无效: {cropped_image.size}. 原始截图: {window_screenshot.size}, 相对坐标: ({rel_crop_x},{rel_crop_y}), 裁剪大小: ({crop_width},{crop_height})")
                # 返回特殊标记，因为截图可能依然是黑的，但不是因为OCR本身
                # 尝试保存原始窗口截图和标记，指示裁剪问题
                error_timestamp = int(time.time())
                window_screenshot_path = f"debug/error_crop_window_orig_{error_timestamp}.png"
                window_screenshot.save(window_screenshot_path)
                return f"OCR_FAILED:CROP_ERROR:window_img={window_screenshot_path},abs_region={abs_crop_x}_{abs_crop_y}_{crop_width}_{crop_height},win_origin={window_screen_x}_{window_screen_y}"

            # 保存区域截图供调试和GPT-4O使用
            region_screenshot_path = f"region_screenshot_{int(time.time())}.png"
            cropped_image.save(region_screenshot_path)
            logger.debug(f"📸 已保存区域截图: {region_screenshot_path} (来自相对裁剪)")
            
            # 首选：使用EasyOCR
            if hasattr(self, '_ocr_reader') and self._ocr_reader:
                try:
                    import numpy as np
                    img_array = np.array(cropped_image)
                    results = self._ocr_reader.readtext(img_array)
                    logger.debug(f"🔍 EasyOCR原始结果数量: {len(results) if results else 0}")
                    
                    if results:
                        all_texts = []
                        for bbox, text, confidence in results:
                            logger.debug(f"  OCR结果: '{text}' 置信度: {confidence:.2f}")
                            if text and len(text.strip()) > 0:
                                all_texts.append(text.strip())
                        
                        if all_texts:
                            combined_text = ' '.join(all_texts)
                            # 清理OCR乱码和噪声
                            cleaned_text = self._clean_ocr_text(combined_text)
                            if cleaned_text:
                                logger.info(f"✅ EasyOCR成功提取文本: {cleaned_text[:100]}...")
                                return cleaned_text
                        else:
                                logger.warning("⚠️ EasyOCR文本清理后为空")
                    else:
                        logger.warning("⚠️ EasyOCR没有返回任何结果")
                        
                except Exception as e:
                    logger.warning(f"⚠️ EasyOCR提取失败: {e}")
            
            # 备选1：使用传入的OCR reader
            if ocr_reader:
                try:
                    if hasattr(ocr_reader, 'readtext'): # EasyOCR like
                        import numpy as np
                        img_array = np.array(cropped_image)
                        results = ocr_reader.readtext(img_array)
                        if results:
                            all_texts = [result[1].strip() for result in results if result[1] and result[1].strip()]
                            if all_texts:
                                combined_text = ' '.join(all_texts)
                                # 清理OCR乱码和噪声
                                cleaned_text = self._clean_ocr_text(combined_text)
                                if cleaned_text:
                                    logger.info(f"✅ 传入OCR成功提取文本: {cleaned_text[:100]}...")
                                    return cleaned_text
                                else:
                                    logger.warning("⚠️ 传入OCR文本清理后为空")
                    else: # Tesseract like
                        import pytesseract
                        text = pytesseract.image_to_string(cropped_image, lang='chi_sim+eng')
                        if text.strip():
                            logger.info(f"✅ Tesseract成功提取文本: {text[:50]}...")
                            return text.strip()
                except Exception as e:
                    logger.warning(f"⚠️ 传入OCR提取失败: {e}")
            
            # 备选2：尝试使用全局OCR（从screen_monitor模块）
            try:
                from modules.screen_monitor import ScreenMonitor
                if hasattr(ScreenMonitor, '_global_ocr_reader') and ScreenMonitor._global_ocr_reader:
                    import numpy as np
                    img_array = np.array(cropped_image)
                    results = ScreenMonitor._global_ocr_reader.readtext(img_array)
                    if results:
                        all_texts = [result[1].strip() for result in results if result[1] and result[1].strip()]
                        if all_texts:
                            combined_text = ' '.join(all_texts)
                            # 清理OCR乱码和噪声
                            cleaned_text = self._clean_ocr_text(combined_text)
                            if cleaned_text:
                                logger.info(f"✅ 全局OCR成功提取文本: {cleaned_text[:100]}...")
                                return cleaned_text
                            else:
                                logger.warning("⚠️ 全局OCR文本清理后为空")
            except Exception as e:
                logger.warning(f"⚠️ 全局OCR提取失败: {e}")
            
            logger.warning("⚠️ 所有OCR方法都失败，将图片直接发送给GPT-4O")
            return f"OCR_FAILED:IMAGE_PATH:{region_screenshot_path}"
            
        except Exception as e:
            logger.error(f"提取区域文字时出错: {e}")
            # 如果裁剪或OCR过程中发生意外错误，也尝试返回带图片路径的标记
            # 但要确保 region_screenshot_path 已定义或有一个备用路径
            # For simplicity, return empty if error before screenshot saving
            # If screenshot was saved, use its path
            path_to_report = ""
            if 'region_screenshot_path' in locals() and region_screenshot_path:
                path_to_report = region_screenshot_path
            elif 'window_screenshot' in locals() and window_screenshot:
                 try:
                    fallback_path = f"debug/error_extract_text_fallback_{int(time.time())}.png"
                    window_screenshot.save(fallback_path)
                    path_to_report = fallback_path
                 except:
                    pass # best effort
            if path_to_report:
                return f"OCR_FAILED:EXCEPTION:{path_to_report}:{e}"
            return f"OCR_FAILED:EXCEPTION:UNKNOWN_PATH:{e}"
    
    def analyze_region_features(self, image) -> str:
        """分析区域特征（已弃用：会被is_valid_content过滤，仅用于调试）"""
        try:
            import numpy as np
            import cv2
            
            img_array = np.array(image)
            
            # 分析图像特征
            features = []
            
            # 检测亮度变化（可能是新文本）
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            brightness = np.mean(gray)
            
            if brightness > 200:
                features.append("high_brightness_content")
            elif brightness < 50:
                features.append("dark_content")
            
            # 检测边缘（文字轮廓）
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size
            
            if edge_density > 0.1:
                features.append("text_like_patterns")
            
            # 检测颜色变化（可能是状态指示）
            hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
            
            # 检测绿色（完成）
            green_mask = cv2.inRange(hsv, np.array([50, 100, 100]), np.array([70, 255, 255]))
            green_ratio = np.sum(green_mask > 0) / green_mask.size
            if green_ratio > 0.01:
                features.append("completion_indicator")
            
            # 检测红色（错误）
            red_mask = cv2.inRange(hsv, np.array([0, 100, 100]), np.array([10, 255, 255]))
            red_ratio = np.sum(red_mask > 0) / red_mask.size
            if red_ratio > 0.01:
                features.append("error_indicator")
            
            # 注意：这个方法的返回值会被is_valid_content()过滤
            # 建议在调试时使用，实际运行时应该返回空字符串
            logger.debug(f"🔍 区域特征分析: {features}")
            return ""  # 修改：返回空字符串而不是特征描述
                
        except Exception as e:
            logger.debug(f"分析区域特征时出错: {e}")
            return ""
    
    def set_ocr_reader(self, ocr_reader):
        """设置OCR读取器"""
        self._ocr_reader = ocr_reader
        logger.debug("✅ WindowSelector OCR引用已设置")
    
    def create_selection_interface_for_window(self) -> dict:
        """为特定窗口创建区域选择界面 - 包括监控区域和输入框"""
        try:
            self.root = tk.Tk()
            self.root.title(f"选择 {self.window_info['title']} 的监控区域和输入框")
            
            # 设置全屏窗口
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            self.root.geometry(f"{screen_width}x{screen_height}+0+0")
            self.root.attributes('-topmost', True)
            
            # 将窗口截图调整为适合屏幕的大小
            display_screenshot = self.screenshot.copy()
            
            # 如果窗口截图比屏幕大，则缩放
            if self.screenshot.width > screen_width * 0.9 or self.screenshot.height > screen_height * 0.9:
                scale_factor = min(screen_width * 0.9 / self.screenshot.width, 
                                 screen_height * 0.9 / self.screenshot.height)
                new_width = int(self.screenshot.width * scale_factor)
                new_height = int(self.screenshot.height * scale_factor)
                display_screenshot = self.screenshot.resize((new_width, new_height), Image.Resampling.LANCZOS)
                self.scale_factor = scale_factor
            else:
                self.scale_factor = 1.0
            
            # 创建画布
            self.canvas = tk.Canvas(self.root, 
                                  width=display_screenshot.width, 
                                  height=display_screenshot.height,
                                  highlightthickness=0)
            self.canvas.pack(expand=True)
            
            # 显示截图
            self.tk_image = ImageTk.PhotoImage(display_screenshot)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
            
            # 初始化选择状态
            self.selections = []
            self.input_box_position = None
            self.current_selection = None
            self.selection_complete = False
            self.selection_mode = "regions"  # "regions" 或 "input_box"
            
            # 更新说明文字
            self.update_instruction_text()
            
            # 绑定鼠标事件
            self.canvas.bind("<Button-1>", self.on_window_mouse_down)
            self.canvas.bind("<B1-Motion>", self.on_window_mouse_drag)
            self.canvas.bind("<ButtonRelease-1>", self.on_window_mouse_up)
            
            # 创建增强的控制按钮
            self.create_window_control_buttons_enhanced()
            
            # 运行选择界面
            self.root.mainloop()
            
            result = {
                'regions': [],
                'input_box': None
            }
            
            if self.selection_complete:
                # 转换监控区域坐标（考虑缩放）
                if self.selections:
                    actual_selections = []
                    for sel in self.selections:
                        x = int(sel[0] / self.scale_factor)
                        y = int(sel[1] / self.scale_factor)
                        w = int(sel[2] / self.scale_factor)
                        h = int(sel[3] / self.scale_factor)
                        actual_selections.append((x, y, w, h))
                    result['regions'] = actual_selections
                
                # 转换输入框坐标（考虑缩放）
                if self.input_box_position:
                    x = int(self.input_box_position[0] / self.scale_factor)
                    y = int(self.input_box_position[1] / self.scale_factor)
                    w = int(self.input_box_position[2] / self.scale_factor)
                    h = int(self.input_box_position[3] / self.scale_factor)
                    result['input_box'] = (x, y, w, h)
                
                logger.info(f"✅ 选择结果: {len(result['regions'])}个监控区域, 输入框: {'已选择' if result['input_box'] else '未选择'}")
                return result
            else:
                logger.info("❌ 用户取消了选择")
                return result
                
        except Exception as e:
            logger.error(f"创建窗口选择界面时出错: {e}")
            return {'regions': [], 'input_box': None}
        finally:
            if self.root:
                try:
                    self.root.destroy()
                except:
                    pass
    
    def on_window_mouse_down(self, event):
        """窗口模式下的鼠标按下事件"""
        self.start_x = event.x
        self.start_y = event.y
        self.current_selection = None
    
    def on_window_mouse_drag(self, event):
        """窗口模式下的鼠标拖拽事件"""
        if hasattr(self, 'current_selection') and self.current_selection:
            self.canvas.delete(self.current_selection)
        
        x1, y1 = self.start_x, self.start_y
        x2, y2 = event.x, event.y
        
        # 确保矩形正确绘制
        left = min(x1, x2)
        top = min(y1, y2)
        right = max(x1, x2)
        bottom = max(y1, y2)
        
        self.current_selection = self.canvas.create_rectangle(
            left, top, right, bottom,
            outline='red', width=2, fill='', stipple='gray50'
        )
    
    def on_window_mouse_up(self, event):
        """窗口模式下的鼠标释放事件"""
        if hasattr(self, 'start_x') and hasattr(self, 'start_y'):
            x1, y1 = self.start_x, self.start_y
            x2, y2 = event.x, event.y
            
            # 计算选择区域
            left = min(x1, x2)
            top = min(y1, y2)
            width = abs(x2 - x1)
            height = abs(y2 - y1)
            
            # 只有当区域足够大时才添加
            if width > 20 and height > 20:
                if self.selection_mode == "regions":
                    self.selections.append((left, top, width, height))
                    logger.info(f"✅ 添加了第 {len(self.selections)} 个监控区域: ({left}, {top}) 大小: {width}x{height}")
                elif self.selection_mode == "input_box":
                    self.input_box_position = (left, top, width, height)
                    logger.info(f"✅ 设置输入框位置: ({left}, {top}) 大小: {width}x{height}")
                
                # 重新绘制所有选择，使用不同颜色
                self.redraw_window_selections()
    
    def update_instruction_text(self):
        """更新说明文字"""
        # 清除旧的说明文字
        for item in self.canvas.find_all():
            tags = self.canvas.gettags(item)
            if 'instruction' in tags:
                self.canvas.delete(item)
        
        if self.selection_mode == "regions":
            self.canvas.create_text(self.tk_image.width() // 2, 30, 
                                  text=f"步骤1: 选择监控区域 - 在 {self.window_info['title']} 中选择要监控的区域（对话内容、运行状态等）", 
                                  font=("Arial", 14, "bold"), fill="red", tags='instruction')
            self.canvas.create_text(self.tk_image.width() // 2, 60, 
                                  text="用鼠标拖拽选择区域，可以选择多个区域。选择完成后点击'下一步:选择输入框'", 
                                  font=("Arial", 12), fill="blue", tags='instruction')
        else:
            self.canvas.create_text(self.tk_image.width() // 2, 30, 
                                  text=f"步骤2: 选择输入框 - 在 {self.window_info['title']} 中选择文本输入框的位置", 
                                  font=("Arial", 14, "bold"), fill="green", tags='instruction')
            self.canvas.create_text(self.tk_image.width() // 2, 60, 
                                  text="用鼠标拖拽选择输入框区域，选择完成后点击'完成选择'", 
                                  font=("Arial", 12), fill="green", tags='instruction')

    def redraw_window_selections(self):
        """重新绘制所有选择区域"""
        # 清除所有选择矩形
        for item in self.canvas.find_all():
            tags = self.canvas.gettags(item)
            if 'selection' in tags:
                self.canvas.delete(item)
        
        # 重新绘制监控区域选择
        colors = ['red', 'green', 'blue', 'orange', 'purple']
        for i, sel in enumerate(self.selections):
            color = colors[i % len(colors)]
            x, y, w, h = sel
            self.canvas.create_rectangle(
                x, y, x + w, y + h,
                outline=color, width=3, fill='', stipple='gray25',
                tags='selection'
            )
            # 添加编号
            self.canvas.create_text(
                x + w // 2, y + h // 2,
                text=f"监控{i + 1}", font=("Arial", 14, "bold"),
                fill=color, tags='selection'
            )
        
        # 绘制输入框选择
        if self.input_box_position:
            x, y, w, h = self.input_box_position
            self.canvas.create_rectangle(
                x, y, x + w, y + h,
                outline='yellow', width=4, fill='yellow', stipple='gray50',
                tags='selection'
            )
            self.canvas.create_text(
                x + w // 2, y + h // 2,
                text="输入框", font=("Arial", 14, "bold"),
                fill='black', tags='selection'
            )
    
    def create_window_control_buttons_enhanced(self):
        """创建增强的窗口模式控制按钮"""
        button_frame = tk.Frame(self.root)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
        
        # 模式切换按钮
        self.next_step_button = tk.Button(button_frame, text="下一步:选择输入框", command=self.switch_to_input_mode,
                                        bg="blue", fg="white", font=("Arial", 12, "bold"), width=18)
        self.next_step_button.pack(side=tk.LEFT, padx=10)
        
        # 完成选择按钮
        self.finish_button = tk.Button(button_frame, text="完成选择", command=self.confirm_window_selection,
                                     bg="green", fg="white", font=("Arial", 12, "bold"), width=15)
        
        # 撤销按钮
        tk.Button(button_frame, text="撤销最后选择", command=self.undo_last_selection,
                 bg="orange", fg="white", font=("Arial", 12), width=15).pack(side=tk.LEFT, padx=10)
        
        # 清除所有选择
        tk.Button(button_frame, text="清除所有", command=self.clear_all_selections,
                 bg="red", fg="white", font=("Arial", 12), width=15).pack(side=tk.LEFT, padx=10)
        
        # 跳过输入框按钮
        self.skip_input_button = tk.Button(button_frame, text="跳过输入框", command=self.skip_input_box,
                                         bg="gray", fg="white", font=("Arial", 12), width=15)
        
        # 取消按钮
        tk.Button(button_frame, text="取消", command=self.cancel_window_selection,
                 bg="gray", fg="white", font=("Arial", 12), width=15).pack(side=tk.RIGHT, padx=10)
        
        # 根据当前模式更新按钮显示
        self.update_button_display()
    
    def switch_to_input_mode(self):
        """切换到输入框选择模式"""
        if not self.selections:
            messagebox.showwarning("警告", "请先选择至少一个监控区域")
            return
        
        self.selection_mode = "input_box"
        self.update_instruction_text()
        self.update_button_display()
        logger.info("🔄 切换到输入框选择模式")
    
    def skip_input_box(self):
        """跳过输入框选择"""
        self.input_box_position = None
        self.confirm_window_selection()
    
    def update_button_display(self):
        """根据当前模式更新按钮显示"""
        if self.selection_mode == "regions":
            self.next_step_button.pack(side=tk.LEFT, padx=10)
            self.finish_button.pack_forget()
            self.skip_input_button.pack_forget()
        else:  # input_box mode
            self.next_step_button.pack_forget()
            self.finish_button.pack(side=tk.LEFT, padx=10)
            self.skip_input_button.pack(side=tk.LEFT, padx=10)

    def create_window_control_buttons(self):
        """创建窗口模式的控制按钮（保留向后兼容）"""
        return self.create_window_control_buttons_enhanced()
    
    def confirm_window_selection(self):
        """确认窗口选择"""
        if self.selection_mode == "regions" and not self.selections:
            messagebox.showwarning("警告", "请先选择至少一个监控区域")
            return
        
        if self.selection_mode == "regions":
            # 从区域选择模式切换到输入框选择
            self.switch_to_input_mode()
            return
        
        # 完成所有选择
        self.selection_complete = True
        self.root.quit()
    
    def undo_last_selection(self):
        """撤销最后一个选择"""
        if self.selection_mode == "regions" and self.selections:
            self.selections.pop()
            self.redraw_window_selections()
        elif self.selection_mode == "input_box" and self.input_box_position:
            self.input_box_position = None
            self.redraw_window_selections()

    def clear_all_selections(self):
        """清除所有选择"""
        if self.selection_mode == "regions":
            self.selections.clear()
        elif self.selection_mode == "input_box":
            self.input_box_position = None
        self.redraw_window_selections()
    
    def cancel_window_selection(self):
        """取消窗口选择"""
        self.selection_complete = False
        self.selections.clear()
        self.root.quit()
    
    def ask_save_regions_with_window_info(self, regions: list, window_info: dict):
        """询问是否保存区域配置（包含窗口信息）"""
        try:
            root = tk.Tk()
            root.title("保存区域配置")
            root.geometry("400x200")
            self.center_window(root, 400, 200)
            
            save_choice = tk.BooleanVar()
            
            def save_config():
                save_choice.set(True)
                root.quit()
            
            def skip_save():
                save_choice.set(False)
                root.quit()
            
            tk.Label(root, text=f"是否保存这 {len(regions)} 个监控区域的配置？", 
                    font=("Arial", 12)).pack(pady=20)
            
            tk.Label(root, text=f"窗口: {window_info['title']}", 
                    font=("Arial", 10), fg="gray").pack(pady=5)
            
            button_frame = tk.Frame(root)
            button_frame.pack(pady=20)
            
            tk.Button(button_frame, text="保存", command=save_config,
                     bg="green", fg="white", font=("Arial", 11), width=10).pack(side=tk.LEFT, padx=10)
            
            tk.Button(button_frame, text="跳过", command=skip_save,
                     bg="gray", fg="white", font=("Arial", 11), width=10).pack(side=tk.LEFT, padx=10)
            
            root.mainloop()
            root.destroy()
            
            if save_choice.get():
                name = self.get_regions_name_with_window(len(regions), window_info)
                if name:
                    self.save_regions_with_window_info(name, regions, window_info)
            
        except Exception as e:
            logger.error(f"询问保存区域配置时出错: {e}")
    
    def get_regions_name_with_window(self, region_count: int, window_info: dict) -> str:
        """获取区域配置名称（包含窗口信息）"""
        try:
            import time
            
            # 生成默认名称
            timestamp = int(time.time())
            default_name = f"{window_info['title']}_{region_count}个区域_{timestamp}"
            
            root = tk.Tk()
            root.title("配置名称")
            root.geometry("450x150")
            self.center_window(root, 450, 150)
            
            name_result = None
            
            def save_name():
                nonlocal name_result
                name = name_entry.get().strip()
                if name:
                    name_result = name
                root.quit()
            
            def cancel():
                root.quit()
            
            tk.Label(root, text="请输入配置名称：", font=("Arial", 11)).pack(pady=10)
            
            name_entry = tk.Entry(root, font=("Arial", 11), width=40)
            name_entry.insert(0, default_name)
            name_entry.pack(pady=5)
            name_entry.focus()
            
            button_frame = tk.Frame(root)
            button_frame.pack(pady=15)
            
            tk.Button(button_frame, text="保存", command=save_name,
                     bg="green", fg="white", font=("Arial", 10), width=8).pack(side=tk.LEFT, padx=5)
            
            tk.Button(button_frame, text="取消", command=cancel,
                     bg="gray", fg="white", font=("Arial", 10), width=8).pack(side=tk.LEFT, padx=5)
            
            # 绑定回车键
            name_entry.bind('<Return>', lambda e: save_name())
            
            root.mainloop()
            root.destroy()
            
            return name_result
            
        except Exception as e:
            logger.error(f"获取区域配置名称时出错: {e}")
            return None
    
    def save_regions_with_window_info(self, name: str, regions: list, window_info: dict):
        """保存区域配置（包含窗口信息）"""
        try:
            import time
            saved_regions = self.load_saved_regions()
            
            config_data = {
                "window": {
                    "title": window_info['title'],
                    "width": window_info['width'],
                    "height": window_info['height']
                },
                "regions": [],
                "timestamp": time.time()
            }
            
            for region in regions:
                x, y, width, height = region
                config_data["regions"].append({
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height
                })
            
            saved_regions[name] = config_data
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(saved_regions, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ 已保存区域配置: {name} ({len(regions)}个区域)")
            messagebox.showinfo("成功", f"区域配置已保存: {name}")
            
        except Exception as e:
            logger.error(f"保存区域配置时出错: {e}")
            messagebox.showerror("错误", f"保存失败: {str(e)}") 

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
import tkinter as tk
from tkinter import ttk, messagebox
import pystray
from PIL import Image, ImageDraw
import threading
import keyboard
import mouse
import json
import os
import sys
from datetime import datetime
import ctypes
import subprocess
import wmi

# 调试模式开关（设为False可隐藏所有调试输出）
DEBUG_MODE = False

def hide_console():
    """隐藏控制台窗口"""
    try:
        # 获取控制台窗口句柄
        console_window = ctypes.windll.kernel32.GetConsoleWindow()
        if console_window != 0:
            # 隐藏控制台窗口
            ctypes.windll.user32.ShowWindow(console_window, 0)  # 0 = SW_HIDE
    except Exception as e:
        if DEBUG_MODE:
            print(f"隐藏控制台失败: {e}")

def show_console():
    """显示控制台窗口（调试用）"""
    try:
        console_window = ctypes.windll.kernel32.GetConsoleWindow()
        if console_window != 0:
            ctypes.windll.user32.ShowWindow(console_window, 1)  # 1 = SW_SHOW
    except Exception as e:
        if DEBUG_MODE:
            print(f"显示控制台失败: {e}")

def debug_print(message):
    """条件调试输出"""
    if DEBUG_MODE:
        print(message)

def is_admin():
    """检查是否以管理员身份运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """以管理员身份重新运行程序"""
    try:
        if is_admin():
            return True
        else:
            # 构建完整的命令行参数，包括调试模式
            args = " ".join(sys.argv)
            debug_print(f"🔄 以管理员身份重新启动: {sys.executable} {args}")
            
            # 以管理员身份重新启动程序，保持所有参数
            ctypes.windll.shell32.ShellExecuteW(
                None, 
                "runas", 
                sys.executable, 
                args,  # 传递完整的参数列表
                None, 
                1
            )
            return False
    except Exception as e:
        messagebox.showerror("权限错误", f"无法获取管理员权限：{e}\n程序可能无法正常工作。")
        return True  # 继续运行，但可能功能受限

class FakeLockScreen:
    def __init__(self):
        self.settings_file = "lock_settings.json"
        self.unlock_key = "ctrl+alt+u"  # 默认解锁键
        self.lock_key = "ctrl+alt+l"    # 默认锁屏键
        self.is_locked = False
        self.lock_window = None
        self.main_window = None
        self.tray_icon = None
        self.capturing_key = False
        self.keyboard_hook = None  # 键盘钩子
        self.original_brightness = None  # 原始亮度值
        self.brightness_control_available = False  # 亮度控制是否可用
        self.mouse_hidden = False  # 鼠标是否已隐藏
        
        # 初始化WMI连接
        try:
            self.wmi_connection = wmi.WMI(namespace='wmi')
            self.brightness_methods = self.wmi_connection.WmiMonitorBrightnessMethods()[0]
            self.brightness_monitor = self.wmi_connection.WmiMonitorBrightness()[0]
            self.brightness_control_available = True
            debug_print("✓ WMI亮度控制初始化成功")
        except Exception as e:
            debug_print(f"⚠ WMI亮度控制初始化失败: {e}")
            self.wmi_connection = None
            self.brightness_methods = None
            self.brightness_monitor = None
            debug_print("💡 程序将在无亮度控制模式下运行")
        
        # 加载设置
        self.load_settings()
        
        # 创建主窗口
        self.create_main_window()
        
        # 设置全局快捷键监听
        self.setup_global_hotkeys()
        
        # 创建系统托盘
        self.create_tray_icon()

    def load_settings(self):
        """加载设置"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.unlock_key = settings.get('unlock_key', 'ctrl+alt+u')
                    self.lock_key = settings.get('lock_key', 'ctrl+alt+l')
        except:
            pass

    def save_settings(self):
        """保存设置"""
        try:
            settings = {
                'unlock_key': self.unlock_key,
                'lock_key': self.lock_key
            }
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except:
            pass

    def create_main_window(self):
        """创建主窗口"""
        self.main_window = tk.Tk()
        self.main_window.title("假锁屏工具")
        self.main_window.geometry("550x500")
        self.main_window.resizable(False, False)
        
        # 设置窗口居中
        self.center_window(self.main_window, 550, 500)
        
        # 创建主框架
        main_frame = ttk.Frame(self.main_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(main_frame, text="假锁屏工具", font=("微软雅黑", 16, "bold"))
        title_label.pack(pady=(0, 15))
        
        # 说明文字
        description = """功能说明：
• 创建全屏黑色遮罩，完全隐蔽
• 完全禁用键盘输入（除解锁快捷键外）
• 完全禁用鼠标输入并隐藏指针
• 动态亮度控制（锁屏时获取当前亮度）
• 可设置自定义锁屏和解锁快捷键
• 支持系统托盘运行

使用方法：
1. 点击"锁定屏幕"或使用锁屏快捷键开始假锁屏
2. 使用设定的快捷键解锁（默认: Ctrl+Alt+U）
3. 可最小化到系统托盘后台运行"""
        
        desc_label = ttk.Label(main_frame, text=description, font=("微软雅黑", 10), justify=tk.LEFT)
        desc_label.pack(pady=(0, 15), anchor=tk.W)
        
        # 当前快捷键显示
        key_frame = ttk.Frame(main_frame)
        key_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 解锁快捷键
        unlock_frame = ttk.Frame(key_frame)
        unlock_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(unlock_frame, text="解锁快捷键:", font=("微软雅黑", 10)).pack(side=tk.LEFT)
        self.unlock_key_label = ttk.Label(unlock_frame, text=self.unlock_key, font=("微软雅黑", 10, "bold"), foreground="blue")
        self.unlock_key_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # 锁屏快捷键
        lock_frame = ttk.Frame(key_frame)
        lock_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(lock_frame, text="锁屏快捷键:", font=("微软雅黑", 10)).pack(side=tk.LEFT)
        self.lock_key_label = ttk.Label(lock_frame, text=self.lock_key, font=("微软雅黑", 10, "bold"), foreground="green")
        self.lock_key_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=15)
        
        # 锁定按钮
        lock_btn = ttk.Button(button_frame, text="锁定屏幕", command=self.lock_screen, width=12)
        lock_btn.pack(side=tk.LEFT, padx=(0, 8))
        
        # 最小化到托盘按钮
        tray_btn = ttk.Button(button_frame, text="最小化到托盘", command=self.hide_to_tray, width=12)
        tray_btn.pack(side=tk.LEFT, padx=(0, 8))
        
        # 设置解锁键按钮
        set_unlock_btn = ttk.Button(button_frame, text="设置解锁键", command=self.set_unlock_key, width=12)
        set_unlock_btn.pack(side=tk.LEFT, padx=(0, 8))
        
        # 设置锁屏键按钮
        set_lock_btn = ttk.Button(button_frame, text="设置锁屏键", command=self.set_lock_key, width=12)
        set_lock_btn.pack(side=tk.LEFT)
        
        # 状态栏
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(15, 0))
        
        self.status_label = ttk.Label(status_frame, text="就绪", font=("微软雅黑", 9))
        self.status_label.pack(side=tk.LEFT)
        
        # 功能状态显示
        status_text = []
        
        # 权限状态显示
        admin_status = "管理员模式" if is_admin() else "普通模式"
        admin_color = "green" if is_admin() else "orange"
        status_text.append(f"[{admin_status}]")
        
        # 亮度控制状态
        brightness_status = "亮度控制✓" if self.brightness_control_available else "亮度控制✗"
        status_text.append(f"[{brightness_status}]")
        
        # 显示状态
        combined_status = " ".join(status_text)
        admin_label = ttk.Label(status_frame, text=combined_status, 
                               font=("微软雅黑", 9), foreground=admin_color)
        admin_label.pack(side=tk.RIGHT)
        
        # 绑定窗口关闭事件
        self.main_window.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 绑定强制鼠标恢复快捷键 (Ctrl+Shift+M)
        self.main_window.bind('<Control-Shift-KeyPress-M>', lambda e: self.force_restore_mouse())
        self.main_window.bind('<Control-Shift-KeyPress-m>', lambda e: self.force_restore_mouse())

    def center_window(self, window, width, height):
        """窗口居中"""
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        window.geometry(f"{width}x{height}+{x}+{y}")

    def create_lock_window(self):
        """创建锁屏窗口"""
        self.lock_window = tk.Toplevel()
        self.lock_window.title("锁屏")
        
        # 全屏设置
        self.lock_window.attributes('-fullscreen', True)
        self.lock_window.attributes('-topmost', True)
        self.lock_window.configure(bg='black')
        
        # 禁用窗口操作
        self.lock_window.overrideredirect(True)
        
        # 隐藏鼠标指针 - 窗口级别
        self.lock_window.config(cursor="none")
        
        # 设置鼠标边界限制
        self.setup_mouse_boundary()
        
        # 提示文字
        hint_label = tk.Label(
            self.lock_window,
            text=f"按 {self.unlock_key.upper()} 解锁",
            font=("微软雅黑", 16),
            fg="gray",
            bg="black",
            cursor="none"
        )
        hint_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # 获取焦点并捕获所有事件
        self.lock_window.focus_force()
        self.lock_window.grab_set()
        
        # 绑定鼠标移动事件来确保指针隐藏
        self.lock_window.bind('<Motion>', self._on_mouse_move)
        self.lock_window.bind('<Enter>', self._on_mouse_move)
        self.lock_window.bind('<Leave>', self._on_mouse_move)
        
        # 绑定所有键盘和鼠标事件到空函数，实现禁用
        self.lock_window.bind('<Key>', lambda e: "break")
        self.lock_window.bind('<Button>', lambda e: "break")
        
        # 禁用Alt+Tab等系统快捷键
        self.lock_window.bind('<Alt-Key>', lambda e: "break")
        self.lock_window.bind('<Control-Key>', lambda e: "break")

    def setup_mouse_boundary(self):
        """设置鼠标边界限制，防止移动到屏幕边缘"""
        try:
            # 获取屏幕尺寸
            screen_width = ctypes.windll.user32.GetSystemMetrics(0)
            screen_height = ctypes.windll.user32.GetSystemMetrics(1)
            
            # 设置安全边界（距离边缘20像素）
            boundary_margin = 20
            
            # 定义边界矩形
            left = boundary_margin
            top = boundary_margin
            right = screen_width - boundary_margin
            bottom = screen_height - boundary_margin
            
            # 使用ClipCursor限制鼠标移动范围
            rect = ctypes.wintypes.RECT()
            rect.left = left
            rect.top = top
            rect.right = right
            rect.bottom = bottom
            
            result = ctypes.windll.user32.ClipCursor(ctypes.byref(rect))
            if result:
                debug_print(f"✓ 已设置鼠标边界限制: ({left}, {top}) - ({right}, {bottom})")
                self.mouse_clipped = True
            else:
                debug_print("⚠ 设置鼠标边界失败")
                self.mouse_clipped = False
                
        except Exception as e:
            debug_print(f"⚠ 设置鼠标边界异常: {e}")
            self.mouse_clipped = False

    def remove_mouse_boundary(self):
        """移除鼠标边界限制"""
        try:
            if hasattr(self, 'mouse_clipped') and self.mouse_clipped:
                # 传入NULL指针来移除限制
                result = ctypes.windll.user32.ClipCursor(None)
                if result:
                    debug_print("✓ 已移除鼠标边界限制")
                    self.mouse_clipped = False
                else:
                    debug_print("⚠ 移除鼠标边界失败")
        except Exception as e:
            debug_print(f"⚠ 移除鼠标边界异常: {e}")

    def _on_mouse_move(self, event=None):
        """鼠标移动事件处理 - 确保指针保持隐藏"""
        try:
            if self.is_locked and self.mouse_hidden:
                # 立即隐藏可能出现的鼠标指针
                ctypes.windll.user32.ShowCursor(False)
                
                # 获取当前鼠标位置
                mouse_pos = ctypes.wintypes.POINT()
                ctypes.windll.user32.GetCursorPos(ctypes.byref(mouse_pos))
                
                # 获取屏幕尺寸
                screen_width = ctypes.windll.user32.GetSystemMetrics(0)
                screen_height = ctypes.windll.user32.GetSystemMetrics(1)
                
                # 检查是否在屏幕边缘
                edge_threshold = 10
                at_edge = (
                    mouse_pos.x <= edge_threshold or 
                    mouse_pos.y <= edge_threshold or 
                    mouse_pos.x >= screen_width - edge_threshold or 
                    mouse_pos.y >= screen_height - edge_threshold
                )
                
                if at_edge:
                    # 如果在边缘，移动到安全位置
                    safe_x = screen_width // 2 + 50
                    safe_y = screen_height // 2 + 50
                    ctypes.windll.user32.SetCursorPos(safe_x, safe_y)
                    debug_print("🖱️ 检测到边缘移动，已重定位鼠标")
        except:
            pass

    def force_restore_mouse(self):
        """强制恢复鼠标指针 - 紧急恢复方法"""
        debug_print("🚨 执行强制鼠标指针恢复...")
        try:
            # 方法1：多次调用ShowCursor(True)
            for i in range(20):  # 增加尝试次数
                result = ctypes.windll.user32.ShowCursor(True)
                debug_print(f"🔄 强制恢复尝试 {i+1}: ShowCursor = {result}")
                if result >= 0:
                    break
            
            # 方法2：获取当前鼠标状态并强制显示
            cursor_info = ctypes.wintypes.CURSORINFO()
            cursor_info.cbSize = ctypes.sizeof(ctypes.wintypes.CURSORINFO)
            ctypes.windll.user32.GetCursorInfo(ctypes.byref(cursor_info))
            debug_print(f"🖱️ 当前鼠标状态: flags={cursor_info.flags}")
            
            # 强制设置鼠标可见
            if cursor_info.flags == 0:  # 鼠标隐藏
                ctypes.windll.user32.ShowCursor(True)
                debug_print("✓ 强制显示鼠标指针")
            
            self.mouse_hidden = False
            debug_print("✅ 强制鼠标恢复完成")
            return True
            
        except Exception as e:
            debug_print(f"❌ 强制鼠标恢复失败: {e}")
            self.mouse_hidden = False  # 重置状态
            return False

    def hide_mouse_cursor(self):
        """隐藏鼠标指针 - 增强版本"""
        try:
            if not self.mouse_hidden:
                debug_print("🔄 正在隐藏鼠标指针...")
                
                # 获取当前鼠标状态
                cursor_info = ctypes.wintypes.CURSORINFO()
                cursor_info.cbSize = ctypes.sizeof(ctypes.wintypes.CURSORINFO)
                ctypes.windll.user32.GetCursorInfo(ctypes.byref(cursor_info))
                debug_print(f"🖱️ 隐藏前鼠标状态: flags={cursor_info.flags}")
                
                # 方法1：多次调用ShowCursor(False)确保完全隐藏
                for i in range(10):  # 连续调用多次
                    result = ctypes.windll.user32.ShowCursor(False)
                    debug_print(f"🖱️ ShowCursor(False) 第{i+1}次调用结果: {result}")
                    if result <= -10:  # 当计数器足够负时停止
                        break
                
                # 方法2：启动持续监控线程
                self.start_cursor_monitor()
                
                self.mouse_hidden = True
                debug_print("✓ 鼠标指针已完全隐藏")
                return True
        except Exception as e:
            debug_print(f"⚠ 隐藏鼠标指针失败: {e}")
            return False

    def start_cursor_monitor(self):
        """启动鼠标指针监控线程，持续确保指针隐藏"""
        def monitor_cursor():
            debug_print("🔄 启动鼠标指针监控线程...")
            while self.is_locked and self.mouse_hidden:
                try:
                    # 检查鼠标指针是否可见
                    cursor_info = ctypes.wintypes.CURSORINFO()
                    cursor_info.cbSize = ctypes.sizeof(ctypes.wintypes.CURSORINFO)
                    ctypes.windll.user32.GetCursorInfo(ctypes.byref(cursor_info))
                    
                    # 如果鼠标指针变为可见，立即隐藏
                    if cursor_info.flags != 0:  # 0表示隐藏，非0表示可见
                        ctypes.windll.user32.ShowCursor(False)
                    
                    # 获取当前鼠标位置
                    mouse_pos = ctypes.wintypes.POINT()
                    ctypes.windll.user32.GetCursorPos(ctypes.byref(mouse_pos))
                    
                    # 获取屏幕尺寸
                    screen_width = ctypes.windll.user32.GetSystemMetrics(0)
                    screen_height = ctypes.windll.user32.GetSystemMetrics(1)
                    
                    # 检查鼠标是否在屏幕边缘（边缘5像素范围内）
                    edge_threshold = 5
                    at_edge = (
                        mouse_pos.x <= edge_threshold or 
                        mouse_pos.y <= edge_threshold or 
                        mouse_pos.x >= screen_width - edge_threshold or 
                        mouse_pos.y >= screen_height - edge_threshold
                    )
                    
                    if at_edge:
                        # 如果鼠标在边缘，强制隐藏指针并移动到安全位置
                        ctypes.windll.user32.ShowCursor(False)
                        # 移动到屏幕中心稍偏的位置，避免边缘效应
                        safe_x = screen_width // 2 + 100
                        safe_y = screen_height // 2 + 100
                        ctypes.windll.user32.SetCursorPos(safe_x, safe_y)
                    
                    import time
                    time.sleep(0.01)  # 每10毫秒检查一次，更频繁
                    
                except Exception as e:
                    debug_print(f"⚠ 鼠标监控异常: {e}")
                    break
            
            debug_print("🔄 鼠标指针监控线程已停止")
        
        # 在后台线程中运行监控
        import threading
        self.cursor_monitor_thread = threading.Thread(target=monitor_cursor, daemon=True)
        self.cursor_monitor_thread.start()

    def show_mouse_cursor(self):
        """显示鼠标指针 - 增强版本"""
        try:
            if self.mouse_hidden:
                debug_print("🔄 正在恢复鼠标指针显示...")
                
                # 停止鼠标监控线程
                self.mouse_hidden = False  # 这会停止监控线程
                
                # 等待监控线程停止
                if hasattr(self, 'cursor_monitor_thread') and self.cursor_monitor_thread.is_alive():
                    import time
                    time.sleep(0.1)  # 给线程一点时间停止
                
                # 强制显示鼠标指针
                cursor_count = 0
                max_attempts = 20  # 增加尝试次数
                
                while cursor_count < max_attempts:
                    result = ctypes.windll.user32.ShowCursor(True)
                    debug_print(f"🖱️ ShowCursor调用结果: {result}")
                    
                    if result >= 0:  # 鼠标指针已显示
                        debug_print("✓ 鼠标指针已恢复显示")
                        return True
                    
                    cursor_count += 1
                    import time
                    time.sleep(0.05)  # 短暂等待
                
                # 如果上面的方法失败，尝试强制恢复
                debug_print("⚠ 标准方法失败，尝试强制恢复鼠标指针...")
                try:
                    # 强制设置鼠标指针可见
                    while ctypes.windll.user32.ShowCursor(True) < 0:
                        pass
                    debug_print("✓ 强制恢复鼠标指针成功")
                    return True
                except:
                    debug_print("❌ 强制恢复也失败")
                    
            else:
                debug_print("ℹ️ 鼠标指针未隐藏，无需恢复")
                return True
                
        except Exception as e:
            debug_print(f"⚠ 恢复鼠标指针异常: {e}")
            # 重置状态，避免程序认为鼠标仍然隐藏
            self.mouse_hidden = False
            return False

    def lock_screen(self):
        """锁定屏幕"""
        if self.is_locked:
            return
            
        debug_print("🔒 开始锁定屏幕...")
        
        # 隐藏鼠标指针
        debug_print("🖱️ 隐藏鼠标指针...")
        self.hide_mouse_cursor()
        
        # 将鼠标移动到屏幕中心安全位置
        try:
            screen_width = ctypes.windll.user32.GetSystemMetrics(0)
            screen_height = ctypes.windll.user32.GetSystemMetrics(1)
            safe_x = screen_width // 2
            safe_y = screen_height // 2
            ctypes.windll.user32.SetCursorPos(safe_x, safe_y)
            debug_print(f"🖱️ 鼠标已移动到安全位置: ({safe_x}, {safe_y})")
        except Exception as e:
            debug_print(f"⚠ 移动鼠标失败: {e}")
        
        # 动态保存当前亮度并设置为最低（如果支持）
        if self.brightness_control_available:
            debug_print("💾 动态获取并保存当前亮度...")
            brightness_saved = self.save_current_brightness()
            if brightness_saved:
                debug_print("🔅 设置亮度为最低...")
                success = self.set_brightness(0)  # 设置亮度为0（最低）
                if not success:
                    debug_print("⚠ 亮度控制失败，但程序继续运行")
            else:
                debug_print("⚠ 无法保存当前亮度，跳过亮度调节")
        else:
            debug_print("ℹ️ 亮度控制不可用，跳过亮度调节")
        
        self.is_locked = True
        self.status_label.config(text="屏幕已锁定")
        
        # 隐藏主窗口
        if self.main_window:
            self.main_window.withdraw()
        
        # 创建锁屏窗口
        self.create_lock_window()
        
        # 禁用键盘输入（除了解锁快捷键）
        self.disable_keyboard()
        
        debug_print("✅ 锁定完成")

    def setup_global_hotkeys(self):
        """设置全局快捷键"""
        try:
            # 移除旧的快捷键
            keyboard.remove_hotkey(self.unlock_key)
            keyboard.remove_hotkey(self.lock_key)
        except:
            pass
            
        try:
            # 设置解锁快捷键
            keyboard.add_hotkey(self.unlock_key, self.unlock_screen, 
                              suppress=True,  # 阻止快捷键传递给其他应用
                              timeout=1)      # 快速响应
            debug_print(f"✓ 已设置解锁快捷键: {self.unlock_key}")
            
            # 设置锁屏快捷键
            keyboard.add_hotkey(self.lock_key, self.lock_screen, 
                              suppress=True,  # 阻止快捷键传递给其他应用
                              timeout=1)      # 快速响应
            debug_print(f"✓ 已设置锁屏快捷键: {self.lock_key}")
            
        except Exception as e:
            debug_print(f"⚠ 设置快捷键失败: {e}")
            if not is_admin():
                debug_print("💡 建议以管理员身份运行程序以获得完整功能")
            
        # 额外设置低级键盘钩子作为备用
        self.setup_backup_hotkey()

    def setup_backup_hotkey(self):
        """设置备用的低级键盘钩子，确保最高优先级"""
        try:
            # 移除现有的备用钩子
            if hasattr(self, 'backup_hook') and self.backup_hook:
                keyboard.unhook(self.backup_hook)
            
            # 解析解锁快捷键
            unlock_keys = self.unlock_key.lower().split('+')
            unlock_ctrl_needed = 'ctrl' in unlock_keys
            unlock_alt_needed = 'alt' in unlock_keys
            unlock_shift_needed = 'shift' in unlock_keys
            unlock_main_key = [k for k in unlock_keys if k not in ['ctrl', 'alt', 'shift']]
            unlock_main_key = unlock_main_key[0] if unlock_main_key else None
            
            # 解析锁屏快捷键
            lock_keys = self.lock_key.lower().split('+')
            lock_ctrl_needed = 'ctrl' in lock_keys
            lock_alt_needed = 'alt' in lock_keys
            lock_shift_needed = 'shift' in lock_keys
            lock_main_key = [k for k in lock_keys if k not in ['ctrl', 'alt', 'shift']]
            lock_main_key = lock_main_key[0] if lock_main_key else None
            
            def backup_hotkey_handler(event):
                if event.event_type == keyboard.KEY_DOWN:
                    # 检查修饰键状态
                    ctrl_pressed = keyboard.is_pressed('ctrl')
                    alt_pressed = keyboard.is_pressed('alt') 
                    shift_pressed = keyboard.is_pressed('shift')
                    
                    # 检查解锁快捷键
                    if (unlock_main_key and event.name == unlock_main_key and
                        unlock_ctrl_needed == ctrl_pressed and 
                        unlock_alt_needed == alt_pressed and 
                        unlock_shift_needed == shift_pressed):
                        
                        debug_print("🔑 备用钩子触发解锁")
                        # 在新线程中执行解锁，避免阻塞键盘钩子
                        import threading
                        threading.Thread(target=self.unlock_screen, daemon=True).start()
                        return True  # 阻止事件传递
                    
                    # 检查锁屏快捷键（只有在未锁定时才响应）
                    if (not self.is_locked and lock_main_key and event.name == lock_main_key and
                        lock_ctrl_needed == ctrl_pressed and 
                        lock_alt_needed == alt_pressed and 
                        lock_shift_needed == shift_pressed):
                        
                        debug_print("🔑 备用钩子触发锁屏")
                        # 在新线程中执行锁屏，避免阻塞键盘钩子
                        import threading
                        threading.Thread(target=self.lock_screen, daemon=True).start()
                        return True  # 阻止事件传递
                
                return False  # 不阻止其他按键
            
            # 设置低级键盘钩子，最高优先级
            self.backup_hook = keyboard.hook(backup_hotkey_handler, suppress=False)
            debug_print(f"✓ 已设置备用高优先级钩子: 解锁({self.unlock_key}) 锁屏({self.lock_key})")
            
        except Exception as e:
            debug_print(f"⚠ 设置备用快捷键失败: {e}")
            if not is_admin():
                debug_print("💡 某些高级功能需要管理员权限")

    def disable_keyboard(self):
        """禁用键盘输入"""
        try:
            # 移除现有的键盘钩子
            if self.keyboard_hook:
                keyboard.unhook(self.keyboard_hook)
            
            # 解析解锁快捷键
            unlock_keys = self.unlock_key.lower().split('+')
            unlock_ctrl_needed = 'ctrl' in unlock_keys
            unlock_alt_needed = 'alt' in unlock_keys
            unlock_shift_needed = 'shift' in unlock_keys
            unlock_main_key = [k for k in unlock_keys if k not in ['ctrl', 'alt', 'shift']]
            unlock_main_key = unlock_main_key[0] if unlock_main_key else None
            
            def enhanced_block_handler(event):
                if not self.is_locked:
                    return False  # 未锁定时不阻止任何按键
                
                # 检查是否是解锁快捷键
                if event.event_type == keyboard.KEY_DOWN and unlock_main_key and event.name == unlock_main_key:
                    ctrl_pressed = keyboard.is_pressed('ctrl')
                    alt_pressed = keyboard.is_pressed('alt')
                    shift_pressed = keyboard.is_pressed('shift')
                    
                    if (unlock_ctrl_needed == ctrl_pressed and 
                        unlock_alt_needed == alt_pressed and 
                        unlock_shift_needed == shift_pressed):
                        debug_print("🔑 键盘阻止器触发解锁")
                        # 这是解锁快捷键，在新线程中执行解锁
                        import threading
                        threading.Thread(target=self.unlock_screen, daemon=True).start()
                        return True  # 阻止事件传递
                
                # 锁定状态下阻止所有其他按键
                return True
            
            # 设置增强的键盘阻止钩子
            self.keyboard_hook = keyboard.hook(enhanced_block_handler, suppress=True)
            debug_print("✓ 已启用增强键盘锁定")
            
        except Exception as e:
            debug_print(f"⚠ 禁用键盘失败: {e}")
            if not is_admin():
                messagebox.showwarning("权限提醒", 
                    "键盘禁用功能需要管理员权限。\n建议重新以管理员身份运行程序。")

    def enable_keyboard(self):
        """启用键盘输入"""
        try:
            if self.keyboard_hook:
                keyboard.unhook(self.keyboard_hook)
                self.keyboard_hook = None
            debug_print("✓ 已解除键盘锁定")
        except Exception as e:
            debug_print(f"⚠ 启用键盘失败: {e}")

    def unlock_screen(self):
        """解锁屏幕"""
        if not self.is_locked:
            return
            
        debug_print("🔓 开始解锁屏幕...")
        self.is_locked = False
        
        # 移除鼠标边界限制
        self.remove_mouse_boundary()
        
        # 恢复鼠标指针显示 - 提前执行，确保优先级
        debug_print("🖱️ 恢复鼠标指针...")
        mouse_restored = self.show_mouse_cursor()
        if not mouse_restored:
            debug_print("⚠ 鼠标指针恢复失败，尝试备用方法...")
            # 备用恢复方法
            try:
                import time
                time.sleep(0.5)
                self.show_mouse_cursor()
            except:
                debug_print("⚠ 备用鼠标恢复方法也失败")
        
        # 恢复原始亮度 - 增加重试机制
        debug_print("🔆 正在恢复屏幕亮度...")
        try:
            self.restore_brightness()
            # 额外等待一点时间确保亮度设置生效
            import time
            time.sleep(0.1)  # 减少等待时间
        except Exception as e:
            debug_print(f"⚠ 亮度恢复出现异常: {e}")
            # 重试一次
            try:
                time.sleep(0.3)
                self.restore_brightness()
            except:
                debug_print("⚠ 亮度恢复重试失败，继续执行其他解锁操作")
        
        # 启用键盘输入
        self.enable_keyboard()
        
        # 安全地关闭锁屏窗口（使用主线程）
        if self.lock_window:
            try:
                # 使用after方法在主线程中执行窗口销毁
                self.lock_window.after(0, self._destroy_lock_window)
            except Exception as e:
                debug_print(f"⚠ 窗口销毁调度失败: {e}")
                # 备用方法：直接销毁
                try:
                    self.lock_window.destroy()
                    self.lock_window = None
                except:
                    debug_print("⚠ 备用窗口销毁也失败，但不影响解锁")
        
        # 显示主窗口
        if self.main_window:
            try:
                self.main_window.after(0, self._show_main_window)
            except:
                # 备用方法
                try:
                    self.main_window.deiconify()
                    self.main_window.lift()
                except:
                    debug_print("⚠ 主窗口显示失败")
        
        # 最后再次确认鼠标指针状态
        if self.mouse_hidden:
            debug_print("🔄 最终确认：再次尝试恢复鼠标指针...")
            self.show_mouse_cursor()
        
        debug_print("✅ 解锁完成")

    def _destroy_lock_window(self):
        """在主线程中安全地销毁锁屏窗口"""
        try:
            if self.lock_window:
                self.lock_window.destroy()
                self.lock_window = None
        except Exception as e:
            debug_print(f"⚠ 锁屏窗口销毁失败: {e}")

    def _show_main_window(self):
        """在主线程中安全地显示主窗口"""
        try:
            if self.main_window:
                self.main_window.deiconify()
                self.main_window.lift()
                self.status_label.config(text="屏幕已解锁")
                
                # 在主窗口显示后，再次检查鼠标状态
                if self.mouse_hidden:
                    debug_print("🔄 主窗口显示后，再次确认鼠标指针状态...")
                    self.show_mouse_cursor()
        except Exception as e:
            debug_print(f"⚠ 主窗口显示失败: {e}")

    def set_unlock_key(self):
        """设置解锁快捷键"""
        if self.capturing_key:
            return
            
        # 创建设置窗口
        setting_window = tk.Toplevel(self.main_window)
        setting_window.title("设置解锁快捷键")
        setting_window.geometry("400x200")
        setting_window.resizable(False, False)
        setting_window.transient(self.main_window)
        setting_window.grab_set()
        
        self.center_window(setting_window, 400, 200)
        
        # 主框架
        frame = ttk.Frame(setting_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # 说明
        ttk.Label(frame, text="请按下您想设置的快捷键组合", font=("微软雅黑", 12)).pack(pady=(0, 20))
        
        # 显示当前捕获的键
        self.captured_key_var = tk.StringVar(value="等待按键...")
        key_display = ttk.Label(frame, textvariable=self.captured_key_var, font=("微软雅黑", 14, "bold"))
        key_display.pack(pady=(0, 20))
        
        # 按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        def save_key():
            if hasattr(self, 'new_unlock_key') and self.new_unlock_key:
                # 移除旧的快捷键
                try:
                    keyboard.remove_hotkey(self.unlock_key)
                except:
                    pass
                
                self.unlock_key = self.new_unlock_key
                self.unlock_key_label.config(text=self.unlock_key)
                self.save_settings()
                self.setup_global_hotkeys()
                
                # 清理状态
                self.capturing_key = False
                keyboard.unhook_all()
                self.setup_global_hotkeys()  # 重新设置解锁快捷键
                
                setting_window.destroy()
                messagebox.showinfo("成功", f"解锁快捷键已设置为: {self.unlock_key}")
            else:
                messagebox.showwarning("警告", "请先按下快捷键")
        
        def cancel():
            # 清理状态
            self.capturing_key = False
            keyboard.unhook_all()
            self.setup_global_hotkeys()  # 重新设置解锁快捷键
            setting_window.destroy()
        
        ttk.Button(btn_frame, text="保存", command=save_key).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="取消", command=cancel).pack(side=tk.LEFT)
        
        # 开始捕获按键
        self.capturing_key = True
        self.new_unlock_key = None
        
        def on_key_event(event):
            if not self.capturing_key:
                return
                
            keys = []
            if event.name == 'ctrl':
                keys.append('ctrl')
            elif event.name == 'alt':
                keys.append('alt')
            elif event.name == 'shift':
                keys.append('shift')
            elif event.name == 'cmd':
                keys.append('cmd')
            else:
                # 检查修饰键状态
                modifiers = []
                if keyboard.is_pressed('ctrl'):
                    modifiers.append('ctrl')
                if keyboard.is_pressed('alt'):
                    modifiers.append('alt')
                if keyboard.is_pressed('shift'):
                    modifiers.append('shift')
                
                if modifiers:
                    keys = modifiers + [event.name]
                    key_combination = '+'.join(keys)
                    self.captured_key_var.set(f"捕获到: {key_combination}")
                    self.new_unlock_key = key_combination
        
        keyboard.on_press(on_key_event)
        
        def on_window_close():
            self.capturing_key = False
            keyboard.unhook_all()
            self.setup_global_hotkeys()  # 重新设置解锁快捷键
            setting_window.destroy()
            
        setting_window.protocol("WM_DELETE_WINDOW", on_window_close)

    def set_lock_key(self):
        """设置锁屏快捷键"""
        if self.capturing_key:
            return
            
        # 创建设置窗口
        setting_window = tk.Toplevel(self.main_window)
        setting_window.title("设置锁屏快捷键")
        setting_window.geometry("400x200")
        setting_window.resizable(False, False)
        setting_window.transient(self.main_window)
        setting_window.grab_set()
        
        self.center_window(setting_window, 400, 200)
        
        # 主框架
        frame = ttk.Frame(setting_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # 说明
        ttk.Label(frame, text="请按下您想设置的快捷键组合", font=("微软雅黑", 12)).pack(pady=(0, 20))
        
        # 显示当前捕获的键
        self.captured_key_var = tk.StringVar(value="等待按键...")
        key_display = ttk.Label(frame, textvariable=self.captured_key_var, font=("微软雅黑", 14, "bold"))
        key_display.pack(pady=(0, 20))
        
        # 按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        def save_key():
            if hasattr(self, 'new_lock_key') and self.new_lock_key:
                # 移除旧的快捷键
                try:
                    keyboard.remove_hotkey(self.lock_key)
                except:
                    pass
                
                self.lock_key = self.new_lock_key
                self.lock_key_label.config(text=self.lock_key)
                self.save_settings()
                self.setup_global_hotkeys()
                
                # 清理状态
                self.capturing_key = False
                keyboard.unhook_all()
                self.setup_global_hotkeys()  # 重新设置锁屏快捷键
                
                setting_window.destroy()
                messagebox.showinfo("成功", f"锁屏快捷键已设置为: {self.lock_key}")
            else:
                messagebox.showwarning("警告", "请先按下快捷键")
        
        def cancel():
            # 清理状态
            self.capturing_key = False
            keyboard.unhook_all()
            self.setup_global_hotkeys()  # 重新设置锁屏快捷键
            setting_window.destroy()
        
        ttk.Button(btn_frame, text="保存", command=save_key).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="取消", command=cancel).pack(side=tk.LEFT)
        
        # 开始捕获按键
        self.capturing_key = True
        self.new_lock_key = None
        
        def on_key_event(event):
            if not self.capturing_key:
                return
                
            keys = []
            if event.name == 'ctrl':
                keys.append('ctrl')
            elif event.name == 'alt':
                keys.append('alt')
            elif event.name == 'shift':
                keys.append('shift')
            elif event.name == 'cmd':
                keys.append('cmd')
            else:
                # 检查修饰键状态
                modifiers = []
                if keyboard.is_pressed('ctrl'):
                    modifiers.append('ctrl')
                if keyboard.is_pressed('alt'):
                    modifiers.append('alt')
                if keyboard.is_pressed('shift'):
                    modifiers.append('shift')
                
                if modifiers:
                    keys = modifiers + [event.name]
                    key_combination = '+'.join(keys)
                    self.captured_key_var.set(f"捕获到: {key_combination}")
                    self.new_lock_key = key_combination
        
        keyboard.on_press(on_key_event)
        
        def on_window_close():
            self.capturing_key = False
            keyboard.unhook_all()
            self.setup_global_hotkeys()  # 重新设置锁屏快捷键
            setting_window.destroy()
            
        setting_window.protocol("WM_DELETE_WINDOW", on_window_close)

    def create_tray_icon(self):
        """创建系统托盘图标"""
        # 创建图标
        def create_icon():
            image = Image.new('RGB', (64, 64), color='black')
            draw = ImageDraw.Draw(image)
            draw.ellipse([16, 16, 48, 48], fill='white')
            draw.ellipse([20, 20, 44, 44], fill='black')
            return image

        # 托盘菜单
        def show_window(icon, item):
            self.main_window.deiconify()
            self.main_window.lift()

        def lock_from_tray(icon, item):
            self.lock_screen()

        def quit_app(icon, item):
            self.quit_application()

        menu = pystray.Menu(
            pystray.MenuItem("显示主窗口", show_window),
            pystray.MenuItem("锁定屏幕", lock_from_tray),
            pystray.MenuItem("退出", quit_app)
        )

        self.tray_icon = pystray.Icon("FakeLockScreen", create_icon(), "假锁屏工具", menu)
        
        # 在单独线程中运行托盘
        def run_tray():
            self.tray_icon.run()
            
        tray_thread = threading.Thread(target=run_tray, daemon=True)
        tray_thread.start()

    def hide_to_tray(self):
        """隐藏到系统托盘"""
        self.main_window.withdraw()
        self.status_label.config(text="已最小化到系统托盘")

    def on_closing(self):
        """窗口关闭事件"""
        if messagebox.askokcancel("确认", "是否要退出程序？\n选择'最小化到托盘'可以继续在后台运行。"):
            self.quit_application()
        else:
            self.hide_to_tray()

    def quit_application(self):
        """退出应用程序"""
        try:
            # 解锁屏幕
            if self.is_locked:
                self.unlock_screen()
            
            # 确保移除鼠标边界限制
            self.remove_mouse_boundary()
            
            # 确保恢复鼠标指针
            if self.mouse_hidden:
                self.show_mouse_cursor()
            
            # 确保恢复亮度 - 只有在锁屏状态下才恢复保存的亮度
            if self.is_locked and self.original_brightness is not None:
                debug_print("🔄 程序退出时恢复保存的亮度...")
                self.restore_brightness()
            elif self.original_brightness is not None:
                debug_print("ℹ️ 程序退出时清除过期的亮度值")
                self.original_brightness = None
            
            # 启用键盘
            self.enable_keyboard()
            
            # 移除所有快捷键和钩子
            keyboard.unhook_all()
            
            # 移除备用钩子
            if hasattr(self, 'backup_hook') and self.backup_hook:
                keyboard.unhook(self.backup_hook)
            
            # 停止托盘图标
            if self.tray_icon:
                self.tray_icon.stop()
            
            # 关闭主窗口
            if self.main_window:
                self.main_window.destroy()
                
        except:
            pass
        finally:
            sys.exit()

    def run(self):
        """运行应用程序"""
        try:
            self.main_window.mainloop()
        except KeyboardInterrupt:
            self.quit_application()

    def get_current_brightness(self):
        """获取当前屏幕亮度 - 实时获取"""
        try:
            # 方法1：使用WMI获取当前亮度
            if self.brightness_control_available and self.brightness_monitor:
                try:
                    # 重新获取WMI对象以确保数据是最新的
                    current_monitor = self.wmi_connection.WmiMonitorBrightness()[0]
                    brightness = current_monitor.CurrentBrightness
                    debug_print(f"🔆 WMI获取当前亮度: {brightness}%")
                    return brightness
                except Exception as wmi_error:
                    debug_print(f"⚠ WMI获取亮度失败: {wmi_error}")
            
            # 方法2：使用PowerShell获取当前亮度
            try:
                powershell_cmd = """
                $brightness = (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness
                Write-Output $brightness
                """
                result = subprocess.run(["powershell", "-Command", powershell_cmd], 
                                      capture_output=True, check=True, text=True)
                brightness = int(result.stdout.strip())
                debug_print(f"🔆 PowerShell获取当前亮度: {brightness}%")
                return brightness
            except Exception as ps_error:
                debug_print(f"⚠ PowerShell获取亮度失败: {ps_error}")
            
            # 方法3：使用Windows注册表获取亮度
            try:
                import winreg
                key_path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0000"
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                    brightness, _ = winreg.QueryValueEx(key, "KMD_EnableBrightnessInterface2")
                    debug_print(f"🔆 注册表获取当前亮度: {brightness}%")
                    return brightness
            except Exception as reg_error:
                debug_print(f"⚠ 注册表获取亮度失败: {reg_error}")
            
            # 如果所有方法都失败，返回默认值
            debug_print("⚠ 无法获取当前亮度，使用默认值50%")
            return 50
            
        except Exception as e:
            debug_print(f"⚠ 获取亮度异常: {e}")
            return 50

    def set_brightness(self, brightness_level):
        """设置屏幕亮度 (0-100)"""
        try:
            brightness_level = max(0, min(100, int(brightness_level)))  # 确保在0-100范围内
            
            # 方法1：WMI设置亮度
            if self.brightness_control_available and self.brightness_methods:
                try:
                    self.brightness_methods.WmiSetBrightness(brightness_level, 0)
                    debug_print(f"✓ 亮度已设置为: {brightness_level}% (WMI)")
                    return True
                except Exception as wmi_error:
                    debug_print(f"⚠ WMI设置亮度失败: {wmi_error}")
            
            # 方法2：PowerShell命令
            if self.brightness_control_available:
                try:
                    powershell_cmd = f"""
                    Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods | 
                    Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{{Brightness={brightness_level}; Timeout=0}}
                    """
                    result = subprocess.run(["powershell", "-Command", powershell_cmd], 
                                          capture_output=True, check=True, text=True)
                    debug_print(f"✓ 亮度已设置为: {brightness_level}% (PowerShell CIM)")
                    return True
                except subprocess.CalledProcessError as ps_error:
                    debug_print(f"⚠ PowerShell CIM设置亮度失败: {ps_error}")
            
            # 方法3：nircmd工具（如果存在）
            if self.brightness_control_available:
                try:
                    result = subprocess.run(["nircmd", "setbrightness", str(brightness_level)], 
                                          capture_output=True, check=True)
                    debug_print(f"✓ 亮度已设置为: {brightness_level}% (nircmd)")
                    return True
                except (subprocess.CalledProcessError, FileNotFoundError):
                    debug_print("⚠ nircmd工具不可用")
            
            # 方法4：显示器调节API
            if self.brightness_control_available:
                try:
                    import win32api
                    import win32con
                    
                    # 尝试通过显示器API设置亮度
                    monitors = win32api.EnumDisplayMonitors()
                    for monitor in monitors:
                        monitor_info = win32api.GetMonitorInfo(monitor[0])
                        if monitor_info['Flags'] & win32con.MONITORINFOF_PRIMARY:
                            # 这是主显示器，尝试设置亮度
                            # 注意：这个方法在某些系统上可能不工作
                            debug_print(f"🔍 尝试通过显示器API设置亮度")
                            break
                except Exception as api_error:
                    debug_print(f"⚠ 显示器API设置失败: {api_error}")
            
            debug_print(f"❌ 所有亮度控制方法都失败")
            return False
            
        except Exception as e:
            debug_print(f"⚠ 设置亮度异常: {e}")
            return False

    def save_current_brightness(self):
        """保存当前亮度 - 动态获取最新亮度值"""
        try:
            # 动态获取当前亮度，而不是使用之前保存的值
            current_brightness = self.get_current_brightness()
            if current_brightness is not None:
                self.original_brightness = current_brightness
                debug_print(f"✓ 已保存当前亮度: {self.original_brightness}%")
                return True
            else:
                debug_print("⚠ 无法获取当前亮度")
                return False
        except Exception as e:
            debug_print(f"⚠ 保存亮度失败: {e}")
            return False

    def restore_brightness(self):
        """恢复原始亮度"""
        if not self.brightness_control_available:
            debug_print("ℹ️ 亮度控制不可用，跳过亮度恢复")
            return True
            
        try:
            if self.original_brightness is not None:
                debug_print(f"🔄 尝试恢复亮度到: {self.original_brightness}%")
                success = self.set_brightness(self.original_brightness)
                if success:
                    debug_print(f"✓ 已恢复原始亮度: {self.original_brightness}%")
                    # 清除保存的亮度值，确保下次锁屏时重新获取
                    self.original_brightness = None
                    debug_print("🔄 已清除保存的亮度值，下次将重新获取")
                    return True
                else:
                    debug_print(f"⚠ 恢复亮度失败，尝试备用方法...")
                    # 尝试备用方法
                    import time
                    time.sleep(0.3)
                    success = self.set_brightness(self.original_brightness)
                    if success:
                        debug_print(f"✓ 备用方法成功恢复亮度: {self.original_brightness}%")
                        self.original_brightness = None  # 清除保存值
                        return True
                    else:
                        debug_print(f"❌ 所有方法都无法恢复亮度，但程序继续运行")
                        self.original_brightness = None  # 清除无效的保存值
                        return False
            else:
                debug_print("⚠ 未找到保存的原始亮度值，使用默认值50%")
                success = self.set_brightness(50)
                if success:
                    debug_print("✓ 已设置默认亮度: 50%")
                    return True
                return False
        except Exception as e:
            debug_print(f"⚠ 恢复亮度异常: {e}")
            self.original_brightness = None  # 清除可能损坏的保存值
            return False

    def toggle_debug_mode(self, event=None):
        """切换调试模式"""
        global DEBUG_MODE
        DEBUG_MODE = not DEBUG_MODE
        
        if DEBUG_MODE:
            show_console()
            debug_print("🐛 调试模式已启用")
            debug_print("🖱️ 使用 Ctrl+Shift+M 可以强制恢复鼠标指针")
            messagebox.showinfo("调试模式", "调试模式已启用\n控制台窗口已显示\n\n快捷键说明：\nCtrl+Shift+M - 强制恢复鼠标")
        else:
            debug_print("🔇 调试模式已关闭")
            hide_console()
            messagebox.showinfo("调试模式", "调试模式已关闭\n控制台窗口已隐藏")

if __name__ == "__main__":
    # 无条件显示启动信息到一个临时文件（用于exe调试）
    import time
    startup_log = f"debug_startup_{int(time.time())}.txt"
    try:
        with open(startup_log, 'w', encoding='utf-8') as f:
            f.write(f"=== 假锁屏工具启动日志 ===\n")
            f.write(f"启动时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Python可执行文件: {sys.executable}\n")
            f.write(f"命令行参数: {sys.argv}\n")
            f.write(f"参数数量: {len(sys.argv)}\n")
            f.write(f"是否包含--debug: {'--debug' in sys.argv}\n")
            f.write(f"当前工作目录: {os.getcwd()}\n")
    except:
        pass
    
    # 首先显示所有命令行参数用于调试
    print(f"🔍 命令行参数: {sys.argv}")
    
    # 检查命令行参数是否包含调试模式
    if "--debug" in sys.argv:
        DEBUG_MODE = True
        print("🐛 检测到 --debug 参数，启用调试模式")
        try:
            with open(startup_log, 'a', encoding='utf-8') as f:
                f.write("✅ 调试模式已启用\n")
        except:
            pass
        debug_print("🐛 调试模式已启用")
        show_console()  # 立即显示控制台
        
        # 在调试模式下显示明确的信息
        print("=" * 60)
        print("🔧 假锁屏工具 - 调试模式")
        print("=" * 60)
        print(f"📍 当前工作目录: {os.getcwd()}")
        print(f"🔍 命令行参数: {sys.argv}")
        print(f"⚡ 调试模式已激活")
        print("=" * 60)
        
    else:
        print("📦 正常模式启动")
        try:
            with open(startup_log, 'a', encoding='utf-8') as f:
                f.write("📦 正常模式启动\n")
        except:
            pass
        # 隐藏控制台窗口（发布模式）
        hide_console()
    
    # 检查并请求管理员权限
    if not run_as_admin():
        # 程序已经以管理员身份重新启动，退出当前实例
        try:
            with open(startup_log, 'a', encoding='utf-8') as f:
                f.write("🔄 请求管理员权限后退出\n")
        except:
            pass
        sys.exit()
    
    # 显示权限状态
    if is_admin():
        debug_print("✓ 已获得管理员权限，程序功能完整")
        try:
            with open(startup_log, 'a', encoding='utf-8') as f:
                f.write("✅ 已获得管理员权限\n")
        except:
            pass
    else:
        debug_print("⚠ 未获得管理员权限，某些功能可能受限")
        try:
            with open(startup_log, 'a', encoding='utf-8') as f:
                f.write("⚠ 未获得管理员权限\n")
        except:
            pass
    
    try:
        app = FakeLockScreen()
        try:
            with open(startup_log, 'a', encoding='utf-8') as f:
                f.write("✅ 应用程序初始化完成\n")
        except:
            pass
        app.run()
    except Exception as e:
        # 在发布模式下，错误信息通过消息框显示
        error_msg = f"程序启动失败：{e}"
        try:
            with open(startup_log, 'a', encoding='utf-8') as f:
                f.write(f"❌ 启动失败: {error_msg}\n")
        except:
            pass
        if DEBUG_MODE:
            debug_print(error_msg)
        else:
            messagebox.showerror("启动错误", error_msg)
        sys.exit(1) 
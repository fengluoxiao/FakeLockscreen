import tkinter as tk
from tkinter import ttk, messagebox
import pystray
from PIL import Image, ImageDraw
import threading
import keyboard
import json
import os
import sys
import ctypes
import subprocess
import wmi

# 调试模式开关
DEBUG_MODE = False
# 全局日志文件变量
startup_log = None

# 单例模式实现
mutex_name = "FakeLockScreenSingletonMutex"
mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
last_error = ctypes.windll.kernel32.GetLastError()

if last_error == 183:  # ERROR_ALREADY_EXISTS
    messagebox.showerror("错误", "程序已经在运行，不能同时运行多个实例。")
    sys.exit(1)

def hide_console():
    """隐藏控制台窗口"""
    try:
        console_window = ctypes.windll.kernel32.GetConsoleWindow()
        if console_window != 0:
            ctypes.windll.user32.ShowWindow(console_window, 0)
    except:
        pass

def show_console():
    """显示控制台窗口"""
    try:
        console_window = ctypes.windll.kernel32.GetConsoleWindow()
        if console_window != 0:
            ctypes.windll.user32.ShowWindow(console_window, 1)
    except:
        pass

def debug_print(message):
    """调试输出，如果启用，则同时打印到控制台和日志文件"""
    if DEBUG_MODE:
        print(message)
        # 只有在startup_log被设置后才写入文件
        if startup_log:
            try:
                with open(startup_log, 'a', encoding='utf-8') as f:
                    f.write(message + "\n")
            except Exception as e:
                # 在这种情况下，只打印到控制台，避免无限循环
                print(f"!! 无法写入日志文件: {e}")

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
            debug_print("⚠ 需要管理员权限，正在重新启动...")
            
            # 准备参数
            args_list = sys.argv
            
            # 如果已有日志文件，将其作为参数传递
            if startup_log and os.path.exists(startup_log):
                args_list.append(f'--log-file="{startup_log}"')

            # 构建完整的命令行参数
            script_path = args_list[0]
            if ' ' in script_path:
                script_path = f'"{script_path}"'
            
            other_args = args_list[1:]
            args_str = ' '.join(other_args)
            
            full_cmd = f'{script_path} {args_str}'.strip()
            debug_print(f"🔄 启动命令: {sys.executable} {full_cmd}")
            
            result = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, full_cmd, None, 1
            )
            
            if result <= 32:
                debug_print(f"❌ 权限请求失败，返回值: {result}")
                messagebox.showerror("权限错误", "无法获取管理员权限，程序将继续运行但功能可能受限。")
                return True  # 继续运行但功能受限
            
            debug_print("✅ 权限请求成功，程序将重新启动")
            return False
    except Exception as e:
        debug_print(f"❌ 权限请求异常: {e}")
        messagebox.showerror("权限错误", f"无法获取管理员权限：{e}\n程序将继续运行但功能可能受限。")
        return True

class FakeLockScreen:
    def __init__(self):
        debug_print("🔧 初始化FakeLockScreen...")
        
        # --- 固定配置文件路径 ---
        self.user_config_dir = os.path.join(os.path.expanduser("~"), ".fakelockscreen")
        self.settings_file = os.path.join(self.user_config_dir, "lock_settings.json")
        debug_print(f"🔩 将始终使用此配置文件: {self.settings_file}")
        # --- 结束 ---

        self.unlock_key = "ctrl+alt+u"
        self.lock_key = "ctrl+alt+l"
        self.is_locked = False
        self.lock_window = None
        self.main_window = None
        self.tray_icon = None
        self.capturing_key = False
        self.keyboard_hook = None
        self.original_brightness = None
        self.mouse_hidden = False
        self.start_on_boot = False
        self.shortcut_name = "FakeLockScreen.lnk"
        
        debug_print("🔆 初始化WMI连接...")
        # 初始化WMI连接
        try:
            self.wmi_connection = wmi.WMI(namespace='wmi')
            self.brightness_methods = self.wmi_connection.WmiMonitorBrightnessMethods()[0]
            self.brightness_monitor = self.wmi_connection.WmiMonitorBrightness()[0]
            self.brightness_control_available = True
            debug_print("✅ WMI亮度控制初始化成功")
        except Exception as e:
            debug_print(f"⚠ WMI初始化失败: {e}")
            self.wmi_connection = None
            self.brightness_methods = None
            self.brightness_monitor = None
            self.brightness_control_available = False
        
        debug_print("📄 加载设置...")
        self.load_settings() # 恢复加载设置
        
        # 与文件系统上的快捷方式状态同步
        self.start_on_boot = self.is_startup_enabled()
        debug_print(f"💡 开机自启状态: {self.start_on_boot}")
        
        debug_print("🖥️ 创建主窗口...")
        self.create_main_window()
        
        debug_print("⌨️ 设置全局快捷键...")
        self.setup_global_hotkeys()
        
        debug_print("📱 创建系统托盘...")
        self.create_tray_icon()
        
        debug_print("✅ FakeLockScreen初始化完成")

    def get_startup_folder(self):
        """获取Windows启动文件夹路径"""
        return os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')

    def get_shortcut_path(self):
        """获取快捷方式的完整路径"""
        return os.path.join(self.get_startup_folder(), self.shortcut_name)

    def is_startup_enabled(self):
        """检查开机自启是否已启用（通过检查快捷方式是否存在）"""
        if os.name != 'nt':
            return False
        return os.path.exists(self.get_shortcut_path())

    def _manage_startup_shortcut(self, create=True):
        """使用PowerShell创建或删除启动快捷方式"""
        if os.name != 'nt':
            debug_print("ℹ️ 开机自启功能仅支持Windows。")
            return False

        shortcut_path = self.get_shortcut_path()

        if not create:
            if os.path.exists(shortcut_path):
                try:
                    os.remove(shortcut_path)
                    debug_print(f"✓ 已删除启动快捷方式: {shortcut_path}")
                    return True
                except Exception as e:
                    debug_print(f"❌ 删除快捷方式失败: {e}")
                    messagebox.showerror("错误", f"删除快捷方式失败: {e}")
                    return False
            return True # 不存在时，删除操作也视为成功

        # --- 创建快捷方式 ---
        # 确保启动目录存在
        startup_dir = self.get_startup_folder()
        if not os.path.exists(startup_dir):
            os.makedirs(startup_dir)

        pythonw_exe = sys.executable.replace("python.exe", "pythonw.exe")
        script_path = os.path.abspath(sys.argv[0])
        working_dir = os.path.dirname(script_path)

        ps_command = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{shortcut_path}')
$Shortcut.TargetPath = '{pythonw_exe}'
$Shortcut.Arguments = '"{script_path}"'
$Shortcut.WorkingDirectory = '{working_dir}'
$Shortcut.WindowStyle = 1
$Shortcut.IconLocation = '{pythonw_exe}, 0'
$Shortcut.Description = '启动假锁屏工具'
$Shortcut.Save()
"""
        try:
            subprocess.run(["powershell", "-Command", ps_command], check=True, capture_output=True, text=True, creationflags=0x08000000)
            debug_print(f"✓ 已创建启动快捷方式: {shortcut_path}")
            return True
        except subprocess.CalledProcessError as e:
            error_message = f"创建快捷方式失败: {e.stderr}"
            debug_print(f"❌ {error_message}")
            messagebox.showerror("错误", error_message)
            return False
        except FileNotFoundError:
            debug_print(f"❌ 创建快捷方式失败: PowerShell未找到。")
            messagebox.showerror("错误", "创建快捷方式失败: 未找到PowerShell, 请确保已安装。")
            return False

    def toggle_startup(self):
        """切换开机自启状态"""
        new_status = not self.start_on_boot
        success = self._manage_startup_shortcut(create=new_status)

        if success:
            self.start_on_boot = new_status
            self.save_settings()
            status_msg = "启用" if self.start_on_boot else "禁用"
            debug_print(f"🔄 开机自启已{status_msg}")
        else:
            # 如果操作失败，状态应恢复
            debug_print(f"❌ 开机自启状态切换失败，状态保持为: {self.start_on_boot}")
            messagebox.showwarning("操作失败", "无法更新开机自启设置，请检查程序是否以管理员权限运行。")

    def load_settings(self):
        """加载设置"""
        try:
            # 确保配置目录存在
            if not os.path.exists(self.user_config_dir):
                debug_print(f"ℹ️ 配置目录不存在，跳过加载。")
                return

            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.unlock_key = settings.get('unlock_key', 'ctrl+alt+u')
                    self.lock_key = settings.get('lock_key', 'ctrl+alt+l')
                    self.start_on_boot = settings.get('start_on_boot', False)
                debug_print(f"✓ 已从 '{self.settings_file}' 加载设置。")
            else:
                debug_print(f"ℹ️ 配置文件 '{self.settings_file}' 不存在，使用默认设置。")
        except Exception as e:
            debug_print(f"❌ 加载设置失败: {e}")

    def save_settings(self):
        """保存设置，并返回操作是否成功"""
        try:
            # 确保配置目录存在
            if not os.path.exists(self.user_config_dir):
                os.makedirs(self.user_config_dir)
                debug_print(f"✓ 已创建配置目录: {self.user_config_dir}")

            settings = {
                'unlock_key': self.unlock_key,
                'lock_key': self.lock_key,
                'start_on_boot': self.start_on_boot
            }
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            
            if os.name == 'nt':
                # 注意：隐藏文件夹内的文件不会在文件管理器中直接隐藏
                pass
            
            debug_print(f"✓ 配置文件 '{self.settings_file}' 已保存。")
            return True
        except Exception as e:
            debug_print(f"❌ 保存设置失败: {e}")
            messagebox.showerror("保存失败", f"无法保存设置文件 '{self.settings_file}'。\n\n错误: {e}")
            return False

    def create_main_window(self):
        """创建主窗口"""
        self.main_window = tk.Tk()
        self.main_window.title("假锁屏工具")
        self.main_window.geometry("550x400")
        self.main_window.resizable(False, False)
        
        # 设置窗口居中
        screen_width = self.main_window.winfo_screenwidth()
        screen_height = self.main_window.winfo_screenheight()
        x = (screen_width - 550) // 2
        y = (screen_height - 400) // 2
        self.main_window.geometry(f"550x400+{x}+{y}")
        
        # 创建主框架
        main_frame = ttk.Frame(self.main_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(main_frame, text="假锁屏工具", font=("微软雅黑", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # 说明文字
        description = """功能说明：
• 创建全屏黑色遮罩
• 禁用键盘输入（除解锁快捷键外）
• 隐藏鼠标指针
• 支持系统托盘运行

使用方法：
1. 点击"锁定屏幕"开始假锁屏
2. 使用设定的快捷键解锁"""
        
        desc_label = ttk.Label(main_frame, text=description, font=("微软雅黑", 10), justify=tk.LEFT)
        desc_label.pack(pady=(0, 20), anchor=tk.W)
        
        # 快捷键显示
        key_frame = ttk.Frame(main_frame)
        key_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(key_frame, text="解锁快捷键:", font=("微软雅黑", 10)).pack(side=tk.LEFT)
        self.unlock_key_label = ttk.Label(key_frame, text=self.unlock_key, font=("微软雅黑", 10, "bold"), foreground="blue")
        self.unlock_key_label.pack(side=tk.LEFT, padx=(10, 0))
        
        ttk.Label(key_frame, text="锁屏快捷键:", font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=(20, 0))
        self.lock_key_label = ttk.Label(key_frame, text=self.lock_key, font=("微软雅黑", 10, "bold"), foreground="green")
        self.lock_key_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=15)
        
        ttk.Button(button_frame, text="锁定屏幕", command=self.lock_screen, width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="设置解锁键", command=self.set_unlock_key, width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="设置锁屏键", command=self.set_lock_key, width=12).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="恢复默认", command=self.restore_default_keys, width=10).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="最小化到托盘", command=self.hide_to_tray, width=12).pack(side=tk.LEFT)
        
        # 状态栏
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(15, 0))
        
        self.status_label = ttk.Label(status_frame, text="就绪", font=("微软雅黑", 9))
        self.status_label.pack(side=tk.LEFT)
        
        # 权限状态
        admin_status = "管理员模式" if is_admin() else "普通模式"
        admin_color = "green" if is_admin() else "orange"
        admin_label = ttk.Label(status_frame, text=f"[{admin_status}]", font=("微软雅黑", 9), foreground=admin_color)
        admin_label.pack(side=tk.RIGHT)
        
        self.main_window.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_lock_window(self):
        """创建锁屏窗口"""
        self.lock_window = tk.Toplevel()
        self.lock_window.title("锁屏")
        self.lock_window.attributes('-fullscreen', True)
        self.lock_window.attributes('-topmost', True)
        self.lock_window.configure(bg='black')
        self.lock_window.overrideredirect(True)
        self.lock_window.config(cursor="none")
        
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
        
        self.lock_window.focus_force()
        self.lock_window.grab_set()

    def setup_global_hotkeys(self):
        """设置全局快捷键"""
        try:
            keyboard.remove_hotkey(self.unlock_key)
            keyboard.remove_hotkey(self.lock_key)
        except:
            pass
            
        try:
            keyboard.add_hotkey(self.unlock_key, self.unlock_screen, suppress=True)
            keyboard.add_hotkey(self.lock_key, self.lock_screen, suppress=True)
        except Exception as e:
            debug_print(f"设置快捷键失败: {e}")

    def enable_keyboard(self):
        """启用键盘输入"""
        try:
            keyboard.unhook_all()
            self.keyboard_hook = None
        except Exception as e:
            debug_print(f"启用键盘失败: {e}")

    def disable_keyboard(self):
        """禁用键盘输入"""
        try:
            keyboard.unhook_all()
            
            unlock_keys = self.unlock_key.lower().split('+')
            unlock_ctrl_needed = 'ctrl' in unlock_keys
            unlock_alt_needed = 'alt' in unlock_keys
            unlock_shift_needed = 'shift' in unlock_keys
            unlock_main_key = [k for k in unlock_keys if k not in ['ctrl', 'alt', 'shift']]
            unlock_main_key = unlock_main_key[0] if unlock_main_key else None
            
            def block_handler(event):
                if not self.is_locked:
                    return False
                
                if event.event_type == keyboard.KEY_DOWN and unlock_main_key and event.name == unlock_main_key:
                    ctrl_pressed = keyboard.is_pressed('ctrl')
                    alt_pressed = keyboard.is_pressed('alt')
                    shift_pressed = keyboard.is_pressed('shift')
                    
                    if (unlock_ctrl_needed == ctrl_pressed and 
                        unlock_alt_needed == alt_pressed and 
                        unlock_shift_needed == shift_pressed):
                        threading.Thread(target=self.unlock_screen, daemon=True).start()
                        return True
                
                return True
            
            self.keyboard_hook = keyboard.hook(block_handler, suppress=True)
            
        except Exception as e:
            debug_print(f"禁用键盘失败: {e}")

    def hide_mouse_cursor(self):
        """隐藏鼠标指针"""
        try:
            for _ in range(10):
                ctypes.windll.user32.ShowCursor(False)
            self.mouse_hidden = True
        except Exception as e:
            debug_print(f"隐藏鼠标失败: {e}")

    def show_mouse_cursor(self):
        """显示鼠标指针"""
        try:
            self.mouse_hidden = False
            # 持续调用ShowCursor(True)直到计数器恢复为非负数
            while ctypes.windll.user32.ShowCursor(True) < 0:
                pass
            debug_print("✅ 鼠标指针已强制显示")
        except Exception as e:
            debug_print(f"显示鼠标失败: {e}")

    def get_current_brightness(self):
        """获取当前屏幕亮度"""
        try:
            if self.brightness_control_available and self.brightness_monitor:
                # 重新获取WMI对象以确保数据是最新的
                current_monitor = self.wmi_connection.WmiMonitorBrightness()[0]
                brightness = current_monitor.CurrentBrightness
                debug_print(f"📊 当前亮度: {brightness}%")
                return brightness
        except Exception as e:
            debug_print(f"⚠ 获取亮度失败: {e}")
        return 50  # 默认亮度

    def set_brightness(self, brightness_level):
        """设置屏幕亮度"""
        try:
            brightness_level = max(0, min(100, int(brightness_level)))
            if self.brightness_control_available and self.brightness_methods:
                self.brightness_methods.WmiSetBrightness(brightness_level, 0)
                debug_print(f"💡 亮度已设置为: {brightness_level}%")
                return True
        except Exception as e:
            debug_print(f"⚠ 设置亮度失败: {e}")
        return False

    def save_current_brightness(self):
        """保存当前亮度"""
        try:
            current_brightness = self.get_current_brightness()
            if current_brightness is not None:
                self.original_brightness = current_brightness
                debug_print(f"💾 已保存当前亮度: {self.original_brightness}%")
                return True
            else:
                debug_print("⚠ 无法获取当前亮度")
                return False
        except Exception as e:
            debug_print(f"⚠ 保存亮度失败: {e}")
            return False

    def restore_brightness(self):
        """恢复原始亮度"""
        try:
            if self.brightness_control_available and self.original_brightness is not None:
                success = self.set_brightness(self.original_brightness)
                if success:
                    debug_print(f"🔆 已恢复原始亮度: {self.original_brightness}%")
                    self.original_brightness = None  # 清除保存的值
                    return True
                else:
                    debug_print("⚠ 恢复亮度失败")
                    return False
            else:
                debug_print("ℹ️ 无需恢复亮度")
                return True
        except Exception as e:
            debug_print(f"⚠ 恢复亮度异常: {e}")
            return False

    def lock_screen(self):
        """
        触发器：锁定屏幕。
        此方法是线程安全的，会将实际的锁定任务调度到主线程执行。
        """
        if self.is_locked:
            return
        # 将实际的锁定任务调度到Tkinter的主事件循环中
        self.main_window.after(0, self._perform_lock_tasks)

    def _perform_lock_tasks(self):
        """
        执行所有锁定任务。必须在主线程上运行。
        """
        if self.is_locked:
            return
            
        debug_print("🔒 开始锁定屏幕...")
        self.is_locked = True
        self.status_label.config(text="屏幕已锁定")
        
        if self.brightness_control_available:
            debug_print("🔅 调整屏幕亮度...")
            if self.save_current_brightness():
                self.set_brightness(0)
            else:
                debug_print("⚠ 亮度保存失败，跳过亮度调节")
        else:
            debug_print("ℹ️ 亮度控制不可用")
        
        debug_print("🖱️ 隐藏鼠标指针...")
        self.hide_mouse_cursor()
        
        if self.main_window:
            self.main_window.withdraw()
        
        debug_print("🖥️ 创建锁屏窗口...")
        self.create_lock_window()
        
        debug_print("⌨️ 禁用键盘输入...")
        self.disable_keyboard()
        
        debug_print("✅ 锁屏完成")

    def unlock_screen(self):
        """
        触发器：解锁屏幕。
        此方法是线程安全的，会将实际的解锁任务调度到主线程执行。
        """
        if not self.is_locked:
            return
        # 将实际的解锁任务调度到Tkinter的主事件循环中
        self.main_window.after(0, self._perform_unlock_tasks)

    def _perform_unlock_tasks(self):
        """
        执行所有解锁任务。必须在主线程上运行。
        """
        if not self.is_locked:
            return # 防止重复执行
            
        debug_print("🔓 开始解锁屏幕...")
        self.is_locked = False
        
        if self.brightness_control_available:
            debug_print("🔆 恢复屏幕亮度...")
            self.restore_brightness()
        
        debug_print("🖱️ 显示鼠标指针...")
        self.show_mouse_cursor()
        
        debug_print("⌨️ 启用键盘输入...")
        self.enable_keyboard()
        
        try:
            debug_print("🔄 正在重置Ctrl和Alt键状态...")
            keyboard.press_and_release('ctrl')
            keyboard.press_and_release('alt')
            debug_print("✅ Ctrl和Alt键状态已重置")
        except Exception as e:
            debug_print(f"⚠ 无法重置修饰键: {e}")
        
        debug_print("🔄 重新注册快捷键...")
        self.setup_global_hotkeys()
        
        if self.lock_window:
            try:
                self.lock_window.destroy()
                self.lock_window = None
                debug_print("🗑️ 锁屏窗口已销毁")
            except:
                pass
        
        if self.main_window and self.main_window.state() != 'withdrawn':
            try:
                self.main_window.deiconify()
                self.main_window.lift()
                self.status_label.config(text="屏幕已解锁")
                self.main_window.config(cursor="arrow")
                debug_print("🖥️ 主窗口已显示")
            except:
                pass
        else:
            self.status_label.config(text="屏幕已解锁")
        
        debug_print("✅ 解锁完成")

    def set_unlock_key(self):
        """设置解锁快捷键"""
        if self.capturing_key:
            return
            
        setting_window = tk.Toplevel(self.main_window)
        setting_window.title("设置解锁快捷键")
        setting_window.geometry("350x150")
        setting_window.resizable(False, False)
        setting_window.transient(self.main_window)
        setting_window.grab_set()
        
        # 居中
        x = (setting_window.winfo_screenwidth() - 350) // 2
        y = (setting_window.winfo_screenheight() - 150) // 2
        setting_window.geometry(f"350x150+{x}+{y}")
        
        frame = ttk.Frame(setting_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="请按下您想设置的快捷键组合", font=("微软雅黑", 12)).pack(pady=(0, 15))
        
        self.captured_key_var = tk.StringVar(value="等待按键...")
        key_display = ttk.Label(frame, textvariable=self.captured_key_var, font=("微软雅黑", 14, "bold"))
        key_display.pack(pady=(0, 15))
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        
        def save_key():
            if hasattr(self, 'new_unlock_key') and self.new_unlock_key:
                self.unlock_key = self.new_unlock_key
                self.unlock_key_label.config(text=self.unlock_key)
                self.save_settings()
                self.setup_global_hotkeys()
                self.capturing_key = False
                keyboard.unhook_all()
                self.setup_global_hotkeys()
                setting_window.destroy()
                messagebox.showinfo("成功", f"解锁快捷键已设置为: {self.unlock_key}")
            else:
                messagebox.showwarning("警告", "请先按下快捷键")
        
        def cancel():
            self.capturing_key = False
            keyboard.unhook_all()
            self.setup_global_hotkeys()
            setting_window.destroy()
        
        ttk.Button(btn_frame, text="保存", command=save_key).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="取消", command=cancel).pack(side=tk.LEFT)
        
        self.capturing_key = True
        self.new_unlock_key = None
        
        def on_key_event(event):
            if not self.capturing_key:
                return
                
            if event.name in ['ctrl', 'alt', 'shift', 'cmd']:
                return
                
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
            self.setup_global_hotkeys()
            setting_window.destroy()
            
        setting_window.protocol("WM_DELETE_WINDOW", on_window_close)

    def set_lock_key(self):
        """设置锁屏快捷键"""
        if self.capturing_key:
            return
            
        setting_window = tk.Toplevel(self.main_window)
        setting_window.title("设置锁屏快捷键")
        setting_window.geometry("350x150")
        setting_window.resizable(False, False)
        setting_window.transient(self.main_window)
        setting_window.grab_set()
        
        # 居中
        x = (setting_window.winfo_screenwidth() - 350) // 2
        y = (setting_window.winfo_screenheight() - 150) // 2
        setting_window.geometry(f"350x150+{x}+{y}")
        
        frame = ttk.Frame(setting_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="请按下您想设置的快捷键组合", font=("微软雅黑", 12)).pack(pady=(0, 15))
        
        self.captured_key_var = tk.StringVar(value="等待按键...")
        key_display = ttk.Label(frame, textvariable=self.captured_key_var, font=("微软雅黑", 14, "bold"))
        key_display.pack(pady=(0, 15))
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        
        def save_key():
            if hasattr(self, 'new_lock_key') and self.new_lock_key:
                self.lock_key = self.new_lock_key
                self.lock_key_label.config(text=self.lock_key)
                self.save_settings()
                self.setup_global_hotkeys()
                self.capturing_key = False
                keyboard.unhook_all()
                self.setup_global_hotkeys()
                setting_window.destroy()
                messagebox.showinfo("成功", f"锁屏快捷键已设置为: {self.lock_key}")
            else:
                messagebox.showwarning("警告", "请先按下快捷键")
        
        def cancel():
            self.capturing_key = False
            keyboard.unhook_all()
            self.setup_global_hotkeys()
            setting_window.destroy()
        
        ttk.Button(btn_frame, text="保存", command=save_key).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="取消", command=cancel).pack(side=tk.LEFT)
        
        self.capturing_key = True
        self.new_lock_key = None
        
        def on_key_event(event):
            if not self.capturing_key:
                return
                
            if event.name in ['ctrl', 'alt', 'shift', 'cmd']:
                return
                
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
            self.setup_global_hotkeys()
            setting_window.destroy()
            
        setting_window.protocol("WM_DELETE_WINDOW", on_window_close)

    def restore_default_keys(self):
        """恢复默认的快捷键设置"""
        if messagebox.askokcancel("确认", "您确定要将锁屏和解锁快捷键恢复为默认设置吗？"):
            # 默认快捷键
            default_unlock_key = "ctrl+alt+u"
            default_lock_key = "ctrl+alt+l"
            
            # 更新设置
            self.unlock_key = default_unlock_key
            self.lock_key = default_lock_key
            
            # 更新UI显示
            self.unlock_key_label.config(text=self.unlock_key)
            self.lock_key_label.config(text=self.lock_key)
            
            # 保存并重新注册快捷键
            if self.save_settings():
                self.setup_global_hotkeys()
                messagebox.showinfo("成功", "快捷键已恢复为默认设置并保存。")
                debug_print("✅ 快捷键已恢复为默认设置并保存")
            # 如果保存失败，save_settings内部会显示错误
        else:
            debug_print("ℹ️ 用户取消了恢复默认快捷键的操作")

    def create_tray_icon(self):
        """创建系统托盘图标"""
        def create_icon():
            image = Image.new('RGB', (64, 64), color='black')
            draw = ImageDraw.Draw(image)
            draw.ellipse([16, 16, 48, 48], fill='white')
            draw.ellipse([20, 20, 44, 44], fill='black')
            return image

        def show_window(icon, item):
            self.main_window.deiconify()
            self.main_window.lift()

        def lock_from_tray(icon, item):
            self.lock_screen()

        def toggle_startup_wrapper(icon, item):
            self.toggle_startup()

        def quit_app(icon, item):
            self.quit_application()

        menu = pystray.Menu(
            pystray.MenuItem("显示主窗口", show_window),
            pystray.MenuItem("锁定屏幕", lock_from_tray),
            pystray.MenuItem(
                "开机自启",
                toggle_startup_wrapper,
                checked=lambda item: self.start_on_boot
            ),
            pystray.MenuItem("退出", quit_app)
        )

        self.tray_icon = pystray.Icon("FakeLockScreen", create_icon(), "假锁屏工具", menu)
        
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
        if messagebox.askokcancel("确认", "是否要退出程序？"):
            self.quit_application()
        else:
            self.hide_to_tray()

    def quit_application(self):
        """退出应用程序"""
        try:
            if self.is_locked:
                self.unlock_screen()
            
            keyboard.unhook_all()
            
            if self.tray_icon:
                self.tray_icon.stop()
            
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

if __name__ == "__main__":
    # 不再需要 'global startup_log'，因为它已经在顶层定义了
    
    debug_print("🔍 程序启动中...")
    
    # 检查是否有传递过来的日志文件
    log_file_arg = [arg for arg in sys.argv if arg.startswith('--log-file=')]
    
    # 检查调试模式
    if "--debug" in sys.argv:
        DEBUG_MODE = True
        import time
        
        if log_file_arg:
            # 如果有日志文件参数，直接使用它
            startup_log = log_file_arg[0].split('=', 1)[1].strip('"')
            print(f"📝 接收并继续使用日志文件: {startup_log}")
        else:
            # 否则，创建新日志文件
            startup_log = f"debug_{time.strftime('%Y%m%d%H%M%S')}.txt"
            try:
                with open(startup_log, 'w', encoding='utf-8') as f:
                    f.write(f"=== 假锁屏工具启动日志 ===\n")
                    f.write(f"启动时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"命令行参数: {sys.argv}\n")
            except:
                pass
        show_console()
    else:
        hide_console()
    
    debug_print("🔐 检查管理员权限...")
    
    # 检查并请求管理员权限
    if not run_as_admin():
        debug_print("🔄 重新以管理员身份启动...")
        sys.exit()
    
    if is_admin():
        debug_print("✅ 管理员权限已获得")
    else:
        debug_print("⚠ 以普通权限运行，某些功能可能受限")
    
    try:
        debug_print("🚀 初始化应用程序...")
        app = FakeLockScreen()
        debug_print("✅ 应用程序初始化完成")
        debug_print("🎯 启动主循环...")
        app.run()
    except Exception as e:
        debug_print(f"❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()
        if DEBUG_MODE:
            debug_print(f"程序启动失败：{e}")
        else:
            messagebox.showerror("启动错误", f"程序启动失败：{e}")
        input("按回车键退出...")
        sys.exit(1) 
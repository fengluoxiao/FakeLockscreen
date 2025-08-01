# 假锁屏工具

一个轻量级的Python假锁屏应用，提供全屏黑色遮罩和核心的快捷键锁定功能。

## 功能特点

- ✅ **全屏黑色遮罩**：创建完全隐蔽的锁屏效果。
- ✅ **核心输入禁用**：锁屏时禁用鼠标指针和键盘输入（除解锁快捷键外）。
- ✅ **亮度控制**：锁屏时自动降低亮度，解锁时恢复。
- ✅ **系统托盘支持**：可最小化到系统托盘后台运行。
- ✅ **自定义快捷键**：可自由设置锁屏和解锁快捷键，并可恢复默认。
- ✅ **自动管理员权限**：程序会自动请求运行所需权限。
- ✅ **单例运行**：防止程序重复启动。
- ✅ **配置文件**：设置会自动保存在用户目录 (`~/.fakelockscreen/`) 下。

## 安装依赖

首先确保你已安装Python 3.7+，然后安装所需依赖：

```bash
pip install -r requirements.txt
```

## 运行程序

### 正常模式 (无控制台)
```bash
python fake_lock_screen.py
```

### 调试模式 (显示详细日志)
```bash
python fake_lock_screen.py --debug
```
在调试模式下，所有操作日志都会实时记录到程序目录下的 `debug_*.txt` 文件中。

## 使用方法

1.  **启动程序**：直接运行 `fake_lock_screen.py`。
2.  **锁定屏幕**：点击"锁定屏幕"按钮或使用锁屏快捷键（默认：`Ctrl+Alt+L`）。
3.  **解锁屏幕**：使用设定的快捷键解锁（默认：`Ctrl+Alt+U`）。
4.  **设置快捷键**：点击"设置锁屏键"或"设置解锁键"可自定义快捷键。
5.  **恢复默认**：点击"恢复默认"按钮，可一键还原快捷键设置。
6.  **托盘运行**：点击"最小化到托盘"可在后台运行。

## 默认快捷键

- **锁定屏幕**：`Ctrl+Alt+L`
- **解锁屏幕**：`Ctrl+Alt+U`

## 系统托盘功能

右键托盘图标可以：
- 显示主窗口
- 直接锁定屏幕
- 退出程序

## 文件说明

- `fake_lock_screen.py` - 主程序文件。
- `requirements.txt` - 依赖包列表。
- `lock_settings.json` - 配置文件（自动生成于用户目录）。
- `build_package/` - 存放打包相关脚本的文件夹。

## 故障排除

- **快捷键不响应**: 程序需要管理员权限才能全局监听快捷键，请允许UAC弹窗授权。
- **亮度控制不工作**: 该功能依赖Windows WMI服务，部分系统可能不兼容。

## 系统要求

- Windows 10/11
- Python 3.7+
- 需要管理员权限以获得完整功能。

## 打包与分发

项目包含完整的打包脚本，可以将程序打包成单个独立的 `.exe` 文件。

### 快速打包

1.  进入 `build_package` 目录。
2.  双击运行 `一键打包.bat`。
3.  根据提示选择打包模式：
    *   **标准模式**：生成的 `.exe` 文件较小，但需要在目标电脑上安装Python和相关依赖 (`requirements.txt`)。
    *   **依赖内置模式**：生成的 `.exe` 文件较大，但无需任何外部依赖，可在任何Windows电脑上独立运行。

### 打包输出

打包完成后，所有文件会输出到根目录下的 `dist` 文件夹中，可以直接将此文件夹分发给用户。

- **标准模式输出（不推荐）**：
  ```
  dist/
  ├── FakeLockScreen.exe
  ├── README.md
  └── requirements.txt  (需要和exe一起分发，且需要运行一次命令。)
  ```
- **依赖内置模式输出**：
  ```
  dist/
  ├── FakeLockScreen.exe (已包含所有依赖)
  └── README.md
  ``` 
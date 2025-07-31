# 假锁屏工具 - 打包说明

本目录包含将Python源码打包为exe可执行文件的完整解决方案。

## 📁 文件结构

```
build_package/
├── build_exe.py              # 自动化打包脚本（主要）
├── requirements_build.txt    # 打包依赖列表
├── 一键打包.bat              # 一键打包批处理
├── README_打包说明.md        # 本说明文件
└── fake_lock_screen.spec     # PyInstaller配置（自动生成）
```

## 🚀 快速开始

### 方法1：一键打包（推荐）
- **标准模式**：双击 `一键打包.bat`
- **依赖内置模式**：双击 `一键打包.bat`，然后按提示选择

### 方法2：手动执行
```bash
cd build_package

# 标准模式（需要目标机器有Python环境）
python build_exe.py

# 依赖内置模式（生成独立exe，无需Python环境）
python build_exe.py --collect-all
```

## 📋 两种打包模式

### 🔹 标准模式
- **命令**: `python build_exe.py`
- **特点**: 较小的exe文件，但需要目标机器有Python环境
- **适用**: 开发测试、有Python环境的机器

### 🔸 依赖内置模式
- **命令**: `python build_exe.py --collect-all`
- **特点**: 较大的exe文件，但完全独立运行
- **适用**: 最终分发、目标机器没有Python环境

## 📋 打包流程说明

自动化脚本执行以下步骤：

1. **环境检查** - 验证Python版本和源文件存在性
2. **依赖安装** - 自动安装PyInstaller等打包工具
3. **清理目录** - 清除之前的构建文件
4. **配置生成** - 创建优化的PyInstaller配置文件
5. **执行打包** - 使用PyInstaller打包为单文件exe
6. **文件复制** - 复制相关文档和脚本
7. **启动脚本** - 生成用户友好的启动脚本
8. **发布信息** - 生成发布说明文档
9. **结果验证** - 检查打包结果和文件完整性
10. **清理临时文件** - 自动删除build目录和临时配置文件

## 📦 输出结果

### 🔹 标准模式输出

```
dist/
├── 假锁屏工具.exe        # 主程序（较小，约5-10MB）
├── 发布说明.txt          # 发布信息和使用说明
├── README.md            # 详细使用文档
└── requirements.txt     # Python依赖列表（必需）
```

### 🔸 依赖内置模式输出

```
dist/
├── 假锁屏工具.exe        # 主程序（较大，约20-30MB，包含所有依赖）
├── 发布说明.txt          # 发布信息和使用说明
└── README.md            # 详细使用文档
```

**注意：** 依赖内置模式不会输出requirements.txt，因为所有依赖都已经内置到exe文件中。

## ⚙️ 打包配置说明

### 优化设置
- **单文件模式** - 所有依赖打包到一个exe文件
- **无控制台** - 发布版本隐藏控制台窗口
- **UPX压缩** - 减小文件体积
- **隐式导入** - 确保所有必要模块被包含

### 包含的模块
- `pystray` - 系统托盘功能
- `keyboard/mouse` - 键盘鼠标控制
- `WMI` - Windows管理接口
- `pywin32` - Windows API访问
- `tkinter` - GUI界面

### 排除的模块
- 大型科学计算库（numpy, scipy, pandas）
- 图形处理库（matplotlib）
- 不相关的GUI框架（PyQt）

## 🔧 故障排除

### 常见问题

**问题1：PyInstaller安装失败**
```bash
pip install --upgrade pip
pip install pyinstaller>=5.0
```

**问题2：打包时缺少模块**
- 检查 `requirements_build.txt` 中的依赖
- 手动安装缺失的包

**问题3：exe文件过大**
- 检查是否有不必要的依赖被包含
- 调整spec文件中的excludes列表

**问题4：运行时出错**
- 使用调试模式启动脚本查看详细错误
- 检查目标系统是否缺少VC++运行库

### 调试技巧

1. **查看详细日志**
   ```bash
   python build_exe.py
   ```

2. **手动执行PyInstaller**
   ```bash
   pyinstaller --onefile --noconsole fake_lock_screen.py
   ```

3. **测试打包结果**
   - 在不同Windows版本上测试
   - 检查杀毒软件是否误报
   - 验证所有功能是否正常

## 📋 系统要求

### 开发环境
- Python 3.7+
- Windows 10/11
- 管理员权限（推荐）

### 目标环境
- Windows 10/11
- 无需安装Python
- 会自动请求管理员权限

## 🎯 分发建议

1. **完整分发**：分发整个 `dist` 文件夹
2. **用户说明**：提供 `发布说明.txt` 给用户
3. **启动方式**：用户直接双击 `假锁屏工具.exe` 运行
4. **调试模式**：如需调试，在命令行运行 `假锁屏工具.exe --debug`
5. **安全提示**：提醒用户添加杀毒软件信任

## 📞 技术支持

如果遇到打包问题：
1. 检查本文档的故障排除部分
2. 确保所有依赖正确安装
3. 在不同环境中测试打包结果
4. 查看PyInstaller官方文档

---
最后更新：2024年 
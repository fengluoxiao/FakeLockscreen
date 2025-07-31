#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
假锁屏工具 - 自动化打包脚本
自动将Python程序打包为exe文件
"""

import os
import sys
import shutil
import subprocess
import time
from pathlib import Path

class ExeBuilder:
    def __init__(self):
        self.script_dir = Path(__file__).parent
        self.project_root = self.script_dir.parent
        self.source_file = self.project_root / "fake_lock_screen.py"
        self.dist_dir = self.project_root / "dist"
        self.build_dir = self.project_root / "build"
        self.spec_file = self.script_dir / "fake_lock_screen.spec"
        
        # 检查是否启用依赖收集
        self.collect_dependencies = "--collect-all" in sys.argv
        if self.collect_dependencies:
            print("🔧 检测到 --collect-all 参数，将完整打包所有依赖")
        else:
            print("📦 默认模式：不打包依赖（需要目标机器有Python环境）")
    
    def print_step(self, step_num, description):
        """打印步骤信息"""
        print(f"\n{'='*60}")
        print(f"步骤 {step_num}: {description}")
        print('='*60)
    
    def check_requirements(self):
        """检查环境要求"""
        self.print_step(1, "检查环境要求")
        
        # 检查Python版本
        python_version = sys.version_info
        print(f"Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}")
        if python_version < (3, 7):
            raise Exception("需要Python 3.7或更高版本")
        
        # 检查源文件是否存在
        if not self.source_file.exists():
            raise Exception(f"源文件不存在: {self.source_file}")
        print(f"✓ 源文件存在: {self.source_file}")
        
        # 检查PyInstaller
        try:
            result = subprocess.run([sys.executable, "-m", "pip", "show", "pyinstaller"], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                print("⚠ PyInstaller未安装，正在安装...")
                subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller>=5.0"], check=True)
            print("✓ PyInstaller已准备就绪")
        except Exception as e:
            raise Exception(f"PyInstaller检查失败: {e}")
    
    def install_dependencies(self):
        """安装打包依赖"""
        self.print_step(2, "安装打包依赖")
        
        requirements_file = self.script_dir / "requirements_build.txt"
        if requirements_file.exists():
            try:
                print("正在安装依赖包...")
                subprocess.run([
                    sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
                ], check=True)
                print("✓ 依赖包安装完成")
            except subprocess.CalledProcessError as e:
                print(f"⚠ 依赖安装失败: {e}")
                print("继续执行打包过程...")
        else:
            print("⚠ requirements_build.txt不存在，跳过依赖安装")
    
    def clean_build_dirs(self):
        """清理构建目录"""
        self.print_step(3, "清理构建目录")
        
        dirs_to_clean = [self.dist_dir, self.build_dir]
        for dir_path in dirs_to_clean:
            if dir_path.exists():
                print(f"删除目录: {dir_path}")
                shutil.rmtree(dir_path)
            print(f"✓ 已清理: {dir_path}")
    
    def create_spec_file(self):
        """创建PyInstaller配置文件"""
        self.print_step(4, "创建打包配置")
        
        # 基础隐式导入（总是包含的核心模块）
        base_hiddenimports = [
            'pystray._win32',
            'PIL._tkinter_finder',
            'wmi',
            'win32api',
            'win32con',
            'win32gui',
            'win32process',
            'win32security',
            'win32service',
            'win32event',
            'win32evtlog',
            'win32file',
            'win32pipe',
            'win32job',
            'pywintypes',
            'pythoncom',
            'keyboard._winkeyboard',
            'mouse._winmouse',
        ]
        
        additional_imports = []
        collect_data_packages = []
        collect_data_str = ""
        
        # 只有在启用依赖收集时才处理requirements.txt
        if self.collect_dependencies:
            requirements_file = self.project_root / "requirements.txt"
            
            if requirements_file.exists():
                print(f"📋 读取依赖文件: {requirements_file}")
                try:
                    with open(requirements_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                # 提取包名（去掉版本号）
                                package_name = line.split('>=')[0].split('==')[0].split('<')[0].split('>')[0]
                                
                                # 添加主包
                                additional_imports.append(package_name.lower())
                                collect_data_packages.append(package_name.lower())
                                print(f"  ✓ 将包含依赖: {package_name}")
                                
                                # 为特定包添加常用子模块
                                if package_name.lower() == 'pystray':
                                    additional_imports.extend([
                                        'pystray._base',
                                        'pystray._util',
                                        'pystray._win32',
                                    ])
                                elif package_name.lower() == 'pillow':
                                    additional_imports.extend([
                                        'PIL.Image',
                                        'PIL.ImageDraw',
                                        'PIL.ImageFont',
                                        'PIL._imaging',
                                        'PIL._tkinter_finder',
                                    ])
                                elif package_name.lower() == 'keyboard':
                                    additional_imports.extend([
                                        'keyboard._canonical_names',
                                        'keyboard._generic',
                                        'keyboard._winkeyboard',
                                    ])
                                elif package_name.lower() == 'mouse':
                                    additional_imports.extend([
                                        'mouse._generic',
                                        'mouse._winmouse',
                                    ])
                                elif package_name.lower() == 'wmi':
                                    additional_imports.extend([
                                        'wmi._wmi_object',
                                        'wmi._wmi_namespace',
                                    ])
                                elif package_name.lower() == 'pywin32':
                                    additional_imports.extend([
                                        'win32clipboard',
                                        'win32crypt',
                                        'win32net',
                                        'win32pdh',
                                        'win32ts',
                                        'win32wnet',
                                    ])
                                
                except Exception as e:
                    print(f"⚠ 读取requirements.txt失败: {e}")
            
            print(f"✓ 从requirements.txt解析出 {len(additional_imports)} 个模块")
            
            # 为requirements包生成collect_data配置
            if collect_data_packages:
                collect_data_str = f"""
# 导入collect_all函数
from PyInstaller.utils.hooks import collect_all

# 收集所有requirements.txt中的包数据
collected_data = []
collected_binaries = []
collected_hiddenimports = []

{chr(10).join(f"data, binaries, hiddenimports = collect_all('{pkg}')" for pkg in collect_data_packages)}
{chr(10).join(f"collected_data.extend(data or [])" for pkg in collect_data_packages)}
{chr(10).join(f"collected_binaries.extend(binaries or [])" for pkg in collect_data_packages)}
{chr(10).join(f"collected_hiddenimports.extend(hiddenimports or [])" for pkg in collect_data_packages)}
"""
        else:
            print("ℹ️ 跳过依赖收集，仅打包核心程序")
            # 默认模式下的空集合
            collect_data_str = """
# 默认模式：不收集额外依赖
collected_data = []
collected_binaries = []
collected_hiddenimports = []
"""
        
        # 组合所有隐式导入
        all_hiddenimports = base_hiddenimports + additional_imports
        
        # 去重
        all_hiddenimports = list(set(all_hiddenimports))
        
        # 生成hiddenimports字符串
        hiddenimports_str = ',\n        '.join([f"'{imp}'" for imp in all_hiddenimports])
        
        spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
{collect_data_str}
block_cipher = None

a = Analysis(
    ['{self.source_file.as_posix()}'],
    pathex=['{self.project_root.as_posix()}'],
    binaries=collected_binaries,
    datas=collected_data,
    hiddenimports=[
        {hiddenimports_str},
    ] + collected_hiddenimports,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'PyQt5',
        'PyQt6',
        'tkinter.test',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='FakeLockScreen',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加图标文件路径
    version_file=None,
)
'''
        
        with open(self.spec_file, 'w', encoding='utf-8') as f:
            f.write(spec_content)
        
        print(f"✓ 配置文件已创建: {self.spec_file}")
        print(f"✓ 包含 {len(all_hiddenimports)} 个隐式导入模块")
        if self.collect_dependencies:
            print(f"✓ 配置完整收集 {len(collect_data_packages)} 个依赖包")
        else:
            print("ℹ️ 未收集额外依赖包")

    def build_exe(self):
        """执行打包"""
        self.print_step(5, "开始打包")
        
        try:
            # 使用spec文件打包，不添加额外参数
            cmd = [
                sys.executable, "-m", "PyInstaller",
                "--clean",
                "--noconfirm",
                str(self.spec_file)
            ]
            
            print(f"执行命令: {' '.join(cmd)}")
            print("打包中，请稍候...")
            
            # 执行打包命令
            result = subprocess.run(cmd, cwd=self.project_root, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✓ 打包成功完成")
                if result.stdout:
                    print("构建输出:")
                    print(result.stdout[-1000:])  # 显示最后1000字符
            else:
                print("❌ 打包失败")
                print("错误输出:")
                print(result.stderr)
                if result.stdout:
                    print("标准输出:")
                    print(result.stdout)
                raise Exception("PyInstaller打包失败")
                
        except Exception as e:
            raise Exception(f"打包过程出错: {e}")
    
    def copy_additional_files(self):
        """复制附加文件"""
        self.print_step(6, "复制附加文件")
        
        if not self.dist_dir.exists():
            print("❌ dist目录不存在，打包可能失败")
            return
        
        # 要复制的文件列表
        files_to_copy = ["README.md"]
        
        # 如果没有收集依赖，则需要复制requirements.txt
        if not self.collect_dependencies:
            files_to_copy.append("requirements.txt")
            print("📋 将复制requirements.txt（因为依赖未内置）")
        else:
            print("ℹ️ 跳过requirements.txt复制（依赖已内置到exe中）")
        
        copied_count = 0
        for filename in files_to_copy:
            source_file = self.project_root / filename
            if source_file.exists():
                dest_file = self.dist_dir / filename
                shutil.copy2(source_file, dest_file)
                print(f"✓ 已复制: {filename}")
                copied_count += 1
            else:
                print(f"⚠ 文件不存在，跳过: {filename}")
        
        print(f"✓ 共复制 {copied_count} 个附加文件")
    
    def create_launcher_batch(self):
        """创建启动批处理文件"""
        self.print_step(7, "跳过启动脚本生成")
        print("ℹ️ 按用户要求，跳过生成bat启动脚本")
        print("ℹ️ 用户可直接双击exe文件运行程序")
    
    def generate_info_file(self):
        """生成发布信息文件"""
        self.print_step(8, "生成发布信息")
        
        if self.collect_dependencies:
            # 依赖内置模式的说明
            info_content = f'''# 假锁屏工具 - 发布包（依赖内置版）

## 构建信息
- 构建时间: {time.strftime('%Y-%m-%d %H:%M:%S')}
- Python版本: {sys.version}
- 构建平台: {sys.platform}
- 打包模式: 依赖内置（--collect-all）

## 文件说明
- `FakeLockScreen.exe` - 主程序文件（单文件，包含所有依赖）
- `README.md` - 使用说明文档

## 使用方法
1. 直接双击 `FakeLockScreen.exe` 运行程序
2. 程序会自动请求管理员权限
3. 如需调试模式，请在命令行中运行：`FakeLockScreen.exe --debug`

## 系统要求
- Windows 10/11
- 无需安装Python或任何依赖包
- 会自动请求管理员权限

## 内置依赖包
程序已内置以下所有依赖，无需单独安装：
- pystray - 系统托盘功能
- pillow - 图像处理
- keyboard - 键盘控制
- mouse - 鼠标控制  
- WMI - Windows管理接口
- pywin32 - Windows API访问

## 默认快捷键
- 锁屏: Ctrl+Alt+L
- 解锁: Ctrl+Alt+U
- 紧急恢复鼠标: Ctrl+Shift+M（调试模式下可用）

## 注意事项
- 首次运行可能被杀毒软件拦截，请添加信任
- 程序需要管理员权限以实现完整功能
- 建议关闭杀毒软件的实时保护后再运行
- 单文件exe包含所有依赖，可独立运行

---
自动生成于 {time.strftime('%Y-%m-%d %H:%M:%S')}
'''
        else:
            # 标准模式的说明
            info_content = f'''# 假锁屏工具 - 发布包（标准版）

## 构建信息
- 构建时间: {time.strftime('%Y-%m-%d %H:%M:%S')}
- Python版本: {sys.version}
- 构建平台: {sys.platform}
- 打包模式: 标准模式（需要Python环境）

## 文件说明
- `FakeLockScreen.exe` - 主程序文件
- `README.md` - 使用说明文档
- `requirements.txt` - Python依赖列表

## 使用方法
1. 确保目标机器已安装Python 3.7+
2. 安装依赖：`pip install -r requirements.txt`
3. 直接双击 `FakeLockScreen.exe` 运行程序
4. 程序会自动请求管理员权限
5. 如需调试模式，请在命令行中运行：`FakeLockScreen.exe --debug`

## 系统要求
- Windows 10/11
- Python 3.7+ 环境
- 安装requirements.txt中的依赖包
- 会自动请求管理员权限

## 依赖包列表
需要安装以下依赖（见requirements.txt）：
- pystray - 系统托盘功能
- pillow - 图像处理
- keyboard - 键盘控制
- mouse - 鼠标控制  
- WMI - Windows管理接口
- pywin32 - Windows API访问

## 默认快捷键
- 锁屏: Ctrl+Alt+L
- 解锁: Ctrl+Alt+U
- 紧急恢复鼠标: Ctrl+Shift+M（调试模式下可用）

## 注意事项
- 首次运行可能被杀毒软件拦截，请添加信任
- 程序需要管理员权限以实现完整功能
- 建议关闭杀毒软件的实时保护后再运行
- 目标机器需要有完整的Python环境和依赖

---
自动生成于 {time.strftime('%Y-%m-%d %H:%M:%S')}
'''
        
        info_file = self.dist_dir / "发布说明.txt"
        try:
            with open(info_file, 'w', encoding='utf-8') as f:
                f.write(info_content)
            print(f"✓ 已生成: {info_file.name}")
        except Exception as e:
            print(f"⚠ 生成发布信息失败: {e}")
    
    def cleanup_build_files(self):
        """清理构建完成后的临时文件"""
        print("\n🧹 清理构建临时文件...")
        
        # 清理build目录
        if self.build_dir.exists():
            try:
                shutil.rmtree(self.build_dir)
                print(f"✓ 已清理构建目录: {self.build_dir}")
            except Exception as e:
                print(f"⚠ 清理构建目录失败: {e}")
        
        # 清理spec文件（如果不需要保留）
        if self.spec_file.exists():
            try:
                self.spec_file.unlink()
                print(f"✓ 已清理配置文件: {self.spec_file}")
            except Exception as e:
                print(f"⚠ 清理配置文件失败: {e}")
        
        print("✅ 临时文件清理完成")

    def verify_build(self):
        """验证构建结果"""
        self.print_step(9, "验证构建结果")
        
        exe_file = self.dist_dir / "FakeLockScreen.exe"
        
        if exe_file.exists():
            file_size = exe_file.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            print(f"✓ EXE文件已生成: {exe_file}")
            print(f"✓ 文件大小: {file_size_mb:.2f} MB")
            
            # 列出dist目录中的所有文件
            print("\n📁 dist目录内容:")
            for item in sorted(self.dist_dir.iterdir()):
                if item.is_file():
                    size = item.stat().st_size
                    print(f"  📄 {item.name} ({size:,} bytes)")
                elif item.is_dir():
                    print(f"  📁 {item.name}/")
            
            return True
        else:
            print("❌ EXE文件未生成")
            return False
    
    def run(self):
        """执行完整的打包流程"""
        print("🚀 假锁屏工具 - 自动化打包程序")
        print(f"项目路径: {self.project_root}")
        
        try:
            self.check_requirements()
            self.install_dependencies()
            self.clean_build_dirs()
            self.create_spec_file()
            self.build_exe()
            self.copy_additional_files()
            self.create_launcher_batch()
            self.generate_info_file()
            
            if self.verify_build():
                self.print_step(10, "🎉 打包完成")
                print(f"✅ 构建成功完成！")
                print(f"📁 输出目录: {self.dist_dir}")
                print(f"🚀 主程序: {self.dist_dir / 'FakeLockScreen.exe'}")
                print(f"📋 发布说明: {self.dist_dir / '发布说明.txt'}")
                
                # 清理构建临时文件
                self.cleanup_build_files()
                
                if self.collect_dependencies:
                    print("\n🎯 依赖内置模式 - 下一步操作:")
                    print("1. 进入 dist 目录")
                    print("2. 直接双击 'FakeLockScreen.exe' 测试程序")
                    print("3. 可在任何Windows机器上运行（无需Python环境）")
                    print("4. 确认无误后即可分发整个 dist 文件夹")
                    print("5. 调试模式：FakeLockScreen.exe --debug")
                else:
                    print("\n🎯 标准模式 - 下一步操作:")
                    print("1. 进入 dist 目录")
                    print("2. 在有Python环境的机器上安装依赖：pip install -r requirements.txt")
                    print("3. 双击 'FakeLockScreen.exe' 测试程序")
                    print("4. 确认无误后分发 dist 文件夹（目标机器需要Python环境）")
                    print("5. 调试模式：FakeLockScreen.exe --debug")
                    print("\n💡 提示：如需生成无依赖的独立exe，请运行：python build_exe.py --collect-all")
            else:
                print("❌ 构建验证失败")
                return False
                
        except Exception as e:
            print(f"\n❌ 打包失败: {e}")
            print("\n🔧 故障排除建议:")
            print("1. 确保所有依赖包已正确安装")
            print("2. 检查Python版本是否为3.7+")
            print("3. 尝试手动安装PyInstaller: pip install pyinstaller")
            print("4. 检查是否有杀毒软件干扰")
            return False
        
        return True

if __name__ == "__main__":
    builder = ExeBuilder()
    success = builder.run()
    
    print("\n" + "="*60)
    if success:
        print("🎉 打包任务完成！")
    else:
        print("❌ 打包任务失败！")
    print("="*60)
    
    input("\n按回车键退出...") 
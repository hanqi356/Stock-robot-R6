#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨平台启动脚本
支持 Windows、macOS、Linux
"""

import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 设置跨平台环境
from platform_utils import setup_environment, PlatformInfo
setup_environment()


def check_dependencies():
    """检查依赖"""
    print("检查依赖...")
    
    required = ['tkinter', 'pandas', 'numpy', 'loguru']
    optional = ['easytrader', 'pytdx', 'czsc']
    
    missing = []
    
    for pkg in required:
        try:
            __import__(pkg)
            print(f"  [OK] {pkg}")
        except ImportError:
            print(f"  [MISSING] {pkg}")
            missing.append(pkg)
    
    for pkg in optional:
        try:
            __import__(pkg)
            print(f"  [OK] {pkg} (可选)")
        except ImportError:
            print(f"  [WARN] {pkg} (可选，未安装)")
    
    if missing:
        print(f"\n缺少必要依赖: {', '.join(missing)}")
        print("请运行: pip install " + " ".join(missing))
        return False
    
    return True


def main():
    """主函数"""
    plat = PlatformInfo.get_platform()
    
    print("=" * 60)
    print("量化交易系统 R6")
    print(f"平台: {plat}")
    print("=" * 60)
    
    # 检查依赖
    if not check_dependencies():
        input("\n按回车键退出...")
        return 1
    
    # 启动GUI
    print("\n启动GUI...")
    try:
        import tkinter as tk
        from stock_pro_gui import ProStockGUI
        
        root = tk.Tk()
        app = ProStockGUI(root)
        root.mainloop()
        
    except Exception as e:
        print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
        input("\n按回车键退出...")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

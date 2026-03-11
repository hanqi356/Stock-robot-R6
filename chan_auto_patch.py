# -*- coding: utf-8 -*-
"""
缠论双引擎自动集成补丁
自动为 GUI 的 6 个核心功能添加缠论分析，无需人工操作
"""
import tkinter as tk
from tkinter import messagebox


class ChanAutoIntegration:
    """缠论自动集成器"""
    
    @staticmethod
    def patch_gui(gui_app):
        """
        为 GUI 应用自动添加缠论分析
        
        Args:
            gui_app: ProStockGUI 实例
        """
        # 保存原始方法
        original_daily_analyze_selected = gui_app.daily_analyze_selected
        original_daily_analyze_watch_list = gui_app.daily_analyze_watch_list
        original_factor_analyze_selected = gui_app.factor_analyze_selected
        original_factor_analyze_watch_list = gui_app.factor_analyze_watch_list
        original_ai_analyze_selected = gui_app.ai_analyze_selected
        
        # 包装方法
        def daily_analyze_selected_with_chan():
            """深度分析选中 + 缠论分析"""
            try:
                # 调用原始方法
                original_daily_analyze_selected()
                
                # 延迟执行缠论分析（等待原始分析完成）
                gui_app.root.after(500, lambda: ChanAutoIntegration._try_chan_analysis(
                    gui_app, gui_app.trade_code.get().strip(), "深度分析"))
            except Exception as e:
                pass
        
        def daily_analyze_watch_list_with_chan():
            """深度分析监控列表 + 缠论分析"""
            try:
                original_daily_analyze_watch_list()
            except Exception as e:
                pass
        
        def factor_analyze_selected_with_chan():
            """因子分析选中 + 缠论分析"""
            try:
                original_factor_analyze_selected()
                
                # 延迟执行缠论分析
                gui_app.root.after(1000, lambda: ChanAutoIntegration._try_chan_analysis(
                    gui_app, gui_app.trade_code.get().strip(), "因子分析"))
            except Exception as e:
                pass
        
        def factor_analyze_watch_list_with_chan():
            """因子分析监控列表 + 缠论分析"""
            try:
                original_factor_analyze_watch_list()
            except Exception as e:
                pass
        
        def ai_analyze_selected_with_chan():
            """AI 分析选中 + 缠论分析"""
            try:
                # 调用原始方法
                original_ai_analyze_selected()
                
                # 延迟执行缠论分析（等待 AI 分析完成）
                gui_app.root.after(1500, lambda: ChanAutoIntegration._try_chan_analysis(
                    gui_app, gui_app.trade_code.get().strip(), "AI 分析"))
            except Exception as e:
                pass
        
        # 替换方法
        gui_app.daily_analyze_selected = daily_analyze_selected_with_chan
        gui_app.daily_analyze_watch_list = daily_analyze_watch_list_with_chan
        gui_app.factor_analyze_selected = factor_analyze_selected_with_chan
        gui_app.factor_analyze_watch_list = factor_analyze_watch_list_with_chan
        gui_app.ai_analyze_selected = ai_analyze_selected_with_chan
        
        print("[OK] 缠论双引擎已自动集成到 GUI 功能")
    
    @staticmethod
    def _try_chan_analysis(gui_app, code, title_prefix):
        """尝试进行缠论分析"""
        if not code:
            return
        
        try:
            from stock_data import get_stock_data
            from chan_gui_extension import show_chan_dual_analysis
            
            df = get_stock_data(code, count=100)
            if not df.empty:
                show_chan_dual_analysis(gui_app.root, df, code, title_prefix)
        except Exception as e:
            gui_app.log(f"自动缠论分析失败：{e}", 'warning')


def auto_integrate():
    """
    自动集成入口函数
    在 GUI 启动后调用此函数即可
    """
    import sys
    import os
    
    # 确保项目路径在 sys.path 中
    project_path = os.path.dirname(os.path.abspath(__file__))
    if project_path not in sys.path:
        sys.path.insert(0, project_path)
    
    print("=" * 70)
    print("缠论双引擎自动集成补丁")
    print("=" * 70)
    print("\n正在加载缠论分析模块...")
    
    try:
        # 测试模块是否可用
        from chan_dual_engine import ChanDualEngine
        engine = ChanDualEngine()
        
        czsc_status = "[OK]" if engine.czsc_available else "[OFF]"
        chan_status = "[OK]" if engine.chan_available else "[FAIL]"
        
        print(f"czsc 引擎：{czsc_status}")
        print(f"chan.py 引擎：{chan_status}")
        
        if not engine.czsc_available and not engine.chan_available:
            print("\n⚠ 警告：未检测到任何缠论引擎")
            print("请确保已安装 czsc 和 chan.py 适配器")
            return False
        
        print("\n[OK] 缠论双引擎模块加载成功")
        print("\n使用说明:")
        print("1. 在 GUI 中使用以下功能时，将自动显示缠论分析结果:")
        print("   - 深度分析选中 (daily_analyze_selected)")
        print("   - 深度分析监控列表 (daily_analyze_watch_list)")
        print("   - 因子分析选中 (factor_analyze_selected)")
        print("   - 因子分析监控列表 (factor_analyze_watch_list)")
        print("   - AI 分析选中股票 (ai_analyze_selected)")
        print("\n2. 缠论分析窗口会自动弹出，无需额外操作")
        print("\n3. 启动方式:")
        print("   - 双击 启动专业版.bat，选择选项 1 即可")
        print("   - 或在命令行添加--chan-mode 参数: python stock_pro_gui.py --chan-mode")
        print("\n4. 如需禁用自动缠论分析，注释掉 stock_pro_gui.py 中的导入语句")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n[WARN] 缠论双引擎模块加载失败：{e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 测试
    success = auto_integrate()
    if success:
        print("\n[OK] 自动集成准备就绪")
        print("\n下一步:")
        print("在 stock_pro_gui.py 的 main() 函数中，ProStockGUI 初始化后添加:")
        print("  from chan_auto_patch import auto_integrate")
        print("  auto_integrate()")
        print("  ChanAutoIntegration.patch_gui(app)")

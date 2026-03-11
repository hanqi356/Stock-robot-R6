# -*- coding: utf-8 -*-
"""
缠论双引擎分析 GUI 面板
独立模块，可在主 GUI 中调用
"""
import tkinter as tk
from tkinter import messagebox


class ChanDualPanel(tk.LabelFrame):
    """缠论双引擎分析面板组件"""
    
    def __init__(self, parent, gui_app, **kwargs):
        super().__init__(parent, text=" 缠论双引擎分析 (czsc + chan.py) ", **kwargs)
        self.gui_app = gui_app
        self.pack(fill='x', padx=5, pady=5)
        
        self._create_widgets()
    
    def _create_widgets(self):
        """创建组件"""
        # 说明文字
        tk.Label(self, text="双引擎互相验证，提高信号可靠性", 
                font=('微软雅黑', 9),
                bg=self.cget('bg'), fg='#94a3b8').pack(anchor='w', padx=10, pady=(5,0))
        
        # 按钮
        btn_frame = tk.Frame(self, bg=self.cget('bg'))
        btn_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Button(btn_frame, text="缠论分析选中", command=self._on_analyze_selected,
                 bg='#ec4899', fg='white', font=('微软雅黑', 10),
                 relief='flat', cursor='hand2').pack(side='left', fill='x', expand=True, padx=2)
        
        tk.Button(btn_frame, text="缠论分析监控列表", command=self._on_analyze_watch_list,
                 bg='#db2777', fg='white', font=('微软雅黑', 10),
                 relief='flat', cursor='hand2').pack(side='left', fill='x', expand=True, padx=2)
    
    def _on_analyze_selected(self):
        """分析选中股票"""
        try:
            # 从主 GUI 获取选中的股票
            selected = self.gui_app.position_tree.selection()
            if not selected:
                code = self.gui_app.trade_code.get().strip()
                if not code:
                    messagebox.showwarning("提示", "请先选择股票或输入股票代码")
                    return
            else:
                values = self.gui_app.position_tree.item(selected[0])['values']
                code = self.gui_app._format_stock_code(values[0])
            
            self.gui_app.log(f"开始缠论双引擎分析：{code}", 'info')
            
            # 获取数据并显示分析
            from stock_data import get_stock_data
            from chan_gui_extension import show_chan_dual_analysis
            
            df = get_stock_data(code, count=100)
            if df.empty:
                messagebox.showwarning("提示", f"无法获取 {code} 的历史数据")
                return
            
            show_chan_dual_analysis(self.gui_app.root, df, code, "缠论分析")
            
        except Exception as e:
            messagebox.showerror("错误", f"缠论分析失败：{e}")
    
    def _on_analyze_watch_list(self):
        """批量分析监控列表"""
        try:
            codes = []
            for i in range(self.gui_app.watch_listbox.size()):
                codes.append(self.gui_app.watch_listbox.get(i))
            
            if not codes:
                messagebox.showwarning("提示", "监控列表为空")
                return
            
            self.gui_app.log(f"开始批量缠论分析：{len(codes)}只股票", 'info')
            
            from stock_data import get_stock_data
            from chan_dual_engine import ChanDualEngine
            
            # 准备数据
            stock_dict = {}
            for code in codes:
                try:
                    df = get_stock_data(code, count=100)
                    if not df.empty:
                        stock_dict[code] = df
                except Exception as e:
                    self.gui_app.log(f"获取 {code} 数据失败：{e}", 'warning')
            
            if not stock_dict:
                messagebox.showwarning("提示", "无法获取任何股票数据")
                return
            
            # 批量分析
            engine = ChanDualEngine()
            results = engine.batch_analyze(stock_dict)
            report = engine.get_summary_report(results)
            
            # 显示汇总报告
            window = tk.Toplevel(self.gui_app.root)
            window.title("缠论双引擎批量分析汇总")
            window.geometry("800x600")
            window.configure(bg=self.gui_app.colors['bg'])
            
            tk.Label(window, text="缠论双引擎批量分析汇总", 
                    font=('微软雅黑', 16, 'bold'),
                    bg=self.gui_app.colors['bg'], 
                    fg=self.gui_app.colors['text_highlight']).pack(pady=10)
            
            text_widget = tk.Text(window, 
                                 font=('Consolas', 10),
                                 bg=self.gui_app.colors['bg_secondary'],
                                 fg=self.gui_app.colors['text'],
                                 relief='flat',
                                 wrap='word')
            text_widget.pack(fill='both', expand=True, padx=20, pady=10)
            
            scrollbar = tk.Scrollbar(window, command=text_widget.yview)
            scrollbar.pack(side='right', fill='y')
            text_widget.config(yscrollcommand=scrollbar.set)
            
            text_widget.insert('end', report)
            text_widget.config(state='disabled')
            
            tk.Button(window, text="关闭", command=window.destroy,
                     bg=self.gui_app.colors['accent'], fg='white',
                     font=('微软雅黑', 10), relief='flat',
                     cursor='hand2', width=10).pack(pady=5)
            
            self.gui_app.log(f"完成批量缠论分析，共{len(results)}只股票", 'info')
            
        except Exception as e:
            messagebox.showerror("错误", f"批量缠论分析失败：{e}")


def create_chan_dual_panel(parent, gui_app):
    """
    便捷函数：创建缠论双引擎面板
    
    Args:
        parent: 父容器
        gui_app: 主 GUI 应用实例
        
    Returns:
        ChanDualPanel 实例
    """
    return ChanDualPanel(parent, gui_app, 
                        font=('微软雅黑', 11, 'bold'),
                        bg=gui_app.colors['bg_secondary'], 
                        fg=gui_app.colors['text'],
                        relief='solid', borderwidth=1)


if __name__ == "__main__":
    # 测试
    root = tk.Tk()
    root.title("缠论双引擎面板测试")
    root.geometry("400x200")
    
    class MockGUI:
        def __init__(self):
            self.colors = {
                'bg': '#1e1e1e',
                'bg_secondary': '#2d2d2d',
                'text': '#ffffff',
                'text_highlight': '#00ff00',
                'accent': '#3b82f6'
            }
            # 修复：去掉 lambda 的 self 参数
            self.trade_code = type('obj', (object,), {'get': lambda: type('obj', (object,), {'strip': lambda: ''})()})()
            self.position_tree = type('obj', (object,), {'selection': lambda: []})()
            self.watch_listbox = type('obj', (object,), {'size': lambda: 0, 'get': lambda i: ''})()
            
        def log(self, msg, level):
            print(f"[LOG] {msg}")
        
        def _format_stock_code(self, code):
            return code
    
    mock_gui = MockGUI()
    panel = create_chan_dual_panel(root, mock_gui)
    
    root.mainloop()

# -*- coding: utf-8 -*-
"""
缠论双引擎分析 GUI 扩展
为 6 个核心功能提供缠论分析界面
"""
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime


class ChanDualAnalysisPopup:
    """缠论双引擎分析弹窗"""
    
    def __init__(self, parent, result, code, title="缠论双引擎分析"):
        self.parent = parent
        self.result = result
        self.code = code
        self.title = title
        
        self.window = tk.Toplevel(parent)
        self.window.title(f"{title} - {code}")
        self.window.geometry("900x700")
        self.window.configure(bg='#1e1e1e')
        
        self._create_ui()
    
    def _create_ui(self):
        """创建 UI"""
        # 标题
        tk.Label(self.window, text=self.title, 
                font=('微软雅黑', 16, 'bold'),
                bg='#1e1e1e', fg='#00ff00').pack(pady=10)
        
        # 滚动区域
        main_frame = tk.Frame(self.window, bg='#1e1e1e')
        main_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        text_widget = tk.Text(main_frame, 
                             font=('Consolas', 10),
                             bg='#2d2d2d',
                             fg='#ffffff',
                             relief='flat',
                             wrap='word')
        text_widget.pack(side='left', fill='both', expand=True)
        
        scrollbar = tk.Scrollbar(main_frame, command=text_widget.yview)
        scrollbar.pack(side='right', fill='y')
        text_widget.config(yscrollcommand=scrollbar.set)
        
        # 填充内容
        self._fill_content(text_widget)
        
        text_widget.config(state='disabled')
        
        # 关闭按钮
        tk.Button(self.window, text="关闭", command=self.window.destroy,
                 bg='#3c3c3c', fg='#ffffff', 
                 font=('微软雅黑', 10), relief='flat', 
                 cursor='hand2', width=15).pack(pady=10)
    
    def _fill_content(self, text_widget):
        """填充分析内容"""
        lines = []
        lines.append(f"股票代码：{self.code}")
        lines.append(f"分析时间：{self.result.get('timestamp', datetime.now()).strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 70)
        
        # czsc 引擎
        lines.append("\n【czsc 引擎】")
        czsc = self.result.get('czsc_analysis', {})
        if 'error' not in czsc:
            lines.append(f"  信号：{czsc.get('signal', 'N/A')}")
            lines.append(f"  评分：{czsc.get('total_score', 'N/A')}")
            lines.append(f"  笔数：{czsc.get('bi_count', 0)}")
            lines.append(f"  分型数：{czsc.get('fx_count', 0)}")
            lines.append(f"  笔方向：{czsc.get('bi_direction', 'N/A')}")
        else:
            lines.append(f"  错误：{czsc.get('error')}")
        
        # chan.py 引擎
        lines.append("\n【chan.py 引擎】")
        chan = self.result.get('chan_analysis', {})
        if 'error' not in chan:
            lines.append(f"  信号：{chan.get('signal', 'N/A')}")
            lines.append(f"  评分：{chan.get('score', 'N/A')}")
            lines.append(f"  笔数：{chan.get('bi_count', 0)}")
            lines.append(f"  段数：{chan.get('duan_count', 0)}")
            lines.append(f"  中枢数：{chan.get('zs_count', 0)}")
        else:
            lines.append(f"  错误：{chan.get('error')}")
        
        # 共识度
        lines.append("\n【双引擎共识】")
        consensus = self.result.get('consensus', {})
        lines.append(f"  信号一致：{'是' if consensus.get('signal_agreement') else '否'}")
        lines.append(f"  置信度：{consensus.get('confidence', 'N/A')}")
        
        # 最终建议
        lines.append(f"\n【最终建议】 {self.result.get('recommendation', 'NEUTRAL')}")
        lines.append("=" * 70)
        
        for line in lines:
            text_widget.insert('end', line + '\n')


def show_chan_dual_analysis(parent, df, code, title=""):
    """
    便捷函数：显示缠论双引擎分析结果
    
    Args:
        parent: 父窗口
        df: DataFrame 股票数据
        code: 股票代码
        title: 标题前缀
    """
    try:
        from chan_dual_engine import ChanDualEngine
        
        engine = ChanDualEngine()
        result = engine.analyze_stock(df, code)
        
        popup = ChanDualAnalysisPopup(parent, result, code, title)
        
        return True
    except Exception as e:
        messagebox.showerror("错误", f"缠论分析失败：{e}")
        return False


if __name__ == "__main__":
    # 测试
    root = tk.Tk()
    root.withdraw()
    
    # 模拟数据
    import pandas as pd
    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=100),
        'open': range(100, 200),
        'high': range(110, 210),
        'low': range(90, 190),
        'close': range(105, 205),
        'volume': [1000000] * 100
    })
    
    show_chan_dual_analysis(root, df, '600519', '测试')
    root.mainloop()

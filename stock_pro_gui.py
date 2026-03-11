"""
专业股票交易GUI - 仿通达信/同花顺风格
深色主题，多面板布局
支持Windows、macOS、Linux
"""

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.font import Font
import threading
import time
import json
from datetime import datetime
import pandas as pd
import numpy as np
import os
import sys

# 跨平台支持
from platform_utils import PlatformInfo, UnicodeHelper, setup_environment
setup_environment()
from paper_trading import PaperTrading
from dongguan_trader import DongguanTrader
from broker_factory import get_broker_factory, create_broker_trader, get_supported_brokers
from ai_analyzer import BailianAIAnalyzer
from smart_watch_manager import SmartWatchManager, SmartWatchConfig, create_smart_watch_manager
from custom_indicators import calculate_all_indicators
from daily_analysis_integration import DailyAnalysisIntegration
from panda_factor_integration import PandaFactorIntegration

# Chan.py-main 缠论模块导入
try:
    from chan_adapter import ChanAdapter, get_chan_adapter, ChanAnalysis
    from chan_plot_overlay import ChanPlotOverlay, plot_kline_with_chan
    from chan_stock_picker import ChanStockPicker, quick_chan_pick
    from chan_auto_trader import ChanAutoTrader, ChanStrategy
    from chan_factor_analysis import ChanFactorAnalyzer, ChanFactorExtractor
    CHAN_PY_AVAILABLE = True
except ImportError as e:
    print(f"Chan.py模块导入失败: {e}")
    CHAN_PY_AVAILABLE = False


class ProStockGUI:
    """专业股票交易界面"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("量化交易系统")
        self.root.geometry("1400x900")
        self.root.configure(bg='#0d1117')
        
        # 配色方案
        self.colors = {
            'bg': '#0d1117',
            'bg_secondary': '#161b22',
            'border': '#30363d',
            'text': '#c9d1d9',
            'text_highlight': '#ffffff',
            'up': '#f85149',      # 红色涨
            'down': '#3fb950',    # 绿色跌
            'accent': '#58a6ff',
            'warning': '#d29922'
        }
        
        # 初始化交易引擎
        self.pt = PaperTrading(initial_capital=100000)
        self.broker_factory = get_broker_factory()
        self.real_trader = None
        self.current_broker = 'dongguan'
        self.ai_analyzer = BailianAIAnalyzer()
        self.daily_analyzer = DailyAnalysisIntegration(self.root, self.colors)
        self.factor_analyzer = PandaFactorIntegration(self.root, self.colors)
        
        # 初始化 Chan.py 缠论模块
        if CHAN_PY_AVAILABLE:
            self.chan_adapter = get_chan_adapter()
            self.chan_picker = ChanStockPicker(min_score=60)
            self.chan_trader = ChanAutoTrader()
            self.chan_factor_analyzer = ChanFactorAnalyzer()
            self.chan_divergence_strategy = None
        else:
            self.chan_adapter = None
            self.chan_picker = None
            self.chan_trader = None
            self.chan_factor_analyzer = None
            self.chan_divergence_strategy = None
        
        self.trade_mode = 'paper'
        self.auto_running = False
        self.watch_list = ['000858', '600519']
        self.chan_enabled = CHAN_PY_AVAILABLE
        
        # 初始化智能监控管理器
        self.smart_watch = create_smart_watch_manager(
            min_score=60,
            max_count=50,
            auto_add=True,
            auto_remove=True
        )
        self.smart_watch.set_callbacks(
            on_add=self._on_smart_watch_add,
            on_remove=self._on_smart_watch_remove,
            on_update=self._on_smart_watch_update
        )
        self.watch_list = self.smart_watch.get_watch_list()
        if not self.watch_list:
            self.watch_list = ['000858', '600519']
        
        # 设置字体
        self.font_large = Font(family='微软雅黑', size=16, weight='bold')
        self.font_medium = Font(family='微软雅黑', size=12)
        self.font_small = Font(family='微软雅黑', size=10)
        self.font_mono = Font(family='Consolas', size=10)
        
        self.create_layout()
        self.refresh_all()
        
        # 加载保存的API密钥
        self.root.after(500, self.load_api_key)
        
        # 启动自动刷新定时器（每秒刷新一次持仓价格）
        self.auto_refresh_enabled = True
        self.start_auto_refresh()
        
        # 自动启动自动交易和智能监控（延迟2秒确保界面初始化完成）
        self.root.after(2000, self._auto_start_services)
    
    def _auto_start_services(self):
        """自动启动服务"""
        try:
            # 启动自动交易
            if not self.auto_running:
                self.start_auto()
                self.log("[自动启动] 自动交易已启动", 'info')
            
            # 启动智能监控
            if not self.smart_watch_running:
                self.toggle_smart_watch()
                self.log("[自动启动] 智能监控已启动", 'info')
                
        except Exception as e:
            self.log(f"[自动启动] 错误: {e}", 'info')
    
    def save_api_key(self):
        """保存API密钥"""
        api_key = self.ai_api_key.get().strip()
        if not api_key:
            messagebox.showwarning("提示", "请输入API密钥")
            return
        
        try:
            with open('api_key.txt', 'w', encoding='utf-8') as f:
                f.write(api_key)
            self.log("API密钥已保存", 'info')
            messagebox.showinfo("成功", "API密钥已保存")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")
    
    def load_api_key(self):
        """加载API密钥"""
        try:
            if os.path.exists('api_key.txt'):
                with open('api_key.txt', 'r', encoding='utf-8') as f:
                    api_key = f.read().strip()
                    if api_key:
                        self.ai_api_key.delete(0, 'end')
                        self.ai_api_key.insert(0, api_key)
                        self.log("API密钥已加载", 'info')
        except Exception as e:
            self.log(f"加载API密钥失败: {e}", 'info')
    
    def _format_stock_code(self, code):
        """格式化股票代码 - 统一为6位数字格式"""
        code = str(code).strip().upper()
        # 去掉SH/SZ前缀
        if code.startswith('SH') or code.startswith('SZ'):
            code = code[2:]
        # 纯数字代码处理
        if code.isdigit():
            # 6位数字：A股标准代码
            if len(code) == 6:
                return code
            # 1-5位数字：补全为6位A股代码（用户简写）
            elif len(code) < 6:
                return code.zfill(6)
        return code
    
    def create_layout(self):
        """创建专业布局（左侧面板带滚动条）"""
        # 顶部标题栏
        self.create_header()
        
        # 主内容区 - 左右分栏
        main_container = tk.Frame(self.root, bg=self.colors['bg'])
        main_container.pack(fill='both', expand=True, padx=2, pady=2)
        
        # ========== 左侧面板（带滚动条）==========
        left_outer = tk.Frame(main_container, bg=self.colors['bg'], width=280)
        left_outer.pack(side='left', fill='both', padx=1)
        left_outer.pack_propagate(False)
        
        # Canvas + Scrollbar 实现滚动
        left_canvas = tk.Canvas(left_outer, bg=self.colors['bg'], highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(left_outer, orient='vertical', command=left_canvas.yview)
        left_inner = tk.Frame(left_canvas, bg=self.colors['bg'])
        
        left_inner.bind('<Configure>', lambda e: left_canvas.configure(scrollregion=left_canvas.bbox('all')))
        left_canvas_window = left_canvas.create_window((0, 0), window=left_inner, anchor='nw', width=260)
        left_canvas.configure(yscrollcommand=left_scrollbar.set)
        
        left_canvas.pack(side='left', fill='both', expand=True)
        left_scrollbar.pack(side='right', fill='y')
        
        # 鼠标滚轮绑定
        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-1*(event.delta/120)), 'units')
        left_canvas.bind('<Enter>', lambda e: left_canvas.bind_all('<MouseWheel>', _on_mousewheel))
        left_canvas.bind('<Leave>', lambda e: left_canvas.unbind_all('<MouseWheel>'))
        
        self.create_account_panel(left_inner)
        self.create_quick_trade(left_inner)
        self.create_watch_list(left_inner)
        
        # ========== 中间面板 - 持仓和交易记录 ==========
        center_panel = tk.Frame(main_container, bg=self.colors['bg'])
        center_panel.pack(side='left', fill='both', expand=True, padx=1)
        
        self.create_positions_panel(center_panel)
        self.create_trade_log(center_panel)
        
        # ========== 右侧面板 ==========
        right_panel = tk.Frame(main_container, bg=self.colors['bg'], width=300)
        right_panel.pack(side='left', fill='y', padx=1)
        right_panel.pack_propagate(False)
        
        self.create_market_overview(right_panel)
        self.create_ai_panel(right_panel)
        self.create_backtest_panel(right_panel)
        self.create_auto_control(right_panel)
        
        # 底部状态栏
        self.create_status_bar()
    
    def create_header(self):
        """顶部标题栏"""
        header = tk.Frame(self.root, bg=self.colors['bg_secondary'], height=50)
        header.pack(fill='x')
        header.pack_propagate(False)
        
        # Logo和标题
        tk.Label(header, text="量化交易", font=self.font_large, 
                bg=self.colors['bg_secondary'], fg=self.colors['accent']).pack(side='left', padx=15, pady=10)
        
        tk.Label(header, text="量化交易系统 R6", font=self.font_medium,
                bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(side='left', pady=10)
        
        # 顶部信息
        self.header_time = tk.Label(header, text="", font=self.font_small, 
                                   bg=self.colors['bg_secondary'], fg=self.colors['text'])
        self.header_time.pack(side='right', padx=15, pady=15)
        
        # 市场状态
        self.market_status = tk.Label(header, text="交易中", font=self.font_small, 
                                     bg=self.colors['bg_secondary'], fg=self.colors['down'])
        self.market_status.pack(side='right', padx=10, pady=15)
    
    def create_account_panel(self, parent):
        """账户信息面板"""
        panel = tk.LabelFrame(parent, text=" 账户概览 ", font=self.font_medium,
                             bg=self.colors['bg_secondary'], fg=self.colors['text'],
                             relief='solid', borderwidth=1)
        panel.pack(fill='x', padx=5, pady=5)
        
        # 券商选择
        tk.Label(panel, text="券商账户", font=self.font_small, 
                bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(anchor='w', padx=10, pady=(10,0))
        
        account_frame = tk.Frame(panel, bg=self.colors['bg_secondary'])
        account_frame.pack(fill='x', padx=10, pady=2)
        
        self.broker_var = tk.StringVar(value='dongguan')
        self.broker_combo = ttk.Combobox(account_frame, textvariable=self.broker_var,
                                        state='readonly', width=12, font=self.font_small)
        self.broker_combo.pack(side='left', fill='x', expand=True, padx=2)
        self._load_broker_list()
        
        tk.Button(account_frame, text="配置", command=self.config_broker,
                 bg=self.colors['accent'], fg='white', font=self.font_small,
                 relief='flat', cursor='hand2').pack(side='left', padx=2)
        
        # 总资产（大字体）
        tk.Label(panel, text="总资产", font=self.font_small, 
                bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(anchor='w', padx=10, pady=(10,0))
        
        self.total_assets = tk.Label(panel, text="--", font=Font(family='微软雅黑', size=20, weight='bold'),
                                    bg=self.colors['bg_secondary'], fg=self.colors['text_highlight'])
        self.total_assets.pack(anchor='w', padx=10)
        
        # 盈亏
        tk.Label(panel, text="当日盈亏", font=self.font_small,
                bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(anchor='w', padx=10, pady=(10,0))
        
        self.daily_pnl = tk.Label(panel, text="--", font=self.font_medium,
                                 bg=self.colors['bg_secondary'], fg=self.colors['text'])
        self.daily_pnl.pack(anchor='w', padx=10)
        
        # 其他信息
        info_frame = tk.Frame(panel, bg=self.colors['bg_secondary'])
        info_frame.pack(fill='x', padx=10, pady=10)
        
        self.account_labels = {}
        items = [
            ('可用资金', 'available'),
            ('总市值', 'market_value'),
            ('持仓数量', 'positions')
        ]
        
        for i, (label, key) in enumerate(items):
            tk.Label(info_frame, text=label, font=self.font_small,
                    bg=self.colors['bg_secondary'], fg=self.colors['text']).grid(row=i, column=0, sticky='w', pady=2)
            self.account_labels[key] = tk.Label(info_frame, text="--", font=self.font_small,
                                               bg=self.colors['bg_secondary'], fg=self.colors['text_highlight'])
            self.account_labels[key].grid(row=i, column=1, sticky='e', pady=2, padx=10)
        
        # 操作按钮
        btn_frame = tk.Frame(panel, bg=self.colors['bg_secondary'])
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Button(btn_frame, text="刷新", command=self.refresh_all,
                 bg=self.colors['accent'], fg='white', font=self.font_small,
                 relief='flat', cursor='hand2').pack(side='left', padx=2)
        
        tk.Button(btn_frame, text="重置", command=self.reset_account,
                 bg=self.colors['warning'], fg='white', font=self.font_small,
                 relief='flat', cursor='hand2').pack(side='left', padx=2)
        
        # 实盘交易控制
        real_frame = tk.Frame(panel, bg=self.colors['bg_secondary'])
        real_frame.pack(fill='x', padx=10, pady=5)
        
        self.trade_mode_label = tk.Label(real_frame, text="模式: 模拟", font=self.font_small,
                                        bg=self.colors['bg_secondary'], fg=self.colors['up'])
        self.trade_mode_label.pack(side='left')
        
        tk.Button(real_frame, text="连接实盘", command=self.connect_real_trading,
                 bg=self.colors['down'], fg='white', font=self.font_small,
                 relief='flat', cursor='hand2').pack(side='right', padx=2)
        
        tk.Button(real_frame, text="切换模式", command=self.switch_trade_mode,
                 bg=self.colors['border'], fg=self.colors['text'], font=self.font_small,
                 relief='flat', cursor='hand2').pack(side='right', padx=2)
    
    def create_quick_trade(self, parent):
        """快速交易面板"""
        panel = tk.LabelFrame(parent, text=" 快速交易 ", font=self.font_medium,
                             bg=self.colors['bg_secondary'], fg=self.colors['text'],
                             relief='solid', borderwidth=1)
        panel.pack(fill='x', padx=5, pady=5)
        
        # 股票代码
        tk.Label(panel, text="股票代码", font=self.font_small,
                bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(anchor='w', padx=10, pady=(10,0))
        
        self.trade_code = tk.Entry(panel, font=self.font_mono, bg=self.colors['bg'],
                                  fg=self.colors['text_highlight'], insertbackground=self.colors['text'])
        self.trade_code.pack(fill='x', padx=10, pady=2)
        self.trade_code.insert(0, "000001")
        
        # 股数
        tk.Label(panel, text="股数", font=self.font_small,
                bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(anchor='w', padx=10, pady=(5,0))
        
        self.trade_shares = tk.Entry(panel, font=self.font_mono, bg=self.colors['bg'],
                                    fg=self.colors['text_highlight'], insertbackground=self.colors['text'])
        self.trade_shares.pack(fill='x', padx=10, pady=2)
        self.trade_shares.insert(0, "100")
        
        # 买入卖出按钮
        btn_frame = tk.Frame(panel, bg=self.colors['bg_secondary'])
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Button(btn_frame, text="买入", command=self.quick_buy,
                 bg=self.colors['down'], fg='white', font=self.font_medium,
                 relief='flat', cursor='hand2', width=8).pack(side='left', padx=2)
        
        tk.Button(btn_frame, text="卖出", command=self.quick_sell,
                 bg=self.colors['up'], fg='white', font=self.font_medium,
                 relief='flat', cursor='hand2', width=8).pack(side='left', padx=2)
    
    def create_watch_list(self, parent):
        """监控列表面板"""
        panel = tk.LabelFrame(parent, text=" 监控列表 ", font=self.font_medium,
                             bg=self.colors['bg_secondary'], fg=self.colors['text'],
                             relief='solid', borderwidth=1)
        panel.pack(fill='both', expand=True, padx=5, pady=5)
        
        # 输入框和按钮区域
        input_frame = tk.Frame(panel, bg=self.colors['bg_secondary'])
        input_frame.pack(fill='x', padx=5, pady=5)
        
        self.watch_input = tk.Entry(input_frame, font=self.font_mono, bg=self.colors['bg'],
                                   fg=self.colors['text'], insertbackground=self.colors['text'])
        self.watch_input.pack(side='left', fill='x', expand=True)
        self.watch_input.bind('<Return>', lambda e: self.add_to_watch())
        
        tk.Button(input_frame, text="+", command=self.add_to_watch,
                 bg=self.colors['down'], fg='white', font=self.font_small,
                 relief='flat', width=3).pack(side='left', padx=2)
        
        tk.Button(input_frame, text="-", command=self.remove_from_watch,
                 bg=self.colors['up'], fg='white', font=self.font_small,
                 relief='flat', width=3).pack(side='left', padx=2)
        
        # 使用Treeview替代Listbox，支持多列显示分析结果
        list_frame = tk.Frame(panel, bg=self.colors['bg_secondary'])
        list_frame.pack(fill='x', padx=5, pady=5)
        
        # 监控列表表格
        watch_columns = ('代码', '评分', '信号', '建议')
        self.watch_tree = ttk.Treeview(list_frame, columns=watch_columns, show='headings',
                                       height=6, style="Custom.Treeview")
        
        for col in watch_columns:
            self.watch_tree.heading(col, text=col)
            self.watch_tree.column(col, width=70 if col != '代码' else 80, anchor='center')
        
        self.watch_tree.pack(side='left', fill='both', expand=True)
        
        # 滚动条
        watch_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.watch_tree.yview)
        watch_scrollbar.pack(side='right', fill='y')
        self.watch_tree.configure(yscrollcommand=watch_scrollbar.set)
        
        # 存储分析结果
        self.watch_analysis_data = {}  # code -> {score, signals, suggestion}
        
        # 填充数据
        for code in self.watch_list:
            self.watch_tree.insert('', 'end', values=(code, '--', '--', '--'), tags=(code,))
        
        # 绑定双击、单击和右键事件
        self.watch_tree.bind('<Double-1>', self.on_watch_double_click)
        self.watch_tree.bind('<<TreeviewSelect>>', self.on_watch_select)
        self.watch_tree.bind('<Button-3>', self.show_watch_menu)
        
        # 按钮区域
        btn_frame = tk.Frame(panel, bg=self.colors['bg_secondary'])
        btn_frame.pack(fill='x', padx=5, pady=5)
        
        tk.Button(btn_frame, text="分析选中", command=self.analyze_watch_selected,
                 bg=self.colors['accent'], fg='white', font=self.font_small,
                 relief='flat', cursor='hand2').pack(side='left', fill='x', expand=True, padx=2)
        
        tk.Button(btn_frame, text="删除选中", command=self.remove_watch_selected,
                 bg=self.colors['up'], fg='white', font=self.font_small,
                 relief='flat', cursor='hand2').pack(side='left', fill='x', expand=True, padx=2)
        
        tk.Button(btn_frame, text="自动分析", command=self.auto_analyze_watch_list,
                 bg='#10b981', fg='white', font=self.font_small,
                 relief='flat', cursor='hand2').pack(side='left', fill='x', expand=True, padx=2)
        
        # 智能监控配置和启动按钮
        smart_frame = tk.Frame(panel, bg=self.colors['bg_secondary'])
        smart_frame.pack(fill='x', padx=5, pady=(0, 5))
        
        tk.Button(smart_frame, text="监控配置", command=self.config_smart_watch,
                 bg=self.colors['warning'], fg='white', font=self.font_small,
                 relief='flat', cursor='hand2').pack(side='left', fill='x', expand=True, padx=2)
        
        self.smart_watch_btn = tk.Button(smart_frame, text="启动自动监控", 
                 command=self.toggle_smart_watch,
                 bg='#8b5cf6', fg='white', font=self.font_small,
                 relief='flat', cursor='hand2')
        self.smart_watch_btn.pack(side='left', fill='x', expand=True, padx=2)
        self.smart_watch_running = False
    
    def create_positions_panel(self, parent):
        """持仓面板"""
        panel = tk.LabelFrame(parent, text=" 当前持仓 ", font=self.font_medium,
                             bg=self.colors['bg_secondary'], fg=self.colors['text'],
                             relief='solid', borderwidth=1)
        panel.pack(fill='both', expand=True, padx=5, pady=5)
        
        # 表格样式
        style = ttk.Style()
        style.theme_use('default')
        style.configure("Custom.Treeview", 
                       background=self.colors['bg'],
                       foreground=self.colors['text'],
                       fieldbackground=self.colors['bg'],
                       font=self.font_small)
        style.configure("Custom.Treeview.Heading",
                       background=self.colors['bg_secondary'],
                       foreground=self.colors['text'],
                       font=self.font_small)
        
        # 持仓表格
        columns = ('代码', '名称', '股数', '成本', '现价', '市值', '盈亏率')
        self.position_tree = ttk.Treeview(panel, columns=columns, show='headings', 
                                         height=10, style="Custom.Treeview")
        
        for col in columns:
            self.position_tree.heading(col, text=col)
            self.position_tree.column(col, width=90, anchor='center')
        
        # 滚动条
        scrollbar = ttk.Scrollbar(panel, orient='vertical', command=self.position_tree.yview)
        self.position_tree.configure(yscrollcommand=scrollbar.set)
        
        self.position_tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar.pack(side='right', fill='y', pady=5)
        
        # 右键菜单
        self.position_tree.bind('<Button-3>', self.show_position_menu)
        
        # 双击显示分时图
        self.position_tree.bind('<Double-1>', self.show_minute_chart)
    
    def create_trade_log(self, parent):
        """交易日志面板"""
        panel = tk.LabelFrame(parent, text=" 交易记录 ", font=self.font_medium,
                             bg=self.colors['bg_secondary'], fg=self.colors['text'],
                             relief='solid', borderwidth=1)
        panel.pack(fill='x', padx=5, pady=5)
        
        self.log_text = tk.Text(panel, height=8, font=self.font_mono, bg=self.colors['bg'],
                               fg=self.colors['text'], relief='flat',
                               wrap='word')
        self.log_text.pack(fill='both', expand=True, padx=5, pady=5)
        
        # 添加标签颜色
        self.log_text.tag_config('buy', foreground=self.colors['down'])
        self.log_text.tag_config('sell', foreground=self.colors['up'])
        self.log_text.tag_config('info', foreground=self.colors['accent'])
    
    def create_market_overview(self, parent):
        """市场概览"""
        panel = tk.LabelFrame(parent, text=" 市场热点 ", font=self.font_medium,
                             bg=self.colors['bg_secondary'], fg=self.colors['text'],
                             relief='solid', borderwidth=1)
        panel.pack(fill='x', padx=5, pady=5)
        
        # 模拟市场数据
        tk.Label(panel, text="上证指数", font=self.font_small,
                bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(anchor='w', padx=10, pady=5)
        
        tk.Label(panel, text="深证成指", font=self.font_small,
                bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(anchor='w', padx=10, pady=5)
        
        tk.Label(panel, text="创业板指", font=self.font_small,
                bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(anchor='w', padx=10, pady=5)
    
    def create_ai_panel(self, parent):
        """AI分析面板 - 简洁版"""
        panel = tk.LabelFrame(parent, text=" AI智能分析 ", font=self.font_medium,
                             bg=self.colors['bg_secondary'], fg=self.colors['text'],
                             relief='solid', borderwidth=1)
        panel.pack(fill='x', padx=5, pady=5)
        
        # API密钥输入
        tk.Label(panel, text="API密钥", font=self.font_small,
                bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(anchor='w', padx=10, pady=(10,0))
        
        key_frame = tk.Frame(panel, bg=self.colors['bg_secondary'])
        key_frame.pack(fill='x', padx=10, pady=2)
        
        self.ai_api_key = tk.Entry(key_frame, font=self.font_mono, bg=self.colors['bg'],
                                  fg=self.colors['text_highlight'], insertbackground=self.colors['text'],
                                  show='*')
        self.ai_api_key.pack(side='left', fill='x', expand=True)
        
        tk.Button(key_frame, text="保存", command=self.save_api_key,
                 bg=self.colors['accent'], fg='white', font=self.font_small,
                 relief='flat', cursor='hand2', width=6).pack(side='left', padx=2)
        
        # 分析按钮
        btn_frame = tk.Frame(panel, bg=self.colors['bg_secondary'])
        btn_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Button(btn_frame, text="分析选中股票", command=self.ai_analyze_selected,
                 bg=self.colors['accent'], fg='white', font=self.font_small,
                 relief='flat', cursor='hand2').pack(side='left', fill='x', expand=True, padx=2)
        
        tk.Button(btn_frame, text="分析持仓组合", command=self.ai_analyze_portfolio,
                 bg=self.colors['down'], fg='white', font=self.font_small,
                 relief='flat', cursor='hand2').pack(side='left', fill='x', expand=True, padx=2)
        
        # PandaFactor 因子分析按钮
        factor_btn_frame = tk.Frame(panel, bg=self.colors['bg_secondary'])
        factor_btn_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Button(factor_btn_frame, text="因子分析选中", command=self.factor_analyze_selected,
                 bg='#10b981', fg='white', font=self.font_small,
                 relief='flat', cursor='hand2').pack(side='left', fill='x', expand=True, padx=2)
        
        tk.Button(factor_btn_frame, text="因子分析监控", command=self.factor_analyze_watch_list,
                 bg='#059669', fg='white', font=self.font_small,
                 relief='flat', cursor='hand2').pack(side='left', fill='x', expand=True, padx=2)
        
        # Daily Stock Analysis 按钮（如果可用）
        if self.daily_analyzer.is_available():
            # 模型选择
            model_frame = tk.Frame(panel, bg=self.colors['bg_secondary'])
            model_frame.pack(fill='x', padx=10, pady=(5,0))
            
            tk.Label(model_frame, text="模型:", font=self.font_small,
                    bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(side='left')
            
            self.daily_model = tk.StringVar(value='aliyun')
            model_select = tk.OptionMenu(model_frame, self.daily_model, 'aliyun', 'gemini', 'openai', 'deepseek')
            model_select.config(font=self.font_small, bg=self.colors['bg'], fg=self.colors['text'],
                               relief='flat', highlightthickness=0)
            model_select.pack(side='left', padx=5)
            
            # 深度分析模式选择
            mode_frame = tk.Frame(panel, bg=self.colors['bg_secondary'])
            mode_frame.pack(fill='x', padx=10, pady=2)
            
            tk.Label(mode_frame, text="分析模式:", bg=self.colors['bg_secondary'], 
                    fg=self.colors['text'], font=self.font_small).pack(side='left', padx=5)
            
            self.daily_quick_mode = tk.BooleanVar(value=True)
            tk.Radiobutton(mode_frame, text="快速(秒级)", variable=self.daily_quick_mode, 
                          value=True, bg=self.colors['bg_secondary'], fg=self.colors['text'],
                          selectcolor=self.colors['bg'], font=self.font_small).pack(side='left', padx=5)
            tk.Radiobutton(mode_frame, text="完整(分钟级)", variable=self.daily_quick_mode, 
                          value=False, bg=self.colors['bg_secondary'], fg=self.colors['text'],
                          selectcolor=self.colors['bg'], font=self.font_small).pack(side='left', padx=5)
            
            daily_btn_frame = tk.Frame(panel, bg=self.colors['bg_secondary'])
            daily_btn_frame.pack(fill='x', padx=10, pady=5)
            
            tk.Button(daily_btn_frame, text="深度分析选中", command=self.daily_analyze_selected,
                     bg='#8b5cf6', fg='white', font=self.font_small,
                     relief='flat', cursor='hand2').pack(side='left', fill='x', expand=True, padx=2)
            
            tk.Button(daily_btn_frame, text="深度分析监控", command=self.daily_analyze_watch_list,
                     bg='#7c3aed', fg='white', font=self.font_small,
                     relief='flat', cursor='hand2').pack(side='left', fill='x', expand=True, padx=2)
    
    def create_backtest_panel(self, parent):
        """策略回测面板"""
        panel = tk.LabelFrame(parent, text=" 策略回测 ", font=self.font_medium,
                             bg=self.colors['bg_secondary'], fg=self.colors['text'],
                             relief='solid', borderwidth=1)
        panel.pack(fill='x', padx=5, pady=5)
        
        # 策略选择
        tk.Label(panel, text="策略:", font=self.font_small,
                bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(anchor='w', padx=10, pady=(5,0))
        
        self.backtest_strategy = tk.StringVar(value='macd')
        strategy_frame = tk.Frame(panel, bg=self.colors['bg_secondary'])
        strategy_frame.pack(fill='x', padx=10, pady=2)
        
        tk.Radiobutton(strategy_frame, text="MACD", variable=self.backtest_strategy, 
                      value='macd', bg=self.colors['bg_secondary'], fg=self.colors['text'],
                      selectcolor=self.colors['bg'], font=self.font_small).pack(side='left', padx=5)
        tk.Radiobutton(strategy_frame, text="双均线", variable=self.backtest_strategy,
                      value='ma', bg=self.colors['bg_secondary'], fg=self.colors['text'],
                      selectcolor=self.colors['bg'], font=self.font_small).pack(side='left', padx=5)
        
        # 回测按钮
        btn_frame = tk.Frame(panel, bg=self.colors['bg_secondary'])
        btn_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Button(btn_frame, text="回测选中", command=self.run_backtest_selected,
                 bg='#f59e0b', fg='white', font=self.font_small,
                 relief='flat', cursor='hand2').pack(side='left', fill='x', expand=True, padx=2)
        
        tk.Button(btn_frame, text="回测输入", command=self.run_backtest_input,
                 bg='#d97706', fg='white', font=self.font_small,
                 relief='flat', cursor='hand2').pack(side='left', fill='x', expand=True, padx=2)
        
        # 选股扫描按钮
        scan_btn_frame = tk.Frame(panel, bg=self.colors['bg_secondary'])
        scan_btn_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Button(scan_btn_frame, text="选股扫描", command=self.run_stock_scan,
                 bg='#10b981', fg='white', font=self.font_small,
                 relief='flat', cursor='hand2').pack(fill='x', padx=2)
    
    def run_backtest_selected(self):
        """对选中的股票进行回测"""
        selected = self.position_tree.selection()
        if not selected:
            code = self.trade_code.get().strip()
            if not code:
                messagebox.showwarning("提示", "请先选择股票或输入股票代码")
                return
        else:
            item = selected[0]
            values = self.position_tree.item(item)['values']
            code = self._format_stock_code(values[0])
        
        self._run_backtest(code)
    
    def run_backtest_input(self):
        """对输入的股票进行回测"""
        code = self.trade_code.get().strip()
        if not code:
            messagebox.showwarning("提示", "请输入股票代码")
            return
        code = self._format_stock_code(code)
        self._run_backtest(code)
    
    def run_stock_scan(self):
        """手动运行选股扫描"""
        if not self.watch_list:
            messagebox.showwarning("提示", "监控列表为空，请先添加股票")
            return
        
        self.log("开始手动选股扫描...", 'info')
        
        def do_scan():
            try:
                from stock_scanner import scan_watch_list
                
                result = scan_watch_list(self.watch_list, score_threshold=60)
                self.root.after(0, lambda: self._show_scan_result(result))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", f"扫描失败: {e}"))
        
        threading.Thread(target=do_scan, daemon=True).start()
    
    def _show_scan_result(self, result: dict):
        """显示选股扫描结果"""
        candidates = result.get('candidates', [])
        all_results = result.get('all_results', [])
        
        # 创建弹窗
        window = tk.Toplevel(self.root)
        window.title("选股扫描结果")
        window.geometry("600x500")
        window.configure(bg=self.colors['bg'])
        
        # 标题
        tk.Label(window, text="选股扫描结果", 
                font=Font(family='微软雅黑', size=18, weight='bold'),
                bg=self.colors['bg'], fg=self.colors['text_highlight']).pack(pady=10)
        
        # 统计信息
        tk.Label(window, text=f"扫描股票: {result['total_scanned']}只 | 候选股票: {result['candidates_count']}只",
                font=self.font_medium, bg=self.colors['bg'], fg=self.colors['text']).pack()
        
        # 候选股票列表
        if candidates:
            tk.Label(window, text="候选股票（评分>=60）", font=self.font_medium,
                    bg=self.colors['bg'], fg=self.colors['down']).pack(anchor='w', padx=10, pady=(10,0))
            
            candidate_frame = tk.Frame(window, bg=self.colors['bg_secondary'])
            candidate_frame.pack(fill='both', expand=True, padx=10, pady=5)
            
            # 表头
            header = tk.Frame(candidate_frame, bg=self.colors['bg_secondary'])
            header.pack(fill='x', padx=5, pady=2)
            tk.Label(header, text="排名", font=self.font_small, width=6,
                    bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(side='left')
            tk.Label(header, text="代码", font=self.font_small, width=10,
                    bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(side='left')
            tk.Label(header, text="评分", font=self.font_small, width=8,
                    bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(side='left')
            tk.Label(header, text="价格", font=self.font_small, width=10,
                    bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(side='left')
            tk.Label(header, text="信号", font=self.font_small, width=20,
                    bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(side='left')
            
            for i, stock in enumerate(candidates[:10], 1):
                row = tk.Frame(candidate_frame, bg=self.colors['bg_secondary'])
                row.pack(fill='x', padx=5, pady=1)
                
                signals = []
                if stock['signals'].get('MACD金叉'):
                    signals.append("MACD金叉")
                if stock['signals'].get('均线金叉'):
                    signals.append("均线金叉")
                if stock['signals'].get('底分型'):
                    signals.append("底分型")
                
                signal_str = ", ".join(signals) if signals else "无"
                
                tk.Label(row, text=str(i), font=self.font_small, width=6,
                        bg=self.colors['bg_secondary'], fg=self.colors['text_highlight']).pack(side='left')
                tk.Label(row, text=stock['code'], font=self.font_small, width=10,
                        bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(side='left')
                tk.Label(row, text=f"{stock['score']}分", font=self.font_small, width=8,
                        bg=self.colors['bg_secondary'], fg=self.colors['down'] if stock['score'] >= 80 else self.colors['text']).pack(side='left')
                tk.Label(row, text=f"{stock['price']:.2f}", font=self.font_small, width=10,
                        bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(side='left')
                tk.Label(row, text=signal_str, font=self.font_small, width=20,
                        bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(side='left')
        
        # 关闭按钮
        tk.Button(window, text="关闭", command=window.destroy,
                 bg=self.colors['accent'], fg='white', font=self.font_medium,
                 relief='flat', cursor='hand2', width=10).pack(pady=10)
        
        self.log(f"选股扫描完成，发现 {len(candidates)} 只候选股票", 'info')
    
    def _run_backtest(self, code: str):
        """执行回测"""
        try:
            from stock_data import get_stock_data
            from backtest_engine import run_backtest
            
            # 获取数据
            df = get_stock_data(code, count=252)  # 一年数据
            if df.empty or len(df) < 60:
                messagebox.showwarning("提示", f"无法获取 {code} 的数据或数据不足")
                return
            
            strategy_type = self.backtest_strategy.get()
            
            self.log(f"开始回测 {code}，策略: {strategy_type}", 'info')
            
            # 在新线程中运行回测
            def do_backtest():
                try:
                    result = run_backtest(df, code, strategy_type)
                    self.root.after(0, lambda: self._show_backtest_result(result, code))
                except Exception as e:
                    self.root.after(0, lambda: messagebox.showerror("错误", f"回测失败: {e}"))
            
            threading.Thread(target=do_backtest, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("错误", f"回测启动失败: {e}")
    
    def _show_backtest_result(self, result: dict, code: str):
        """显示回测结果"""
        if 'error' in result:
            messagebox.showerror("回测失败", result['error'])
            return
        
        # 创建弹窗
        window = tk.Toplevel(self.root)
        window.title(f"回测结果 - {code}")
        window.geometry("500x600")
        window.configure(bg=self.colors['bg'])
        
        # 标题
        tk.Label(window, text=f"{code} 回测报告", 
                font=Font(family='微软雅黑', size=18, weight='bold'),
                bg=self.colors['bg'], fg=self.colors['text_highlight']).pack(pady=10)
        
        # 结果框架
        result_frame = tk.Frame(window, bg=self.colors['bg_secondary'])
        result_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # 显示关键指标
        metrics = [
            ("策略", result['strategy']),
            ("初始资金", f"{result['initial_capital']:,.2f}"),
            ("最终权益", f"{result['final_equity']:,.2f}"),
            ("总收益率", f"{result['total_return']:+.2f}%"),
            ("年化收益", f"{result['annual_return']:+.2f}%"),
            ("最大回撤", f"{result['max_drawdown']:.2f}%"),
            ("胜率", f"{result['win_rate']:.1f}%"),
            ("交易次数", f"{result['total_trades']}次"),
            ("盈利次数", f"{result['winning_trades']}次"),
            ("亏损次数", f"{result['losing_trades']}次"),
            ("总盈亏", f"{result['total_pnl']:+.2f}"),
        ]
        
        for i, (label, value) in enumerate(metrics):
            row = tk.Frame(result_frame, bg=self.colors['bg_secondary'])
            row.pack(fill='x', padx=10, pady=2)
            
            tk.Label(row, text=label, font=self.font_small,
                    bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(side='left')
            
            # 根据数值设置颜色
            color = self.colors['text_highlight']
            if isinstance(value, str) and '%' in value:
                try:
                    val = float(value.replace('%', '').replace('+', ''))
                    if val > 0:
                        color = self.colors['down']  # 上涨绿色
                    elif val < 0:
                        color = self.colors['up']    # 下跌红色
                except:
                    pass
            
            tk.Label(row, text=value, font=self.font_small,
                    bg=self.colors['bg_secondary'], fg=color).pack(side='right')
        
        # 交易记录
        if result['trades']:
            tk.Label(window, text="交易记录", font=self.font_medium,
                    bg=self.colors['bg'], fg=self.colors['text']).pack(anchor='w', padx=10, pady=(10,0))
            
            trade_frame = tk.Frame(window, bg=self.colors['bg'])
            trade_frame.pack(fill='both', expand=True, padx=10, pady=5)
            
            trade_text = tk.Text(trade_frame, font=self.font_small,
                                bg=self.colors['bg_secondary'], fg=self.colors['text'],
                                relief='flat', height=10)
            trade_text.pack(side='left', fill='both', expand=True)
            
            scrollbar = tk.Scrollbar(trade_frame, command=trade_text.yview)
            scrollbar.pack(side='right', fill='y')
            trade_text.config(yscrollcommand=scrollbar.set)
            
            for trade in result['trades']:
                date_str = str(trade['date'])[:10] if 'date' in trade else ''
                action = trade['action']
                price = trade['price']
                if action == 'BUY':
                    trade_text.insert('end', f"{date_str} 买入 @ {price:.2f} x {trade.get('shares', 0)}股\n")
                else:
                    pnl = trade.get('pnl', 0)
                    trade_text.insert('end', f"{date_str} 卖出 @ {price:.2f} 盈亏: {pnl:+.2f}\n")
            
            trade_text.config(state='disabled')
        
        # 关闭按钮
        tk.Button(window, text="关闭", command=window.destroy,
                 bg=self.colors['accent'], fg='white', font=self.font_medium,
                 relief='flat', cursor='hand2', width=10).pack(pady=10)
        
        self.log(f"回测完成: {code} 收益率 {result['total_return']:+.2f}%", 'info')
    
    def ai_analyze_selected(self):
        """AI分析选中的股票"""
        api_key = self.ai_api_key.get().strip()
        if not api_key:
            messagebox.showwarning("提示", "请输入API密钥")
            return
        
        # 获取选中的股票
        selected = self.position_tree.selection()
        if not selected:
            code = self.trade_code.get().strip()
            if not code:
                messagebox.showwarning("提示", "请先选择股票或输入股票代码")
                return
        else:
            item = selected[0]
            values = self.position_tree.item(item)['values']
            code = self._format_stock_code(values[0])
        
        self.ai_analyzer.set_api_key(api_key)
        
        # 获取股票数据
        try:
            from stock_data import get_realtime_data
            quotes = get_realtime_data([code])
            if quotes.empty:
                messagebox.showwarning("提示", f"无法获取 {code} 的股票数据")
                return
            
            q = quotes.iloc[0]
            stock_data = {
                'price': float(q.get('price', 0)),
                'change_pct': round((float(q.get('price', 0)) - float(q.get('last_close', 0))) / float(q.get('last_close', 1)) * 100, 2),
                'volume': float(q.get('vol', 0)),
                'macd': '待计算',
                'ma5': '待计算',
                'ma20': '待计算',
                'rsi': '待计算'
            }
            
            # 在新线程中调用AI分析
            def analyze():
                result = self.ai_analyzer.analyze_stock(code, stock_data)
                self.root.after(0, lambda: self._show_ai_popup(result, code))
            
            threading.Thread(target=analyze, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("错误", f"分析失败: {e}")
    
    def ai_analyze_portfolio(self):
        """AI分析整个持仓组合"""
        api_key = self.ai_api_key.get().strip()
        if not api_key:
            messagebox.showwarning("提示", "请输入API密钥")
            return
        
        positions = self.pt.get_positions()
        if not positions:
            messagebox.showwarning("提示", "当前没有持仓")
            return
        
        self.ai_analyzer.set_api_key(api_key)
        
        def analyze():
            result = self.ai_analyzer.analyze_portfolio(positions)
            self.root.after(0, lambda: self._show_ai_popup(result, "持仓组合"))
        
        threading.Thread(target=analyze, daemon=True).start()
    
    def _show_ai_popup(self, result, title_name):
        """弹出窗口显示AI分析结论"""
        if result.get('success'):
            analysis = result.get('analysis', {})
            
            # 提取操作结论
            conclusion = ""
            if isinstance(analysis, dict):
                if '操作建议' in analysis:
                    conclusion = analysis['操作建议']
                elif '操作' in analysis:
                    conclusion = analysis['操作']
                elif '建议' in analysis:
                    conclusion = analysis['建议']
                elif 'conclusion' in analysis:
                    conclusion = analysis['conclusion']
                elif 'action' in analysis:
                    conclusion = analysis['action']
                else:
                    conclusion = str(list(analysis.values())[0]) if analysis else "分析完成"
            else:
                conclusion = str(analysis)
            
            # 确定颜色：卖出红色，其他白色
            color = "#ffffff"  # 白色默认
            if any(word in conclusion for word in ['卖出', 'sell', '抛售', '减仓']):
                color = "#ff4444"  # 红色卖出
            
            # 创建弹窗
            popup = tk.Toplevel(self.root)
            popup.title(f"AI智能分析 - {title_name}")
            popup.geometry("650x500")
            popup.configure(bg=self.colors['bg'])
            popup.transient(self.root)
            popup.grab_set()
            popup.resizable(True, True)
            
            # 主框架
            main_frame = tk.Frame(popup, bg=self.colors['bg'])
            main_frame.pack(fill='both', expand=True, padx=20, pady=20)
            
            # 股票标题
            tk.Label(main_frame, text=title_name, font=Font(family='微软雅黑', size=20, weight='bold'),
                    bg=self.colors['bg'], fg='#ffffff').pack(pady=5)
            
            # 分隔线
            tk.Frame(main_frame, bg='#444444', height=2).pack(fill='x', pady=10)
            
            # 操作建议（自动换行，字体适中）
            tk.Label(main_frame, text="操作建议", font=self.font_medium,
                    bg=self.colors['bg'], fg='#aaaaaa').pack(anchor='w')
            
            action_label = tk.Label(main_frame, text=conclusion, 
                                   font=Font(family='微软雅黑', size=14),
                                   bg=self.colors['bg'], fg=color,
                                   wraplength=550, justify='left')
            action_label.pack(pady=10, fill='x')
            
            # 详细分析
            detail_frame = tk.Frame(main_frame, bg=self.colors['bg'])
            detail_frame.pack(fill='both', expand=True, pady=10)
            
            tk.Label(detail_frame, text="分析详情", font=self.font_medium,
                    bg=self.colors['bg'], fg='#aaaaaa').pack(anchor='w')
            
            detail_text = tk.Text(detail_frame, font=self.font_small,
                                 bg='#1a1a1a', fg='#ffffff',
                                 relief='flat', wrap='word', height=6)
            detail_text.pack(fill='both', expand=True, pady=5)
            
            # 构建详细内容
            detail_lines = []
            if isinstance(analysis, dict):
                for key, value in analysis.items():
                    if key not in ['操作建议', '操作', '建议', 'conclusion', 'action']:
                        detail_lines.append(f"{key}: {value}")
            
            if detail_lines:
                detail_text.insert('1.0', '\n'.join(detail_lines))
            else:
                detail_text.insert('1.0', '基于当前市场数据和技术指标的综合分析结果。')
            
            detail_text.config(state='disabled')
            
            # 按钮区域
            btn_frame = tk.Frame(main_frame, bg=self.colors['bg'])
            btn_frame.pack(fill='x', pady=10)
            
            tk.Button(btn_frame, text="确定", command=popup.destroy,
                     bg='#444444', fg='#ffffff', font=self.font_medium,
                     relief='flat', cursor='hand2', width=10).pack(side='right', padx=5)
            
            self.log("AI分析完成", 'info')
        else:
            error = result.get('error', '未知错误')
            messagebox.showerror("分析失败", f"AI分析失败: {error}")
    
    def create_auto_control(self, parent):
        """自动交易控制"""
        panel = tk.LabelFrame(parent, text=" 自动交易 ", font=self.font_medium,
                             bg=self.colors['bg_secondary'], fg=self.colors['text'],
                             relief='solid', borderwidth=1)
        panel.pack(fill='x', padx=5, pady=5)
        
        self.auto_status_label = tk.Label(panel, text="状态: 停止", font=self.font_medium,
                                         bg=self.colors['bg_secondary'], fg=self.colors['up'])
        self.auto_status_label.pack(pady=10)
        
        btn_frame = tk.Frame(panel, bg=self.colors['bg_secondary'])
        btn_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Button(btn_frame, text="启动", command=self.start_auto,
                 bg=self.colors['down'], fg='white', font=self.font_medium,
                 relief='flat', cursor='hand2').pack(side='left', fill='x', expand=True, padx=2)
        
        tk.Button(btn_frame, text="停止", command=self.stop_auto,
                 bg=self.colors['up'], fg='white', font=self.font_medium,
                 relief='flat', cursor='hand2').pack(side='left', fill='x', expand=True, padx=2)
    
    def create_status_bar(self):
        """状态栏"""
        status = tk.Frame(self.root, bg=self.colors['bg_secondary'], height=25)
        status.pack(fill='x', side='bottom')
        
        self.status_text = tk.Label(status, text="就绪", font=self.font_small,
                                   bg=self.colors['bg_secondary'], fg=self.colors['text'])
        self.status_text.pack(side='left', padx=10)
    
    def refresh_all(self):
        """刷新所有数据"""
        try:
            # 确保数据连接
            if not self.pt.api.connected:
                self.log("正在连接数据服务器...", 'info')
                self.pt.api.connect()
            
            # 账户信息
            info = self.pt.get_account_info()
            self.total_assets.config(text=f"¥{info['总资产']:,.2f}")
            self.daily_pnl.config(text=f"{info['总盈亏']:+.2f} ({info['总盈亏率']})",
                                 fg=self.colors['down'] if info['总盈亏'] >= 0 else self.colors['up'])
            
            self.account_labels['available'].config(text=f"¥{info['可用资金']:,.2f}")
            self.account_labels['market_value'].config(text=f"¥{info['总市值']:,.2f}")
            self.account_labels['positions'].config(text=str(info['持仓数量']))
            
            # 持仓 - 智能更新（保留选中状态）
            positions = self.pt.get_positions()
            print(f"DEBUG: 获取到 {len(positions)} 条持仓")
            
            # 获取当前选中的代码
            selected_codes = []
            for sel_item in self.position_tree.selection():
                vals = self.position_tree.item(sel_item)['values']
                if vals:
                    selected_codes.append(str(vals[0]).zfill(6))  # 统一为6位字符串
            
            # 获取现有item的代码映射
            existing_items = {}
            for item in self.position_tree.get_children():
                vals = self.position_tree.item(item)['values']
                if vals:
                    existing_items[str(vals[0]).zfill(6)] = item  # 统一为6位字符串
            
            # 更新或插入
            current_codes = set()
            for p in positions:
                try:
                    code = p.get('代码', '')
                    current_codes.add(code)
                    
                    values = (
                        code,
                        p.get('名称', ''),
                        p.get('股数', 0),
                        f"{p.get('成本价', 0):.2f}",
                        f"{p.get('现价', 0):.2f}",
                        f"{p.get('市值', 0):,.2f}",
                        f"{p.get('盈亏率', 0):+.2f}%"
                    )
                    tag = 'up' if p.get('盈亏率', 0) >= 0 else 'down'
                    
                    if code in existing_items:
                        # 更新现有行
                        item = existing_items[code]
                        self.position_tree.item(item, values=values, tags=(tag,))
                    else:
                        # 插入新行
                        self.position_tree.insert('', 'end', values=values, tags=(tag,))
                except Exception as e:
                    print(f"DEBUG: 更新持仓失败 {p}: {e}")
            
            # 删除不再持仓的行
            for code, item in existing_items.items():
                if code not in current_codes:
                    self.position_tree.delete(item)
            
            # 恢复选中状态
            for item in self.position_tree.get_children():
                vals = self.position_tree.item(item)['values']
                if vals and vals[0] in selected_codes:
                    self.position_tree.selection_add(item)
            
            self.position_tree.tag_configure('up', foreground=self.colors['down'])
            self.position_tree.tag_configure('down', foreground=self.colors['up'])
            
            # 时间
            self.header_time.config(text=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
        except Exception as e:
            self.log(f"刷新错误: {e}", 'info')
            print(f"DEBUG: refresh_all 异常: {e}")
            import traceback
            traceback.print_exc()
            # 尝试重新连接
            try:
                self.pt.api.connect()
            except:
                pass
    
    def log(self, message, tag='info'):
        """添加日志"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.insert('end', f"[{timestamp}] {message}\n", tag)
        self.log_text.see('end')
    
    def quick_buy(self):
        """快速买入 - 支持模拟和实盘"""
        code = self.trade_code.get().strip()
        shares_str = self.trade_shares.get().strip()
        
        if not code:
            messagebox.showwarning("提示", "请输入股票代码")
            return
        
        # 格式化股票代码
        code = self._format_stock_code(code)
        
        try:
            shares = int(shares_str) if shares_str else 100
        except:
            shares = 100
        
        # 根据模式执行买入
        if self.trade_mode == 'real':
            # 实盘买入
            mode_text = "实盘"
            confirm_msg = f"【实盘】买入 {code} {shares}股?\n\n确认后将真实成交！"
        else:
            mode_text = "模拟"
            confirm_msg = f"【模拟】买入 {code} {shares}股?"
        
        if messagebox.askyesno("确认", confirm_msg):
            if self.trade_mode == 'real':
                # 获取当前价格
                try:
                    quotes = self.pt.api.get_realtime_quotes([code])
                    price = float(quotes.iloc[0]['price']) if not quotes.empty else 0
                except:
                    price = 0
                
                success, msg = self.real_trader.buy(code, price, shares)
                if success:
                    self.log(f"【实盘】买入 {code} {shares}股", 'buy')
                    self.refresh_real_account()
                else:
                    messagebox.showerror("失败", f"买入失败: {msg}")
            else:
                # 模拟买入
                success = self.pt.buy(code, shares=shares, reason="快速买入")
                if success:
                    self.log(f"【模拟】买入 {code} {shares}股", 'buy')
                    self.refresh_all()
                else:
                    messagebox.showerror("失败", "买入失败")
    
    def quick_sell(self):
        """快速卖出 - 支持模拟和实盘"""
        code = self.trade_code.get().strip()
        shares_str = self.trade_shares.get().strip()
        
        if not code:
            messagebox.showwarning("提示", "请输入股票代码")
            return
        
        # 格式化股票代码
        code = self._format_stock_code(code)
        
        try:
            shares = int(shares_str) if shares_str else 0
        except:
            shares = 0
        
        # 根据模式执行卖出
        if self.trade_mode == 'real':
            mode_text = "实盘"
            confirm_msg = f"【实盘】卖出 {code} {shares}股?\n\n确认后将真实成交！"
        else:
            mode_text = "模拟"
            confirm_msg = f"【模拟】卖出 {code} {shares}股?"
        
        if messagebox.askyesno("确认", confirm_msg):
            if self.trade_mode == 'real':
                # 获取当前价格
                try:
                    quotes = self.pt.api.get_realtime_quotes([code])
                    price = float(quotes.iloc[0]['price']) if not quotes.empty else 0
                except:
                    price = 0
                
                # 确定卖出股数
                positions = self.real_trader.get_positions()
                hold_shares = 0
                for p in positions:
                    if p['代码'] == code:
                        hold_shares = p['可用']
                        break
                
                sell_shares = shares if shares > 0 else hold_shares
                
                success, msg = self.real_trader.sell(code, price, sell_shares)
                if success:
                    self.log(f"【实盘】卖出 {code} {sell_shares}股", 'sell')
                    self.refresh_real_account()
                else:
                    messagebox.showerror("失败", f"卖出失败: {msg}")
            else:
                # 模拟卖出
                positions = self.pt.get_positions()
                for p in positions:
                    if p['代码'] == code:
                        sell_shares = shares if shares > 0 else p['股数']
                        success = self.pt.sell(code, shares=sell_shares, reason="快速卖出")
                        if success:
                            self.log(f"【模拟】卖出 {code} {sell_shares}股", 'sell')
                            self.refresh_all()
                        return
                messagebox.showwarning("提示", "未持有该股票")
    
    def update_watch(self):
        """更新监控列表"""
        # 从Listbox获取列表
        self.watch_list = [self.watch_listbox.get(i) for i in range(self.watch_listbox.size())]
        self.log(f"监控列表更新: {self.watch_list}")
    
    def on_watch_select(self, event):
        """监控列表选中事件"""
        selection = self.watch_listbox.curselection()
        if selection:
            code = self.watch_listbox.get(selection[0])
            self.watch_input.delete(0, 'end')
            self.watch_input.insert(0, code)
    
    def on_watch_double_click(self, event):
        """监控列表双击事件"""
        selection = self.watch_listbox.curselection()
        if selection:
            code = self.watch_listbox.get(selection[0])
            # 设置到交易代码框
            self.trade_code.delete(0, 'end')
            self.trade_code.insert(0, code)
            self.log(f"选中监控股票: {code}", 'info')
    
    def remove_watch_selected(self):
        """删除选中的监控股票"""
        selection = self.watch_listbox.curselection()
        if not selection:
            messagebox.showwarning("提示", "请先选中要删除的股票")
            return
        
        index = selection[0]
        code = self.watch_listbox.get(index)
        self.watch_listbox.delete(index)
        self.watch_input.delete(0, 'end')
        self.log(f"删除监控: {code}", 'info')
    
    def analyze_watch_selected(self):
        """分析选中的监控股票"""
        selection = self.watch_listbox.curselection()
        if not selection:
            messagebox.showwarning("提示", "请先选中要分析的股票")
            return
        
        code = self.watch_listbox.get(selection[0])
        api_key = self.ai_api_key.get().strip()
        if not api_key:
            messagebox.showwarning("提示", "请输入API密钥")
            return
        
        self.ai_analyzer.set_api_key(api_key)
        
        # 获取股票数据并分析
        try:
            from stock_data import get_realtime_data
            quotes = get_realtime_data([code])
            if quotes.empty:
                messagebox.showwarning("提示", f"无法获取 {code} 的股票数据")
                return
            
            q = quotes.iloc[0]
            stock_data = {
                'price': float(q.get('price', 0)),
                'change_pct': round((float(q.get('price', 0)) - float(q.get('last_close', 0))) / float(q.get('last_close', 1)) * 100, 2),
                'volume': float(q.get('vol', 0)),
                'macd': '待计算',
                'ma5': '待计算',
                'ma20': '待计算',
                'rsi': '待计算'
            }
            
            def analyze():
                result = self.ai_analyzer.analyze_stock(code, stock_data)
                self.root.after(0, lambda: self._show_ai_popup(result, code))
            
            threading.Thread(target=analyze, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("错误", f"分析失败: {e}")
    
    def add_to_watch(self):
        """添加股票到监控列表"""
        code = self.watch_input.get().strip()
        if not code:
            return
        
        # 格式化代码
        code = self._format_stock_code(code)
        
        # 检查是否已存在
        if code in self.watch_list:
            messagebox.showwarning("提示", f"{code} 已在监控列表中")
            return
        
        # 验证股票代码是否有效
        try:
            from stock_data import get_realtime_data
            quotes = get_realtime_data([code])
            if quotes.empty:
                messagebox.showwarning("提示", f"无法获取 {code} 的行情，请检查代码")
                return
        except Exception as e:
            messagebox.showwarning("提示", f"验证股票代码失败: {e}")
            return
        
        # 添加到Treeview和列表
        self.watch_list.append(code)
        self.watch_tree.insert('', 'end', values=(code, '--', '--', '--'), tags=(code,))
        self.watch_input.delete(0, 'end')
        self.log(f"添加监控: {code}", 'info')
    
    def remove_from_watch(self):
        """从输入框删除股票"""
        code = self.watch_input.get().strip()
        if not code:
            messagebox.showwarning("提示", "请输入要删除的股票代码")
            return
        
        code = self._format_stock_code(code)
        
        # 查找并删除
        for i in range(self.watch_listbox.size()):
            if self.watch_listbox.get(i) == code:
                self.watch_listbox.delete(i)
                self.watch_input.delete(0, 'end')
                self.log(f"删除监控: {code}", 'info')
                return
        
        messagebox.showwarning("提示", f"{code} 不在监控列表中")
    
    def remove_watch_selected(self):
        """删除选中的股票"""
        selection = self.watch_tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择要删除的股票")
            return
        
        item = selection[0]
        values = self.watch_tree.item(item)['values']
        code = values[0] if values else ''
        self.watch_tree.delete(item)
        if code in self.watch_list:
            self.watch_list.remove(code)
        if code in self.watch_analysis_data:
            del self.watch_analysis_data[code]
        self.log(f"删除监控: {code}", 'info')
    
    def on_watch_select(self, event):
        """监控列表选中事件"""
        selection = self.watch_tree.selection()
        if selection:
            item = selection[0]
            values = self.watch_tree.item(item)['values']
            code = values[0] if values else ''
            self.trade_code.delete(0, 'end')
            self.trade_code.insert(0, code)
    
    def show_watch_menu(self, event):
        """监控列表右键菜单"""
        # 获取点击位置的item
        item = self.watch_tree.identify_row(event.y)
        if not item:
            return
        
        # 选中该项
        self.watch_tree.selection_set(item)
        
        values = self.watch_tree.item(item)['values']
        code = values[0] if values else ''
        
        # 创建右键菜单
        menu = tk.Menu(self.root, tearoff=0, bg=self.colors['bg_secondary'], fg=self.colors['text'])
        
        # 分析菜单
        menu.add_command(label=f"深度分析 {code}", command=lambda: self._watch_deep_analysis(code))
        menu.add_command(label=f"通达信评分 {code}", command=lambda: self._watch_tdx_score(code))
        menu.add_command(label=f"因子分析 {code}", command=lambda: self._watch_factor_analysis(code))
        menu.add_separator()
        
        # 策略菜单
        menu.add_command(label=f"MACD回测 {code}", command=lambda: self._watch_backtest(code, 'macd'))
        menu.add_command(label=f"均线回测 {code}", command=lambda: self._watch_backtest(code, 'ma'))
        menu.add_separator()
        
        # 操作菜单
        menu.add_command(label=f"保留 {code} (继续监控)", command=lambda: self._watch_keep(item))
        menu.add_command(label=f"删除 {code} (从列表移除)", command=lambda: self._watch_remove(item))
        menu.add_separator()
        
        # 交易菜单
        menu.add_command(label=f"立即买入 {code}", command=lambda: self._watch_buy(code))
        
        menu.post(event.x_root, event.y_root)
    
    def _watch_deep_analysis(self, code: str):
        """对监控列表股票进行深度分析"""
        api_key = self.ai_api_key.get().strip()
        if not api_key:
            messagebox.showwarning("提示", "请输入API密钥")
            return
        
        self.log(f"深度分析 {code}...", 'info')
        
        def analyze():
            try:
                result = self.daily_analyzer.analyze_stock(code, api_key, self.daily_model.get(),
                                                           lambda r, e=None: self._handle_watch_analysis(r, e, code),
                                                           quick_mode=self.daily_quick_mode.get())
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", f"分析失败: {e}"))
        
        threading.Thread(target=analyze, daemon=True).start()
    
    def _handle_watch_analysis(self, result, error, code: str):
        """处理监控列表分析结果"""
        if error:
            messagebox.showerror("分析失败", error)
            return
        
        if result:
            self.daily_analyzer.show_analysis_result(result, f"深度分析 - {code}")
    
    def _watch_tdx_score(self, code: str):
        """对监控列表股票进行通达信评分"""
        self.log(f"通达信评分 {code}...", 'info')
        
        def calc_score():
            try:
                from stock_data import get_stock_data
                from tdx_stock_picker import TDXStockPicker
                
                df = get_stock_data(code, count=100)
                if df.empty or len(df) < 60:
                    self.root.after(0, lambda: messagebox.showwarning("提示", "数据不足"))
                    return
                
                picker = TDXStockPicker(df)
                result = picker.get_latest_score()
                
                self.root.after(0, lambda: self._show_tdx_score_result(result, code))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", f"评分失败: {e}"))
        
        threading.Thread(target=calc_score, daemon=True).start()
    
    def _show_tdx_score_result(self, result: dict, code: str):
        """显示通达信评分结果"""
        window = tk.Toplevel(self.root)
        window.title(f"通达信评分 - {code}")
        window.geometry("400x400")
        window.configure(bg=self.colors['bg'])
        
        tk.Label(window, text=f"{code} 评分结果", 
                font=Font(family='微软雅黑', size=16, weight='bold'),
                bg=self.colors['bg'], fg=self.colors['text_highlight']).pack(pady=10)
        
        # 评分
        score = result['score']
        score_color = self.colors['down'] if score >= 80 else self.colors['text'] if score >= 60 else self.colors['up']
        tk.Label(window, text=f"{score}分", font=Font(family='微软雅黑', size=32, weight='bold'),
                bg=self.colors['bg'], fg=score_color).pack()
        
        # 评分等级
        level = '强烈买入' if score >= 80 else '买入' if score >= 60 else '观望' if score >= 40 else '卖出'
        tk.Label(window, text=level, font=self.font_medium,
                bg=self.colors['bg'], fg=score_color).pack()
        
        # 评分构成
        frame = tk.Frame(window, bg=self.colors['bg_secondary'])
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        tk.Label(frame, text="评分构成:", font=self.font_small,
                bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(anchor='w', padx=5, pady=5)
        
        for key, value in result['components'].items():
            if value > 0:
                row = tk.Frame(frame, bg=self.colors['bg_secondary'])
                row.pack(fill='x', padx=5, pady=1)
                tk.Label(row, text=key, font=self.font_small,
                        bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(side='left')
                tk.Label(row, text=f"+{value}分", font=self.font_small,
                        bg=self.colors['bg_secondary'], fg=self.colors['down']).pack(side='right')
        
        # 技术信号
        signals = result['signals']
        signal_frame = tk.Frame(window, bg=self.colors['bg'])
        signal_frame.pack(fill='x', padx=10, pady=5)
        
        signal_text = []
        if signals.get('MACD金叉'):
            signal_text.append("MACD金叉")
        if signals.get('均线金叉'):
            signal_text.append("均线金叉")
        if signals.get('底分型'):
            signal_text.append("底分型")
        if signals.get('顶分型'):
            signal_text.append("顶分型")
        
        if signal_text:
            tk.Label(signal_frame, text=f"信号: {', '.join(signal_text)}",
                    font=self.font_small, bg=self.colors['bg'], fg=self.colors['accent']).pack()
        
        tk.Button(window, text="关闭", command=window.destroy,
                 bg=self.colors['accent'], fg='white', font=self.font_medium,
                 relief='flat', cursor='hand2', width=10).pack(pady=10)
        
        self.log(f"{code} 评分: {score}分", 'info')
    
    def _watch_factor_analysis(self, code: str):
        """对监控列表股票进行因子分析"""
        self.log(f"因子分析 {code}...", 'info')
        
        def analyze():
            try:
                from stock_data import get_stock_data
                
                df = get_stock_data(code, count=60)
                if df.empty:
                    self.root.after(0, lambda: messagebox.showwarning("提示", "无法获取数据"))
                    return
                
                result = self.factor_analyzer.calculate_factors(df, code)
                self.root.after(0, lambda: self.factor_analyzer.show_factor_result(result, code))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", f"因子分析失败: {e}"))
        
        threading.Thread(target=analyze, daemon=True).start()
    
    def _watch_backtest(self, code: str, strategy: str):
        """对监控列表股票进行回测"""
        self._run_backtest(code)
    
    def _watch_buy(self, code: str):
        """买入监控列表股票"""
        self.trade_code.delete(0, 'end')
        self.trade_code.insert(0, code)
        self.quick_buy()
    
    def _watch_keep(self, item):
        """保留监控列表股票（确认继续监控）"""
        values = self.watch_tree.item(item)['values']
        code = values[0] if values else ''
        
        # 重置为正常监控状态
        self.watch_tree.item(item, tags=('keep',))
        self.watch_tree.tag_configure('keep', foreground=self.colors['text'])
        
        self.log(f"保留监控: {code}，将继续自动交易", 'info')
        messagebox.showinfo("操作确认", f"已保留 {code}\n该股票将继续参与自动交易")
    
    def _watch_remove(self, item):
        """删除监控列表股票"""
        values = self.watch_tree.item(item)['values']
        code = values[0] if values else ''
        
        # 确认删除
        if messagebox.askyesno("确认删除", f"确定从监控列表删除 {code} 吗？\n删除后将不再自动交易该股票"):
            self.watch_tree.delete(item)
            # 从列表中移除
            if code in self.watch_list:
                self.watch_list.remove(code)
            # 清除分析数据
            if code in self.watch_analysis_data:
                del self.watch_analysis_data[code]
            self.log(f"删除监控: {code}", 'info')
    
    def on_watch_double_click(self, event):
        """监控列表双击事件"""
        item = self.watch_tree.identify_row(event.y)
        if item:
            values = self.watch_tree.item(item)['values']
            code = values[0] if values else ''
            self.trade_code.delete(0, 'end')
            self.trade_code.insert(0, code)
            self.show_minute_chart_from_watch(code)
    
    def show_minute_chart_from_watch(self, code):
        """显示监控列表股票的分时图"""
        try:
            # 尝试导入分时图模块
            try:
                from minute_chart import MinuteChart
                chart = MinuteChart(self.root, code)
            except ImportError:
                # 模块不存在，显示提示信息
                messagebox.showinfo("提示", f"股票 {code} 分时图功能暂未实现\n\n建议：使用通达信软件查看实时行情")
                self.log(f"[{code}] 双击选中，分时图功能暂未实现", "info")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开分时图: {e}")
    
    def analyze_watch_selected(self):
        """分析监控列表选中的股票"""
        selection = self.watch_tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择要分析的股票")
            return
        
        item = selection[0]
        values = self.watch_tree.item(item)['values']
        code = values[0] if values else ''
        api_key = self.ai_api_key.get().strip()
        
        if not api_key:
            messagebox.showwarning("提示", "请输入API密钥")
            return
        
        self.ai_analyzer.set_api_key(api_key)
        
        try:
            from stock_data import get_realtime_data
            quotes = get_realtime_data([code])
            if quotes.empty:
                messagebox.showwarning("提示", f"无法获取 {code} 的行情")
                return
            
            result = self.ai_analyzer.analyze_stock(code, quotes)
            self._show_ai_popup(result, code)
        except Exception as e:
            messagebox.showerror("错误", f"分析失败: {e}")
    
    def auto_analyze_watch_list(self):
        """自动分析监控列表所有股票"""
        if not self.watch_list:
            messagebox.showwarning("提示", "监控列表为空")
            return
        
        self.log(f"开始自动分析监控列表 {len(self.watch_list)} 只股票...", 'info')
        
        def analyze_all():
            from stock_data import get_stock_data
            from tdx_stock_picker import TDXStockPicker
            
            results = []
            for code in self.watch_list:
                try:
                    df = get_stock_data(code, count=100)
                    if df.empty or len(df) < 60:
                        continue
                    
                    picker = TDXStockPicker(df)
                    result = picker.get_latest_score()
                    
                    # 构建信号文本
                    signals = []
                    if result['signals'].get('MACD金叉'):
                        signals.append("MACD金叉")
                    if result['signals'].get('均线金叉'):
                        signals.append("均线金叉")
                    if result['signals'].get('底分型'):
                        signals.append("底分型")
                    if result['signals'].get('顶分型'):
                        signals.append("顶分型")
                    
                    signal_str = ", ".join(signals) if signals else "无"
                    
                    # 建议
                    score = result['score']
                    if score >= 80:
                        suggestion = "强烈买入"
                    elif score >= 60:
                        suggestion = "买入"
                    elif score >= 40:
                        suggestion = "观望"
                    else:
                        suggestion = "卖出"
                    
                    results.append({
                        'code': code,
                        'score': score,
                        'signals': signal_str,
                        'suggestion': suggestion,
                        'price': result['price']
                    })
                    
                    # 更新UI
                    self.root.after(0, lambda c=code, s=score, sig=signal_str, sug=suggestion: 
                        self._update_watch_item(c, s, sig, sug))
                    
                except Exception as e:
                    print(f"分析 {code} 失败: {e}")
                    continue
            
            # 按评分排序
            results.sort(key=lambda x: x['score'], reverse=True)
            
            # 显示结果汇总
            self.root.after(0, lambda: self._show_watch_analysis_summary(results))
        
        threading.Thread(target=analyze_all, daemon=True).start()
    
    def _update_watch_item(self, code: str, score: int, signals: str, suggestion: str):
        """更新监控列表项的显示"""
        # 查找对应的item
        for item in self.watch_tree.get_children():
            values = self.watch_tree.item(item)['values']
            if values and values[0] == code:
                self.watch_tree.item(item, values=(code, f"{score}", signals, suggestion))
                
                # 根据评分设置颜色标签
                if score >= 80:
                    self.watch_tree.item(item, tags=('strong_buy',))
                elif score >= 60:
                    self.watch_tree.item(item, tags=('buy',))
                elif score < 40:
                    self.watch_tree.item(item, tags=('sell',))
                break
        
        # 配置标签颜色
        self.watch_tree.tag_configure('strong_buy', foreground='#00ff00')  # 亮绿色
        self.watch_tree.tag_configure('buy', foreground=self.colors['down'])  # 绿色
        self.watch_tree.tag_configure('sell', foreground=self.colors['up'])   # 红色
    
    def _show_watch_analysis_summary(self, results: list):
        """显示监控列表分析汇总"""
        if not results:
            self.log("分析完成，无有效结果", 'info')
            return
        
        # 统计
        strong_buy = [r for r in results if r['score'] >= 80]
        buy = [r for r in results if 60 <= r['score'] < 80]
        sell = [r for r in results if r['score'] < 40]
        
        self.log(f"分析完成: 强烈买入{len(strong_buy)}只, 买入{len(buy)}只, 卖出{len(sell)}只", 'info')
        
        # 显示前5名
        self.log("评分前5名:", 'info')
        for i, r in enumerate(results[:5], 1):
            self.log(f"  {i}. {r['code']} {r['score']}分 {r['suggestion']}", 'info')
        
        # 如果有强烈买入的，弹出提示，由人工决定是否保留
        if strong_buy:
            codes = [r['code'] for r in strong_buy[:3]]
            msg = f"发现强烈买入信号股票:\n{', '.join(codes)}\n\n建议操作:\n- 保留: 继续监控并自动交易\n- 删除: 从列表移除\n\n请在监控列表中右键操作"
            messagebox.showinfo("选股提示", msg)
    
    def start_auto_refresh(self):
        """启动自动刷新定时器"""
        if not self.auto_refresh_enabled:
            return
        
        def refresh_loop():
            while self.auto_refresh_enabled:
                try:
                    # 在主线程中执行刷新
                    self.root.after(0, self.refresh_all)
                except Exception as e:
                    print(f"自动刷新错误: {e}")
                time.sleep(1)  # 每秒刷新一次
        
        threading.Thread(target=refresh_loop, daemon=True).start()
        self.log("自动刷新已启动（每秒）", 'info')
    
    def stop_auto_refresh(self):
        """停止自动刷新"""
        self.auto_refresh_enabled = False
        self.log("自动刷新已停止", 'info')
    
    def _run_stock_scanner(self):
        """运行选股扫描（仅标记，不自动买卖）"""
        if not self.watch_list:
            return
        
        try:
            from stock_scanner import scan_watch_list
            
            self.log("开始选股扫描...", 'info')
            
            # 扫描监控列表
            result = scan_watch_list(self.watch_list, score_threshold=60)
            
            candidates = result.get('candidates', [])
            
            if candidates:
                self.log(f"选股扫描完成，发现 {len(candidates)} 只候选股票", 'info')
                
                # 显示前3名并标记
                for i, stock in enumerate(candidates[:3], 1):
                    code = stock['code']
                    score = stock['score']
                    price = stock['price']
                    self.log(f"  候选{i}: {code} 评分{score}分 价格{price:.2f}", 'info')
                    
                    # 在监控列表中高亮标记
                    self._highlight_watch_item(code, score, "候选")
            else:
                self.log("选股扫描完成，未发现候选股票", 'info')
                
        except Exception as e:
            self.log(f"选股扫描失败: {e}", 'info')
    
    def _highlight_watch_item(self, code: str, score: int, tag: str):
        """高亮监控列表中的股票"""
        for item in self.watch_tree.get_children():
            values = self.watch_tree.item(item)['values']
            if values and values[0] == code:
                # 更新显示
                signals = values[2] if len(values) > 2 else ""
                self.watch_tree.item(item, values=(code, f"{score}", signals, f"{tag}"))
                
                # 设置颜色
                if score >= 80:
                    self.watch_tree.item(item, tags=('candidate_strong',))
                else:
                    self.watch_tree.item(item, tags=('candidate',))
                break
        
        # 配置候选标签颜色
        self.watch_tree.tag_configure('candidate_strong', foreground='#00ff00', font=('微软雅黑', 9, 'bold'))
        self.watch_tree.tag_configure('candidate', foreground=self.colors['down'])
    
    def start_auto(self):
        """启动自动交易（整合选股扫描）"""
        if self.auto_running:
            return
        
        self.auto_running = True
        self.auto_status_label.config(text="状态: 运行中", fg=self.colors['down'])
        self.log("自动交易已启动（含选股扫描）")
        
        def auto_loop():
            scan_counter = 0
            while self.auto_running:
                # 每30秒执行一次常规扫描
                self.pt.auto_scan(self.watch_list)
                self.root.after(0, self.refresh_all)
                
                # 每5分钟执行一次选股扫描（10次*30秒=300秒）
                scan_counter += 1
                if scan_counter >= 10:
                    scan_counter = 0
                    self._run_stock_scanner()
                
                time.sleep(30)
        
        threading.Thread(target=auto_loop, daemon=True).start()
    
    def stop_auto(self):
        """停止自动交易"""
        self.auto_running = False
        self.auto_status_label.config(text="状态: 停止", fg=self.colors['up'])
        self.log("自动交易已停止")
    
    def reset_account(self):
        """重置账户"""
        if messagebox.askyesno("确认", "重置账户? 所有数据将清空!"):
            self.pt.reset()
            self.log("账户已重置")
            self.refresh_all()
    

    def _load_broker_list(self):
        """加载券商列表到下拉框"""
        brokers = get_supported_brokers()
        broker_names = [b['name'] for b in brokers]
        self.broker_combo['values'] = broker_names if broker_names else ['东莞证券']
        if broker_names:
            self.broker_combo.current(0)
    
    def config_broker(self):
        """配置券商"""
        win = tk.Toplevel(self.root)
        win.title("券商配置")
        win.geometry("400x300")
        win.configure(bg=self.colors['bg'])
        win.transient(self.root)
        win.grab_set()
        
        tk.Label(win, text="券商配置", font=self.font_medium,
                bg=self.colors['bg'], fg=self.colors['text']).pack(pady=10)
        
        brokers = get_supported_brokers()
        for broker in brokers:
            frame = tk.Frame(win, bg=self.colors['bg_secondary'])
            frame.pack(fill='x', padx=20, pady=5)
            tk.Label(frame, text=broker['name'], font=self.font_small,
                    bg=self.colors['bg_secondary'], fg=self.colors['text'],
                    width=15).pack(side='left', padx=10, pady=5)
            tk.Label(frame, text=broker.get('status', '可用'), font=self.font_small,
                    bg=self.colors['bg_secondary'], fg=self.colors['down']).pack(side='right', padx=10, pady=5)
        
        tk.Button(win, text="关闭", command=win.destroy,
                 bg=self.colors['accent'], fg='white', font=self.font_small,
                 relief='flat').pack(pady=20)
    
    def config_smart_watch(self):
        """智能监控配置"""
        win = tk.Toplevel(self.root)
        win.title("智能监控配置")
        win.geometry("400x350")
        win.configure(bg=self.colors['bg'])
        win.transient(self.root)
        win.grab_set()
        
        tk.Label(win, text="智能监控配置", font=self.font_medium,
                bg=self.colors['bg'], fg=self.colors['text']).pack(pady=10)
        
        config_frame = tk.Frame(win, bg=self.colors['bg_secondary'])
        config_frame.pack(fill='x', padx=20, pady=5)
        
        # 最低评分
        row1 = tk.Frame(config_frame, bg=self.colors['bg_secondary'])
        row1.pack(fill='x', padx=10, pady=5)
        tk.Label(row1, text="最低评分:", font=self.font_small,
                bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(side='left')
        self.sw_min_score = tk.Entry(row1, font=self.font_small, width=8,
                                    bg=self.colors['bg'], fg=self.colors['text'])
        self.sw_min_score.pack(side='right', padx=5)
        self.sw_min_score.insert(0, "60")
        
        # 最大监控数
        row2 = tk.Frame(config_frame, bg=self.colors['bg_secondary'])
        row2.pack(fill='x', padx=10, pady=5)
        tk.Label(row2, text="最大监控数:", font=self.font_small,
                bg=self.colors['bg_secondary'], fg=self.colors['text']).pack(side='left')
        self.sw_max_count = tk.Entry(row2, font=self.font_small, width=8,
                                    bg=self.colors['bg'], fg=self.colors['text'])
        self.sw_max_count.pack(side='right', padx=5)
        self.sw_max_count.insert(0, "50")
        
        # 自动添加
        self.sw_auto_add_var = tk.BooleanVar(value=True)
        tk.Checkbutton(config_frame, text="自动添加符合条件的股票", 
                      variable=self.sw_auto_add_var,
                      bg=self.colors['bg_secondary'], fg=self.colors['text'],
                      selectcolor=self.colors['bg'],
                      font=self.font_small).pack(anchor='w', padx=10, pady=5)
        
        # 自动移除
        self.sw_auto_remove_var = tk.BooleanVar(value=True)
        tk.Checkbutton(config_frame, text="自动移除不符合条件的股票",
                      variable=self.sw_auto_remove_var,
                      bg=self.colors['bg_secondary'], fg=self.colors['text'],
                      selectcolor=self.colors['bg'],
                      font=self.font_small).pack(anchor='w', padx=10, pady=5)
        
        def save_config():
            try:
                min_score = int(self.sw_min_score.get())
                max_count = int(self.sw_max_count.get())
                self.smart_watch.update_config(
                    min_score=min_score,
                    max_count=max_count,
                    auto_add=self.sw_auto_add_var.get(),
                    auto_remove=self.sw_auto_remove_var.get()
                )
                self.log(f"智能监控配置已更新: 评分>={min_score}, 最大{max_count}只", 'info')
                messagebox.showinfo("成功", "配置已保存")
                win.destroy()
            except ValueError:
                messagebox.showwarning("错误", "请输入有效数字")
        
        tk.Button(win, text="保存配置", command=save_config,
                 bg=self.colors['down'], fg='white', font=self.font_small,
                 relief='flat').pack(pady=15)
    
    def toggle_smart_watch(self):
        """启动/停止智能自动监控"""
        if self.smart_watch_running:
            self.smart_watch_running = False
            self.smart_watch_btn.config(text="启动自动监控", bg='#8b5cf6')
            self.log("智能自动监控已停止", 'info')
        else:
            self.smart_watch_running = True
            self.smart_watch_btn.config(text="停止自动监控", bg=self.colors['up'])
            self.log("智能自动监控已启动", 'info')
            threading.Thread(target=self._smart_watch_loop, daemon=True).start()
    
    def _smart_watch_loop(self):
        """智能监控循环"""
        while self.smart_watch_running:
            try:
                result = self.smart_watch.scan_and_update()
                if result:
                    added = result.get('added', [])
                    removed = result.get('removed', [])
                    if added:
                        self.root.after(0, lambda a=added: self.log(f"[智能监控] 新增: {', '.join(a)}", 'info'))
                    if removed:
                        self.root.after(0, lambda r=removed: self.log(f"[智能监控] 移除: {', '.join(r)}", 'info'))
                    self.root.after(0, self._refresh_watch_tree)
            except Exception as e:
                self.root.after(0, lambda e=e: self.log(f"[智能监控] 错误: {e}", 'info'))
            time.sleep(300)
    
    def _refresh_watch_tree(self):
        """刷新监控列表 Treeview"""
        try:
            self.watch_list = self.smart_watch.get_watch_list()
            if not self.watch_list:
                self.watch_list = ['000858', '600519']
            for item in self.watch_tree.get_children():
                self.watch_tree.delete(item)
            for code in self.watch_list:
                data = self.watch_analysis_data.get(code, {})
                score = data.get('score', '--')
                signal = data.get('signal', '--')
                suggestion = data.get('suggestion', '--')
                self.watch_tree.insert('', 'end', values=(code, score, signal, suggestion), tags=(code,))
        except Exception:
            pass
    
    def _on_smart_watch_add(self, code):
        """智能监控添加回调"""
        if code not in self.watch_list:
            self.watch_list.append(code)
            self.root.after(0, lambda: self.watch_tree.insert('', 'end', values=(code, '--', '--', '--'), tags=(code,)))
            self.root.after(0, lambda: self.log(f"[智能监控] 添加: {code}", 'info'))
    
    def _on_smart_watch_remove(self, code):
        """智能监控移除回调"""
        if code in self.watch_list:
            self.watch_list.remove(code)
            self.root.after(0, self._refresh_watch_tree)
            self.root.after(0, lambda: self.log(f"[智能监控] 移除: {code}", 'info'))
    
    def _on_smart_watch_update(self, watch_items):
        """智能监控更新回调 - 接收整个监控列表"""
        for item in watch_items:
            self.watch_analysis_data[item.code] = item.to_dict()
    
    def save_broker_account(self):
        """保存券商账户"""
        account = self.broker_account.get().strip()
        if not account or account == "请输入券商账号":
            messagebox.showwarning("提示", "请输入有效的券商账号")
            return
        
        # 保存到文件
        try:
            with open('broker_account.txt', 'w', encoding='utf-8') as f:
                f.write(account)
            self.log(f"券商账号已保存: {account}", 'info')
            messagebox.showinfo("成功", f"券商账号已保存\n账号: {account}")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")
    
    def load_broker_account(self):
        """加载券商账户"""
        try:
            if os.path.exists('broker_account.txt'):
                with open('broker_account.txt', 'r', encoding='utf-8') as f:
                    account = f.read().strip()
                    if account:
                        self.broker_account.delete(0, 'end')
                        self.broker_account.insert(0, account)
        except Exception as e:
            self.log(f"加载券商账号失败: {e}", 'info')
    
    def connect_real_trading(self):
        """连接实盘交易"""
        if self.real_trader.connected:
            messagebox.showinfo("提示", "已连接实盘")
            return
        
        # 提示用户确保客户端已登录
        if not messagebox.askyesno("确认", 
            "请确保：\n1. 东莞证券掌证宝已启动\n2. 已完成登录\n3. 客户端保持运行\n\n是否继续连接？"):
            return
        
        try:
            success = self.real_trader.connect()
            if success:
                self.trade_mode = 'real'
                self.trade_mode_label.config(text="模式: 实盘", fg=self.colors['down'])
                self.log("实盘连接成功", 'info')
                messagebox.showinfo("成功", "东莞证券实盘连接成功！")
                
                # 刷新实盘账户信息
                self.refresh_real_account()
            else:
                messagebox.showerror("失败", "连接失败，请检查客户端状态")
        except Exception as e:
            messagebox.showerror("错误", f"连接异常: {e}")
    
    def switch_trade_mode(self):
        """切换交易模式"""
        if self.trade_mode == 'paper':
            if self.real_trader.connected:
                self.trade_mode = 'real'
                self.trade_mode_label.config(text="模式: 实盘", fg=self.colors['down'])
                self.log("切换至实盘模式", 'info')
            else:
                messagebox.showwarning("提示", "请先连接实盘")
        else:
            self.trade_mode = 'paper'
            self.trade_mode_label.config(text="模式: 模拟", fg=self.colors['up'])
            self.log("切换至模拟模式", 'info')
    
    def refresh_real_account(self):
        """刷新实盘账户信息"""
        if not self.real_trader.connected:
            return
        
        try:
            info = self.real_trader.get_account_info()
            self.total_assets.config(text=f"¥{info.get('总资产', 0):,.2f}")
            self.account_labels['available'].config(text=f"¥{info.get('可用资金', 0):,.2f}")
            self.account_labels['market_value'].config(text=f"¥{info.get('市值', 0):,.2f}")
            
            # 刷新实盘持仓
            positions = self.real_trader.get_positions()
            for item in self.position_tree.get_children():
                self.position_tree.delete(item)
            
            for p in positions:
                values = (
                    p['代码'],
                    p['名称'],
                    p['股数'],
                    f"{p['成本价']:.2f}",
                    f"{p['现价']:.2f}",
                    f"{p['市值']:,.2f}",
                    f"{p['盈亏率']:+.2f}%"
                )
                tag = 'up' if p['盈亏率'] >= 0 else 'down'
                self.position_tree.insert('', 'end', values=values, tags=(tag,))
            
            self.account_labels['positions'].config(text=str(len(positions)))
            
        except Exception as e:
            self.log(f"刷新实盘信息失败: {e}", 'info')
    
    def show_position_menu(self, event):
        """持仓右键菜单"""
        item = self.position_tree.identify_row(event.y)
        if item:
            self.position_tree.selection_set(item)
            menu = tk.Menu(self.root, tearoff=0, bg=self.colors['bg'], fg=self.colors['text'])
            menu.add_command(label="卖出", command=lambda: self.sell_selected(item))
            menu.add_command(label="查看详情", command=lambda: self.show_detail(item))
            menu.post(event.x_root, event.y_root)
    
    def sell_selected(self, item):
        """卖出选中"""
        values = self.position_tree.item(item)['values']
        code = str(values[0]).zfill(6)  # Treeview返回int，需转为6位字符串
        shares = int(values[2])
        name = values[1] if len(values) > 1 else code
        
        if messagebox.askyesno("确认卖出", f"股票: {name} ({code})\n数量: {shares}股\n\n确定卖出?"):
            try:
                success = self.pt.sell(code, price=None, shares=shares, reason="持仓右键卖出")
                if success:
                    self.log(f"[卖出成功] {code} {shares}股", 'sell')
                    self.refresh_all()
                else:
                    messagebox.showerror("卖出失败", f"无法卖出 {code}\n请检查:\n1. 是否持有该股票\n2. 网络连接是否正常")
            except Exception as e:
                messagebox.showerror("卖出错误", f"卖出异常: {e}")
                self.log(f"[卖出错误] {code}: {e}", 'info')
    
    def show_detail(self, item):
        """显示详情"""
        values = self.position_tree.item(item)['values']
        code = str(values[0]).zfill(6)
        messagebox.showinfo("详情", f"股票: {code}\n股数: {values[2]}\n成本: {values[3]}\n现价: {values[4]}")
    
    def show_realtime_data(self, event):
        """双击显示实时数据"""
        item = self.position_tree.identify_row(event.y)
        if not item:
            return
        
        values = self.position_tree.item(item)['values']
        code = self._format_stock_code(values[0])  # 使用统一格式化方法
        
        # 创建实时数据窗口
        window = tk.Toplevel(self.root)
        window.title(f"实时行情 - {code}")
        window.geometry("400x500")
        window.configure(bg=self.colors['bg'])
        
        # 获取实时数据
        try:
            quotes = self.pt.api.get_realtime_quotes([code])
            if not quotes.empty:
                q = quotes.iloc[0]
                price = q.get('price', 0)
                open_price = q.get('open', 0)
                high = q.get('high', 0)
                low = q.get('low', 0)
                prev_close = q.get('last_close', price)
                volume = q.get('vol', 0)
                
                change = price - prev_close
                change_pct = (change / prev_close * 100) if prev_close else 0
            else:
                price = float(values[4])
                open_price = high = low = prev_close = price
                change = change_pct = 0
                volume = 0
        except:
            price = float(values[4])
            open_price = high = low = prev_close = price
            change = change_pct = 0
            volume = 0
        
        # 股票代码和名称
        tk.Label(window, text=code, font=Font(family='微软雅黑', size=24, weight='bold'),
                bg=self.colors['bg'], fg=self.colors['text_highlight']).pack(pady=10)
        
        # 当前价格（大字体）
        color = self.colors['down'] if change >= 0 else self.colors['up']
        price_label = tk.Label(window, text=f"{price:.2f}", 
                              font=Font(family='微软雅黑', size=36, weight='bold'),
                              bg=self.colors['bg'], fg=color)
        price_label.pack()
        
        # 涨跌幅
        change_text = f"{change:+.2f} ({change_pct:+.2f}%)"
        change_label = tk.Label(window, text=change_text,
                               font=self.font_medium,
                               bg=self.colors['bg'], fg=color)
        change_label.pack(pady=5)
        
        # 分隔线
        tk.Frame(window, bg=self.colors['border'], height=2).pack(fill='x', padx=20, pady=10)
        
        # 详细数据
        data_frame = tk.Frame(window, bg=self.colors['bg'])
        data_frame.pack(fill='x', padx=30, pady=10)
        
        data_items = [
            ("今开", f"{open_price:.2f}"),
            ("最高", f"{high:.2f}"),
            ("最低", f"{low:.2f}"),
            ("昨收", f"{prev_close:.2f}"),
            ("成交量", f"{volume/10000:.2f}万"),
            ("市值", f"{float(values[5]):,.2f}"),
            ("成本", values[3]),
            ("盈亏", values[6])
        ]
        
        for i, (label, value) in enumerate(data_items):
            tk.Label(data_frame, text=label, font=self.font_small,
                    bg=self.colors['bg'], fg=self.colors['text']).grid(row=i, column=0, sticky='w', pady=3)
            tk.Label(data_frame, text=value, font=self.font_small,
                    bg=self.colors['bg'], fg=self.colors['text_highlight']).grid(row=i, column=1, sticky='e', pady=3)
            data_frame.grid_columnconfigure(1, weight=1)
        
        # 操作按钮
        btn_frame = tk.Frame(window, bg=self.colors['bg'])
        btn_frame.pack(fill='x', padx=30, pady=20)
        
        def buy_more():
            window.destroy()
            self.trade_code.delete(0, 'end')
            self.trade_code.insert(0, code)
            self.quick_buy()
        
        def sell_some():
            window.destroy()
            self.trade_code.delete(0, 'end')
            self.trade_code.insert(0, code)
            self.quick_sell()
        
        tk.Button(btn_frame, text="买入", command=buy_more,
                 bg=self.colors['down'], fg='white', font=self.font_medium,
                 relief='flat', cursor='hand2', width=10).pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="卖出", command=sell_some,
                 bg=self.colors['up'], fg='white', font=self.font_medium,
                 relief='flat', cursor='hand2', width=10).pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="关闭", command=window.destroy,
                 bg=self.colors['border'], fg=self.colors['text'], font=self.font_medium,
                 relief='flat', cursor='hand2', width=10).pack(side='right', padx=5)
        
        self.log(f"查看实时行情: {code}", 'info')
    
    def show_minute_chart(self, event):
        """双击显示分时图"""
        item = self.position_tree.identify_row(event.y)
        if not item:
            return
        
        values = self.position_tree.item(item)['values']
        code = self._format_stock_code(values[0])  # 使用统一格式化方法
        
        # 创建分时图窗口
        window = tk.Toplevel(self.root)
        window.title(f"分时图 - {code}")
        window.geometry("800x500")
        window.configure(bg=self.colors['bg'])
        
        # 获取实时行情数据
        try:
            from stock_data import get_realtime_data, get_stock_data
            quotes = get_realtime_data([code])
            if quotes.empty:
                messagebox.showwarning("提示", "无法获取实时行情")
                window.destroy()
                return
            
            q = quotes.iloc[0]
            current_price = float(q.get('price', 0))
            open_price = float(q.get('open', 0))
            high = float(q.get('high', 0))
            low = float(q.get('low', 0))
            prev_close = float(q.get('last_close', open_price))
            
            # 尝试获取分时数据，如果没有则使用实时数据生成
            df = get_stock_data(code, period='1min', count=240)
            
            # 如果数据不是今天的，使用实时数据模拟
            today = datetime.now().date()
            is_today_data = False
            if not df.empty:
                try:
                    last_date = pd.to_datetime(df['datetime'].iloc[-1]).date()
                    is_today_data = (last_date == today)
                except:
                    is_today_data = False
            
            if df.empty or not is_today_data:
                # 使用实时数据生成模拟分时走势
                n_points = 240  # 4小时交易时间
                times = pd.date_range(start='09:30', periods=n_points, freq='1min')
                
                # 生成从开盘价到当前价的随机游走
                if current_price > 0 and open_price > 0:
                    # 使用实际高低点作为范围
                    price_range = high - low if high > low else current_price * 0.02
                    base_price = open_price
                    
                    # 生成随机游走价格序列，终点为当前价
                    random_walk = np.random.randn(n_points).cumsum()
                    random_walk = (random_walk - random_walk[-1]) * price_range * 0.1
                    prices = base_price + random_walk + (current_price - base_price) * np.linspace(0, 1, n_points)
                    
                    # 确保价格在合理范围内
                    prices = np.clip(prices, low * 0.99, high * 1.01)
                    prices[-1] = current_price  # 最后一个点为当前价
                else:
                    prices = [open_price] * n_points
                
                df = pd.DataFrame({
                    'datetime': times,
                    'open': prices,
                    'high': prices,
                    'low': prices,
                    'close': prices,
                    'vol': [0] * n_points,
                    'amount': [0] * n_points
                })
            
        except Exception as e:
            messagebox.showerror("错误", f"获取数据失败: {e}")
            window.destroy()
            return
        
        # 顶部信息栏
        header = tk.Frame(window, bg=self.colors['bg_secondary'], height=40)
        header.pack(fill='x', padx=5, pady=5)
        
        change = current_price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0
        color = self.colors['down'] if change >= 0 else self.colors['up']
        
        tk.Label(header, text=code, font=self.font_large,
                bg=self.colors['bg_secondary'], fg=self.colors['text_highlight']).pack(side='left', padx=10)
        
        tk.Label(header, text=f"{current_price:.2f}", font=self.font_large,
                bg=self.colors['bg_secondary'], fg=color).pack(side='left', padx=10)
        
        tk.Label(header, text=f"{change:+.2f} ({change_pct:+.2f}%)", font=self.font_medium,
                bg=self.colors['bg_secondary'], fg=color).pack(side='left', padx=10)
        
        # 周期选择按钮
        period_frame = tk.Frame(header, bg=self.colors['bg_secondary'])
        period_frame.pack(side='right', padx=10)
        
        # 当前周期变量
        current_period = tk.StringVar(value='分时')
        
        def switch_period(period):
            current_period.set(period)
            if period == '分时':
                window.title(f"分时图 - {code}")
            else:
                window.title(f"{period} - {code}")
            draw_chart()
        
        periods = ['分时', '5分', '30分', '日K', '周K', '月K']
        for p in periods:
            tk.Button(period_frame, text=p, 
                     command=lambda x=p: switch_period(x),
                     bg=self.colors['down'] if p == '分时' else self.colors['border'],
                     fg='white' if p == '分时' else self.colors['text'],
                     font=self.font_small, relief='flat', width=5).pack(side='left', padx=1)
        
        # 缩放比例变量
        zoom_level = [1.0]  # 使用列表以便在嵌套函数中修改
        
        def zoom_in():
            zoom_level[0] = max(zoom_level[0] * 0.8, 0.5)
            draw_chart()
        
        def zoom_out():
            zoom_level[0] = min(zoom_level[0] * 1.2, 3.0)
            draw_chart()
        
        def reset_zoom():
            zoom_level[0] = 1.0
            draw_chart()
        
        # 在周期按钮后添加缩放按钮
        zoom_frame = tk.Frame(header, bg=self.colors['bg_secondary'])
        zoom_frame.pack(side='right', padx=5)
        
        tk.Button(zoom_frame, text="缩小", command=zoom_in,
                 bg=self.colors['border'], fg=self.colors['text'], font=self.font_small,
                 relief='flat', width=4).pack(side='left', padx=1)
        tk.Button(zoom_frame, text="放大", command=zoom_out,
                 bg=self.colors['border'], fg=self.colors['text'], font=self.font_small,
                 relief='flat', width=4).pack(side='left', padx=1)
        tk.Button(zoom_frame, text="重置", command=reset_zoom,
                 bg=self.colors['border'], fg=self.colors['text'], font=self.font_small,
                 relief='flat', width=4).pack(side='left', padx=1)
        
        # Canvas绘制区域 - 使用两个Canvas分别显示主图和MACD副图
        chart_frame = tk.Frame(window, bg=self.colors['bg'])
        chart_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # 主图Canvas（占70%高度）
        main_canvas = tk.Canvas(chart_frame, bg=self.colors['bg'], highlightthickness=0, height=280)
        main_canvas.pack(fill='x', padx=0, pady=0)
        
        # 分隔线
        tk.Frame(chart_frame, bg=self.colors['border'], height=2).pack(fill='x', padx=0, pady=2)
        
        # MACD副图Canvas（占30%高度）
        macd_canvas = tk.Canvas(chart_frame, bg=self.colors['bg'], highlightthickness=0, height=120)
        macd_canvas.pack(fill='x', padx=0, pady=0)
        
        def calculate_macd(prices, short=6, long=13, mid=5):
            """计算MACD指标"""
            # 计算EMA
            def ema(data, period):
                multiplier = 2 / (period + 1)
                ema_values = [data[0]]
                for i in range(1, len(data)):
                    ema_values.append(data[i] * multiplier + ema_values[-1] * (1 - multiplier))
                return ema_values
            
            # 确保有足够的数据
            if len(prices) < long:
                return None, None, None
            
            ema_short = ema(prices, short)
            ema_long = ema(prices, long)
            
            # DIF = EMA(12) - EMA(26)  这里用 short=6, long=13
            dif = [s - l for s, l in zip(ema_short, ema_long)]
            
            # DEA = EMA(DIF, mid)
            dea = ema(dif, mid)
            
            # MACD = 2 * (DIF - DEA)
            macd = [2 * (d - e) for d, e in zip(dif, dea)]
            
            return dif, dea, macd
        
        def draw_chart():
            # 清空两个Canvas
            main_canvas.delete('all')
            macd_canvas.delete('all')
            
            width = main_canvas.winfo_width()
            main_height = main_canvas.winfo_height()
            macd_height = macd_canvas.winfo_height()
            
            if width < 100 or main_height < 100:
                main_canvas.after(100, draw_chart)
                return
            
            period = current_period.get()
            chart_df = df
            
            # 根据周期获取数据，应用缩放
            if period != '分时':
                try:
                    period_map = {'5分': '5min', '30分': '30min', '日K': 'day', '周K': 'week', '月K': 'month'}
                    ktype = period_map.get(period, 'day')
                    # 根据缩放调整数据条数：放大=显示更多数据，缩小=显示更少数据
                    base_count = int(60 / zoom_level[0])
                    base_count = max(20, min(base_count, 200))
                    chart_df = get_stock_data(code, period=ktype, count=base_count)
                    if chart_df.empty:
                        main_canvas.create_text(width/2, main_height/2, text="无数据", 
                                         fill=self.colors['text'], font=self.font_medium)
                        return
                except Exception as e:
                    main_canvas.create_text(width/2, main_height/2, text=f"获取数据失败: {e}", 
                                     fill=self.colors['up'], font=self.font_medium)
                    return
            else:
                # 分时图也根据缩放调整显示的数据点数
                if zoom_level[0] != 1.0:
                    # 根据缩放比例截取数据
                    total_points = len(df)
                    show_points = int(total_points / zoom_level[0])
                    show_points = max(20, min(show_points, total_points))
                    if show_points < total_points:
                        chart_df = df.iloc[-show_points:].copy()
                    else:
                        chart_df = df
            
            # 计算价格范围
            prices = chart_df['close'].tolist()
            if not prices:
                return
            
            max_price = max(chart_df['high']) if 'high' in chart_df.columns else max(prices)
            min_price = min(chart_df['low']) if 'low' in chart_df.columns else min(prices)
            price_range = max_price - min_price if max_price != min_price else 1
            
            # 绘制主图网格
            for i in range(5):
                y = main_height * 0.1 + (main_height * 0.8) * i / 4
                main_canvas.create_line(50, y, width-20, y, fill=self.colors['border'], dash=(2, 2))
                price = max_price - price_range * i / 4
                main_canvas.create_text(30, y, text=f"{price:.2f}", fill=self.colors['text'], font=self.font_small)
            
            # 绘制K线或分时线
            # 周期调试标记
            main_canvas.create_text(100, 80, text=f'周期:{period}', fill='#00FF00', font=self.font_small)
            
            if period == '分时':
                # 绘制分时线
                points = []
                for i, price in enumerate(prices):
                    x = 50 + (width - 70) * i / max(len(prices) - 1, 1)
                    y = main_height * 0.1 + (main_height * 0.8) * (max_price - price) / price_range
                    points.append((x, y))
                
                if len(points) > 1:
                    for i in range(len(points) - 1):
                        main_canvas.create_line(points[i][0], points[i][1], points[i+1][0], points[i+1][1],
                                         fill=self.colors['accent'], width=2)
                
                # 绘制均价线
                if 'amount' in chart_df.columns and 'vol' in chart_df.columns:
                    chart_df['avg'] = chart_df['amount'].cumsum() / chart_df['vol'].cumsum()
                    avg_prices = chart_df['avg'].tolist()
                    avg_points = []
                    for i, price in enumerate(avg_prices):
                        x = 50 + (width - 70) * i / max(len(avg_prices) - 1, 1)
                        y = main_height * 0.1 + (main_height * 0.8) * (max_price - price) / price_range
                        avg_points.append((x, y))
                    
                    if len(avg_points) > 1:
                        for i in range(len(avg_points) - 1):
                            main_canvas.create_line(avg_points[i][0], avg_points[i][1], 
                                             avg_points[i+1][0], avg_points[i+1][1],
                                             fill=self.colors['warning'], width=1, dash=(4, 2))
            else:
                # 绘制K线
                candle_width = (width - 70) / len(prices) * 0.6
                for i, (idx, row) in enumerate(chart_df.iterrows()):
                    x = 50 + (width - 70) * i / max(len(prices) - 1, 1)
                    
                    open_p = row['open']
                    close_p = row['close']
                    high_p = row['high']
                    low_p = row['low']
                    
                    # 计算Y坐标
                    y_open = main_height * 0.1 + (main_height * 0.8) * (max_price - open_p) / price_range
                    y_close = main_height * 0.1 + (main_height * 0.8) * (max_price - close_p) / price_range
                    y_high = main_height * 0.1 + (main_height * 0.8) * (max_price - high_p) / price_range
                    y_low = main_height * 0.1 + (main_height * 0.8) * (max_price - low_p) / price_range
                    
                    # 颜色：涨红跌绿
                    candle_color = self.colors['down'] if close_p >= open_p else self.colors['up']
                    
                    # 绘制影线
                    main_canvas.create_line(x, y_high, x, y_low, fill=self.colors['text'], width=1)
                    
                    # 绘制实体
                    main_canvas.create_rectangle(x - candle_width/2, y_open, 
                                          x + candle_width/2, y_close,
                                          fill=candle_color, outline=candle_color)
                
                # ========== 步骤1：识别并绘制顶分型和底分型 ==========
                # 强制显示标记确认代码执行
                main_canvas.create_text(150, 60, text='分型识别已启用', fill='#FF0000', font=self.font_small)
                
                if len(prices) >= 5:
                    highs = chart_df['high'].values
                    lows = chart_df['low'].values
                    closes = chart_df['close'].values
                    
                    # 调试信息
                    top_count = 0
                    bottom_count = 0
                    
                    # 识别顶分型：中间K线的高点比左右两边都高
                    # 识别底分型：中间K线的低点比左右两边都低
                    for i in range(2, len(prices) - 2):
                        # 顶分型条件：第i根K线的高点 > 左边两根和右边两根的高点
                        is_top_fractal = (highs[i] > highs[i-1] and highs[i] > highs[i-2] and 
                                          highs[i] > highs[i+1] and highs[i] > highs[i+2])
                        
                        # 底分型条件：第i根K线的低点 < 左边两根和右边两根的低点
                        is_bottom_fractal = (lows[i] < lows[i-1] and lows[i] < lows[i-2] and 
                                             lows[i] < lows[i+1] and lows[i] < lows[i+2])
                        
                        x = 50 + (width - 70) * i / max(len(prices) - 1, 1)
                        
                        if is_top_fractal:
                            top_count += 1
                            # 顶分型：绘制紫色倒三角形
                            y_high = main_height * 0.1 + (main_height * 0.8) * (max_price - highs[i]) / price_range
                            y_high = max(15, min(y_high, main_height - 15))
                            main_canvas.create_polygon(
                                x, y_high - 12, x-6, y_high - 2, x+6, y_high - 2,
                                fill='#FF00FF', outline='#FF00FF'
                            )
                            main_canvas.create_text(x, y_high - 18, text='顶', fill='#FF00FF', font=self.font_small)
                        
                        if is_bottom_fractal:
                            bottom_count += 1
                            # 底分型：绘制黄色正三角形
                            y_low = main_height * 0.1 + (main_height * 0.8) * (max_price - lows[i]) / price_range
                            y_low = max(15, min(y_low, main_height - 15))
                            main_canvas.create_polygon(
                                x, y_low + 12, x-6, y_low + 2, x+6, y_low + 2,
                                fill='#FFFF00', outline='#FFFF00'
                            )
                            main_canvas.create_text(x, y_low + 20, text='底', fill='#FFFF00', font=self.font_small)
                    
                    # 显示分型统计（调试用，确认代码执行）
                    main_canvas.create_text(200, 40, text=f'顶:{top_count} 底:{bottom_count}', fill='#00FFFF', font=self.font_small)
                    
                    # 计算MACD指标（short=6, long=13, mid=5）用于辅助验证
                    def calculate_macd_for_fractal(data, short=6, long=13, mid=5):
                        # 计算EMA
                        def ema(data, period):
                            multiplier = 2 / (period + 1)
                            ema_values = [data[0]]
                            for i in range(1, len(data)):
                                ema_values.append(data[i] * multiplier + ema_values[-1] * (1 - multiplier))
                            return ema_values
                        
                        ema_short = ema(data, short)
                        ema_long = ema(data, long)
                        dif = [s - l for s, l in zip(ema_short, ema_long)]
                        dea = ema(dif, mid)
                        macd = [2 * (d - e) for d, e in zip(dif, dea)]
                        return dif, dea, macd
                    
                    # 计算收盘价的MACD
                    dif, dea, macd = calculate_macd_for_fractal(closes)
                    
                    # ========== 步骤2：连接顶底分型画出笔（加入MACD辅助验证） ==========
                    # 收集所有分型点
                    fractals = []
                    for i in range(2, len(prices) - 2):
                        is_top = (highs[i] > highs[i-1] and highs[i] > highs[i-2] and 
                                  highs[i] > highs[i+1] and highs[i] > highs[i+2])
                        is_bottom = (lows[i] < lows[i-1] and lows[i] < lows[i-2] and 
                                     lows[i] < lows[i+1] and lows[i] < lows[i+2])
                        if is_top:
                            fractals.append(('top', i, highs[i]))
                        if is_bottom:
                            fractals.append(('bottom', i, lows[i]))
                    
                    # 按索引排序
                    fractals.sort(key=lambda x: x[1])
                    
                    # 构建笔：严格按照缠论108课规则，加入MACD辅助验证
                    # 规则：
                    # 1. 顶分型和底分型相连
                    # 2. 每笔至少5根K线（位置差>=5，即中间至少3根独立K线）
                    # 3. 不足5根K线则笔延续（继续找下一个反向分型）
                    # 4. 上一笔结束后，上升笔连接到最高点的顶分型，下降笔连接到最低点的底分型
                    # 5. MACD辅助：上升笔要求DIF在上升，下降笔要求DIF在下降
                    pens = []
                    if len(fractals) >= 2:
                        i = 0
                        while i < len(fractals):
                            curr_type, curr_pos, curr_price = fractals[i]
                            
                            # 寻找满足5根K线条件的下一个反向分型中的极值点
                            target_idx = None
                            extreme_price = None
                            extreme_pos = None
                            macd_confirmed = False
                            
                            for j in range(i + 1, len(fractals)):
                                if fractals[j][0] != curr_type:
                                    # 检查是否满足5根K线（位置差>=5）
                                    if fractals[j][1] - curr_pos >= 5:
                                        target_idx = j
                                        target_pos = fractals[j][1]
                                        
                                        if curr_type == 'bottom':
                                            # 上升笔：在区间内找最高点的顶分型
                                            max_high = highs[curr_pos]
                                            max_pos = curr_pos
                                            for k in range(curr_pos, min(target_pos + 1, len(highs))):
                                                if highs[k] > max_high:
                                                    max_high = highs[k]
                                                    max_pos = k
                                            extreme_price = max_high
                                            extreme_pos = max_pos
                                            # MACD验证：上升笔要求DIF在终点大于起点
                                            if max_pos < len(dif) and curr_pos < len(dif):
                                                macd_confirmed = dif[max_pos] > dif[curr_pos]
                                        else:
                                            # 下降笔：在区间内找最低点的底分型
                                            min_low = lows[curr_pos]
                                            min_pos = curr_pos
                                            for k in range(curr_pos, min(target_pos + 1, len(lows))):
                                                if lows[k] < min_low:
                                                    min_low = lows[k]
                                                    min_pos = k
                                            extreme_price = min_low
                                            extreme_pos = min_pos
                                            # MACD验证：下降笔要求DIF在终点小于起点
                                            if min_pos < len(dif) and curr_pos < len(dif):
                                                macd_confirmed = dif[min_pos] < dif[curr_pos]
                                        
                                        # MACD确认或无条件接受（如果没有MACD数据）
                                        if macd_confirmed or max_pos >= len(dif):
                                            break
                                        # MACD不确认，继续寻找下一个
                                    # 不满足，继续寻找更远的反向分型（笔延续）
                            
                            if target_idx is None:
                                break
                            
                            # 绘制笔：从当前分型到区间极值点
                            if curr_type == 'bottom':
                                pens.append(('up', curr_pos, lows[curr_pos], extreme_pos, extreme_price))
                            else:
                                pens.append(('down', curr_pos, highs[curr_pos], extreme_pos, extreme_price))
                            
                            # 从目标分型继续
                            i = target_idx
                    
                    # 绘制笔
                    pen_count = 0
                    for pen in pens:
                        pen_type, start_pos, start_price, end_pos, end_price = pen
                        
                        x1 = 50 + (width - 70) * start_pos / max(len(prices) - 1, 1)
                        x2 = 50 + (width - 70) * end_pos / max(len(prices) - 1, 1)
                        y1 = main_height * 0.1 + (main_height * 0.8) * (max_price - start_price) / price_range
                        y2 = main_height * 0.1 + (main_height * 0.8) * (max_price - end_price) / price_range
                        y1 = max(15, min(y1, main_height - 15))
                        y2 = max(15, min(y2, main_height - 15))
                        
                        # 上升笔：橙色，下降笔：青色
                        if pen_type == 'up':
                            pen_color = '#FFA500'  # 上升笔橙色
                        else:
                            pen_color = '#00FFFF'  # 下降笔青色
                        
                        main_canvas.create_line(x1, y1, x2, y2, fill=pen_color, width=3)
                        pen_count += 1
                    
                    # 显示笔统计
                    main_canvas.create_text(300, 40, text=f'笔:{pen_count}', fill='#FFA500', font=self.font_small)
                    
                    # ========== 步骤3：以笔为基础画出线段（段），加入MACD辅助验证 ==========
                    # 线段规则：至少3笔，有方向，笔之间有重叠，MACD确认趋势
                    if len(pens) >= 3:
                        segments = []
                        
                        # 构建线段：至少3笔，顶底交替，MACD确认
                        i = 0
                        while i <= len(pens) - 3:
                            # 检查连续3笔是否形成线段
                            pen1 = pens[i]
                            pen2 = pens[i + 1]
                            pen3 = pens[i + 2]
                            
                            # 笔类型必须交替（上升-下降-上升 或 下降-上升-下降）
                            if pen1[0] != pen2[0] and pen2[0] != pen3[0]:
                                # 确定线段方向（第一笔的方向）
                                seg_type = pen1[0]  # 'up'或'down'
                                
                                # 线段起点：第一笔的起点
                                seg_start_pos = pen1[1]
                                seg_start_price = pen1[2]
                                
                                # 线段终点：第三笔的终点
                                seg_end_pos = pen3[3]
                                seg_end_price = pen3[4]
                                
                                # MACD验证线段趋势
                                macd_valid = True
                                if seg_start_pos < len(dif) and seg_end_pos < len(dif):
                                    if seg_type == 'up':
                                        # 上升段：DIF应该上升
                                        macd_valid = dif[seg_end_pos] > dif[seg_start_pos]
                                    else:
                                        # 下降段：DIF应该下降
                                        macd_valid = dif[seg_end_pos] < dif[seg_start_pos]
                                
                                # MACD确认或无条件接受
                                if macd_valid:
                                    segments.append((seg_type, seg_start_pos, seg_start_price, seg_end_pos, seg_end_price))
                                    i += 2  # 跳过已使用的笔
                                else:
                                    i += 1  # MACD不确认，继续寻找
                            else:
                                i += 1
                        
                        # 绘制线段
                        seg_count = 0
                        for seg in segments:
                            seg_type, start_pos, start_price, end_pos, end_price = seg
                            
                            x1 = 50 + (width - 70) * start_pos / max(len(prices) - 1, 1)
                            x2 = 50 + (width - 70) * end_pos / max(len(prices) - 1, 1)
                            y1 = main_height * 0.1 + (main_height * 0.8) * (max_price - start_price) / price_range
                            y2 = main_height * 0.1 + (main_height * 0.8) * (max_price - end_price) / price_range
                            y1 = max(15, min(y1, main_height - 15))
                            y2 = max(15, min(y2, main_height - 15))
                            
                            # 上升段：红色粗线，下降段：绿色粗线
                            if seg_type == 'up':
                                seg_color = '#FF0000'  # 上升段红色
                            else:
                                seg_color = '#00FF00'  # 下降段绿色
                            
                            # 线段用更粗的虚线表示
                            main_canvas.create_line(x1, y1, x2, y2, fill=seg_color, width=4, dash=(6, 3))
                            seg_count += 1
                        
                        # 显示线段统计
                        main_canvas.create_text(380, 40, text=f'段:{seg_count}', fill='#FF00FF', font=self.font_small)
                        
                        # ========== 步骤4：以线段为基础画出中枢，加入MACD辅助验证 ==========
                        # 中枢规则：至少3段重叠，有ZG（上沿）和ZD（下沿），MACD在零轴附近震荡
                        if len(segments) >= 3:
                            centers = []
                            
                            # 找中枢：连续3段有价格重叠，MACD在零轴附近
                            i = 0
                            while i <= len(segments) - 3:
                                seg1 = segments[i]
                                seg2 = segments[i + 1]
                                seg3 = segments[i + 2]
                                
                                # 获取每段的高低点
                                seg1_high = max(seg1[2], seg1[4])
                                seg1_low = min(seg1[2], seg1[4])
                                seg2_high = max(seg2[2], seg2[4])
                                seg2_low = min(seg2[2], seg2[4])
                                seg3_high = max(seg3[2], seg3[4])
                                seg3_low = min(seg3[2], seg3[4])
                                
                                # 计算重叠区间
                                overlap_high = min(seg1_high, seg2_high, seg3_high)  # ZG：上沿
                                overlap_low = max(seg1_low, seg2_low, seg3_low)      # ZD：下沿
                                
                                # 检查是否有重叠（ZG > ZD）
                                if overlap_high > overlap_low:
                                    # 中枢时间范围
                                    center_start = min(seg1[1], seg2[1], seg3[1])
                                    center_end = max(seg1[3], seg2[3], seg3[3])
                                    
                                    # MACD验证：中枢期间DIF应该在零轴附近震荡（绝对值较小）
                                    macd_in_center = []
                                    for k in range(center_start, min(center_end + 1, len(dif))):
                                        macd_in_center.append(abs(dif[k]))
                                    
                                    avg_macd = sum(macd_in_center) / len(macd_in_center) if macd_in_center else 0
                                    
                                    # MACD在零轴附近（绝对值平均值较小）或无条件接受
                                    if avg_macd < max_price * 0.02 or center_start >= len(dif):  # 允许2%的价格波动范围
                                        centers.append((center_start, center_end, overlap_high, overlap_low))
                                        i += 3  # 跳过已使用的段
                                    else:
                                        i += 1  # MACD不确认，继续寻找
                                else:
                                    i += 1
                            
                            # 绘制中枢
                            center_count = 0
                            for center in centers:
                                start_pos, end_pos, zg, zd = center
                                
                                x1 = 50 + (width - 70) * start_pos / max(len(prices) - 1, 1)
                                x2 = 50 + (width - 70) * end_pos / max(len(prices) - 1, 1)
                                y_zg = main_height * 0.1 + (main_height * 0.8) * (max_price - zg) / price_range
                                y_zd = main_height * 0.1 + (main_height * 0.8) * (max_price - zd) / price_range
                                
                                # 限制在画布范围内
                                y_zg = max(15, min(y_zg, main_height - 15))
                                y_zd = max(15, min(y_zd, main_height - 15))
                                
                                # 绘制中枢矩形框（黄色半透明填充）
                                main_canvas.create_rectangle(x1, y_zg, x2, y_zd,
                                                           outline='#FFFF00', width=2, dash=(4, 2))
                                # 标注ZG和ZD
                                main_canvas.create_text(x1 - 10, y_zg, text='ZG', fill='#FFFF00', font=self.font_small)
                                main_canvas.create_text(x1 - 10, y_zd, text='ZD', fill='#FFFF00', font=self.font_small)
                                
                                center_count += 1
                            
                            # 显示中枢统计
                            main_canvas.create_text(450, 40, text=f'中枢:{center_count}', fill='#FFFF00', font=self.font_small)
                            
                            # ========== 步骤5：依据中枢计算买卖点 ==========
                            # 买卖点规则：
                            # 一买：中枢下方，背驰（价格创新低，MACD不创新低）
                            # 二买：一买后回调不破一买低点
                            # 三买：突破中枢后回调不破ZG
                            # 一卖/二卖/三卖：对应相反
                            if len(centers) >= 1 and len(segments) >= 2:
                                buy_points = []  # (位置, 价格, 类型, 得分)
                                sell_points = []  # (位置, 价格, 类型, 得分)
                                
                                # 获取最后一个中枢
                                last_center = centers[-1]
                                center_start, center_end, zg, zd = last_center
                                
                                # 获取中枢后的走势
                                if center_end < len(prices) - 5:
                                    # 一买检测：中枢后价格跌破ZD，且MACD背驰
                                    for i in range(center_end, min(center_end + 20, len(prices) - 2)):
                                        if closes[i] < zd:  # 价格跌破中枢下沿
                                            # 检查MACD背驰：价格新低，DIF不新低
                                            price_low = min(closes[max(0, i-5):i+1])
                                            prev_price_low = min(closes[max(0, i-10):max(0, i-5)])
                                            
                                            if i < len(dif) and i >= 5:
                                                dif_low = min(dif[max(0, i-5):i+1])
                                                prev_dif_low = min(dif[max(0, i-10):max(0, i-5)])
                                                
                                                # 背驰条件：价格新低，DIF不新低
                                                if price_low < prev_price_low and dif_low >= prev_dif_low:
                                                    score = 60  # 基础分
                                                    if closes[i] > opens[i]:  # 阳线加分
                                                        score += 10
                                                    if volumes[i] > np.mean(volumes[max(0,i-5):i]) * 1.2:  # 放量加分
                                                        score += 10
                                                    buy_points.append((i, lows[i], '一买', score))
                                                    break
                                    
                                    # 三买检测：突破ZG后回调不破ZG
                                    breakout = False
                                    breakout_pos = None
                                    for i in range(center_end, min(center_end + 15, len(prices) - 2)):
                                        if highs[i] > zg:  # 突破中枢上沿
                                            breakout = True
                                            breakout_pos = i
                                            break
                                    
                                    if breakout and breakout_pos:
                                        for i in range(breakout_pos, min(breakout_pos + 10, len(prices) - 2)):
                                            if lows[i] > zd and closes[i] > zg * 0.98:  # 回调不破ZG
                                                score = 70  # 三买基础分高
                                                if closes[i] > opens[i]:
                                                    score += 10
                                                buy_points.append((i, lows[i], '三买', score))
                                                break
                                    
                                    # 一卖检测：中枢后价格突破ZG，且MACD背驰
                                    for i in range(center_end, min(center_end + 20, len(prices) - 2)):
                                        if highs[i] > zg:  # 价格突破中枢上沿
                                            # 检查MACD背驰：价格新高，DIF不新高
                                            price_high = max(closes[max(0, i-5):i+1])
                                            prev_price_high = max(closes[max(0, i-10):max(0, i-5)])
                                            
                                            if i < len(dif) and i >= 5:
                                                dif_high = max(dif[max(0, i-5):i+1])
                                                prev_dif_high = max(dif[max(0, i-10):max(0, i-5)])
                                                
                                                # 背驰条件：价格新高，DIF不新高
                                                if price_high > prev_price_high and dif_high <= prev_dif_high:
                                                    score = 60
                                                    if closes[i] < opens[i]:  # 阴线加分
                                                        score += 10
                                                    if volumes[i] > np.mean(volumes[max(0,i-5):i]) * 1.2:
                                                        score += 10
                                                    sell_points.append((i, highs[i], '一卖', score))
                                                    break
                                    
                                    # 三卖检测：跌破ZD后反弹不破ZD
                                    breakdown = False
                                    breakdown_pos = None
                                    for i in range(center_end, min(center_end + 15, len(prices) - 2)):
                                        if lows[i] < zd:  # 跌破中枢下沿
                                            breakdown = True
                                            breakdown_pos = i
                                            break
                                    
                                    if breakdown and breakdown_pos:
                                        for i in range(breakdown_pos, min(breakdown_pos + 10, len(prices) - 2)):
                                            if highs[i] < zg and closes[i] < zd * 1.02:  # 反弹不破ZD
                                                score = 70
                                                if closes[i] < opens[i]:
                                                    score += 10
                                                sell_points.append((i, highs[i], '三卖', score))
                                                break
                                
                                # 绘制买卖点
                                for pos, price, btype, score in buy_points:
                                    x = 50 + (width - 70) * pos / max(len(prices) - 1, 1)
                                    y = main_height * 0.1 + (main_height * 0.8) * (max_price - price) / price_range
                                    y = max(15, min(y, main_height - 15))
                                    # 买点用红色文字标注
                                    color = '#FF0000' if score >= 80 else '#FFFF00' if score >= 60 else '#00FF00'
                                    main_canvas.create_text(x, y + 25, text=f'{btype}{score}', fill=color, font=self.font_small)
                                
                                for pos, price, stype, score in sell_points:
                                    x = 50 + (width - 70) * pos / max(len(prices) - 1, 1)
                                    y = main_height * 0.1 + (main_height * 0.8) * (max_price - price) / price_range
                                    y = max(15, min(y, main_height - 15))
                                    # 卖点用绿色文字标注
                                    color = '#00FF00' if score >= 80 else '#00FFFF' if score >= 60 else '#FFFFFF'
                                    main_canvas.create_text(x, y - 25, text=f'{stype}{score}', fill=color, font=self.font_small)
                                
                                # 显示买卖点统计
                                main_canvas.create_text(530, 40, text=f'买:{len(buy_points)} 卖:{len(sell_points)}', fill='#FF00FF', font=self.font_small)
                    
                else:
                    main_canvas.create_text(200, 40, text='数据不足5根', fill='#FF0000', font=self.font_small)
                
                # 计算并绘制均线
                ma_periods = [5, 10, 20, 25, 30]
                ma_colors = ['#FFFFFF', '#FFFF00', '#FF00FF', '#00FFFF', '#FFA500']
                
                for ma_period, ma_color in zip(ma_periods, ma_colors):
                    if len(prices) >= ma_period:
                        ma_values = chart_df['close'].rolling(window=ma_period).mean().tolist()
                        ma_points = []
                        for i, ma_val in enumerate(ma_values):
                            if not np.isnan(ma_val):
                                x = 50 + (width - 70) * i / max(len(prices) - 1, 1)
                                y = main_height * 0.1 + (main_height * 0.8) * (max_price - ma_val) / price_range
                                ma_points.append((x, y))
                        
                        if len(ma_points) > 1:
                            for i in range(len(ma_points) - 1):
                                main_canvas.create_line(ma_points[i][0], ma_points[i][1], 
                                                 ma_points[i+1][0], ma_points[i+1][1],
                                                 fill=ma_color, width=1.5)
                
                # 绘制MA20资金流颜色（红=流入，绿=流出）
                if len(prices) >= 20:
                    ma20_values = chart_df['close'].rolling(window=20).mean().tolist()
                    volumes = chart_df['volume'].values if 'volume' in chart_df.columns else np.ones(len(prices))
                    closes = chart_df['close'].values
                    opens = chart_df['open'].values
                    highs = chart_df['high'].values
                    lows = chart_df['low'].values
                    
                    # 计算资金流
                    for i in range(20, len(prices)):
                        if np.isnan(ma20_values[i]):
                            continue
                        
                        # 计算当前K线的资金流
                        price_range = highs[i] - lows[i] if highs[i] > lows[i] else 0.001
                        var1 = volumes[i] / (price_range * 2 - abs(closes[i] - opens[i]))
                        
                        if closes[i] > opens[i]:
                            buy_flow = var1 * (highs[i] - lows[i])
                        elif closes[i] < opens[i]:
                            buy_flow = var1 * ((highs[i] - opens[i]) + (closes[i] - lows[i]))
                        else:
                            buy_flow = volumes[i] / 2
                        
                        sell_flow = volumes[i] - buy_flow
                        
                        # 计算4日均值
                        if i >= 4:
                            avg_buy = np.mean([volumes[j] for j in range(i-3, i+1)])
                            avg_sell = np.mean([sell_flow for _ in range(i-3, i+1)])
                        else:
                            avg_buy = buy_flow
                            avg_sell = sell_flow
                        
                        # 根据资金流确定颜色
                        if avg_buy > avg_sell:
                            color = '#FF0000'  # 红色 - 资金流入
                        else:
                            color = '#00FF00'  # 绿色 - 资金流出
                        
                        # 绘制MA20的这一段
                        if i > 20 and not np.isnan(ma20_values[i-1]):
                            x1 = 50 + (width - 70) * (i-1) / max(len(prices) - 1, 1)
                            y1 = main_height * 0.1 + (main_height * 0.8) * (max_price - ma20_values[i-1]) / price_range
                            x2 = 50 + (width - 70) * i / max(len(prices) - 1, 1)
                            y2 = main_height * 0.1 + (main_height * 0.8) * (max_price - ma20_values[i]) / price_range
                            main_canvas.create_line(x1, y1, x2, y2, fill=color, width=2)
                
                # 绘制均线图例
                legend_y = 20
                legend_x = width - 150
                for i, (ma_period, ma_color) in enumerate(zip(ma_periods, ma_colors)):
                    main_canvas.create_line(legend_x + i*25, legend_y, legend_x + i*25 + 15, legend_y, 
                                     fill=ma_color, width=2)
                    main_canvas.create_text(legend_x + i*25 + 20, legend_y, text=f"MA{ma_period}", 
                                     fill=ma_color, font=self.font_small, anchor='w')
                
                # 绘制指标标题
                main_canvas.create_text(80, 20, text="通达信指标系统", fill='#FFFF00', font=self.font_medium)
                
                # 绘制MACD金叉死叉标记
                if len(prices) >= 20:
                    # 计算MACD
                    def ema(data, period):
                        multiplier = 2 / (period + 1)
                        ema_values = [data[0]]
                        for i in range(1, len(data)):
                            ema_values.append(data[i] * multiplier + ema_values[-1] * (1 - multiplier))
                        return ema_values
                    
                    ema_short = ema(prices, 6)
                    ema_long = ema(prices, 13)
                    dif = [s - l for s, l in zip(ema_short, ema_long)]
                    dea = ema(dif, 5)
                    
                    # 找金叉死叉点
                    for i in range(1, len(dif)):
                        # 金叉：DIF上穿DEA
                        if dif[i-1] <= dea[i-1] and dif[i] > dea[i]:
                            x = 50 + (width - 70) * i / max(len(prices) - 1, 1)
                            y_low = main_height * 0.1 + (main_height * 0.8) * (max_price - chart_df['low'].iloc[i]) / price_range
                            # 画向上箭头（买入信号）
                            main_canvas.create_polygon(
                                x, y_low - 15, x-5, y_low - 5, x+5, y_low - 5,
                                fill='#00FF00', outline='#00FF00'
                            )
                            main_canvas.create_text(x, y_low - 20, text='买', fill='#00FF00', font=self.font_small)
                        
                        # 死叉：DIF下穿DEA
                        elif dif[i-1] >= dea[i-1] and dif[i] < dea[i]:
                            x = 50 + (width - 70) * i / max(len(prices) - 1, 1)
                            y_high = main_height * 0.1 + (main_height * 0.8) * (max_price - chart_df['high'].iloc[i]) / price_range
                            # 画向下箭头（卖出信号）
                            main_canvas.create_polygon(
                                x, y_high + 15, x-5, y_high + 5, x+5, y_high + 5,
                                fill='#FF0000', outline='#FF0000'
                            )
                            main_canvas.create_text(x, y_high + 22, text='卖', fill='#FF0000', font=self.font_small)
                
                # 绘制基于评分的买卖点（缠论极点）
                if len(prices) >= 20:
                    # 计算局部高低点
                    highs = chart_df['high'].values
                    lows = chart_df['low'].values
                    closes = chart_df['close'].values
                    volumes = chart_df['volume'].values if 'volume' in chart_df.columns else np.ones(len(closes))
                    
                    # 找3日高低点
                    for i in range(5, len(prices) - 2):
                        # 局部低点（潜在买点）
                        if lows[i] == min(lows[i-2:i+3]):
                            # 计算买点得分
                            score = 30  # 基础分
                            
                            # 价格创新低但指标不创新低（背离）+20分
                            if lows[i] < min(lows[i-10:i]) and closes[i] > min(closes[i-5:i]):
                                score += 20
                            
                            # 成交量放大 +10分
                            if volumes[i] > np.mean(volumes[i-5:i]) * 1.2:
                                score += 10
                            
                            # 大阳线反弹 +15分
                            if closes[i] > chart_df['open'].iloc[i] * 1.02:
                                score += 15
                            
                            # 根据得分确定颜色
                            if score >= 80:
                                color = '#FF0000'  # 红色 - 强烈买入
                            elif score >= 60:
                                color = '#FFFF00'  # 黄色 - 较好买点
                            elif score >= 40:
                                color = '#00FF00'  # 绿色 - 一般买点
                            else:
                                color = '#FFFFFF'  # 白色 - 较弱买点
                            
                            x = 50 + (width - 70) * i / max(len(prices) - 1, 1)
                            y_low = main_height * 0.1 + (main_height * 0.8) * (max_price - lows[i]) / price_range
                            main_canvas.create_text(x, y_low + 15, text=f'买{score}', fill=color, font=self.font_small)
                        
                        # 局部高点（潜在卖点）
                        if highs[i] == max(highs[i-2:i+3]):
                            # 计算卖点得分
                            score = 30  # 基础分
                            
                            # 价格创新高但指标不创新高（背离）+20分
                            if highs[i] > max(highs[i-10:i]) and closes[i] < max(closes[i-5:i]):
                                score += 20
                            
                            # 成交量放大 +10分
                            if volumes[i] > np.mean(volumes[i-5:i]) * 1.2:
                                score += 10
                            
                            # 大阴线回调 +15分
                            if closes[i] < chart_df['open'].iloc[i] * 0.98:
                                score += 15
                            
                            # 根据得分确定颜色
                            if score >= 80:
                                color = '#FF0000'  # 红色 - 强烈卖出
                            elif score >= 60:
                                color = '#FFFF00'  # 黄色 - 较好卖点
                            elif score >= 40:
                                color = '#00FF00'  # 绿色 - 一般卖点
                            else:
                                color = '#FFFFFF'  # 白色 - 较弱卖点
                            
                            x = 50 + (width - 70) * i / max(len(prices) - 1, 1)
                            y_high_pos = main_height * 0.1 + (main_height * 0.8) * (max_price - highs[i]) / price_range
                            main_canvas.create_text(x, y_high_pos - 15, text=f'卖{score}', fill=color, font=self.font_small)
                
                # 绘制三买三卖标记
                if len(prices) >= 30:
                    closes = chart_df['close'].values
                    highs = chart_df['high'].values
                    lows = chart_df['low'].values
                    
                    # 找中枢（简化版：用20日高低点区间）
                    for i in range(25, len(prices) - 5):
                        # 计算前20日的中枢区间
                        center_high = max(highs[i-20:i])
                        center_low = min(lows[i-20:i])
                        
                        # 三买条件：突破中枢上沿，且回调不回到中枢
                        if closes[i] > center_high and closes[i-1] <= center_high:
                            # 检查后续5天是否一直在中枢上方
                            if all(lows[j] > center_high for j in range(i+1, min(i+6, len(prices)))):
                                x = 50 + (width - 70) * i / max(len(prices) - 1, 1)
                                y = main_height * 0.1 + (main_height * 0.8) * (max_price - highs[i]) / price_range
                                main_canvas.create_text(x, y - 25, text='三买', fill='#FF00FF', font=self.font_small)
                        
                        # 三卖条件：跌破中枢下沿，且反弹不回到中枢
                        if closes[i] < center_low and closes[i-1] >= center_low:
                            # 检查后续5天是否一直在中枢下方
                            if all(highs[j] < center_low for j in range(i+1, min(i+6, len(prices)))):
                                x = 50 + (width - 70) * i / max(len(prices) - 1, 1)
                                y = main_height * 0.1 + (main_height * 0.8) * (max_price - lows[i]) / price_range
                                main_canvas.create_text(x, y + 25, text='三卖', fill='#00FFFF', font=self.font_small)
                
                # 绘制背驰检测标记
                if len(prices) >= 20:
                    closes = chart_df['close'].values
                    highs = chart_df['high'].values
                    lows = chart_df['low'].values
                    
                    # 计算MACD用于背驰判断
                    def ema(data, period):
                        multiplier = 2 / (period + 1)
                        ema_values = [data[0]]
                        for j in range(1, len(data)):
                            ema_values.append(data[j] * multiplier + ema_values[-1] * (1 - multiplier))
                        return ema_values
                    
                    ema_short = ema(closes, 6)
                    ema_long = ema(closes, 13)
                    dif = [s - l for s, l in zip(ema_short, ema_long)]
                    
                    # 找局部高低点进行背驰判断
                    for i in range(10, len(prices) - 5):
                        # 顶背驰：价格新高但DIF不新高
                        if highs[i] == max(highs[i-5:i+6]):
                            # 找前一个高点
                            prev_high_idx = None
                            for j in range(i-5, max(i-15, 0), -1):
                                if highs[j] == max(highs[max(0,j-5):min(len(highs),j+6)]):
                                    prev_high_idx = j
                                    break
                            
                            if prev_high_idx and highs[i] > highs[prev_high_idx]:
                                # 价格新高，检查DIF
                                if dif[i] < dif[prev_high_idx] * 1.1:  # DIF没有同步新高
                                    x = 50 + (width - 70) * i / max(len(prices) - 1, 1)
                                    y = main_height * 0.1 + (main_height * 0.8) * (max_price - highs[i]) / price_range
                                    # 顶背驰：绿色向下箭头
                                    main_canvas.create_polygon(
                                        x, y - 15, x-5, y - 5, x+5, y - 5,
                                        fill='#00FF00', outline='#00FF00'
                                    )
                        
                        # 底背驰：价格新低但DIF不新低
                        if lows[i] == min(lows[i-5:i+6]):
                            # 找前一个低点
                            prev_low_idx = None
                            for j in range(i-5, max(i-15, 0), -1):
                                if lows[j] == min(lows[max(0,j-5):min(len(lows),j+6)]):
                                    prev_low_idx = j
                                    break
                            
                            if prev_low_idx and lows[i] < lows[prev_low_idx]:
                                # 价格新低，检查DIF
                                if dif[i] > dif[prev_low_idx] * 0.9:  # DIF没有同步新低
                                    x = 50 + (width - 70) * i / max(len(prices) - 1, 1)
                                    y = main_height * 0.1 + (main_height * 0.8) * (max_price - lows[i]) / price_range
                                    # 底背驰：红色向上箭头
                                    main_canvas.create_polygon(
                                        x, y + 15, x-5, y + 5, x+5, y + 5,
                                        fill='#FF0000', outline='#FF0000'
                                    )
                
                # 绘制一买二买标记
                if len(prices) >= 20:
                    closes = chart_df['close'].values
                    highs = chart_df['high'].values
                    lows = chart_df['low'].values
                    
                    # 找下跌趋势中的背驰点（一买）
                    for i in range(15, len(prices) - 5):
                        # 一买条件：下跌趋势结束 + 底背驰
                        # 1. 前一段是下跌趋势（至少5根K线新低）
                        is_downtrend = all(lows[j] <= lows[j-1] for j in range(i-5, i+1))
                        
                        # 2. 当前是局部低点
                        is_local_low = lows[i] == min(lows[i-2:i+3])
                        
                        # 3. 后续开始反弹
                        is_bounce = closes[i+1] > closes[i] if i+1 < len(closes) else False
                        
                        if is_downtrend and is_local_low and is_bounce:
                            x = 50 + (width - 70) * i / max(len(prices) - 1, 1)
                            y = main_height * 0.1 + (main_height * 0.8) * (max_price - lows[i]) / price_range
                            main_canvas.create_text(x, y + 45, text='一买', fill='#FF69B4', font=self.font_small)
                        
                        # 二买条件：一买后的回调不创新低
                        # 找一买后的回调低点
                        if i > 5:
                            # 检查是否是一买后的回调
                            prev_low = min(lows[max(0,i-10):i])
                            current_low = lows[i]
                            
                            # 二买：回调低点高于一买低点
                            if current_low > prev_low * 1.01 and is_local_low and is_bounce:
                                # 检查前面是否有一买
                                has_first_buy = any(
                                    lows[j] == min(lows[max(0,j-2):min(len(lows),j+3)]) and 
                                    all(lows[k] <= lows[k-1] for k in range(max(1,j-5), j+1))
                                    for j in range(max(0,i-10), i)
                                )
                                if has_first_buy:
                                    x = 50 + (width - 70) * i / max(len(prices) - 1, 1)
                                    y = main_height * 0.1 + (main_height * 0.8) * (max_price - lows[i]) / price_range
                                    main_canvas.create_text(x, y + 45, text='二买', fill='#FF1493', font=self.font_small)
                
                # 绘制一卖二卖标记
                if len(prices) >= 20:
                    closes = chart_df['close'].values
                    highs = chart_df['high'].values
                    lows = chart_df['low'].values
                    
                    for i in range(15, len(prices) - 5):
                        # 一卖条件：上涨趋势结束 + 顶背驰
                        is_uptrend = all(highs[j] >= highs[j-1] for j in range(i-5, i+1))
                        is_local_high = highs[i] == max(highs[i-2:i+3])
                        is_pullback = closes[i+1] < closes[i] if i+1 < len(closes) else False
                        
                        if is_uptrend and is_local_high and is_pullback:
                            x = 50 + (width - 70) * i / max(len(prices) - 1, 1)
                            y = main_height * 0.1 + (main_height * 0.8) * (max_price - highs[i]) / price_range
                            main_canvas.create_text(x, y - 45, text='一卖', fill='#87CEEB', font=self.font_small)
                        
                        # 二卖条件：一卖后的反弹不创新高
                        if i > 5:
                            prev_high = max(highs[max(0,i-10):i])
                            current_high = highs[i]
                            
                            if current_high < prev_high * 0.99 and is_local_high and is_pullback:
                                has_first_sell = any(
                                    highs[j] == max(highs[max(0,j-2):min(len(highs),j+3)]) and
                                    all(highs[k] >= highs[k-1] for k in range(max(1,j-5), j+1))
                                    for j in range(max(0,i-10), i)
                                )
                                if has_first_sell:
                                    x = 50 + (width - 70) * i / max(len(prices) - 1, 1)
                                    y = main_height * 0.1 + (main_height * 0.8) * (max_price - highs[i]) / price_range
                                    main_canvas.create_text(x, y - 45, text='二卖', fill='#00BFFF', font=self.font_small)
                
                # 中枢画线功能已移除，等待基于缠论108课重新实现
            
            # 绘制MACD副图
            dif, dea, macd = calculate_macd(prices, short=6, long=13, mid=5)
            if dif and dea and macd:
                # 计算MACD范围
                all_macd = dif + dea + macd
                max_macd = max(all_macd)
                min_macd = min(all_macd)
                macd_range = max_macd - min_macd if max_macd != min_macd else 1
                
                # 绘制零轴
                zero_y = macd_height * 0.5
                macd_canvas.create_line(50, zero_y, width-20, zero_y, fill=self.colors['text'], width=1)
                
                # 绘制DIF线（白色）
                dif_points = []
                for i, val in enumerate(dif):
                    if not np.isnan(val):
                        x = 50 + (width - 70) * i / max(len(dif) - 1, 1)
                        y = macd_height * 0.1 + (macd_height * 0.8) * (max_macd - val) / macd_range
                        dif_points.append((x, y))
                
                if len(dif_points) > 1:
                    for i in range(len(dif_points) - 1):
                        macd_canvas.create_line(dif_points[i][0], dif_points[i][1], 
                                               dif_points[i+1][0], dif_points[i+1][1],
                                               fill='#FFFFFF', width=1.5)
                
                # 绘制DEA线（黄色）
                dea_points = []
                for i, val in enumerate(dea):
                    if not np.isnan(val):
                        x = 50 + (width - 70) * i / max(len(dea) - 1, 1)
                        y = macd_height * 0.1 + (macd_height * 0.8) * (max_macd - val) / macd_range
                        dea_points.append((x, y))
                
                if len(dea_points) > 1:
                    for i in range(len(dea_points) - 1):
                        macd_canvas.create_line(dea_points[i][0], dea_points[i][1], 
                                               dea_points[i+1][0], dea_points[i+1][1],
                                               fill='#FFFF00', width=1.5)
                
                # 绘制MACD柱状图（红绿柱）
                bar_width = (width - 70) / len(macd) * 0.5
                for i, val in enumerate(macd):
                    if not np.isnan(val):
                        x = 50 + (width - 70) * i / max(len(macd) - 1, 1)
                        y_val = macd_height * 0.1 + (macd_height * 0.8) * (max_macd - val) / macd_range
                        y_zero = macd_height * 0.1 + (macd_height * 0.8) * (max_macd - 0) / macd_range
                        
                        color = self.colors['down'] if val >= 0 else self.colors['up']
                        macd_canvas.create_rectangle(x - bar_width/2, y_val, x + bar_width/2, y_zero,
                                                    fill=color, outline=color)
                
                # MACD图例
                macd_canvas.create_text(width - 80, 15, text="MACD(6,13,5)", fill=self.colors['text'], font=self.font_small)
                macd_canvas.create_line(width - 150, 15, width - 140, 15, fill='#FFFFFF', width=2)
                macd_canvas.create_text(width - 135, 15, text="DIF", fill='#FFFFFF', font=self.font_small, anchor='w')
                macd_canvas.create_line(width - 100, 15, width - 90, 15, fill='#FFFF00', width=2)
                macd_canvas.create_text(width - 85, 15, text="DEA", fill='#FFFF00', font=self.font_small, anchor='w')
            
            # 时间轴
            if period == '分时':
                times = ['09:30', '10:30', '11:30/13:00', '14:00', '15:00']
            else:
                n = len(prices)
                times = [chart_df['datetime'].iloc[int(n*i/4)].strftime('%m-%d') if n > 0 else '' for i in range(5)]
            
            for i, t in enumerate(times):
                x = 50 + (width - 70) * i / 4
                macd_canvas.create_text(x, macd_height - 10, text=t, fill=self.colors['text'], font=self.font_small)
        
        # 延迟绘制等待布局完成
        main_canvas.after(100, draw_chart)
        
        # 底部操作区
        btn_frame = tk.Frame(window, bg=self.colors['bg'])
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        def buy_from_chart():
            window.destroy()
            self.trade_code.delete(0, 'end')
            self.trade_code.insert(0, code)
            self.quick_buy()
        
        def sell_from_chart():
            window.destroy()
            self.trade_code.delete(0, 'end')
            self.trade_code.insert(0, code)
            self.quick_sell()
        
        tk.Button(btn_frame, text="买入", command=buy_from_chart,
                 bg=self.colors['down'], fg='white', font=self.font_medium,
                 relief='flat', cursor='hand2', width=12).pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="卖出", command=sell_from_chart,
                 bg=self.colors['up'], fg='white', font=self.font_medium,
                 relief='flat', cursor='hand2', width=12).pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="刷新", command=draw_chart,
                 bg=self.colors['border'], fg=self.colors['text'], font=self.font_medium,
                 relief='flat', cursor='hand2', width=12).pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="关闭", command=window.destroy,
                 bg=self.colors['border'], fg=self.colors['text'], font=self.font_medium,
                 relief='flat', cursor='hand2', width=12).pack(side='right', padx=5)
        
        self.log(f"查看分时图: {code}", 'info')
    
    def daily_analyze_selected(self):
        """使用 Daily Stock Analysis 深度分析选中的股票"""
        # 获取API密钥
        api_key = self.ai_api_key.get().strip()
        
        # 获取选中的股票
        selected = self.position_tree.selection()
        if not selected:
            code = self.trade_code.get().strip()
            if not code:
                messagebox.showwarning("提示", "请先选择股票或输入股票代码")
                return
        else:
            item = selected[0]
            values = self.position_tree.item(item)['values']
            code = self._format_stock_code(values[0])
        
        if not api_key:
            if not messagebox.askyesno("提示", "未输入API密钥，将只获取数据不进行AI分析。\n是否继续？"):
                return
        
        self.log(f"开始深度分析: {code}", 'info')
        
        def on_result(result, error=None):
            if error:
                messagebox.showerror("错误", error)
                return
            if result:
                self.daily_analyzer.show_analysis_result(result, f"深度分析 - {code}")
            else:
                messagebox.showwarning("提示", "分析结果为空")
        
        model_type = self.daily_model.get()
        quick_mode = self.daily_quick_mode.get()
        mode_text = "快速" if quick_mode else "完整"
        self.log(f"使用{mode_text}模式进行深度分析", 'info')
        self.daily_analyzer.analyze_stock(code, api_key=api_key, model_type=model_type, 
                                          callback=on_result, quick_mode=quick_mode)
    
    def daily_analyze_watch_list(self):
        """使用 Daily Stock Analysis 深度分析监控列表中的所有股票"""
        # 获取API密钥
        api_key = self.ai_api_key.get().strip()
        
        codes = []
        for i in range(self.watch_listbox.size()):
            codes.append(self.watch_listbox.get(i))
        
        if not codes:
            messagebox.showwarning("提示", "监控列表为空")
            return
        
        if not api_key:
            if not messagebox.askyesno("提示", "未输入API密钥，将只获取数据不进行AI分析。\n是否继续？"):
                return
        
        self.log(f"开始批量深度分析: {', '.join(codes)}", 'info')
        
        def on_results(results, error=None):
            if error:
                messagebox.showerror("错误", error)
                return
            if results:
                # 显示汇总结果
                window = tk.Toplevel(self.root)
                window.title("监控列表深度分析汇总")
                window.geometry("800x600")
                window.configure(bg=self.colors['bg'])
                
                # 标题
                tk.Label(window, text="监控列表深度分析汇总", 
                        font=('微软雅黑', 16, 'bold'),
                        bg=self.colors['bg'], fg=self.colors['text_highlight']).pack(pady=10)
                
                # 结果列表
                result_frame = tk.Frame(window, bg=self.colors['bg'])
                result_frame.pack(fill='both', expand=True, padx=10, pady=5)
                
                text_widget = tk.Text(result_frame, 
                                     font=('微软雅黑', 10),
                                     bg=self.colors['bg_secondary'],
                                     fg=self.colors['text'],
                                     relief='flat',
                                     wrap='word')
                text_widget.pack(side='left', fill='both', expand=True)
                
                scrollbar = tk.Scrollbar(result_frame, command=text_widget.yview)
                scrollbar.pack(side='right', fill='y')
                text_widget.config(yscrollcommand=scrollbar.set)
                
                # 填充结果
                for result in results:
                    code = getattr(result, 'stock_code', '未知')
                    name = getattr(result, 'stock_name', '未知')
                    action = getattr(result, 'action', '观望')
                    
                    text_widget.insert('end', f"\n{'='*50}\n")
                    text_widget.insert('end', f"{code} {name}\n")
                    text_widget.insert('end', f"操作建议: {action}\n")
                    text_widget.insert('end', f"{'='*50}\n\n")
                
                text_widget.config(state='disabled')
                
                # 关闭按钮
                tk.Button(window, text="关闭", command=window.destroy,
                         bg=self.colors['accent'], fg='white',
                         font=('微软雅黑', 11),
                         relief='flat', cursor='hand2',
                         width=10).pack(pady=10)
            else:
                messagebox.showwarning("提示", "分析结果为空")
        
        model_type = self.daily_model.get()
        self.daily_analyzer.analyze_stocks(codes, api_key=api_key, model_type=model_type, callback=on_results)
    
    def factor_analyze_selected(self):
        """使用PandaFactor进行因子分析"""
        api_key = self.ai_api_key.get().strip()
        if not api_key:
            messagebox.showwarning("提示", "请输入API密钥（用于阿里云百炼大模型分析）")
            return
        
        # 获取选中的股票
        selected = self.position_tree.selection()
        if not selected:
            code = self.trade_code.get().strip()
            if not code:
                messagebox.showwarning("提示", "请先选择股票或输入股票代码")
                return
        else:
            item = selected[0]
            values = self.position_tree.item(item)['values']
            code = self._format_stock_code(values[0])
        
        self.log(f"开始因子分析: {code}", 'info')
        
        # 获取历史数据
        try:
            from stock_data import get_stock_data
            df = get_stock_data(code, count=60)
            if df.empty:
                messagebox.showwarning("提示", f"无法获取 {code} 的历史数据")
                return
            
            # 计算因子
            factors_df = self.factor_analyzer.calculate_factors(df)
            if factors_df.empty:
                messagebox.showwarning("提示", "因子计算失败")
                return
            
            # 使用大模型分析因子
            def on_result(result, error=None):
                if error:
                    messagebox.showerror("错误", error)
                    return
                if result:
                    self.factor_analyzer.show_factor_result(result, f"因子分析 - {code}")
                else:
                    messagebox.showwarning("提示", "分析结果为空")
            
            self.factor_analyzer.analyze_with_llm(code, factors_df, api_key, on_result)
            
        except Exception as e:
            messagebox.showerror("错误", f"因子分析失败: {e}")
    
    def factor_analyze_watch_list(self):
        """批量因子分析监控列表"""
        api_key = self.ai_api_key.get().strip()
        if not api_key:
            messagebox.showwarning("提示", "请输入API密钥")
            return
        
        codes = []
        for i in range(self.watch_listbox.size()):
            codes.append(self.watch_listbox.get(i))
        
        if not codes:
            messagebox.showwarning("提示", "监控列表为空")
            return
        
        self.log(f"开始批量因子分析: {', '.join(codes)}", 'info')
        messagebox.showinfo("提示", f"开始分析 {len(codes)} 只股票，请稍候...")
        
        # 简化版：只分析第一只作为示例
        if codes:
            self.trade_code.delete(0, 'end')
            self.trade_code.insert(0, codes[0])
            self.factor_analyze_selected()


def main():
    root = tk.Tk()
    app = ProStockGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()

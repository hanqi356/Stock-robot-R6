# -*- coding: utf-8 -*-
"""
Daily Stock Analysis 整合模块
集成OpenClaw Skills: 交易记录、投资组合、税务报告、预算控制
集成Polymarket预测市场数据
"""

import os
import threading
import tkinter as tk
from tkinter import messagebox, Toplevel, Text, Scrollbar
import json
from datetime import datetime

# 项目根目录
PROJECT_ROOT = os.path.dirname(__file__)

# OpenClaw Skills 数据存储路径
OPENCLAW_DATA_PATH = os.path.join(os.path.dirname(__file__), 'openclaw_data')
os.makedirs(OPENCLAW_DATA_PATH, exist_ok=True)

# 导入Polymarket集成
try:
    from polymarket_integration import PolymarketClient
    POLYMARKET_AVAILABLE = True
except ImportError:
    POLYMARKET_AVAILABLE = False

# 交易记录文件
TRADE_RECORDS_FILE = os.path.join(OPENCLAW_DATA_PATH, 'trade_records.json')
# 投资组合文件
PORTFOLIO_FILE = os.path.join(OPENCLAW_DATA_PATH, 'portfolio.json')
# 预算文件
BUDGET_FILE = os.path.join(OPENCLAW_DATA_PATH, 'budget.json')


class DailyAnalysisIntegration:
    """Daily Stock Analysis 整合类 - 命令行方式
    集成OpenClaw Skills功能
    """
    
    def __init__(self, parent_window=None, colors=None):
        self.parent = parent_window
        self.colors = colors or {
            'bg': '#0d1117',
            'bg_secondary': '#161b22',
            'text': '#c9d1d9',
            'text_highlight': '#ffffff',
            'accent': '#58a6ff',
            'up': '#f85149',
            'down': '#3fb950'
        }
        self.analysis_thread = None
        
        # 初始化OpenClaw Skills数据
        self._init_openclaw_data()
    
    def _init_openclaw_data(self):
        """初始化OpenClaw Skills数据文件"""
        # 初始化交易记录
        if not os.path.exists(TRADE_RECORDS_FILE):
            with open(TRADE_RECORDS_FILE, 'w', encoding='utf-8') as f:
                json.dump([], f)
        
        # 初始化投资组合
        if not os.path.exists(PORTFOLIO_FILE):
            with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
                json.dump({'holdings': {}, 'history': []}, f)
        
        # 初始化预算
        if not os.path.exists(BUDGET_FILE):
            with open(BUDGET_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    'total_budget': 100000,
                    'used_budget': 0,
                    'monthly_limit': 20000,
                    'categories': {
                        '股票买入': {'limit': 20000, 'used': 0},
                        '税费': {'limit': 5000, 'used': 0}
                    }
                }, f)
    
    # ==================== OpenClaw Skills: 交易记录管理 ====================
    
    def record_trade(self, stock_code: str, action: str, price: float, 
                     quantity: int, date: str = None):
        """记录交易 - expense-tracker-pro功能
        
        Args:
            stock_code: 股票代码
            action: 买入/卖出
            price: 成交价格
            quantity: 成交数量
            date: 交易日期(默认今天)
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        trade = {
            'date': date,
            'stock_code': stock_code,
            'action': action,
            'price': price,
            'quantity': quantity,
            'amount': price * quantity,
            'timestamp': datetime.now().isoformat()
        }
        
        # 读取现有记录
        with open(TRADE_RECORDS_FILE, 'r', encoding='utf-8') as f:
            records = json.load(f)
        
        records.append(trade)
        
        # 保存记录
        with open(TRADE_RECORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        
        # 更新投资组合
        self._update_portfolio(trade)
        
        # 更新预算
        self._update_budget(trade)
        
        return trade
    
    def get_trade_records(self, stock_code: str = None, days: int = 30):
        """获取交易记录
        
        Args:
            stock_code: 筛选特定股票(可选)
            days: 最近N天
        """
        try:
            with open(TRADE_RECORDS_FILE, 'r', encoding='utf-8') as f:
                records = json.load(f)
            
            # 筛选
            from datetime import timedelta
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            filtered = [r for r in records if r.get('date', '') >= cutoff_date]
            if stock_code:
                filtered = [r for r in filtered if r.get('stock_code') == stock_code]
            
            return filtered
        except Exception as e:
            print(f"获取交易记录失败: {e}")
            return []
    
    # ==================== OpenClaw Skills: 投资组合分析 ====================
    
    def _update_portfolio(self, trade: dict):
        """更新投资组合"""
        with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
            portfolio = json.load(f)
        
        stock_code = trade['stock_code']
        action = trade['action']
        quantity = trade['quantity']
        price = trade['price']
        amount = trade['amount']
        
        if stock_code not in portfolio['holdings']:
            portfolio['holdings'][stock_code] = {
                'quantity': 0,
                'cost_basis': 0,
                'trades': []
            }
        
        holding = portfolio['holdings'][stock_code]
        
        if action == '买入':
            total_cost = holding['cost_basis'] * holding['quantity'] + amount
            holding['quantity'] += quantity
            holding['cost_basis'] = total_cost / holding['quantity'] if holding['quantity'] > 0 else 0
        elif action == '卖出':
            holding['quantity'] -= quantity
            if holding['quantity'] <= 0:
                holding['quantity'] = 0
                holding['cost_basis'] = 0
        
        holding['trades'].append(trade)
        portfolio['history'].append(trade)
        
        with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
            json.dump(portfolio, f, ensure_ascii=False, indent=2)
    
    def get_portfolio_summary(self):
        """获取投资组合摘要 - sure功能"""
        try:
            with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
                portfolio = json.load(f)
            
            holdings = portfolio.get('holdings', {})
            history = portfolio.get('history', [])
            
            # 计算统计数据
            total_trades = len(history)
            buy_trades = len([h for h in history if h.get('action') == '买入'])
            sell_trades = len([h for h in history if h.get('action') == '卖出'])
            
            total_invested = sum(h.get('amount', 0) for h in history if h.get('action') == '买入')
            total_sold = sum(h.get('amount', 0) for h in history if h.get('action') == '卖出')
            
            # 当前持仓
            current_holdings = []
            for code, data in holdings.items():
                if data.get('quantity', 0) > 0:
                    current_holdings.append({
                        'stock_code': code,
                        'quantity': data.get('quantity', 0),
                        'cost_basis': data.get('cost_basis', 0),
                        'total_cost': data.get('quantity', 0) * data.get('cost_basis', 0)
                    })
            
            return {
                'total_trades': total_trades,
                'buy_trades': buy_trades,
                'sell_trades': sell_trades,
                'total_invested': total_invested,
                'total_sold': total_sold,
                'net_investment': total_invested - total_sold,
                'current_holdings': current_holdings,
                'holding_count': len(current_holdings)
            }
        except Exception as e:
            print(f"获取投资组合摘要失败: {e}")
            return {
                'total_trades': 0,
                'buy_trades': 0,
                'sell_trades': 0,
                'total_invested': 0,
                'total_sold': 0,
                'net_investment': 0,
                'current_holdings': [],
                'holding_count': 0
            }
    
    # ==================== OpenClaw Skills: 税务报告 ====================
    
    def calculate_tax_report(self, year: int = None):
        """计算税务报告 - tax-professional功能
        
        Args:
            year: 年份(默认当前年)
        """
        try:
            if year is None:
                year = datetime.now().year
            
            with open(TRADE_RECORDS_FILE, 'r', encoding='utf-8') as f:
                records = json.load(f)
            
            # 筛选当年卖出记录
            year_records = [r for r in records if r.get('date', '').startswith(str(year)) and r.get('action') == '卖出']
            
            # 计算收益
            total_gain = 0
            total_loss = 0
            
            for record in year_records:
                # 获取对应买入成本
                cost_basis = self._get_cost_basis(record.get('stock_code', ''), record.get('date', ''))
                gain = (record.get('price', 0) - cost_basis) * record.get('quantity', 0)
                
                if gain > 0:
                    total_gain += gain
                else:
                    total_loss += abs(gain)
            
            net_gain = total_gain - total_loss
            # 中国A股税率：盈利部分20%(暂免)，这里按10%计算预估
            estimated_tax = max(0, net_gain * 0.1)
            
            return {
                'year': year,
                'total_gain': total_gain,
                'total_loss': total_loss,
                'net_gain': net_gain,
                'estimated_tax': estimated_tax,
                'sell_records': len(year_records)
            }
        except Exception as e:
            print(f"计算税务报告失败: {e}")
            return {
                'year': year or datetime.now().year,
                'total_gain': 0,
                'total_loss': 0,
                'net_gain': 0,
                'estimated_tax': 0,
                'sell_records': 0
            }
    
    def _get_cost_basis(self, stock_code: str, before_date: str):
        """获取股票成本基础"""
        with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
            portfolio = json.load(f)
        
        if stock_code in portfolio['holdings']:
            return portfolio['holdings'][stock_code].get('cost_basis', 0)
        return 0
    
    # ==================== OpenClaw Skills: 预算控制 ====================
    
    def _update_budget(self, trade: dict):
        """更新预算使用情况"""
        with open(BUDGET_FILE, 'r', encoding='utf-8') as f:
            budget = json.load(f)
        
        amount = trade['amount']
        
        if trade['action'] == '买入':
            budget['used_budget'] += amount
            budget['categories']['股票买入']['used'] += amount
        
        with open(BUDGET_FILE, 'w', encoding='utf-8') as f:
            json.dump(budget, f, ensure_ascii=False, indent=2)
    
    def get_budget_status(self):
        """获取预算状态 - ynab功能"""
        try:
            with open(BUDGET_FILE, 'r', encoding='utf-8') as f:
                budget = json.load(f)
            
            total_budget = budget.get('total_budget', 100000)
            used_budget = budget.get('used_budget', 0)
            remaining = total_budget - used_budget
            
            categories = budget.get('categories', {})
            stock_budget = categories.get('股票买入', {'limit': 20000, 'used': 0})
            tax_budget = categories.get('税费', {'limit': 5000, 'used': 0})
            
            return {
                'total_budget': total_budget,
                'used_budget': used_budget,
                'remaining': remaining,
                'usage_rate': (used_budget / total_budget * 100) if total_budget > 0 else 0,
                'stock_buy': {
                    'limit': stock_budget.get('limit', 20000),
                    'used': stock_budget.get('used', 0),
                    'remaining': stock_budget.get('limit', 20000) - stock_budget.get('used', 0)
                },
                'tax': {
                    'limit': tax_budget.get('limit', 5000),
                    'used': tax_budget.get('used', 0),
                    'remaining': tax_budget.get('limit', 5000) - tax_budget.get('used', 0)
                }
            }
        except Exception as e:
            print(f"获取预算状态失败: {e}")
            return {
                'total_budget': 100000,
                'used_budget': 0,
                'remaining': 100000,
                'usage_rate': 0,
                'stock_buy': {'limit': 20000, 'used': 0, 'remaining': 20000},
                'tax': {'limit': 5000, 'used': 0, 'remaining': 5000}
            }
    
    def check_budget_before_trade(self, amount: float):
        """检查是否有足够预算进行交易"""
        budget = self.get_budget_status()
        return budget['stock_buy']['remaining'] >= amount
        
    def analyze_stock(self, stock_code: str, api_key: str = None, model_type: str = 'gemini', 
                       callback=None, quick_mode: bool = True):
        """通过命令行分析单只股票
        
        Args:
            stock_code: 股票代码
            api_key: API密钥（从GUI输入框传入）
            model_type: 模型类型（gemini/openai/deepseek）
            callback: 回调函数
            quick_mode: 快速模式（跳过大盘分析，只分析单股）
        """
        def run_analysis():
            try:
                # 构建环境变量
                env = os.environ.copy()
                if api_key:
                    if model_type == 'gemini':
                        env['GEMINI_API_KEY'] = api_key
                    elif model_type == 'openai':
                        env['OPENAI_API_KEY'] = api_key
                    elif model_type == 'deepseek':
                        env['OPENAI_API_KEY'] = api_key
                        env['OPENAI_BASE_URL'] = 'https://api.deepseek.com/v1'
                        env['OPENAI_MODEL'] = 'deepseek-chat'
                    elif model_type == 'aliyun':
                        # 阿里云百炼 - OpenAI兼容模式
                        env['OPENAI_API_KEY'] = api_key
                        env['OPENAI_BASE_URL'] = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
                        env['OPENAI_MODEL'] = 'qwen-max'
                
                # 根据模式执行分析
                if quick_mode:
                    # 快速模式：直接使用内置数据源，计算更多指标
                    try:
                        import sys
                        sys.path.insert(0, os.path.dirname(__file__))
                        from stock_data import get_stock_data
                        from MyTT import MACD, KDJ, RSI, BOLL
                        
                        df = get_stock_data(stock_code, count=100)
                        if df.empty or len(df) < 30:
                            raise Exception(f"无法获取 {stock_code} 的数据或数据不足")
                        
                        close = df['close'].values
                        high = df['high'].values
                        low = df['low'].values
                        vol = df['vol'].values
                        
                        # 计算均线
                        df['ma5'] = df['close'].rolling(5).mean()
                        df['ma10'] = df['close'].rolling(10).mean()
                        df['ma20'] = df['close'].rolling(20).mean()
                        df['ma60'] = df['close'].rolling(60).mean()
                        
                        # 计算技术指标
                        dif, dea, macd = MACD(close)
                        k, d, j = KDJ(close, high, low)
                        rsi = RSI(close, 14)
                        upper, mid, lower = BOLL(close)
                        
                        # 计算资金流向指标
                        df['vol_ma5'] = df['vol'].rolling(5).mean()
                        df['vol_ma20'] = df['vol'].rolling(20).mean()
                        
                        # 价格变动
                        price_change = (close[-1] - close[-2]) / close[-2] * 100
                        price_change_5d = (close[-1] - close[-5]) / close[-5] * 100
                        price_change_20d = (close[-1] - close[-20]) / close[-20] * 100
                        
                        # 成交量变动
                        vol_ratio = vol[-1] / df['vol_ma20'].iloc[-1] if df['vol_ma20'].iloc[-1] > 0 else 0
                        
                        # 波动率
                        volatility = df['close'].rolling(20).std().iloc[-1] / df['close'].rolling(20).mean().iloc[-1] * 100
                        
                        latest = df.iloc[-1]
                        
                        # 获取日期
                        if 'datetime' in df.columns:
                            last_date = df['datetime'].iloc[-1]
                        else:
                            last_date = str(df.index[-1])
                        
                        # 趋势判断
                        trend = "多头"
                        if latest['ma5'] < latest['ma10'] < latest['ma20']:
                            trend = "空头"
                        elif latest['ma5'] > latest['ma10'] and latest['close'] > latest['ma20']:
                            trend = "强势"
                        elif latest['close'] < latest['ma20']:
                            trend = "弱势"
                        
                        # 生成投资建议结论
                        action = "观望"
                        reasons = []
                        
                        # 基于趋势判断
                        if trend == "强势":
                            action = "买入"
                            reasons.append("趋势强势，均线多头排列")
                        elif trend == "多头":
                            action = "持有"
                            reasons.append("趋势向上")
                        elif trend == "空头":
                            action = "卖出"
                            reasons.append("趋势空头，均线空头排列")
                        elif trend == "弱势":
                            action = "观望"
                            reasons.append("趋势弱势")
                        
                        # 基于MACD
                        if macd[-1] > 0 and macd[-1] > macd[-2]:
                            if action != "买入":
                                action = "买入"
                            reasons.append("MACD红柱放大，动能增强")
                        elif macd[-1] < 0 and macd[-1] < macd[-2]:
                            if action not in ["卖出"]:
                                action = "卖出"
                            reasons.append("MACD绿柱放大，动能减弱")
                        
                        # 基于RSI
                        if rsi[-1] > 70:
                            if action == "买入":
                                action = "观望"
                            reasons.append("RSI超买")
                        elif rsi[-1] < 30:
                            if action == "卖出":
                                action = "观望"
                            reasons.append("RSI超卖")
                        
                        # 基于成交量
                        if vol_ratio > 2:
                            reasons.append("大幅放量，资金关注")
                        elif vol_ratio < 0.5:
                            reasons.append("缩量整理")
                        
                        # 基于KDJ
                        if j[-1] > 100:
                            reasons.append("KDJ超买")
                        elif j[-1] < 0:
                            reasons.append("KDJ超卖")
                        
                        # 通达信选股评分
                        tdx_score_str = ""
                        try:
                            from tdx_stock_picker import TDXStockPicker
                            picker = TDXStockPicker(df)
                            score_result = picker.get_latest_score()
                            
                            score = score_result['score']
                            components = score_result['components']
                            signals = score_result['signals']
                            
                            # 根据评分调整建议
                            if score >= 80 and action != "买入":
                                action = "买入"
                                reasons.append(f"通达信评分高达{score}分，强烈买入信号")
                            elif score >= 60 and action == "观望":
                                action = "关注"
                                reasons.append(f"通达信评分{score}分，值得关注")
                            elif score < 30 and action not in ["卖出"]:
                                action = "卖出"
                                reasons.append(f"通达信评分仅{score}分，卖出信号")
                            
                            tdx_score_str = f"""
【通达信选股评分】
综合评分: {score}分 (0-100分制)
评分等级: {'强烈买入' if score >= 80 else '买入' if score >= 60 else '观望' if score >= 40 else '卖出' if score >= 20 else '强烈卖出'}

评分构成:
  中枢背离: +{components['中枢背离']}分
  笔背离: +{components['笔背离']}分
  衰竭信号: +{components['衰竭']}分
  强分型: +{components['强分型']}分
  MACD金叉: +{components['MACD']}分
  均线金叉: +{components['均线']}分

技术信号:
  顶分型: {'是' if signals['顶分型'] else '否'}
  底分型: {'是' if signals['底分型'] else '否'}
  MACD金叉: {'是' if signals['MACD金叉'] else '否'}
  均线金叉: {'是' if signals['均线金叉'] else '否'}

缠论数据:
  中枢上沿: {score_result['zhongshu_upper']:.2f}
  中枢下沿: {score_result['zhongshu_lower']:.2f}
  当前位置: {'中枢上方' if latest['close'] > score_result['zhongshu_upper'] else '中枢下方' if latest['close'] < score_result['zhongshu_lower'] else '中枢内部'}
"""
                        except Exception as e:
                            tdx_score_str = f"\n【通达信选股评分】\n评分计算失败: {str(e)}\n"
                        
                        # 获取OpenClaw Skills数据
                        try:
                            portfolio = self.get_portfolio_summary()
                            if portfolio is None:
                                portfolio = {}
                            
                            budget = self.get_budget_status()
                            if budget is None:
                                budget = {}
                            
                            tax_report = self.calculate_tax_report()
                            if tax_report is None:
                                tax_report = {}
                            
                            recent_trades = self.get_trade_records(stock_code, days=30)
                            if recent_trades is None:
                                recent_trades = []
                            
                            # 计算该股票持仓
                            stock_holding = None
                            holdings = portfolio.get('current_holdings', []) or []
                            for h in holdings:
                                if h.get('stock_code') == stock_code:
                                    stock_holding = h
                                    break
                            
                            # 计算该股票盈亏
                            stock_pnl = 0
                            if stock_holding:
                                qty = stock_holding.get('quantity', 0)
                                cost = stock_holding.get('cost_basis', 0)
                                current_value = qty * latest['close']
                                cost_value = qty * cost
                                stock_pnl = current_value - cost_value
                            
                            # 安全获取预算信息
                            stock_buy_budget = budget.get('stock_buy', {}) or {}
                            can_buy = stock_buy_budget.get('remaining', 0) >= latest['close'] * 100
                            
                            openclaw_str = f"""
【交易记录管理】
最近30天交易次数: {len(recent_trades) if recent_trades else 0}
当前持仓数量: {stock_holding.get('quantity', 0) if stock_holding else 0}股
持仓成本: {(stock_holding.get('cost_basis', 0) if stock_holding else 0):.2f}
当前盈亏: {stock_pnl:+.2f}元

【投资组合分析】
总交易次数: {portfolio.get('total_trades', 0)}
买入次数: {portfolio.get('buy_trades', 0)}
卖出次数: {portfolio.get('sell_trades', 0)}
累计投入: {portfolio.get('total_invested', 0):,.2f}元
累计卖出: {portfolio.get('total_sold', 0):,.2f}元
净投入: {portfolio.get('net_investment', 0):,.2f}元
当前持仓股票数: {portfolio.get('holding_count', 0)}

【税务报告】
本年度卖出次数: {tax_report.get('sell_records', 0)}
已实现盈利: {tax_report.get('total_gain', 0):,.2f}元
已实现亏损: {tax_report.get('total_loss', 0):,.2f}元
净收益: {tax_report.get('net_gain', 0):+.2f}元
预估税费: {tax_report.get('estimated_tax', 0):,.2f}元

【预算控制】
总预算: {budget.get('total_budget', 0):,.0f}元
已使用: {budget.get('used_budget', 0):,.2f}元 ({budget.get('usage_rate', 0):.1f}%)
剩余预算: {budget.get('remaining', 0):,.2f}元
股票买入预算: {stock_buy_budget.get('limit', 0):,.0f}元 (已用{stock_buy_budget.get('used', 0):,.2f}元, 剩余{stock_buy_budget.get('remaining', 0):,.2f}元)
是否可买入(100股): {'是' if can_buy else '否(预算不足)'}
"""
                        except Exception as e:
                            openclaw_str = f"\n【投资管理数据】\n数据加载失败: {str(e)}\n"
                        
                        # 获取Polymarket预测市场数据
                        polymarket_str = ""
                        if POLYMARKET_AVAILABLE:
                            try:
                                pm_client = PolymarketClient()
                                # 搜索与股票相关的预测市场
                                pm_markets = pm_client.search_markets(stock_code[:2], limit=3)
                                
                                if pm_markets:
                                    polymarket_str = "\n【Polymarket预测市场】\n"
                                    for i, market in enumerate(pm_markets[:3], 1):
                                        polymarket_str += f"""
{i}. {market['question'][:50]}...
   类别: {market['category']}
   24h交易量: ${market['volume_24h']:,.0f}
   最佳价格: {market['best_price']:.4f}
   选项: {', '.join(market['outcomes'][:2])}
"""
                                else:
                                    # 获取热门市场
                                    hot_markets = pm_client.get_trending_markets(2)
                                    if hot_markets:
                                        polymarket_str = "\n【Polymarket热门预测市场】\n"
                                        for i, market in enumerate(hot_markets[:2], 1):
                                            polymarket_str += f"""
{i}. {market['question'][:50]}...
   类别: {market['category']}
   24h交易量: ${market['volume_24h']:,.0f}
"""
                            except Exception as e:
                                polymarket_str = f"\n【Polymarket数据】\n获取失败: {str(e)}\n"
                        
                        result_str = f"""【投资建议】
操作建议: {action}
理由: {'; '.join(reasons) if reasons else '技术指标中性，建议观望'}

【基础行情】
股票代码: {stock_code}
最新日期: {last_date}
最新价格: {latest['close']:.2f}
涨跌(1日): {price_change:+.2f}%
涨跌(5日): {price_change_5d:+.2f}%
涨跌(20日): {price_change_20d:+.2f}%

【均线系统】
5日均线: {latest['ma5']:.2f} ({'上' if latest['close'] > latest['ma5'] else '下'})
10日均线: {latest['ma10']:.2f}
20日均线: {latest['ma20']:.2f}
60日均线: {latest['ma60']:.2f}
趋势判断: {trend}

【技术指标】
MACD: DIF={dif[-1]:.3f}, DEA={dea[-1]:.3f}, MACD={macd[-1]:.3f}
KDJ: K={k[-1]:.2f}, D={d[-1]:.2f}, J={j[-1]:.2f}
RSI(14): {rsi[-1]:.2f}
布林带: 上轨={upper[-1]:.2f}, 中轨={mid[-1]:.2f}, 下轨={lower[-1]:.2f}

【资金面】
成交量: {latest['vol']:,.0f}
量比: {vol_ratio:.2f} ({'放量' if vol_ratio > 1.5 else '缩量' if vol_ratio < 0.8 else '正常'})
20日波动率: {volatility:.2f}%

【位置评估】
相对布林带: {(latest['close']-lower[-1])/(upper[-1]-lower[-1])*100:.1f}%
{tdx_score_str}{openclaw_str}{polymarket_str}
"""
                        
                        # 构建结果对象
                        class SimpleResult:
                            def __init__(self, code, summary, analysis):
                                self.stock_code = code
                                self.stock_name = code
                                self.summary = summary
                                self.analysis = analysis
                                self.action = "数据获取完成"
                        
                        result = SimpleResult(
                            stock_code, 
                            {"深度分析": result_str},
                            result_str
                        )
                        
                        if callback:
                            self.parent.after(0, lambda: callback(result))
                        return
                        
                    except Exception as e:
                        error_msg = f"快速分析失败: {str(e)}"
                        if callback:
                            self.parent.after(0, lambda: callback(None, error_msg))
                        return
                else:
                    # 完整模式：使用内置深度分析（不再依赖外部系统）
                    try:
                        from stock_data import get_stock_data
                        from MyTT import MACD, KDJ, RSI, BOLL
                        
                        df = get_stock_data(stock_code, count=100)
                        if df.empty or len(df) < 30:
                            raise Exception(f"无法获取 {stock_code} 的数据或数据不足")
                        
                        # 使用与快速模式相同的分析逻辑
                        close = df['close'].values
                        high = df['high'].values
                        low = df['low'].values
                        vol = df['vol'].values
                        
                        # 计算指标
                        df['ma5'] = df['close'].rolling(5).mean()
                        df['ma10'] = df['close'].rolling(10).mean()
                        df['ma20'] = df['close'].rolling(20).mean()
                        df['ma60'] = df['close'].rolling(60).mean()
                        
                        dif, dea, macd = MACD(close)
                        k, d, j = KDJ(close, high, low)
                        rsi = RSI(close, 14)
                        upper, mid, lower = BOLL(close)
                        
                        latest = df.iloc[-1]
                        last_date = df['datetime'].iloc[-1] if 'datetime' in df.columns else str(df.index[-1])
                        
                        # 生成完整分析报告
                        result_str = f"""【完整深度分析】
股票代码: {stock_code}
最新日期: {last_date}
最新价格: {latest['close']:.2f}

【均线系统】
5日均线: {latest['ma5']:.2f}
10日均线: {latest['ma10']:.2f}
20日均线: {latest['ma20']:.2f}
60日均线: {latest['ma60']:.2f}

【技术指标】
MACD: DIF={dif[-1]:.3f}, DEA={dea[-1]:.3f}, MACD={macd[-1]:.3f}
KDJ: K={k[-1]:.2f}, D={d[-1]:.2f}, J={j[-1]:.2f}
RSI(14): {rsi[-1]:.2f}
布林带: 上轨={upper[-1]:.2f}, 中轨={mid[-1]:.2f}, 下轨={lower[-1]:.2f}

【资金面】
成交量: {latest['vol']:,.0f}
"""
                        
                        class SimpleResult:
                            def __init__(self, code, analysis):
                                self.stock_code = code
                                self.stock_name = code
                                self.action = "完整分析完成"
                                self.analysis = analysis
                        
                        result = SimpleResult(stock_code, result_str)
                        
                        if callback:
                            self.parent.after(0, lambda: callback(result))
                            
                    except Exception as e:
                        error_msg = f"完整分析失败: {str(e)}"
                        if callback:
                            self.parent.after(0, lambda: callback(None, error_msg))
                    return
                    
            except Exception as e:
                error_msg = f"分析失败: {str(e)}"
                if callback:
                    self.parent.after(0, lambda: callback(None, error_msg))
        
        # 在新线程中运行分析
        self.analysis_thread = threading.Thread(target=run_analysis, daemon=True)
        self.analysis_thread.start()
    
    def analyze_stocks(self, stock_codes: list, api_key: str = None, model_type: str = 'gemini', callback=None, quick_mode: bool = True):
        """分析多只股票（内置实现，不再依赖外部系统）
        
        Args:
            stock_codes: 股票代码列表
            api_key: API密钥（可选，用于AI分析）
            model_type: 模型类型（gemini/openai/deepseek）
            callback: 回调函数
            quick_mode: 快速模式（默认True）
        """
        def run_analysis():
            try:
                from stock_data import get_stock_data
                from MyTT import MACD, KDJ, RSI, BOLL
                
                results = []
                
                for stock_code in stock_codes:
                    try:
                        df = get_stock_data(stock_code, count=60)
                        if df.empty or len(df) < 30:
                            continue
                        
                        close = df['close'].values
                        high = df['high'].values
                        low = df['low'].values
                        
                        # 计算基础指标
                        df['ma5'] = df['close'].rolling(5).mean()
                        df['ma10'] = df['close'].rolling(10).mean()
                        df['ma20'] = df['close'].rolling(20).mean()
                        
                        dif, dea, macd = MACD(close)
                        k, d, j = KDJ(close, high, low)
                        rsi = RSI(close, 14)
                        
                        latest = df.iloc[-1]
                        
                        # 生成简要分析
                        result_str = f"""股票代码: {stock_code}
最新价格: {latest['close']:.2f}
5日均线: {latest['ma5']:.2f}
10日均线: {latest['ma10']:.2f}
MACD: {macd[-1]:.3f}
KDJ-J: {j[-1]:.2f}
RSI: {rsi[-1]:.2f}
"""
                        
                        class SimpleResult:
                            def __init__(self, code, analysis):
                                self.stock_code = code
                                self.stock_name = code
                                self.action = "分析完成"
                                self.analysis = analysis
                        
                        results.append(SimpleResult(stock_code, result_str))
                        
                    except Exception as e:
                        print(f"分析 {stock_code} 失败: {e}")
                        continue
                
                if callback:
                    self.parent.after(0, lambda: callback(results))
                    
            except Exception as e:
                error_msg = f"批量分析失败: {str(e)}"
                if callback:
                    self.parent.after(0, lambda: callback(None, error_msg))
        
        self.analysis_thread = threading.Thread(target=run_analysis, daemon=True)
        self.analysis_thread.start()
    
    def show_analysis_result(self, result, title="AI分析结果"):
        """显示分析结果弹窗"""
        if result is None:
            messagebox.showerror("错误", "分析结果为空")
            return
        
        # 创建弹窗
        window = Toplevel(self.parent)
        window.title(title)
        window.geometry("700x500")
        window.configure(bg=self.colors['bg'])
        
        # 股票代码和名称
        header_frame = tk.Frame(window, bg=self.colors['bg_secondary'], height=60)
        header_frame.pack(fill='x', padx=10, pady=10)
        header_frame.pack_propagate(False)
        
        stock_code = getattr(result, 'stock_code', '未知')
        stock_name = getattr(result, 'stock_name', '未知')
        
        tk.Label(header_frame, text=f"{stock_code} {stock_name}", 
                font=('微软雅黑', 18, 'bold'),
                bg=self.colors['bg_secondary'], 
                fg=self.colors['text_highlight']).pack(side='left', padx=15, pady=10)
        
        # 操作建议
        action = getattr(result, 'action', '观望')
        action_color = self.colors['down'] if '卖出' in action or '减持' in action else \
                      self.colors['up'] if '买入' in action or '增持' in action else \
                      self.colors['accent']
        
        tk.Label(header_frame, text=action, 
                font=('微软雅黑', 14, 'bold'),
                bg=self.colors['bg_secondary'], 
                fg=action_color).pack(side='right', padx=15, pady=10)
        
        # 分析详情文本框
        text_frame = tk.Frame(window, bg=self.colors['bg'])
        text_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        text_widget = Text(text_frame, 
                          font=('微软雅黑', 11),
                          bg=self.colors['bg'],
                          fg=self.colors['text'],
                          relief='flat',
                          wrap='word',
                          padx=10,
                          pady=10)
        text_widget.pack(side='left', fill='both', expand=True)
        
        # 滚动条
        scrollbar = Scrollbar(text_frame, command=text_widget.yview)
        scrollbar.pack(side='right', fill='y')
        text_widget.config(yscrollcommand=scrollbar.set)
        
        # 填充分析内容
        content = getattr(result, 'analysis', str(result))
        text_widget.insert('1.0', content)
        text_widget.config(state='disabled')
        
        # 关闭按钮
        tk.Button(window, text="关闭", command=window.destroy,
                 bg=self.colors['accent'], fg='white',
                 font=('微软雅黑', 11),
                 relief='flat', cursor='hand2',
                 width=10).pack(pady=10)
    
    def is_available(self) -> bool:
        """检查深度分析模块是否可用"""
        try:
            # 检查核心依赖是否可用
            from stock_data import get_stock_data
            from MyTT import MACD, KDJ, RSI, BOLL
            return True
        except:
            return False
    
    # ==================== GUI集成便捷方法 ====================
    
    def quick_record_trade(self, stock_code: str, action: str, price: float, quantity: int):
        """快速记录交易(供GUI调用)
        
        Args:
            stock_code: 股票代码
            action: 买入/卖出
            price: 成交价格
            quantity: 成交数量
            
        Returns:
            dict: 交易记录结果
        """
        try:
            trade = self.record_trade(stock_code, action, price, quantity)
            return {'success': True, 'trade': trade}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_investment_summary(self):
        """获取投资摘要(供GUI显示)
        
        Returns:
            dict: 投资组合、预算、税务综合信息
        """
        try:
            return {
                'success': True,
                'portfolio': self.get_portfolio_summary(),
                'budget': self.get_budget_status(),
                'tax': self.calculate_tax_report()
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def check_can_trade(self, amount: float):
        """检查是否可以进行交易(预算检查)
        
        Args:
            amount: 交易金额
            
        Returns:
            bool: 是否有足够预算
        """
        return self.check_budget_before_trade(amount)
    
    # ==================== Polymarket 预测市场功能 ====================
    
    def get_polymarket_markets(self, keyword: str = None, limit: int = 5):
        """获取Polymarket预测市场数据
        
        Args:
            keyword: 搜索关键词(可选)
            limit: 返回数量
            
        Returns:
            dict: 市场数据
        """
        if not POLYMARKET_AVAILABLE:
            return {'success': False, 'error': 'Polymarket模块未安装'}
        
        try:
            client = PolymarketClient()
            
            if keyword:
                markets = client.search_markets(keyword, limit)
            else:
                markets = client.get_trending_markets(limit)
            
            return {
                'success': True,
                'markets': markets,
                'count': len(markets)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_polymarket_summary(self):
        """获取Polymarket市场摘要"""
        if not POLYMARKET_AVAILABLE:
            return {'success': False, 'error': 'Polymarket模块未安装'}
        
        try:
            client = PolymarketClient()
            summary = client.get_market_summary()
            
            return {
                'success': True,
                'summary': summary
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
